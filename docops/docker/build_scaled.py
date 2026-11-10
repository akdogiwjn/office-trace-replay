"""Build the NEW docops-replay:openeuler-scaled image from the verified unified
candidate image, without replacing earlier tags. The old image is preserved and
is never produced by docker commit from a running container.

The build copies the unified 24-variant scaling payload and the current public
replay entry into the base image, then runs the install-state acceptance
(network none, no source mounts) and records the build inputs / image identity.
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import shutil
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]      # .../docops
REPO = ROOT.parent                              # repository root (docker build context)
DOCKER = ['docker', '--host', 'unix:///var/run/docker.sock']

BASE_TAG = 'docops-replay:openeuler-unified-candidate-04'
BASE_ID = 'sha256:57483856a27942ffd4aef853950ca66b00c12b0787aae6c1dac74371d03e6164'
NEW_TAG = 'docops-replay:openeuler-scaled'
DOCKERFILE = ROOT / 'docker/Dockerfile.scaled'


def sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def docker(*args, **kwargs):
    return subprocess.run(DOCKER + list(args), check=True, capture_output=True,
                          text=True, timeout=300, **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', default=NEW_TAG)
    parser.add_argument('--force', action='store_true',
                        help='allow replacing an existing delivery tag; the replaced '
                             'image id is recorded (the old image is never deleted)')
    args = parser.parse_args()
    image = json.loads(docker('image', 'inspect', BASE_TAG).stdout)[0]
    if image['Id'] != BASE_ID:
        raise ValueError('base tag identity changed: ' + image['Id'])
    if (image['Os'], image['Architecture']) != ('linux', 'arm64'):
        raise ValueError('unexpected platform')
    probe = subprocess.run(DOCKER + ['image', 'inspect', args.tag],
                           capture_output=True, text=True)
    replaced_tag_image_id = None
    if probe.returncode == 0:
        if not args.force:
            raise ValueError('refusing to overwrite existing image tag: ' + args.tag)
        replaced_tag_image_id = json.loads(probe.stdout)[0]['Id']

    # static validation of the payload that will be installed
    spec = importlib.util.spec_from_file_location('docops_compile', ROOT / 'compile.py')
    compile_mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(compile_mod)
    scaling = compile_mod.validate_payload(ROOT / 'scaling/payload-all')
    if scaling.get('status') != 'static_valid' or scaling.get('tasks') != 24:
        raise ValueError('payload-all not static-valid 24 tasks: ' + json.dumps(scaling))
    official = compile_mod.validate_payload(ROOT / 'payload')
    if official.get('status') != 'static_valid' or official.get('tasks') != 12:
        raise ValueError('official payload not static-valid 12 tasks')

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        '%Y%m%dT%H%M%SZ') + '-scaled-' + uuid.uuid4().hex[:8]
    records = ROOT / 'docker/records' / stamp
    records.mkdir(parents=True, exist_ok=True)

    source_files = ['replay.py', 'compile.py',
                    'scaling/payload-all/payload-index.json',
                    'scaling/payload-all/catalog.json',
                    'docker/Dockerfile.scaled', 'docker/check_scaled_install.py']
    payload_all_tree = {}
    for p in sorted((ROOT / 'scaling/payload-all').rglob('*')):
        if p.is_file():
            payload_all_tree[str(p.relative_to(ROOT / 'scaling/payload-all'))] = {
                'bytes': p.stat().st_size, 'sha256': sha(p)}
    inputs = {
        'schema': 'docops-scaled-build-inputs-v1',
        'base_tag': BASE_TAG, 'base_id': BASE_ID,
        'official_payload': {'files': official.get('files'),
                             'tasks': official.get('tasks'), 'status': official.get('status')},
        'scaling_payload_all': {'files': scaling.get('files'),
                                'tasks': scaling.get('tasks'), 'status': scaling.get('status')},
        'scaling_payload_index_sha256': sha(ROOT / 'scaling/payload-all/payload-index.json'),
        'scaling_payload_all_tree': payload_all_tree,
        'source_sha256': {p: sha(ROOT / p) for p in source_files},
    }
    (records / 'build-inputs.json').write_text(
        json.dumps(inputs, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (records / 'base-inspect.json').write_text(
        json.dumps(image, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    # Pin the immutable base image in the build itself (not just the
    # separately-checked tag). BuildKit treats a bare `sha256:<id>` as a
    # registry pull, so we alias the immutable ID to a local pin tag and pass
    # that tag as BASE_IMAGE; the pin is verified to resolve to BASE_ID.
    base_pin = f'docops-replay:base-{BASE_ID[7:15]}'
    docker('tag', BASE_ID, base_pin)
    pin_after = json.loads(docker('image', 'inspect', base_pin).stdout)[0]
    if pin_after['Id'] != BASE_ID:
        raise ValueError('base pin tag did not resolve to the immutable base id')
    build = DOCKER + ['build', '-f', str(DOCKERFILE), '-t', args.tag, '--network', 'none',
                      '--build-arg', f'BASE_IMAGE={base_pin}', str(REPO)]
    inputs['base_image_arg'] = base_pin
    inputs['base_image_arg_resolves_to'] = BASE_ID
    inputs['build_argv'] = build
    (records / 'build-inputs.json').write_text(
        json.dumps(inputs, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('BUILD ' + args.tag, flush=True)
    with (records / 'build.log').open('w') as log:
        cp = subprocess.run(build, stdout=log, stderr=subprocess.STDOUT, timeout=3600)
    if cp.returncode != 0:
        raise RuntimeError('docker build failed; see build.log')

    new = json.loads(docker('image', 'inspect', args.tag).stdout)[0]
    (records / 'image-id.txt').write_text(new['Id'] + '\n')
    (records / 'image-inspect.json').write_text(
        json.dumps(new, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if new['Id'] == BASE_ID:
        raise ValueError('built image id must differ from base id')

    # Install-state acceptance: network none, no source mounts.
    probe_out = records / 'install-state.json'
    cp = subprocess.run(
        DOCKER + ['run', '--rm', '--network', 'none',
                  '--entrypoint', '/opt/docops/venv/bin/python3', new['Id'], '-B',
                  '/opt/docops/docker/check_scaled_install.py'],
        capture_output=True, text=True, timeout=1800)
    probe_out.write_text((cp.stdout + cp.stderr).replace('\n\n', '\n'))
    result = {}
    try:
        result = json.loads(cp.stdout[cp.stdout.index('{'):cp.stdout.rindex('}') + 1])
    except Exception as exc:
        result = {'parse_error': f'{type(exc).__name__}: {exc}', 'stderr': cp.stderr[-2000:]}
    (records / 'install-state.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if cp.returncode != 0 or result.get('status') != 'passed':
        raise RuntimeError('install-state acceptance failed')

    closeout = {'schema': 'docops-scaled-build-closeout-v1', 'status': 'passed',
                'tag': args.tag, 'image_id': new['Id'], 'base_id': BASE_ID,
                'replaced_tag_image_id': replaced_tag_image_id,
                'build_inputs': str((records / 'build-inputs.json').relative_to(ROOT)),
                'install_state': result,
                'finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (records / 'closeout.json').write_text(
        json.dumps(closeout, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    index = {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)}
             for p in sorted(records.iterdir()) if p.is_file()}
    (records / 'sha256-index.json').write_text(
        json.dumps({'files': index}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'passed', 'tag': args.tag, 'image_id': new['Id'],
                      'record': str(records.relative_to(ROOT))}, ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
