"""Common capabilities for the unified document-oe workload and executor.

The integrity boundary is split explicitly:
  - `workload` files are byte-identical to the original document-oe container
    export and are strictly verified (recipes, helper-adjacent tools, skills,
    inputs and verifiers).
  - `executor` files (the unified runner and its timing wrapper) are versioned;
    they are validated against the frozen executor lock so any change must be
    a deliberate, recorded executor release.

`launch` remains the legacy `--scene` compatibility entry: it forwards the
original flags to the unified runner, which for the old `opm`/`tlc` workloads
reproduces the original loop, workspace reset, timeout, error handling, exit
status and timing semantics.
"""
import os
from pathlib import Path
import sys

from .common import ROOT, digest, read, relative

LEGACY = ROOT / 'legacy/document-oe'
NATIVE = Path('/opt/document-bench')

EXECUTOR_VERSION = 'unified-dataset-runner-v2'
EXECUTOR_FILES = ('bin/run_document_scene_loop.py', 'bin/run_document_scene_loop_timed.py')


def validate(root=LEGACY, check_installed=False):
    lock = read(root / 'lock.json')
    executor = lock.get('executor', {})
    if executor.get('version') != EXECUTOR_VERSION:
        raise ValueError('executor version mismatch: ' + str(executor.get('version')))
    if set(executor.get('files', [])) != set(EXECUTOR_FILES):
        raise ValueError('executor file set changed: ' + str(executor.get('files')))
    for name in lock.get('workload', list(lock['files'])):
        _check(root, lock, name, check_installed)
    for name in EXECUTOR_FILES:
        _check(root, lock, name, check_installed)
    return lock


def _check(root, lock, name, check_installed):
    spec = lock['files'][name]
    local = root / relative(name)
    if not local.is_file() or digest(local) != spec['sha256']:
        raise ValueError('legacy bytes changed: ' + name)
    if check_installed:
        installed = NATIVE / relative(name)
        if not installed.is_file() or digest(installed) != spec['sha256']:
            raise ValueError('installed legacy bytes changed: ' + name)
        if installed.stat().st_mode & 0o777 != spec['mode']:
            raise ValueError('installed legacy mode changed: ' + name)


def native_command(arguments, timed=False, python_mode='venv'):
    # The unified runner handles its own environment preparation and timing;
    # --legacy-python and --timed are forwarded so direct and suite invocation
    # use identical rules.
    args = list(arguments) + ['--legacy-python', python_mode]
    if timed:
        args.append('--timed')
    executable = '/usr/bin/python3' if python_mode == 'system' else '/opt/document-bench/.venv/bin/python'
    return [executable, str(NATIVE / 'bin' / 'run_document_scene_loop.py'), *args]


def launch(arguments, timed=False, python_mode='venv'):
    if not Path('/.dockerenv').exists():
        raise ValueError('legacy execution requires a disposable container')
    validate(check_installed=True)
    env = os.environ.copy()
    env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
    env.pop('VIRTUAL_ENV', None)
    if python_mode == 'venv':
        env['PATH'] = '/opt/document-bench/.venv/bin:' + env['PATH']
        env['VIRTUAL_ENV'] = '/opt/document-bench/.venv'
    env.pop('OFFICE_TRACE_PROJECT', None)
    env.pop('PYTHONPATH', None)
    # No new-engine soffice wrapper, macro/profile reset, shell prefix, stdout
    # redirection, extra verifier, or execute_call monkey-patch enters this path.
    # The runner performs its own environment preparation and timing hooks.
    os.chdir('/opt/document-bench')
    command = native_command(arguments, timed, python_mode)
    os.execve(command[0], command, env)
