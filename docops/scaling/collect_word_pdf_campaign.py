"""Host-side formal perf+DevKit capture campaign for the four Word/PDF scale variants.

Runs 8 independent captures (4 tasks x {perf, topdown}) with the declared per-task
replay loops (003-u100=3, 003-u500=1, 037-u5=3, 037-u20=1), strictly serial, one
fresh retained offline container per capture, using the existing verified pilot /
measurement suite with the round-2 Word/PDF scaling payload selected.

This driver only collects, parses, verifies and archives; it draws no performance
conclusions. After capture it performs the offline symbol enrichment (per-file
build-id matched debug mounts + recover_perf) for each perf capture and the full
DevKit hierarchy extraction (devkit_full_extract) for each topdown capture, then
publishes a verification record, delivery notes and a final SHA256 index.

Existing 014/021 capture configuration, historical evidence and campaign dirs are
never touched.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ANALYSIS = ROOT / 'analysis' / 'docops'
TOP = ROOT / 'analysis' / 'topdown'
sys.path.insert(0, str(TOP))
sys.path.insert(0, str(ANALYSIS))
sys.path.insert(0, str(HERE))

from pilot import DOCKER, launch, sha, write  # noqa: E402
from campaign import check_archive  # noqa: E402
from quality import function_qualification  # noqa: E402
from enrich_unified import prepare_symbols  # noqa: E402
from symbol_enrich import verify_build_ids  # noqa: E402
import devkit_full_extract  # noqa: E402

IMAGE_TAG = 'docops-replay:openeuler-unified-candidate-04'
EXPECTED_IMAGE_ID = 'sha256:57483856a27942ffd4aef853950ca66b00c12b0787aae6c1dac74371d03e6164'
PAYLOAD = ROOT / 'docops/scaling/payload-word-pdf'
REPLAY_PY = ROOT / 'docops/replay.py'
COMPILE_PY = ROOT / 'docops/compile.py'
SEARCH = ROOT / 'analysis/docops/symbol-search/20261104-unified'
SOURCE_FILES = ('recover_perf.py', 'quality.py', 'native_adapter.py', 'enrich_unified.py',
                'native_profile.py', 'native_capture_helpers.py')

VARIANT_LOOPS = {'003-u100': 3, '003-u500': 1, '037-u5': 3, '037-u20': 1}
ORDER = ['003-u100', '003-u500', '037-u5', '037-u20']
WORKLOAD_TIMEOUT = 7200
STEP_TIMEOUT = 3600
HOST_TIMEOUT = 10800
SUSPECT_FLAGS = ('--structure-only', '--skip', '--fixture', '--dry-run')


def load_compile_validate():
    spec = importlib.util.spec_from_file_location('docops_compile', COMPILE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.validate_payload


def load_replay_module():
    spec = importlib.util.spec_from_file_location('docops_replay_measured', REPLAY_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tree_sha(root: Path) -> str:
    files = sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file())
    h = hashlib.sha256()
    for rel in files:
        h.update(rel.encode())
        h.update(b'\0')
        h.update((root / rel).read_bytes())
        h.update(b'\0')
    return h.hexdigest()


def host_cpu_ticks():
    ticks = {}
    for line in Path('/proc/stat').read_text().splitlines():
        parts = line.split()
        if re.fullmatch(r'cpu\d+', parts[0]) and int(parts[0][3:]) in range(10):
            ticks[parts[0]] = list(map(int, parts[1:]))
    return ticks


def host_cpu_deltas(before, after):
    out = {}
    for cpu in before:
        b, a = before[cpu], after[cpu]
        total = max(sum(a) - sum(b), 1)
        idle = a[3] - b[3]
        out[cpu] = {'total_ticks': sum(a) - sum(b), 'idle_pct': 100 * idle / total}
    return out


def recipe_input_name(task: str) -> str:
    meta = json.loads((PAYLOAD / 'tasks' / task / 'seed/root/task_metadata.json').read_text())
    return Path(meta['input_path']).name


def preflight(campaign_dir: Path) -> dict:
    result = {'status': 'running'}
    validate_payload = load_compile_validate()
    try:
        result['payload'] = validate_payload(PAYLOAD)
    except Exception as exc:
        result['payload'] = {'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'}

    index = json.loads((PAYLOAD / 'payload-index.json').read_text())['files']
    replay_mod = load_replay_module()
    binding = {}
    for task in ORDER:
        recipe = json.loads((PAYLOAD / 'tasks' / task / 'recipe.json').read_text())
        sv = recipe['synthetic_variant']
        problems = []
        for f in recipe['files']:
            if index[f['payload']]['sha256'] != f['sha256'] or index[f['payload']]['bytes'] != f['bytes']:
                problems.append(f'recipe file binding mismatch: {f["payload"]}')
        for s in recipe['steps']:
            body = (PAYLOAD / s['shell_body']).read_text()
            if body != s['argv'][2]:
                problems.append(f'shell body mismatch: {s["shell_body"]}')
            for flag in SUSPECT_FLAGS:
                if flag in s['argv'][2]:
                    problems.append(f'formal command contains {flag}')
        material = 'units.json' if task.startswith('003') else 'notices.json'
        material_sha = sha(PAYLOAD / 'tasks' / task / 'seed/root/tmp/docs' / material)
        scoped = replay_mod.task_scoped_paths(recipe)
        # /results overlap can only be asserted inside the image (abs_path resolves
        # against /root); string-level guard here, hard guarantee by replay check_layout
        # which runs before every round and aborts the run on overlap.
        reset_overlap = [p for p in scoped
                         if p == '/results' or p.startswith('/results') or p.startswith('/results/')]
        binding[task] = {
            'ok': not problems and not reset_overlap,
            'problems': problems,
            'reset_overlap_results': reset_overlap,
            'recipe_sha256': sha(PAYLOAD / 'tasks' / task / 'recipe.json'),
            'input_sha256': sv['input_sha256'],
            'expected_sha256': sv['expected_sha256'],
            f'{material}_sha256': material_sha,
            'steps': [s['name'] for s in recipe['steps']],
        }
    result['binding'] = binding
    result['binding_all_ok'] = all(b['ok'] for b in binding.values())

    word_validator = sha(PAYLOAD / 'tasks/003-u100/seed/root/tmp/docs/validate_public_packet_variant.py')
    word_source = sha(ROOT / 'docops/scaling/cases/003/scripts/validate_public_packet_variant.py')
    word_copy2 = sha(PAYLOAD / 'tasks/003-u500/seed/root/tmp/docs/validate_public_packet_variant.py')
    pdf_validator = sha(PAYLOAD / 'tasks/037-u5/seed/root/tmp/docs/validate_bus_detour_packet_variant.py')
    pdf_source = sha(ROOT / 'docops/scaling/cases/037/scripts/validate_bus_detour_packet_variant.py')
    pdf_copy2 = sha(PAYLOAD / 'tasks/037-u20/seed/root/tmp/docs/validate_bus_detour_packet_variant.py')
    result['verifier_consistency'] = {
        'word': {'source': word_source, 'u100_payload': word_validator,
                 'u500_payload': word_copy2,
                 'all_equal': word_source == word_validator == word_copy2},
        'pdf': {'source': pdf_source, 'u5_payload': pdf_validator,
                'u20_payload': pdf_copy2,
                'all_equal': pdf_source == pdf_validator == pdf_copy2},
    }

    image = json.loads(subprocess.check_output(DOCKER + ['image', 'inspect', IMAGE_TAG], text=True))[0]
    result['image_tag'] = IMAGE_TAG
    result['image_id'] = image['Id']
    result['image_id_matches_expected'] = image['Id'] == EXPECTED_IMAGE_ID

    # in-container validate-only --env-check with the exact mounts
    probe_argv = ['/opt/docops/venv/bin/python3', '-B', '/opt/docops/replay.py', 'validate-only',
                  '--payload', '/opt/docops/scaling/payload', '--env-check',
                  '--workdir', '/workspace/docops/work']
    name = 'docops-wp-perf-precheck-' + campaign_dir.name.lower()
    existing = subprocess.check_output(DOCKER + ['ps', '-aq', '--filter', f'name=^{name}$'],
                                       text=True).splitlines()
    for cid in existing:
        subprocess.run(DOCKER + ['rm', '-f', cid], capture_output=True)
    cid = subprocess.check_output(
        DOCKER + ['create', '--name', name, '--network', 'none',
                  '-v', str(PAYLOAD) + ':/opt/docops/scaling/payload:ro',
                  '-v', str(REPLAY_PY) + ':/opt/docops/replay.py:ro',
                  '-v', str(COMPILE_PY) + ':/opt/docops/compile.py:ro',
                  '-v', str(campaign_dir / 'precheck-results') + ':/results',
                  '--entrypoint', probe_argv[0], image['Id'], *probe_argv[1:]], text=True).strip()
    result['precheck_container'] = cid
    log_path = campaign_dir / 'precheck-container.log'
    with log_path.open('w') as log:
        cp = subprocess.run(DOCKER + ['start', '-a', cid], stdout=log,
                            stderr=subprocess.STDOUT, timeout=HOST_TIMEOUT)
    result['precheck_rc'] = cp.returncode
    raw = log_path.read_text()
    result['precheck_stdout'] = raw[-4000:]
    try:
        parsed = json.loads(raw[raw.index('{'):raw.rindex('}') + 1])
        result['precheck'] = parsed
        result['precheck_env_errors'] = parsed.get('environment_errors', [])
        result['precheck_payload_status'] = parsed.get('payload', {}).get('status')
        plan = parsed.get('plan', {})
        result['precheck_plan_tasks'] = sorted(plan) if isinstance(plan, dict) else []
        env = parsed.get('environment', {})
        result['precheck_environment'] = {
            'python': env.get('python', {}).get('version'),
            'python_prefix': env.get('python', {}).get('prefix'),
            'payload_kind': env.get('payload_kind'),
            'payload_declared_tasks': env.get('payload_declared_tasks'),
            'payload_tasks': env.get('payload_tasks'),
        }
    except Exception as exc:
        result['precheck'] = {'parse_error': f'{type(exc).__name__}: {exc}'}
        result['precheck_env_errors'] = ['unparseable']
        result['precheck_plan_tasks'] = []
    result['payload_index_sha256'] = sha(PAYLOAD / 'payload-index.json')
    result['symbol_search_sha256'] = sha(SEARCH / 'search-results.json')
    result['frozen_before'] = {
        'official_payload_tree': tree_sha(ROOT / 'docops/payload'),
        'round1_payload_tree': tree_sha(ROOT / 'docops/scaling/payload'),
        'official_catalog': sha(ROOT / 'docops/payload/catalog.json'),
        'official_index': sha(ROOT / 'docops/payload/payload-index.json'),
        'round1_index': sha(ROOT / 'docops/scaling/payload/payload-index.json'),
    }
    result['status'] = 'passed' if (
        result.get('payload', {}).get('status') == 'static_valid'
        and result['binding_all_ok']
        and result['verifier_consistency']['word']['all_equal']
        and result['verifier_consistency']['pdf']['all_equal']
        and result['image_id_matches_expected']
        and result.get('precheck_rc') == 0
        and result.get('precheck_env_errors') == []
        and result.get('precheck_plan_tasks') == sorted(ORDER)
    ) else 'failed'
    return result


def copy_sources(campaign_dir: Path) -> dict:
    """Idempotent analyst-source staging (resume-safe)."""
    src = campaign_dir / 'source'
    src.mkdir(parents=True, exist_ok=True)
    for name in ('recover_perf.py', 'quality.py', 'native_adapter.py', 'enrich_unified.py'):
        shutil.copy2(ANALYSIS / name, src / name)
    shutil.copy2(ROOT / 'analysis/hotspots/native_profile.py', src / 'native_profile.py')
    shutil.copy2(ROOT / 'analysis/hotspots/collect_native.py', src / 'native_capture_helpers.py')
    return {p.name: sha(p) for p in src.iterdir()}


def prepare_symbols_dir(destination: Path) -> dict:
    """Copy build-id matched debug files into destination; verify sha + build-id."""
    if not destination.is_dir():
        destination.mkdir(parents=True)
    rows = prepare_symbols(SEARCH, destination)
    arch_ok = True
    checked = []
    for row in rows:
        source = destination / row['path']
        notes = subprocess.check_output(['readelf', '-h', str(source)], text=True)
        machine = [l for l in notes.splitlines() if 'Machine:' in l]
        is_aarch64 = any('AArch64' in l for l in machine)
        arch_ok = arch_ok and is_aarch64
        checked.append({'path': row['path'], 'build_id': row['build_id'],
                        'runtime_path': row['runtime_path'], 'sha256': row['sha256'],
                        'bytes': row['bytes'], 'aarch64': is_aarch64,
                        'machine_lines': machine})
    return {'rows': rows, 'arch_all_aarch64': arch_ok, 'checked': checked}


def capture_one(task: str, mode: str, campaign_dir: Path, state: dict) -> dict:
    loops = VARIANT_LOOPS[task]
    record = launch(task, loops, [mode], return_record=True,
                    payload=PAYLOAD, campaign_dir=campaign_dir,
                    workload_timeout=WORKLOAD_TIMEOUT, step_timeout=STEP_TIMEOUT,
                    host_timeout=HOST_TIMEOUT)
    row = {'status': record.get('status'), 'raw': record.get('raw'),
           'error': record.get('error'), 'modes': record.get('modes', {}).get(mode, {}),
           'loops': loops}
    return row


def enrich_perf(task: str, campaign_dir: Path, state: dict, rows: list, source_sha: dict,
                reuse_existing: bool = True) -> dict:
    """Offline per-file symbol enrichment for the given perf capture."""
    raw_dir = ROOT / state['tasks'][task]['perf']['raw']
    original = raw_dir / 'perf' / 'out'
    if not (original / 'perf.data').is_file():
        raise ValueError(f'{task} perf.data missing')
    original_archive = check_archive(original)
    baseline_profile = json.loads((original / 'profile.json').read_text())
    symbols = campaign_dir / 'symbols'
    builds_check = verify_build_ids(original, rows)
    base = campaign_dir / (task + '-enrich')
    folder = base
    if base.exists():
        record_path = base / 'out' / 'recovery-record.json'
        if reuse_existing and record_path.is_file():
            existing = json.loads(record_path.read_text())
            if existing.get('status') == 'passed' and existing.get('original_evidence_unchanged'):
                return enrich_result(task, folder, original_archive, baseline_profile, builds_check,
                                     source_sha, reused=True)
        number = 2
        while (campaign_dir / f'{task}-enrich-r{number}').exists():
            number += 1
        folder = campaign_dir / f'{task}-enrich-r{number}'
    out = folder / 'out'
    folder.mkdir(parents=True, exist_ok=False)
    out.mkdir()
    argv = DOCKER + ['create', '--name', f'docops-enrich-{task}-{folder.name.lower()}',
                     '--network', 'none', '--cpuset-cpus', '9',
                     '--mount', f'type=bind,source={original},target=/original,readonly',
                     '--mount', f'type=bind,source={campaign_dir/"source"},target=/opt/docops-measurement,readonly',
                     '--mount', f'type=bind,source={symbols},target=/analysis-symbols,readonly',
                     '--mount', f'type=bind,source={out},target=/results']
    for row in rows:
        argv += ['--mount', f"type=bind,source={symbols / row['path']},target=/usr/lib/debug/{row['path']},readonly"]
    argv += ['--entrypoint', 'python3', state['preflight']['image_id'], '-B',
             '/opt/docops-measurement/recover_perf.py', '--allow-limited',
             '--symbols', '/analysis-symbols']
    cid = subprocess.check_output(argv, text=True, timeout=60).strip()
    before = json.loads(subprocess.check_output(DOCKER + ['inspect', cid], text=True))[0]
    write(folder / 'container-before.json', before)
    if before['Image'] != state['preflight']['image_id'] or before['HostConfig']['NetworkMode'] != 'none':
        raise ValueError('wrong offline image/network')
    if any(m['RW'] for m in before['Mounts'] if m['Destination'] != '/results'):
        raise ValueError('writable offline input')
    print('OFFLINE EXPORT ' + task, flush=True)
    with (folder / 'container.log').open('x') as log:
        try:
            cp = subprocess.run(DOCKER + ['start', '-a', cid], stdout=log,
                                stderr=subprocess.STDOUT, timeout=1800)
        except BaseException:
            subprocess.run(DOCKER + ['stop', '-t', '3', cid], capture_output=True, timeout=15)
            raise
    after = json.loads(subprocess.check_output(DOCKER + ['inspect', cid], text=True))[0]
    write(folder / 'container-after.json', after)
    value = json.loads((out / 'recovery-record.json').read_text())
    if cp.returncode or after['State']['ExitCode'] or value['status'] != 'passed':
        raise RuntimeError(f'offline export failed: {task} {value.get("error")}')
    if not value['original_evidence_unchanged']:
        raise ValueError('original evidence changed')
    return enrich_result(task, folder, original_archive, baseline_profile, builds_check, source_sha,
                         cid=cid)


def enrich_result(task: str, folder: Path, original_archive: dict, baseline_profile: dict,
                  builds_check: dict, source_sha: dict, cid: str | None = None,
                  reused: bool = False) -> dict:
    out = folder / 'out'
    value = json.loads((out / 'recovery-record.json').read_text())
    enriched = json.loads((out / 'profile.json').read_text())
    before_totals = collections.Counter()
    for f in baseline_profile['functions']:
        before_totals[f['dso']] += f['period']
    after_totals = collections.Counter()
    for f in enriched['functions']:
        after_totals[f['dso']] += f['period']
    if dict(before_totals) != dict(after_totals):
        raise ValueError('DSO period accounting changed: ' + task)
    unknown_before = [f for f in baseline_profile['functions']
                      if f.get('function') in ('[unknown]', None)]
    unknown_after = [f for f in enriched['functions']
                     if f.get('function') in ('[unknown]', None)]
    dso_improve = collections.defaultdict(dict)
    for f in unknown_before:
        dso_improve[f['dso']]['before_period'] = f['period']
    for f in unknown_after:
        dso_improve[f['dso']]['after_period'] = f['period']
    return {
        'status': value['status'], 'out': str(out.relative_to(ROOT)),
        'container_id': cid, 'reused': reused, 'original_archive': original_archive,
        'builds_check': builds_check,
        'source_sha256': source_sha,
        'record_sha256': sha(out / 'recovery-record.json'),
        'quality_before': value['quality_before'], 'quality_after': value['quality_after'],
        'function_qualification': value['function_qualification'],
        'roi_samples': value['roi_samples'], 'roi_period': value['roi_period'],
        'unknown_leaf_share_before': value['quality_before']['unknown_leaf_symbol_share'],
        'unknown_leaf_share_after': value['quality_after']['unknown_leaf_symbol_share'],
        'dso_unknown_improvement': {d: dict(x) for d, x in dso_improve.items()},
        'archive': check_archive(out), 'profile_sha256': sha(out / 'profile.json'),
    }


def topdown_extract(task: str, campaign_dir: Path, state: dict) -> dict:
    raw_dir = ROOT / state['tasks'][task]['topdown']['raw']
    out = raw_dir / 'topdown' / 'out'
    stdout_txt = out / 'devkit.stdout.txt'
    folder = campaign_dir / (task + '-topdown-extract')
    target = folder / 'full-extract.json'
    reused = False
    if not (folder.is_dir() and target.is_file()):
        number = 2
        while (campaign_dir / f'{task}-topdown-extract-r{number}').exists():
            number += 1
        folder = campaign_dir / f'{task}-topdown-extract-r{number}'
        folder.mkdir(exist_ok=False)
        target = folder / 'full-extract.json'
        devkit_full_extract.main([str(stdout_txt), '--output', str(target)])
    else:
        reused = True
    parsed = json.loads(target.read_text())
    final = parsed['final']
    nodes = {n['path']: n['value_pct'] for n in final['hierarchy']}
    return {'rc': 0 if not reused else None, 'reused': reused,
            'file': str(target.relative_to(ROOT)),
            'timesteps': len(parsed['timesteps']),
            'final_hierarchy_nodes': len(final['hierarchy']),
            'final_top_nodes': [n['name'] for n in final['hierarchy'] if n['depth'] == 0],
            'final_pmu_events': len(final['pmu_events']),
            'final_header': final['header'],
            'final_metrics': {
                'IPC': final['header'].get('IPC'),
                'Frontend Bound': nodes.get('Frontend Bound'),
                'Backend Bound': nodes.get('Backend Bound'),
                'Core Bound': nodes.get('Backend Bound/Core Bound'),
                'Memory Bound': nodes.get('Backend Bound/Memory Bound'),
                'Retiring': nodes.get('Retiring'),
                'Bad Speculation': nodes.get('Bad Speculation'),
                'Fetch Latency Bound': nodes.get('Frontend Bound/Fetch Latency Bound'),
                'Fetch Bandwidth Bound': nodes.get('Frontend Bound/Fetch Bandwidth Bound'),
            },
            'not_counted_markers': parsed['not_counted_markers'],
            'sha256': sha(target)}


def verify_capture(task: str, mode: str, campaign_dir: Path, state: dict) -> dict:
    row = state['tasks'][task][mode]
    raw_dir = ROOT / row['raw']
    out = raw_dir / mode / 'out'
    collection = json.loads((out / 'collection.json').read_text())
    if collection['status'] != 'passed':
        raise ValueError(f'{task} {mode} collection not passed')
    expected = dict(requested=VARIANT_LOOPS[task], completed=VARIANT_LOOPS[task],
                    successes=VARIANT_LOOPS[task], failures=0)
    if collection['counts'] != expected:
        raise ValueError(f'{task} {mode} loop counts mismatch: {collection["counts"]}')
    archive = check_archive(out)
    v = {'task': task, 'mode': mode, 'status': 'passed',
         'raw': str(raw_dir.relative_to(ROOT)), 'counts': collection['counts'],
         'roi_seconds': collection['roi_seconds'],
         'roi_intervals_ns': collection.get('roi_intervals_ns'),
         'workflow_status': collection['workflow_status'],
         'archive': archive, 'container_id': row['modes'].get('container_id'),
         'container_exit_code': row['modes'].get('container_exit_code'),
         'docker_returncode': row['modes'].get('docker_returncode'),
         'collection_sha256': sha(out / 'collection.json')}
    if mode == 'perf':
        profile = json.loads((out / 'profile.json').read_text())
        cq = profile['capture_quality']
        v.update({
            'record_returncode': collection.get('record_returncode'),
            'roi_samples': profile['roi_samples'], 'roi_period': profile['roi_period'],
            'all_recorded_samples': profile['all_recorded_samples'],
            'all_recorded_period': profile['all_recorded_period'],
            'excluded_period': profile['excluded_period'],
            'sample_crosscheck': collection.get('sample_crosscheck'),
            'loss_diagnostics': cq,
            'perf_data_bytes': (out / 'perf.data').stat().st_size,
            'function_qualification': collection.get('function_qualification'),
            'quality': profile['quality'],
            'profile_sha256': sha(out / 'profile.json'),
            'requested_freq_hz': 49,
            'actual_sample_rate_per_cpu_hz': (profile['roi_samples'] / collection['roi_seconds']) / 8,
        })
    else:
        summary = json.loads((out / 'topdown-summary.json').read_text())
        v.update({
            'profiler_returncode': collection.get('profiler_returncode'),
            'profiler_envelope_seconds': collection.get('profiler_envelope_seconds'),
            'outside_workflow_envelope_seconds': collection.get('outside_workflow_envelope_seconds'),
            'cpu_window': collection.get('cpu_window'),
            'profiler_affinity': collection.get('profiler_affinity'),
            'metrics': summary.get('metrics'),
            'topdown_summary_sha256': sha(out / 'topdown-summary.json'),
            'exact_roi_event_filtering': False,
        })
    return v


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign-dir', required=True, type=Path)
    parser.add_argument('--preflight-only', action='store_true',
                        help='stop after preflight (no capture)')
    parser.add_argument('--resume', action='store_true',
                        help='continue an existing campaign whose 8 captures all passed; '
                             'reuse captures and any valid enrichment, never recapture')
    args = parser.parse_args(argv)
    campaign = args.campaign_dir.resolve()
    if args.resume:
        if not (campaign / 'campaign.json').is_file():
            raise ValueError('no campaign to resume: ' + str(campaign))
        state = json.loads((campaign / 'campaign.json').read_text())
        if state.get('preflight', {}).get('status') != 'passed':
            raise ValueError('cannot resume: preflight not passed')
        missing = [(t, m) for t in ORDER for m in ('perf', 'topdown')
                   if state.get('tasks', {}).get(t, {}).get(m, {}).get('status') != 'passed']
        if missing:
            raise ValueError(f'cannot resume: captures not all passed: {missing}')
        state['status'] = 'running'
        state.pop('error', None)
        state.pop('traceback', None)
        state.pop('stopped_at', None)
        state['resume_count'] = state.get('resume_count', 0) + 1
        state['driver_sha256'] = sha(Path(__file__).resolve())
        write(campaign / 'campaign.json', state)
    else:
        if campaign.exists():
            raise ValueError('refusing to reuse existing campaign: ' + str(campaign))
        campaign.mkdir(parents=True)
        created = datetime.datetime.now(datetime.timezone.utc).isoformat()
        state = dict(schema='docops-scaling-word-pdf-performance-v1', status='preflight',
                     created_utc=created, image_tag=IMAGE_TAG, image_id=EXPECTED_IMAGE_ID,
                     variants=ORDER, loops_per_variant=VARIANT_LOOPS, captures_planned=8,
                     tasks={}, payload=str(PAYLOAD), driver_sha256=sha(Path(__file__).resolve()),
                     campaign_rel=str(campaign.relative_to(ROOT)))
        state['preflight'] = preflight(campaign)
        write(campaign / 'campaign.json', state)
        if state['preflight']['status'] != 'passed':
            state['status'] = 'failed'
            write(campaign / 'campaign.json', state)
            print(json.dumps({'status': state['status'], 'preflight': state['preflight']},
                             ensure_ascii=False), flush=True)
            return 1
        if args.preflight_only:
            state['status'] = 'preflight_passed_not_run'
            write(campaign / 'campaign.json', state)
            print(json.dumps({'status': 'preflight_passed', 'campaign': str(campaign)},
                             ensure_ascii=False), flush=True)
            return 0
        state['status'] = 'running'
        write(campaign / 'campaign.json', state)

    try:
        if args.resume:
            host_before = host_cpu_ticks()  # post-processing span only
        else:
            host_before = host_cpu_ticks()
        # one-time symbol staging + source staging (shared by all perf captures)
        symbols = prepare_symbols_dir(campaign / 'symbols')
        rows = symbols['rows']
        state['symbol_staging'] = {
            'rows': len(rows),
            'arch_all_aarch64': symbols['arch_all_aarch64'],
            'index_sha256': sha(campaign / 'symbols/index.json'),
            'search_record_sha256': state['preflight']['symbol_search_sha256'],
        }
        source_sha = copy_sources(campaign)
        state['measurement_source_sha256'] = source_sha
        write(campaign / 'campaign.json', state)
        if not args.resume:
            for task in ORDER:
                state['tasks'][task] = {}
                for mode in ('perf', 'topdown'):
                    state['active'] = {'variant': task, 'mode': mode}
                    write(campaign / 'campaign.json', state)
                    print(f'CAPTURE START {task} {mode} loops={VARIANT_LOOPS[task]}', flush=True)
                    row = capture_one(task, mode, campaign, state)
                    state['tasks'][task][mode] = row
                    state['active'] = None
                    write(campaign / 'campaign.json', state)
                    print(f'CAPTURE END {task} {mode} status={row["status"]}', flush=True)
                    if row['status'] != 'passed':
                        state['status'] = 'failed'
                        state['stopped_at'] = (task, mode)
                        raise RuntimeError(f'capture failed: {task} {mode}')
        host_after = host_cpu_ticks()
        if not args.resume:
            state['host_cpu_deltas_capture_span'] = host_cpu_deltas(host_before, host_after)
        state['host_interference_note'] = (
            'Host per-CPU idle% over the capture span on CPUs 0-9; '
            'diagnostic only, other project processes were not stopped.')
        write(campaign / 'campaign.json', state)

        # verification of the raw captures
        verification = {'schema': 'docops-scaling-word-pdf-performance-verification-v1',
                        'campaign': str(campaign.relative_to(ROOT)),
                        'payload_index_sha256': state['preflight']['payload_index_sha256'],
                        'variants': {}, 'captures': {}, 'enrichment': {}, 'topdown_extract': {}}
        for task in ORDER:
            for mode in ('perf', 'topdown'):
                verification['captures'][f'{task}-{mode}'] = verify_capture(task, mode, campaign, state)
            verification['variants'][task] = {
                'recipe_sha256': state['preflight']['binding'][task]['recipe_sha256'],
                'input_sha256': state['preflight']['binding'][task]['input_sha256'],
                'expected_sha256': state['preflight']['binding'][task]['expected_sha256'],
                'loops': VARIANT_LOOPS[task],
            }
            # offline symbol enrichment
            print('ENRICH ' + task, flush=True)
            verification['enrichment'][task] = enrich_perf(task, campaign, state, rows, source_sha)
            # full DevKit hierarchy extraction
            print('TOPDOWN EXTRACT ' + task, flush=True)
            verification['topdown_extract'][task] = topdown_extract(task, campaign, state)
        verification['host_cpu_deltas_capture_span'] = state['host_cpu_deltas_capture_span']
        write(campaign / 'verification.json', verification)
        state['verification_sha256'] = sha(campaign / 'verification.json')
        state['status'] = 'passed'
        state['active'] = None
    except BaseException as exc:
        state.update(status='failed', error=f'{type(exc).__name__}: {exc}',
                     traceback=traceback.format_exc())
    finally:
        state['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        state['frozen_after'] = {
            'official_payload_tree': tree_sha(ROOT / 'docops/payload'),
            'round1_payload_tree': tree_sha(ROOT / 'docops/scaling/payload'),
            'official_catalog': sha(ROOT / 'docops/payload/catalog.json'),
            'official_index': sha(ROOT / 'docops/payload/payload-index.json'),
            'round1_index': sha(ROOT / 'docops/scaling/payload/payload-index.json'),
        }
        write(campaign / 'campaign.json', state)
        # delivery notes and final index only when the campaign completed
        if state['status'] == 'passed' and (campaign / 'verification.json').is_file():
            write_delivery(campaign, state, verification)
            final_index_and_readback(campaign, state)
    print(json.dumps({'status': state['status'], 'campaign': str(campaign),
                      'error': state.get('error'), 'stopped_at': state.get('stopped_at')},
                     ensure_ascii=False), flush=True)
    return 0 if state['status'] == 'passed' else 1


def _sha_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def final_index_and_readback(campaign: Path, state: dict):
    """SHA256 index over campaign-managed evidence (capture dirs keep their own
    immutable per-capture index); then read back every indexed file."""
    files = {}
    for p in sorted(campaign.rglob('*')):
        if not p.is_file():
            continue
        rel = p.relative_to(campaign)
        parts = rel.parts
        # capture mode out dirs keep their own immutable per-capture index
        capture_out = (len(parts) >= 4 and 'chain-pilot' in parts[0]
                       and parts[1] in ('perf', 'topdown') and parts[2] == 'out')
        if capture_out or rel.name == 'campaign.sha256-index.json':
            continue
        files[rel.as_posix()] = {'bytes': p.stat().st_size, 'sha256': _sha_of(p)}
    path = campaign / 'campaign.sha256-index.json'
    path.write_text(json.dumps({'schema': 'docops-scaling-word-pdf-performance-index-v1',
                                'files': files}, ensure_ascii=False, indent=2) + '\n')
    entry = json.loads(path.read_text())
    for rel, row in entry['files'].items():
        p = (campaign / rel).resolve()
        if not p.is_relative_to(campaign.resolve()):
            raise ValueError('indexed path escapes campaign')
        if p.stat().st_size != row['bytes'] or _sha_of(p) != row['sha256']:
            raise ValueError('index readback mismatch: ' + rel)
    state['final_index'] = {'path': str(path.relative_to(ROOT)),
                            'files_indexed': len(entry['files']),
                            'full_readback_passed': True}
    write(campaign / 'campaign.json', state)


def write_delivery(campaign: Path, state: dict, verification: dict):
    lines = ['# DocOps Word/PDF 规模变体 perf + DevKit 采集（本轮仅采集/解析/核验/归档）', '',
             f'- campaign: `{state["campaign_rel"] if "campaign_rel" in state else str(campaign.relative_to(ROOT))}`',
             f'- 镜像: `{IMAGE_TAG}` = `{EXPECTED_IMAGE_ID}`',
             f'- payload: `docops/scaling/payload-word-pdf/`（kind=scaling，四任务）',
             f'- 每份采集独立新容器，network=none，结束后保留停止容器，不重启旧容器',
             f'- 请求频率: perf `cycles:u -F 49 -k mono --call-graph dwarf,16384`；DevKit `-c 0-7 -L 0 -i 1 -l 0`',
             '', '## 结果表', '',
             '| 任务 | 采集 | 回放轮数 | 完成/成功/失败 | workflow(s) | 采集包络(s) | 请求频率 | 实际采样/CPU/s | native样本 | ROI period | 补前未知叶% | 补后未知叶% | 丢样 | 归档 |',
             '|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|']
    for task in ORDER:
        v = verification['variants'][task]
        for mode in ('perf', 'topdown'):
            c = verification['captures'][f'{task}-{mode}']
            if mode == 'perf':
                cq = c['loss_diagnostics']
                lost = f"chunks={cq.get('perf_record_reported_lost_chunks')}, lost_records={cq.get('reported_lost_records')}"
                e = verification['enrichment'][task]
                lines.append(f"| {task} | perf | {v['loops']} | {c['counts']['completed']}/{c['counts']['successes']}/0 | "
                             f"{c['roi_seconds']:.2f} | — | 49 | {c['actual_sample_rate_per_cpu_hz']:.2f} | "
                             f"{c['roi_samples']} | {c['roi_period']} | {100*e['unknown_leaf_share_before']:.3f}% | "
                             f"{100*e['unknown_leaf_share_after']:.3f}% | {lost} | {c['archive']['files_verified']} |")
            else:
                t = verification['topdown_extract'][task]
                env = c.get('profiler_envelope_seconds')
                lines.append(f"| {task} | topdown | {v['loops']} | {c['counts']['completed']}/{c['counts']['successes']}/0 | "
                             f"{c['roi_seconds']:.2f} | {env:.2f} | — | — | — | — | — | — | — | {c['archive']['files_verified']} |")
    lines += ['', '## DevKit Topdown（ALL 累计口径）', '',
              '| 任务 | 过程点数(timesteps) | IPC | Frontend | Backend | Core | Memory | Retiring | Bad Spec | 未计数标记 | 有效性限制 |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|']
    for task in ORDER:
        c = verification['captures'][f'{task}-topdown']
        t = verification['topdown_extract'][task]
        m = t['final_metrics']
        nc = ','.join(t['not_counted_markers']) if t['not_counted_markers'] else '无'
        limit = 'CPU包络含初始读数/步间与轮间间隙/尾部；无精确PID裁剪；ALL为累计口径'
        def pct(x):
            return '—' if x is None else f'{x:.2f}'
        lines.append(f"| {task} | {t['timesteps']} | {m.get('IPC')} | {pct(m.get('Frontend Bound'))} | {pct(m.get('Backend Bound'))} | "
                     f"{pct(m.get('Core Bound'))} | {pct(m.get('Memory Bound'))} | {pct(m.get('Retiring'))} | {pct(m.get('Bad Speculation'))} | "
                     f"{nc} | {limit} |")
    lines += ['', '## 符号与函数资格（补符号后）', '',
              '| 任务 | 补前未知叶% | 补后未知叶% | 函数资格 | 剩余未知归属 |',
              '|---|---:|---:|---|---|']
    for task in ORDER:
        e = verification['enrichment'][task]
        remaining = [kv for kv in e['dso_unknown_improvement'].items() if 'after_period' in kv[1]]
        unk = sorted(remaining, key=lambda kv: kv[1]['after_period'], reverse=True)[:3]
        rest = '；'.join(f"{d}:after={x['after_period']}" for d, x in unk)
        lines.append(f"| {task} | {100*e['unknown_leaf_share_before']:.3f}% | {100*e['unknown_leaf_share_after']:.3f}% | "
                     f"{e['function_qualification']['status']} | {rest or '无'} |")
    lines += ['', '## 容器身份（每份采集独立新容器，network=none，保留停止，不重启）', '',
              '| 任务 | 采集 | 容器 ID | cpuset | 退出码 | DevKit 控制 affinity |',
              '|---|---:|---|---:|---:|---:|']
    for task in ORDER:
        for mode in ('perf', 'topdown'):
            cap = verification['captures'][f'{task}-{mode}']
            cid = cap.get('container_id', '—') or '—'
            aff = cap.get('profiler_affinity', '—')
            lines.append(f"| {task} | {mode} | {cid[:12]}… | 0-9 | {cap.get('container_exit_code')} | {aff} |")
    lines += ['', '## 修复 / 恢复 / 重试记录', '',
              '- 驱动开发阶段修复：`campaign_dir` 变量误写（符号暂存阶段 NameError）；`copy_sources` 目标目录两级嵌套；`preflight` 使用 `check_output(...).stdout` 取错返回值。均属采集接线小修，不影响业务脚本/输入/expected。',
              '- 首次正式运行：8 份采集全部 passed；离线补符号阶段因驱动 DSO 守恒校验误写为函数计数而非 period 求和而中断（仅影响校验，不重跑任何采集）。修复后以 `--resume` 复用已通过采集与有效补符号结果完成解析、核验与归档；失败尝试 `scaling-word-pdf-performance-20261105T170412Z-fd0e085c` 与 `20261105T170439Z-f51a5621` 及本 campaign 内 `resume_count` 均如实保留。',
              '- 补符号复用：`003-u100-enrich` 复用首次失败尝试中已通过的原证据核验与 recovery-record（`reused=true`），其余三任务为独立新 attempt。',
              '', '## 采集与核验事实', '',
              '- 每份采集：collector/导出/parser 退出状态、workflow 与循环内业务验证记录在各自 `collection.json` / `run.json`。',
              '- 符号：逐文件 build-id/SHA256/AArch64 核对后只读挂载至 `/usr/lib/debug/.build-id/...`；不覆盖镜像已有调试目录；原始捕获未修改。',
              '- 未解析叶比例分母为 workflow ROI 完整 cycles:u period；未知项保留，不强制置为 passed。',
              '- 丢样：记录数、事件报告丢样数与 lost chunks 分别保存，不折算、不补 period。',
              '- 索引：每份采集内部 `sha256-index.json` 已全量回读；campaign 顶层另生成 `campaign.sha256-index.json` 并全量回读，索引后不再修改被索引文件。',
              '', '## 证据入口', '',
              '- `campaign.json`：campaign 清单（含 preflight、每份采集、修复/恢复/重试记录、frozen_after）',
              '- `verification.json`：逐任务逐模式核验、补符号前后对比、Topdown 全层级提取、host CPU 干扰盘点',
              '- `precheck-container.log`：容器内 `validate-only --env-check` 原始输出',
              '- `*.chain-pilot-*/perf/out/` 与 `*.chain-pilot-*/topdown/out/`：perf.data、完整 samples、counter-only、perf report、buildids、stderr、ROI、profile、质量统计',
              '- `*-enrich/out/`：补符号后 profile / recovery-record',
              '- `*-topdown-extract/full-extract.json`：DevKit 全层级指标与 PMU 事件',
              '- `symbols/index.json`：匹配符号清单（build-id / SHA256）', '']
    (campaign / 'delivery.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
