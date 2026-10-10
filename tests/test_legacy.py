import copy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from replay.common import digest, read
from replay import legacy
from replay.entry import OLD, NEW, DEFAULT, main


class LegacyCompatibilityTests(unittest.TestCase):
    def test_original_recipe_calls_and_defaults_are_preserved(self):
        lock = legacy.validate()
        self.assertEqual(lock['files']['bin/run_document_scene_loop.py']['sha256'],
                         '5f1f5d2ab8075ded5b12e6e583c0b733de09389c2c60d63d735c82a252d7c2d1')
        from replay.run import document_executor
        core = document_executor()
        self.assertEqual(core.LOOP_COUNT, 20000)
        self.assertEqual(core.PDF_APPLICANT_COUNT, 1)
        self.assertEqual(core.SCENES['xlsx']['recalc_timeout'], 600)
        expected = {'pdf': ('f1f90debf96d444f8fd56e9f4f2a3193f54e7786697c5b6fcbb2526d2a2e57b5', 21),
                    'xlsx': ('53a475924f0bf6f2b2fef4e85c13bae467241e5785ba7867e195422d2e9b07f2', 15)}
        for kind, (sha, count) in expected.items():
            p = legacy.LEGACY / 'operations' / (kind + '_key_operations.json')
            self.assertEqual(digest(p), sha)
            recipe = read(p)
            self.assertEqual(sum(len(s['source_tool_calls']) for s in recipe['key_operations']), count)
            core.load_recipe(p, kind, core.SCENES[kind]['step_order'])

    def test_native_scene_and_timing_flags_are_forwarded_verbatim(self):
        arguments = ['--scene', 'pdf', '--loops', '3', '--pdf-applicant-count', '10', '--recalc-timeout', '180']
        with patch('replay.entry.legacy.launch') as launch:
            self.assertEqual(main(arguments), 0)
            launch.assert_called_once_with(arguments, False, 'system')
        with patch('replay.entry.legacy.launch') as launch:
            self.assertEqual(main(arguments + ['--timed']), 0)
            launch.assert_called_once_with(arguments, True, 'system')

        self.assertEqual(legacy.native_command(arguments)[0], '/usr/bin/python3')
        self.assertEqual(legacy.native_command(arguments, python_mode='venv')[0], '/opt/document-bench/.venv/bin/python')

    def test_old_names_never_select_new_opm_tlc(self):
        self.assertEqual(OLD['opm'], 'pdf')
        self.assertEqual(OLD['tlc'], 'xlsx')
        self.assertEqual(NEW['opm_v2'], 'opm')
        self.assertEqual(NEW['tlc_v2'], 'tlc')
        self.assertNotIn('opm_v2', DEFAULT)
        self.assertNotIn('tlc_v2', DEFAULT)
        with patch('replay.entry.legacy.validate'), patch('replay.entry.subprocess.call', return_value=0) as call:
            self.assertEqual(main(['--dataset', 'opm', '--dataset', 'tlc', '--loops', '1']), 0)
            commands = [c.args[0] for c in call.call_args_list]
            self.assertEqual([c[c.index('--scene') + 1] for c in commands], ['pdf', 'xlsx'])
            self.assertTrue(all('run.py' not in ' '.join(c) for c in commands))

    def test_mutated_legacy_helper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            helper = root / 'helper.py'
            helper.write_text('changed')
            from replay.common import write
            write(root / 'lock.json', {'files': {'helper.py': {'sha256': '0' * 64, 'mode': 420}}})
            with self.assertRaisesRegex(ValueError, 'legacy bytes changed'):
                legacy.validate(root)


if __name__ == '__main__':
    unittest.main()
