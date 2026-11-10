"""Host-side formal functional campaign for the four Word/PDF scale variants.

Runs one replay round (loops=1) per variant, strictly serial and confirmed in
order: 003-u5, 037-u5 (small), then 003-u20, 037-u20 (large). Each run uses a
fresh, uniquely named, retained (no --rm), offline (network=none) container
created from the exact image ID. No perf/DevKit, no agent, no image build, no
official report update.

This driver only launches, archives and verifies functional results; it draws no
performance conclusions.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

IMAGE_TAG = 'docops-replay:openeuler-unified-candidate-04'
EXPECTED_IMAGE_ID = 'sha256:57483856a27942ffd4aef853950ca66b00c12b0787aae6c1dac74371d03e6164'
PAYLOAD = ROOT / 'docops/scaling/payload-word-pdf'
REPLAY_PY = ROOT / 'docops/replay.py'
COMPILE_PY = ROOT / 'docops/compile.py'
OFFICIAL_PAYLOAD = ROOT / 'docops/payload'
ROUND1_PAYLOAD = ROOT / 'docops/scaling/payload'
INTERPRETER = '/opt/docops/venv/bin/python3'
TASKS = ['003-u100', '003-u500', '037-u5', '037-u20']
STEP_TIMEOUT = 3600
HOST_TIMEOUT = 10800  # generous margin covering execution + archive


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def docker(*args, **kwargs):
    return subprocess.run(['docker', *args], check=True, capture_output=True,
                          text=True, timeout=60, **kwargs)


def docker_out(*args, **kwargs):
    return subprocess.check_output(['docker', *args], text=True, timeout=60, **kwargs)


def create_clean(name: str, *create_args) -> str:
    """Create a uniquely-named container, first removing any stale same-name
    container (stopped helper containers or failed-run containers being retried).
    Completed successful run containers are never recreated: passed tasks are
    reused by the campaign driver, not re-run."""
    existing = docker('ps', '-aq', '--filter', f'name=^{name}$').stdout.strip().splitlines()
    for cid in existing:
        docker('rm', '-f', cid)
    return docker('create', '--name', name, *create_args).stdout.strip()


def tree_sha(root: Path) -> str:
    files = sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file())
    h = hashlib.sha256()
    for rel in files:
        h.update(rel.encode())
        h.update(b'\0')
        h.update((root / rel).read_bytes())
        h.update(b'\0')
    return h.hexdigest()


def load_compile_validate():
    spec = importlib.util.spec_from_file_location('docops_compile', COMPILE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.validate_payload


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
    binding = {}
    for task in TASKS:
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
            for flag in ('--structure-only', '--skip', '--fixture', '--dry-run'):
                if flag in s['argv'][2]:
                    problems.append(f'formal command contains {flag}')
        for name in ('expected.json',):
            exp = recipe['files']
        expected_sha = sv['expected_sha256']
        material = 'units.json' if task.startswith('003') else 'notices.json'
        material_sha = sha(PAYLOAD / 'tasks' / task / 'seed/root/tmp/docs' / material)
        binding[task] = {
            'ok': not problems, 'problems': problems,
            'recipe_sha256': sha(PAYLOAD / 'tasks' / task / 'recipe.json'),
            'input_sha256': sv['input_sha256'],
            'expected_sha256': expected_sha,
            f'{material}_sha256': material_sha,
            'steps': [s['name'] for s in recipe['steps']],
        }
    result['binding'] = binding
    result['binding_all_ok'] = all(b['ok'] for b in binding.values())

    image = json.loads(docker('image', 'inspect', IMAGE_TAG).stdout)[0]
    result['image_tag'] = IMAGE_TAG
    result['image_id'] = image['Id']
    result['image_id_matches_expected'] = image['Id'] == EXPECTED_IMAGE_ID

    # Environment probe via a retained offline container with the exact mounts.
    probe_argv = [INTERPRETER, '-B', '/opt/docops/replay.py', 'validate-only',
                  '--payload', '/opt/docops/scaling/payload', '--env-check',
                  '--workdir', '/workspace/docops/work']
    name = 'docops-wp-precheck-' + campaign_dir.name.lower()
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
        env_errors = parsed.get('environment_errors', [])
        result['precheck_env_errors'] = env_errors
        result['precheck_payload_status'] = parsed.get('payload', {}).get('status')
    except Exception as exc:
        result['precheck'] = {'parse_error': f'{type(exc).__name__}: {exc}'}
        result['precheck_env_errors'] = ['unparseable']
    result['payload_index_sha256'] = sha(PAYLOAD / 'payload-index.json')
    result['frozen_before'] = {
        'official_payload_tree': tree_sha(OFFICIAL_PAYLOAD),
        'round1_payload_tree': tree_sha(ROUND1_PAYLOAD),
        'official_catalog': sha(OFFICIAL_PAYLOAD / 'catalog.json'),
        'official_index': sha(OFFICIAL_PAYLOAD / 'payload-index.json'),
        'round1_index': sha(ROUND1_PAYLOAD / 'payload-index.json'),
    }
    result['status'] = 'passed' if (
        result.get('payload', {}).get('status') == 'static_valid'
        and result['binding_all_ok']
        and result['image_id_matches_expected']
        and result.get('precheck_rc') == 0
        and result.get('precheck_env_errors') == []
    ) else 'failed'
    return result


def run_task(task: str, image_id: str, campaign_dir: Path) -> dict:
    folder = campaign_dir / task
    recipe = json.loads((PAYLOAD / 'tasks' / task / 'recipe.json').read_text())
    record = dict(task=task, status='running', loops=1,
                  image_id=image_id, recipe_sha256=sha(PAYLOAD / 'tasks' / task / 'recipe.json'))
    cid = None
    try:
        argv = [INTERPRETER, '-B', '/opt/docops/replay.py', 'run',
                '--payload', '/opt/docops/scaling/payload',
                '--workdir', '/workspace/docops/work',
                '--results-dir', '/results',
                '--task', task, '--loops', '1', '--step-timeout', str(STEP_TIMEOUT)]
        name = f'docops-wp-{task}-{campaign_dir.name.lower()}'
        create = ['create', '--name', name, '--network', 'none',
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
                      input_sha256=recipe['synthetic_variant']['input_sha256'])
        # frozen input unchanged (docker cp back from workspace)
        input_name = recipe_input_name(task)
        input_dst = folder / 'verified-input'
        input_dst.mkdir(exist_ok=True)
        docker('cp', f'{cid}:/root/{input_name}', str(input_dst / input_name))
        assert sha(input_dst / input_name) == recipe['synthetic_variant']['input_sha256']
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


def post_verify(task: str, campaign_dir: Path) -> dict:
    """Re-run the frozen business validation + extra acceptance checks in a
    fresh retained offline container (reuses the frozen expected oracle and the
    case validator modules; never regenerates anything)."""
    folder = campaign_dir / task
    rounds = sorted([r for r in (folder / 'results' / task).iterdir()
                     if r.is_dir() and r.name.startswith('round-')])
    run = json.loads((rounds[0] / 'run.json').read_text())
    out_rel = run['archive']['archive_path']
    out_ctr = '/results/' + out_rel
    expected_ctr = '/repo/' + str((PAYLOAD / f'tasks/{task}/seed/root/tmp/docs/expected.json').resolve().relative_to(ROOT.resolve()))
    validator_mod = ('validate_public_packet_variant' if task.startswith('003')
                     else 'validate_bus_detour_packet_variant')
    script = (
        "import sys, json, importlib\n"
        "sys.path.insert(0, '/repo/docops')\n"
        f"out = {out_ctr!r}\n"
        f"exp = {expected_ctr!r}\n"
        f"mod = importlib.import_module('scaling.cases.{task.split('-')[0]}.scripts.{validator_mod}')\n"
        "rep = mod.check(out, exp)\n"
        "print(json.dumps({'errors': rep['errors'], 'passed': rep['passed']}))\n"
    )
    name = f'docops-wp-verify-{task}-{campaign_dir.name.lower()}'
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


def acceptance(task: str, campaign_dir: Path) -> dict:
    """Host-side extra acceptance checks (docx structure / pdf pages+bookmarks /
    PNG continuity / last-unit / 17-stop matrix) using the archived artifacts.
    PDF checks run in a retained offline container because the host python has
    no pypdf; Word structure is checked on the host with python-docx."""
    folder = campaign_dir / task
    rounds = sorted([r for r in (folder / 'results' / task).iterdir()
                     if r.is_dir() and r.name.startswith('round-')])
    run = json.loads((rounds[0] / 'run.json').read_text())
    out_ctr = '/results/' + run['archive']['archive_path']
    expected = json.loads((PAYLOAD / f'tasks/{task}/seed/root/tmp/docs/expected.json').read_text())
    docs = folder / 'workspace-docs'  # docker cp copies /root/tmp/docs contents here
    result = {'round': rounds[0].name}

    if task.startswith('003'):
        from docx import Document
        doc = Document(str((folder / 'results' / run['archive']['archive_path']).resolve()))
        paras = [p.text for p in doc.paragraphs]
        headings = [p.text for p in doc.paragraphs
                    if p.style and p.style.name in ('Title', 'Heading 1')]
        tables = doc.tables
        result['paragraphs'] = len(doc.paragraphs)
        result['tables'] = len(tables)
        result['table_rows'] = sum(len(t.rows) for t in tables)
        result['headings_match'] = headings == expected['headings']
        result['tables_match'] = len(tables) == expected['table_count']
        unit_ids = [u['id'] for u in expected['units']]
        present = [uid for uid in unit_ids if any(uid in p for p in paras)]
        result['units_all_present'] = present == unit_ids
        last = expected['units'][-1]
        last_heading = f"Unit {last['id']} — {last['category']}"
        last_table = next((t for t in tables if last['id'] in
                           ' '.join(c.text for r in t.rows for c in r.cells)), None)
        result['last_unit_heading_present'] = last_heading in headings
        result['last_unit_table_rows'] = len(last_table.rows) if last_table else 0
        result['last_unit_amount_present'] = (
            last_table is not None and f"${last['right_amount']}" in
            ' '.join(c.text for r in last_table.rows for c in r.cells))
        # rendered PNG continuity
        pngs = sorted((docs / 'rendered_v2').glob('page-*.png')) if (docs / 'rendered_v2').exists() else []
        nums = sorted(int(p.name.split('-')[1].split('.')[0]) for p in pngs)
        result['render_png_count'] = len(pngs)
        result['render_png_contiguous'] = nums == list(range(1, len(nums) + 1))
    else:
        # PDF checks need pypdf: run inside a retained offline container.
        expected_compact = {
            'total_pages': expected['total_pages'],
            'bookmark_titles': expected['bookmark_titles'],
            'bookmark_page_indexes': expected['bookmark_page_indexes'],
        }
        group17 = next((g for g in expected['groups'] if g['closed_stop_count'] == 17), None)
        route210 = next((g for g in expected['groups'] if g['route'] == 'Route 210'), None)
        group17_info = (None if group17 is None else {
            # page_start is 1-based; the matrix is the 3rd page (1-based
            # page_start+2) so its 0-based pypdf index is page_start+1.
            'matrix_page_index': group17['page_start'] + 1,
            'stop_ids': group17['stop_ids'],
            'count': group17['closed_stop_count'],
        })
        route210_info = (None if route210 is None else {
            'page_start': route210['page_start'],
            'forbidden': route210['forbidden'],
        })
        script = (
            "import sys, json, re\n"
            "from pypdf import PdfReader\n"
            "def normalized(t):\n"
            "    return re.sub(r'\\s+', ' ', t or '').strip()\n"
            "def contains_token(text, phrase):\n"
            "    return bool(re.search(r'(?<![A-Za-z0-9])' + re.escape(phrase) + r'(?![A-Za-z0-9])', text, re.I))\n"
            f"out = {out_ctr!r}\n"
            f"exp = json.loads({json.dumps(expected_compact)!r})\n"
            f"g17 = json.loads({json.dumps(group17_info)!r})\n"
            f"r210 = json.loads({json.dumps(route210_info)!r})\n"
            "r = PdfReader(out)\n"
            "out_pages = len(r.pages)\n"
            "bm = r.outline or []\n"
            "bm_titles = [normalized(item.title) for item in bm]\n"
            "bm_pages = []\n"
            "for item in bm:\n"
            "    bm_pages.append(r.get_destination_page_number(item))\n"
            "if g17:\n"
            "    page_text = normalized(r.pages[g17['matrix_page_index']].extract_text() or '')\n"
            "    g17['missing_ids'] = [sid for sid in g17['stop_ids'] if sid not in page_text]\n"
            "if r210:\n"
            "    pages = [normalized(r.pages[i].extract_text() or '') for i in range(r210['page_start']-1, r210['page_start']+4)]\n"
            "    r210['forbidden_hits'] = [p for p in r210['forbidden'] if contains_token(' '.join(pages), p)]\n"
            "print(json.dumps({\n"
            "  'pages': out_pages, 'expected_pages': exp['total_pages'],\n"
            "  'bookmarks': len(bm), 'expected_bookmarks': len(exp['bookmark_titles']),\n"
            "  'bookmark_titles_match': bm_titles == [normalized(t) for t in exp['bookmark_titles']],\n"
            "  'bookmark_pages_match': bm_pages == exp['bookmark_page_indexes'],\n"
            "  'group17': g17,\n"
            "  'route210': r210,\n"
            "}))\n"
        )
        name = f'docops-wp-accept-{task}-{campaign_dir.name.lower()}'
        cid = create_clean(name, '--network', 'none',
                     '-v', str(folder / 'results') + ':/results',
                     '--entrypoint', INTERPRETER, EXPECTED_IMAGE_ID, '-B', '-c', script)
        log = folder / 'acceptance.log'
        with log.open('w') as fh:
            cp = subprocess.run(['docker', 'start', '-a', cid], stdout=fh,
                                stderr=subprocess.STDOUT, timeout=600)
        result['rc'] = cp.returncode
        raw = log.read_text()
        try:
            rep = json.loads(raw[raw.index('{'):raw.rindex('}') + 1])
        except Exception:
            rep = {'parse_error': raw[-800:]}
        result.update(rep)
        pngs = sorted((docs / 'render_v2').glob('page-*.png')) if (docs / 'render_v2').exists() else []
        nums = sorted(int(p.name.split('-')[1].split('.')[0]) for p in pngs)
        result['render_png_count'] = len(pngs)
        result['render_png_contiguous'] = nums == list(range(1, len(nums) + 1))
        result['png_matches_pdf_pages'] = len(pngs) == result.get('pages')
        result['group17_stop_count'] = group17['closed_stop_count'] if group17 else None
        result['group17_matrix_page'] = (group17['page_start'] + 2) if group17 else None
        result['route210_present'] = route210['route'] if route210 else None
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign-dir', type=Path, required=True)
    parser.add_argument('--preflight-only', action='store_true',
                        help='stop after preflight checks (no workload run)')
    parser.add_argument('--resume', action='store_true',
                        help='continue an existing campaign, reusing already-passed tasks')
    parser.add_argument('--tasks', nargs='*', default=None,
                        help='task ids to run (default: all active Word/PDF variants)')
    args = parser.parse_args(argv)
    campaign = args.campaign_dir.resolve()
    run_tasks = list(args.tasks) if args.tasks else list(TASKS)
    unknown = set(run_tasks) - set(TASKS)
    if unknown:
        raise ValueError(f'unknown tasks: {sorted(unknown)}; active set={TASKS}')

    if args.resume:
        if not campaign.is_dir() or not (campaign / 'campaign.json').is_file():
            raise ValueError('no campaign to resume: ' + str(campaign))
        state = json.loads((campaign / 'campaign.json').read_text())
        if state.get('preflight', {}).get('status') != 'passed':
            raise ValueError('cannot resume: preflight not passed')
        state['tasks'] = {}
        state['selected_tasks'] = list(run_tasks)
        state['status'] = 'running'
        state.pop('error', None)
        state.pop('stopped_at', None)
    else:
        if campaign.exists():
            raise ValueError('refusing to reuse existing campaign: ' + str(campaign))
        campaign.mkdir(parents=True)
        stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        state = dict(schema='docops-scaling-word-pdf-functional-v1', status='preflight',
                     created_utc=stamp, image_tag=IMAGE_TAG, image_id=EXPECTED_IMAGE_ID,
                     selected_tasks=list(run_tasks), tasks={}, loops=1, step_timeout=STEP_TIMEOUT,
                     driver_sha256=sha(Path(__file__).resolve()))
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

    def already_passed(task: str) -> bool:
        rec_path = campaign / task / 'trial-record.json'
        summary_path = campaign / task / 'results' / task / 'summary.json'
        if not rec_path.is_file() or not summary_path.is_file():
            return False
        rec = json.loads(rec_path.read_text())
        if rec.get('status') != 'passed':
            return False
        summary = json.loads(summary_path.read_text())
        return {k: summary[k] for k in ('requested', 'completed', 'successes', 'failures')} == \
            dict(requested=1, completed=1, successes=1, failures=0)

    try:
        for task in run_tasks:
            if already_passed(task):
                rec = json.loads((campaign / task / 'trial-record.json').read_text())
                # Re-run only the (idempotent) verification steps against the
                # archived artifacts; never re-runs the workload.
                verify = post_verify(task, campaign)
                accept = acceptance(task, campaign)
                rec['post_verify'] = verify
                rec['acceptance'] = accept
                write(campaign / task / 'trial-record.json', rec)
                state['tasks'][task] = {
                    'status': 'passed', 'reused': True,
                    'round_id': rec.get('round_id'), 'summary': rec.get('summary'),
                    'roi_wall_s': rec.get('roi_wall_s'), 'steps': rec.get('steps'),
                    'output': rec.get('output'),
                    'post_verify': verify,
                    'acceptance': accept,
                    'error': rec.get('error'),
                }
                write(campaign / 'campaign.json', state)
                print(f'REUSE PASSED {task} roi_wall_s={rec.get("roi_wall_s")}', flush=True)
                continue
            state['active'] = task
            write(campaign / 'campaign.json', state)
            print(f'RUN START {task}', flush=True)
            record = run_task(task, EXPECTED_IMAGE_ID, campaign)
            verify = post_verify(task, campaign) if record['status'] == 'passed' else {}
            accept = acceptance(task, campaign) if record['status'] == 'passed' else {}
            record['post_verify'] = verify
            record['acceptance'] = accept
            write(campaign / task / 'trial-record.json', record)
            state['tasks'][task] = {
                'status': record['status'],
                'round_id': record.get('round_id'),
                'summary': record.get('summary'),
                'roi_wall_s': record.get('roi_wall_s'),
                'steps': record.get('steps'),
                'output': record.get('output'),
                'post_verify': verify,
                'acceptance': accept,
                'error': record.get('error'),
            }
            state['active'] = None
            write(campaign / 'campaign.json', state)
            print(f"RUN END {task} status={record['status']} roi_wall_s={record.get('roi_wall_s')}", flush=True)
            if record['status'] != 'passed':
                state['status'] = 'failed'
                state['stopped_at'] = task
                break
        else:
            state['status'] = 'passed'
    except BaseException as exc:
        state.update(status='failed', error=f'{type(exc).__name__}: {exc}')
    finally:
        state['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # frozen materials unchanged after the campaign
        state['frozen_after'] = {
            'official_payload_tree': tree_sha(OFFICIAL_PAYLOAD),
            'round1_payload_tree': tree_sha(ROUND1_PAYLOAD),
            'official_catalog': sha(OFFICIAL_PAYLOAD / 'catalog.json'),
            'official_index': sha(OFFICIAL_PAYLOAD / 'payload-index.json'),
            'round1_index': sha(ROUND1_PAYLOAD / 'payload-index.json'),
        }
        write(campaign / 'campaign.json', state)
    print(json.dumps({'status': state['status'], 'campaign': str(campaign),
                      'tasks': {k: v.get('status') for k, v in state.get('tasks', {}).items()},
                      'error': state.get('error'), 'stopped_at': state.get('stopped_at')},
                     ensure_ascii=False), flush=True)
    state['active_payload_tasks'] = list(TASKS)
    return 0 if state['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
