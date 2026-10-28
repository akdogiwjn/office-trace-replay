from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import repeat_plots
from summarize import METRICS


class RepeatPlotTests(unittest.TestCase):
    def series(self):
        return dict(runs=[dict(dataset_id=ds, repeat=r, points=[
            dict(sample_index=i, metrics={m: float(i + r) for m in METRICS}) for i in range(1, 4)])
            for ds in repeat_plots.LABELS for r in range(1, 6)])

    def test_exports_real_samples_and_all_nine_metrics_for_every_dataset(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(repeat_plots, 'ROOT', Path(tmp)):
            figures, version = repeat_plots.export(self.series(), Path(tmp))
            self.assertEqual(len(figures), 9)
            self.assertEqual(sum(not r['detail'] for r in figures), 2)
            self.assertTrue(version)
            for row in figures:
                path = Path(tmp) / row['filename']
                self.assertEqual(row['sha256'], repeat_plots.sha(path))
                text = path.read_text()
                for token in ('Sample index', 'Run 1', 'Run 5', 'Backend Bound'):
                    self.assertIn(token, text)
                if row['detail']:
                    self.assertIn('IPC', text)
                    self.assertIn('Fetch Bandwidth Bound', text)
                self.assertGreater(path.with_suffix('.png').stat().st_size, 1000)

    def test_run_boundaries_are_gaps_not_connected_or_interpolated(self):
        runs = self.series()['runs'][:5]
        parts = repeat_plots.segments(runs)
        self.assertEqual([xs for _, xs in parts], [[1, 2, 3], [6, 7, 8], [11, 12, 13],
                                                 [16, 17, 18], [21, 22, 23]])
        self.assertEqual([r for r, _ in parts], runs)
        runs[0]['points'][1]['sample_index'] = 3
        with self.assertRaisesRegex(ValueError, 'noncontiguous'):
            repeat_plots.segments(runs)

    def test_missing_repeat_is_rejected(self):
        series = self.series()
        series['runs'].pop()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'all five'):
                repeat_plots.export(series, Path(tmp))


if __name__ == '__main__':
    unittest.main()
