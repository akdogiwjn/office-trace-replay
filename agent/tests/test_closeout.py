import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED
import xml.etree.ElementTree as ET

import test_replay as fixtures
from test_replay import module

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'datasets'


class TraceOrigins(unittest.TestCase):
    def setUp(self):
        self.compiler = module(ROOT / 'tools/import_traces.py', 'origin_compiler')

    def test_mentions_and_inline_strings_are_not_execution(self):
        for text in ('cat /skills/scripts/extract.py',
                     "echo 'python3 /skills/scripts/extract.py'",
                     "cat <<'EOF'\npython3 /skills/scripts/extract.py input\nEOF\n",
                     'python3 -c "print(\'scripts/extract.py x\')"',
                     'python3 -m example scripts/extract.py'):
            with self.subTest(text=text):
                self.assertFalse(self.compiler.executes_script(text, 'extract.py'))
        for text in ('cd /work && python3 /skills/scripts/extract.py input output',
                     '/venv/bin/python3 -B scripts/extract.py input',
                     'cat scripts/extract.py\npython3 scripts/extract.py input',
                     "cat scripts/extract.py; python3 'scripts/extract.py' input"):
            self.assertTrue(self.compiler.executes_script(text, 'extract.py'))

    def test_real_pdf_origins_match_executed_events(self):
        for name in ('irs_w4', 'sba1919'):
            case = CASES / name
            events = json.loads((case / 'evidence/round-1/tool_events.json').read_text())['events']
            recipe = json.loads((case / 'recipe.json').read_text())
            for call, expected in zip(recipe['phases'][0]['calls'], (8, 9, 10)):
                script = Path(call['argv'][1]).name
                self.assertEqual(self.compiler.script_event(events, script), expected)
                self.assertEqual(call['origin'], self.compiler.source_call(events, expected, recipe['source_run_id']))


class LoopCSV(unittest.TestCase):
    def fixture(self, root, name):
        contract, workbook = fixtures.CacheCSV().fixture(root, name)
        verifier = module(CASES / name / 'scripts/verify_xlsx_enhanced.py', 'loop_csv_' + name)
        config = copy.deepcopy(verifier.CONFIG)
        values = {'B5': 12.5, 'B6': 42, 'B7': 3.36, 'B8': 0.5, 'B9': 'PASS', 'B15': 12.5, 'B16': 42}
        config['numeric_formula_cells'] = ['B5', 'B6', 'B7', 'B8', 'B15', 'B16']
        config['lookup_values'] = {}
        config['metric_values'] = {key: values[spec['cell']] for key, spec in config['features']['metrics'].items()}
        config['projection_values'] = {key: values[spec['cell']] for key, spec in config['features']['scenario']['projections'].items()}
        verifier.CONFIG = config
        exporter = module(CASES / name / 'scripts/export_xlsx_csv.py', 'loop_export_' + name)
        exporter.export(root, contract)
        (root / 'output/formula_recalc.json').write_text(json.dumps(dict(status='success', total_errors=0, total_formulas=999)))
        return verifier, contract, workbook

    def check(self, verifier, root):
        # Exercise the real cached-load/CSV integration; formula/style tests are
        # unrelated to this tiny cache fixture and remain in the original tests.
        with patch.object(verifier, 'verify_formula_workbook'):
            with patch.object(verifier, 'load_workbook', wraps=verifier.load_workbook) as load:
                result = verifier.verify_workspace(root)
        self.assertEqual(load.call_count, 1)
        self.assertEqual(load.call_args.kwargs, dict(data_only=True, read_only=True))
        return result

    def test_all_three_reuse_cached_load_and_do_not_modify_workbook(self):
        for name in ('egrid', 'hr_metro', 'industry_productivity'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); verifier, contract, workbook = self.fixture(root, name)
                before = workbook.read_bytes()
                self.assertEqual(self.check(verifier, root)['status'], 'success')
                self.assertEqual(workbook.read_bytes(), before)
                path = root / 'output' / contract['exports'][0]['filename']
                path.write_text(path.read_text().replace('12.5', '999'))
                result = self.check(verifier, root)
                self.assertEqual(result['failures'], ['csv_matches_current_cache:' + path.name])

    def test_missing_header_label_and_nonfinite_values_fail(self):
        for change in ('missing', 'header', 'label', 'nan'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); verifier, contract, workbook = self.fixture(root, 'egrid')
                path = root / 'output' / contract['exports'][0]['filename']
                text = path.read_text()
                if change == 'missing': path.unlink()
                elif change == 'header': path.write_text(text.replace(contract['exports'][0]['header'][0], 'wrong', 1))
                elif change == 'label': path.write_text(text.replace(contract['exports'][0]['rows'][0]['label'], 'wrong', 1))
                else: path.write_text(text.replace('12.5', 'NaN', 1))
                self.assertIn('csv_matches_current_cache:' + path.name, self.check(verifier, root)['failures'])

    def set_numeric_formula_cache(self, workbook, kind, value):
        # B20 is outside KPI/CSV checks, so only the numeric-cache guard can
        # reject it. Keep a real formula and change only its tiny fixture cache.
        with ZipFile(workbook) as archive:
            parts = {name: archive.read(name) for name in archive.namelist()}
        ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
        xml = ET.fromstring(parts['xl/worksheets/sheet1.xml'])
        xml.find(ns + 'dimension').set('ref', 'A1:B20')
        row = ET.SubElement(xml.find(ns + 'sheetData'), ns + 'row', r='20')
        cell = ET.SubElement(row, ns + 'c', r='B20', t=kind)
        ET.SubElement(cell, ns + 'f').text = '1+1'
        if value is not None:
            ET.SubElement(cell, ns + 'v').text = value
        parts['xl/worksheets/sheet1.xml'] = ET.tostring(xml, encoding='utf-8')
        with ZipFile(workbook, 'w', ZIP_DEFLATED) as archive:
            for name, content in parts.items():
                archive.writestr(name, content)

    def test_numeric_formula_caches_reject_text_boolean_missing_and_nonfinite(self):
        for name in ('egrid', 'hr_metro', 'industry_productivity'):
            for kind, value in (('str', 'not-a-number'), ('str', '12.5'),
                                ('str', ''), ('b', '1'), ('n', None),
                                ('n', '1e999'), ('n', '-1e999')):
                with self.subTest(dataset=name, kind=kind, value=value), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp); verifier, _, workbook = self.fixture(root, name)
                    verifier.CONFIG['numeric_formula_cells'].append('B20')
                    self.set_numeric_formula_cache(workbook, kind, value)
                    before = workbook.read_bytes()
                    result = self.check(verifier, root)
                    self.assertEqual(result['status'], 'failed')
                    self.assertIn('cached_numeric_values', result['failures'])
                    self.assertEqual(workbook.read_bytes(), before)

    def test_numeric_formula_caches_accept_finite_zero_negative_and_float(self):
        for name in ('egrid', 'hr_metro', 'industry_productivity'):
            for value in ('0', '-3', '2.5'):
                with self.subTest(dataset=name, value=value), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp); verifier, _, workbook = self.fixture(root, name)
                    verifier.CONFIG['numeric_formula_cells'].append('B20')
                    self.set_numeric_formula_cache(workbook, 'n', value)
                    before = workbook.read_bytes()
                    self.assertEqual(self.check(verifier, root)['status'], 'success')
                    self.assertEqual(workbook.read_bytes(), before)

    def test_generator_keeps_source_verifiers_immutable(self):
        compiler = module(ROOT / 'tools/import_traces.py', 'loop_compiler')
        for case in (CASES / n for n in ('egrid', 'hr_metro', 'industry_productivity')):
            source = case / 'seed/input/verify_xlsx_enhanced.py'
            original = json.loads((case / 'provenance.json').read_text())
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                             original['original_input_hashes']['input/verify_xlsx_enhanced.py'])
            self.assertEqual(compiler.adapted_loop_verifier(source.read_text()),
                             (case / 'scripts/verify_xlsx_enhanced.py').read_text())


class IterationRecords(unittest.TestCase):
    def fixture(self, root):
        runner = module(CASES / 'egrid/run.py', 'iteration_closeout')
        workspace = root / 'workspace'; (workspace / 'output').mkdir(parents=True)
        (workspace / 'output/business_verification.json').write_text('{"status":"success","failures":[]}')
        folder = root / 'iteration-0001'; folder.mkdir()
        recipe = dict(dataset_id='fixture', source_run_id='original-run', mode='effective-tool-chain',
                      workspace=str(workspace), required_outputs=['business_verification.json'],
                      phases=[dict(id='P01', calls=[dict(argv=['{python}', '-c', 'pass'], origin={'type':'fixture'})])])
        return runner, workspace, folder, recipe

    def test_archive_begins_after_both_roi_ends(self):
        with tempfile.TemporaryDirectory() as temp:
            runner, ws, folder, recipe = self.fixture(Path(temp))
            stamps = []
            original = runner.shutil.copytree
            def archive(*a, **kw):
                stamps.append(time.monotonic_ns())
                return original(*a, **kw)
            with patch.object(runner, 'prepare', return_value=(ws, {})), patch.object(runner, 'run_command'), \
                    patch.object(runner.shutil, 'copytree', side_effect=archive):
                result = runner.run_iteration(recipe, 1, folder, 'document-oe')
            self.assertEqual(result['status'], 'success')
            marks = result['boundaries']
            self.assertEqual([(x['scope'],x['event']) for x in marks],
                [('loop_including_reset','start'),('workflow','start'),('workflow','end'),
                 ('loop_including_reset','end'),('archive_excluded','start'),('archive_excluded','end')])
            self.assertGreater(stamps[0], marks[3]['monotonic_ns'])
            self.assertEqual([json.loads(x) for x in (folder / 'roi.jsonl').read_text().splitlines()], marks)

    def test_archive_failure_preserves_workload_success_or_original_error(self):
        for failed in (False, True):
            with self.subTest(failed=failed), tempfile.TemporaryDirectory() as temp:
                runner, ws, folder, recipe = self.fixture(Path(temp))
                with patch.object(runner, 'prepare', return_value=(ws, {})), \
                        patch.object(runner, 'run_command', side_effect=ValueError('primary-workload-error') if failed else None), \
                        patch.object(runner.shutil, 'copytree', side_effect=PermissionError('archive denied')):
                    result = runner.run_iteration(recipe, 1, folder, 'document-oe')
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['archive_status'], 'failed')
                self.assertEqual(result['workload_status'], 'failed' if failed else 'success')
                self.assertIn('archive denied', result['archive_error'])
                if failed: self.assertIn('primary-workload-error', result['error'])
                self.assertEqual(json.loads((folder / 'iteration.json').read_text()), result)

    def test_record_publication_failure_gets_emergency_failed_record(self):
        with tempfile.TemporaryDirectory() as temp:
            runner, ws, folder, recipe = self.fixture(Path(temp)); original = runner.write
            def write(path, value):
                if Path(path).name == 'iteration.json' and value['status'] == 'success':
                    raise OSError('atomic publish failed')
                original(path, value)
            with patch.object(runner, 'prepare', return_value=(ws, {})), patch.object(runner, 'run_command'), \
                    patch.object(runner, 'write', side_effect=write):
                result = runner.run_iteration(recipe, 1, folder, 'document-oe')
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['workload_status'], 'success')
            self.assertIn('atomic publish failed', result['record_error'])
            self.assertEqual(json.loads((folder / 'iteration.emergency.json').read_text())['status'], 'failed')

    def test_missing_start_marker_stops_before_reset_or_workload(self):
        with tempfile.TemporaryDirectory() as temp:
            runner, ws, folder, recipe = self.fixture(Path(temp))
            original = runner.boundary
            def boundary(*args):
                mark = original(*args)
                if args[-2:] == ('loop_including_reset','start'):
                    mark['record_error'] = 'marker write failed'
                return mark
            with patch.object(runner,'boundary',side_effect=boundary), patch.object(runner,'prepare') as prepare, \
                    patch.object(runner,'run_command') as call, patch.object(runner.shutil,'copytree') as archive:
                result=runner.run_iteration(recipe,1,folder,'document-oe')
            prepare.assert_not_called();call.assert_not_called();archive.assert_not_called()
            self.assertEqual(result['status'],'failed')
            self.assertEqual(result['measurement_status'],'failed')
            self.assertEqual(result['archive_status'],'skipped_before_workspace_ready')

    def test_summary_publication_failure_is_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            runner=module(CASES/'egrid/run.py','summary_persistence')
            path=Path(temp)/'summary.json';path.write_text('{"status":"in_progress"}')
            with patch.object(runner,'write',side_effect=OSError('summary denied')):
                error=runner.persist(path,dict(status='success',completed=1,workload_successes=1))
            self.assertIn('summary denied',error)
            emergency=json.loads((path.parent/'summary.emergency.json').read_text())
            self.assertEqual(emergency['status'],'failed')
            self.assertEqual(emergency['workload_successes'],1)

    def test_main_reports_archive_failure_and_stops_before_next_iteration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); runner, ws, folder, recipe = self.fixture(root)
            real_exists = Path.exists
            def exists(path): return True if str(path) == '/.dockerenv' else real_exists(path)
            with patch.dict(os.environ, {'OFFICE_AGENT_REPLAY_CONTAINER':'1'}), \
                    patch.object(runner.Path, 'exists', exists), patch.object(runner, 'configure_runtime'), \
                    patch.object(runner, 'validate', return_value=recipe), patch.object(runner, 'environment', return_value={}), \
                    patch.object(runner, 'snapshot_context', return_value={'container':{'status':'missing','actual_image_id':'unknown'}}), \
                    patch.object(runner, 'prepare', return_value=(ws, {})), patch.object(runner, 'run_command') as calls, \
                    patch.object(runner.shutil, 'copytree', side_effect=OSError('archive failed')):
                code = runner.main(['--loops','2','--results-dir',str(root / 'results')])
            self.assertEqual(code, 1); self.assertEqual(calls.call_count, 1)
            summary = json.loads(next((root / 'results').glob('fixture/*/summary.json')).read_text())
            self.assertEqual(summary['status'], 'failed')
            self.assertEqual(summary['workload_successes'], 1)
            self.assertEqual(summary['successes'], 0)
            self.assertEqual(summary['completed'], 1)

    def test_context_copies_freeze_material_and_validates_inspect_and_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); runner = module(CASES / 'egrid/run.py', 'context_snapshot')
            case = root / 'case'; case.mkdir()
            for name in ('lock.json','provenance.json','recipe.json','environment.json','replay-environment.json'):
                (case / name).write_text('{}\n')
            evidence = root / 'host'; evidence.mkdir()
            inspect_path = evidence / 'container-inspect.before.json'
            data = [dict(Id='a'*64, Image='sha256:'+'b'*64, Config={'Hostname':os.uname().nodename})]
            inspect_path.write_text(json.dumps(data))
            plan = evidence / 'launch-plan.json'
            plan.write_text(json.dumps({'dataset_locks':{'fixture':hashlib.sha256((case / 'lock.json').read_bytes()).hexdigest()}}))
            dest = root / 'results'; dest.mkdir()
            with patch.object(runner, 'HERE', case):
                binding = runner.snapshot_context({'dataset_id':'fixture','source_run_id':'source'},dest,inspect_path)
                self.assertEqual(binding['container']['status'],'host_inspect_bound')
                for name, sha in binding['files'].items():
                    self.assertEqual(hashlib.sha256((dest / 'context' / name).read_bytes()).hexdigest(),sha)
                plan.write_text('{"dataset_locks":{"fixture":"wrong"}}')
                bad = root / 'bad'; bad.mkdir()
                with self.assertRaisesRegex(ValueError,'differs from host launch plan'):
                    runner.snapshot_context({'dataset_id':'fixture','source_run_id':'source'},bad,inspect_path)
                data[0]['Config']['Hostname']='different-container';inspect_path.write_text(json.dumps(data))
                bad2 = root / 'bad2';bad2.mkdir()
                with self.assertRaisesRegex(ValueError,'hostname does not match'):
                    runner.snapshot_context({'dataset_id':'fixture','source_run_id':'source'},bad2,inspect_path)
                bad3 = root/'bad3';bad3.mkdir()
                with self.assertRaisesRegex(ValueError,'inspect file is missing'):
                    runner.snapshot_context({'dataset_id':'fixture','source_run_id':'source'},bad3,root/'missing.json')


class HostLaunch(unittest.TestCase):
    def args(self, root):
        import argparse
        return argparse.Namespace(results_dir=root, docker_host='unix:///fake',docker_image='fixture:installed',
                                  loops=1,runtime='document-oe')

    def test_create_inspect_then_start_and_retain_container(self):
        entry = module(ROOT / 'replay.py','host_launch')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); commands=[]; cid='a'*64
            def command(argv, **kw):
                commands.append(argv)
                if 'create' in argv: return subprocess.CompletedProcess(argv,0,cid+'\n','')
                if 'inspect' in argv:
                    after = any('start' in x for x in commands)
                    data=[dict(Id=cid,Image='sha256:'+'b'*64,Config={'Hostname':cid[:12]},
                               State={'ExitCode':0,'Running':False,'StartedAt':'2026-01-01' if after else '0001-01-01'})]
                    return subprocess.CompletedProcess(argv,0,json.dumps(data),'')
                self.assertTrue(next((root / '.launch').glob('*/container-inspect.before.json')).is_file())
                return subprocess.CompletedProcess(argv,0)
            with patch.object(entry.subprocess,'run',side_effect=command):
                self.assertEqual(entry.launch_container(self.args(root),['egrid']),0)
            create=commands[0]
            self.assertIn('--pull=never',create);self.assertIn('none',create)
            self.assertTrue(any('target=/run/office-replay,readonly' in x for x in create))
            self.assertFalse(any('rm' in x for x in commands))
            record=json.loads(next((root / '.launch').glob('*/launch-record.json')).read_text())
            self.assertEqual(record['status'],'success');self.assertTrue(record['container_started'])
            for name,sha in record['evidence_files'].items():
                folder=next((root / '.launch').iterdir())
                self.assertEqual(hashlib.sha256((folder/name).read_bytes()).hexdigest(),sha)

    def test_inspect_failure_never_starts_container_and_is_persisted(self):
        entry=module(ROOT / 'replay.py','host_launch_fail')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);commands=[]
            def command(argv,**kw):
                commands.append(argv)
                if 'create' in argv:return subprocess.CompletedProcess(argv,0,'a'*64,'')
                raise subprocess.CalledProcessError(1,argv,stderr='inspect denied')
            with patch.object(entry.subprocess,'run',side_effect=command):
                self.assertEqual(entry.launch_container(self.args(root),['egrid']),1)
            self.assertFalse(any('start' in x for x in commands))
            record=json.loads(next((root / '.launch').glob('*/launch-record.json')).read_text())
            self.assertEqual(record['status'],'failed');self.assertFalse(record['container_started'])


if __name__ == '__main__':
    unittest.main()
