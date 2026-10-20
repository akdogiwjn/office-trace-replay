"""Offline accounting regressions; no workload, Docker or real workbook."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/analyze_cpu_measurement.py'
SPEC = importlib.util.spec_from_file_location('cpu_measurement_analysis_fixture', SCRIPT)
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


class MonitorWindowTests(unittest.TestCase):
    def monitor(self, points):
        monitor = analysis.Monitor.__new__(analysis.Monitor)
        monitor.series = {3: {3: points}}
        return monitor

    def test_processes_entirely_before_or_after_roi_contribute_nothing(self):
        for points in ([(1, 10), (5, 100)], [(30, 100), (40, 200)]):
            self.assertEqual(self.monitor(points).window_ticks(3, 10, 20), {})

    def test_does_not_take_first_counter_after_roi_end(self):
        self.assertEqual(self.monitor([(5, 100), (15, 130), (25, 170)])
                         .window_ticks(3, 10, 20), {3: 30})

    def test_new_thread_inside_roi_has_zero_baseline(self):
        self.assertEqual(self.monitor([(12, 10), (18, 40)])
                         .window_ticks(3, 10, 20), {3: 40})

    def test_decreasing_counter_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'counter decreased'):
            self.monitor([(5, 100), (15, 90)]).window_ticks(3, 10, 20)

    def test_shell_text_is_not_entry_or_helper_identity(self):
        command = '/bin/bash -c "python /opt/project/replay/entry.py; soffice --version"'
        self.assertFalse(analysis.is_workload_entry(command))
        self.assertEqual(analysis.command_role(command), 'shell')
        self.assertEqual(analysis.command_role('python .enhance_workbook.runtime.py'), 'helper')
        self.assertEqual(analysis.command_role('python input/verify_xlsx_enhanced.py'), 'verifier')


class ShutdownAccountingTests(unittest.TestCase):
    def fixture(self, root, snapshot_ns=500_000_000):
        def write(name, data, lines=False):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text((''.join(json.dumps(row) + '\n' for row in data)
                             if lines else json.dumps(data)), encoding='utf-8')
        write('clock-anchor.json', {'real_ns': 0, 'mono_ns': 0})
        write('workload/xlsx/run/summary.json', {
            'requested_iterations': 1, 'completed_iterations': 1,
            'successes': 1, 'failures': 0})
        write('workload/xlsx/run/iterations.jsonl', [{
            'finished_at': '1970-01-01T00:00:02+00:00',
            'elapsed_seconds': 1, 'reset_seconds': 0, 'status': 'success'}], True)
        write('workspace-parent/CASE/output/business_verification.json',
              {'status': 'success', 'failures': []})
        identities = [
            (900_000_000, 1, 0, 'bash', '/bin/bash -c "python /opt/project/replay/entry.py"'),
            (900_000_000, 25, 1, 'python', 'python /opt/project/replay/entry.py'),
            (1_100_000_000, 30, 25, 'python', 'python inspect_xlsx.py source'),
            (2_100_000_000, 40, 25, 'python', 'python post_roi.py'),
        ]
        write('monitor/identity.jsonl', [dict(zip(
            ['t_ns', 'pid', 'ppid', 'comm', 'cmdline'], row)) for row in identities], True)
        samples = []
        for time_ns, runner_ticks, child_ticks in [
                (950_000_000, 10, None), (1_100_000_000, 10, 10),
                (1_500_000_000, 10, 40), (1_900_000_000, 11, 80),
                (2_100_000_000, 12, None)]:
            threads = [[25, 25, 'python', runner_ticks, 0]]
            if child_ticks is not None:
                threads.append([30, 30, 'python', child_ticks, 0])
            if time_ns > 2_000_000_000:
                threads.append([40, 40, 'python', 100, 0])
            samples.append({'t_ns': time_ns, 'threads': threads})
        write('monitor/monitor.jsonl', samples, True)
        empty = {key: {'cpu_ns': 0, 'calls': 0} for key in
                 ['load_workbook', 'readonly_lazy_parse', 'workbook_save']}
        write('ledgers/ledger-25.json', {'pid': 25, 'cpu_total_process_time_ns': 200_000_000,
                                       'buckets': empty})
        buckets = {key: {'cpu_ns': value, 'calls': 1} for key, value in
                   [('load_workbook', 200_000_000), ('readonly_lazy_parse', 50_000_000),
                    ('workbook_save', 100_000_000)]}
        write('ledgers/ledger-30.json', {'pid': 30, 'cpu_total_process_time_ns': snapshot_ns,
                                       'buckets': buckets})

    def test_shutdown_cpu_not_replaced_by_smaller_atexit_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            result = analysis.analyse(root)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['entry_pid'], 25)
        self.assertAlmostEqual(result['denominator_seconds'], 81 / analysis.CLK_TCK)
        self.assertEqual(result['numerator_union_seconds'], .35)
        self.assertEqual(result['excluded_outside_roi_pids'], [40])
        diff = next(row for row in result['crosscheck'] if row['pid'] == 30)
        self.assertAlmostEqual(diff['monitor_minus_atexit_seconds'],
                               80 / analysis.CLK_TCK - .5)

    def test_monitor_snapshot_difference_preserves_both_directions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, snapshot_ns=900_000_000)
            result = analysis.analyse(root)
        diff = next(row for row in result['crosscheck'] if row['pid'] == 30)
        expected = 80 / analysis.CLK_TCK - .9
        self.assertAlmostEqual(diff['monitor_minus_atexit_seconds'], expected)
        self.assertAlmostEqual(diff['absolute_difference_seconds'], abs(expected))
        self.assertAlmostEqual(result['denominator_seconds'], 81 / analysis.CLK_TCK)


if __name__ == '__main__':
    unittest.main()
