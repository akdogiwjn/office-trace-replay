#!/usr/bin/env python3
"""Run the explicitly requested native / py-spy campaign in strict order."""
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import shlex
import shutil
from datetime import datetime, timezone
from pathlib import Path
import uuid

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
PLAN_PATH = HERE / 'config/targeted-functional-hotspot-plan-v2.json'
CAMPAIGNS = HERE / 'raw/current-loop-hotspots-v2'
COLLECTOR_PATH = HERE / 'scripts/collect_current_loop_profiles.py'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def sha_tree(root, *, required_raw_files=(), record_path=None, acquisition_ok=True):
    """Index a stage and make its final qualification agree with persistence.

    The collection record is written before the index and its resulting bytes
    are hashed into that index.  On an index failure the record is downgraded
    and the caller must persist that final failure in the campaign manifest.
    Acquisition/parser stage results are retained separately.
    """
    root = Path(root)
    index_path = root / 'sha256-index.json'
    record_path = Path(record_path) if record_path else None
    rows = []
    seen = set()
    for path in sorted(p for p in root.rglob('*') if p.is_file()
                       and p.name != index_path.name
                       and (record_path is None or p != record_path)):
        rel = str(path.relative_to(root))
        seen.add(rel)
        try:
            size = path.stat().st_size
            digest = sha(path)
            rows.append({'path': rel, 'bytes': size, 'sha256': digest, 'status': 'hashed'})
        except OSError as exc:
            try:
                size = path.stat().st_size
            except OSError:
                size = None
            rows.append({'path': rel, 'bytes': size, 'sha256': None,
                         'status': 'unreadable',
                         'error': f'{type(exc).__name__}: {exc}'})

    required_rows = []
    for rel in required_raw_files:
        row = next((r for r in rows if r['path'] == rel), None)
        if row is None:
            full_path = root / rel
            row = {'path': rel, 'bytes': None, 'sha256': None,
                   'status': 'missing',
                   'error': 'required raw file was not present during indexing'}
            rows.append(row)
        required_rows.append(row)
    required_complete = bool(required_rows) and all(r['status'] == 'hashed' for r in required_rows)
    hash_errors = [r for r in rows if r['status'] != 'hashed']
    integrity = {
        'status': 'complete' if not hash_errors else 'partial',
        'index_path': str(index_path),
        'index_write_status': 'pending',
        'indexed_file_count': sum(r['status'] == 'hashed' for r in rows),
        'unreadable_or_missing_file_count': len(hash_errors),
        'required_raw_files': list(required_raw_files),
        'required_raw_sha256_complete': required_complete,
        'required_raw_failures': [r for r in required_rows if r['status'] != 'hashed'],
    }

    acquisition_eligible = False
    record_update_error = None
    if record_path and record_path.is_file():
        try:
            record = read(record_path)
            stages = record.setdefault('stage_status', {})
            acquisition_eligible = bool(stages.get('profile_eligible') and acquisition_ok)
            record['acquisition_profile_eligible'] = acquisition_eligible
            record['final_profile_eligible'] = False
            integrity['index_write_status'] = 'success'  # candidate; downgraded if replace fails
            candidate_eligible = bool(acquisition_eligible and required_complete and not hash_errors)
            integrity['final_profile_eligible'] = candidate_eligible
            record['archive_integrity'] = integrity
            stages['archive_sha256_index'] = 'success'
            stages['required_raw_sha256'] = 'success' if required_complete else 'failed'
            stages['profile_eligible'] = candidate_eligible
            record['final_profile_eligible'] = candidate_eligible
            write(record_path, record)
            rel = str(record_path.relative_to(root))
            rows.append({'path': rel, 'bytes': record_path.stat().st_size,
                         'sha256': sha(record_path), 'status': 'hashed'})
        except (OSError, ValueError, TypeError) as exc:
            record_update_error = f'{type(exc).__name__}: {exc}'
            integrity['record_update_error'] = record_update_error
            integrity['status'] = 'failed'
            failed_record = {'path': str(record_path.relative_to(root)),
                             'bytes': None, 'sha256': None, 'status': 'unreadable',
                             'error': record_update_error}
            rows.append(failed_record)
            hash_errors.append(failed_record)

    index = {'schema_version': 'campaign-sha256-index-v2',
             'status': integrity['status'], 'files': rows,
             'required_raw_sha256_complete': required_complete}
    temp = index_path.with_name(index_path.name + '.tmp')
    index_error = None
    try:
        write(temp, index)
        temp.replace(index_path)
    except OSError as exc:
        index_error = f'{type(exc).__name__}: {exc}'
        integrity.update(status='failed', index_write_status='failed',
                         final_profile_eligible=False, index_write_error=index_error)
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        if record_path and record_path.is_file():
            try:
                record = read(record_path)
                record['final_profile_eligible'] = False
                record.setdefault('archive_integrity', {}).update(integrity)
                record.setdefault('stage_status', {})['archive_sha256_index'] = 'failed'
                record['stage_status']['profile_eligible'] = False
                write(record_path, record)
            except (OSError, ValueError, TypeError) as record_exc:
                integrity['record_update_error'] = f'{type(record_exc).__name__}: {record_exc}'
    else:
        integrity['index_write_status'] = 'success'
        integrity['final_profile_eligible'] = bool(
            acquisition_eligible and required_complete and not hash_errors
            and record_update_error is None)
    if record_update_error:
        integrity.update(status='failed', final_profile_eligible=False)
    # On success, the record bytes already hashed above are the final bytes.
    # Do not update it after the index replacement.
    return integrity


def finalize_mode(campaign, manifest, plan, dataset, mode, record_path, ok):
    """Persist acquisition, archive and stop state before any next stage."""
    campaign, record_path = Path(campaign), Path(record_path)
    stage_dir = record_path.parent.parent
    try:
        record = read(record_path) if record_path.is_file() else {}
    except (OSError, ValueError, TypeError) as exc:
        record = {'status': 'unreadable',
                  'record_read_error': f'{type(exc).__name__}: {exc}'}
    config_id = dataset
    required = ([f'raw/{config_id}.data', f'raw/{config_id}.samples.txt']
                if mode == 'native' else [f'raw/{config_id}.pyspy.raw'])
    try:
        archive = sha_tree(stage_dir, required_raw_files=required,
                           record_path=record_path if record_path.is_file() else None,
                           acquisition_ok=ok)
        if not record_path.is_file():
            archive.update(status='failed', final_profile_eligible=False,
                           record_update_error='collection record missing; final archive record was not saved')
    except Exception as exc:
        archive = {'status': 'failed', 'required_raw_sha256_complete': False,
                   'error': f'{type(exc).__name__}: {exc}'}
        if record_path.is_file():
            try:
                record = read(record_path)
                record['archive_integrity'] = archive
                stages = record.setdefault('stage_status', {})
                stages['archive_sha256_index'] = 'failed'
                stages['required_raw_sha256'] = 'failed'
                stages['profile_eligible'] = False
                write(record_path, record)
            except (OSError, ValueError, TypeError):
                pass
    try:
        record = read(record_path) if record_path.is_file() else record
    except (OSError, ValueError, TypeError) as exc:
        record = {'status': 'unreadable',
                  'record_read_error': f'{type(exc).__name__}: {exc}',
                  'archive_integrity': archive,
                  'stage_status': {'archive_sha256_index': 'failed',
                                   'required_raw_sha256': 'failed',
                                   'profile_eligible': False}}
    record_eligible = bool(record.get('acquisition_profile_eligible',
                                      record.get('stage_status', {}).get('profile_eligible', False)))
    final_eligible = bool(ok and record_eligible
                          and archive.get('status') == 'complete'
                          and archive.get('required_raw_sha256_complete')
                          and archive.get('index_write_status') == 'success'
                          and archive.get('final_profile_eligible'))
    # A failure discovered after sha_tree() (for example an exception around
    # indexing) is reflected explicitly in the campaign record, independently
    # of workload/record/export/parser outcomes.
    if not final_eligible:
        archive['final_profile_eligible'] = False
    record['final_profile_eligible'] = final_eligible
    record.setdefault('stage_status', {})['profile_eligible'] = final_eligible
    manifest['completed_modes'].append({
        'dataset': dataset, 'mode': mode,
        'status': record.get('status', 'failed'),
        'record': str(record_path.relative_to(campaign)),
        'stage_status': record.get('stage_status', {}),
        'archive_integrity': archive,
        'profile_eligible': final_eligible,
    })
    stage_ok = final_eligible
    if not stage_ok:
        current_index = plan['order'].index(dataset)
        current_mode_index = plan['modes'].index(mode)
        not_started = []
        for later in plan['order'][current_index:]:
            for next_mode in plan['modes']:
                if (plan['order'].index(later) > current_index
                        or (later == dataset and plan['modes'].index(next_mode) > current_mode_index)):
                    not_started.append({'dataset': later, 'mode': next_mode,
                                        'status': 'not_started',
                                        'reason': 'earlier collection or archive stage failed; strict stop policy'})
        if archive.get('index_write_status') != 'success':
            failure_stage = 'archive_sha256_index'
        elif not archive.get('required_raw_sha256_complete'):
            failure_stage = 'required_raw_sha256'
        elif archive.get('status') != 'complete':
            failure_stage = 'archive_integrity'
        else:
            failure_stage = 'collection'
        manifest.update(status='stopped_on_failure',
                        failure={'dataset': dataset, 'mode': mode,
                                 'stage': failure_stage,
                                 'collection_ok': bool(ok),
                                 'collection_status': record.get('status'),
                                 'collection_reason': record.get('reason'),
                                 'archive_integrity': archive,
                                 'profile_eligible': False,
                                 'record_path': str(record_path.relative_to(campaign)),
                                 'archive_failure_reason': archive.get('index_write_error')
                                     or archive.get('record_update_error')
                                     or archive.get('error')
                                     or ('acquisition/parser qualification failed'
                                         if not record_eligible or not ok else None),
                                 'stage_status': record.get('stage_status', {})},
                        not_started=not_started)
    write(campaign / 'campaign-manifest.json', manifest)
    return stage_ok, record, archive


def evidence_inventory():
    """Read-only snapshot of reusable evidence and the exact gaps this plan fills."""
    history_path = HERE / 'reports/hotspot-version-comparison-v1/evidence-inventory.json'
    history = read(history_path) if history_path.is_file() else {}
    previous_controls = history.get('current_old_control_profiles', {})
    current_v1 = HERE / 'raw/current-loop-verifier-v1'
    reusable = {}
    for config in ('opm-n1', 'opm-n10', 'tlc'):
        previous = previous_controls.get(config, {})
        path = HERE / 'processed' / f'{config}.json'
        reusable[config] = {
            'status': 'available_for_current-old-control-comparison' if path.is_file() and previous else 'missing',
            'source': str(path.relative_to(HERE)) if path.is_file() and previous else None,
            'sha256': sha(path) if path.is_file() and previous else None,
            'repeat_count': len(previous.get('native', [])) if path.is_file() and previous else 0,
            'quality_scope': 'existing parsed native cycles:u ROI profiles; retain runner/recipe version recorded in comparison evidence',
        }
    failures = {}
    for dataset in ('retail', 'hr', 'industry_productivity'):
        path = current_v1 / dataset / 'r1/out/collection-record.json'
        failure_path = current_v1 / dataset / 'r1/failure-record.json'
        source = path if path.is_file() else failure_path if failure_path.is_file() else None
        record = read(source) if source else {}
        failures[dataset] = {
            'status': record.get('status', 'missing'),
            'source': str(source.relative_to(HERE)) if source else None,
            'sha256': sha(source) if source else None,
            'eligible_for_formal_native_percentages': record.get('stage_status', {}).get('profile_eligible', False),
            'reason': record.get('reason') or record.get('profile_eligibility') or record.get('failure_stage'),
            'prior_pyspy': 'not a current-version complete pair; excluded from current lightweight-loop comparison',
        }
    return {
        'schema_version': 'hotspot-evidence-inventory-v2',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'reuse': {
            'current_old_controls': reusable,
            'historical_reference': {
                'source': 'reports/hotspot-version-comparison-v1/evidence-inventory.json',
                'sha256': sha(history_path) if history_path.is_file() else None,
                'scope': 'historical reported/profile evidence only where its source supports the requested PDF N scale or TLC comparison; not represented as same-environment current code',
            },
            'prior_new_dataset_attempts': failures,
        },
        'missing_or_excluded': {
            'retail_hr_industry_productivity_current_loop_native': 'prior failures, incomplete export/ROI or verifier failure; not eligible',
            'retail_hr_industry_productivity_current_loop_pyspy': 'no eligible complete current lightweight-loop py-spy profile',
            'current_new_dataset_native_repeats': 'one repeat per dataset only; exploratory profile, no repeat stability estimate',
            'stat_strace_and_independent_audit': 'out of scope and intentionally not collected',
        },
        'required_minimal_collection': [
            {'dataset': d, 'mode': m, 'loops': 1}
            for d in ('retail', 'hr', 'industry_productivity')
            for m in ('native', 'pyspy')
        ],
        'old_control_inventory_source': history.get('current_old_control_profiles', {}),
    }


def load_collector():
    spec = importlib.util.spec_from_file_location('targeted_hotspot_collector', COLLECTOR_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def host_preflight(collector, cfg, plan=None):
    spec = importlib.util.spec_from_file_location(
        'targeted_preflight_runner', REPO / 'legacy/document-oe/bin/run_document_scene_loop.py')
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    from replay.run import validate_project
    from replay import freeze
    validate_project()
    count = (cfg.get('record_count') or 1) if cfg['scene'] == 'pdf' else None
    layout = runner.dataset_layout(cfg['scene'], cfg['dataset'], count or 1)
    if plan:
        expected_operation = int(plan.get('operation_timeout_seconds', 900))
        expected_recalc = int(plan.get('recalc_timeout_seconds', 600))
        if (layout['operation_timeout'] != expected_operation
                or layout['recalc_timeout'] != expected_recalc):
            raise ValueError('runner timeout settings do not match the selected performance plan')
    recipe = freeze.validate_dataset(cfg['scene'], cfg['dataset'], layout, count,
                                     check_installed=False)
    _, recipe_path, _ = collector.recipe_info(cfg)
    return {
        'status': 'success', 'dataset': cfg['dataset'],
        'workspace': str(layout['workspace']),
        'operation_timeout_seconds': layout['operation_timeout'],
        'recalc_timeout_seconds': layout['recalc_timeout'],
        'recipe_sha256': sha(recipe_path),
        'runner_sha256': sha(REPO / 'legacy/document-oe/bin/run_document_scene_loop.py'),
        'verifier_sha256': collector.verifier_hashes(cfg['scene']),
        'input_sha256': {name: sha(REPO / recipe['seed_path'] / name)
                         for name in recipe['input_hashes']},
        'helper_sha256': recipe.get('helper_hashes', {}),
    }


def container_preflight(plan, cfg, campaign, token):
    """Run the existing authoritative preflight in the selected image only."""
    folder = Path(campaign) / 'container-preflight' / cfg['dataset']
    folder.mkdir(parents=True, exist_ok=False)
    report = folder / 'preflight.json'
    name = f'office-hs-preflight-{token}-{cfg["dataset"]}'
    runner = REPO / 'legacy/document-oe/bin/run_document_scene_loop.py'
    timed = REPO / 'legacy/document-oe/bin/run_document_scene_loop_timed.py'
    py = plan.get('python', '/opt/document-bench/.venv/bin/python')
    args = ['/host-analysis/scripts/preflight_replay.py', '--scene', cfg['scene'],
            '--dataset', cfg['dataset'], '--expected-operation-timeout',
            str(plan.get('operation_timeout_seconds', 900)), '--expected-recalc-timeout',
            str(plan.get('recalc_timeout_seconds', 600)), '--output', '/preflight/preflight.json']
    command = ['docker', 'run', '--name', name, '--network', 'none',
               '-e', 'PYTHONDONTWRITEBYTECODE=1',
               '--mount', f'type=bind,src={HERE},dst=/host-analysis,readonly',
               '--mount', f'type=bind,src={REPO},dst=/opt/office-trace-replay,readonly',
               '--mount', f'type=bind,src={runner},dst=/opt/document-bench/bin/run_document_scene_loop.py,readonly',
               '--mount', f'type=bind,src={timed},dst=/opt/document-bench/bin/run_document_scene_loop_timed.py,readonly',
               '--mount', f'type=bind,src={folder},dst=/preflight',
               '--entrypoint', '/opt/document-bench/.venv/bin/python',
               plan.get('image_id', plan['image']), *args]
    (folder / 'docker-argv.json').write_text(json.dumps(command, indent=2) + '\n')
    with (folder / 'container.log').open('w') as log:
        proc = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                              text=True, timeout=120)
    (folder / 'exit-code.txt').write_text(f'{proc.returncode}\n')
    inspected = subprocess.run(['docker', 'inspect', name], text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if inspected.returncode == 0:
        obj = json.loads(inspected.stdout)[0]
        write(folder / 'container-inspect.json', obj)
        image_id, container_id = obj.get('Image'), obj.get('Id')
    else:
        image_id, container_id = None, None
        (folder / 'inspect.stderr').write_text(inspected.stderr)
    payload = read(report) if report.is_file() else {}
    ok = (proc.returncode == 0 and payload.get('status') == 'success'
          and payload.get('python_version') == '3.12.3'
          and image_id == plan.get('image_id'))
    row = {'status': 'success' if ok else 'failed', 'container_name': name,
           'container_id': container_id, 'actual_image_id': image_id,
           'exit_code': proc.returncode, 'report': str(report.relative_to(campaign)),
           'report_sha256': sha(report) if report.is_file() else None,
           'python_version': payload.get('python_version'),
           'runner_sha256': payload.get('runner_sha256'),
           'timed_runner_sha256': payload.get('timed_runner_sha256'),
           'recipe_sha256': payload.get('recipe_sha256'),
           'workspace': payload.get('workspace'),
           'operation_timeout_seconds': payload.get('operation_timeout_seconds'),
           'recalc_timeout_seconds': payload.get('recalc_timeout_seconds')}
    write(folder / 'preflight-record.json', row)
    if not ok:
        raise RuntimeError(f'container preflight failed for {cfg["dataset"]}: {row}')
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight-only', action='store_true',
                        help='Check all host bindings without Docker, evidence inventory or sampling')
    parser.add_argument('--plan', type=Path, default=PLAN_PATH)
    parser.add_argument('--campaign-root', type=Path,
                        help='new unique output directory; defaults below raw/current-loop-hotspots-v2')
    parser.add_argument('--container-preflight-only', action='store_true',
                        help='also run authoritative preflight containers, but no sampler or workload')
    args = parser.parse_args(argv)
    plan = read(args.plan)
    if (plan.get('loops') != 1 or plan.get('order') != ['hr_metro', 'retail_online']
            or plan.get('modes') != ['native', 'pyspy']):
        raise SystemExit('this campaign requires hr_metro -> retail_online, native -> pyspy, loops=1')
    collector = load_collector()
    configs = {cfg['config_id']: cfg for cfg in plan['configs']}
    if len(configs) != len(plan['configs']) or set(configs) != set(plan['order']) or any(
            configs[d].get('dataset') != d or configs[d].get('scene') != 'xlsx'
            or configs[d].get('record_count') is not None or configs[d].get('loops') != 1
            for d in plan['order']):
        raise SystemExit('selected configs must match both dataset IDs, xlsx, record_count=null, loops=1')
    if args.preflight_only:
        results = []
        for dataset in plan['order']:
            try:
                results.append(host_preflight(collector, configs[dataset], plan))
            except Exception as exc:
                results.append({'dataset': dataset, 'status': 'failed',
                                'error': f'{type(exc).__name__}: {exc}'})
        ok = all(item['status'] == 'success' for item in results)
        print(json.dumps({'status': 'success' if ok else 'failed',
                          'scope': 'host bindings only; no container or sampler started',
                          'datasets': results}, indent=2), flush=True)
        return 0 if ok else 1
    if args.container_preflight_only:
        token = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        campaign = args.campaign_root.resolve() if args.campaign_root else CAMPAIGNS / f'{token}-container-preflight'
        campaign.mkdir(parents=True, exist_ok=False)
        result = {'schema_version': 'new-xlsx-container-preflight-v1',
                  'status': 'in_progress', 'image': plan['image'],
                  'image_id': subprocess.check_output(
                      ['docker', 'image', 'inspect', plan['image'], '--format', '{{.Id}}'],
                      text=True).strip(),
                  'plan_sha256': sha(args.plan), 'datasets': []}
        if result['image_id'] != plan['image_id']:
            result.update(status='failed', error='selected image ID does not match plan')
            write(campaign / 'preflight-manifest.json', result)
            return 1
        try:
            for dataset in plan['order']:
                host_preflight(collector, configs[dataset], plan)
                result['datasets'].append(container_preflight(
                    plan, configs[dataset], campaign, token))
        except Exception as exc:
            result.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        else:
            result['status'] = 'success'
        write(campaign / 'preflight-manifest.json', result)
        print(json.dumps(result, indent=2), flush=True)
        return 0 if result['status'] == 'success' else 1
    actual_image = subprocess.check_output(
        ['docker', 'image', 'inspect', plan['image'], '--format', '{{.Id}}'],
        text=True).strip()
    if actual_image != plan['image_id']:
        raise SystemExit(f"image ID mismatch: {actual_image} != {plan['image_id']}; no workloads started")

    run_token = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    campaign = args.campaign_root.resolve() if args.campaign_root else CAMPAIGNS / run_token
    campaign.mkdir(parents=True, exist_ok=False)
    manifest = {
        'schema_version': 'targeted-hotspot-campaign-v2',
        'status': 'in_progress', 'run_token': run_token,
        'image': plan['image'], 'image_id': actual_image,
        'plan_path': str(args.plan), 'plan_sha256': sha(args.plan),
        'collector_sha256': sha(COLLECTOR_PATH),
        'analysis_scripts_sha256': {
            name: sha(HERE / 'scripts' / name) for name in (
                'collect_current_loop_profiles.py', 'collect_native.sh',
                'collect_pyspy.sh', 'run_workload.sh', 'preflight_replay.py',
                'bounded_perf_export.py', 'collection_quality.py', 'parse_native.py', 'parse_pyspy.py',
                'script_identity.py',
                'monitor_procs.py', 'roi_marker.py', 'tstamp_pipe.py')},
        'requested_task_order': [
            {'dataset': dataset, 'mode': mode, 'loops': 1}
            for dataset in plan['order'] for mode in plan['modes']],
        'datasets': list(plan['order']), 'loops': plan['loops'],
        'sampling': plan['sampling'], 'modes': plan['modes'],
        'host_preflight': {}, 'completed_modes': [],
        'stop_policy': 'Any binding, workload, record, export, parser, ROI, py-spy, or business validation failure stops all later modes and datasets; no retries.',
    }
    write(campaign / 'campaign-manifest.json', manifest)
    write(campaign / 'evidence-inventory-v2.json', evidence_inventory())

    # Validate the first dataset before its first container. Every later run
    # repeats the authoritative installed-image check inside its own container.
    try:
        first = configs[plan['order'][0]]
        manifest['host_preflight'][first['dataset']] = host_preflight(collector, first, plan)
        write(campaign / 'campaign-manifest.json', manifest)
    except Exception as exc:
        manifest.update(status='stopped_preflight_failure',
                        failure={'dataset': plan['order'][0], 'mode': 'host_preflight',
                                 'error': f'{type(exc).__name__}: {exc}'})
        write(campaign / 'campaign-manifest.json', manifest)
        print(json.dumps(manifest['failure'], indent=2), flush=True)
        return 1

    for dataset in plan['order']:
        cfg = configs[dataset]
        if dataset not in manifest['host_preflight']:
            try:
                manifest['host_preflight'][dataset] = host_preflight(collector, cfg, plan)
                write(campaign / 'campaign-manifest.json', manifest)
            except Exception as exc:
                manifest.update(status='stopped_preflight_failure',
                                failure={'dataset': dataset, 'mode': 'host_preflight',
                                         'error': f'{type(exc).__name__}: {exc}'})
                write(campaign / 'campaign-manifest.json', manifest)
                print(json.dumps(manifest['failure'], indent=2), flush=True)
                return 1
        for mode in plan['modes']:
            print(f"START {dataset} mode={mode} loops=1", flush=True)
            try:
                ok = collector.collect_one(plan, cfg, mode, campaign_root=campaign)
                stage = campaign / dataset / ('r1' if mode == 'native' else 'pyspy')
                record_path = stage / 'out/collection-record.json'
                record = read(record_path) if record_path.is_file() else {}
            except Exception as exc:
                ok = False
                record = {'status': 'failed', 'reason': f'{type(exc).__name__}: {exc}'}
                record_path = campaign / dataset / ('r1' if mode == 'native' else 'pyspy') / 'out/collection-record.json'
                if not record_path.exists():
                    write(record_path, record)
            stage_ok, record, archive = finalize_mode(
                campaign, manifest, plan, dataset, mode, record_path, ok)
            manifest['completed_modes'][-1]['indexed_file_count'] = archive.get('indexed_file_count', 0)
            write(campaign / 'campaign-manifest.json', manifest)
            if not stage_ok:
                print(json.dumps(manifest['failure'], indent=2), flush=True)
                return 1

    manifest['status'] = 'complete'
    write(campaign / 'campaign-manifest.json', manifest)
    print(json.dumps({'status': manifest['status'], 'campaign': str(campaign),
                      'completed_modes': manifest['completed_modes']}, indent=2), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
