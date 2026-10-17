import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from replay.common import ROOT, digest, read, write
from replay.compatible import validate
from replay import freeze, suite
from compatibility.verification.pdf import selected_records
from replay.entry import main


class CanonicalizedWorkflowTests(unittest.TestCase):
    def test_native_defaults_and_effective_operations(self):
        index = validate()
        self.assertEqual(len(index['entries']), 7)
        for entry in index['entries']:
            recipe = read(ROOT / entry['recipe_path'])
            roles = [c['role'] for s in recipe['key_operations'] for c in s['source_tool_calls']]
            self.assertEqual(roles.count('build'), 1)
            self.assertNotIn('runtime/bin/soffice', json.dumps(recipe))
            self.assertEqual(recipe['classification'], 'canonicalized_deterministic_replay_derived_from_successful_agent_executions')
            if recipe['case_kind'] == 'xlsx':
                self.assertEqual(recipe['workflow_contract'], 'spreadsheet-semantic-v3')
                self.assertEqual(roles.count('recalculate'), 1)
                self.assertEqual(recipe['recalc_timeout'], 600)
                self.assertEqual(roles.count('export_csv'), 1)
                recalc = next(c['tool_call']['arguments']['command'] for s in recipe['key_operations']
                              for c in s['source_tool_calls'] if c['role'] == 'recalculate')
                self.assertIn('2> output/formula_recalc.stderr.log', recalc)
                self.assertNotIn('2>&1', recalc)
                build = next(c['tool_call']['arguments']['command'] for s in recipe['key_operations']
                             for c in s['source_tool_calls'] if c['role'] == 'build')
                self.assertIn('run_xlsx_helper_atomic.py', build)
                calls_text = json.dumps(recipe['key_operations'])
                for legacy_call in ('assemble_output', 'inject_caches', 'patch.py'):
                    self.assertNotIn(legacy_call, calls_text)
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

    def test_new_xlsx_helper_hashes_are_frozen_and_match_content(self):
        files = {'retail': 'retail_build_enhance.py', 'manufacturing': 'manufacturing_build_enhanced.py', 'hr': 'hr_build.py'}
        for entry in read(ROOT / 'compatibility/suite.json')['entries']:
            if entry['record_count'] is not None:
                continue
            recipe = read(ROOT / entry['recipe_path'])
            self.assertEqual(len(recipe['helper_hashes']), 1)
            helper, sha = next(iter(recipe['helper_hashes'].items()))
            write_call = next(c['tool_call'] for s in recipe['key_operations']
                              for c in s['source_tool_calls']
                              if c['role'] == 'write_helper' and c['tool_call']['arguments']['path'].endswith(helper))
            import hashlib
            self.assertEqual(hashlib.sha256(write_call['arguments']['content'].encode()).hexdigest(), sha)
            self.assertEqual((ROOT / 'compatibility/helpers' / files[entry['dataset_id']]).read_text(),
                             write_call['arguments']['content'])

    def test_suite_runs_all_loops_before_final_acceptance_and_archive(self):
        self._exercise_native_series()

    def test_failed_or_incomplete_native_series_never_passes_on_last_success(self):
        for defect in ('earlier_failure', 'missing_event', 'acceptance_failure'):
            with self.subTest(defect=defect):
                self._exercise_native_series(defect)

    def _exercise_native_series(self, defect=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / 'workspace'
            write(workspace / 'output/result.json', {'value': 1})
            layout = {'source': root / 'source', 'workspace': str(workspace),
                      'operation_timeout': 900, 'recalc_timeout': 600}
            (root / 'source').mkdir()
            expected_recipe = freeze.expected_recipe_sha256('retail', None)
            calls = []
            def execute(command, check, **kwargs):
                calls.append(command)
                if '--scene' in command:
                    scene = command[command.index('--scene') + 1]
                    destination = Path(command[command.index('--results-dir') + 1])
                    run = destination / scene / '20261010T000000Z-pid1'
                    run.mkdir(parents=True)
                    summary = {'dataset': 'retail', 'scene': 'xlsx',
                               'pdf_applicant_count': None, 'recipe_sha256': expected_recipe,
                               'requested_iterations': 3, 'completed_iterations': 3,
                               'successes': 3, 'failures': 0, 'interrupted': False,
                               'run_id': '20261010T000000Z-pid1'}
                    events = [{'iteration': i, 'status': 'success'} for i in range(1, 4)]
                    if defect == 'earlier_failure':
                        summary.update(successes=2, failures=1)
                        events[0]['status'] = 'failed'
                    elif defect == 'missing_event':
                        events.pop(0)
                    write(run / 'summary.json', summary)
                    (run / 'iterations.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
                else:
                    destination = Path(command[command.index('--report') + 1])
                    write(destination,
                          {'status': 'failed' if defect == 'acceptance_failure' else 'success',
                           'failures': ['bad'] if defect == 'acceptance_failure' else []})
            with patch('replay.suite.subprocess.run', side_effect=execute):
                item = suite.run_dataset(None, 'retail', 'xlsx', layout, root / 'results', 3, True, 'venv', 1)
            self.assertEqual(sum('--scene' in c for c in calls), 1)
            self.assertEqual(sum(any('replay/accept.py' in str(x) for x in c) for c in calls),
                             1 if (not defect or defect == 'acceptance_failure') else 0)
            self.assertEqual(item['status'], 'failed' if defect else 'success')
            self.assertEqual(item['archive_scope'], 'final_iteration_only')
            if not defect:
                self.assertEqual(len(item['native_iterations']), 3)
                archives = list((root / 'results/retail').glob('*/workspace_artifacts/output/result.json'))
                self.assertEqual(len(archives), 1)

    def test_repeat_runs_and_pdf_variants_get_unique_dirs(self):
        # Two consecutive runs on the same results root must not collide, and
        # the PDF 1/10 variants must use distinguishable destination paths.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / 'workspace'
            write(workspace / 'output/result.json', {'value': 1})
            layout = {'source': root / 'source', 'workspace': str(workspace),
                      'operation_timeout': 900, 'recalc_timeout': 600}
            (root / 'source').mkdir()
            expected = freeze.expected_recipe_sha256('retail', None)
            def execute(command, check, **kwargs):
                if '--scene' in command:
                    scene = command[command.index('--scene') + 1]
                    destination = Path(command[command.index('--results-dir') + 1])
                    run = destination / scene / '20261010T000000Z-pid1'
                    run.mkdir(parents=True)
                    write(run / 'summary.json', {'dataset': 'retail', 'scene': 'xlsx',
                          'pdf_applicant_count': None, 'recipe_sha256': expected,
                          'requested_iterations': 1, 'completed_iterations': 1,
                          'successes': 1, 'failures': 0, 'interrupted': False,
                          'run_id': '20261010T000000Z-pid1'})
                    (run / 'iterations.jsonl').write_text('{"iteration": 1, "status": "success"}\n')
                else:
                    dest = Path(command[command.index('--report') + 1])
                    write(dest, {'status': 'success', 'failures': []})
            with patch('replay.suite.subprocess.run', side_effect=execute):
                first = suite.run_dataset(None, 'retail', 'xlsx', layout, root / 'results', 1, False, 'venv', 1)
                second = suite.run_dataset(None, 'retail', 'xlsx', layout, root / 'results', 1, False, 'venv', 1)
            self.assertEqual(first['status'], 'success')
            self.assertEqual(second['status'], 'success')
            self.assertNotEqual(first['run_stamp'], second['run_stamp'])
            self.assertNotEqual(first['run_dir'], second['run_dir'])
            self.assertTrue(Path(first['run_dir']).is_dir())
            self.assertTrue(Path(second['run_dir']).is_dir())
            self.assertFalse(Path(first['run_dir']).samefile(Path(second['run_dir'])))

    def test_env_passed_to_runner_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / 'workspace'
            write(workspace / 'output/result.json', {'value': 1})
            layout = {'source': root / 'source', 'workspace': str(workspace),
                      'operation_timeout': 900, 'recalc_timeout': 600}
            (root / 'source').mkdir()
            expected = freeze.expected_recipe_sha256('retail', None)
            def execute(command, check, **kwargs):
                if '--scene' in command:
                    scene = command[command.index('--scene') + 1]
                    destination = Path(command[command.index('--results-dir') + 1])
                    run = destination / scene / '20261010T000000Z-pid1'
                    run.mkdir(parents=True)
                    write(run / 'summary.json', {'dataset': 'retail', 'scene': 'xlsx',
                          'pdf_applicant_count': None, 'recipe_sha256': expected,
                          'requested_iterations': 1, 'completed_iterations': 1,
                          'successes': 1, 'failures': 0, 'interrupted': False,
                          'run_id': '20261010T000000Z-pid1'})
                    (run / 'iterations.jsonl').write_text('{"iteration": 1, "status": "success"}\n')
                else:
                    dest = Path(command[command.index('--report') + 1])
                    write(dest, {'status': 'success', 'failures': []})
            seen = {}
            def execute_system(command, check, **kwargs):
                execute(command, check, **kwargs)
                if '--scene' in command:
                    seen['env'] = kwargs.get('env')
                    seen['command'] = command
            with patch('replay.suite.subprocess.run', side_effect=execute_system):
                suite.run_dataset(None, 'retail', 'xlsx', layout, root / 'results', 1, False, 'system', 1)
            env = seen['env']
            self.assertIsNotNone(env)
            self.assertEqual(seen['command'][0], '/usr/bin/python3')
            self.assertIn('--legacy-python', seen['command'])
            self.assertEqual(seen['command'][seen['command'].index('--legacy-python') + 1], 'system')
            self.assertNotIn('VIRTUAL_ENV', env)
            self.assertNotIn('PYTHONPATH', env)
            self.assertEqual(env.get('OFFICE_TRACE_PROJECT'), str(root / 'source'))

    def test_entry_dispatches_each_dataset_to_one_runner_process(self):
        with patch('replay.entry.legacy.validate'), \
             patch('replay.entry.suite.run_dataset', return_value={'status': 'success'}) as run_dataset, \
             patch('replay.entry.suite.run_old_dataset', return_value=0) as run_old:
            self.assertEqual(main(['--dataset', 'retail', '--dataset', 'pdf', '--timed']), 0)
            self.assertEqual([(r.args[1], r.args[0]) for r in run_old.call_args_list], [('pdf', 'opm')])
            self.assertEqual(run_dataset.call_args.args[1], 'retail')
            self.assertEqual(run_dataset.call_args.args[2], 'xlsx')

    def test_contract_prompt_and_parent_bindings(self):
        default = read(ROOT / 'suites/default.json')
        index = read(ROOT / 'compatibility/suite.json')
        self.assertEqual(default['compatible_suite_sha256'], digest(ROOT / 'compatibility/suite.json'))
        self.assertEqual(default['compatible_contract_sha256'], index['contract_sha256'])
        self.assertEqual(read(ROOT / 'compatibility/contract.json')['python']['default'], 'venv')
        self.assertTrue(all(e['python_default'] == 'venv-3.12.3' for e in default['datasets']))
        for entry in default['datasets'][2:]:
            self.assertEqual(entry['mode'], 'canonicalized_deterministic_replay')
            self.assertEqual(entry['recipe_sha256'], digest(ROOT / entry['recipe_path']))
        for entry in index['entries']:
            recipe = read(ROOT / entry['recipe_path'])
            self.assertEqual(recipe['parent']['recipe_sha256'], digest(ROOT / recipe['parent']['recipe_path']))
            self.assertEqual(recipe['prompt_sha256'], digest(ROOT / recipe['prompt_path']))

    def test_active_helpers_are_written_inside_native_build_phase(self):
        for entry in read(ROOT / 'compatibility/suite.json')['entries']:
            recipe = read(ROOT / entry['recipe_path'])
            seed = ROOT / recipe['seed_path']
            self.assertTrue(all(p.relative_to(seed).parts[0] == 'input' for p in seed.rglob('*') if p.is_file()))
            writes = [c['tool_call'] for c in recipe['key_operations'][1]['source_tool_calls'] if c['role'] == 'write_helper']
            self.assertTrue(writes)
            self.assertTrue(all(c['function_name'] == 'write' and c['arguments']['content'] for c in writes))

    def test_freeze_rejects_tampered_recipe(self):
        # A recipe whose bytes no longer match the frozen index hash must be
        # rejected before execution; the expected hash always comes from the
        # frozen index, never recomputed-and-accepted.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'compatibility/recipes').mkdir(parents=True)
            recipe_path = root / 'compatibility/recipes/retail.json'
            recipe_path.write_text(json.dumps({'key_operations': [
                {'source_tool_calls': [{'tool_call': {'function_name': 'exec',
                                                      'arguments': {'command': 'echo x'}}}]}]}))
            index = {'schema_version': 'document-oe-compatible-suite-v1',
                     'contract_sha256': '0' * 64, 'legacy_lock_sha256': '0' * 64,
                     'entries': [{'dataset_id': 'retail', 'variant_id': 'retail',
                                  'record_count': None,
                                  'recipe_path': 'compatibility/recipes/retail.json',
                                  'recipe_sha256': '0' * 64}]}
            write(root / 'compatibility/suite.json', index)
            layout = {'source': 'compatibility/cases/retail/source'}
            with patch('replay.freeze.ROOT', root), \
                 patch('replay.freeze.legacy.validate'), \
                 patch('replay.run.validate_project'):
                with self.assertRaisesRegex(ValueError, 'recipe hash mismatch'):
                    freeze.validate_dataset('xlsx', 'retail', layout, None, check_installed=False)


if __name__ == '__main__':
    unittest.main()
