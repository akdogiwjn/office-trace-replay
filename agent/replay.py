#!/usr/bin/env python3
"""The only shared runtime entry; all workload code belongs to one dataset."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent
DATASETS = ('egrid', 'hr_metro', 'industry_productivity', 'irs_w4', 'sba1919')

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


def launch_container(args, selected):
    """Optional host mode of the SAME entry; freeze inspect before workload starts."""
    results = args.results_dir.resolve()
    results.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    evidence = results / '.launch' / stamp
    evidence.mkdir(parents=True, exist_ok=False)
    if ',' in str(results):
        raise ValueError('Docker bind paths containing commas are unsupported')
    docker = ['docker', '--host', args.docker_host]
    record = dict(status='in_progress', launch_id=stamp, container_id=None, requested_image=args.docker_image,
                  selected_datasets=selected, container_started=False)
    def save(name, value):
        path = evidence / name
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        temp.replace(path)
    def inspect(name):
        proc = subprocess.run(docker + ['container', 'inspect', record['container_id']],
                              capture_output=True, text=True, check=True, timeout=30)
        data = json.loads(proc.stdout)
        if len(data) != 1 or data[0]['Id'] != record['container_id']:
            raise ValueError('Docker inspect container identity mismatch')
        save(name, data)
        return data[0]
    plan = dict(selected_datasets=selected, loops=args.loops, runtime=args.runtime,
                dataset_locks={ds: hashlib.sha256((ROOT / 'datasets' / ds / 'lock.json').read_bytes()).hexdigest()
                               for ds in selected}, suite_sha256=hashlib.sha256((ROOT / 'suite.json').read_bytes()).hexdigest())
    save('launch-plan.json', plan)
    command = docker + ['container', 'create', '--pull=never', '--name', 'office-agent-replay-' + stamp,
        '--network', 'none', '--env', 'OFFICE_AGENT_REPLAY_CONTAINER=1',
        '--mount', f'type=bind,source={results},target=/results',
        '--mount', f'type=bind,source={evidence},target=/run/office-replay,readonly',
        '--mount', f'type=bind,source={results / ".launch"},target=/results/.launch,readonly',
        '--entrypoint', '/opt/document-bench/.venv/bin/python', args.docker_image,
        '/opt/office-trace-replay/agent/replay.py', '--loops', str(args.loops),
        '--results-dir', '/results', '--runtime', args.runtime,
        '--container-inspect', '/run/office-replay/container-inspect.before.json']
    for ds in selected:
        command += ['--dataset', ds]
    record['create_argv'] = command
    code = 1
    try:
        save('launch-record.json', record)
        created = subprocess.run(command, capture_output=True, text=True, check=True, timeout=60)
        container_id = created.stdout.strip()
        if len(container_id) != 64 or any(c not in '0123456789abcdef' for c in container_id):
            raise ValueError('invalid Docker container ID')
        record['container_id'] = container_id
        before = inspect('container-inspect.before.json')
        record['actual_image_id'] = before['Image']
        record['container_start_requested'] = True
        save('launch-record.json', record)
        started = subprocess.run(docker + ['container', 'start', '--attach', container_id])
        record['docker_start_exit_code'] = started.returncode
        after = inspect('container-inspect.after.json')
        record['container_state'] = after['State']
        record['container_started'] = after['State'].get('StartedAt', '0001-01-01').startswith('0001-') is False
        code = after['State']['ExitCode']
        if after['State']['Running'] or started.returncode:
            code = code or started.returncode or 1
        record['status'] = 'success' if code == 0 else 'failed'
    except Exception as exc:
        record.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        if isinstance(exc, subprocess.CalledProcessError):
            record['stderr'] = exc.stderr
    finally:
        record['exit_code'] = code
        record['evidence_files'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in evidence.glob('*.json') if p.name != 'launch-record.json'}
        try:
            save('launch-record.json', record)
        except Exception as exc:
            record.update(status='failed', record_error=str(exc))
            print(json.dumps(record), file=sys.stderr, flush=True)
            code = code or 1
        print('Container launch evidence:', evidence, flush=True)
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', action='append', choices=DATASETS)
    parser.add_argument('--loops', type=int, default=1)
    parser.add_argument('--results-dir', type=Path, default=Path('/results'))
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--docker-image', help='Host launch mode: create/inspect/start an installed image; retain container.')
    parser.add_argument('--docker-host', default='unix:///var/run/docker.sock')
    parser.add_argument('--container-inspect', type=Path)
    parser.add_argument('--runtime', choices=['document-oe', 'original'], default='document-oe',
                        help='Default: the common openEuler image; original is for trace-environment diagnostics.')
    parser.add_argument('--audit-only', type=Path, metavar='ARCHIVED_WORKSPACE',
                        help='Audit an existing workspace; requires exactly one dataset.')
    args = parser.parse_args(argv)
    if args.loops < 1:
        parser.error('--loops must be positive')
    if args.docker_image and (args.audit_only or args.validate_only or args.container_inspect):
        parser.error('--docker-image cannot be combined with --audit-only, --validate-only or --container-inspect')
    selected = list(dict.fromkeys(args.dataset or DATASETS))
    if args.audit_only and (not args.dataset or len(selected) != 1 or args.validate_only):
        parser.error('--audit-only needs exactly one explicit dataset and no --validate-only')
    suite = json.loads((ROOT / 'suite.json').read_text())
    entries = {item['dataset_id']: item for item in suite['datasets']}
    if set(entries) != set(DATASETS) or len(suite['datasets']) != len(DATASETS):
        raise ValueError('frozen suite inventory mismatch')
    for dataset in selected:
        lock = ROOT / 'datasets' / dataset / 'lock.json'
        if hashlib.sha256(lock.read_bytes()).hexdigest() != entries[dataset]['lock_sha256']:
            raise ValueError('dataset lock differs from frozen suite: ' + dataset)
    # Validate every selection before any dataset starts execution.
    for dataset in selected:
        code = subprocess.call([sys.executable, str(ROOT / 'datasets' / dataset / 'run.py'),
                                '--validate-only'])
        if code:
            return code
    if args.validate_only:
        return 0
    if args.docker_image:
        return launch_container(args, selected)
    if not Path('/.dockerenv').exists() or os.environ.get('OFFICE_AGENT_REPLAY_CONTAINER') != '1':
        raise ValueError('execution requires a disposable replay container')
    configure_runtime(args.runtime)
    for dataset in selected:
        command = [sys.executable, str(ROOT / 'datasets' / dataset / 'run.py'),
                   '--loops', str(args.loops), '--results-dir', str(args.results_dir.resolve()),
                   '--runtime', args.runtime]
        if args.audit_only:
            command += ['--audit-only', str(args.audit_only.resolve())]
        if args.container_inspect:
            command += ['--container-inspect', str(args.container_inspect.resolve())]
        code = subprocess.call(command)
        if code:
            return code
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
