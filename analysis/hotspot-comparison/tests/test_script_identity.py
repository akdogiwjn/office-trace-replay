import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from script_identity import python_script_operand, role_for_command, role_for_script


class ScriptIdentityTests(unittest.TestCase):
    def test_new_helpers_and_atomic_runtime_variants(self):
        cases = {
            '/opt/python /workspace/hr_metro_build.py': 'xlsx-enhance',
            '/opt/python /workspace/.hr_metro_build.runtime.py': 'xlsx-enhance',
            '/opt/python /workspace/retail_online_build.py': 'xlsx-enhance',
            '/opt/python /workspace/.retail_online_build.runtime.py': 'xlsx-enhance',
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(role_for_command(command, 'xlsx'), expected)

    def test_mentions_in_data_arguments_and_inline_text_are_not_execution_identity(self):
        command = ('/opt/python /opt/office-trace-replay/replay/entry.py '
                   '--dataset hr_metro /workspace/hr_metro_build.py')
        self.assertEqual(python_script_operand(command), 'entry.py')
        self.assertEqual(role_for_command(command, 'xlsx'), 'runner')
        inline = '/opt/python -c "print(\'hr_metro_build.py\')"'
        self.assertIsNone(python_script_operand(inline))
        self.assertIsNone(role_for_command(inline, 'xlsx'))

    def test_module_frame_basename_only_is_supported(self):
        self.assertEqual(role_for_script('retail_online_build.py', 'xlsx'), 'xlsx-enhance')
        self.assertEqual(role_for_script('.hr_metro_build.runtime.py', 'xlsx'), 'xlsx-enhance')
        self.assertEqual(role_for_command('process 42:"python3 recalc.py a.xlsx"', 'xlsx'),
                         'xlsx-recalc')

    def test_production_native_and_profile_role_functions_use_script_identity(self):
        spec = importlib.util.spec_from_file_location('native_role_test', SCRIPTS / 'parse_native.py')
        native = importlib.util.module_from_spec(spec); spec.loader.exec_module(native)
        command = '/opt/document-bench/.venv/bin/python /workspace/.retail_online_build.runtime.py'
        self.assertEqual(native.script_role(command, 'xlsx'), 'xlsx-enhance')
        self.assertEqual(native.script_role(
            '/opt/document-bench/.venv/bin/python /repo/replay/entry.py --dataset retail_online '
            '/workspace/retail_online_build.py', 'xlsx'), 'runner')
        profile_spec = importlib.util.spec_from_file_location(
            'profile_role_test', SCRIPTS / 'build_profiles.py')
        profiles = importlib.util.module_from_spec(profile_spec); profile_spec.loader.exec_module(profiles)
        self.assertEqual(profiles.script_role(command, 'xlsx'), 'xlsx-enhance')


if __name__ == '__main__':
    unittest.main()
