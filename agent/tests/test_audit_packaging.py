import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class PDFAuditPackaging(unittest.TestCase):
    def test_both_auditors_can_import_their_private_field_extractor(self):
        for dataset in ('irs_w4', 'sba1919'):
            with self.subTest(dataset=dataset), patch.object(sys, 'path', list(sys.path)):
                case = ROOT / 'datasets' / dataset
                spec = importlib.util.spec_from_file_location('audit_packaging_' + dataset, case / 'audit.py')
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                extractor = importlib.util.find_spec('extract_form_field_info')
                self.assertIsNotNone(extractor)
                self.assertEqual(Path(extractor.origin), case / 'skills/pdf/scripts/extract_form_field_info.py')

    def test_auditors_remain_materialized_from_template(self):
        expected = (ROOT / 'tools/audit.py.template').read_bytes()
        for case in (ROOT / 'datasets').iterdir():
            self.assertEqual((case / 'audit.py').read_bytes(), expected)


if __name__ == '__main__':
    unittest.main()
