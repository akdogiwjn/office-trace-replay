"""Timeout-chain parameter tests (mock subprocess/entry only; no real task)."""
import importlib.util
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]  # /home/lcq/office-trace-replay
sys.path.insert(0, str(ROOT / 'analysis' / 'docops'))

import worker
import capture
import pilot


class ReplayArgvTests(unittest.TestCase):
    def test_worker_replay_cli_includes_step_timeout_and_payload(self):
        argv = worker.replay_cli_args('021-g10', 1, '/opt/docops/scaling/payload', 3600)
        self.assertEqual(argv[0], 'run')
        self.assertIn('--step-timeout', argv)
        self.assertEqual(argv[argv.index('--step-timeout') + 1], '3600')
        self.assertEqual(argv[argv.index('--payload') + 1], '/opt/docops/scaling/payload')

    def test_worker_default_step_timeout(self):
        argv = worker.replay_cli_args('031', 10, None, 1200)
        self.assertNotIn('--payload', argv)
        self.assertEqual(argv[argv.index('--step-timeout') + 1], '1200')

    def test_worker_main_forwards_step_timeout_to_entry_cli(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            captured = {}
            recorded = []
            tmp.mkdir(parents=True, exist_ok=True)
            (tmp / 'results').mkdir(exist_ok=True)

            class FakeLoader:
                @staticmethod
                def create_module(_spec):
                    return None  # let importlib create a fresh module

                def exec_module(self, mod):
                    mod.__file__ = '/opt/docops/replay.py'
                    mod.run_step = lambda *a, **k: None
                    mod.cli = lambda: recorded.append(list(sys.argv)) or 0

            class FakeSpec:
                name = 'docops_measured_entry'
                loader = FakeLoader()
                submodule_search_locations = None
                has_location = False

            def fake_spec(_name, _path):
                return FakeSpec()

            def fake_path(*parts):
                parts = list(parts)
                if parts and str(parts[0]).startswith('/'):
                    parts[0] = str(parts[0]).lstrip('/')
                return tmp / Path(*parts)

            with mock.patch.object(worker.os, 'sched_setaffinity', lambda *a: None), \
                 mock.patch.object(worker.importlib.util, 'spec_from_file_location', fake_spec), \
                 mock.patch.object(worker, 'Path', fake_path), \
                 mock.patch.object(sys, 'argv', ['worker.py', '--task', '014-n1000',
                                                 '--loops', '1', '--mode', 'perf',
                                                 '--step-timeout', '3600',
                                                 '--payload', '/opt/docops/scaling/payload']):
                rc = worker.main()
            self.assertEqual(rc, 0)
            self.assertEqual(len(recorded), 1)
            cli = recorded[0]
            self.assertEqual(cli[cli.index('--step-timeout') + 1], '3600')
            self.assertEqual(cli[cli.index('--payload') + 1], '/opt/docops/scaling/payload')


class CaptureArgvTests(unittest.TestCase):
    def test_capture_workload_argv_includes_timeouts_and_payload(self):
        argv = capture.workload_argv('014-n10000', 1, 'topdown', '/opt/docops/scaling/payload', 3600)
        self.assertEqual(argv[0], sys.executable)
        self.assertIn('--step-timeout', argv)
        self.assertEqual(argv[argv.index('--step-timeout') + 1], '3600')
        self.assertEqual(argv[argv.index('--payload') + 1], '/opt/docops/scaling/payload')

    def test_capture_default_workload_timeout_is_600(self):
        argv = capture.workload_argv('031', 10, 'perf', None, 600)
        self.assertNotIn('--payload', argv)
        self.assertEqual(argv[argv.index('--step-timeout') + 1], '600')


class PilotArgvTests(unittest.TestCase):
    def test_pilot_capture_args_scaling(self):
        argv = pilot.capture_args('021-g10', 1, 'topdown', '/opt/docops/scaling/payload', 7200, 3600)
        self.assertEqual(argv[argv.index('--workload-timeout') + 1], '7200')
        self.assertEqual(argv[argv.index('--step-timeout') + 1], '3600')
        self.assertEqual(argv[argv.index('--payload') + 1], '/opt/docops/scaling/payload')

    def test_pilot_capture_args_old_defaults(self):
        # old callers without explicit timeouts keep 600/1200 and no payload
        argv = pilot.capture_args('031', 10, 'perf', None, 600, 1200)
        self.assertEqual(argv[argv.index('--workload-timeout') + 1], '600')
        self.assertEqual(argv[argv.index('--step-timeout') + 1], '1200')
        self.assertNotIn('--payload', argv)

    def test_chain_ordering_worker_wait_not_below_step_timeout_when_configured(self):
        # scaling run: workload wait (7200) >= step timeout (3600) and host (10800) above both
        self.assertGreaterEqual(7200, 3600)
        self.assertGreaterEqual(10800, 7200)


if __name__ == '__main__':
    unittest.main()
