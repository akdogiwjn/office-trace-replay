"""Build a NEW offline unified-runtime image, without replacing earlier tags."""
import argparse
import datetime
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

from verify_build_inputs import sha, verify_tree

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
DOCKER = ['docker', '--host', 'unix:///var/run/docker.sock']


def docker(*args, **kwargs):
    return subprocess.run(DOCKER + list(args), check=True, text=True, **kwargs)


def image(reference):
    return json.loads(docker('image', 'inspect', reference, capture_output=True).stdout)[0]


def require_unused(tag):
    probe = subprocess.run(DOCKER+['image', 'inspect', tag], capture_output=True, text=True)
    if probe.returncode == 0:
        raise ValueError('refusing to overwrite existing image tag: '+tag)
    if 'No such image' not in probe.stderr and 'No such object' not in probe.stderr:
        raise RuntimeError('cannot verify tag absence: '+probe.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    profile = json.loads((ROOT/'docker/runtime-profile.json').read_text())
    base = image(profile['base_reference'])
    assert base['Id'] == profile['base_id'], 'base tag identity changed'
    assert (base['Os'], base['Architecture']) == ('linux', 'arm64')
    require_unused(args.image)
    spec = importlib.util.spec_from_file_location('unified_compile', ROOT/'compile.py')
    compile_module = importlib.util.module_from_spec(spec); spec.loader.exec_module(compile_module)
    payload = compile_module.validate_payload(ROOT/'payload')
    vendor_manifest = ROOT/'vendor/unified-sha256.json'
    manifest = json.loads(vendor_manifest.read_text())
    verify_tree(ROOT/'vendor/unified', manifest['files'], 'file')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-unified-'+uuid.uuid4().hex[:8]
    records = ROOT/'docker/records'/stamp; records.mkdir()
    shutil.copy2(vendor_manifest, records/'vendor-manifest.json')
    source_paths = ['replay.py', 'compile.py', 'docker/install_state_check.py', 'docker/devkit.sh',
                    'docker/Dockerfile.unified', 'docker/build_unified.py', 'docker/check_image.py',
                    'docker/runtime-profile.json', 'docker/core_identity.py',
                    'docker/smoke_unified.py', 'docker/docops-runtime.sh', 'docker/soffice-unified',
                    'docker/verify_build_inputs.py']
    inputs = {'schema': 'docops-offline-unified-build-inputs-v1', 'payload': payload,
              'base_image_id': base['Id'], 'runtime_profile': profile,
              'source_sha256': {p: sha(ROOT/p) for p in source_paths},
              'payload_index_sha256': sha(ROOT/'payload/payload-index.json'),
              'vendor_manifest_sha256': sha(vendor_manifest)}
    baseline = docker('run', '--rm', '--network', 'none', '--entrypoint', 'python3', base['Id'],
                      '-B', '-c', (ROOT/'docker/core_identity.py').read_text(), capture_output=True)
    core = json.loads(baseline.stdout)
    (records/'core-baseline.json').write_text(json.dumps(core, indent=2)+'\n')
    inputs['core_baseline_sha256'] = sha(records/'core-baseline.json')
    (records/'base-inspect.json').write_text(json.dumps(base, indent=2)+'\n')
    dk = REPO/'analysis/topdown/tools/DevKit-Tuner-CLI-26.0.RC1-Linux-aarch64'
    assert (dk/'devkit').is_file() and (dk/'tuner/libtuner.so').is_file()
    inputs['devkit_sha256'] = {str(p.relative_to(dk)): sha(p) for p in sorted(dk.rglob('*')) if p.is_file()}
    (records/'build-inputs.json').write_text(json.dumps(inputs, indent=2)+'\n')
    print('BUILD_RECORD '+str(records.relative_to(REPO)), flush=True)
    with tempfile.TemporaryDirectory(prefix='docops-unified-build-') as tmp:
        context = Path(tmp)
        for name in ('replay.py', 'compile.py'):
            shutil.copy2(ROOT/name, context/name)
        for name in ('install_state_check.py', 'devkit.sh', 'runtime-profile.json', 'core_identity.py',
                     'smoke_unified.py', 'docops-runtime.sh', 'soffice-unified'):
            shutil.copy2(ROOT/'docker'/name, context/name)
        shutil.copy2(ROOT/'docker/Dockerfile.unified', context/'Dockerfile')
        shutil.copy2(records/'core-baseline.json', context/'core-baseline.json')
        shutil.copytree(ROOT/'payload', context/'payload')
        shutil.copytree(ROOT/'vendor/unified/wheels', context/'vendor/wheels')
        shutil.copytree(ROOT/'vendor/unified/rpms', context/'vendor/rpms')
        shutil.copytree(ROOT/'vendor/unified/bin', context/'vendor/bin')
        shutil.copytree(ROOT/'vendor/unified/fonts', context/'vendor/fonts')
        shutil.copy2(ROOT/'vendor/unified/requirements.lock', context/'requirements.lock')
        shutil.copytree(dk, context/'devkit'/dk.name)
        with (records/'build.log').open('x') as log:
            docker('build', '--pull=false', '--network', 'none', '--build-arg',
                   'BASE_IMAGE='+profile['base_reference'], '--iidfile', str(records/'image-id.txt'),
                   str(context), stdout=log, stderr=subprocess.STDOUT)
    assert image(profile['base_reference'])['Id'] == profile['base_id'], 'base changed during build'
    require_unused(args.image)
    iid = (records/'image-id.txt').read_text().strip()
    docker('tag', iid, args.image)
    (records/'image-inspect.json').write_text(json.dumps(image(args.image), indent=2)+'\n')
    (records/'candidate-image.json').write_text(json.dumps({
        'candidate_tag': args.image, 'candidate_id': iid, 'base_image_id': base['Id'],
        'runtime_profile': profile['id'], 'real_workload_executed': False,
        'profiling_started': False}, indent=2)+'\n')
    print(json.dumps({'image': args.image, 'id': iid, 'records': str(records.relative_to(REPO))}), flush=True)


if __name__ == '__main__':
    main()
