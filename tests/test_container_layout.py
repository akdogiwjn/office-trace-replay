import fcntl
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


class SingleImage(unittest.TestCase):
    def test_one_dockerfile_contains_both_entries_and_seven_datasets(self):
        self.assertEqual(list(ROOT.glob('*/Dockerfile')), [])
        text = (ROOT / 'Dockerfile').read_text()
        self.assertEqual(sum(line.startswith('FROM ') for line in text.splitlines()), 1)
        self.assertIn('COPY agent/', text)
        self.assertIn('COPY document-oe/', text)
        self.assertIn('--validate-only --installed', text)
        contract = json.loads((ROOT / 'container-contract.json').read_text())
        entries = contract['entries']
        datasets = [n for item in entries.values() for n in item['datasets']]
        self.assertEqual(len(datasets), 7)
        self.assertEqual(len(set(datasets)), 7)
        for item in entries.values(): self.assertTrue((ROOT / item['path']).is_file())

    def test_all_five_use_same_target_image_but_preserve_source_environment(self):
        contract = json.loads((ROOT / 'container-contract.json').read_text())
        for case in (ROOT / 'agent/datasets').iterdir():
            actual = json.loads((case / 'replay-environment.json').read_text())
            source = json.loads((case / 'environment.json').read_text())
            self.assertEqual(actual['image_id'], contract['base_image_id'])
            self.assertEqual(actual['libreoffice'], contract['libreoffice'])
            self.assertNotEqual(source['image_id'], actual['image_id'])
            self.assertTrue((case / 'runtime/bin/soffice').stat().st_mode & 0o111)

    def test_new_old_new_context_switch_keeps_skill_code_separate(self):
        old = module(ROOT / 'document-oe/run.py', 'context_old')
        new = module(ROOT / 'agent/datasets/egrid/run.py', 'context_new')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); case = root / 'new-case'; (case / 'seed/input').mkdir(parents=True)
            (case / 'scripts').mkdir(); (case / 'skills/xlsx').mkdir(parents=True)
            legacy = root / 'old-skills'
            for name in ('pdf', 'xlsx'): (legacy / name).mkdir(parents=True)
            links = root / 'links'
            recipe = dict(kind='xlsx', workspace=str(root / 'workspace'))
            with patch.object(new, 'HERE', case):
                new.prepare(recipe, skill_directory=links)
                self.assertEqual((links / 'xlsx').resolve(), case / 'skills/xlsx')
                old.restore_skill_links(links, legacy)
                self.assertEqual((links / 'xlsx').resolve(), legacy / 'xlsx')
                new.prepare(recipe, skill_directory=links)
                self.assertEqual((links / 'xlsx').resolve(), case / 'skills/xlsx')
            self.assertTrue((legacy / 'xlsx').is_dir())

    def test_parallel_old_entry_rejected_before_context_change(self):
        old = module(ROOT / 'document-oe/run.py', 'parallel_old')
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / 'shared.lock'
            with lock.open('w') as first:
                fcntl.flock(first, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch.object(old, 'restore_skill_links') as restore, patch.object(old.subprocess, 'call') as call:
                    with self.assertRaises(BlockingIOError): old.run_locked([], {}, lock)
                    restore.assert_not_called(); call.assert_not_called()
        for case in (ROOT / 'agent/datasets').iterdir():
            self.assertIn('/tmp/office-agent-replay.lock', (case / 'run.py').read_text())

    def test_new_entry_does_not_dispatch_old_workload(self):
        entry = module(ROOT / 'agent/replay.py', 'family_entry')
        self.assertEqual(set(entry.DATASETS), {'egrid', 'hr_metro', 'industry_productivity', 'irs_w4', 'sba1919'})


if __name__ == '__main__':
    unittest.main()
