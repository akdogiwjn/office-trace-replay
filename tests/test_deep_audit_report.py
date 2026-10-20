import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'analysis/hotspot-comparison/scripts'))
from deep_audit_report import markdown_dataset_rows, output_unchanged


class DeepAuditReportTests(unittest.TestCase):
    def test_output_unchanged_is_derived_from_hashes(self):
        same = 'a' * 64
        different = 'b' * 64
        self.assertIs(output_unchanged(same, same.upper()), True)
        self.assertIs(output_unchanged(same, different), False)
        self.assertIsNone(output_unchanged(same, 'not-a-hash'))
        self.assertIsNone(output_unchanged(None, same))

    def test_markdown_row_does_not_trust_stored_boolean(self):
        digest = 'c' * 64
        rows = markdown_dataset_rows({
            'retail_online': {
                'output_sha256_before_audit': digest,
                'output_sha256_after_audit': digest,
                'output_unchanged': False,  # stale/manual value is ignored
                'independent_verification': {
                    'status': 'failed', 'checks_passed': 59, 'checks_total': 60,
                    'failures': ['source:number_formats_meaning:Online Retail'],
                },
                'audit_container_id': 'cid-1',
            },
        })
        self.assertIn('| retail_online | failed (59/60) | source:number_formats_meaning:Online Retail | 是 | cid-1 |', rows)


if __name__ == '__main__':
    unittest.main()
