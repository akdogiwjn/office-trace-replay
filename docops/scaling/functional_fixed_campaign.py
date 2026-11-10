"""Host-side functional re-verification campaign for the round-3-fixed 016
variants (016-u100, 016-u500) on the reviewed image, plus offline read-only
re-verification of existing 029 outputs via directed checks.

Each 016 variant runs one replay round in a fresh, retained, offline
(network=none) container from ``docops-replay:openeuler-scaled-reviewed`` using
the image's INSTALLED unified payload and installed replay.py/scripts - no host
source mount overrides the image. Attempts always write to NEW directories and
containers; completed workloads are never deleted or rerun just because an
offline re-check failed (re-check-only retries). The offline re-check is a
genuinely read-only process: source, archived output, expected and render
evidence are mounted read-only, a separate writable report directory receives
the report, and the delivered files' SHA256 are verified unchanged before/after.

Acceptance is a real gate: workload+counts+steps, post-verify rc=0 with a
parsed report whose passed is explicitly true, render count/continuity matching
the task contract, frozen-material binding and archive index all must pass or
the task/campaign fail and the process stops.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

DOCKER = ['docker', '--host', 'unix:///var/run/docker.sock']

from prepare import PARENT_CONFIG  # noqa: E402

IMAGE_TAG = 'docops-replay:openeuler-scaled-reviewed'
EXPECTED_IMAGE_ID = 'sha256:9ae9d418980ab88a305eb37fc2399edadea129a70d803cdbc642357daa56f7d6'
INSTALLED_PAYLOAD = '/opt/docops/scaling/payload-all'
PAYLOAD = ROOT / 'docops/scaling/payload-all'
INTERPRETER = '/opt/docops/venv/bin/python3'
TASKS = ['016-u100', '016-u500']
STEP_TIMEOUT = 3600
HOST_TIMEOUT = 10800

RENDER_CONTRACTS = {
    '016': {'kind': 'single', 'dir': 'render_landscape', 'pattern': r'^dashboard\.png$',
            'count': 1},
    '029': {'kind': 'single', 'dir': '', 'pattern': r'^release_final_slide-\d+\.jpg$',
            'count': 1},
    '009': {'kind': 'contiguous', 'dir': 'rendered_v2', 'pattern': r'^page-(\d+)\.png$'},
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


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


def tree_sha(root: Path) -> str:
    files = sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file())
    h = hashlib.sha256()
    for rel in files:
        h.update(rel.encode()); h.update(b'\0')
        h.update((root / rel).read_bytes()); h.update(b'\0')
    return h.hexdigest()


def catalog_tasks(payload_root: Path) -> list[str]:
    return sorted(t['task'] for t in json.loads((payload_root / 'catalog.json').read_text())['tasks'])


FROZEN_KEYS = ['official_payload_tree', 'round1_payload_tree', 'round2_payload_tree',
              'official_catalog', 'official_index']


def frozen_snapshot() -> dict:
    """Compute the protected-material hashes from the ACTUAL files now."""
    return {
        'official_payload_tree': tree_sha(ROOT / 'docops/payload'),
        'round1_payload_tree': tree_sha(ROOT / 'docops/scaling/payload'),
        'round2_payload_tree': tree_sha(ROOT / 'docops/scaling/payload-word-pdf'),
        'official_catalog': sha(ROOT / 'docops/payload/catalog.json'),
        'official_index': sha(ROOT / 'docops/payload/payload-index.json'),
    }


def frozen_consistency_problems(state: dict) -> list[str]:
    """Compare the frozen baseline recorded at preflight with the current files.
    A missing/incomplete baseline, a compute failure, or any changed key is a
    problem with an explicit reason."""
    problems = []
    base = (state.get('preflight') or {}).get('frozen_before') or {}
    if not base or not all(k in base for k in FROZEN_KEYS):
        problems.append('frozen baseline missing or incomplete')
        return problems
    try:
        current = frozen_snapshot()
    except BaseException as exc:
        problems.append(f'frozen snapshot compute failed: {type(exc).__name__}: {exc}')
        return problems
    for key in FROZEN_KEYS:
        if base.get(key) != current.get(key):
            problems.append(f'frozen material changed: {key} {base.get(key)} -> {current.get(key)}')
    return problems


def new_attempt_dir(folder: Path) -> Path:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        '%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    path = folder / f'attempt-{stamp}'
    path.mkdir(parents=True, exist_ok=False)
    return path


def recipe_input_sha(task: str) -> str:
    r = json.loads((PAYLOAD / 'tasks' / task / 'recipe.json').read_text())
    return r['synthetic_variant']['input_sha256']


def recipe_expected_sha(task: str) -> str:
    return sha(PAYLOAD / 'tasks' / task / 'seed/root/tmp/docs/expected.json')


# ---------------------------------------------------------------------------
# Render contract (F5): the render evidence must match the task's contract.
# ---------------------------------------------------------------------------

def render_contract_problems(task: str, attempt_dir: Path) -> list[str]:
    parent = task.split('-')[0]
    contract = RENDER_CONTRACTS.get(parent)
    if contract is None:
        return [f'no render contract for parent {parent}']
    docs = attempt_dir / 'workspace-docs'
    if not docs.is_dir():
        return ['workspace-docs missing']
    base = docs / contract['dir'] if contract['dir'] else docs
    if not base.is_dir():
        return [f'render dir missing: {contract["dir"]}']
    matched = sorted(p for p in base.iterdir() if re.fullmatch(contract['pattern'], p.name))
    problems = []
    if contract['kind'] == 'single':
        if len(matched) != contract['count']:
            problems.append(f'expected {contract["count"]} render image(s), found {len(matched)}')
        if len(matched) == 1 and not matched[0].is_file():
            problems.append('render image is not a file')
    else:  # contiguous
        nums = []
        for p in matched:
            m = re.fullmatch(contract['pattern'], p.name)
            nums.append(int(m.group(1)))
        nums.sort()
        if not nums:
            problems.append('no rendered page images')
        elif nums != list(range(1, len(nums) + 1)) and nums != list(range(0, len(nums))):
            problems.append(f'page numbering not contiguous: {nums[:8]}')
        pdfs = list((docs / contract['dir']).glob('*.pdf'))
        if not pdfs:
            problems.append('rendered PDF missing')
        else:
            info = subprocess.run(['pdfinfo', str(pdfs[0])], capture_output=True,
                                  text=True).stdout
            m = re.search(r'^Pages:\s+(\d+)', info, re.M)
            pdf_pages = int(m.group(1)) if m else None
            if pdf_pages is None:
                problems.append('could not read rendered PDF page count')
            elif len(nums) != pdf_pages:
                problems.append(f'page images {len(nums)} != pdf pages {pdf_pages}')
    return problems


# ---------------------------------------------------------------------------
# Acceptance gate (F5): every required fact must pass, not just be recorded.
# ---------------------------------------------------------------------------

def acceptance_problems(task: str, record: dict, verify: dict, render_problems: list,
                        frozen_ok: bool, binding_ok: bool) -> list[str]:
    problems = []
    if record.get('status') != 'passed':
        problems.append('workload status not passed')
    counts = record.get('summary') or {}
    loops = record.get('loops', 1)
    if counts.get('requested') != loops or counts.get('completed') != loops \
            or counts.get('successes') != loops or counts.get('failures') != 0:
        problems.append(f'loop counts mismatch: {counts}')
    steps = record.get('steps') or []
    if not steps:
        problems.append('no workflow steps recorded')
    for step in steps:
        if step.get('status') != 'ok' or step.get('rc') != 0:
            problems.append(f"step {step.get('id')}: status={step.get('status')} rc={step.get('rc')}")
    if record.get('round_id') is None or record.get('output') is None:
        problems.append('round/output record missing')
    if verify.get('rc') != 0:
        problems.append(f'post-verify rc={verify.get("rc")} != 0')
    report = verify.get('report') or {}
    if report.get('parse_error'):
        problems.append(f"post-verify report unparseable: {report.get('parse_error')}")
    elif report.get('passed') is not True:
        problems.append(f'post-verify passed not explicitly true: {report.get("passed")!r}')
    if verify.get('pre_sha') and verify.get('post_sha'):
        if verify.get('pre_sha') != verify.get('post_sha'):
            problems.append('delivered files changed during read-only re-verify')
    if render_problems:
        problems.append('render contract: ' + '; '.join(render_problems))
    if not frozen_ok:
        problems.append('frozen materials changed across the campaign')
    if not binding_ok:
        problems.append('payload/recipe/input/expected binding mismatch')
    return problems


def verify_report_ok(verify: dict) -> bool:
    if verify.get('rc') != 0:
        return False
    report = verify.get('report') or {}
    if report.get('parse_error'):
        return False
    return report.get('passed') is True


# ---------------------------------------------------------------------------
# Read-only offline re-verify (F4)
# ---------------------------------------------------------------------------

def build_verify_spec(task: str, attempt_dir: Path, verify_dir: Path):
    """Return (create_argv, mounts_evidence, delivered_paths). /repo and the
    archived results/expected/render evidence are read-only; only the verify
    report directory is writable."""
    rounds = sorted([r for r in (attempt_dir / 'results' / task).iterdir()
                     if r.is_dir() and r.name.startswith('round-')])
    run = json.loads((rounds[0] / 'run.json').read_text())
    out_rel = run['archive']['archive_path']
    out_host = (attempt_dir / 'results' / out_rel).resolve()
    expected_host = (PAYLOAD / f'tasks/{task}/seed/root/tmp/docs/expected.json').resolve()
    delivered = [out_host, expected_host]
    create = DOCKER + ['create', '--name', f'docops-fixed-verify-{task}-{verify_dir.name.lower()}',
              '--network', 'none',
              '-v', str(ROOT) + ':/repo:ro',
              '-v', str((attempt_dir / 'results').resolve()) + ':/results:ro',
              '-v', str((attempt_dir / 'workspace-docs').resolve()) + ':/render:ro',
              '-v', str(verify_dir) + ':/report',
              '--entrypoint', INTERPRETER, EXPECTED_IMAGE_ID, '-B']
    mounts_evidence = {
        '/repo': {'source': str(ROOT), 'rw': False},
        '/results': {'source': str((attempt_dir / 'results').resolve()), 'rw': False},
        '/render': {'source': str((attempt_dir / 'workspace-docs').resolve()), 'rw': False},
        '/report': {'source': str(verify_dir), 'rw': True},
    }
    return create, mounts_evidence, delivered, run


def post_verify(task: str, attempt_dir: Path, campaign_dir: Path) -> dict:
    parent = task.split('-')[0]
    validator_mod = PARENT_CONFIG[parent]['scripts'][-1].replace('.py', '')
    verify_dir = campaign_dir / 'verify' / f'{task}-{uuid.uuid4().hex[:8]}'
    verify_dir.mkdir(parents=True)
    create, mounts_evidence, delivered, run = build_verify_spec(task, attempt_dir, verify_dir)
    out_rel = run['archive']['archive_path']
    out_ctr = '/results/' + out_rel
    expected_ctr = '/repo/' + str((PAYLOAD / f'tasks/{task}/seed/root/tmp/docs/expected.json')
                                  .resolve().relative_to(ROOT.resolve()))
    pre_sha = {str(p): sha_file(p) for p in delivered}
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
        "out = {'errors': rep['errors'], 'passed': rep['passed'], 'measured': rep.get('measured')}\n"
        "json.dump(out, open('/report/report.json', 'w'))\n"
        "print(json.dumps(out))\n"
    )
    create += ['-c', script]
    cid = subprocess.check_output(create, text=True, timeout=60).strip()
    inspect = json.loads(subprocess.check_output(
        ['docker', '--host', 'unix:///var/run/docker.sock', 'inspect', cid], text=True))[0]
    actual_mounts = [{'destination': m['Destination'], 'source': m['Source'], 'rw': m['RW']}
                     for m in inspect['Mounts']]
    log = verify_dir / 'post-verify.log'
    with log.open('w') as fh:
        cp = subprocess.run(['docker', 'start', '-a', cid], stdout=fh,
                            stderr=subprocess.STDOUT, timeout=600)
    post_sha = {str(p): sha_file(p) for p in delivered}
    result = {'rc': cp.returncode, 'mounts': actual_mounts, 'mounts_planned': mounts_evidence,
              'container_id': cid,
              'pre_sha': pre_sha, 'post_sha': post_sha,
              'delivered_unchanged': pre_sha == post_sha,
              'log': log.read_text()[-4000:]}
    report = {}
    try:
        report = json.loads((verify_dir / 'report.json').read_text())
    except Exception as exc:
        report = {'parse_error': f'{type(exc).__name__}: {exc}'}
    result['report'] = report
    result['report_path'] = str((verify_dir / 'report.json').relative_to(ROOT))
    return result


# ---------------------------------------------------------------------------
# Resume / attempt policy (F7): never delete evidence or rerun completed work.
# ---------------------------------------------------------------------------

def decide_action(state: dict, task: str) -> tuple[str, str | None]:
    """Return ('reuse'|'reverify'|'run', attempt_dir or None).

    A completed workload is never rerun: if its offline re-check already passed
    -> reuse; if it did not pass (or was never attempted) -> re-check only. Only
    when no completed workload exists is a new workload attempt started (always
    in a NEW directory/container).
    """
    task_state = state.get('tasks', {}).get(task)
    if not task_state:
        return 'run', None
    attempts = task_state.get('attempts', [])
    if not attempts:
        return 'run', None
    last = attempts[-1]
    if last.get('workload') != 'passed':
        return 'run', None
    if verify_report_ok(last.get('verify') or {}):
        return 'reuse', last.get('dir')
    return 'reverify', last.get('dir')


def attempt_archive_problems(task: str, attempt_dir) -> list[str]:
    """Full bindings check of an existing completed attempt's archived evidence:
    archive directory/round, per-step success, artifact size+sha, recipe /
    input / expected / image identity. Returns explicit problems (empty when ok)."""
    if attempt_dir is None:
        return ['attempt dir missing']
    ad = Path(attempt_dir)
    result = ad / 'results' / task
    if not result.is_dir():
        return ['archive results dir missing']
    rounds = sorted([r for r in result.iterdir() if r.is_dir() and r.name.startswith('round-')])
    if not rounds:
        return ['no round directory in archive']
    run_path = rounds[0] / 'run.json'
    if not run_path.is_file():
        return ['round run.json missing']
    problems = []
    run = json.loads(run_path.read_text())
    if run.get('status') != 'completed':
        problems.append('round not completed')
    if run.get('successes') != 1 or run.get('failures'):
        problems.append('round not successful')
    for step in run.get('steps', []):
        if step.get('status') != 'ok' or step.get('rc') != 0:
            problems.append(f"round step {step.get('id')} not ok")
    archive = run.get('archive', {})
    artifact = (ad / 'results' / archive.get('archive_path', '')).resolve()
    if not artifact.is_file():
        problems.append('archive artifact missing')
    else:
        if artifact.stat().st_size != archive.get('bytes'):
            problems.append('archive artifact size mismatch')
        if sha(artifact) != archive.get('sha256'):
            problems.append('archive artifact sha mismatch')
    if run.get('recipe_sha256') != sha(PAYLOAD / 'tasks' / task / 'recipe.json'):
        problems.append('recipe binding mismatch')
    expected_file = PAYLOAD / f'tasks/{task}/seed/root/tmp/docs/expected.json'
    if run.get('expected_sha256') is not None and run.get('expected_sha256') != sha(expected_file):
        problems.append('expected binding mismatch')
    recipe = json.loads((PAYLOAD / 'tasks' / task / 'recipe.json').read_text())
    record_path = ad / 'attempt-record.json'
    if not record_path.is_file():
        problems.append('attempt record missing (input/image identity unverifiable)')
    else:
        attempt_rec = json.loads(record_path.read_text())
        if attempt_rec.get('image_id') != EXPECTED_IMAGE_ID:
            problems.append('image identity mismatch')
        if attempt_rec.get('input_sha256') != recipe['synthetic_variant']['input_sha256']:
            problems.append('input binding mismatch')
    return problems


def bindings_ok(task: str, attempt_dir) -> bool:
    return not attempt_archive_problems(task, attempt_dir)


# ---------------------------------------------------------------------------
# Workload run (F7): new attempt dir + new unique container, never delete.
# ---------------------------------------------------------------------------

def run_task(task: str, image_id: str, campaign_dir: Path) -> tuple[Path, dict]:
    folder = campaign_dir / task
    attempt_dir = new_attempt_dir(folder)
    results_root = attempt_dir / 'results'
    results_root.mkdir()
    record = dict(task=task, status='running', loops=1,
                  image_id=image_id, image_tag=IMAGE_TAG,
                  recipe_sha256=sha(PAYLOAD / 'tasks' / task / 'recipe.json'))
    cid = None
    try:
        argv = [INTERPRETER, '-B', '/opt/docops/replay.py', 'run',
                '--payload', INSTALLED_PAYLOAD,
                '--workdir', '/workspace/docops/work',
                '--results-dir', '/results',
                '--task', task, '--loops', '1', '--step-timeout', str(STEP_TIMEOUT)]
        name = f'docops-reviewed-{task}-{campaign_dir.name.lower()}-{attempt_dir.name.lower()}'
        create = DOCKER + ['create', '--name', name, '--network', 'none',
                  '--cpuset-cpus', '0-9', '--cap-add', 'PERFMON', '--cap-add', 'SYS_PTRACE',
                  '--security-opt', 'seccomp=unconfined',
                  '-v', str(results_root) + ':/results',
                  '--entrypoint', argv[0], image_id, *argv[1:]]
        cid = subprocess.check_output(create, text=True, timeout=60).strip()
        record.update(container_id=cid, create_argv=create)
        before = json.loads(subprocess.check_output(
            ['docker', '--host', 'unix:///var/run/docker.sock', 'inspect', cid], text=True))[0]
        write(attempt_dir / 'container-before.json', before)
        assert before['Image'] == image_id
        assert before['HostConfig']['NetworkMode'] == 'none'
        assert before['HostConfig'].get('CpusetCpus') == '0-9'
        assert {m['Destination'] for m in before['Mounts']} == {'/results'}
        assert next(m['RW'] for m in before['Mounts']) is True  # results must be writable for the workload
        with (attempt_dir / 'container.log').open('w') as log:
            cp = subprocess.run(['docker', 'start', '-a', cid], stdout=log,
                                stderr=subprocess.STDOUT, timeout=HOST_TIMEOUT)
        after = json.loads(subprocess.check_output(
            ['docker', '--host', 'unix:///var/run/docker.sock', 'inspect', cid], text=True))[0]
        write(attempt_dir / 'container-after.json', after)
        record.update(docker_returncode=cp.returncode, container_exit_code=after['State']['ExitCode'])
        assert cp.returncode == 0 and after['State']['ExitCode'] == 0, 'workload failed'

        summary = json.loads((results_root / task / 'summary.json').read_text())
        counts = {k: summary[k] for k in ('requested', 'completed', 'successes', 'failures')}
        assert counts == dict(requested=1, completed=1, successes=1, failures=0), counts
        rounds = [r for r in (results_root / task).iterdir() if r.is_dir() and r.name.startswith('round-')]
        assert len(rounds) == 1
        run = json.loads((rounds[0] / 'run.json').read_text())
        assert run['completed'] and run['successes'] == 1 and not run['failures']
        assert all(s['status'] == 'ok' and s['rc'] == 0 for s in run['steps'])
        assert run['recipe_sha256'] == record['recipe_sha256']
        archive = run['archive']
        artifact = (results_root / archive['archive_path']).resolve()
        assert artifact.is_file() and artifact.stat().st_size == archive['bytes'] > 0
        assert sha(artifact) == archive['sha256']
        record.update(round_id=rounds[0].name, summary=counts, roi_wall_s=run['roi_wall_s'],
                      steps=run['roi_steps'], output=archive,
                      input_sha256=recipe_input_sha(task))
        subprocess.run(['docker', 'cp', f'{cid}:/root/tmp/docs', str(attempt_dir / 'workspace-docs')],
                       check=True, timeout=120)
        record.update(status='passed')
    except BaseException as exc:
        record.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        if cid:
            subprocess.run(['docker', 'stop', '-t', '3', cid], capture_output=True, timeout=30)
    finally:
        write(attempt_dir / 'attempt-record.json', record)
    return attempt_dir, record


# ---------------------------------------------------------------------------
# Index / finalize (F6): files final before hashing; readback verified in a
# separate excluded record; no post-index modification of indexed files.
# ---------------------------------------------------------------------------

INDEX_EXCLUDED = {'campaign.sha256-index.json', 'campaign.index-verification.json',
                  'campaign.json'}  # mutable manifest, written final-but-after readback logic


def readback_index(campaign: Path, index_path: Path, indexed: dict) -> list[str]:
    failures = []
    for rel, row in indexed.items():
        p = (campaign / rel).resolve()
        if not p.is_relative_to(campaign.resolve()):
            failures.append(rel + ': path escapes campaign')
            continue
        if p.stat().st_size != row['bytes'] or sha_file(p) != row['sha256']:
            failures.append(rel)
    return failures


def verify_existing_index(campaign: Path) -> tuple[bool, list[str]]:
    """Re-read an existing campaign index against the current files (read-only)."""
    index_path = campaign / 'campaign.sha256-index.json'
    if not index_path.is_file():
        return False, ['index file missing']
    entry = json.loads(index_path.read_text())
    failures = readback_index(campaign, index_path, entry.get('files', {}))
    return (not failures), failures


def index_campaign(campaign: Path, state: dict) -> None:
    """Write a SHA256 index over every indexed campaign file, then actually
    read it back. The verification result is recorded in a SEPARATE excluded
    record only after a successful full readback; indexed files are never
    modified after the index is written."""
    indexed = {}
    for p in sorted(campaign.rglob('*')):
        if not p.is_file():
            continue
        rel = p.relative_to(campaign)
        if rel.name in INDEX_EXCLUDED:
            continue
        indexed[rel.as_posix()] = {'bytes': p.stat().st_size, 'sha256': sha_file(p)}
    state['index'] = {'path': 'campaign.sha256-index.json', 'files_indexed': len(indexed)}
    write(campaign / 'campaign.json', state)
    index_path = campaign / 'campaign.sha256-index.json'
    index_path.write_text(json.dumps(
        {'schema': 'docops-reviewed-index-v1', 'files': indexed}, indent=2) + '\n',
        encoding='utf-8')
    index_sha = sha_file(index_path)
    failures = readback_index(campaign, index_path, indexed)
    verification = {
        'schema': 'docops-reviewed-index-verification-v1',
        'index_sha256': index_sha,
        'files_checked': len(indexed),
        'status': 'passed' if not failures else 'failed',
        'failures': failures[:100],
        'checked_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'index_covers': 'Every immutable evidence file under the campaign is indexed '
                        '(attempt records, container inspect, results, workspace-docs, '
                        'verify reports). The index excludes only the mutable manifest '
                        'campaign.json, the index file itself, and this verification '
                        'record (documented exclusions; no self-reference).',
    }
    (campaign / 'campaign.index-verification.json').write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if failures:
        state['status'] = 'failed'
        state['index_failure'] = verification
        write(campaign / 'campaign.json', state)


def _sha_of(path: Path) -> str:
    return sha_file(path)


def _fail_campaign(campaign: Path, state: dict, task: str, problems: list) -> int:
    state['status'] = 'failed'
    state['stopped_at'] = task
    state['task_failure'] = {task: problems}
    write(campaign / 'campaign.json', state)
    print(json.dumps({'status': 'failed', 'task': task, 'problems': problems},
                     ensure_ascii=False), flush=True)
    return 1


def process_one_task(task: str, campaign: Path, state: dict, frozen_ok: bool) -> int:
    """Run one task under the acceptance gate.

    Returns 0 when the task is accepted, 1 when the campaign must fail. A
    completed workload is never rerun: archive bindings are checked first; if
    only the offline re-check is missing/failed, the task is re-verified
    (post_verify only); reuse additionally requires the verify report, the
    render evidence and a valid campaign archive index.
    """
    action, attempt_dir = decide_action(state, task)
    if action == 'run':
        print(f'RUN START {task}', flush=True)
        attempt_dir, record = run_task(task, EXPECTED_IMAGE_ID, campaign)
        attempt_state = {'dir': str(attempt_dir), 'workload': record['status'],
                         'record': record}
        state['tasks'].setdefault(task, {'attempts': []})['attempts'].append(attempt_state)
        write(campaign / 'campaign.json', state)
        if record['status'] != 'passed':
            return _fail_campaign(campaign, state, task,
                                  ['workload failed: ' + str(record.get('error'))])
        verify = post_verify(task, attempt_dir, campaign)
        render_problems = render_contract_problems(task, attempt_dir)
        attempt_state['verify'] = verify
        attempt_state['render_problems'] = render_problems
        write(campaign / 'campaign.json', state)
        problems = acceptance_problems(task, record, verify, render_problems,
                                       frozen_ok, bindings_ok(task, attempt_dir))
        state['tasks'][task] = {'attempts': state['tasks'][task]['attempts'],
                                'accepted': not problems, 'problems': problems}
        write(campaign / 'campaign.json', state)
        print(f"RUN END {task} problems={problems}", flush=True)
        if problems:
            return _fail_campaign(campaign, state, task, problems)
        return 0

    # workload already passed: never rerun it.
    ad = Path(attempt_dir)
    last = state['tasks'][task]['attempts'][-1]
    record = last.get('record') or {}
    archive_problems = attempt_archive_problems(task, ad)
    if archive_problems:
        return _fail_campaign(campaign, state, task,
                              ['reuse blocked: ' + '; '.join(archive_problems)])
    verify = last.get('verify') or {}
    render_problems = render_contract_problems(task, ad)
    if not verify_report_ok(verify) or render_problems:
        # offline re-check only (workload not rerun, no deletion).
        print(f'RE-VERIFY {task} (workload not rerun)', flush=True)
        verify = post_verify(task, ad, campaign)
        render_problems = render_contract_problems(task, ad)
        last['verify'] = verify
        last['render_problems'] = render_problems
        write(campaign / 'campaign.json', state)
        problems = acceptance_problems(task, record, verify, render_problems,
                                       frozen_ok, bindings_ok(task, ad))
        state['tasks'][task] = {'attempts': state['tasks'][task]['attempts'],
                                'accepted': not problems, 'problems': problems}
        write(campaign / 'campaign.json', state)
        if problems:
            return _fail_campaign(campaign, state, task, problems)
        return 0

    # reuse: full acceptance gate including the campaign archive index.
    idx_ok, idx_failures = verify_existing_index(campaign)
    idx_problems = [] if idx_ok else ['campaign archive index: ' + '; '.join(idx_failures)]
    problems = acceptance_problems(task, record, verify, render_problems,
                                   frozen_ok, bindings_ok(task, ad)) + idx_problems
    state['tasks'][task] = {'attempts': state['tasks'][task]['attempts'],
                            'accepted': not problems, 'problems': problems}
    write(campaign / 'campaign.json', state)
    if problems:
        return _fail_campaign(campaign, state, task, problems)
    print(f'REUSE PASSED {task}', flush=True)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign-dir', required=True, type=Path)
    parser.add_argument('--preflight-only', action='store_true')
    parser.add_argument('--resume', action='store_true')
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
        state.pop('stopped_at', None)
        state.pop('task_failure', None)
        state['resume_count'] = state.get('resume_count', 0) + 1
        write(campaign / 'campaign.json', state)
    else:
        if campaign.exists():
            raise ValueError('refusing to reuse existing campaign: ' + str(campaign))
        campaign.mkdir(parents=True)
        state = dict(schema='docops-reviewed-functional-v1', status='preflight',
                     created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     image_tag=IMAGE_TAG, image_id=EXPECTED_IMAGE_ID,
                     installed_payload=INSTALLED_PAYLOAD,
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

    # Frozen-material consistency is checked for EVERY invocation (new, resume,
    # reverify-only, reuse-only) before any task work.
    frozen_problems = frozen_consistency_problems(state)
    frozen_ok = not frozen_problems
    if frozen_problems:
        state['status'] = 'failed'
        state['frozen_problems'] = frozen_problems
        write(campaign / 'campaign.json', state)
        print(json.dumps({'status': 'failed', 'frozen_problems': frozen_problems},
                         ensure_ascii=False), flush=True)
        return 1

    selected = state.get('selected_tasks') or list(TASKS)
    try:
        for task in selected:
            if process_one_task(task, campaign, state, frozen_ok) != 0:
                return 1
        else:
            # Final success: recompute frozen materials and require consistency
            # with the frozen baseline before entering the passed state.
            state['frozen_after'] = frozen_snapshot()
            final_problems = frozen_consistency_problems(state)
            if final_problems:
                state['status'] = 'failed'
                state['frozen_problems'] = final_problems
                write(campaign / 'campaign.json', state)
                print(json.dumps({'status': 'failed', 'frozen_problems': final_problems},
                                 ensure_ascii=False), flush=True)
                return 1
            state['status'] = 'passed'
            write(campaign / 'campaign.json', state)
            index_campaign(campaign, state)
            if state['status'] != 'passed':
                return 1
    except BaseException as exc:
        state.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        write(campaign / 'campaign.json', state)
        return 1
    print(json.dumps({'status': state['status'], 'campaign': str(campaign),
                      'tasks': {k: v.get('accepted', not v.get('problems'))
                                for k, v in state.get('tasks', {}).items()},
                      'error': state.get('error'), 'stopped_at': state.get('stopped_at')},
                     ensure_ascii=False), flush=True)
    return 0 if state['status'] == 'passed' else 1


def preflight(campaign_dir: Path) -> dict:
    result = {'status': 'running'}
    image = json.loads(docker('image', 'inspect', IMAGE_TAG).stdout)[0]
    result['image_tag'] = IMAGE_TAG
    result['image_id'] = image['Id']
    result['image_id_matches_expected'] = image['Id'] == EXPECTED_IMAGE_ID
    result['installed_payload'] = INSTALLED_PAYLOAD
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
        result['image_id_matches_expected'] and result['selected_are_subset_of_24']
    ) else 'failed'
    return result


if __name__ == '__main__':
    raise SystemExit(main())
