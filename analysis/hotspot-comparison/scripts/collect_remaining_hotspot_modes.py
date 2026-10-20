#!/usr/bin/env python3
"""Collect only the five explicitly missing Retail/HR/Industry modes."""
from __future__ import annotations

import json
import shlex
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
if str(HERE / 'scripts') not in sys.path:
    sys.path.insert(0, str(HERE / 'scripts'))

import collect_targeted_hotspots_v2 as campaign_tools

PLAN_PATH = HERE / 'config/targeted-functional-hotspot-plan-v2.json'
RECOVERY_RECORD = (HERE / 'raw/current-loop-hotspots-v2/recovery/'
                   '20261019T122928Z-a6a55875-retail-native-offline/retail/r1/'
                   'out/recovery-record.json')
TASKS = (
    ('retail', 'pyspy'),
    ('hr', 'native'),
    ('hr', 'pyspy'),
    ('industry_productivity', 'native'),
    ('industry_productivity', 'pyspy'),
)


def validate_tasks(tasks=TASKS):
    if tuple(tasks) != TASKS:
        raise ValueError(f'this recovery scheduler is fixed to tasks {TASKS!r}')
    return TASKS


def recovery_reference(path=RECOVERY_RECORD):
    """Verify, but do not import, the already recovered Retail native status."""
    path = Path(path)
    record = campaign_tools.read(path)
    if record.get('status') != 'offline_reparse_complete' or not record.get('final_profile_eligible'):
        raise ValueError('Retail native recovery record is not eligible')
    archive = record.get('archive_integrity', {})
    if (archive.get('status') != 'complete'
            or archive.get('index_write_status') != 'success'
            or not archive.get('required_raw_sha256_complete')):
        raise ValueError('Retail native recovery archive is incomplete')
    index_path = Path(archive.get('index_path', ''))
    index = campaign_tools.read(index_path)
    record_rel = 'out/recovery-record.json'
    row = next((item for item in index.get('files', []) if item.get('path') == record_rel), None)
    record_hash = campaign_tools.sha(path)
    if not row or row.get('status') != 'hashed' or row.get('sha256') != record_hash:
        raise ValueError('Retail native recovery record hash does not match its index')
    source_perf_hash = record.get('source_artifacts', {}).get('perf_data', {}).get('sha256')
    raw_row = next((item for item in index.get('files', [])
                    if item.get('path') == 'raw/retail.data'), None)
    if not raw_row or raw_row.get('sha256') != source_perf_hash:
        raise ValueError('Retail native perf.data hash is not bound by its recovery index')
    return {
        'path': str(path.relative_to(REPO)),
        'record_sha256': record_hash,
        'index_path': str(index_path.relative_to(REPO)),
        'index_sha256': campaign_tools.sha(index_path),
        'status': record['status'],
        'profile_eligible': True,
        'source_perf_data_sha256': source_perf_hash,
        'relation': 'existing offline recovery evidence; not a task completed in this campaign',
    }


def runtime_preflight(plan, cfg, campaign, token):
    """Run the existing in-image binding/Python preflight without workload."""
    preflight_dir = Path(campaign) / 'preflight'
    preflight_dir.mkdir(parents=True, exist_ok=True)
    container_name = f'office-hs-preflight-{token}-{cfg["dataset"]}'
    script = (
        'set -euo pipefail; cp -r /host-analysis/scripts /tmp/hs-scripts; '
        f'"{plan.get("python", "/opt/document-bench/.venv/bin/python")}" '
        '/tmp/hs-scripts/preflight_replay.py '
        f'--scene {shlex.quote(cfg["scene"])} --dataset {shlex.quote(cfg["dataset"])} '
        f'--pdf-applicant-count {cfg.get("record_count") or 1} '
        '--output /tmp/preflight.json'
    )
    runner_path = REPO / 'legacy/document-oe/bin/run_document_scene_loop.py'
    command = [
        'docker', 'run', '--rm', '--name', container_name, '--network', 'none',
        '--mount', f'type=bind,src={HERE},dst=/host-analysis,readonly',
        '--mount', f'type=bind,src={REPO},dst=/opt/office-trace-replay,readonly',
        '--mount', (f'type=bind,src={runner_path},'
                    'dst=/opt/document-bench/bin/run_document_scene_loop.py,readonly'),
        '--entrypoint', '/bin/bash', plan.get('image_id', plan['image']), '-c', script,
    ]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    (preflight_dir / f'{cfg["dataset"]}.stdout.log').write_text(result.stdout)
    (preflight_dir / f'{cfg["dataset"]}.stderr.log').write_text(result.stderr)
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        payload = {'status': 'failed', 'error': 'container preflight emitted no JSON result'}
    payload['container_name'] = container_name
    payload['container_exit_code'] = result.returncode
    campaign_tools.write(preflight_dir / f'{cfg["dataset"]}.json', payload)
    if result.returncode != 0 or payload.get('status') != 'success':
        raise RuntimeError(f'{cfg["dataset"]} runtime preflight failed: {payload}')
    if payload.get('python_version') != '3.12.3':
        raise RuntimeError(f'{cfg["dataset"]} runtime Python is not 3.12.3')
    return payload


def execute_tasks(plan, configs, campaign, manifest, *, collector, tasks=TASKS):
    """Run exact tasks serially and persist stop state after each task."""
    tasks = validate_tasks(tasks)
    for task_index, (dataset, mode) in enumerate(tasks):
        cfg = configs[dataset]
        print(f'START {dataset} mode={mode} loops=1', flush=True)
        record_path = Path(campaign) / dataset / ('r1' if mode == 'native' else 'pyspy') / 'out/collection-record.json'
        try:
            ok = collector.collect_one(plan, cfg, mode, campaign_root=campaign)
        except Exception as exc:
            ok = False
            if not record_path.is_file():
                campaign_tools.write(record_path, {
                    'status': 'failed', 'reason': f'{type(exc).__name__}: {exc}',
                    'stage_status': {'profile_eligible': False},
                })
        stage_ok, _record, archive = campaign_tools.finalize_mode(
            campaign, manifest, plan, dataset, mode, record_path, bool(ok))
        manifest['completed_modes'][-1]['indexed_file_count'] = archive.get('indexed_file_count', 0)
        if not stage_ok:
            manifest['not_started'] = [
                {'dataset': later_dataset, 'mode': later_mode,
                 'status': 'not_started',
                 'reason': 'earlier selected task or archive stage failed; strict stop policy'}
                for later_dataset, later_mode in tasks[task_index + 1:]
            ]
            campaign_tools.write(Path(campaign) / 'campaign-manifest.json', manifest)
            return False
        campaign_tools.write(Path(campaign) / 'campaign-manifest.json', manifest)
        print(f'COMPLETE {dataset} mode={mode} profile_eligible=true', flush=True)
    manifest['status'] = 'complete'
    manifest['not_started'] = []
    campaign_tools.write(Path(campaign) / 'campaign-manifest.json', manifest)
    return True


def main():
    tasks = validate_tasks()
    plan = campaign_tools.read(PLAN_PATH)
    configs = {cfg['config_id']: cfg for cfg in plan['configs']}
    if plan.get('loops') != 1:
        raise SystemExit('plan must request exactly one loop')
    for dataset, _mode in tasks:
        if dataset not in configs:
            raise SystemExit(f'missing selected dataset configuration: {dataset}')
    try:
        reused_recovery = recovery_reference()
    except Exception as exc:
        raise SystemExit(f'Retail native recovery evidence check failed: {exc}')

    actual_image_id = subprocess.check_output(
        ['docker', 'image', 'inspect', plan['image'], '--format', '{{.Id}}'], text=True
    ).strip()
    if actual_image_id != plan['image_id']:
        raise SystemExit(f'image ID mismatch: {actual_image_id} != {plan["image_id"]}')
    plan['image_id'] = actual_image_id

    token = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    campaign = campaign_tools.CAMPAIGNS / f'{token}-remaining-modes'
    campaign.mkdir(parents=True, exist_ok=False)
    manifest = {
        'schema_version': 'targeted-hotspot-selected-campaign-v1',
        'status': 'preflight_in_progress', 'run_token': token,
        'image': plan['image'], 'image_id': actual_image_id,
        'plan_path': str(PLAN_PATH), 'plan_sha256': campaign_tools.sha(PLAN_PATH),
        'scheduler_sha256': campaign_tools.sha(Path(__file__)),
        'collector_sha256': campaign_tools.sha(campaign_tools.COLLECTOR_PATH),
        'analysis_scripts_sha256': {
            name: campaign_tools.sha(HERE / 'scripts' / name) for name in (
                'collect_current_loop_profiles.py', 'collect_native.sh', 'collect_pyspy.sh',
                'run_workload.sh', 'preflight_replay.py', 'bounded_perf_export.py',
                'collection_quality.py', 'parse_native.py', 'parse_pyspy.py',
                'monitor_procs.py', 'roi_marker.py', 'tstamp_pipe.py')},
        'selected_tasks': [{'dataset': dataset, 'mode': mode, 'loops': 1}
                           for dataset, mode in tasks],
        'reused_recovery_evidence': reused_recovery,
        'host_preflight': {}, 'runtime_preflight': {}, 'completed_modes': [],
        'stop_policy': 'Any preflight, workload, sampler, parser, ROI, validation, archive, or hash failure stops all later selected tasks; no retries.',
    }
    campaign_tools.write(campaign / 'campaign-manifest.json', manifest)

    selected_datasets = list(dict.fromkeys(dataset for dataset, _ in tasks))
    try:
        collector = campaign_tools.load_collector()
        for dataset in selected_datasets:
            result = campaign_tools.host_preflight(collector, configs[dataset])
            if result.get('status') != 'success':
                raise RuntimeError(f'{dataset} host preflight failed: {result}')
            manifest['host_preflight'][dataset] = result
            campaign_tools.write(campaign / 'campaign-manifest.json', manifest)
        for dataset in selected_datasets:
            result = runtime_preflight(plan, configs[dataset], campaign, token)
            manifest['runtime_preflight'][dataset] = result
            campaign_tools.write(campaign / 'campaign-manifest.json', manifest)
    except Exception as exc:
        manifest.update(status='stopped_preflight_failure',
                        failure={'stage': 'preflight', 'error': f'{type(exc).__name__}: {exc}'},
                        not_started=[{'dataset': d, 'mode': m, 'status': 'not_started'}
                                     for d, m in tasks])
        campaign_tools.write(campaign / 'campaign-manifest.json', manifest)
        print(json.dumps(manifest['failure'], indent=2), flush=True)
        return 1

    manifest['status'] = 'in_progress'
    campaign_tools.write(campaign / 'campaign-manifest.json', manifest)
    ok = execute_tasks(plan, configs, campaign, manifest, collector=collector)
    if not ok:
        print(json.dumps({'status': manifest['status'], 'campaign': str(campaign),
                          'completed_modes': manifest['completed_modes'],
                          'not_started': manifest.get('not_started')}, indent=2), flush=True)
        return 1
    print(json.dumps({'status': manifest['status'], 'campaign': str(campaign),
                      'completed_modes': manifest['completed_modes']}, indent=2), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
