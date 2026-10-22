import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / 'analysis/hotspot-comparison/scripts/analyze_comparison.py'
SPEC = importlib.util.spec_from_file_location('hotspot_analyze_comparison', MODULE_PATH)
ANALYSIS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYSIS)
REPORT_SPEC = importlib.util.spec_from_file_location(
    'hotspot_generate_report', ROOT / 'analysis/hotspot-comparison/scripts/generate_report.py')
REPORT = importlib.util.module_from_spec(REPORT_SPEC)
REPORT_SPEC.loader.exec_module(REPORT)


class FutureAnalysisSelectionTests(unittest.TestCase):
    def test_forward_xlsx_comparison_uses_industry_not_manufacturing(self):
        self.assertEqual(ANALYSIS.selected_xlsx_ids(),
                         ['tlc', 'retail_online', 'hr_metro', 'industry_productivity'])
        self.assertNotIn('manufacturing', ANALYSIS.selected_xlsx_ids())
        self.assertEqual(ANALYSIS.selected_profile_ids(), [
            'opm-n1', 'opm-n10', 'tlc', 'irs_w4-n1', 'irs_w4-n10',
            'sba1919-n1', 'sba1919-n10', 'retail_online', 'hr_metro',
            'industry_productivity'])

    def test_manual_hashes_are_valid_and_match_formal_manifests(self):
        self.assertTrue(ANALYSIS.validate_manual_input_hashes())
        selection = ANALYSIS.active_comparison_selection()
        selection['manual_adaptations']['retail_online']['input_sha256'] = 'a' * 63
        with self.assertRaisesRegex(ValueError, '64 hexadecimal'):
            ANALYSIS.validate_manual_input_hashes(selection)

    def test_registered_dataset_without_profile_is_not_emitted_as_zero(self):
        self.assertIn('retail_online', ANALYSIS.selected_xlsx_ids())
        self.assertEqual(ANALYSIS.new_hotspots({}, write_outputs=False), [])

    def test_historical_manufacturing_profile_is_not_deleted(self):
        selection = ANALYSIS.active_comparison_selection()
        self.assertEqual(selection['excluded_from_future_comparisons']['manufacturing']
                         .startswith('Owner requested replacement'), True)
        self.assertIn('manufacturing', selection['excluded_from_future_comparisons'])
        self.assertNotIn('manufacturing', REPORT.CONFIG_ORDER)
        self.assertIn('industry_productivity', REPORT.CONFIG_ORDER)
        self.assertIn('retail_online', REPORT.CONFIG_ORDER)
        self.assertIn('hr_metro', REPORT.CONFIG_ORDER)


if __name__ == '__main__':
    unittest.main()
