import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    'prepare_checkout', Path(__file__).resolve().parents[1] / 'scripts/prepare_checkout.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CheckoutPermissions(unittest.TestCase):
    def fixture(self, root):
        path = root / 'document-oe/assets/input.txt'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'frozen input')
        path.chmod(0o644)
        record = {'workload_files': {'input.txt': {
            'size': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'mode': 0o664}}}
        (root / 'document-oe/lock.json').write_text(json.dumps(record))
        return path

    def test_restore_permissions_without_changing_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = self.fixture(root)
            result = module.prepare(root)
            self.assertEqual(result['permissions_restored'], 1)
            self.assertEqual(path.stat().st_mode & 0o777, 0o664)
            self.assertEqual(path.read_bytes(), b'frozen input')
            self.assertEqual(module.prepare(root)['permissions_restored'], 0)

    def test_changed_input_is_rejected_before_permissions_are_restored(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = self.fixture(root)
            path.write_bytes(b'modified data')
            with self.assertRaisesRegex(ValueError, 'changed workload'):
                module.prepare(root)
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)
