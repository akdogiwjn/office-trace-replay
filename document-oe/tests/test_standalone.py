import ast
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def entry():
    spec = importlib.util.spec_from_file_location('legacy_public_entry', ROOT / 'run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StandaloneDocumentOE(unittest.TestCase):
    def test_exact_43_workload_files_and_both_recipes(self):
        result = entry().validate()
        self.assertEqual(len(result['workload_files']), 43)

    def test_no_dependency_on_the_other_repositories(self):
        path = ROOT / 'assets/bin/run_document_scene_loop.py'
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module, ('replay', 'office_trace_bench'))
        proc = subprocess.run([sys.executable, '-B', str(ROOT / 'run.py'), '--validate-only'],
                              cwd='/tmp', capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_changed_workload_rejected_in_isolated_copy(self):
        record = json.loads((ROOT / 'lock.json').read_text())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            name = 'bin/export_xlsx_csv.py'
            record['workload_files'] = {name: record['workload_files'][name]}
            (root / 'lock.json').write_text(json.dumps(record))
            target = root / 'assets' / name; target.parent.mkdir(parents=True)
            shutil.copy2(ROOT / 'assets' / name, target)
            target.write_text('tampered')
            with self.assertRaisesRegex(ValueError, 'workload file missing/size mismatch'):
                entry().validate(root)

    def test_host_cannot_reset_workspace_or_start_workload(self):
        module = entry()
        with patch.dict('os.environ', {}, clear=True), patch.object(module.subprocess, 'call') as call:
            with self.assertRaisesRegex(ValueError, 'disposable'):
                module.main(['--scene', 'xlsx'])
            call.assert_not_called()


if __name__ == '__main__':
    unittest.main()
