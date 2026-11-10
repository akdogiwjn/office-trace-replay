"""Host-side formal functional campaign for the sixteen new scale variants.

Runs one replay round (loops=1) per variant, strictly serial, each in a fresh,
uniquely named, retained (no --rm), offline (network=none) container created
from the exact unified image, using the unified 24-variant payload
(``docops/scaling/payload-all``). The existing eight variants are NOT rerun
and are carried byte-identically into the unified payload.

After each run the archived output and the frozen expected oracle are re-checked
by the case validator in a fresh read-only offline container (independent
read-only verification), render artifacts are copied out of the retained
container and counted (structural evidence; no human image viewing is claimed),
and per-loop run records are verified. This driver only launches, verifies and
archives; it draws no performance conclusions and does not touch the official
payload, the existing scaling payloads or any historical evidence.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from prepare import PARENT_CONFIG  # noqa: E402

IMAGE_TAG = 'docops-replay:openeuler-unified-candidate-04'
EXPECTED_IMAGE_ID = 'sha256:57483856a27942ffd4aef853950ca66b00c12b0787aae6c1dac74371d03e6164'
PAYLOAD = ROOT / 'docops/scaling/payload-all'
REPLAY_PY = ROOT / 'docops/replay.py'
COMPILE_PY = ROOT / 'docops/compile.py'
INTERPRETER = '/opt/docops/venv/bin/python3'
TASKS = ['001-u100', '001-u500', '009-u100', '009-u500',
         '013-v100', '013-v1000', '016-u100', '016-u500',
         '026-u5', '026-u10', '029-u5', '029-u10',
         '031-u5', '031-u20', 'pdfwf005-u5', 'pdfwf005-u20']
STEP_TIMEOUT = 3600
HOST_TIMEOUT = 10800

RENDER_PATTERNS = {
    '001': {'dir': 'render_variant_v2', 'pattern': r'^page-\d+\.png$'},
    '009': {'dir': 'rendered_v2', 'pattern': r'^page-\d+\.png$'},
    '013': {'dir': 'rendered-final', 'pattern': r'^final-page-\d+\.png$'},
    '016': {'dir': 'render_landscape', 'pattern': r'^dashboard\.png$'},
    '026': {'dir': 'rendered', 'pattern': r'^slide-\d+\.jpg$'},
    '029': {'dir': '', 'pattern': r'^release_final_slide-\d+\.jpg$'},
    '031': {'dir': '', 'pattern': r'^release_page-\d+\.png$'},
    'pdfwf005': {'dir': 'render-output', 'pattern': r'^page-\d+\.png$'},
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def docker(*args, **kwargs):
    return subprocess.run(['docker', *args], check=True, capture_output=True,
                          text=True, timeout=120, **kwargs)


def docker_out(*args, **kwargs):
    return subprocess.check_output(['docker', *args], text=True, timeout=120, **kwargs)


def create_clean(name: str, *create_args) -> str:
    existing = docker('ps', '-aq', '--filter', f'name=^{name}$').stdout.splitlines()
    for cid in existing:
        docker('rm', '-f', cid)
    return docker('create', '--name', name, *create_args).stdout.strip()


def tree_sha(root: Path) -> str:
    files = sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file())
    h = hashlib.sha256()
    for rel in files:
        h.update(rel.encode()); h.update(b'\0')
        h.update((root / rel).read_bytes()); h.update(b'\0')
    return h.hexdigest()


def load_compile_validate():
    spec = importlib.util.spec_from_file_location('docops_compile', COMPILE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.validate_payload


def load_replay_module():
    spec = importlib.util.spec_from_file_location('docops_replay', REPLAY_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def catalog_tasks(payload_root: Path) -> list[str]:
    return sorted(t['task'] for t in json.loads((payload_root / 'catalog.json').read_text())['tasks'])


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
    for task in TASKS:
        recipe = json.loads((PAYLOAD / 'tasks' / task / 'recipe.json').read_text())
        problems = []
        for f in recipe['files']:
            if index[f['payload']]['sha256'] != f['sha256'] or index[f['payload']]['bytes'] != f['bytes']:
                problems.append(f'recipe file binding mismatch: {f["payload"]}')
        for s in recipe['steps']:
            body = (PAYLOAD / s['shell_body']).read_text()
            if body != s['argv'][2]:
                problems.append(f'shell body mismatch: {s["shell_body"]}')
            for flag in ('--structure-only', '--skip', '--fixture', '--dry-run'):
                if flag in s['argv'][2]:
                    problems.append(f'formal command contains {flag}')
        scoped = replay_mod.task_scoped_paths(recipe)
        reset_overlap = [p for p in scoped
                         if p == '/results' or p.startswith('/results') or p.startswith('/results/')]
        binding[task] = {
            'ok': not problems and not reset_overlap,
            'problems': problems,
            'reset_overlap_results': reset_overlap,
            'recipe_sha256': sha(PAYLOAD / 'tasks' / task / 'recipe.json'),
            'sv': recipe['synthetic_variant'],
            'steps': [s['name'] for s in recipe['steps']],
        }
    result['binding'] = binding
    result['binding_all_ok'] = all(b['ok'] for b in binding.values())

    image = json.loads(docker('image', 'inspect', IMAGE_TAG).stdout)[0]
    result['image_tag'] = IMAGE_TAG
    result['image_id'] = image['Id']
    result['image_id_matches_expected'] = image['Id'] == EXPECTED_IMAGE_ID

    probe_argv = [INTERPRETER, '-B', '/opt/docops/replay.py', 'validate-only',
                  '--payload', '/opt/docops/scaling/payload', '--env-check',
                  '--workdir', '/workspace/docops/work']
    name = 'docops-all-precheck-' + campaign_dir.name.lower()
    cid = create_clean(name, '--network', 'none',
                 '-v', str(PAYLOAD) + ':/opt/docops/scaling/payload:ro',
                 '-v', str(REPLAY_PY) + ':/opt/docops/replay.py:ro',
                 '-v', str(COMPILE_PY) + ':/opt/docops/compile.py:ro',
                 '-v', str(campaign_dir / 'precheck-results') + ':/results',
                 '--entrypoint', probe_argv[0], image['Id'], *probe_argv[1:])
    result['precheck_container'] = cid
    log_path = campaign_dir / 'precheck-container.log'
    with log_path.open('w') as log:
        cp = subprocess.run(['docker', 'start', '-a', cid], stdout=log,
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
    result['catalog_tasks'] = catalog_tasks(PAYLOAD)
    all_24 = sorted(catalog_tasks(PAYLOAD))
    result['selected_are_subset_of_24'] = set(TASKS) <= set(all_24)
    result['frozen_before'] = {
        'official_payload_tree': tree_sha(ROOT / 'docops/payload'),
        'round1_payload_tree': tree_sha(ROOT / 'docops/scaling/payload'),
        'round2_payload_tree': tree_sha(ROOT / 'docops/scaling/payload-word-pdf'),
        'official_catalog': sha(ROOT / 'docops/payload/catalog.json'),
        'official_index': sha(ROOT / 'docops/payload/payload-index.json'),
    }
    result['status'] = 'passed' if (
        result.get('payload', {}).get('status') == 'static_valid'
        and result['binding_all_ok']
        and result['image_id_matches_expected']
        and result.get('precheck_rc') == 0
        and result.get('precheck_env_errors') == []
        and result.get('precheck_plan_tasks') == all_24
        and result['selected_are_subset_of_24']
    ) else 'failed'
    return result


def recipe_input_name(task: str) -> str:
    meta = json.loads((PAYLOAD / 'tasks' / task / 'seed/root/task_metadata.json').read_text())
    return Path(meta['input_path']).name


def run_task(task: str, image_id: str, campaign_dir: Path) -> dict:
    folder = campaign_dir / task
    results_root = folder / 'results'
    # Fresh attempt: a previous failed round in the same results dir would make
    # replay write round-002 and leave a stale round-001; remove the task's own
    # campaign results root so this run starts cleanly from round-001. The prior
    # failed evidence stays in the campaign trial-record and container logs.
    # The results root may be container-root-owned, so clean it through docker.
    if results_root.exists():
        # Never delete a completed workload's evidence; refuse instead.
        task_dir = results_root / task
        if task_dir.is_dir():
            completed = [p for p in task_dir.glob('round-*/run.json')
                         if json.loads(p.read_text()).get('status') == 'completed']
            if completed:
                raise ValueError('refusing to delete a completed workload results dir: ' + str(results_root))
        subprocess.run(['docker', 'run', '--rm', '--network', 'none',
                        '-v', str(folder) + ':/t',
                        '--entrypoint', '/bin/rm', EXPECTED_IMAGE_ID,
                        '-rf', '/t/results'],
                       check=False, capture_output=True, timeout=120)
    folder.mkdir(parents=True, exist_ok=True)
    results_root.mkdir(parents=True, exist_ok=True)
    record = dict(task=task, status='running', loops=1,
                  image_id=image_id, recipe_sha256=sha(PAYLOAD / 'tasks' / task / 'recipe.json'))
    cid = None
    try:
        argv = [INTERPRETER, '-B', '/opt/docops/replay.py', 'run',
                '--payload', '/opt/docops/scaling/payload',
                '--workdir', '/workspace/docops/work',
                '--results-dir', '/results',
                '--task', task, '--loops', '1', '--step-timeout', str(STEP_TIMEOUT)]
        name = f'docops-all-{task}-{campaign_dir.name.lower()}'
        create = ['create', '--name', name, '--network', 'none',
                  '--cpuset-cpus', '0-9', '--cap-add', 'PERFMON', '--cap-add', 'SYS_PTRACE',
                  '--security-opt', 'seccomp=unconfined',
                  '-v', str(PAYLOAD) + ':/opt/docops/scaling/payload:ro',
                  '-v', str(REPLAY_PY) + ':/opt/docops/replay.py:ro',
                  '-v', str(COMPILE_PY) + ':/opt/docops/compile.py:ro',
                  '-v', str(folder / 'results') + ':/results',
                  '--entrypoint', argv[0], image_id, *argv[1:]]
        cid = create_clean(name, *create[3:])
        record.update(container_id=cid, create_argv=create)
        before = json.loads(docker('inspect', cid).stdout)[0]
        write(folder / 'container-before.json', before)
        assert before['Image'] == image_id
        assert before['HostConfig']['NetworkMode'] == 'none'
        assert before['HostConfig'].get('CpusetCpus') == '0-9'
        caps = before['HostConfig'].get('CapAdd', [])
        assert 'PERFMON' in caps and 'SYS_PTRACE' in caps
        results_mount = next(m for m in before['Mounts'] if m['Destination'] == '/results')
        assert Path(results_mount['Source']).resolve() == (folder / 'results').resolve()
        assert results_mount['RW'] is True
        assert all(m['RW'] is False for m in before['Mounts'] if m['Destination'] != '/results')
        with (folder / 'container.log').open('w') as log:
            cp = subprocess.run(['docker', 'start', '-a', cid], stdout=log,
                                stderr=subprocess.STDOUT, timeout=HOST_TIMEOUT)
        after = json.loads(docker('inspect', cid).stdout)[0]
        write(folder / 'container-after.json', after)
        record.update(docker_returncode=cp.returncode, container_exit_code=after['State']['ExitCode'])
        assert cp.returncode == 0 and after['State']['ExitCode'] == 0, 'workload failed'

        summary = json.loads((folder / 'results' / task / 'summary.json').read_text())
        counts = {k: summary[k] for k in ('requested', 'completed', 'successes', 'failures')}
        assert counts == dict(requested=1, completed=1, successes=1, failures=0), counts
        rounds = [r for r in (folder / 'results' / task).iterdir() if r.is_dir() and r.name.startswith('round-')]
        assert len(rounds) == 1, f'expected one round dir, got {[r.name for r in rounds]}'
        run = json.loads((rounds[0] / 'run.json').read_text())
        assert run['completed'] and run['successes'] == 1 and not run['failures']
        assert all(s['status'] == 'ok' and s['rc'] == 0 for s in run['steps'])
        assert run['recipe_sha256'] == record['recipe_sha256']
        archive = run['archive']
        artifact = (folder / 'results' / archive['archive_path']).resolve()
        assert artifact.is_file() and artifact.stat().st_size == archive['bytes'] > 0
        assert sha(artifact) == archive['sha256']
        record.update(round_id=rounds[0].name, summary=counts, roi_wall_s=run['roi_wall_s'],
                      steps=run['roi_steps'], output=archive,
                      input_sha256=recipe_input_sha(task))
        # frozen input unchanged (docker cp back from workspace)
        input_name = recipe_input_name(task)
        input_dst = folder / 'verified-input'
        input_dst.mkdir(exist_ok=True)
        docker('cp', f'{cid}:/root/{input_name}', str(input_dst / input_name))
        assert sha(input_dst / input_name) == recipe_input_sha(task)
        # preserve /root/tmp/docs (stages, validation reports, rendered pages)
        docker('cp', f'{cid}:/root/tmp/docs', str(folder / 'workspace-docs'))
        record.update(status='passed')
    except BaseException as exc:
        record.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        if cid:
            subprocess.run(['docker', 'stop', '-t', '3', cid], capture_output=True, timeout=30)
    finally:
        write(folder / 'trial-record.json', record)
        index = {str(p.relative_to(folder)): {'bytes': p.stat().st_size, 'sha256': sha(p)}
                 for p in sorted(folder.rglob('*')) if p.is_file()}
        write(folder / 'sha256-index.json', {'files': index})
    return record


def recipe_input_sha(task: str) -> str:
    r = json.loads((PAYLOAD / 'tasks' / task / 'recipe.json').read_text())
    return r['synthetic_variant']['input_sha256']


def post_verify(task: str, campaign_dir: Path) -> dict:
    """Independent read-only re-check of the archived output with the frozen
    expected oracle using the case validator in a fresh retained offline
    container. The validator module is the case's own validate script."""
    folder = campaign_dir / task
    parent = task.split('-')[0]
    validator_mod = PARENT_CONFIG[parent]['scripts'][1].replace('.py', '')
    rounds = sorted([r for r in (folder / 'results' / task).iterdir()
                     if r.is_dir() and r.name.startswith('round-')])
    run = json.loads((rounds[0] / 'run.json').read_text())
    out_rel = run['archive']['archive_path']
    out_ctr = '/results/' + out_rel
    expected_ctr = '/repo/' + str((PAYLOAD / f'tasks/{task}/seed/root/tmp/docs/expected.json').resolve().relative_to(ROOT.resolve()))
    script = (
        "import sys, json, importlib\n"
        "sys.path.insert(0, '/repo/docops')\n"
        f"out = {out_ctr!r}\n"
        f"exp = {expected_ctr!r}\n"
        f"mod = importlib.import_module('scaling.cases.{parent}.scripts.{validator_mod}')\n"
        "rep = mod.check(out, exp)\n"
        "if 'errors' not in rep:\n"
        "    checks = rep.get('checks', {})\n"
        "    rep['errors'] = [k for k, v in checks.items() if v is not True]\n"
        "if rep.get('passed') is None:\n"
        "    rep['passed'] = not rep.get('errors', [])\n"
        "if rep.get('measured') is None:\n"
        "    rep['measured'] = {k: v for k, v in rep.items() if k not in ('errors', 'passed', 'measured')}\n"
        "print(json.dumps({'errors': rep['errors'], 'passed': rep['passed'], 'measured': rep.get('measured'), 'raw_checks': rep.get('checks')}))\n"
    )
    name = f'docops-all-verify-{task}-{campaign_dir.name.lower()}'
    cid = create_clean(name, '--network', 'none',
                 '-v', str(ROOT) + ':/repo:ro',
                 '-v', str(folder / 'results') + ':/results',
                 '--entrypoint', INTERPRETER, EXPECTED_IMAGE_ID, '-B', '-c', script)
    log = folder / 'post-verify.log'
    with log.open('w') as fh:
        cp = subprocess.run(['docker', 'start', '-a', cid], stdout=fh,
                            stderr=subprocess.STDOUT, timeout=600)
    result = {'rc': cp.returncode, 'log': log.read_text()[-4000:]}
    try:
        raw = log.read_text()
        result['report'] = json.loads(raw[raw.index('{'):raw.rindex('}') + 1])
    except Exception as exc:
        result['report'] = {'parse_error': f'{type(exc).__name__}: {exc}'}
    result['container_id'] = cid
    return result


def count_renders(task: str, campaign_dir: Path) -> dict:
    parent = task.split('-')[0]
    spec = RENDER_PATTERNS.get(parent)
    docs = campaign_dir / task / 'workspace-docs'
    if spec is None or not docs.is_dir():
        return {'pattern': None, 'count': None, 'note': 'no render pattern defined or workspace-docs missing'}
    base = docs / spec['dir'] if spec['dir'] else docs
    files = sorted(base.glob('*')) if base.is_dir() else []
    matched = [p for p in files if re.fullmatch(spec['pattern'], p.name)]
    contact = sorted(docs.glob('output-contact*.png')) if docs.is_dir() else []
    return {'pattern': spec['pattern'], 'dir': spec['dir'],
            'files_in_dir': len(files), 'matched': len(matched),
            'contact_sheet_tiles': len(contact),
            'samples': [p.name for p in matched[:3]]}


def run_completed_round(task: str, campaign_dir: Path) -> bool:
    r = campaign_dir / task / 'results' / task / 'round-001' / 'run.json'
    if not r.is_file():
        return False
    return json.loads(r.read_text()).get('status') == 'completed'


def reuse_binding_ok(task: str, campaign_dir: Path) -> bool:
    """Minimal reuse binding: the archived round must exist, be completed, and
    its recipe/artifact hashes must match the selected payload materials."""
    run_path = campaign_dir / task / 'results' / task / 'round-001' / 'run.json'
    if not run_path.is_file():
        return False
    run = json.loads(run_path.read_text())
    if run.get('status') != 'completed' or run.get('successes') != 1:
        return False
    if run.get('recipe_sha256') != sha(PAYLOAD / 'tasks' / task / 'recipe.json'):
        return False
    archive = run.get('archive', {})
    artifact = (campaign_dir / task / 'results' / archive.get('archive_path', '')).resolve()
    return artifact.is_file() and sha(artifact) == archive.get('sha256')


def frozen_consistency_problems(state: dict) -> list[str]:
    base = (state.get('preflight') or {}).get('frozen_before') or {}
    if not base or not all(k in base for k in ('official_payload_tree', 'round1_payload_tree',
                                               'round2_payload_tree', 'official_catalog',
                                               'official_index')):
        return ['frozen baseline missing or incomplete']
    try:
        current = {
            'official_payload_tree': tree_sha(ROOT / 'docops/payload'),
            'round1_payload_tree': tree_sha(ROOT / 'docops/scaling/payload'),
            'round2_payload_tree': tree_sha(ROOT / 'docops/scaling/payload-word-pdf'),
            'official_catalog': sha(ROOT / 'docops/payload/catalog.json'),
            'official_index': sha(ROOT / 'docops/payload/payload-index.json'),
        }
    except BaseException as exc:
        return [f'frozen snapshot compute failed: {type(exc).__name__}: {exc}']
    return [f'frozen material changed: {k} {base.get(k)} -> {current.get(k)}'
            for k in current if base.get(k) != current.get(k)]


def task_gate(record: dict, verify: dict, renders: dict) -> list[str]:
    problems = []
    if record.get('status') != 'passed':
        problems.append('workload not passed')
    if verify.get('rc') != 0:
        problems.append(f'post-verify rc={verify.get("rc")}')
    report = verify.get('report') or {}
    if report.get('parse_error'):
        problems.append('post-verify report unparseable')
    elif report.get('passed') is not True:
        problems.append(f'post-verify passed not true: {report.get("passed")!r}')
    matched = (renders or {}).get('matched')
    if not isinstance(matched, int) or matched <= 0:
        problems.append(f'render count invalid: {matched!r}')
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign-dir', required=True, type=Path)
    parser.add_argument('--preflight-only', action='store_true')
    parser.add_argument('--resume', action='store_true',
                        help='continue an existing campaign; reuse passed tasks and '
                             'completed rounds, never rerun an already completed round')
    args = parser.parse_args(argv)
    campaign = args.campaign_dir.resolve()
    if args.resume:
        if not (campaign / 'campaign.json').is_file():
            raise ValueError('no campaign to resume: ' + str(campaign))
        state = json.loads((campaign / 'campaign.json').read_text())
        if state.get('preflight', {}).get('status') != 'passed':
            raise ValueError('cannot resume: preflight not passed')
        state['status'] = 'running'
        state.pop('error', None)
        state['resume_count'] = state.get('resume_count', 0) + 1
        state['driver_sha256'] = sha(Path(__file__).resolve())
        write(campaign / 'campaign.json', state)
    else:
        if campaign.exists():
            raise ValueError('refusing to reuse existing campaign: ' + str(campaign))
        campaign.mkdir(parents=True)
        state = dict(schema='docops-scaling-all-functional-v1', status='preflight',
                     created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     image_tag=IMAGE_TAG, image_id=EXPECTED_IMAGE_ID,
                     selected_tasks=TASKS, tasks={}, loops=1, step_timeout=STEP_TIMEOUT,
                     driver_sha256=sha(Path(__file__).resolve()),
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
            return 0
        state['status'] = 'running'
        write(campaign / 'campaign.json', state)

    def already_ok(task: str) -> bool:
        rec = state.get('tasks', {}).get(task, {})
        if rec.get('status') != 'passed':
            return False
        verify = rec.get('post_verify', {})
        report = verify.get('report', {})
        if verify.get('rc') not in (0, None):
            return False
        if report.get('parse_error') or report.get('passed') is not True:
            return False
        if not reuse_binding_ok(task, campaign):
            return False
        return True

    try:
        for task in TASKS:
            if already_ok(task):
                print(f'REUSE PASSED {task}', flush=True)
                continue
            if args.resume and run_completed_round(task, campaign):
                print(f'RE-VERIFY {task}', flush=True)
                record = json.loads((campaign / task / 'trial-record.json').read_text())
                verify = post_verify(task, campaign)
                renders = count_renders(task, campaign)
                record['post_verify'] = verify
                record['render_counts'] = renders
                write(campaign / task / 'trial-record.json', record)
                state['tasks'][task] = {
                    'status': record['status'], 'round_id': record.get('round_id'),
                    'summary': record.get('summary'), 'roi_wall_s': record.get('roi_wall_s'),
                    'steps': record.get('steps'), 'output': record.get('output'),
                    'post_verify': verify, 'render_counts': renders, 'error': record.get('error'),
                }
                write(campaign / 'campaign.json', state)
                print(f"RE-VERIFY END {task} rc={verify.get('rc')} passed={verify.get('report', {}).get('passed')}", flush=True)
                gate_problems = task_gate(record, verify, renders)
                if gate_problems:
                    state['status'] = 'failed'
                    state['stopped_at'] = task
                    state['task_failure'] = {task: gate_problems}
                    write(campaign / 'campaign.json', state)
                    break
                continue
            state['active'] = task
            write(campaign / 'campaign.json', state)
            print(f'RUN START {task}', flush=True)
            record = run_task(task, EXPECTED_IMAGE_ID, campaign)
            verify = post_verify(task, campaign) if record['status'] == 'passed' else {}
            renders = count_renders(task, campaign)
            record['post_verify'] = verify
            record['render_counts'] = renders
            write(campaign / task / 'trial-record.json', record)
            state['tasks'][task] = {
                'status': record['status'],
                'round_id': record.get('round_id'),
                'summary': record.get('summary'),
                'roi_wall_s': record.get('roi_wall_s'),
                'steps': record.get('steps'),
                'output': record.get('output'),
                'post_verify': verify,
                'render_counts': renders,
                'error': record.get('error'),
            }
            state['active'] = None
            write(campaign / 'campaign.json', state)
            print(f"RUN END {task} status={record['status']} roi_wall_s={record.get('roi_wall_s')}", flush=True)
            gate_problems = task_gate(record, verify, renders)
            if gate_problems:
                state['status'] = 'failed'
                state['stopped_at'] = task
                state['task_failure'] = {task: gate_problems}
                write(campaign / 'campaign.json', state)
                break
        else:
            state['status'] = 'passed'
    except BaseException as exc:
        state.update(status='failed', error=f'{type(exc).__name__}: {exc}')
    finally:
        state['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        frozen_problems = frozen_consistency_problems(state)
        state['frozen_after'] = {
            'official_payload_tree': tree_sha(ROOT / 'docops/payload'),
            'round1_payload_tree': tree_sha(ROOT / 'docops/scaling/payload'),
            'round2_payload_tree': tree_sha(ROOT / 'docops/scaling/payload-word-pdf'),
            'official_catalog': sha(ROOT / 'docops/payload/catalog.json'),
            'official_index': sha(ROOT / 'docops/payload/payload-index.json'),
        }
        if frozen_problems:
            state['status'] = 'failed'
            state['frozen_problems'] = frozen_problems
        write(campaign / 'campaign.json', state)
        if state['status'] == 'passed':
            final_index_and_readback(campaign, state)
    print(json.dumps({'status': state['status'], 'campaign': str(campaign),
                      'tasks': {k: v.get('status') for k, v in state.get('tasks', {}).items()},
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
    files = {}
    for p in sorted(campaign.rglob('*')):
        if not p.is_file():
            continue
        rel = p.relative_to(campaign)
        if rel.name == 'campaign.sha256-index.json':
            continue
        files[rel.as_posix()] = {'bytes': p.stat().st_size, 'sha256': _sha_of(p)}
    path = campaign / 'campaign.sha256-index.json'
    path.write_text(json.dumps({'schema': 'docops-scaling-all-functional-index-v1',
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


if __name__ == '__main__':
    raise SystemExit(main())
