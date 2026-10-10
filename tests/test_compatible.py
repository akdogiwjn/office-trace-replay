import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from replay.common import ROOT, digest, read
from replay.compatible import validate
from replay.entry import main


class CompatibleWorkflowTests(unittest.TestCase):
    def test_native_defaults_and_effective_operations(self):
        index = validate()
        self.assertEqual(len(index['entries']), 7)
        for entry in index['entries']:
            recipe = read(ROOT / entry['recipe_path'])
            roles = [c['role'] for s in recipe['key_operations'] for c in s['source_tool_calls']]
            self.assertEqual(roles.count('build'), 1)
            self.assertNotIn('runtime/bin/soffice', json.dumps(recipe))
            self.assertEqual(recipe['classification'], 'adapted_replay_recipe_not_new_agent_trace')
            if recipe['case_kind'] == 'xlsx':
                self.assertEqual(roles.count('recalculate'), 1)
                self.assertEqual(roles.count('source_preservation'), 1)
                self.assertEqual(recipe['recalc_timeout'], 600)
                self.assertEqual(roles.count('export_csv'), 1)
                recalc = next(c['tool_call']['arguments']['command'] for s in recipe['key_operations']
                              for c in s['source_tool_calls'] if c['role'] == 'recalculate')
                self.assertIn('2> output/formula_recalc.stderr.log', recalc)
                self.assertNotIn('2>&1', recalc)
            else:
                self.assertEqual(roles.count('fill_render_batch'), 1)

    def test_frozen_pdf_subsets_have_coherent_hashes_and_oracles(self):
        for entry in read(ROOT / 'compatibility/suite.json')['entries']:
            if entry['record_count'] is None:
                continue
            recipe = read(ROOT / entry['recipe_path'])
            seed = ROOT / recipe['seed_path']
            manifest = read(seed / 'input/dataset_manifest.json')
            dataset = ROOT / recipe['source_path'] / 'datasets/pdf' / entry['dataset_id']
            self.assertEqual(read(dataset / 'manifest.json'), manifest)
            records = read(seed / 'input' / manifest['records'])[manifest['records_key']]
            self.assertEqual(len(records), entry['record_count'])
            self.assertEqual(manifest['requirements']['record_count'], len(records))
            self.assertEqual(digest(dataset / manifest['expected_file']), manifest['expected_sha256'])
            self.assertEqual(read(dataset / manifest['expected_file'])['summary_values']['filled_pdf_count'], len(records))
            for name, sha in manifest['input_files'].items():
                self.assertEqual(digest(dataset / name), sha)
                self.assertEqual(digest(seed / name), sha)
            parent = read(ROOT / 'assets/cases' / entry['dataset_id'] / 'seed/input/dataset_manifest.json')
            self.assertEqual(parent['requirements']['record_count'], 10)
            original_records = read(ROOT / 'assets/cases' / entry['dataset_id'] / 'seed/input' / parent['records'])
            self.assertEqual(records, original_records[parent['records_key']][:entry['record_count']])

    def test_active_helpers_are_written_inside_native_build_phase(self):
        for entry in read(ROOT / 'compatibility/suite.json')['entries']:
            recipe = read(ROOT / entry['recipe_path'])
            seed = ROOT / recipe['seed_path']
            self.assertTrue(all(p.relative_to(seed).parts[0] == 'input' for p in seed.rglob('*') if p.is_file()))
            writes = [c['tool_call'] for c in recipe['key_operations'][1]['source_tool_calls'] if c['role'] == 'write_helper']
            self.assertTrue(writes)
            self.assertTrue(all(c['function_name'] == 'write' and c['arguments']['content'] for c in writes))

    def test_compatible_entry_forwards_same_runtime_and_timing_modes(self):
        with patch('replay.entry.legacy.validate'), patch('replay.entry.subprocess.call', return_value=0) as call:
            self.assertEqual(main(['--dataset', 'retail', '--timed', '--legacy-python', 'venv']), 0)
            command = call.call_args.args[0]
            self.assertEqual(command[0], '/opt/document-bench/.venv/bin/python')
            self.assertIn(str(ROOT / 'replay/compatible.py'), command)
            self.assertIn('--timed', command)
            self.assertEqual(command[command.index('--legacy-python') + 1], 'venv')
        with patch('replay.entry.legacy.validate'), patch('replay.entry.subprocess.call', return_value=0) as call:
            main(['--dataset', 'retail', '--workflow', 'derived-v1'])
            self.assertIn(str(ROOT / 'replay/run.py'), call.call_args.args[0])

    def test_contract_prompt_and_parent_bindings(self):
        default = read(ROOT / 'suites/default.json')
        index = read(ROOT / 'compatibility/suite.json')
        self.assertEqual(default['compatible_suite_sha256'], digest(ROOT / 'compatibility/suite.json'))
        self.assertEqual(default['compatible_contract_sha256'], index['contract_sha256'])
        for entry in default['datasets'][2:]:
            self.assertEqual(entry['mode'], 'document_oe_compatible_adapter')
            self.assertEqual(entry['recipe_sha256'], digest(ROOT / entry['recipe_path']))
        for entry in index['entries']:
            recipe = read(ROOT / entry['recipe_path'])
            self.assertEqual(recipe['parent']['recipe_sha256'], digest(ROOT / recipe['parent']['recipe_path']))
            self.assertEqual(recipe['prompt_sha256'], digest(ROOT / recipe['prompt_path']))


if __name__ == '__main__':
    unittest.main()
