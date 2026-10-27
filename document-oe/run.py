#!/usr/bin/env python3
"""Independent document-oe entry for the byte-preserved OPM and TLC workloads."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

# Copied into each entry/executor at development time; no shared runtime import.
PINNED_VENV = Path('/opt/document-bench/.venv')
PINNED_PYTHON = PINNED_VENV / 'bin/python'
PINNED_SOFFICE = Path('/opt/libreoffice25.8-symbols/program')


def runtime_environment(runtime='document-oe', inherited=None):
    env = dict(os.environ if inherited is None else inherited)
    for key in ('PYTHONHOME', 'PYTHONPATH', 'PYTHONUSERBASE'):
        env.pop(key, None)
    env['PYTHONNOUSERSITE'] = '1'
    env['PYTHONUNBUFFERED'] = '1'
    if runtime == 'document-oe':
        env['VIRTUAL_ENV'] = str(PINNED_VENV)
        env['PYTHON_PREFIX'] = '/opt/python-3.12.3'
        prefixes = [str(PINNED_VENV / 'bin'), str(PINNED_SOFFICE)]
    else:
        prefixes = [str(Path(sys.executable).parent)]
    rest = [p for p in env.get('PATH', '').split(os.pathsep) if p and p not in prefixes]
    env['PATH'] = os.pathsep.join(prefixes + rest)
    return env


def configure_runtime(runtime='document-oe'):
    if runtime != 'document-oe':
        return
    if not PINNED_PYTHON.is_file() or not os.access(PINNED_PYTHON, os.X_OK):
        raise ValueError('pinned Python is unavailable: ' + str(PINNED_PYTHON))
    env = runtime_environment(runtime)
    # A matching version alone is insufficient: system Python and external
    # site-packages must not become the runner or its children's environment.
    restart = (Path(sys.prefix) != PINNED_VENV
               or Path(sys.executable).parent != PINNED_VENV / 'bin'
               or not sys.flags.no_user_site
               or any(key in os.environ for key in ('PYTHONHOME', 'PYTHONPATH', 'PYTHONUSERBASE')))
    if restart:
        if env.get('OFFICE_RUNTIME_REEXEC') == '1':
            raise ValueError('pinned Python bootstrap did not select the isolated venv')
        env['OFFICE_RUNTIME_REEXEC'] = '1'
        os.execve(str(PINNED_PYTHON), [str(PINNED_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]], env)
        raise RuntimeError('Python re-exec returned unexpectedly')
    os.environ.clear()
    os.environ.update(env)


def validate(root=ROOT, installed=False):
    root = Path(root)
    record = json.loads((root / 'lock.json').read_text())
    assets = Path('/opt/document-bench') if installed else root / 'assets'
    for name, meta in record['workload_files'].items():
        path = assets / name
        if not path.is_file() or path.is_symlink() or path.stat().st_size != meta['size']:
            raise ValueError('workload file missing/size mismatch: ' + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != meta['sha256']:
            raise ValueError('workload changed: ' + name)
        if (path.stat().st_mode & 0o777) != meta['mode']:
            raise ValueError('workload file mode changed: ' + name)
    runner = assets / record['executor']['file']
    if hashlib.sha256(runner.read_bytes()).hexdigest() != record['executor']['sha256']:
        raise ValueError('standalone executor mismatch')
    spec = importlib.util.spec_from_file_location('standalone_document_executor', runner)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    for scene, layout in module.SCENES.items():
        module.load_recipe(assets / 'operations' / (scene + '_key_operations.json'),
                           scene, layout['step_order'])
    return record


def restore_skill_links(skills=Path('/root/.openclaw/skills'), assets=Path('/opt/document-bench/skills')):
    """Restore old context after a new-dataset run, without changing any Skill."""
    skills.mkdir(parents=True, exist_ok=True)
    for kind in ('pdf', 'xlsx'):
        target = skills / kind
        if target.is_symlink() or target.is_file():
            target.unlink()
        elif target.exists():
            raise ValueError('refuse to replace a non-link Skill directory: ' + str(target))
        target.symlink_to(assets / kind)


def run_locked(command, env, lock_path=Path('/tmp/office-agent-replay.lock')):
    with Path(lock_path).open('w') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        restore_skill_links()
        return subprocess.call(command, env=env)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', choices=['pdf', 'xlsx'])
    parser.add_argument('--loops', type=int, default=1)
    parser.add_argument('--pdf-applicant-count', type=int, choices=[1, 10], default=1)
    parser.add_argument('--results-dir', type=Path, default=Path('/results'))
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--installed', action='store_true', help='Validate installed /opt/document-bench files.')
    args = parser.parse_args(argv)
    if args.loops < 1:
        parser.error('--loops must be positive')
    if not args.validate_only and not args.scene:
        parser.error('--scene is required to execute; no implicit long-running suite')
    record = validate(installed=args.installed)
    if args.validate_only:
        print('document-oe:', len(record['workload_files']), 'unchanged workload files; both recipes valid')
        return 0
    if not Path('/.dockerenv').exists() or os.environ.get('DOCUMENT_OE_REPLAY_CONTAINER') != '1':
        raise ValueError('execute only in a disposable document-oe replay container')
    configure_runtime()
    if sys.version_info[:3] != (3, 12, 3):
        raise ValueError('use the pinned Python 3.12.3 venv')
    validate(installed=True)
    command = [sys.executable, '/opt/document-bench/bin/run_document_scene_loop.py',
               '--scene', args.scene, '--loops', str(args.loops),
               '--results-dir', str(args.results_dir.resolve())]
    if args.scene == 'pdf':
        command += ['--pdf-applicant-count', str(args.pdf_applicant_count)]
    env = runtime_environment()
    # Both entries can be used sequentially in the same container. They share
    # only an OS lock because original Skills use fixed absolute aliases.
    return run_locked(command, env)


if __name__ == '__main__':
    raise SystemExit(main())
