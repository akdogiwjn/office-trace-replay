import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NAMES = ('egrid', 'hr_metro', 'industry_productivity', 'irs_w4', 'sba1919')


def module(path, name='test_private_module'):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


class FrozenRecipes(unittest.TestCase):
    def test_all_dataset_locks_and_cli(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'replay.py'), '--validate-only'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in NAMES:
            self.assertIn(name + ' frozen recipe valid', result.stdout)

    def test_private_runtime_does_not_import_shared_workloads(self):
        for name in NAMES:
            case = ROOT / 'datasets' / name
            for path in [case / 'run.py', *list((case / 'scripts').rglob('*.py'))]:
                tree = ast.parse(path.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        self.assertNotIn(node.module, ('replay', 'compatibility', 'office_trace_bench'))
            self.assertFalse(any(p.is_symlink() for p in case.rglob('*')))

    def test_dataset_can_validate_without_repository_or_siblings(self):
        for name in ('egrid', 'irs_w4'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                case = Path(temp) / name
                shutil.copytree(ROOT / 'datasets' / name, case)
                process = subprocess.run([sys.executable, '-B', str(case / 'run.py'), '--validate-only'],
                                         cwd=temp, capture_output=True, text=True)
                self.assertEqual(process.returncode, 0, process.stderr)

    def test_no_generated_deliverables_restored_as_seed(self):
        for name in NAMES:
            seed = ROOT / 'datasets' / name / 'seed/output'
            self.assertEqual([p.name for p in seed.iterdir()] if seed.exists() else [],
                             ['workbook_features.json'] if name in NAMES[:3] else [])

    def test_helpers_and_skills_bound_to_captured_bytes(self):
        for name in NAMES:
            case = ROOT / 'datasets' / name
            source = json.loads((case / 'provenance.json').read_text())
            for helper in source['agent_helpers']:
                self.assertTrue(helper['revision_capture_verified'])
                self.assertEqual(hashlib.sha256((case / 'scripts' / helper['path']).read_bytes()).hexdigest(),
                                 helper['sha256'])
            if source['kind'] == 'xlsx':
                self.assertEqual(source['skill_recalc_sha256'],
                                 'cf419d15e02965aeaec17773c05b61303f7f520f67fa2696547e7da07502eac7')

    def test_each_run_preserves_both_trace_sources(self):
        for name in NAMES:
            for n in (1, 2):
                evidence = ROOT / 'datasets' / name / 'evidence' / f'round-{n}'
                self.assertTrue((evidence / 'trajectory.json').is_file())
                self.assertTrue((evidence / 'qualified-independent.json').is_file())
                self.assertTrue(any((evidence / 'code-objects').iterdir()))

    def test_xlsx_has_one_effective_build_recalc_and_cache_export(self):
        for name in NAMES[:3]:
            recipe = json.loads((ROOT / 'datasets' / name / 'recipe.json').read_text())
            calls = [x for p in recipe['phases'] for x in p['calls']]
            self.assertEqual(sum('recalc.py' in ' '.join(x['argv']) for x in calls), 1)
            self.assertEqual(sum(x['argv'][1] == 'export_xlsx_csv.py' for x in calls), 1)
            self.assertFalse(any('prepared_' in ' '.join(x['argv']) for x in calls))

    def test_pdf_check_log_and_record_scale_are_preserved(self):
        for name in NAMES[3:]:
            case = ROOT / 'datasets' / name
            recipe = json.loads((case / 'recipe.json').read_text())
            check = recipe['phases'][0]['calls'][0]
            self.assertEqual(check['stdout'], 'output/check_fillable_fields.log')
            self.assertIn('check_fillable_fields.log', recipe['required_outputs'])
            config = json.loads((case / 'scripts/replay-config.json').read_text())
            self.assertEqual(config['requirements']['record_count'], 10)

    def test_missing_or_tampered_file_rejected(self):
        runner = module(ROOT / 'datasets/egrid/run.py', 'private_runner')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'egrid'; root.mkdir()
            (root / 'one.txt').write_text('bad')
            (root / 'lock.json').write_text(json.dumps({'files': {'one.txt': '0' * 64}}))
            with self.assertRaisesRegex(ValueError, 'frozen file mismatch'):
                runner.validate(root)
            (root / 'one.txt').unlink()
            with self.assertRaisesRegex(ValueError, 'frozen file mismatch'):
                runner.validate(root)

    def test_host_execution_is_rejected_before_environment_or_reset(self):
        runner = module(ROOT / 'datasets/egrid/run.py', 'private_host_guard')
        with patch.dict('os.environ', {}, clear=True), patch.object(runner, 'environment') as probe:
            with self.assertRaisesRegex(ValueError, 'disposable container'):
                runner.main([])
            probe.assert_not_called()

    def test_dispatcher_preflight_failure_never_starts_workload(self):
        entry = module(ROOT / 'replay.py', 'public_entry')
        with patch.object(entry.subprocess, 'call', side_effect=[0, 1]) as call:
            self.assertEqual(entry.main(['--dataset', 'egrid', '--dataset', 'hr_metro']), 1)
            self.assertEqual(call.call_count, 2)
            self.assertTrue(all('--validate-only' in c.args[0] for c in call.call_args_list))

    def test_audit_detects_output_mutation(self):
        runner = module(ROOT / 'datasets/egrid/run.py', 'private_audit_guard')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); ws = root / 'workspace'; (ws / 'output').mkdir(parents=True)
            report = root / 'reports'; report.mkdir()
            output = ws / 'output/report.xlsx'; output.write_bytes(b'original')
            def mutate(*args, **kwargs): output.write_bytes(b'changed')
            with patch.object(runner, 'run_command', side_effect=mutate):
                result = runner.audit({}, ws, report)
            self.assertEqual(result['status'], 'failed')
            self.assertFalse(result['unchanged'])

    def test_command_nonzero_is_not_masked_by_shell(self):
        runner = module(ROOT / 'datasets/egrid/run.py', 'private_command')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(RuntimeError, 'exit 7'):
                runner.run_command([sys.executable, '-c', 'raise SystemExit(7)'], root,
                                   root / 'out', root / 'err', 10, {})


class CacheCSV(unittest.TestCase):
    def fixture(self, root, name, missing=False):
        from openpyxl import Workbook
        case = ROOT / 'datasets' / name
        contract = json.loads((case / 'scripts/csv-contract.json').read_text())
        output = root / 'output'; output.mkdir()
        book = Workbook(); sheet = book.active; sheet.title = contract['sheet']
        values = {'B5': 12.5, 'B6': 42, 'B7': 3.36, 'B8': 0.5, 'B9': 'PASS',
                  'B15': 12.5, 'B16': 42}
        for address, value in values.items():
            sheet[address] = '=1+1' if address != 'B9' else value
        path = output / contract['workbook']; book.save(path); book.close()
        # Inject tiny fixture caches only; never alter any real benchmark file.
        with ZipFile(path) as archive:
            parts = {n: archive.read(n) for n in archive.namelist()}
        xml = ET.fromstring(parts['xl/worksheets/sheet1.xml'])
        ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
        for cell in xml.iter(ns + 'c'):
            address = cell.attrib['r']
            if address not in values or address == 'B9' or (missing and address == 'B5'):
                continue
            value_node = cell.find(ns + 'v')
            if value_node is None:
                value_node = ET.SubElement(cell, ns + 'v')
            value_node.text = str(values[address])
        parts['xl/worksheets/sheet1.xml'] = ET.tostring(xml, encoding='utf-8')
        with ZipFile(path, 'w', ZIP_DEFLATED) as archive:
            for n, content in parts.items(): archive.writestr(n, content)
        return contract, path

    def test_all_three_exports_use_caches_without_modifying_workbook(self):
        for name in NAMES[:3]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); contract, workbook = self.fixture(root, name)
                export = module(ROOT / 'datasets' / name / 'scripts/export_xlsx_csv.py', 'csv_' + name)
                before = workbook.read_bytes()
                export.export(root, contract); export.validate_csv(root, contract)
                self.assertEqual(workbook.read_bytes(), before)
                self.assertIn('12.5', (root / 'output' / contract['exports'][0]['filename']).read_text())

    def test_missing_cache_fails_before_publishing_any_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); contract, _ = self.fixture(root, 'egrid', missing=True)
            export = module(ROOT / 'datasets/egrid/scripts/export_xlsx_csv.py', 'missing_cache')
            with self.assertRaisesRegex(ValueError, 'missing/error cache'):
                export.export(root, contract)
            self.assertEqual(list((root / 'output').glob('*.csv')), [])

    def test_corrupt_csv_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); contract, _ = self.fixture(root, 'egrid')
            export = module(ROOT / 'datasets/egrid/scripts/export_xlsx_csv.py', 'corrupt_csv')
            export.export(root, contract)
            path = root / 'output' / contract['exports'][0]['filename']
            path.write_text(path.read_text().replace('12.5', '999'))
            with self.assertRaisesRegex(ValueError, 'CSV cache mismatch'):
                export.validate_csv(root, contract)

    def test_numeric_serialization_tolerance_and_nonfinite_rejected(self):
        export = module(ROOT / 'datasets/egrid/scripts/export_xlsx_csv.py', 'csv_numbers')
        self.assertTrue(export.same('61430.0', 61430))
        self.assertFalse(export.same('NaN', 1))
        self.assertFalse(export.same('FAIL', 'PASS'))


class PDFSummary(unittest.TestCase):
    def fixture(self, root):
        requirements = {'record_count': 1, 'page_count': 1, 'protected_blank': ['SSN']}
        (root / 'replay-config.json').write_text(json.dumps(dict(kind='pdf', requirements=requirements,
             form='fixture.pdf', source_run_id='fixture', dataset_id='irs_w4')))
        output = root / 'output'
        for d in ['filled', 'rendered/template', 'rendered/one', 'field_values', 'logs']:
            (output / d).mkdir(parents=True)
        for file in ['filled/one.pdf', 'rendered/template/page_1.png', 'rendered/one/page_1.png']:
            (output / file).write_text('inventory fixture, not a real PDF/PNG')
        (output / 'field_values/one.json').write_text('[{"field_id":"name","value":"Synthetic"}]')
        (output / 'logs/operation_counts.json').write_text('{"fill":1,"render":1,"failures":[]}')
        for file in ['fill_one.log', 'render_one.log']:
            (output / 'logs' / file).write_text('[exit 0]\n')

    def test_summary_has_privacy_field_required_by_actual_verifier(self):
        summary = module(ROOT / 'datasets/irs_w4/scripts/write_pdf_batch_summary.py', 'pdf_summary')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            summary.__file__ = str(root / 'summary.py')
            summary.main()
            data = json.loads((root / 'output/batch_summary.json').read_text())
            self.assertTrue(data['ssn_and_signatures_left_blank'])
            self.assertEqual(data['render_script_invocations'], 2)

    def test_protected_mapping_rejected(self):
        summary = module(ROOT / 'datasets/irs_w4/scripts/write_pdf_batch_summary.py', 'pdf_protected')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            (root / 'output/field_values/one.json').write_text('[{"field_id":"SSN","value":"bad"}]')
            summary.__file__ = str(root / 'summary.py')
            with self.assertRaisesRegex(ValueError, 'protected field'):
                summary.main()


if __name__ == '__main__':
    unittest.main()
