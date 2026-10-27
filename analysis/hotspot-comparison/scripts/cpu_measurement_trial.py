#!/usr/bin/env python3
"""Minimal CPU-measurement launcher: one measured loop per dataset, in-container.

Reuses the proven functional-trial launcher pattern (qualified image, read-only repo
and runner mounts, removable workspace child) and adds only the measurement
machinery:

  * sitecustomize.py + cpu_ledger.py are mounted read-only as single files into
    the venv site-packages (PYTHONPATH is cleared by the runner, so it cannot
    carry the hook); CPU_LEDGER_OUT points at a writable results directory far
    outside the workspace-reset scope;
  * monitor_procs.py runs inside the same container as a background poller of
    the full process tree (per-thread utime+stime), stopped via its alive-file
    protocol after the loop;
  * a clock anchor (CLOCK_MONOTONIC + CLOCK_REALTIME pair) aligns the
    iteration ROI (finished_at - elapsed_seconds) with monitor samples;
  * before any real measurement, a small synthetic probe container proves the
    injection works (main + child ledgers, all three buckets, module hash,
    no-ledger control).  The launcher refuses to measure if the probe fails.

Nothing here modifies the 43 frozen workload files, the runner, the recipes or
the business outputs; no perf/py-spy/strace runs concurrently.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import secrets
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
IMAGE = 'office-trace-replay:openeuler-release'
PYTHON = '/opt/document-bench/.venv/bin/python'
REPO_MOUNT_DST = '/opt/office-trace-replay'
RUNNER_SOURCE = ROOT / 'legacy/document-oe/bin/run_document_scene_loop.py'
TIMED_SOURCE = ROOT / 'legacy/document-oe/bin/run_document_scene_loop_timed.py'
RUNNER_TARGET = '/opt/document-bench/bin/run_document_scene_loop.py'
TIMED_TARGET = '/opt/document-bench/bin/run_document_scene_loop_timed.py'
SITE_PACKAGES = '/opt/document-bench/.venv/lib/python3.12/site-packages'
MEASUREMENT_DIR = ROOT / 'analysis/hotspot-comparison/measurement'
MONITOR_SCRIPT = 'analysis/hotspot-comparison/scripts/monitor_procs.py'
PROBE_SCRIPT = 'analysis/hotspot-comparison/measurement/probe_injection.py'
WORKSPACE_PARENT = '/root/.openclaw/workspace/tool-modeling'
DATASETS = ('hr_metro', 'retail_online', 'tlc', 'industry_productivity')
DOCKER = ['docker', '--host', 'unix:///var/run/docker.sock']


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n',
                         encoding='utf-8')
    temporary.replace(path)


def docker_json(args):
    completed = subprocess.run([*DOCKER, *args], check=True, text=True, capture_output=True)
    return json.loads(completed.stdout)


def inspect_image(image=IMAGE):
    values = docker_json(['image', 'inspect', image])
    if len(values) != 1:
        raise RuntimeError(f'expected one image for {image}')
    return values[0]['Id']


def inspect_container(name):
    values = docker_json(['inspect', name])
    if len(values) != 1:
        raise RuntimeError(f'expected one container for {name}')
    return values[0]


def run_attached(container_id, log_path):
    started = time.monotonic()
    with Path(log_path).open('wb') as log:
        process = subprocess.Popen([*DOCKER, 'start', '-a', container_id],
                                   stdout=log, stderr=subprocess.STDOUT)
        last_notice = started
        while process.poll() is None:
            time.sleep(5)
            elapsed = time.monotonic() - started
            if elapsed >= 30 and time.monotonic() - last_notice >= 30:
                print(f'container {container_id[:12]} still running ({elapsed:.0f}s)', flush=True)
                last_notice = time.monotonic()
        return process.returncode


def measurement_mounts():
    hook_site = MEASUREMENT_DIR / 'sitecustomize.py'
    hook_ledger = MEASUREMENT_DIR / 'cpu_ledger.py'
    return [
        f'type=bind,src={hook_site.resolve()},dst={SITE_PACKAGES}/sitecustomize.py,readonly',
        f'type=bind,src={hook_ledger.resolve()},dst={SITE_PACKAGES}/cpu_ledger.py,readonly',
    ]


def base_mounts():
    return [
        f'type=bind,src={ROOT.resolve()},dst={REPO_MOUNT_DST},readonly',
        f'type=bind,src={RUNNER_SOURCE.resolve()},dst={RUNNER_TARGET},readonly',
        f'type=bind,src={TIMED_SOURCE.resolve()},dst={TIMED_TARGET},readonly',
    ]


def validate_mounts(inspect, results_host, workspace_host=None):
    mounts = {item['Destination']: item for item in inspect.get('Mounts', [])}
    problems = []
    requirements = [(REPO_MOUNT_DST, False), (RUNNER_TARGET, False),
                    (TIMED_TARGET, False),
                    (f'{SITE_PACKAGES}/sitecustomize.py', False),
                    (f'{SITE_PACKAGES}/cpu_ledger.py', False),
                    ('/results', True)]
    if workspace_host is not None:
        requirements.append((WORKSPACE_PARENT, True))
    for destination, expected_rw in requirements:
        item = mounts.get(destination)
        if item is None or bool(item.get('RW')) != expected_rw:
            problems.append(f'{destination} rw={item.get("RW") if item else "missing"}'
                            f' (expected {expected_rw})')
    results = mounts.get('/results')
    if results is not None and Path(results['Source']).resolve() != Path(results_host).resolve():
        problems.append('results mount source mismatch')
    if workspace_host is not None:
        workspace = mounts.get(WORKSPACE_PARENT)
        if workspace is None or bool(workspace.get('RW')) is not True:
            problems.append(f'{WORKSPACE_PARENT} rw='
                            f'{workspace.get("RW") if workspace else "missing"} (expected True)')
        elif Path(workspace['Source']).resolve() != Path(workspace_host).resolve():
            problems.append('workspace parent mount source mismatch')
    return mounts, problems


def probe_container(name, results_host):
    """Small synthetic injection proof; refuses measurement if it fails."""
    argv = [*DOCKER, 'create', '--name', name, '--network', 'none',
            '--env', 'PYTHONDONTWRITEBYTECODE=1',
            '--env', 'CPU_LEDGER_OUT=/results/probe-ledgers',
            *sum((['--mount', m] for m in base_mounts() + measurement_mounts()), []),
            '--mount', f'type=bind,src={Path(results_host).resolve()},dst=/results',
            '--entrypoint', '/bin/bash', IMAGE, '-c',
            f'mkdir -p /results/probe-ledgers && {PYTHON} {REPO_MOUNT_DST}/{PROBE_SCRIPT}'
            f' > /results/probe-verdict.json']
    subprocess.run(argv, check=True, capture_output=True, text=True)
    inspect = inspect_container(name)
    mounts, problems = validate_mounts(inspect, results_host)
    exit_code = run_attached(inspect['Id'], Path(results_host) / 'probe-container.log')
    probe_json = Path(results_host) / 'probe-verdict.json'
    verdict = {}
    if probe_json.is_file():
        try:
            verdict = read_json(probe_json)
        except ValueError:
            verdict = {'status': 'unparseable'}
    return {'exit_code': exit_code, 'mount_problems': problems, 'verdict': verdict,
            'mounts': {d: {'rw': i['RW']} for d, i in mounts.items()}}


def measurement_shell(dataset, runner_python_mode='venv'):
    return f'''
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
export CPU_LEDGER_OUT=/results/ledgers
export HOTSPOT_MONITOR_STOP=/results/monitor-stop
mkdir -p /results/ledgers /results/monitor /results/monitor-stop
touch /results/monitor-stop/alive
{PYTHON} {REPO_MOUNT_DST}/{MONITOR_SCRIPT} /results/monitor 50 &
MON=$!
{PYTHON} - <<'PY'
import json, time
json.dump({{'mono_ns': time.clock_gettime_ns(time.CLOCK_MONOTONIC),
            'real_ns': time.clock_gettime_ns(time.CLOCK_REALTIME)}},
          open('/results/clock-anchor.json', 'w'))
PY
trap 'rm -f /results/monitor-stop/alive' EXIT
soffice --version > /results/libreoffice-version.txt 2>&1 || true
{PYTHON} {REPO_MOUNT_DST}/replay/entry.py --scene xlsx --dataset {dataset} \
    --loops 1 --results-dir /results/workload --legacy-python {runner_python_mode}
rm -f /results/monitor-stop/alive
wait $MON
{PYTHON} {REPO_MOUNT_DST}/analysis/hotspot-comparison/scripts/archive_results.py /results
'''


def run_measurement(dataset, campaign, token, results_host, workspace_host):
    name = f'otr-cpumeasure-{dataset}-{token}'
    image_id = inspect_image()
    shell = measurement_shell(dataset)
    argv = [*DOCKER, 'create', '--name', name, '--network', 'none',
            '--env', 'PYTHONDONTWRITEBYTECODE=1',
            '--env', 'CPU_LEDGER_OUT=/results/ledgers',
            *sum((['--mount', m] for m in base_mounts() + measurement_mounts()), []),
            '--mount', f'type=bind,src={Path(results_host).resolve()},dst=/results',
            '--mount', f'type=bind,src={Path(workspace_host).resolve()},dst={WORKSPACE_PARENT}',
            '--entrypoint', '/bin/bash', IMAGE, '-c', shell]
    created = subprocess.run(argv, check=True, capture_output=True, text=True)
    container_id = created.stdout.strip()
    inspect = inspect_container(name)
    mounts, problems = validate_mounts(inspect, results_host, workspace_host)
    if inspect['Image'] != image_id:
        raise RuntimeError('measurement container image differs from the inspected tag')
    if problems:
        raise ValueError('measurement mount evidence rejected: ' + '; '.join(problems))
    exit_code = run_attached(container_id, Path(results_host) / 'container.log')
    # the launcher itself writes container.log until the container exits; add
    # its final hash to the in-container archive index now that it is final
    log_path = Path(results_host) / 'container.log'
    index_path = Path(results_host) / 'archive-index.json'
    index = read_json(index_path)
    index['files'].append({'path': 'container.log',
                           'size_bytes': log_path.stat().st_size,
                           'sha256': sha256(log_path)})
    index['files'].sort(key=lambda row: row['path'])
    write_json(index_path, index)
    return {'image_id': image_id, 'container_id': container_id,
            'exit_code': exit_code,
            'mounts': {d: {'source': i['Source'], 'rw': i['RW']} for d, i in mounts.items()},
            'shell': shell}


def host_binding_check(dataset):
    """Record the frozen identities the measurement is bound to."""
    bindings = {'validate_only': None}
    result = subprocess.run([sys.executable, str(ROOT / 'replay/entry.py'),
                              '--dataset', dataset, '--validate-only'],
                             cwd=ROOT, text=True, capture_output=True)
    bindings['validate_only_exit'] = result.returncode
    bindings['validate_only_output'] = (result.stdout or result.stderr).strip().splitlines()[-3:]
    if result.returncode:
        raise RuntimeError(f'validate-only failed for {dataset}: {result.stderr or result.stdout}')
    index = read_json(ROOT / 'compatibility/suite.json')
    entry = next((e for e in index['entries']
                  if e['dataset_id'] == dataset and e.get('record_count') is None), None)
    if entry is not None:
        recipe_path = ROOT / entry['recipe_path']
        if sha256(recipe_path) != entry['recipe_sha256']:
            raise ValueError(f'{dataset}: recipe hash differs from suite binding')
        recipe = read_json(recipe_path)
        bindings['recipe'] = {'path': entry['recipe_path'], 'sha256': entry['recipe_sha256'],
                              'helper_hashes': recipe.get('helper_hashes'),
                              'input_hashes': recipe.get('input_hashes'),
                              'operation_timeout': recipe.get('operation_timeout'),
                              'recalc_timeout': recipe.get('recalc_timeout')}
        if 'manual_source' in recipe:
            bindings['manual_source'] = recipe['manual_source']
    else:
        # tlc: the frozen legacy workload; its recipe lives under legacy/document-oe
        bindings['legacy_workload'] = True
    bindings['measurement_code'] = {
        'cpu_ledger_sha256': sha256(MEASUREMENT_DIR / 'cpu_ledger.py'),
        'sitecustomize_sha256': sha256(MEASUREMENT_DIR / 'sitecustomize.py'),
        'monitor_sha256': sha256(ROOT / MONITOR_SCRIPT),
        'probe_sha256': sha256(MEASUREMENT_DIR / 'probe_injection.py'),
    }
    bindings['runner_sha256'] = sha256(RUNNER_SOURCE)
    bindings['image_id'] = inspect_image()
    return bindings


def archive_results(results_host):
    """Load the in-container archive index and spot-verify host-readable files."""
    index_path = Path(results_host) / 'archive-index.json'
    if not index_path.is_file():
        raise FileNotFoundError(
            f'in-container archive index missing: {index_path}')
    index = read_json(index_path)
    verified = unreadable = 0
    for row in index['files']:
        path = Path(results_host) / row['path']
        try:
            if sha256(path) == row['sha256']:
                verified += 1
            else:
                raise ValueError(f'hash mismatch for {row["path"]}')
        except PermissionError:
            unreadable += 1  # hashed inside the container; host cannot re-read
    index['host_verified_files'] = verified
    index['host_unreadable_files'] = unreadable
    index['all_hashes_verified'] = index.get('all_hashes_verified', False) and verified > 0
    write_json(index_path, index)
    return index


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True, choices=DATASETS)
    parser.add_argument('--campaign-dir', type=Path, required=True)
    parser.add_argument('--probe-only', action='store_true',
                        help='run only the synthetic injection probe container')
    args = parser.parse_args(argv)
    token = secrets.token_hex(4)
    campaign = args.campaign_dir.resolve()
    try:
        campaign.relative_to(ROOT)
    except ValueError:
        parser.error('--campaign-dir must be inside the repository')
    campaign.mkdir(parents=True, exist_ok=True)
    results_host = campaign / args.dataset
    if results_host.exists() and any(results_host.iterdir()):
        raise FileExistsError(f'refusing to reuse dataset result directory: {results_host}')
    results_host.mkdir()
    workspace_host = results_host / 'workspace-parent'
    workspace_host.mkdir()

    bindings = host_binding_check(args.dataset)
    write_json(results_host / 'host-bindings.json', bindings)

    print(f'PROBE {args.dataset}', flush=True)
    probe = probe_container(f'otr-cpuprobe-{args.dataset}-{token}', results_host)
    write_json(results_host / 'probe-record.json', probe)
    probe_ok = (probe['exit_code'] == 0 and probe['verdict'].get('status') == 'success'
                and not probe['mount_problems'])
    if not probe_ok:
        print(f'PROBE FAILED for {args.dataset}; refusing to measure', flush=True)
        return 1
    if args.probe_only:
        print('probe-only mode: injection verified, no measurement started', flush=True)
        return 0

    print(f'MEASURE {args.dataset} loops=1', flush=True)
    record = run_measurement(args.dataset, campaign, token, results_host, workspace_host)
    write_json(results_host / 'measurement-record.json', record)
    index = archive_results(results_host)
    write_json(results_host / 'measurement-record.json',
               {**read_json(results_host / 'measurement-record.json'),
                'archive_files': len(index['files']),
                'archive_hashes_verified': index['all_hashes_verified']})
    status = 'success' if record['exit_code'] == 0 and index['all_hashes_verified'] else 'failed'
    write_json(results_host / 'measurement-record.json',
               {**read_json(results_host / 'measurement-record.json'), 'status': status})
    print(f'MEASURE {args.dataset}: {status} (container exit {record["exit_code"]}, '
          f'{len(index["files"])} archived files)', flush=True)
    return 0 if status == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
