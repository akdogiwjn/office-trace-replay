import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from replay.common import digest, read
from replay import legacy
from replay.entry import OLD, NEW, HISTORICAL, DEFAULT, main


class LegacyCompatibilityTests(unittest.TestCase):
    def test_original_recipe_calls_and_defaults_are_preserved(self):
        lock = legacy.validate()
        self.assertEqual(lock['files']['bin/run_document_scene_loop.py']['sha256'],
                         '3623f72779249b9cc95517adc09064f96286d02105e1793cf09733e20f771e80')
        self.assertEqual(lock['executor']['version'], 'unified-dataset-runner-v1')
        self.assertIn('bin/run_document_scene_loop_timed.py', lock['executor']['files'])
        self.assertIn('operations/xlsx_key_operations.json', lock['workload'])
        from replay.run import document_executor
        core = document_executor()
        self.assertEqual(core.LOOP_COUNT, 20000)
        self.assertEqual(core.PDF_APPLICANT_COUNT, 1)
        self.assertEqual(core.SCENES['xlsx']['recalc_timeout'], 600)
        expected = {'pdf': ('f1f90debf96d444f8fd56e9f4f2a3193f54e7786697c5b6fcbb2526d2a2e57b5', 21),
                    'xlsx': ('53a475924f0bf6f2b2fef4e85c13bae467241e5785ba7867e195422d2e9b07f2', 15)}
        for kind, (sha, count) in expected.items():
            p = legacy.LEGACY / 'operations' / (kind + '_key_operations.json')
            self.assertEqual(digest(p), sha)
            recipe = read(p)
            self.assertEqual(sum(len(s['source_tool_calls']) for s in recipe['key_operations']), count)
            core.load_recipe(p, kind, core.SCENES[kind]['step_order'])

    def test_runner_prepares_environment_and_legacy_python_flags(self):
        from replay.run import document_executor
        core = document_executor()
        self.assertIn('--legacy-python', legacy.native_command(['--scene', 'pdf']))
        command = legacy.native_command(['--scene', 'xlsx'], timed=True, python_mode='venv')
        self.assertEqual(command[0], '/opt/document-bench/.venv/bin/python')
        self.assertIn('--timed', command)
        self.assertEqual(command[command.index('--legacy-python') + 1], 'venv')
        system = legacy.native_command(['--scene', 'pdf'], python_mode='system')
        self.assertEqual(system[0], '/usr/bin/python3')
        # The runner prepares env itself for canonicalized layouts.
        layout = core.dataset_layout('xlsx', 'retail')
        self.assertIsNotNone(layout['source'])
        self.assertIn('/opt/office-trace-replay/compatibility/cases/retail/source', str(layout['source']))
        layout_old = core.dataset_layout('xlsx', 'tlc')
        self.assertIsNone(layout_old['source'])

    def test_ensure_interpreter_noop_when_already_matching(self):
        from replay.run import document_executor
        core = document_executor()
        with patch('os.path.realpath', return_value='/usr/bin/python3'), \
             patch.object(core.sys, 'executable', '/usr/bin/python3'):
            core.ensure_interpreter('system')  # must not raise or re-exec

    def test_ensure_interpreter_rejects_missing_interpreter(self):
        from replay.run import document_executor
        core = document_executor()
        with patch('os.path.realpath', side_effect=lambda p: p), \
             patch.object(core.sys, 'executable', '/usr/bin/python3'), \
             patch('os.path.isfile', return_value=False):
            with self.assertRaises(FileNotFoundError):
                core.ensure_interpreter('venv')

    def test_unified_registry_defaults_and_mismatch_rejection(self):
        from replay.run import document_executor
        core = document_executor()
        self.assertEqual(core.SCENE_DEFAULT_DATASET, {'pdf': 'opm', 'xlsx': 'tlc'})
        # Old defaults preserved byte-for-byte.
        for scene, dataset in core.SCENE_DEFAULT_DATASET.items():
            layout = core.dataset_layout(scene, dataset)
            old = core.SCENES[scene]
            for key in ('seed', 'workspace', 'recipe', 'operation_timeout', 'recalc_timeout', 'step_order'):
                self.assertEqual(layout[key], old[key])
        # All seven formal datasets parse.
        self.assertEqual(set(core.ALL_DATASETS),
                         {'opm', 'irs_w4', 'sba1919', 'tlc', 'retail', 'manufacturing', 'hr'})
        for ds in ('opm', 'irs_w4', 'sba1919'):
            core.dataset_layout('pdf', ds, 1)
        for ds in ('tlc', 'retail', 'manufacturing', 'hr'):
            core.dataset_layout('xlsx', ds)
        # Illegal combinations are rejected.
        for scene, dataset, count in [('pdf', 'tlc', 1), ('xlsx', 'opm', 1), ('pdf', 'retail', 1), ('pdf', 'irs_w4', 5)]:
            with self.subTest(scene=scene, dataset=dataset), self.assertRaises(ValueError):
                core.dataset_layout(scene, dataset, count)
        # New XLSX layouts point into the replay tree with TLC-like timeouts.
        for ds in ('retail', 'manufacturing', 'hr'):
            layout = core.dataset_layout('xlsx', ds)
            self.assertEqual(layout['recalc_timeout'], 600)
            self.assertEqual(layout['operation_timeout'], 900)

    def test_native_scene_and_timing_flags_are_forwarded_verbatim(self):
        arguments = ['--scene', 'pdf', '--loops', '3', '--pdf-applicant-count', '10', '--recalc-timeout', '180']
        with patch('replay.entry.legacy.launch') as launch:
            self.assertEqual(main(arguments), 0)
            launch.assert_called_once_with(arguments, False, 'venv')
        with patch('replay.entry.legacy.launch') as launch:
            self.assertEqual(main(arguments + ['--timed']), 0)
            launch.assert_called_once_with(arguments, True, 'venv')

        with patch('replay.entry.legacy.launch') as launch:
            self.assertEqual(main(arguments + ['--legacy-python', 'system']), 0)
            launch.assert_called_once_with(arguments, False, 'system')

        self.assertEqual(legacy.native_command(arguments)[0], '/opt/document-bench/.venv/bin/python')
        self.assertEqual(legacy.native_command(arguments, python_mode='system')[0], '/usr/bin/python3')

    def test_old_names_never_select_new_opm_tlc(self):
        self.assertEqual(OLD['opm'], 'pdf')
        self.assertEqual(OLD['tlc'], 'xlsx')
        self.assertEqual(HISTORICAL['opm_v2'], 'opm')
        self.assertEqual(HISTORICAL['tlc_v2'], 'tlc')
        self.assertNotIn('opm_v2', DEFAULT)
        self.assertNotIn('tlc_v2', DEFAULT)
        self.assertNotIn('opm_v2', NEW)
        self.assertNotIn('tlc_v2', NEW)
        with patch('replay.entry.legacy.validate'), \
             patch('replay.entry.suite.run_old_dataset', return_value=0) as run:
            self.assertEqual(main(['--dataset', 'opm', '--dataset', 'tlc', '--loops', '1']), 0)
            self.assertEqual([(r.args[1], r.args[0]) for r in run.call_args_list], [('pdf', 'opm'), ('xlsx', 'tlc')])

    def test_historical_aliases_route_to_derived_v1_engine_and_parent_recipes(self):
        from replay.common import ROOT as REPO_ROOT
        with patch('replay.entry.legacy.validate'), \
             patch('replay.entry.subprocess.call', return_value=0) as call:
            self.assertEqual(main(['--dataset', 'opm_v2', '--dataset', 'tlc_v2', '--loops', '1']), 0)
            command = call.call_args.args[0]
            self.assertIn(str(REPO_ROOT / 'replay/run.py'), command)
            datasets = [command[i + 1] for i, c in enumerate(command) if c == '--dataset']
            self.assertEqual(datasets, ['opm', 'tlc'])
            # The unified runner must never be used for the historical aliases.
            self.assertNotIn('--scene', command)

    def test_historical_alias_mixed_with_formal_runs_formal_first(self):
        # The derived-v1 engine replaces Skill links / source context, so the
        # formal unified-runner workloads must complete before it starts.
        order = []
        with patch('replay.entry.legacy.validate'), \
             patch('replay.entry.suite.run_old_dataset', side_effect=lambda *a, **k: order.append('old') or 0), \
             patch('replay.entry.suite.run_dataset', side_effect=lambda *a, **k: order.append('formal') or {'status': 'success'}), \
             patch('replay.entry.subprocess.call', side_effect=lambda c, **k: order.append('historical') or 0):
            self.assertEqual(main(['--dataset', 'retail', '--dataset', 'opm', '--dataset', 'opm_v2', '--loops', '1']), 0)
        self.assertEqual(order, ['old', 'formal', 'historical'])

    def test_timed_with_historical_alias_rejected_before_execution(self):
        with patch('replay.entry.legacy.validate') as validate, \
             patch('replay.entry.suite.run_old_dataset') as run_old, \
             patch('replay.entry.suite.run_dataset') as run_dataset, \
             patch('replay.entry.subprocess.call') as call:
            with self.assertRaises(SystemExit):
                main(['--dataset', 'opm_v2', '--timed', '--loops', '1'])
            with self.assertRaises(SystemExit):
                main(['--dataset', 'retail', '--dataset', 'tlc_v2', '--timed', '--loops', '1'])
            with self.assertRaises(SystemExit):
                main(['--dataset', 'retail', '--timed', '--workflow', 'derived-v1', '--loops', '1'])
        validate.assert_not_called()
        run_old.assert_not_called()
        run_dataset.assert_not_called()
        call.assert_not_called()

    def test_workflow_derived_v1_routes_all_new_selections_to_historical_engine(self):
        with patch('replay.entry.legacy.validate'), \
             patch('replay.entry.subprocess.call', return_value=0) as call:
            self.assertEqual(main(['--dataset', 'retail', '--dataset', 'opm_v2',
                                   '--workflow', 'derived-v1', '--loops', '1']), 0)
            command = call.call_args.args[0]
            datasets = [command[i + 1] for i, c in enumerate(command) if c == '--dataset']
            self.assertEqual(sorted(datasets), ['opm', 'retail'])

    def test_mutated_legacy_helper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            helper = root / 'helper.py'
            helper.write_text('changed')
            from replay.common import write
            lock = read(legacy.LEGACY / 'lock.json')
            lock = {
                'executor': {'version': 'unified-dataset-runner-v1',
                             'files': ['bin/run_document_scene_loop.py', 'bin/run_document_scene_loop_timed.py']},
                'workload': ['helper.py'],
                'files': {'helper.py': {'sha256': '0' * 64, 'mode': 420}}}
            write(root / 'lock.json', lock)
            with self.assertRaisesRegex(ValueError, 'legacy bytes changed'):
                legacy.validate(root)


if __name__ == '__main__':
    unittest.main()
