import hashlib
from pathlib import Path
import tempfile
import unittest

from replay.common import ROOT, digest, read, write
from replay.run import document_executor, validate_project
from replay.selections import RUNS


class FrozenReplayTests(unittest.TestCase):
    def test_suite_and_document_executor_contract(self):
        suite = validate_project()
        self.assertEqual({e['dataset_id'] for e in suite['datasets']}, set(RUNS))
        doc = document_executor()
        for entry in suite['datasets']:
            recipe = read(ROOT / entry['recipe_path'])
            doc.load_recipe(ROOT / entry['recipe_path'], recipe['case_kind'], recipe['workflow']['success_path'])
            self.assertFalse(recipe['requires_llm'])
            self.assertEqual(recipe['source']['original_run_id'], RUNS[entry['dataset_id']])

    def test_seeds_have_no_generated_output_or_intermediate_workbook(self):
        for entry in read(ROOT / 'recipes/suite.json')['datasets']:
            recipe = read(ROOT / entry['recipe_path'])
            seed = ROOT / recipe['seed_path']
            # Git does not track empty directories; the document executor
            # creates output during reset on both archive and image installs.
            if (seed / 'output').exists():
                self.assertEqual(list((seed / 'output').iterdir()), [])
            for p in seed.rglob('*'):
                if p.is_file() and p.suffix in ('.xlsx', '.pdf', '.png'):
                    self.assertEqual(p.relative_to(seed).parts[0], 'input')
            for name, expected in recipe['source']['input_hashes'].items():
                self.assertEqual(digest(seed / name), expected)
            for name, expected in recipe['helper_hashes'].items():
                self.assertEqual(digest(seed / name), expected)

    def test_selected_calls_and_explicit_adaptations_have_source_evidence(self):
        for entry in read(ROOT / 'recipes/suite.json')['datasets']:
            recipe = read(ROOT / entry['recipe_path'])
            events = read(ROOT / entry['canonical_path'] / 'tool_events.json')['events']
            import json
            for step in recipe['key_operations']:
                for selected in step['source_tool_calls']:
                    source = events[selected['source_event_index']]['tool_call']
                    self.assertEqual(source['tool_call_id'], selected['tool_call_id'])
                    self.assertEqual(hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest(), selected['source_call_sha256'])
                    self.assertIn(selected['tool_call']['function_name'], ('read', 'write', 'exec'))
                    if selected['tool_call']['function_name'] == 'exec':
                        self.assertTrue(selected['tool_call']['arguments']['command'].startswith('set -e\nset -o pipefail\n'))

    def test_tampered_asset_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / 'assets').mkdir()
            (p / 'asset').write_text('original')
            write(p / 'assets/project-lock.json', {'files': {'asset': digest(p / 'asset')}})
            (p / 'asset').write_text('tampered')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                validate_project(p)

    def test_tmp_gaps_are_reviewed_using_rename_evidence(self):
        for entry in read(ROOT / 'recipes/suite.json')['datasets']:
            recipe = read(ROOT / entry['recipe_path'])
            canonical = read(ROOT / entry['canonical_path'] / 'canonical.json')
            self.assertEqual(len(recipe['review']['capture_gap_decisions']), len(canonical['revision_capture']['gaps']))
            for decision in recipe['review']['capture_gap_decisions']:
                self.assertEqual(decision['classification'], 'ephemeral_in_selected_recipe')
                self.assertIn('moved_to', decision['evidence'])
                self.assertEqual(decision['final_artifact_sha256'], canonical['artifact_inventory']['workspace/output/business_verification.json']['sha256'])

    def test_command_failure_and_timeout_propagate(self):
        doc = document_executor()
        with self.assertRaises(RuntimeError): doc.run_command('exit 7', 5)
        with self.assertRaises(TimeoutError): doc.run_command('sleep 5', 1)

    def test_skill_office_namespace_with_clean_pythonpath(self):
        import os
        import subprocess
        import sys
        source = ROOT / 'assets/cases/hr/source'
        env = os.environ.copy()
        env.pop('PYTHONPATH', None)
        result = subprocess.run([sys.executable, '-c', 'import office.soffice; print(office.soffice.__file__)'],
                                cwd=source / 'vendor/skills/xlsx/scripts', env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('vendor/skills/xlsx/scripts/office/soffice.py', result.stdout)


if __name__ == '__main__':
    unittest.main()
