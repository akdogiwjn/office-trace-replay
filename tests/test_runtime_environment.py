import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = (ROOT / 'agent/tools/runtime_bootstrap.py.template').read_text().rstrip()


def load(path):
    spec = importlib.util.spec_from_file_location('environment_test_' + str(hash(path)), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RuntimeEnvironment(unittest.TestCase):
    def entries(self):
        return [ROOT / 'agent/replay.py', ROOT / 'document-oe/run.py',
                *sorted((ROOT / 'agent/datasets').glob('*/run.py'))]

    def test_bootstrap_is_private_and_generator_keeps_copies_in_sync(self):
        template = (ROOT / 'agent/tools/dataset_runner.py.template').read_text()
        for path in self.entries():
            with self.subTest(path=path):
                self.assertIn(BOOTSTRAP, path.read_text())
                if path.parent.parent.name == 'datasets':
                    self.assertEqual(path.read_text(), template.replace('# DATASET_RUNTIME_BOOTSTRAP', BOOTSTRAP))

    def test_every_entry_pins_child_python_office_and_cleans_external_packages(self):
        inherited = dict(PATH='/usr/bin:/bin', PYTHONHOME='/wrong', PYTHONPATH='/outside',
                         PYTHONUSERBASE='/user-packages', VIRTUAL_ENV='/wrong', KEEP='yes')
        for path in self.entries():
            with self.subTest(path=path):
                env = load(path).runtime_environment(inherited=inherited)
                self.assertEqual(env['PATH'].split(':')[:2],
                                 ['/opt/document-bench/.venv/bin', '/opt/libreoffice25.8-symbols/program'])
                self.assertEqual(env['VIRTUAL_ENV'], '/opt/document-bench/.venv')
                self.assertEqual(env['PYTHONNOUSERSITE'], '1')
                self.assertEqual(env['KEEP'], 'yes')
                for key in ('PYTHONHOME', 'PYTHONPATH', 'PYTHONUSERBASE'):
                    self.assertNotIn(key, env)
                self.assertEqual(inherited['PYTHONPATH'], '/outside')
                self.assertEqual(load(path).runtime_environment(inherited=env), env)

    def test_missing_pinned_python_refuses_before_environment_or_reset(self):
        module = load(ROOT / 'agent/datasets/egrid/run.py')
        with tempfile.TemporaryDirectory() as temp, patch.object(module, 'PINNED_PYTHON', Path(temp) / 'missing'):
            with patch.object(module, 'prepare') as prepare:
                with self.assertRaisesRegex(ValueError, 'pinned Python is unavailable'):
                    module.configure_runtime()
                prepare.assert_not_called()

    def test_real_reexec_and_grandchild_use_same_isolated_venv(self):
        # Only a tiny temporary venv and a JSON probe, no benchmark input/workspace.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); venv = root / 'venv'; script = root / 'probe.py'
            subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(venv)], check=True,
                           capture_output=True, timeout=30)
            script.write_text('import os, sys, json, subprocess\nfrom pathlib import Path\n' + BOOTSTRAP
                              + '\nPINNED_VENV = Path(' + repr(str(venv)) + ')\n'
                              + 'PINNED_PYTHON = PINNED_VENV / "bin/python"\n'
                              + 'configure_runtime()\n'
                              + 'child = subprocess.check_output(["python3", "-c", '
                              + repr('import sys,json; print(json.dumps(dict(prefix=sys.prefix, no_user_site=sys.flags.no_user_site)))')
                              + '], text=True)\n'
                              + 'print(json.dumps(dict(prefix=sys.prefix, no_user_site=sys.flags.no_user_site, '
                              + 'argv=sys.argv[1:], child=json.loads(child), '
                              + 'external_paths=[k for k in ("PYTHONPATH","PYTHONHOME","PYTHONUSERBASE") if k in os.environ])))\n')
            env = os.environ.copy()
            env.pop('OFFICE_RUNTIME_REEXEC', None)
            env.pop('PYTHONHOME', None)
            env.update(PYTHONPATH=str(root / 'outside'), PYTHONUSERBASE=str(root / 'user'),
                       VIRTUAL_ENV='/wrong', PYTHONNOUSERSITE='0')
            result = subprocess.run([sys.executable, str(script), '--probe', 'unchanged'], env=env,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data['prefix'], str(venv))
            self.assertEqual(data['child'], dict(prefix=str(venv), no_user_site=1))
            self.assertEqual(data['argv'], ['--probe', 'unchanged'])
            self.assertEqual(data['external_paths'], [])
            self.assertEqual(data['no_user_site'], 1)

    def test_reexec_guard_refuses_an_incorrect_second_interpreter(self):
        module = load(ROOT / 'agent/replay.py')
        with patch.object(module, 'PINNED_PYTHON', Path(sys.executable)), \
                patch.object(module, 'PINNED_VENV', Path('/wrong/venv')), \
                patch.dict(os.environ, {'OFFICE_RUNTIME_REEXEC': '1'}), patch.object(module.os, 'execve') as execute:
            with self.assertRaisesRegex(ValueError, 'bootstrap did not select'):
                module.configure_runtime()
            execute.assert_not_called()

    def test_private_adapter_still_wins_over_shared_office(self):
        module = load(ROOT / 'agent/datasets/egrid/run.py')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); case = root / 'case'
            (case / 'seed/input').mkdir(parents=True); (case / 'scripts').mkdir()
            (case / 'skills/xlsx').mkdir(parents=True)
            with patch.object(module, 'HERE', case):
                _, env = module.prepare(dict(kind='xlsx', workspace=str(root / 'workspace')),
                                        skill_directory=root / 'links')
            self.assertEqual(env['PATH'].split(':')[:3],
                             [str(case / 'runtime/bin'), '/opt/document-bench/.venv/bin',
                              '/opt/libreoffice25.8-symbols/program'])


if __name__ == '__main__':
    unittest.main()
