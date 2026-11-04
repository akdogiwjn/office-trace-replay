from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import capture
import quality


class ArchiveTests(unittest.TestCase):
    def test_streams_raw_and_binds_final_collection_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            raw = out/'perf.data'
            raw.write_bytes(b'0123456789' * 250_000)
            expected = hashlib.sha256(raw.read_bytes()).hexdigest()
            state = {'status': 'passed', 'record_returncode': 0}
            capture.write(out/'collection.json', state)
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('whole-file read')):
                self.assertTrue(capture.archive_evidence(out, state))
            index = json.loads((out/'sha256-index.json').read_text())['files']
            self.assertEqual(index['perf.data']['sha256'], expected)
            self.assertEqual(index['collection.json']['sha256'], quality.file_sha256(out/'collection.json'))

    def test_unreadable_raw_preserves_acquisition_but_fails_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            (out/'perf.data').write_bytes(b'raw')
            state = {'status': 'passed', 'record_returncode': 0, 'workflow_status': 'passed'}
            capture.write(out/'collection.json', state)
            with patch.object(capture, 'file_sha256', side_effect=PermissionError('fixture')):
                self.assertFalse(capture.archive_evidence(out, state))
            final = json.loads((out/'collection.json').read_text())
            self.assertEqual(final['status'], 'failed')
            self.assertEqual(final['record_returncode'], 0)
            self.assertEqual(final['workflow_status'], 'passed')
            self.assertTrue((out/'archive-error.json').is_file())
            self.assertFalse((out/'sha256-index.json').exists())

    def test_index_write_failure_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            state = {'status': 'passed'}
            capture.write(out/'collection.json', state)
            original_write = capture.write

            def fail_index(path, value):
                if path.name == 'sha256-index.json':
                    raise OSError('fixture index publication failure')
                original_write(path, value)

            with patch.object(capture, 'write', side_effect=fail_index):
                self.assertFalse(capture.archive_evidence(out, state))
            self.assertEqual(json.loads((out/'collection.json').read_text())['status'], 'failed')
            self.assertIn('index publication', json.loads((out/'archive-error.json').read_text())['error'])


if __name__ == '__main__':
    unittest.main()
