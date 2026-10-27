"""Tiny container-only path probe; never calls a recipe/helper/reset/recalc."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
exec(compile((ROOT / 'agent/tools/runtime_bootstrap.py.template').read_text(),
             'frozen-runtime-bootstrap', 'exec'))
configure_runtime()

results = {}
for case in sorted((ROOT / 'agent/datasets').iterdir()):
    spec = importlib.util.spec_from_file_location('runtime_probe_' + case.name, case / 'run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    results[case.name] = module.environment(json.loads((case / 'recipe.json').read_text()))
    assert Path(results[case.name]['python3_path']) == PINNED_VENV / 'bin/python3'
    assert results[case.name]['soffice_path'] == str(case / 'runtime/bin/soffice')
child = subprocess.check_output(['python3', '-c',
    'import json,sys,openpyxl; print(json.dumps(dict(executable=sys.executable,prefix=sys.prefix,openpyxl=openpyxl.__file__)))'], text=True)
assert json.loads(child)['prefix'] == str(PINNED_VENV)
assert Path(sys.executable).parent == PINNED_VENV / 'bin'
assert sys.flags.no_user_site
assert not any(key in os.environ for key in ('PYTHONHOME', 'PYTHONPATH', 'PYTHONUSERBASE'))
print(json.dumps(dict(status='success', datasets=results, child=json.loads(child),
                     scope='versions and paths only; no workload'), indent=2))
