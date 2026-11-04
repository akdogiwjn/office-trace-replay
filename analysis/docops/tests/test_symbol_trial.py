"""Symbol coverage uses physical leaf period and the full unchanged denominator."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import symbol_trial


class SymbolTrialTests(unittest.TestCase):
    def profile(self):
        return dict(roi_period=100, quality={'unknown_leaf_symbol_share': .3}, functions=[
            {'dso': '/libpython.so', 'function': '[unknown]', 'period': 20},
            {'dso': '/libxml.so', 'function': '0x1234', 'period': 10},
            {'dso': '/libpython.so', 'function': '_PyEval_EvalFrameDefault', 'period': 70}])

    def test_unknown_is_retained_in_full_period_denominator(self):
        value = symbol_trial.symbol_partition(self.profile())
        self.assertEqual(value['unknown_period'], 30)
        self.assertAlmostEqual(value['unknown_share'], .3)
        self.assertAlmostEqual(value['resolved_share'], .7)
        self.assertAlmostEqual(sum(r['share_roi'] for r in value['unresolved_dsos']), .3)

    def test_missing_period_cannot_upgrade_symbol_coverage(self):
        value = self.profile(); value['functions'].pop(1)
        with self.assertRaises(ValueError): symbol_trial.symbol_partition(value)

    def test_quality_summary_must_match_leaf_counts(self):
        value = self.profile(); value['quality']['unknown_leaf_symbol_share'] = .2
        with self.assertRaises(ValueError): symbol_trial.symbol_partition(value)

    def test_addresses_and_empty_frames_are_not_named_functions(self):
        for name in ('[unknown]', '[no-frame]', '0x123', 'abcdef123456'):
            self.assertTrue(symbol_trial.unresolved(name))
        for name in ('_PyEval_EvalFrameDefault', 'ScInterpreter::Interpret()'):
            self.assertFalse(symbol_trial.unresolved(name))


if __name__ == '__main__':
    unittest.main()
