import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from replay.common import ROOT, digest, read, write
from replay.compatible import validate, run_dataset
from compatibility.verification.pdf import selected_records
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
                self.assertEqual(roles.count('validate_mapping'), 1)
                self.assertEqual(roles.count('write_helper'), 2)
                self.assertEqual(len(roles), 21)
                self.assertNotIn('verify_mapping_dryrun.py', json.dumps(recipe['key_operations']))

    def test_full_pdf_preparation_and_selected_execution_are_frozen(self):
        for entry in read(ROOT / 'compatibility/suite.json')['entries']:
            if entry['record_count'] is None:
                continue
            recipe = read(ROOT / entry['recipe_path'])
            seed = ROOT / recipe['seed_path']
            manifest = read(seed / 'input/dataset_manifest.json')
            dataset = ROOT / recipe['source_path'] / 'datasets/pdf' / entry['dataset_id']
            self.assertEqual(read(dataset / 'manifest.json'), manifest)
            records = read(seed / 'input' / manifest['records'])[manifest['records_key']]
            self.assertEqual(len(records), 10)
            self.assertEqual(recipe['prepared_record_count'], 10)
            self.assertEqual(len(selected_records(manifest, records)), entry['record_count'])
            self.assertEqual(manifest['requirements']['record_count'], len(records))
            self.assertEqual(digest(dataset / manifest['expected_file']), manifest['expected_sha256'])
            summary = read(dataset / manifest['expected_file'])['summary_values']
            self.assertEqual(summary['filled_pdf_count'], entry['record_count'])
            self.assertEqual(summary['field_values_count'], 10)
            for name, sha in manifest['input_files'].items():
                self.assertEqual(digest(dataset / name), sha)
                self.assertEqual(digest(seed / name), sha)
            parent = read(ROOT / 'assets/cases' / entry['dataset_id'] / 'seed/input/dataset_manifest.json')
            self.assertEqual(parent['requirements']['record_count'], 10)
            original_records = read(ROOT / 'assets/cases' / entry['dataset_id'] / 'seed/input' / parent['records'])
            self.assertEqual(records, original_records[parent['records_key']])
            self.assertEqual(digest(seed / 'input' / manifest['records']), parent['input_files']['input/' + parent['records']])
            self.assertEqual(digest(dataset / 'records_contract.json'), parent['records_contract_sha256'])

    def test_invalid_pdf_selection_is_rejected(self):
        records = [{'id': 'first'}, {'id': 'second'}]
        for ids, count in [([], 0), (['second'], 1), (['first', 'first'], 2), (['first'], 2), (['missing'], 1)]:
            with self.subTest(ids=ids, count=count), self.assertRaises(ValueError):
                selected_records({'pdf_execution': {'record_ids': ids, 'record_count': count}}, records)

    def test_native_loop_runs_once_before_final_acceptance_and_archive(self):
        self._exercise_native_series()

    def test_failed_or_incomplete_native_series_never_passes_on_last_success(self):
        for defect in ('earlier_failure', 'missing_event', 'wrong_recipe', 'acceptance_failure'):
            with self.subTest(defect=defect):
                self._exercise_native_series(defect)

    def _exercise_native_series(self, defect=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / 'workspace'
            write(workspace / 'output/result.json', {'value': 1})
            recipe = {'case_kind': 'pdf', 'source_path': 'source', 'workspace': str(workspace), 'parent': {}}
            write(root / 'recipe.json', recipe)
            entry = {'dataset_id': 'irs_w4', 'variant_id': 'irs_w4-n1', 'recipe_path': 'recipe.json', 'recipe_sha256': digest(root / 'recipe.json')}
            calls = []
            def execute(command, check):
                calls.append(command)
                destination = root / 'results/irs_w4-n1/series'
                self.assertFalse((destination / 'workspace_artifacts').exists())
                if '--native-child' in command:
                    self.assertEqual(command[command.index('--loops') + 1], '3')
                    summary = {'requested_iterations': 3, 'completed_iterations': 3, 'successes': 3,
                               'failures': 0, 'interrupted': False, 'recipe_sha256': entry['recipe_sha256']}
                    events = [{'iteration': i, 'status': 'success'} for i in range(1, 4)]
                    if defect == 'earlier_failure':
                        summary.update(successes=2, failures=1)
                        events[0]['status'] = 'failed'
                    elif defect == 'missing_event':
                        events.pop(0)
                    elif defect == 'wrong_recipe':
                        summary['recipe_sha256'] = 'wrong'
                    write(destination / 'pdf/native/summary.json', summary)
                    (destination / 'pdf/native/iterations.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
                else:
                    self.assertEqual(len(calls), 2)
                    write(destination / 'independent_verification.json',
                          {'status': 'failed' if defect == 'acceptance_failure' else 'success',
                           'failures': ['bad_mapping'] if defect == 'acceptance_failure' else []})
            with patch('replay.compatible.ROOT', root), patch('replay.compatible.subprocess.run', side_effect=execute):
                result = run_dataset(entry, root / 'results', 3, True, 'venv')
            self.assertEqual(sum('--native-child' in c for c in calls), 1)
            self.assertEqual(result['status'], 'failed' if defect else 'success')
            self.assertEqual(len(calls), 1 if defect in ('earlier_failure', 'missing_event', 'wrong_recipe') else 2)
            if not defect:
                self.assertEqual(len(result['native_iterations']), 3)
                self.assertEqual(result['archive_scope'], 'final_iteration_only')
                self.assertTrue((root / 'results/irs_w4-n1/series/workspace_artifacts/output/result.json').is_file())

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
            self.assertEqual(main(['--dataset', 'retail', '--timed']), 0)
            command = call.call_args.args[0]
            self.assertEqual(command[0], '/opt/document-bench/.venv/bin/python')
            self.assertIn(str(ROOT / 'replay/compatible.py'), command)
            self.assertIn('--timed', command)
            self.assertEqual(command[command.index('--legacy-python') + 1], 'venv')
        with patch('replay.entry.legacy.validate'), patch('replay.entry.subprocess.call', return_value=0) as call:
            self.assertEqual(main(['--dataset', 'retail', '--legacy-python', 'system']), 0)
            command = call.call_args.args[0]
            self.assertEqual(command[0], '/usr/bin/python3')
            self.assertEqual(command[command.index('--legacy-python') + 1], 'system')
        with patch('replay.entry.legacy.validate'), patch('replay.entry.subprocess.call', return_value=0) as call:
            main(['--dataset', 'retail', '--workflow', 'derived-v1'])
            self.assertIn(str(ROOT / 'replay/run.py'), call.call_args.args[0])

    def test_contract_prompt_and_parent_bindings(self):
        default = read(ROOT / 'suites/default.json')
        index = read(ROOT / 'compatibility/suite.json')
        self.assertEqual(default['compatible_suite_sha256'], digest(ROOT / 'compatibility/suite.json'))
        self.assertEqual(default['compatible_contract_sha256'], index['contract_sha256'])
        self.assertEqual(read(ROOT / 'compatibility/contract.json')['python']['default'], 'venv')
        self.assertTrue(all(e['python_default'] == 'venv-3.12.3' for e in default['datasets']))
        for entry in default['datasets'][2:]:
            self.assertEqual(entry['mode'], 'document_oe_compatible_adapter')
            self.assertEqual(entry['recipe_sha256'], digest(ROOT / entry['recipe_path']))
        for entry in index['entries']:
            recipe = read(ROOT / entry['recipe_path'])
            self.assertEqual(recipe['parent']['recipe_sha256'], digest(ROOT / recipe['parent']['recipe_path']))
            self.assertEqual(recipe['prompt_sha256'], digest(ROOT / recipe['prompt_path']))


if __name__ == '__main__':
    unittest.main()
