"""Runtime-source asset checks without a workbook load or a container."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from replay.common import digest, write
from replay.source_assets import validate_source_assets
from replay.compatible import validate_public_suite
from scripts.compile_compatible import _refresh_public_suite


ROOT = Path(__file__).resolve().parents[1]


class RuntimeSourceAssetTests(unittest.TestCase):
    def fixture(self, root):
        source = root / 'case/source'
        package = source / 'office_trace_bench'
        package.mkdir(parents=True)
        (package / '__init__.py').write_text('')
        shutil.copyfile(ROOT / 'compatibility/verification/contracts.py', package / 'contracts.py')
        dataset = source / 'datasets/xlsx/manual'
        (dataset / 'input').mkdir(parents=True)
        (dataset / 'input/book.xlsx').write_bytes(b'fixture bytes; no workbook is opened')
        write(dataset / 'expected.json', {})
        write(dataset / 'provenance.json', {'origin_type': 'manual_workflow_adaptation'})
        (source / 'prompts').mkdir()
        prompt = source / 'prompts/xlsx.txt'
        prompt.write_text('current prompt')
        public = root / 'compatibility/prompts/xlsx.txt'
        public.parent.mkdir(parents=True)
        public.write_text('current prompt')
        manifest = {
            'schema_version': 'office-dataset-v2', 'kind': 'xlsx', 'dataset_id': 'manual',
            'task': 'small fixture', 'input_files': {'input/book.xlsx': digest(dataset / 'input/book.xlsx')},
            'expected_file': 'expected.json', 'expected_sha256': digest(dataset / 'expected.json'),
            'workbook': 'book.xlsx', 'output_workbook': 'result.xlsx', 'trace_rules': [],
            'requirements': {'metrics': [], 'scenario': {}, 'charts': []},
            'workload_contract': 'spreadsheet-semantic-v3',
            'prompt_template': 'xlsx.txt', 'prompt_template_sha256': digest(prompt),
            'analysis_metadata': {'provenance.json': digest(dataset / 'provenance.json')},
        }
        write(dataset / 'manifest.json', manifest)
        seed = root / 'case/seed/input/dataset_manifest.json'
        write(seed, manifest)
        recipe = {
            'dataset_id': 'manual', 'case_kind': 'xlsx', 'origin_type': 'manual_workflow_adaptation',
            'source_path': 'case/source', 'seed_path': 'case/seed',
            'prompt_path': 'compatibility/prompts/xlsx.txt', 'prompt_sha256': digest(public),
        }
        return recipe, dataset, prompt, seed

    def test_source_assets_pass_and_leave_no_imported_dataset_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe, _, _, _ = self.fixture(root)
            for _ in range(2):
                self.assertEqual(validate_source_assets(recipe, root)['dataset_id'], 'manual')
            self.assertFalse(any(n.startswith('_office_trace_asset_check_') for n in sys.modules))

    def test_stale_source_prompt_is_rejected_even_when_public_prompt_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe, _, prompt, _ = self.fixture(root)
            prompt.write_text('stale inherited prompt')
            with self.assertRaisesRegex(ValueError, 'manual: runtime source assets invalid: prompt template hash mismatch'):
                validate_source_assets(recipe, root)

    def test_other_source_assets_are_checked_before_business_verification(self):
        for target, message in [('input/book.xlsx', 'input hash mismatch'),
                                ('expected.json', 'expected results hash mismatch'),
                                ('provenance.json', 'analysis metadata hash mismatch')]:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                recipe, dataset, _, _ = self.fixture(root)
                (dataset / target).write_text('tampered')
                with self.assertRaisesRegex(ValueError, message):
                    validate_source_assets(recipe, root)

    def test_seed_and_source_manifest_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe, _, _, seed = self.fixture(root)
            manifest = json.loads(seed.read_text())
            manifest['task'] = 'stale task'
            write(seed, manifest)
            with self.assertRaisesRegex(ValueError, 'seed and source manifests differ'):
                validate_source_assets(recipe, root)

    def test_manual_source_cannot_bind_a_different_prompt_from_recipe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe, dataset, prompt, seed = self.fixture(root)
            prompt.write_text('self-consistent but different source prompt')
            manifest = json.loads(seed.read_text())
            manifest['prompt_template_sha256'] = digest(prompt)
            write(dataset / 'manifest.json', manifest)
            write(seed, manifest)
            with self.assertRaisesRegex(ValueError, 'manual source prompt differs from recipe'):
                validate_source_assets(recipe, root)


class PublicSuiteBindingTests(unittest.TestCase):
    def test_refresh_preserves_selection_and_preflight_rejects_stale_bindings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('legacy/document-oe/lock.json', 'compatibility/contract.json',
                         'compatibility/suite.json', 'compatibility/recipes/old.json'):
                write(root / name, {})
            public = {'datasets': [{'dataset_id': 'old',
                                   'recipe_path': 'compatibility/recipes/old.json',
                                   'recipe_sha256': 'stale'}],
                      'default_datasets': ['old'],
                      'compatible_suite_sha256': 'stale'}
            write(root / 'suites/default.json', public)
            with self.assertRaisesRegex(ValueError, 'public suite binding mismatch'):
                validate_public_suite(root)
            _refresh_public_suite(root)
            validate_public_suite(root)
            refreshed = json.loads((root / 'suites/default.json').read_text())
            self.assertEqual([e['dataset_id'] for e in refreshed['datasets']], ['old'])
            (root / 'compatibility/recipes/old.json').write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError, 'public suite recipe hash mismatch: old'):
                validate_public_suite(root)


if __name__ == '__main__':
    unittest.main()
