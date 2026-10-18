import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/profile_artifacts.py"
spec = importlib.util.spec_from_file_location("profile_artifacts", SCRIPT)
artifacts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(artifacts)


class ProfileArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_root = artifacts.ROOT
        artifacts.ROOT = self.root
        for name in ("config", "metadata", "processed"):
            (self.root / name).mkdir()
        (self.root / "config/run-plan.json").write_text('{"configs": []}')
        self.content = b'{"profile": "frozen", "period": 123}\n'
        self.profile = self.root / "processed/all-profiles.json"
        self.profile.write_bytes(self.content)
        artifacts.pack()
        self.entry = json.loads((self.root / artifacts.MANIFEST).read_text())["files"][0]

    def tearDown(self):
        artifacts.ROOT = self.old_root
        self.temp.cleanup()

    def test_restore_preserves_exact_bytes_and_hash(self):
        self.profile.unlink()
        artifacts.restore_entry(self.entry)
        self.assertEqual(self.profile.read_bytes(), self.content)
        self.assertEqual(artifacts.digest(self.profile), hashlib.sha256(self.content).hexdigest())

    def test_corrupt_archive_does_not_publish_profile(self):
        self.profile.unlink()
        (self.root / self.entry["archive"]).write_bytes(b"corrupted")
        with self.assertRaisesRegex(ValueError, "compressed hash mismatch"):
            artifacts.restore_entry(self.entry)
        self.assertFalse(self.profile.exists())
        self.assertEqual(list(self.profile.parent.iterdir()), [self.profile.parent / "packed"])

    def test_existing_modified_profile_is_preserved(self):
        self.profile.write_bytes(b"local changes")
        with self.assertRaisesRegex(ValueError, "existing profile differs"):
            artifacts.restore_entry(self.entry)
        self.assertEqual(self.profile.read_bytes(), b"local changes")

    def test_profile_paths_cannot_escape_processed(self):
        with self.assertRaises(ValueError):
            artifacts.checked_path("../outside.json")
