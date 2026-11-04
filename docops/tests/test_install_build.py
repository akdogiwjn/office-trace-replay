"""Build and installation gates, using synthetic facts rather than containers."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'docker' / f'{name}.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


install = module('install_state_check')
build = module('verify_build_inputs')


class InstallBuildTests(unittest.TestCase):
    def facts(self):
        return {'payload': {'status': 'static_valid', 'tasks': 12}, 'environment': {}, 'extra': {
            'perf': {'present': True, 'rc': 0, 'version': 'perf version 6.1.190'},
            'soffice': {'present': True, 'rc': 0, 'version': 'LibreOffice 7.4.7.2'},
            'devkit': {'present': True, 'version_rc': 0, 'version': '26.0.RC1',
                       'libtuner_ldd_rc': 0, 'libtuner_unresolved': 0}}}

    def test_complete_installation_passes(self):
        self.assertEqual(install.acceptance_errors(self.facts(), lambda _: []), [])

    def test_missing_or_wrong_tools_and_unresolved_libraries_fail(self):
        for tool, field, value in [('perf', 'present', False), ('perf', 'rc', 1),
                                    ('soffice', 'version', 'wrong'),
                                    ('devkit', 'version_rc', 1), ('devkit', 'libtuner_unresolved', 1),
                                    ('devkit', 'libtuner_ldd_rc', 1)]:
            with self.subTest(tool=tool, field=field):
                facts = self.facts()
                facts['extra'][tool][field] = value
                self.assertTrue(install.acceptance_errors(facts, lambda _: []))

    def test_library_version_and_payload_failure_rejected(self):
        self.assertTrue(install.acceptance_errors(self.facts(), lambda _: ['wrong python']))
        facts = self.facts()
        facts['payload']['status'] = 'failed'
        self.assertTrue(install.acceptance_errors(facts, lambda _: []))

    def test_failed_check_returns_nonzero_and_never_starts_perf_record(self):
        fake = SimpleNamespace(validate_payload=lambda _: {'status': 'static_valid', 'tasks': 12},
                               check_environment=lambda _: {},
                               environment_errors=lambda _: ['missing python'])
        completed = SimpleNamespace(returncode=1, stdout='bad version', stderr='')
        with tempfile.TemporaryDirectory() as temp, \
             mock.patch.object(install, 'OUT', Path(temp) / 'install.json'), \
             mock.patch.object(install, 'load_replay', return_value=fake), \
             mock.patch.object(install.subprocess, 'run', return_value=completed) as run, \
             mock.patch('builtins.print'):
            self.assertEqual(install.main(), 1)
            record = json.loads(install.OUT.read_text())
            self.assertEqual(record['status'], 'failed')
            self.assertEqual(record['image']['actual_id'], 'unknown')
            self.assertTrue(all('record' not in call.args[0] for call in run.call_args_list))

    def test_vendor_hash_missing_extra_and_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            file = root / 'package'
            file.write_bytes(b'abc')
            records = [{'file': 'package', 'bytes': 3, 'sha256': hashlib.sha256(b'abc').hexdigest()}]
            build.verify_tree(root, records, 'file')
            file.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                build.verify_tree(root, records, 'file')
            file.unlink()
            with self.assertRaisesRegex(ValueError, 'inventory'):
                build.verify_tree(root, records, 'file')
            file.write_bytes(b'abc')
            (root / 'untracked').write_bytes(b'extra')
            with self.assertRaisesRegex(ValueError, 'inventory'):
                build.verify_tree(root, records, 'file')

    def test_vendor_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'data').write_bytes(b'abc')
            (root / 'link').symlink_to(root / 'data')
            records = [{'file': name, 'bytes': 3, 'sha256': hashlib.sha256(b'abc').hexdigest()}
                       for name in ('data', 'link')]
            with self.assertRaisesRegex(ValueError, 'escapes'):
                build.verify_tree(root, records, 'file')


if __name__ == '__main__':
    unittest.main()
