"""Host-side formal performance-capture campaign for the four DocOps scale variants.

Runs 8 independent captures (4 tasks x {perf, topdown}), each with one replay
round (loops=1), sequentially, using the existing verified pilot/measurement
suite with the scaling payload selected. perf and DevKit never run at the same
time; each capture gets its own container and results directory.

This driver only collects, verifies and archives; it draws no performance
conclusions.
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
import traceback
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ANALYSIS = ROOT / 'analysis' / 'docops'
sys.path.insert(0, str(ANALYSIS))

from pilot import launch, sha  # noqa: E402

VARIANTS = ['014-n1000', '014-n10000', '021-g5', '021-g10']
IMAGE_TAG = 'docops-replay:openeuler-unified-candidate-04'
EXPECTED_IMAGE_ID = 'sha256:57483856a27942ffd4aef853950ca66b00c12b0787aae6c1dac74371d03e6164'


def load_compile_validate():
    spec = importlib.util.spec_from_file_location('docops_compile', ROOT / 'docops' / 'compile.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.validate_payload


def preflight(payload: Path, campaign_dir: Path) -> dict:
    result = {'status': 'running'}
    # 1) static payload validation
    validate_payload = load_compile_validate()
    try:
        static = validate_payload(payload)
        result['payload'] = static
    except Exception as exc:
        result['payload'] = {'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'}
    # 2) per-variant binding + formal-command checks
    index = json.loads((payload / 'payload-index.json').read_text())['files']
    binding = {}
    for variant in VARIANTS:
        recipe = json.loads((payload / 'tasks' / variant / 'recipe.json').read_text())
        sv = recipe['synthetic_variant']
        ok = True
        problems = []
        for f in recipe['files']:
            if index[f['payload']]['sha256'] != f['sha256'] or index[f['payload']]['bytes'] != f['bytes']:
                ok = False
                problems.append(f'recipe file binding mismatch: {f["payload"]}')
        for s in recipe['steps']:
            body = (payload / s['shell_body']).read_text()
            if body != s['argv'][2]:
                ok = False
                problems.append(f'shell body mismatch: {s["shell_body"]}')
            if '--structure-only' in s['argv'][2]:
                ok = False
                problems.append('formal command uses --structure-only')
        if sv['parent_task'] == '021':
            cmd = (payload / 'tasks' / variant / 'commands' / '02.sh').read_text()
            if '--expected' not in cmd:
                ok = False
                problems.append('montage command missing --expected')
        binding[variant] = {'ok': ok, 'problems': problems,
                            'recipe_sha256': sha(payload / 'tasks' / variant / 'recipe.json'),
                            'input_sha256': sv['input_sha256'],
                            'expected_sha256': sv['expected_sha256']}
    result['binding'] = binding
    result['binding_all_ok'] = all(b['ok'] for b in binding.values())
    # 3) image identity
    image = json.loads(subprocess.check_output(
        ['docker', '--host', 'unix:///var/run/docker.sock', 'image', 'inspect', IMAGE_TAG], text=True))[0]
    result['image_tag'] = IMAGE_TAG
    result['image_id'] = image['Id']
    result['image_id_matches_expected'] = image['Id'] == EXPECTED_IMAGE_ID
    # 4) container environment probe (interpreter + libs + tools)
    probe = subprocess.run(
        ['docker', '--host', 'unix:///var/run/docker.sock', 'run', '--rm', '--network', 'none',
         '--entrypoint', '/opt/docops/venv/bin/python3', IMAGE_TAG, '-B', '-c',
         "import sys, openpyxl, pptx, lxml\n"
         "print('python', sys.version.split()[0])\n"
         "print('openpyxl', openpyxl.__version__)\n"
         "print('pptx', pptx.__version__)\n"
         "print('lxml', lxml.__version__)\n"],
        capture_output=True, text=True, timeout=120)
    env = {}
    for line in probe.stdout.splitlines():
        key, _, value = line.partition(' ')
        env[key] = value.strip()
    env['interpreter'] = '/opt/docops/venv/bin/python3'
    env['probe_rc'] = probe.returncode
    tools = subprocess.run(
        ['docker', '--host', 'unix:///var/run/docker.sock', 'run', '--rm', '--network', 'none',
         '--entrypoint', '/bin/bash', IMAGE_TAG, '-c',
         'perf --version 2>/dev/null | head -1; devkit --version 2>/dev/null | head -1; '
         'which python3'],
        capture_output=True, text=True, timeout=120)
    env['tools_probe'] = tools.stdout.strip()
    env['tools_probe_rc'] = tools.returncode
    result['environment'] = env
    result['payload_index_sha256'] = sha(payload / 'payload-index.json')
    result['measurement_source_sha256'] = {
        name: sha(ANALYSIS / name) for name in ('capture.py', 'worker.py', 'monitor.py',
                                               'quality.py', 'pilot.py', 'native_adapter.py')
    }
    result['status'] = 'passed' if (result.get('payload', {}).get('status') == 'static_valid'
                                     and result['binding_all_ok'] and result['image_id_matches_expected']
                                     and env.get('python') == '3.12.3') else 'failed'
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign-dir', required=True, type=Path)
    parser.add_argument('--payload', type=Path, default=HERE / 'payload')
    args = parser.parse_args(argv)
    campaign = args.campaign_dir.resolve()
    if campaign.exists():
        raise ValueError('refusing to reuse existing campaign: ' + str(campaign))
    campaign.mkdir(parents=True)
    payload = args.payload.resolve()
    created = datetime.datetime.now(datetime.timezone.utc).isoformat()
    state = dict(schema='docops-scaling-performance-campaign-v1', status='preflight',
                 created_utc=created, image_tag=IMAGE_TAG, variants=VARIANTS,
                 loops=1, captures_planned=8, tasks={}, payload=str(payload))
    state['preflight'] = preflight(payload, campaign)
    write(campaign / 'campaign.json', state)
    if state['preflight']['status'] != 'passed':
        state['status'] = 'failed'
        write(campaign / 'campaign.json', state)
        print(json.dumps({'status': state['status'], 'preflight': state['preflight']},
                         ensure_ascii=False), flush=True)
        return 1
    state['status'] = 'running'
    write(campaign / 'campaign.json', state)
    try:
        for variant in VARIANTS:
            state['tasks'][variant] = {}
            for mode in ('perf', 'topdown'):
                state['active'] = {'variant': variant, 'mode': mode}
                write(campaign / 'campaign.json', state)
                print(f'CAPTURE START {variant} {mode}', flush=True)
                record = launch(variant, 1, [mode], return_record=True,
                                payload=payload, campaign_dir=campaign,
                                workload_timeout=7200, step_timeout=3600, host_timeout=10800)
                modes = record.get('modes', {}).get(mode, {})
                collection = modes.get('collection', {}) if modes else {}
                row = {
                    'status': record.get('status'),
                    'raw': record.get('raw'),
                    'modes': modes,
                    'error': record.get('error'),
                    'counts': collection.get('counts'),
                    'roi_seconds': collection.get('roi_seconds'),
                    'roi_samples': collection.get('roi_samples'),
                    'function_qualification': collection.get('function_qualification'),
                    'metrics': collection.get('metrics'),
                    'quality': collection.get('quality'),
                }
                state['tasks'][variant][mode] = row
                state['active'] = None
                write(campaign / 'campaign.json', state)
                print(f'CAPTURE END {variant} {mode} status={row["status"]}', flush=True)
        all_passed = all(
            state['tasks'][v][m].get('status') == 'passed'
            for v in VARIANTS for m in ('perf', 'topdown')
        )
        state['status'] = 'passed' if all_passed else 'failed'
        if not all_passed:
            state['partial_failures'] = [
                (v, m) for v in VARIANTS for m in ('perf', 'topdown')
                if state['tasks'][v][m].get('status') != 'passed'
            ]
    except BaseException as exc:
        state.update(status='failed', error=f'{type(exc).__name__}: {exc}',
                     traceback=traceback.format_exc())
    finally:
        state['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write(campaign / 'campaign.json', state)
    print(json.dumps({'status': state['status'], 'campaign': str(campaign),
                      'error': state.get('error')}, ensure_ascii=False), flush=True)
    return 0 if state['status'] == 'passed' else 1


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
