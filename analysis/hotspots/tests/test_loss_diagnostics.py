"""Small checks for the perf loss-statistics parser.

Covers: two stats blocks parsed separately without value bleed, a missing
`cycles:u stats:` block, explicit zeros vs missing stats (None), nonzero values,
multiple event blocks, and lost chunks from perf-record stderr.
"""
import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_profile import loss_diagnostics

AGG_WITH_LOSS = (
    "Aggregated stats:\n"
    "           TOTAL events:      100\n"
    "            LOST events:          5\n"
    "          SAMPLE events:       90\n"
    "    LOST_SAMPLES events:          2\n"
    "cycles:u stats:\n"
    "          SAMPLE events:       90\n"
    "    LOST_SAMPLES events:        7\n"
)


class LossDiagnosticsTests(unittest.TestCase):
    def test_two_blocks_do_not_bleed(self):
        d = loss_diagnostics('', AGG_WITH_LOSS)
        self.assertEqual(d['aggregated_lost_records'], 5)            # Aggregated block only
        self.assertEqual(d['aggregated_lost_sample_records'], 2)     # Aggregated block only
        self.assertEqual(d['cycles_u_stats_lost_samples'], 7)        # cycles:u block only
        self.assertEqual(d['aggregated_sample_events'], 90)
        self.assertEqual(d['cycles_u_stats_sample_events'], 90)

    def test_missing_cycles_block_is_unknown(self):
        d = loss_diagnostics('', 'Aggregated stats:\n LOST events: 2\n SAMPLE events: 10\n')
        self.assertEqual(d['aggregated_lost_records'], 2)
        self.assertIsNone(d['cycles_u_stats_lost_samples'])   # absent block -> None
        self.assertIsNone(d['cycles_u_stats_sample_events'])

    def test_missing_field_inside_present_block_is_unknown(self):
        d = loss_diagnostics('', 'Aggregated stats:\n SAMPLE events: 10\n')
        self.assertIsNone(d['aggregated_lost_records'])       # absent stat -> None
        self.assertIsNone(d['aggregated_lost_sample_records'])
        self.assertEqual(d['aggregated_sample_events'], 10)

    def test_explicit_zero_is_zero_not_unknown(self):
        d = loss_diagnostics('', 'Aggregated stats:\n LOST events: 0\n LOST_SAMPLES events: 0\n SAMPLE events: 10\n')
        self.assertEqual(d['aggregated_lost_records'], 0)
        self.assertEqual(d['aggregated_lost_sample_records'], 0)

    def test_lost_chunks_from_stderr(self):
        d = loss_diagnostics('Processed 100 events and lost 3 chunks!', 'Aggregated stats:\n SAMPLE events: 10\n')
        self.assertEqual(d['perf_record_reported_lost_chunks'], 3)
        self.assertIs(d['perf_record_reported_loss_warning'], True)
        d2 = loss_diagnostics('Captured and wrote file', 'Aggregated stats:\n SAMPLE events: 10\n')
        self.assertEqual(d2['perf_record_reported_lost_chunks'], 0)
        self.assertIs(d2['perf_record_reported_loss_warning'], False)

    def test_record_counts_are_not_quantified_samples(self):
        d = loss_diagnostics('lost 3 chunks', AGG_WITH_LOSS)
        # LOST/LOST_SAMPLES are record counts; never summed or converted
        self.assertIsNone(d['quantified_lost_samples'])
        self.assertIn('never summed', d['quantified_lost_samples_reason'])


if __name__ == '__main__':
    unittest.main()
