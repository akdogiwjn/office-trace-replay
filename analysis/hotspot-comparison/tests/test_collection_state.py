import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / 'analysis/hotspot-comparison/scripts'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


collector = load('current_loop_collector', SCRIPTS / 'collect_current_loop_profiles.py')
exporter = load('bounded_perf_export', SCRIPTS / 'bounded_perf_export.py')


class CollectionStateTests(unittest.TestCase):
    def test_runner_failure_is_separate_from_later_export_status(self):
        summary = {'requested_iterations': 1, 'completed_iterations': 1,
                   'successes': 0, 'failures': 1}
        self.assertEqual(collector.workload_status(summary, 1), 'failed')
        eligible, stages = collector.native_profile_eligibility(
            workload='failed', record='not_run', export='not_run',
            parser='not_run', roi='not_run')
        self.assertFalse(eligible)
        self.assertEqual(stages['workload'], 'failed')

    def test_successful_workload_export_failure_is_not_workload_failure(self):
        summary = {'requested_iterations': 1, 'completed_iterations': 1,
                   'successes': 1, 'failures': 0}
        self.assertEqual(collector.workload_status(summary, 1), 'success')
        eligible, stages = collector.native_profile_eligibility(
            workload='success', record='success', export='failed',
            parser='not_run', roi='not_run')
        self.assertFalse(eligible)
        self.assertEqual(stages['workload'], 'success')
        self.assertEqual(stages['perf_export'], 'failed')

    def test_complete_export_is_separate_from_parse_and_roi_eligibility(self):
        eligible, _ = collector.native_profile_eligibility(
            workload='success', record='success', export='success',
            parser='failed', roi='not_run')
        self.assertFalse(eligible)

    def test_small_export_success_preserves_source_and_promotes_complete_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / 'tiny.data'
            raw.write_bytes(b'fixture perf data')
            command = ['python3', '-c', "import sys; sys.stdout.write('sample\\n')"]
            result = exporter.bounded_export(raw, root / 'samples.txt',
                                             root / 'status.json', 3, command=command)
            self.assertEqual(result['status'], 'complete')
            self.assertEqual((root / 'samples.txt').read_text(), 'sample\n')
            self.assertFalse((root / 'samples.txt.partial').exists())
            self.assertEqual(raw.read_bytes(), b'fixture perf data')

    def test_force_input_adds_perf_force_without_changing_read_only_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / 'capture.data'
            raw.write_bytes(b'fixture raw')
            output, status = root / 'samples.txt', root / 'status.json'
            seen = {}

            def fake_popen(argv, **kwargs):
                seen['argv'] = argv
                class Proc:
                    pid = 123
                    returncode = 0
                    def communicate(self, timeout=None):
                        kwargs['stdout'].write(b'sample\\n')
                return Proc()

            result = exporter.bounded_export(raw, output, status, 3,
                                             popen_factory=fake_popen,
                                             force_input=True)
            self.assertEqual(result['status'], 'complete')
            self.assertEqual(seen['argv'][:3], ['perf', 'script', '-f'])
            self.assertEqual(raw.read_bytes(), b'fixture raw')

    def test_failed_and_timed_out_export_keep_partial_stdout_and_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / 'tiny.data'
            raw.write_bytes(b'raw')
            failed = exporter.bounded_export(
                raw, root / 'failed.txt', root / 'failed.json', 3,
                command=['python3', '-c', "import sys; print('partial'); print('bad', file=sys.stderr); sys.exit(7)"])
            self.assertEqual(failed['status'], 'incomplete')
            self.assertEqual(failed['return_code'], 7)
            self.assertIn('partial', Path(failed['partial_output']).read_text())
            self.assertIn('bad', Path(failed['stderr_log']).read_text())
            timed = exporter.bounded_export(
                raw, root / 'timeout.txt', root / 'timeout.json', 0.1,
                command=['python3', '-c', "import time; print('partial', flush=True); time.sleep(5)"])
            self.assertEqual(timed['status'], 'incomplete')
            self.assertTrue(timed['timed_out'])
            self.assertIn('timeout', timed['reason'])
            self.assertIn('partial', Path(timed['partial_output']).read_text())
            before = Path(timed['partial_output']).read_bytes()
            not_retried = exporter.bounded_export(
                raw, root / 'timeout.txt', root / 'timeout.json', 0.1,
                command=['python3', '-c', "raise SystemExit(0)"])
            self.assertEqual(not_retried['status'], 'not_started')
            self.assertEqual(Path(timed['partial_output']).read_bytes(), before)
            self.assertEqual(raw.read_bytes(), b'raw')

    def test_duplicate_success_and_timeout_targets_are_byte_preserving(self):
        for state in ('success', 'timeout'):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                raw = root / 'tiny.data'
                raw.write_bytes(b'raw')
                output, status = root / 'samples.txt', root / 'status.json'
                partial = output.with_name(output.name + '.partial')
                stderr = output.with_name(output.name + '.stderr.log')
                contents = {
                    'success': {output: b'complete export', stderr: b'old stderr',
                                status: b'{"status":"complete","historical":true}\n'},
                    'timeout': {partial: b'partial export', stderr: b'timeout diagnostic',
                                status: b'{"status":"incomplete","timed_out":true}\n'},
                }[state]
                for path, data in contents.items():
                    path.write_bytes(data)
                before = {path: path.read_bytes() for path in
                          (output, partial, stderr, status) if path.exists()}
                launch = unittest.mock.Mock(side_effect=AssertionError('export process launched'))
                result = exporter.bounded_export(raw, output, status, 3,
                                                 command=['must-not-run'], popen_factory=launch)
                self.assertEqual(result['status'], 'not_started')
                self.assertIn('refused', result['reason'])
                launch.assert_not_called()
                self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_duplicate_target_cli_prints_refusal_and_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw, output, status = root / 'tiny.data', root / 'samples.txt', root / 'status.json'
            raw.write_bytes(b'raw')
            output.with_name(output.name + '.stderr.log').write_bytes(b'preserve me')
            before = output.with_name(output.name + '.stderr.log').read_bytes()
            stdout = io.StringIO()
            with patch('sys.argv', ['bounded_perf_export.py', str(raw), str(output), str(status)]), \
                 redirect_stdout(stdout):
                rc = exporter.main()
            result = json.loads(stdout.getvalue())
            self.assertEqual(rc, 1)
            self.assertEqual(result['status'], 'not_started')
            self.assertEqual(result['existing_artifacts'],
                             [str(output.with_name(output.name + '.stderr.log'))])
            self.assertEqual(output.with_name(output.name + '.stderr.log').read_bytes(), before)
            self.assertFalse(status.exists())


if __name__ == '__main__':
    unittest.main()
