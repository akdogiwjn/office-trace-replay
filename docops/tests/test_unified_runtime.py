"""Fixed replay runtime contracts; synthetic facts only, no task or sampler."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


replay = module('unified_replay_test', ROOT/'replay.py')
install = module('unified_install_test', ROOT/'docker/install_state_check.py')


class UnifiedRuntimeTests(unittest.TestCase):
    def test_soffice_adapter_preserves_explicit_profiles_and_arguments(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root/'target'
            target.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            target.chmod(0o755)
            wrapper = root/'soffice'
            wrapper.write_text((ROOT/'docker/soffice-unified').read_text().replace(
                '/usr/local/bin/soffice', str(target)))
            wrapper.chmod(0o755)
            args = ['--headless', 'a file.xlsx']
            cp = subprocess.run([str(wrapper), *args], check=True, capture_output=True, text=True,
                                env=dict(os.environ, HOME=str(root)))
            self.assertEqual(cp.stdout.splitlines(), ['-env:UserInstallation='+ (root/'.config/libreoffice/4').as_uri(), *args])
            explicit = ['-env:UserInstallation=file:///tmp/explicit', *args]
            cp = subprocess.run([str(wrapper), *explicit], check=True, capture_output=True, text=True)
            self.assertEqual(cp.stdout.splitlines(), explicit)

    def facts(self):
        facts = {k: {'present': True, 'version': v} for k, v in replay.UNIFIED_VERSIONS.items()}
        facts.update(runtime_profile=replay.UNIFIED_PROFILE, optional_numpy_present=False,
                     skills={k: True for k in ('doc', 'xlsx', 'pptx', 'pdf')},
                     payload_catalog=True, payload_tasks=list(range(12)))
        facts['python']['prefix'] = '/opt/docops/venv'
        facts['frozen_font_sources'] = {name: True for name in replay.UNIFIED_FONT_SHA256}
        for name in replay.UNIFIED_REQUIRED_TOOLS:
            if name in ('python', 'python3'):
                continue
            facts[name] = {'present': True}
        facts['python3'] = {'present': True}
        return facts

    def test_unified_fixed_versions_pass_and_wrong_interpreter_rejected(self):
        self.assertEqual(replay.environment_errors(self.facts()), [])
        for key, value in [('version', '3.12.14'), ('prefix', '/opt/document-bench/.venv')]:
            facts = self.facts(); facts['python'][key] = value
            self.assertTrue(replay.environment_errors(facts))

    def test_optional_blas_and_wrong_pdf_version_rejected(self):
        facts = self.facts(); facts['optional_numpy_present'] = True
        self.assertTrue(replay.environment_errors(facts))
        facts = self.facts(); facts['pypdf']['version'] = '6.16.2'
        self.assertTrue(replay.environment_errors(facts))

    def test_missing_diagnostic_command_rejected_before_workflow(self):
        facts = self.facts(); facts['rg'] = {'present': False}
        self.assertIn('missing tool: rg', replay.environment_errors(facts))

    def test_missing_or_wrong_task_font_rejected_before_workflow(self):
        for value in ({}, {name: False for name in replay.UNIFIED_FONT_SHA256}):
            facts = self.facts(); facts['frozen_font_sources'] = value
            self.assertIn('missing or mismatched frozen font sources', replay.environment_errors(facts))

    def test_installed_declaration_and_historical_default(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'profile.json'
            with mock.patch.object(replay, 'RUNTIME_PROFILE_PATH', path):
                self.assertEqual(replay.runtime_profile(), replay.LEGACY_PROFILE)
                path.write_text(json.dumps({'schema': 'docops-runtime-profile-v1', 'id': replay.UNIFIED_PROFILE}))
                self.assertEqual(replay.runtime_profile(), replay.UNIFIED_PROFILE)
                path.write_text(json.dumps({'schema': 'docops-runtime-profile-v1', 'id': 'custom-unchecked'}))
                with self.assertRaises(ValueError): replay.runtime_profile()

    def test_installation_requires_matching_unified_native_tools(self):
        result = {'payload': {'status': 'static_valid', 'tasks': 12}, 'environment': self.facts(),
                  'extra': {'perf': {'present': True, 'rc': 0, 'version': 'perf version 6.6.0-145.3.23.154'},
                            'soffice': {'present': True, 'rc': 0, 'version': 'LibreOffice 25.8.7.3'},
                            'devkit': {'present': True, 'version_rc': 0, 'version': '26.0.RC1',
                                       'libtuner_ldd_rc': 0, 'libtuner_unresolved': 0}}}
        self.assertEqual(install.acceptance_errors(result, replay.environment_errors), [])
        result['extra']['soffice']['version'] = 'LibreOffice 7.4.7.2'
        self.assertTrue(install.acceptance_errors(result, replay.environment_errors))


if __name__ == '__main__':
    unittest.main()
