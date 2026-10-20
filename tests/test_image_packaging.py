"""Small build-entry checks; never start Docker or a workload."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_image_packaging', ROOT / 'scripts/build_image.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ImagePackagingTests(unittest.TestCase):
    def test_context_keeps_frozen_nested_reports_but_excludes_host_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in ('reports/host.json', 'analysis/raw/data', 'tests/test.py',
                             'assets/evidence/reports/frozen.json', 'replay/main.py'):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'123')
            self.assertEqual(builder.context_estimate(root),
                             {'file_count': 2, 'payload_bytes_estimate': 6})

    def test_versions_have_distinct_evidence_paths(self):
        root = Path('/fixture')
        v10 = builder.evidence_paths('office-trace-replay:openeuler-v10', root)
        v11 = builder.evidence_paths('office-trace-replay:openeuler-v11', root)
        v12 = builder.evidence_paths('office-trace-replay:openeuler-v12', root)
        self.assertEqual(v10[0].name, 'image-build-v10.json')
        self.assertEqual(v11[1].name, 'image-install-acceptance-v11.json')
        self.assertEqual(v12[0].name, 'image-build-v12.json')
        self.assertTrue(set(v10).isdisjoint(v11))
        self.assertTrue(set(v11).isdisjoint(v12))

    def test_existing_evidence_refuses_before_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = builder.evidence_paths('office-trace-replay:openeuler-v12', root)
            record.parent.mkdir()
            record.write_text('preserve me')
            with patch.object(builder, 'ROOT', root), \
                    patch('sys.argv', ['build_image.py']), \
                    patch.object(builder, 'local_image_id', side_effect=AssertionError('Docker called')):
                with self.assertRaises(FileExistsError):
                    builder.main()
            self.assertEqual(record.read_text(), 'preserve me')


if __name__ == '__main__':
    unittest.main()
