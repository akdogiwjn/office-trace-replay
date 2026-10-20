#!/usr/bin/env python3
"""Run small, isolated functional loops for the two manual XLSX adaptations."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
IMAGE = 'office-trace-replay:openeuler-v11'
DATASETS = ('hr_metro', 'retail_online')
PYTHON = '/opt/document-bench/.venv/bin/python'
REPO_CONTAINER = Path('/opt/office-trace-replay')
WORKSPACE_PARENT_CONTAINER = Path('/root/.openclaw/workspace/tool-modeling')
RUNNER_SOURCE = ROOT / 'legacy/document-oe/bin/run_document_scene_loop.py'
TIMED_SOURCE = ROOT / 'legacy/document-oe/bin/run_document_scene_loop_timed.py'
RUNNER_TARGET = '/opt/document-bench/bin/run_document_scene_loop.py'
TIMED_TARGET = '/opt/document-bench/bin/run_document_scene_loop_timed.py'
PREFLIGHT_SCRIPT = 'analysis/hotspot-comparison/scripts/preflight_replay.py'
DOCKER = ['docker', '--host', 'unix:///var/run/docker.sock']


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
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


def load_runner(path=RUNNER_SOURCE):
    """Load the frozen runner with its dataclass module registered first."""
    spec = importlib.util.spec_from_file_location('functional_trial_runner', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def source_bindings(dataset):
    recipe_path = ROOT / f'compatibility/recipes/{dataset}.json'
    recipe = read_json(recipe_path)
    suite = read_json(ROOT / 'compatibility/suite.json')
    suite_entry = next(item for item in suite['entries']
                       if item['dataset_id'] == dataset and item['record_count'] is None)
    if sha256(recipe_path) != suite_entry['recipe_sha256']:
        raise ValueError(f'{dataset}: recipe hash differs from suite binding')
    helper_path = ROOT / recipe['manual_source']['helper_path']
    manifest_path = ROOT / recipe['manual_source']['manifest_path']
    record_path = ROOT / recipe['manual_source']['record_path']
    if sha256(helper_path) != recipe['manual_source']['helper_sha256']:
        raise ValueError(f'{dataset}: helper binding mismatch')
    if sha256(manifest_path) != recipe['manual_source']['manifest_sha256']:
        raise ValueError(f'{dataset}: manifest binding mismatch')
    if sha256(record_path) != recipe['manual_source']['record_sha256']:
        raise ValueError(f'{dataset}: provenance binding mismatch')
    if recipe['recalc_timeout'] != 600 or recipe['operation_timeout'] != 900:
        raise ValueError(f'{dataset}: timeout metadata is not 600/900')
    input_root = ROOT / recipe['seed_path']
    inputs = {name: sha256(input_root / name) for name in recipe['input_hashes']}
    if inputs != recipe['input_hashes']:
        raise ValueError(f'{dataset}: seed input hash mismatch')
    return recipe, {
        'recipe_path': str(recipe_path.relative_to(ROOT)),
        'recipe_sha256': sha256(recipe_path),
        'manifest_path': str(manifest_path.relative_to(ROOT)),
        'manifest_sha256': sha256(manifest_path),
        'provenance_path': str(record_path.relative_to(ROOT)),
        'provenance_sha256': sha256(record_path),
        'helper_path': str(helper_path.relative_to(ROOT)),
        'helper_sha256': sha256(helper_path),
        'input_hashes': inputs,
        'entry_sha256': sha256(ROOT / 'replay/entry.py'),
        'project_lock_sha256': sha256(ROOT / 'assets/project-lock.json'),
        'contract_sha256': sha256(ROOT / 'compatibility/contract.json'),
        'suite_sha256': sha256(ROOT / 'compatibility/suite.json'),
        'runner_sha256': sha256(RUNNER_SOURCE),
        'timed_wrapper_sha256': sha256(TIMED_SOURCE),
    }


def workspace_layout(recipe, result_dir):
    workspace = Path(recipe['workspace'])
    if workspace.parent != WORKSPACE_PARENT_CONTAINER:
        raise ValueError(f'unexpected dataset workspace parent: {workspace.parent}')
    host_parent = Path(result_dir) / 'workspace-parent'
    return workspace, host_parent


def shell_command(dataset, phase):
    # All executable paths are fixed container paths; dataset and phase have
    # already passed closed-set validation. The bash -c payload is one argv item.
    command = [
        'set -euo pipefail',
        'export PYTHONDONTWRITEBYTECODE=1',
        f'{PYTHON} /opt/office-trace-replay/{PREFLIGHT_SCRIPT} '
        f'--scene xlsx --dataset {dataset} --output /results/preflight.json '
        f'--workspace-parent {WORKSPACE_PARENT_CONTAINER}',
        f'{PYTHON} /opt/office-trace-replay/replay/entry.py '
        f'--dataset {dataset} --validate-only',
    ]
    if phase == 'trial':
        command.append(
            f'exec {PYTHON} /opt/office-trace-replay/replay/entry.py '
            f'--scene xlsx --dataset {dataset} --loops 1 --results-dir /results')
    return ';\n'.join(command)


def docker_create_argv(dataset, phase, image, result_dir, host_parent, name):
    repo_mount = f'type=bind,src={ROOT.resolve()},dst={REPO_CONTAINER},readonly'
    runner_mount = (f'type=bind,src={RUNNER_SOURCE.resolve()},'
                    f'dst={RUNNER_TARGET},readonly')
    timed_mount = (f'type=bind,src={TIMED_SOURCE.resolve()},'
                   f'dst={TIMED_TARGET},readonly')
    result_mount = f'type=bind,src={Path(result_dir).resolve()},dst=/results'
    workspace_mount = (f'type=bind,src={Path(host_parent).resolve()},'
                       f'dst={WORKSPACE_PARENT_CONTAINER}')
    return [
        *DOCKER, 'create', '--name', name, '--network', 'none',
        '--env', 'PYTHONDONTWRITEBYTECODE=1',
        '--mount', repo_mount, '--mount', runner_mount, '--mount', timed_mount,
        '--mount', result_mount, '--mount', workspace_mount,
        '--entrypoint', '/bin/bash', image, '-c', shell_command(dataset, phase),
    ]


def validate_container_mounts(inspect, host_parent):
    mounts = {item['Destination']: item for item in inspect.get('Mounts', [])}
    required = {
        str(REPO_CONTAINER): False,
        RUNNER_TARGET: False,
        TIMED_TARGET: False,
        '/results': True,
        str(WORKSPACE_PARENT_CONTAINER): True,
    }
    for destination, writable in required.items():
        item = mounts.get(destination)
        if item is None or item.get('RW') is not writable:
            raise ValueError(f'missing or wrong-permission mount: {destination}')
    workspace = next(item for item in mounts.values()
                     if item['Destination'] == str(WORKSPACE_PARENT_CONTAINER))
    if Path(workspace['Source']).resolve() != Path(host_parent).resolve():
        raise ValueError('workspace parent mount source mismatch')
    if any(Path(item['Destination']) == Path('/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-HR-METRO')
           or Path(item['Destination']) == Path('/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-RETAIL-ONLINE')
           for item in mounts.values()):
        raise ValueError('dataset workspace must be a removable child, not a bind mount target')
    config = inspect.get('Config', {})
    if config.get('Entrypoint') != ['/bin/bash'] or not config.get('Cmd', [''])[0] == '-c':
        raise ValueError('container shell entrypoint was not set before image arguments')


def docker_json(args):
    completed = subprocess.run([*DOCKER, *args], check=True, text=True, capture_output=True)
    return json.loads(completed.stdout)


def inspect_container(name):
    values = docker_json(['inspect', name])
    if len(values) != 1:
        raise RuntimeError(f'expected one container for {name}')
    return values[0]


def inspect_image(image=IMAGE):
    values = docker_json(['image', 'inspect', image])
    if len(values) != 1:
        raise RuntimeError(f'expected one image for {image}')
    return values[0]['Id']


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
                print(f'container {container_id[:12]} still running ({elapsed:.0f}s)',
                      flush=True)
                last_notice = time.monotonic()
        return process.returncode


def host_validate(dataset):
    recipe, bindings = source_bindings(dataset)
    runner = load_runner()
    layout = runner.dataset_layout('xlsx', dataset, None)
    workspace, _ = workspace_layout(recipe, ROOT / 'tmp-functional-layout')
    if Path(layout['workspace']) != workspace:
        raise ValueError(f'{dataset}: runner registry and recipe workspace differ')
    if (int(layout['operation_timeout']) != 900
            or int(layout['recalc_timeout']) != 600):
        raise ValueError(f'{dataset}: runner registry timeout mismatch')
    result = subprocess.run([sys.executable, str(ROOT / 'replay/entry.py'),
                             '--dataset', dataset, '--validate-only'],
                            cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f'host frozen binding check failed: {result.stderr or result.stdout}')
    return recipe, bindings, {
        'status': 'success', 'runner_workspace': str(layout['workspace']),
        'operation_timeout_seconds': layout['operation_timeout'],
        'recalc_timeout_seconds': layout['recalc_timeout'],
        'validate_only_stdout': result.stdout.strip(),
    }


def _summary_and_archive(dataset, result_dir, recipe, run_record):
    result_dir = Path(result_dir)
    workspace = Path(recipe['workspace'])
    output_dir = result_dir / 'workspace-parent' / workspace.name / 'output'
    summary_candidates = list((result_dir / 'xlsx').glob('*/summary.json'))
    iteration_candidates = list((result_dir / 'xlsx').glob('*/iterations.jsonl'))
    if len(summary_candidates) != 1 or len(iteration_candidates) != 1:
        return False, 'runner summary/iteration inventory is incomplete', []
    summary_path, iterations_path = summary_candidates[0], iteration_candidates[0]
    summary = read_json(summary_path)
    lines = [line for line in iterations_path.read_text().splitlines() if line.strip()]
    if len(lines) != 1:
        return False, f'expected one iteration event, found {len(lines)}', []
    iteration = json.loads(lines[0])
    business_path = output_dir / 'business_verification.json'
    if business_path.is_file():
        business = read_json(business_path)
    else:
        business = {}
    checks = {
        'requested_completed_success_failures': (
            summary.get('requested_iterations') == 1
            and summary.get('completed_iterations') == 1
            and summary.get('successes') == 1 and summary.get('failures') == 0),
        'timeouts': (summary.get('operation_timeout_seconds') == 900
                     and summary.get('recalc_timeout_seconds') == 600),
        'business_verification': (business.get('status') == 'success'
                                  and business.get('failures') == []),
        'iteration_success': iteration.get('iteration') == 1 and iteration.get('status') == 'success',
    }
    outputs = list(recipe_manifest(recipe, dataset))
    outputs.extend(['metrics.csv', 'scenario.csv', 'xlsx_enhancement_summary.json',
                    'xlsx_business_diagnostics.json', 'business_verification.json'])
    output_files = [output_dir / name for name in dict.fromkeys(outputs)]
    checks['required_outputs_nonempty'] = all(p.is_file() and p.stat().st_size > 0
                                               for p in output_files)
    log_path = result_dir / 'container.log'
    checks['runner_log_nonempty'] = log_path.is_file() and log_path.stat().st_size > 0
    file_rows = []
    paths = [summary_path, iterations_path, log_path, *output_files]
    preflight_path = result_dir / 'preflight.json'
    if preflight_path.is_file():
        paths.append(preflight_path)
    for path in dict.fromkeys(paths):
        if path.is_file():
            file_rows.append({'path': str(path.relative_to(result_dir)),
                              'size_bytes': path.stat().st_size,
                              'sha256': sha256(path)})
    run_record['iteration_checks'] = checks
    run_record['runner_summary'] = str(summary_path.relative_to(result_dir))
    run_record['iterations'] = str(iterations_path.relative_to(result_dir))
    run_record['business_verification'] = business
    run_record['outputs_directory'] = str(output_dir.relative_to(result_dir))
    return all(checks.values()), ('success' if all(checks.values()) else 'one or more output checks failed'), file_rows


def recipe_manifest(recipe, dataset):
    path = ROOT / recipe['manual_source']['manifest_path']
    return read_json(path)['required_outputs']


def run_one(dataset, phase, result_dir, campaign_token):
    result_dir = Path(result_dir)
    if result_dir.exists():
        raise FileExistsError(f'refusing to reuse result directory: {result_dir}')
    record = {
        'schema_version': 'functional-trial-record-v1', 'dataset': dataset,
        'phase': phase, 'status': 'in_progress', 'image_tag': IMAGE,
        'started': False, 'container_retained': False,
    }
    try:
        result_dir.mkdir(parents=True)
        (result_dir / 'workspace-parent').mkdir()
        recipe, bindings, host_check = host_validate(dataset)
        workspace, host_parent = workspace_layout(recipe, result_dir)
        if host_parent != result_dir / 'workspace-parent':
            raise AssertionError('workspace host layout changed unexpectedly')
        name = f'otr-functional-{phase}-{dataset}-{campaign_token}'
        image_before = inspect_image()
        argv = docker_create_argv(dataset, phase, IMAGE, result_dir, host_parent, name)
        record.update(image_id_before_create=image_before, container_name=name,
                      workspace_container_parent=str(WORKSPACE_PARENT_CONTAINER),
                      workspace_container_path=str(workspace),
                      workspace_host_parent=str(host_parent.resolve()),
                      host_binding_check=host_check, bindings=bindings,
                      docker_create_argv=argv, shell_payload=shell_command(dataset, phase),
                      entrypoint_before_image=argv.index('--entrypoint') < argv.index(IMAGE))
        write_json(result_dir / 'run-record.json', record)
        created = subprocess.run(argv, check=True, text=True, capture_output=True)
        container_id = created.stdout.strip()
        record['container_id_from_create'] = container_id
        record['container_id'] = container_id
        record['container_retained'] = True
        inspect = inspect_container(name)
        record.update(container_id=inspect['Id'], container_image_id=inspect['Image'],
                      container_status_before_start=inspect['State']['Status'])
        record['mount_targets'] = {m['Destination']: {'source': m['Source'], 'rw': m['RW']}
                                   for m in inspect.get('Mounts', [])}
        if inspect['Id'] != container_id:
            raise RuntimeError('docker create ID differs from inspected container ID')
        if inspect['Image'] != image_before:
            raise RuntimeError('created container image ID differs from inspected tag ID')
        validate_container_mounts(inspect, host_parent)
        write_json(result_dir / 'run-record.json', record)
        record['started'] = True
        record['container_retained'] = True
        write_json(result_dir / 'run-record.json', record)
        print(f"START {phase} {dataset}: container={inspect['Id'][:12]} image={inspect['Image']}",
              flush=True)
        exit_code = run_attached(inspect['Id'], result_dir / 'container.log')
        final = inspect_container(name)
        image_after = inspect_image()
        record.update(container_exit_code=exit_code,
                      container_status_after=final['State']['Status'],
                      image_id_after_run=image_after,
                      image_identity_stable=(image_before == final['Image'] == image_after))
        preflight_path = result_dir / 'preflight.json'
        preflight = read_json(preflight_path) if preflight_path.is_file() else {}
        record['container_preflight'] = preflight
        if phase == 'preflight':
            record['status'] = ('success' if exit_code == 0 and final['State']['ExitCode'] == 0
                                and preflight.get('status') == 'success'
                                and record['image_identity_stable'] else 'failed')
            if record['status'] != 'success':
                record['failure_stage'] = ('container_preflight' if preflight.get('status') != 'success'
                                           else 'container_exit')
        else:
            accepted, detail, rows = _summary_and_archive(dataset, result_dir, recipe, record)
            record['archive_files'] = rows
            record['archive_hashes_verified'] = all(
                sha256(result_dir / row['path']) == row['sha256'] for row in rows)
            record['status'] = ('success' if exit_code == 0 and final['State']['ExitCode'] == 0
                                and accepted and record['archive_hashes_verified']
                                and record['image_identity_stable'] else 'failed')
            if record['status'] != 'success':
                record['failure_stage'] = ('container_preflight' if preflight.get('status') != 'success'
                                           else 'workload_or_loop_validation')
                record['failure_detail'] = detail
        record['container_retained'] = True
    except Exception as exc:
        record['status'] = 'failed'
        record.setdefault('failure_stage',
                          'host_frozen_preflight' if 'host_check' not in record
                          else 'container_create_or_preflight_setup')
        record['error'] = f'{type(exc).__name__}: {exc}'
        record['container_retained'] = bool(record.get('container_id'))
    write_json(result_dir / 'run-record.json', record)
    # Recheck and index all durable evidence. Do not include the index itself.
    indexed = []
    for path in sorted(result_dir.rglob('*')):
        if path.is_file() and path.name not in ('archive-index.json', 'run-record.json'):
            indexed.append({'path': str(path.relative_to(result_dir)),
                            'size_bytes': path.stat().st_size,
                            'sha256': sha256(path)})
    write_json(result_dir / 'archive-index.json', {
        'schema_version': 'functional-trial-archive-v1',
        'dataset': dataset, 'phase': phase, 'files': indexed,
        'all_hashes_verified': all(
            sha256(result_dir / row['path']) == row['sha256'] for row in indexed),
    })
    record['archive_index'] = 'archive-index.json'
    record['archive_index_sha256'] = sha256(result_dir / 'archive-index.json')
    record['archive_hashes_verified'] = read_json(result_dir / 'archive-index.json')['all_hashes_verified']
    write_json(result_dir / 'run-record.json', record)
    return record


def run_preflights(campaign, token):
    campaign = Path(campaign)
    campaign.mkdir(parents=True, exist_ok=False)
    state = {'schema_version': 'functional-trial-campaign-v1', 'phase': 'preflight',
             'status': 'in_progress', 'image_tag': IMAGE, 'datasets': {},
             'not_started': []}
    for dataset in DATASETS:
        print(f'PREFLIGHT {dataset}', flush=True)
        result = run_one(dataset, 'preflight', campaign / 'preflight' / dataset, token)
        state['datasets'][dataset] = str((campaign / 'preflight' / dataset / 'run-record.json').relative_to(ROOT))
        if result['status'] != 'success':
            state['status'] = 'failed'
            state['failed_dataset'] = dataset
            state['not_started'] = [name for name in DATASETS if name not in state['datasets']]
            write_json(campaign / 'campaign-record.json', state)
            return 1
    state['status'] = 'success'
    write_json(campaign / 'campaign-record.json', state)
    return 0


AUDIT_ENTRY = 'analysis/hotspot-comparison/scripts/offline_audit_entry.py'
# The physical repository root, independent of the patchable ROOT used for
# campaign-relative bookkeeping; verifier hashes must always come from here.
PHYSICAL_REPO = Path(__file__).resolve().parents[3]
AUDIT_REPO_MOUNT = '/opt/office-trace-replay'
AUDIT_WORKSPACE_MOUNT = '/workspace'
AUDIT_RESULTS_MOUNT = '/results'
VERIFIER_PACKAGE_FILES = ('verify.py', 'spreadsheet.py', 'contracts.py', 'workbooks.py')


def run_trials(campaign, token):
    campaign = Path(campaign)
    state_path = campaign / 'campaign-record.json'
    state = read_json(state_path)
    if state.get('phase') != 'preflight' or state.get('status') != 'success':
        raise ValueError('both pure container preflights must succeed first')
    preflight_records = {name: read_json(ROOT / path) for name, path in state['datasets'].items()}
    if set(preflight_records) != set(DATASETS) or any(r.get('status') != 'success' for r in preflight_records.values()):
        raise ValueError('preflight result inventory is incomplete or failed')
    expected_image = inspect_image()
    for dataset, prior in preflight_records.items():
        if prior.get('container_image_id') != expected_image:
            raise ValueError(f'{dataset}: image tag no longer matches preflight container identity')
        _recipe, current_bindings = source_bindings(dataset)
        if prior.get('bindings') != current_bindings:
            raise ValueError(f'{dataset}: source bindings changed after pure preflight')
    state.update(phase='trial', status='in_progress', trials={}, not_started=[])
    for dataset in DATASETS:
        print(f'TRIAL {dataset} loops=1', flush=True)
        result = run_one(dataset, 'trial', campaign / 'trials' / dataset, token)
        state['trials'][dataset] = str((campaign / 'trials' / dataset / 'run-record.json').relative_to(ROOT))
        if result['status'] != 'success':
            state['status'] = 'failed'
            state['failed_dataset'] = dataset
            state['not_started'] = [name for name in DATASETS if name not in state['trials']]
            write_json(state_path, state)
            return 1
    state['status'] = 'success'
    write_json(state_path, state)
    return 0


def _audit_docker_argv(dataset, workspace_host, results_host, name):
    repo_mount = f'type=bind,src={ROOT.resolve()},dst={AUDIT_REPO_MOUNT},readonly'
    workspace_mount = (f'type=bind,src={Path(workspace_host).resolve()},'
                       f'dst={AUDIT_WORKSPACE_MOUNT},readonly')
    results_mount = (f'type=bind,src={Path(results_host).resolve()},'
                     f'dst={AUDIT_RESULTS_MOUNT}')
    command = (f'{PYTHON} {AUDIT_REPO_MOUNT}/{AUDIT_ENTRY} '
               f'--dataset {dataset} '
               f'--workspace {AUDIT_WORKSPACE_MOUNT} '
               f'--report {AUDIT_RESULTS_MOUNT}/independent-verification.json '
               f'--identity {AUDIT_RESULTS_MOUNT}/audit-identity.json')
    return [
        *DOCKER, 'create', '--name', name, '--network', 'none',
        '--env', 'PYTHONDONTWRITEBYTECODE=1',
        '--mount', repo_mount, '--mount', workspace_mount, '--mount', results_mount,
        '--entrypoint', '/bin/bash', IMAGE, '-c', command,
    ], command


def _audit_mount_evidence(container_name, workspace_host, results_host):
    """Prove the workspace/repo mounts are read-only and results are writable."""
    inspect = inspect_container(container_name)
    mounts = {item['Destination']: item for item in inspect.get('Mounts', [])}
    workspace = mounts.get(AUDIT_WORKSPACE_MOUNT)
    repo = mounts.get(AUDIT_REPO_MOUNT)
    results = mounts.get(AUDIT_RESULTS_MOUNT)
    problems = []
    if workspace is None or workspace.get('RW'):
        problems.append(f'{AUDIT_WORKSPACE_MOUNT} is not a read-only mount')
    if repo is None or repo.get('RW'):
        problems.append(f'{AUDIT_REPO_MOUNT} is not a read-only mount')
    if results is None or not results.get('RW'):
        problems.append(f'{AUDIT_RESULTS_MOUNT} is not a writable mount')
    if workspace is not None and Path(workspace['Source']).resolve() != Path(workspace_host).resolve():
        problems.append('workspace mount source does not point at the archived trial workspace')
    if results is not None and Path(results['Source']).resolve() != Path(results_host).resolve():
        problems.append('results mount source does not point at the acceptance directory')
    return mounts, problems


def _verify_trial_inventory(campaign, state):
    """Reject empty/partial inventories and inconsistent trial records."""
    trials = state.get('trials') or {}
    if set(trials) != set(DATASETS):
        raise ValueError(f'acceptance requires exactly {sorted(DATASETS)} in the trial '
                         f'inventory; found {sorted(trials) or "nothing"}')
    for dataset in DATASETS:
        record = read_json(ROOT / trials[dataset])
        result_dir = (ROOT / trials[dataset]).parent
        if (record.get('dataset') != dataset or record.get('phase') != 'trial'
                or record.get('status') != 'success'
                or record.get('container_exit_code') != 0):
            raise ValueError(f'{dataset}: trial record is not a completed successful run '
                             f"(phase={record.get('phase')}, status={record.get('status')}, "
                             f"exit={record.get('container_exit_code')})")
        index_path = result_dir / 'archive-index.json'
        if not index_path.is_file():
            raise ValueError(f'{dataset}: archived trial has no archive index')
        index = read_json(index_path)
        mismatches = [row['path'] for row in index.get('files', [])
                      if sha256(result_dir / row['path']) != row['sha256']]
        if mismatches:
            raise ValueError(f'{dataset}: archived trial files no longer match their '
                             f'recorded hashes: {mismatches[:3]}')
        workspace_name = Path(record['workspace_container_path']).name
        workspace = result_dir / 'workspace-parent' / workspace_name
        if not workspace.is_dir():
            raise ValueError(f'{dataset}: archived trial workspace missing: {workspace}')
        # the audited workspace inputs must still match the trial-time bindings
        for name, want in record.get('bindings', {}).get('input_hashes', {}).items():
            actual = sha256(workspace / name)
            if actual != want:
                raise ValueError(f'{dataset}: workspace input {name} hash {actual} != '
                                 f'trial-time binding {want}')
        yield dataset, record, result_dir, workspace


def _source_association(dataset, trial_record):
    """Separate production materials (trial-bound) from the audit implementation."""
    trial_sources = trial_record.get('bindings', {})
    _recipe, audit_sources = source_bindings(dataset)
    production_keys = ('recipe_sha256', 'manifest_sha256', 'provenance_sha256',
                       'helper_sha256', 'input_hashes')
    production = {key: {'trial': trial_sources.get(key), 'audit': audit_sources.get(key),
                        'match': trial_sources.get(key) == audit_sources.get(key)}
                  for key in production_keys}
    trial_preflight = trial_record.get('container_preflight') or {}
    trial_verifier = trial_preflight.get('source_verifier_sha256')
    audit_verifier = {name: sha256(PHYSICAL_REPO / 'compatibility/verification' / name)
                      for name in VERIFIER_PACKAGE_FILES}
    if not isinstance(trial_verifier, dict):
        trial_verifier = {name: 'unknown' for name in VERIFIER_PACKAGE_FILES}
    return {
        'trial_sources': trial_sources,
        'audit_sources': audit_sources,
        'production_materials': production,
        'production_materials_all_match': all(item['match'] for item in production.values()),
        'verifier_comparison': {
            name: {'trial': trial_verifier.get(name, 'unknown'),
                   'audit': audit_verifier[name],
                   'match': trial_verifier.get(name) == audit_verifier[name]}
            for name in VERIFIER_PACKAGE_FILES},
        'trial_runner_sha256': trial_record.get('bindings', {}).get('runner_sha256'),
        'audit_runner_sha256': sha256(RUNNER_SOURCE),
    }


def _run_container_audit(dataset, workspace, acceptance_dir, token):
    name = f'otr-accept-{dataset}-{token}'
    image_before = inspect_image()
    argv, command = _audit_docker_argv(dataset, workspace, acceptance_dir, name)
    created = subprocess.run(argv, check=True, text=True, capture_output=True)
    container_id = created.stdout.strip()
    inspect = inspect_container(name)
    mounts, mount_problems = _audit_mount_evidence(name, workspace, acceptance_dir)
    if inspect['Image'] != image_before:
        raise RuntimeError('audit container image ID differs from the inspected tag')
    if mount_problems:
        raise ValueError('audit mount evidence rejected: ' + '; '.join(mount_problems))
    exit_code = run_attached(container_id, acceptance_dir / 'container.log')
    identity = read_json(acceptance_dir / 'audit-identity.json') \
        if (acceptance_dir / 'audit-identity.json').is_file() else {}
    return {
        'execution': 'container',
        'audit_image_id': inspect['Image'],
        'audit_container_id': container_id,
        'audit_container_exit_code': exit_code,
        'mount_evidence': {dest: {'source': item['Source'], 'rw': item['RW']}
                           for dest, item in mounts.items()},
        'mount_problems': mount_problems,
        'readonly_enforced': not mount_problems,
        'identity': identity,
    }


def _run_host_audit(dataset, workspace, acceptance_dir):
    """Host fallback: same entry script, but read-only is NOT enforced by the OS."""
    command = [sys.executable, str(ROOT / AUDIT_ENTRY),
               '--dataset', dataset,
               '--repo', str(ROOT),
               '--workspace', str(workspace),
               '--report', str(acceptance_dir / 'independent-verification.json'),
               '--identity', str(acceptance_dir / 'audit-identity.json')]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    (acceptance_dir / 'container.log').write_text(
        'host-mode audit (no container; read-only NOT enforced by mounts)\n'
        f"command: {command}\nexit: {completed.returncode}\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}")
    identity = read_json(acceptance_dir / 'audit-identity.json') \
        if (acceptance_dir / 'audit-identity.json').is_file() else {}
    return {
        'execution': 'host',
        'readonly_enforced': False,
        'readonly_note': ('host mode: the workspace is NOT protected by read-only mounts; '
                          'the interpreter and packages are the host ones, not the image ones'),
        'identity': identity,
        'audit_container_exit_code': completed.returncode,
    }


def accept_archived(campaign, token, host_mode=False):
    """Offline independent acceptance over a successful trial campaign's outputs.

    Re-runs nothing.  Every dataset expected by this launcher must be present
    in the trial inventory with a consistent, hash-verified archive; the
    audited workspace inputs must still match the trial-time bindings.  The
    audit itself runs the frozen execution source's independent verifier over
    an actually read-only mount of the archived workspace (container mode) or
    an explicitly-labelled host process, capturing the output hash before and
    after the verifier.  Production materials are associated with the trial
    record; the audit implementation is recorded as its own version, and a
    trial-time verifier hash that was never recorded is reported as unknown.
    Results go to a fresh acceptance directory; existing acceptance records
    are never overwritten and trial records are never rewritten.
    """
    campaign = Path(campaign)
    state = read_json(campaign / 'campaign-record.json')
    if state.get('phase') != 'trial' or state.get('status') != 'success':
        raise ValueError('offline acceptance requires a successful trial campaign: run '
                         '--preflight-only and then --run-trials on the SAME campaign-dir first')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    acceptance_root = campaign / f'acceptance-{stamp}-{token}'
    if acceptance_root.exists():
        raise FileExistsError(f'refusing to overwrite an existing acceptance record: {acceptance_root}')
    overall = {'schema_version': 'functional-trial-acceptance-campaign-v2',
               'phase': 'acceptance', 'status': 'in_progress',
               'campaign': str(campaign.relative_to(ROOT)),
               'acceptance_dir': str(acceptance_root.relative_to(ROOT)),
               'mode': 'host' if host_mode else 'container',
               'datasets': {}}
    write_json(acceptance_root / 'acceptance-campaign-record.json', overall)
    try:
        for dataset, trial_record, result_dir, workspace in _verify_trial_inventory(campaign, state):
            dataset_dir = acceptance_root / dataset
            dataset_dir.mkdir(parents=True)
            association = _source_association(dataset, trial_record)
            output_name = None
            for row in read_json(result_dir / 'archive-index.json').get('files', []):
                candidate = result_dir / row['path']
                if candidate.parent.name == 'output' and candidate.suffix == '.xlsx' \
                        and candidate.is_file() and candidate.stat().st_size > 1024 * 1024:
                    output_name = candidate.name
                    break
            if output_name is None:
                raise ValueError(f'{dataset}: cannot identify the archived output workbook')
            if host_mode:
                audit = _run_host_audit(dataset, workspace, dataset_dir)
            else:
                audit = _run_container_audit(dataset, workspace, dataset_dir, token)
            identity = audit.get('identity') or {}
            record = {
                'schema_version': 'functional-trial-acceptance-v2',
                'dataset': dataset,
                'status': 'success' if (audit.get('audit_container_exit_code') == 0
                                        and identity.get('status') == 'success'
                                        and identity.get('verifier_status') == 'success'
                                        and identity.get('output_unchanged_by_audit')
                                        and association['production_materials_all_match']) else 'failed',
                'trial_image_id': trial_record.get('container_image_id'),
                'trial_image_tag': trial_record.get('image_tag'),
                'audit': audit,
                'audit_image_id': audit.get('audit_image_id'),
                'association': association,
                'workspace': str(workspace.relative_to(ROOT)),
                'output_workbook': output_name,
                'output_sha256_before_audit': identity.get('output_sha256_before_audit'),
                'output_sha256_after_audit': identity.get('output_sha256_after_audit'),
                'output_unchanged_by_audit': identity.get('output_unchanged_by_audit'),
                'verification_report': str((dataset_dir / 'independent-verification.json').relative_to(ROOT)),
                'verifier_contract': identity.get('verifier_contract'),
                'verifier_status': identity.get('verifier_status'),
            }
            report_path = dataset_dir / 'independent-verification.json'
            if report_path.is_file():
                report = read_json(report_path)
                record['verifier_failures'] = report.get('failures')
                record['verifier_contract'] = report.get('validation_contract')
                record['checks_total'] = len(report.get('checks', {}))
                record['checks_passed'] = sum(1 for item in report.get('checks', {}).values()
                                              if item.get('ok'))
            write_json(dataset_dir / 'acceptance-record.json', record)
            overall['datasets'][dataset] = str((dataset_dir / 'acceptance-record.json').relative_to(ROOT))
            print(f"ACCEPT {dataset}: {record['status']} "
                  f"(verifier={record.get('verifier_status')}, "
                  f"unchanged={record.get('output_unchanged_by_audit')})", flush=True)
            if record['status'] != 'success':
                overall['status'] = 'failed'
                overall['failed_dataset'] = dataset
                break
        else:
            overall['status'] = 'success'
    except Exception as exc:
        overall['status'] = 'failed'
        overall['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        write_json(acceptance_root / 'acceptance-campaign-record.json', overall)
    return 0 if overall.get('status') == 'success' else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign-dir', type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--preflight-only', action='store_true')
    group.add_argument('--run-trials', action='store_true')
    group.add_argument('--accept-archived', action='store_true',
                       help='offline independent acceptance over a successful trial '
                            "campaign's archived workspaces (no re-run)")
    parser.add_argument('--host', action='store_true',
                        help='with --accept-archived: run the audit on the host instead '
                             'of a read-only container (labelled, not mount-protected)')
    args = parser.parse_args(argv)
    token = secrets.token_hex(4)
    campaign = args.campaign_dir
    if campaign is None:
        if args.accept_archived:
            parser.error('--accept-archived requires an explicit --campaign-dir '
                         'pointing at the successful trial campaign')
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        campaign = ROOT / 'analysis/hotspot-comparison/replay-runs' / f'{stamp}-functional-trials-{token}'
    elif not campaign.is_absolute():
        campaign = ROOT / campaign
    campaign = campaign.resolve()
    try:
        campaign.relative_to(ROOT)
    except ValueError:
        parser.error('--campaign-dir must be inside the repository')
    if args.preflight_only:
        return run_preflights(campaign, token)
    if args.accept_archived:
        return accept_archived(campaign, token, host_mode=args.host)
    return run_trials(campaign, token)


if __name__ == '__main__':
    raise SystemExit(main())
