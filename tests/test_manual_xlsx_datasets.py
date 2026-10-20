"""Small fixtures for the two manually adapted XLSX registrations."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import Workbook, load_workbook

from compatibility.tools.run_xlsx_helper_atomic import redirect_target
from compatibility.helpers.hr_metro_build import TARGET as HR_TARGET
from compatibility.helpers.retail_online_build import TARGET as RETAIL_TARGET
from replay import freeze
from replay.common import digest, write
from scripts.compile_compatible import (MANUAL_XLSX, _compile_manual_xlsx,
                                        main as compile_main, preserved_suite_entries)
from scripts.prepare_manual_xlsx_assets import select_hr_metro, select_retail_rows
from compatibility.verification.verify import Checks


class ManualBusinessScopeTests(unittest.TestCase):
    def test_hr_scope_keeps_exact_area_and_major_level_and_counts_suppression(self):
        headers = ['AREA', 'AREA_TITLE', 'AREA_TYPE', 'NAICS', 'I_GROUP', 'OWN_CODE',
                   'O_GROUP', 'OCC_CODE', 'OCC_TITLE', 'TOT_EMP', 'A_MEAN',
                   'H_MEDIAN', 'H_MEAN', 'A_MEDIAN']
        rows = [[
            '35620', 'New York-Newark-Jersey City, NY-NJ', '4', '000000',
            'cross-industry', '1235', 'total', '00-0000', 'All occupations',
            1000000, 80000, 30, 40, 60000,
        ]]
        for i in range(5):
            rows.append(['35620', 'New York-Newark-Jersey City, NY-NJ', '4',
                         '000000', 'cross-industry', '1235', 'major',
                         f'{i:02d}-0000', f'Group {i}', 500 - i, 0, 'N' if i == 4 else 20,
                         0, '*'])
        rows.extend([
            ['00000', 'United States', '1', '000000', 'cross-industry', '1235',
             'total', '00-0000', 'National total', 99999999, 1, 1, 1, 1],
            ['35620', 'New York-Newark-Jersey City, NY-NJ', '4', '000000',
             'cross-industry', '1235', 'detailed', '11-1011', 'Detailed row',
             999999, 1, 1, 1, 1],
        ])
        result = select_hr_metro(rows, headers)
        self.assertEqual(result['selected_record_count'], 7)
        self.assertEqual(result['metric_values']['total_employment'], 1000000)
        self.assertEqual(result['major_group_count'], 5)
        self.assertEqual(result['major_group_suppressed_employment_count'], 0)
        self.assertEqual(result['suppression_marker_counts']['H_MEDIAN'], 1)
        self.assertEqual(len(result['chart_rows']), 5)

    def test_retail_uses_transaction_lines_and_excludes_cancel_return_missing_fields(self):
        headers = ['InvoiceNo', 'Quantity', 'UnitPrice', 'InvoiceDate', 'CustomerID']
        rows = [
            ('100', 2, 3.0, datetime(2010, 1, 4), None),
            ('100', 1, 4.0, datetime(2010, 2, 4), 12),
            ('C100', 5, 2.0, datetime(2010, 2, 5), 12),
            ('101', -1, 2.0, datetime(2010, 2, 5), 12),
            ('102', 1, 0.0, datetime(2010, 2, 5), 12),
            ('103', 1, 2.0, None, 12),
            (None, 1, 2.0, datetime(2010, 2, 5), 12),
        ]
        prepared = select_retail_rows(headers, rows)
        self.assertEqual(prepared['eligible_line_count'], 2)
        self.assertEqual(prepared['gross_eligible_sales_gbp'], 10.0)
        self.assertEqual(prepared['distinct_invoice_ids'], {'100'})
        self.assertEqual(prepared['eligible_lines_missing_customer_id'], 1)
        self.assertEqual(prepared['exclusion_counts']['cancelled_invoice'], 1)
        self.assertEqual(prepared['exclusion_counts']['nonpositive_quantity'], 1)
        self.assertEqual(prepared['exclusion_counts']['nonpositive_unit_price'], 1)
        self.assertEqual(prepared['monthly_2010_sales_gbp'][0:2], [6.0, 4.0])
class ManualBindingAndGenerationTests(unittest.TestCase):
    def test_helpers_have_redirectable_targets(self):
        root = Path(__file__).resolve().parents[1]
        for name, expected in (('hr_metro_build.py', HR_TARGET),
                               ('retail_online_build.py', RETAIL_TARGET)):
            text = (root / 'compatibility/helpers' / name).read_text()
            rewritten = redirect_target(text, Path('/tmp/redirected.xlsx'))
            self.assertIn("TARGET = '/tmp/redirected.xlsx'", rewritten)
            self.assertEqual(text.count('TARGET ='), 1)
            self.assertIn(expected, text)

    def _manual_fixture(self, root):
        prompt = root / 'prompts/xlsx.txt'
        prompt.parent.mkdir(parents=True)
        prompt.write_text('fixture prompt')
        asset = root / 'assets/cases/manual/source/datasets/xlsx/manual'
        (asset / 'input').mkdir(parents=True)
        source_input = asset / 'input/source.xlsx'
        source_input.write_bytes(b'official fixture bytes')
        expected = asset / 'expected.json'
        expected.write_text('{}\n')
        complexity = asset / 'complexity.json'
        complexity.write_text('{}\n')
        summary = asset / 'content-summary.json'
        summary.write_text('{}\n')
        ref_recipe = root / 'compatibility/recipes/reference.json'
        ref_recipe.parent.mkdir(parents=True)
        ref_recipe.write_text('{}\n')
        ref_helper = root / 'compatibility/helpers/reference.py'
        ref_helper.parent.mkdir(parents=True)
        ref_helper.write_text('pass\n')
        input_hash = digest(source_input)
        provenance = {
            'dataset_id': 'manual', 'origin_type': 'manual_workflow_adaptation',
            'agent_generated': False, 'requires_llm': False,
            'sha256': input_hash, 'status': 'registered_not_run',
            'references': [{'recipe_path': str(ref_recipe.relative_to(root)),
                            'recipe_sha256': digest(ref_recipe),
                            'helper_path': str(ref_helper.relative_to(root)),
                            'helper_sha256': digest(ref_helper)}],
        }
        provenance_path = asset / 'provenance.json'
        provenance_path.write_text(json.dumps(provenance))
        manifest = {
            'schema_version': 'office-dataset-v2', 'workload_contract': 'spreadsheet-semantic-v3',
            'kind': 'xlsx', 'dataset_id': 'manual', 'task': 'fixture',
            'runtime_case': 'OFFICE-XLSX-MANUAL', 'workbook': 'source.xlsx',
            'output_workbook': 'output.xlsx', 'input_files': {'input/source.xlsx': input_hash},
            'expected_file': 'expected.json', 'expected_sha256': digest(expected),
            'prompt_template': 'xlsx.txt', 'prompt_template_sha256': digest(prompt),
            'trace_rules': [], 'requirements': {'metrics': [], 'scenario': {}, 'charts': []},
            'analysis_metadata': {'complexity.json': digest(complexity),
                                  'content-summary.json': digest(summary),
                                  'provenance.json': digest(provenance_path)},
            'origin_type': 'manual_workflow_adaptation', 'agent_generated': False,
            'requires_llm': False,
        }
        manifest_path = asset / 'manifest.json'
        manifest_path.write_text(json.dumps(manifest))
        helper = root / 'compatibility/helpers/manual.py'
        helper.write_text('TARGET = "output.xlsx"\n')
        recipe = {
            'dataset_id': 'manual', 'origin_type': 'manual_workflow_adaptation',
            'classification': 'manual_workflow_adaptation', 'agent_generated': False,
            'requires_llm': False, 'input_hashes': {'input/source.xlsx': input_hash},
            'manual_source': {
                'record_path': str(provenance_path.relative_to(root)),
                'record_sha256': digest(provenance_path),
                'manifest_path': str(manifest_path.relative_to(root)),
                'manifest_sha256': digest(manifest_path),
                'helper_path': str(helper.relative_to(root)), 'helper_sha256': digest(helper),
                'references': provenance['references'],
            },
        }
        return asset, source_input, helper, recipe

    def test_manual_origin_is_explicit_and_rejects_input_or_helper_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            asset, input_path, helper, recipe = self._manual_fixture(root)
            with patch('compatibility.verification.contracts.ROOT', root):
                self.assertEqual(freeze.validate_recipe_origin(recipe, root),
                                 'manual_workflow_adaptation')
                unknown = dict(recipe, origin_type='not_a_supported_origin')
                with self.assertRaisesRegex(ValueError, 'unknown or missing workflow origin'):
                    freeze.validate_recipe_origin(unknown, root)
                input_path.write_bytes(b'tampered')
                with self.assertRaisesRegex(ValueError, 'input hash mismatch'):
                    freeze.validate_recipe_origin(recipe, root)
                input_path.write_bytes(b'official fixture bytes')
                helper.write_text('TARGET = "changed.xlsx"\n')
                with self.assertRaisesRegex(ValueError, 'helper hash mismatch'):
                    freeze.validate_recipe_origin(recipe, root)

    def test_selective_compile_preserves_entries_for_unselected_datasets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'compatibility').mkdir()
            (root / 'legacy/document-oe').mkdir(parents=True)
            (root / 'compatibility/contract.json').write_text('{}\n')
            (root / 'legacy/document-oe/lock.json').write_text('{}\n')
            write(root / 'compatibility/suite.json', {'entries': [
                {'dataset_id': 'hr', 'recipe_path': 'old.json'},
                {'dataset_id': 'retail', 'recipe_path': 'old2.json'},
            ]})
            with patch('scripts.compile_compatible._compile_manual_xlsx',
                       side_effect=lambda _root, dataset, index: index['entries'].append(
                           {'dataset_id': dataset, 'recipe_path': dataset + '.json'})):
                compile_main(root=root, datasets=['hr_metro', 'retail_online'])
            result = json.loads((root / 'compatibility/suite.json').read_text())
            self.assertEqual({entry['dataset_id'] for entry in result['entries']},
                             {'hr', 'retail', 'hr_metro', 'retail_online'})
        self.assertEqual({e['dataset_id'] for e in preserved_suite_entries(
            {'entries': [{'dataset_id': 'hr'}, {'dataset_id': 'retail'}]}, ['hr'])},
            {'retail'})

    def test_manual_recipe_inspection_modes_and_order(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'compatibility/contract.json').parent.mkdir(parents=True)
            (root / 'compatibility/contract.json').write_text('{}\n')
            (root / 'prompts').mkdir()
            (root / 'prompts/xlsx.txt').write_text('prompt')
            (root / 'compatibility/prompts').mkdir(parents=True)
            (root / 'compatibility/prompts/xlsx.txt').write_text('prompt')
            index = {'contract_sha256': 'fixture-contract', 'entries': []}
            for dataset, reference in MANUAL_XLSX.items():
                template = root / 'compatibility/cases' / reference / 'source'
                (template / 'prompts').mkdir(parents=True)
                (template / 'prompts/xlsx.txt').write_text('stale template prompt')
                manifest_dir = root / 'assets/cases' / dataset / 'source/datasets/xlsx' / dataset
                (manifest_dir / 'input').mkdir(parents=True)
                input_path = manifest_dir / 'input/data.xlsx'
                input_path.write_bytes(b'fixture input')
                for name in ('expected.json', 'complexity.json', 'content-summary.json'):
                    (manifest_dir / name).write_text('{}\n')
                helper_path = root / 'compatibility/helpers' / f'{dataset}_build.py'
                helper_path.parent.mkdir(parents=True, exist_ok=True)
                helper_path.write_text('TARGET = "fixture.xlsx"\n')
                provenance = manifest_dir / 'provenance.json'
                provenance.write_text(json.dumps({'references': []}))
                manifest = {
                    'origin_type': 'manual_workflow_adaptation', 'agent_generated': False,
                    'requires_llm': False, 'workbook': input_path.name,
                    'prompt_template': 'xlsx.txt',
                    'prompt_template_sha256': digest(root / 'compatibility/prompts/xlsx.txt'),
                    'runtime_case': 'fixture', 'kind': 'xlsx',
                    'loop_verification_contract': 'document-oe-compatible-xlsx-loop-v1',
                }
                (manifest_dir / 'manifest.json').write_text(json.dumps(manifest))
                with patch('scripts.compile_compatible._copy_current_verifier_package'):
                    _compile_manual_xlsx(root, dataset, index)
                recipe = json.loads((root / 'compatibility/recipes' / f'{dataset}.json').read_text())
                source_prompt = root / recipe['source_path'] / 'prompts/xlsx.txt'
                self.assertEqual(source_prompt.read_text(), 'prompt')
                self.assertEqual(digest(source_prompt), recipe['prompt_sha256'])
                calls = [item['tool_call'].get('arguments', {}).get('command', '')
                         for step in recipe['key_operations'] for item in step['source_tool_calls']
                         if item['tool_call']['function_name'] == 'exec']
                modes = [command.rsplit(' ', 1)[-1] for command in calls
                         if 'inspect_xlsx.py' in command]
                self.assertEqual(modes, ['source', 'copy', 'formula', 'cached'])
                self.assertEqual(recipe['operation_timeout'], 900)
                self.assertEqual(recipe['recalc_timeout'], 600)
                self.assertIn('xlsx_business_diagnostics.json', calls[-1])
                self.assertEqual(recipe['key_operations'][0]['operation_id'], 'XLSX-P01-inspect_prepare')
                roles = [item['role'] for item in recipe['key_operations'][0]['source_tool_calls']]
                self.assertLess(roles.index('inspect_source'), roles.index('copy_official_input'))
                self.assertLess(roles.index('copy_official_input'), roles.index('inspect_copy'))
                seed_manifest = root / recipe['seed_path'] / 'input/dataset_manifest.json'
                frozen_seed_bytes = seed_manifest.read_bytes()
                manifest['prompt_template_sha256'] = '0' * 64
                (manifest_dir / 'manifest.json').write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, 'manifest does not bind the current shared prompt'):
                    _compile_manual_xlsx(root, dataset, index)
                self.assertEqual(seed_manifest.read_bytes(), frozen_seed_bytes)


if __name__ == '__main__':
    unittest.main()

