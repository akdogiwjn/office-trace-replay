"""Delegate to untouched document-oe files; never adapt its tool calls."""
import os
from pathlib import Path
import sys

from .common import ROOT, digest, read, relative

LEGACY = ROOT / 'legacy/document-oe'
NATIVE = Path('/opt/document-bench')


def validate(root=LEGACY, check_installed=False):
    lock = read(root / 'lock.json')
    for name, spec in lock['files'].items():
        local = root / relative(name)
        if not local.is_file() or digest(local) != spec['sha256']:
            raise ValueError('legacy bytes changed: ' + name)
        if check_installed:
            installed = NATIVE / relative(name)
            if not installed.is_file() or digest(installed) != spec['sha256']:
                raise ValueError('installed legacy bytes changed: ' + name)
            if installed.stat().st_mode & 0o777 != spec['mode']:
                raise ValueError('installed legacy mode changed: ' + name)
    return lock


def native_command(arguments, timed=False, python_mode='venv'):
    # Forward all original flags unchanged: scene, loops, 1/10 applicants,
    # operation timeout, recalc timeout and original results format.
    script = 'run_document_scene_loop_timed.py' if timed else 'run_document_scene_loop.py'
    executable = '/usr/bin/python3' if python_mode == 'system' else '/opt/document-bench/.venv/bin/python'
    return [executable, str(NATIVE / 'bin' / script), *arguments]


def launch(arguments, timed=False, python_mode='venv'):
    if not Path('/.dockerenv').exists():
        raise ValueError('legacy execution requires a disposable container')
    validate(check_installed=True)
    skills = Path('/root/.openclaw/skills')
    skills.mkdir(parents=True, exist_ok=True)
    for name in ('pdf', 'xlsx'):
        path = skills / name
        target = NATIVE / 'skills' / name
        if path.is_symlink() and path.resolve() == target.resolve():
            continue
        # Fresh legacy containers have the original symlinks. Refuse a foreign
        # tree rather than replacing it or silently borrowing newer Skills.
        if path.exists() or path.is_symlink():
            raise ValueError('legacy Skill context changed; use a fresh container')
        path.symlink_to(target)
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
    os.chdir('/opt/document-bench')
    command = native_command(arguments, timed, python_mode)
    os.execve(command[0], command, env)
