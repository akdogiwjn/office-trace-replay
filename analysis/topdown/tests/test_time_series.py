import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from time_series import parse_intervals, load_campaign
from summarize import METRICS

VALUES = (1.2, 5, 15, 60, 20, 45, 15, 12, 3)


def block(number, cycles, instructions):
    return '\n'.join([f'TOP-DOWN Summary Report-{number}  Time:2026/10/28 12:00:01',
                      f'Cycles {cycles}', f'Instructions {instructions}',
                      *[f'  {m} {v:.2f}  --' for m, v in zip(METRICS, VALUES)]])


def fixture():
    return '\n'.join([block(1, 10, 12), block(2, 20, 24), block('ALL', 30, 36)])


class TimeSeriesTests(unittest.TestCase):
    def test_intervals_remain_separate_and_all_is_not_a_sample(self):
        data = parse_intervals(fixture())
        self.assertEqual([p['sample_index'] for p in data['points']], [1, 2])
        self.assertEqual([p['cycles'] for p in data['points']], [10, 20])
        self.assertEqual(data['final']['cycles'], 30)
        self.assertEqual(data['interval_counter_deltas'], dict(cycles=0, instructions=0))

    def test_single_printed_unit_is_recorded_without_adjusting_counts(self):
        data = parse_intervals(fixture().replace('Cycles 30', 'Cycles 29'))
        self.assertEqual(data['interval_counter_deltas']['cycles'], 1)
        self.assertEqual(data['final']['cycles'], 29)

    def test_missing_points_bad_hierarchy_and_counter_mismatch_rejected(self):
        cases = [fixture().replace('Report-2', 'Report-3'),
                 fixture().replace('Report-ALL', 'Report-3'),
                 fixture().replace('Core Bound 45.00', 'Core Bound 40.00'),
                 fixture().replace('Cycles 30', 'Cycles 50'),
                 fixture().replace('IPC 1.20  --', 'missing')]
        for text in cases:
            with self.subTest(text=text[-80:]), self.assertRaises(ValueError):
                parse_intervals(text)

    def test_capture_hash_and_qualified_final_metrics_are_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'raw/out').mkdir(parents=True)
            source = root / 'raw/out/devkit.stdout.txt'
            source.write_text(fixture())
            summary = dict(metrics=dict(zip(METRICS, VALUES)), evidence_hashes={
                'out/devkit.stdout.txt': hashlib.sha256(source.read_bytes()).hexdigest()})
            (root / 'summary.json').write_text(json.dumps(summary))
            campaign = dict(completed=[dict(dataset_id='opm', repeat=1, raw='raw', summary='summary.json')])
            result = load_campaign(campaign, root)
            self.assertEqual(result['total_points'], 2)
            self.assertIn('no per-interval idle', result['idle_policy'])
            source.write_text(fixture() + '\nchanged')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                load_campaign(campaign, root)


if __name__ == '__main__':
    unittest.main()
