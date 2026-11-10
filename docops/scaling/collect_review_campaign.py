"""Host-side formal perf+DevKit capture campaign for the sixteen remaining scale variants.

Runs 32 independent captures (16 tasks x {perf, topdown}), loops=1 each, strictly
serial, one fresh retained offline container per capture, using the reviewed
image with its INSTALLED unified 24-variant scaling payload. Business payload,
replay.py and compile.py come from the image; only the measurement code is
mounted read-only.

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
from contextlib import contextmanager
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ANALYSIS = ROOT / 'analysis' / 'docops'
TOP = ROOT / 'analysis' / 'topdown'
sys.path.insert(0, str(TOP))
sys.path.insert(0, str(ANALYSIS))
sys.path.insert(0, str(HERE))

from pilot import DOCKER, launch, sha, write  # noqa: E402
from prepare import PARENT_CONFIG  # noqa: E402
from campaign import check_archive  # noqa: E402
from quality import function_qualification  # noqa: E402
from enrich_unified import prepare_symbols  # noqa: E402
from symbol_enrich import verify_build_ids  # noqa: E402
import devkit_full_extract  # noqa: E402
from review_campaign_summary import historical_reuse, dataset_inventory  # noqa: E402

IMAGE_TAG = 'docops-replay:openeuler-scaled-reviewed'
EXPECTED_IMAGE_ID = 'sha256:9ae9d418980ab88a305eb37fc2399edadea129a70d803cdbc642357daa56f7d6'
PAYLOAD = ROOT / 'docops/scaling/payload-all'
INSTALLED_PAYLOAD = '/opt/docops/scaling/payload-all'
REPLAY_PY = ROOT / 'docops/replay.py'
COMPILE_PY = ROOT / 'docops/compile.py'
SEARCH = ROOT / 'analysis/docops/symbol-search/20261104-unified'
SOURCE_FILES = ('recover_perf.py', 'quality.py', 'native_adapter.py', 'enrich_unified.py',
                'native_profile.py', 'native_capture_helpers.py')

ORDER = ['016-u100','001-u100','001-u500','009-u100','009-u500','013-v100','013-v1000',
        '016-u500','026-u5','026-u10','029-u5','029-u10',
        '031-u5','031-u20','pdfwf005-u5','pdfwf005-u20']
VARIANT_LOOPS = {t: 1 for t in ORDER}

WORKLOAD_TIMEOUT = 7200
STEP_TIMEOUT = 3600
HOST_TIMEOUT = 10800
SUSPECT_FLAGS = ('--structure-only', '--skip', '--fixture', '--dry-run')


class CampaignBusy(RuntimeError):
    pass


@contextmanager
def campaign_lock(campaign):
    """One live controller per campaign, including direct Python invocations.

    Never unlink the lock file: replacing its inode would allow two owners.
    The descriptor is non-inheritable, so workload descendants cannot retain it.
    """
    fd = os.open(Path(campaign) / '.collector.lock', os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CampaignBusy('campaign already has a running collector; not starting another') from exc
        os.ftruncate(fd, 0)
        os.write(fd, (str(os.getpid()) + '\n').encode())
        yield
    finally:
        os.close(fd)


def protected_snapshot():
    return {
        'official_payload_tree': tree_sha(ROOT / 'docops/payload'),
        'round1_payload_tree': tree_sha(ROOT / 'docops/scaling/payload'),
        'round2_payload_tree': tree_sha(ROOT / 'docops/scaling/payload-word-pdf'),
        **{name + '_index': sha(ROOT / path / 'payload-index.json') for name, path in (
            ('official', 'docops/payload'), ('round1', 'docops/scaling/payload'),
            ('round2', 'docops/scaling/payload-word-pdf'))},
        'official_catalog': sha(ROOT / 'docops/payload/catalog.json'),
    }


def validate_resume(campaign, state):
    """Read-only checks before reusing passed captures; never recapture a bad archive."""
    if state.get('preflight', {}).get('status') != 'passed':
        raise ValueError('cannot resume: preflight not passed')
    if state.get('image_id') != EXPECTED_IMAGE_ID or state.get('variants') != ORDER:
        raise ValueError('resume image/task plan changed')
    preflight = state['preflight']
    if sha(PAYLOAD / 'payload-index.json') != preflight['payload_index_sha256']:
        raise ValueError('payload changed since campaign preflight')
    for task in ORDER:
        if sha(PAYLOAD / 'tasks' / task / 'recipe.json') != preflight['binding'][task]['recipe_sha256']:
            raise ValueError('recipe changed since campaign preflight: ' + task)
    baseline = preflight.get('frozen_before')
    if not baseline or baseline != protected_snapshot():
        raise ValueError('protected materials changed since campaign preflight')
    passed = []
    for task, modes in state.get('tasks', {}).items():
        for mode in ('perf', 'topdown'):
            if modes.get(mode, {}).get('status') == 'passed':
                verify_capture(task, mode, campaign, state)
                passed.append(task + '/' + mode)
    return passed


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
        material = PARENT_CONFIG[task.split('-')[0]]['material']
        material_sha = sha(PAYLOAD / 'tasks' / task / 'seed/root/tmp/docs' / material) if material else None
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


    image = json.loads(subprocess.check_output(DOCKER + ['image', 'inspect', IMAGE_TAG], text=True))[0]
    result['image_tag'] = IMAGE_TAG
    result['image_id'] = image['Id']
    result['image_id_matches_expected'] = image['Id'] == EXPECTED_IMAGE_ID

    # in-container validate-only --env-check using the image's INSTALLED payload
    # (no host source mount; business payload/replay/compile come from the image).
    probe_argv = ['/opt/docops/venv/bin/python3', '-B', '/opt/docops/replay.py', 'validate-only',
                  '--payload', INSTALLED_PAYLOAD, '--env-check',
                  '--workdir', '/workspace/docops/work']
    name = 'docops-rv-precheck-' + campaign_dir.name.lower()
    existing = subprocess.check_output(DOCKER + ['ps', '-aq', '--filter', f'name=^{name}$'],
                                       text=True).splitlines()
    for cid in existing:
        subprocess.run(DOCKER + ['rm', '-f', cid], capture_output=True)
    cid = subprocess.check_output(
        DOCKER + ['create', '--name', name, '--network', 'none',
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
        result['catalog_tasks'] = sorted(
            t['task'] for t in json.loads((PAYLOAD / 'catalog.json').read_text())['tasks'])
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
        'round2_payload_tree': tree_sha(ROOT / 'docops/scaling/payload-word-pdf'),
        'official_catalog': sha(ROOT / 'docops/payload/catalog.json'),
        'official_index': sha(ROOT / 'docops/payload/payload-index.json'),
        'round1_index': sha(ROOT / 'docops/scaling/payload/payload-index.json'),
        'round2_index': sha(ROOT / 'docops/scaling/payload-word-pdf/payload-index.json'),
    }
    result['status'] = 'passed' if (
        result.get('payload', {}).get('status') == 'static_valid'
        and result['binding_all_ok']
        and result['image_id_matches_expected']
        and result.get('precheck_rc') == 0
        and result.get('precheck_env_errors') == []
        and result.get('precheck_plan_tasks') == sorted(
            t['task'] for t in json.loads((PAYLOAD / 'catalog.json').read_text())['tasks'])
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
                    installed_payload=INSTALLED_PAYLOAD,
                    image_ref=IMAGE_TAG, expected_image_id=EXPECTED_IMAGE_ID,
                    campaign_dir=campaign_dir,
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
    argv = DOCKER + ['create', '--name', f'docops-enrich-{task}-{uuid.uuid4().hex[:12]}',
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
            'samples_per_roi_second': profile['roi_samples'] / collection['roi_seconds'],
            'actual_sample_rate_per_cpu_hz': (profile['roi_samples'] / collection['roi_seconds']) / 8,
            'sample_rate_note': 'Legacy per_cpu field divides by eight allocated CPUs; '
                                'it is not the actual frequency of each active process.',
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


def run_campaign(args, campaign) -> int:
    if args.resume:
        if not (campaign / 'campaign.json').is_file():
            raise ValueError('no campaign to resume: ' + str(campaign))
        state = json.loads((campaign / 'campaign.json').read_text())
        if state.get('preflight', {}).get('status') != 'passed':
            raise ValueError('cannot resume: preflight not passed')
        if state.get('status') not in ('running', 'paused', 'failed'):
            raise ValueError('campaign state not resumable: ' + str(state.get('status')))
        passed = validate_resume(campaign, state)
        print(f'RESUME VALIDATED {len(passed)} completed captures; no recapture', flush=True)
        state['status'] = 'running'
        state.pop('error', None)
        state.pop('traceback', None)
        state.pop('stopped_at', None)
        state.pop('frozen_problems', None)
        state['resume_count'] = state.get('resume_count', 0) + 1
        old_driver = state.get('driver_sha256')
        new_driver = sha(Path(__file__).resolve())
        if old_driver != new_driver:
            state.setdefault('driver_history', []).append({'previous_sha256': old_driver,
                                                          'resume_sha256': new_driver})
        state['driver_sha256'] = new_driver
        state['captures_planned'] = len(ORDER) * 2
        write(campaign / 'campaign.json', state)
    else:
        if (campaign / 'campaign.json').exists():
            raise ValueError('refusing to reuse existing campaign: ' + str(campaign))
        campaign.mkdir(parents=True, exist_ok=True)
        created = datetime.datetime.now(datetime.timezone.utc).isoformat()
        state = dict(schema='docops-scaling-reviewed-performance-v1', status='preflight',
                     created_utc=created, image_tag=IMAGE_TAG, image_id=EXPECTED_IMAGE_ID,
                     variants=ORDER, loops_per_variant=VARIANT_LOOPS, captures_planned=len(ORDER) * 2,
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
        historical = historical_reuse(ROOT, PAYLOAD, EXPECTED_IMAGE_ID)
        write(campaign / 'historical-reuse.json', historical)
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
        for task in ORDER:
            state['tasks'].setdefault(task, {})
            for mode in ('perf', 'topdown'):
                if state['tasks'][task].get(mode, {}).get('status') == 'passed':
                    print(f'REUSE PASSED {task} {mode}', flush=True)
                    continue
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
        state['host_cpu_deltas_capture_span'] = host_cpu_deltas(host_before, host_after)
        state['host_interference_note'] = (
            'Host per-CPU idle% over the capture span on CPUs 0-9; '
            'diagnostic only, other project processes were not stopped.')
        write(campaign / 'campaign.json', state)

        # verification of the raw captures
        verification = {'schema': 'docops-scaling-reviewed-performance-verification-v1',
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
        # Recheck historical links at finalization instead of trusting an old status.
        historical = historical_reuse(ROOT, PAYLOAD, EXPECTED_IMAGE_ID)
        write(campaign / 'historical-reuse.json', historical)
        inventory = dataset_inventory(ROOT, state, verification, historical)
        write(campaign / 'dataset-inventory.json', inventory)
        verification['dataset_inventory'] = {
            'path': str((campaign / 'dataset-inventory.json').relative_to(ROOT)),
            'sha256': sha(campaign / 'dataset-inventory.json'),
            'new_tasks': len(ORDER), 'historical_tasks': len(historical['tasks'])}
        write(campaign / 'verification.json', verification)
        state['verification_sha256'] = sha(campaign / 'verification.json')
        state['status'] = 'passed'
        state['active'] = None
    except BaseException as exc:
        state.update(status='failed', error=f'{type(exc).__name__}: {exc}',
                     traceback=traceback.format_exc())
    finally:
        state['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            state['frozen_after'] = protected_snapshot()
            base = (state.get('preflight') or {}).get('frozen_before') or {}
            if base != state['frozen_after']:
                state['status'] = 'failed'
                state['frozen_problems'] = ['protected materials changed or baseline incomplete']
            write(campaign / 'campaign.json', state)
            if state['status'] == 'passed' and (campaign / 'verification.json').is_file():
                write_delivery(campaign, state, verification)
                final_index_and_readback(campaign, state)
        except BaseException as exc:
            state.update(status='failed', closeout_error=f'{type(exc).__name__}: {exc}',
                         closeout_traceback=traceback.format_exc())
            write(campaign / 'campaign.json', state)
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
    """SHA256 index over campaign-managed evidence (capture mode out dirs keep
    their own immutable per-capture index). campaign.json is written FINAL
    before the index; readback is verified in a separate excluded record."""
    excluded = {'campaign.sha256-index.json', 'campaign.index-verification.json',
                'campaign.json', '.collector.lock'}
    tracked = set()
    for t, modes in state.get('tasks', {}).items():
        for m, row in modes.items():
            raw = row.get('raw')
            if raw:
                tracked.add(Path(raw).name)
    skipped_orphans = []
    files = {}
    for p in sorted(campaign.rglob('*')):
        if not p.is_file():
            continue
        rel = p.relative_to(campaign)
        parts = rel.parts
        if 'chain-pilot' in parts[0]:
            if parts[0] not in tracked:
                skipped_orphans.append(parts[0])
                continue
            # tracked capture: a mode out dir with its own index is covered by
            # that per-capture index and excluded here.
            if (len(parts) >= 4 and parts[1] in ('perf', 'topdown') and parts[2] == 'out'
                    and (campaign / parts[0] / parts[1] / 'out/sha256-index.json').is_file()):
                continue
        if rel.name in excluded:
            continue
        files[rel.as_posix()] = {'bytes': p.stat().st_size, 'sha256': _sha_of(p)}
    state['index_skipped_orphan_attempts'] = sorted(set(skipped_orphans))
    path = campaign / 'campaign.sha256-index.json'
    state['final_index'] = {'path': str(path.relative_to(ROOT)),
                            'files_indexed': len(files)}
    write(campaign / 'campaign.json', state)  # final before the index
    path.write_text(json.dumps({'schema': 'docops-scaling-reviewed-performance-index-v1',
                                'files': files}, ensure_ascii=False, indent=2) + '\n')
    failures = []
    for rel, row in files.items():
        p = (campaign / rel).resolve()
        if not p.is_relative_to(campaign.resolve()):
            failures.append(rel + ': escapes campaign')
            continue
        if p.stat().st_size != row['bytes'] or _sha_of(p) != row['sha256']:
            failures.append(rel)
    verification = {
        'schema': 'docops-scaling-reviewed-performance-index-verification-v1',
        'index_sha256': _sha_of(path), 'files_checked': len(files),
        'status': 'passed' if not failures else 'failed',
        'failures': failures[:100],
        'index_covers': 'campaign-managed evidence except capture mode out dirs '
                        '(each has its own index); excludes campaign.json, the '
                        'index file, runtime .collector.lock and this verification record. '
                        'Untracked/incomplete orphan attempt dirs are skipped and '
                        'retained on disk (never deleted); they are listed in '
                        'index_skipped_orphan_attempts.',
        'skipped_orphan_attempts': state.get('index_skipped_orphan_attempts', []),
    }
    (campaign / 'campaign.index-verification.json').write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if failures:
        state['status'] = 'failed'
        state['index_failure'] = verification
        write(campaign / 'campaign.json', state)


def write_delivery(campaign: Path, state: dict, verification: dict):
    inventory = json.loads((campaign / 'dataset-inventory.json').read_text())
    lines = ['# DocOps 24 项规模变体采集清单', '',
             f'- campaign: `{state["campaign_rel"] if "campaign_rel" in state else str(campaign.relative_to(ROOT))}`',
             f'- 镜像: `{IMAGE_TAG}` = `{EXPECTED_IMAGE_ID}`',
             '- payload: `/opt/docops/scaling/payload-all`（kind=scaling，24任务）',
             f'- 本轮新增 {len(ORDER)} 个变体、{len(ORDER)*2} 份独立采集；历史8个变体按原轮数复用，两种来源分开记录。',
             '- 完整清单：`dataset-inventory.json`；历史来源及核验范围：`historical-reuse.json`。',
             f'- 每份采集独立新容器，network=none，结束后保留停止容器，不重启旧容器',
             f'- 请求频率: perf `cycles:u -F 49 -k mono --call-graph dwarf,16384`；DevKit `-c 0-7 -L 0 -i 1 -l 0`',
             '', '## 结果表', '',
             '| 任务 | 采集 | 回放轮数 | 完成/成功/失败 | workflow(s) | 采集包络(s) | 请求频率 | ROI样本/秒 | native样本 | ROI period | 补前未知叶% | 补后未知叶% | 丢样 | 归档 |',
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
                             f"{c['roi_seconds']:.2f} | — | 49 | {c['roi_samples']/c['roi_seconds']:.2f} | "
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
              f'- 本 campaign 恢复次数：{state.get("resume_count", 0)}；启动保护仅防重复控制器，不删除旧容器/结果。',
              '- 已通过采集先核验其归档再复用；未完成的旧 attempt 保留，新尝试使用新目录。',
              '- 具体采集尝试见各 `*-chain-pilot-*/launch.json`；驱动版本变化见 campaign.json 的 driver_history。',
              '- 此处只记录本 campaign，不复制历史 campaign 的失败故事。',
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
    lines += ['## 历史8项复用关联', '',
              '| 变体 | 原轮数/模式 | 原镜像ID | 已解析 native profile | 完整 Topdown |',
              '|---|---:|---|---|---|']
    for task, entry in inventory['tasks'].items():
        if entry['origin'] == 'historical_reuse':
            lines.append(f"| {task} | {entry['loops']} | `{entry['image_id']}` | "
                         f"`{entry['native_profile']['path']}` | `{entry['topdown_full_extract']['path']}` |")
    lines += ['', '历史数据不改写镜像身份或轮数；复用前核对任务文件、来源绑定与函数资格。',
              '采样周期权重不等于 CPU 时间；本轮不计算热点覆盖率或相似度。', '']
    (campaign / 'delivery.md').write_text('\n'.join(lines) + '\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign-dir', required=True, type=Path)
    parser.add_argument('--preflight-only', action='store_true')
    parser.add_argument('--resume', action='store_true',
                        help='resume 16 variants / 32 captures; verify and skip passed captures')
    parser.add_argument('--startup-status', type=Path,
                        help='exclusive startup-handshake path supplied by the detached launcher')
    parser.add_argument('--check-resume', action='store_true',
                        help='read-only resume/evidence/historical checks; never start capture or Docker')
    args = parser.parse_args(argv)
    campaign = args.campaign_dir.resolve()
    if args.check_resume:
        state = json.loads((campaign / 'campaign.json').read_text())
        passed = validate_resume(campaign, state)
        historical = historical_reuse(ROOT, PAYLOAD, EXPECTED_IMAGE_ID)
        print(json.dumps({'status': 'ready', 'passed_captures': len(passed),
                          'remaining_captures': len(ORDER)*2-len(passed),
                          'historical_tasks': len(historical['tasks']),
                          'capture_started': False}, ensure_ascii=False))
        return 0
    # Refuse accidental paths before creating a lock file or mutating campaign state.
    if not campaign.is_relative_to(ROOT):
        parser.error('campaign must live inside the repository')
    if args.resume and not (campaign / 'campaign.json').is_file():
        parser.error('campaign.json missing')
    if not args.resume and campaign.exists():
        parser.error('refusing to overwrite existing campaign')
    if not campaign.exists():
        campaign.mkdir(parents=True, exist_ok=False)
        # The empty directory exists so the lock can be acquired before any
        # manifest is written; run_campaign still rejects an existing manifest.
    startup = args.startup_status
    if startup is not None and (startup.exists() or startup.is_relative_to(campaign)):
        parser.error('startup-status must be a new path outside the campaign')
    try:
        with campaign_lock(campaign):
            if startup is not None:
                write(startup, {'status': 'started', 'pid': os.getpid(),
                                'sid': os.getsid(0), 'campaign': str(campaign)})
            return run_campaign(args, campaign)
    except BaseException as exc:
        if startup is not None and not startup.exists():
            write(startup, {'status': 'rejected', 'pid': os.getpid(),
                            'error': f'{type(exc).__name__}: {exc}'})
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr, flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
