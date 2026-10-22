"""Small fixtures for byte-preserving offline asset distribution."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'distribution/assets.py'
spec = importlib.util.spec_from_file_location('offline_assets', SCRIPT)
assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)


class OfflineAssetTests(unittest.TestCase):
    def fixture(self, root):
        payload = b'frozen workbook bytes\x00\xff'
        manifest = {'schema_version': 'office-offline-assets-v1', 'files': [
            {'path': name, 'size_bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(),
             'mode': 0o644} for name in ('input/source.xlsx', 'seed/source.xlsx')]}
        (root / 'distribution').mkdir(parents=True)
        (root / assets.MANIFEST).write_text(json.dumps(manifest))
        for entry in manifest['files']:
            path = root / entry['path']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        return assets.Assets(root)

    def test_bundle_round_trip_deduplicates_and_preserves_existing_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'source'
            source = self.fixture(root)
            bundle, store = Path(tmp) / 'offline.tar', Path(tmp) / 'store'
            result = source.export(store, bundle)
            self.assertEqual(result['unique_objects'], 1)
            with tarfile.open(bundle) as archive:
                self.assertEqual(len(archive.getnames()), 2)
            (root / 'seed/source.xlsx').unlink()
            before = (root / 'input/source.xlsx').stat().st_mtime_ns
            self.assertEqual(source.restore(bundle=bundle)['restored_files'], 1)
            self.assertEqual((root / 'input/source.xlsx').stat().st_mtime_ns, before)
            self.assertEqual(source.verify()['status'], 'success')

    def test_store_round_trip_and_export_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'source'
            source = self.fixture(root)
            bundle, store = Path(tmp) / 'offline.tar', Path(tmp) / 'store'
            source.export(store, bundle)
            for item in source.files:
                source.path(item).unlink()
            self.assertEqual(source.restore(store=store)['restored_files'], 2)
            before = bundle.read_bytes()
            with self.assertRaises(FileExistsError):
                source.export(store, bundle)
            self.assertEqual(bundle.read_bytes(), before)

    def test_conflicting_destination_rejected_before_any_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.fixture(Path(tmp) / 'source')
            bundle, store = Path(tmp) / 'offline.tar', Path(tmp) / 'store'
            source.export(store, bundle)
            source.path(source.files[0]).unlink()
            conflict = source.path(source.files[1])
            conflict.write_bytes(b'user modified data')
            with self.assertRaisesRegex(ValueError, 'refusing to overwrite'):
                source.restore(bundle=bundle)
            self.assertFalse(source.path(source.files[0]).exists())
            self.assertEqual(conflict.read_bytes(), b'user modified data')

    def test_corrupt_store_rejected_before_any_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.fixture(Path(tmp) / 'source')
            bundle, store = Path(tmp) / 'offline.tar', Path(tmp) / 'store'
            source.export(store, bundle)
            for item in source.files:
                source.path(item).unlink()
            (store / 'objects/sha256' / source.files[0]['sha256']).write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'hash/size mismatch'):
                source.restore(store=store)
            self.assertTrue(all(not source.path(item).exists() for item in source.files))

    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.fixture(root)
            manifest = source.manifest
            manifest['files'][0]['path'] = '../outside.xlsx'
            (root / assets.MANIFEST).write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'unsafe'):
                assets.Assets(root)

    def test_wrong_manifest_is_rejected_without_restoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.fixture(Path(tmp) / 'source')
            bundle, store = Path(tmp) / 'offline.tar', Path(tmp) / 'store'
            source.export(store, bundle)
            source.path(source.files[0]).unlink()
            (store / 'manifest.json').write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError, 'different manifest'):
                source.restore(store=store)
            self.assertFalse(source.path(source.files[0]).exists())

    def test_symlink_bundle_object_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.fixture(Path(tmp) / 'source')
            bundle = Path(tmp) / 'unsafe.tar'
            with tarfile.open(bundle, 'w') as archive:
                info = tarfile.TarInfo('manifest.json')
                info.size = len(source.manifest_bytes)
                archive.addfile(info, io.BytesIO(source.manifest_bytes))
                info = tarfile.TarInfo('objects/sha256/' + source.files[0]['sha256'])
                info.type, info.linkname = tarfile.SYMTYPE, '/etc/passwd'
                archive.addfile(info)
            source.path(source.files[0]).unlink()
            with self.assertRaisesRegex(ValueError, 'regular file'):
                source.restore(bundle=bundle)
            self.assertFalse(source.path(source.files[0]).exists())


if __name__ == '__main__':
    unittest.main()
