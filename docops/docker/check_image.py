"""Installed-image check only: no real task and no profiler is launched."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid


PROBE = r'''
import hashlib, importlib.util, json, os, pathlib, runpy, tempfile
root = pathlib.Path('/opt/docops')
paths = {'replay.py': root/'replay.py', 'compile.py': root/'compile.py',
         'docker/install_state_check.py': root/'docker/install_state_check.py',
         'docker/devkit.sh': pathlib.Path('/usr/local/bin/devkit')}
if (root/'runtime-profile.json').exists():
    paths['docker/runtime-profile.json'] = root/'runtime-profile.json'
hashes = {k: hashlib.sha256(v.read_bytes()).hexdigest() for k,v in paths.items()}
spec = importlib.util.spec_from_file_location('replay_image_probe', root/'replay.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
recipe = json.loads((root/'payload/tasks/031/recipe.json').read_text())
assert '/root' not in m.task_scoped_paths(recipe)
with tempfile.TemporaryDirectory(prefix='docops-install-fixture-') as temporary:
    os.environ['DOC_REPLAY_ROOT'] = temporary
    base = pathlib.Path(temporary)
    sentinel = base/'root/.codex/skills/pdf/SKILL.md'
    sentinel.parent.mkdir(parents=True); sentinel.write_text('preserved')
    m.reset_workspace(recipe)
    assert sentinel.read_text() == 'preserved'
    first, second = m.WorkLock(base/'one'), m.WorkLock(base/'two')
    try:
        assert first.acquire()
        assert not second.acquire()
    finally:
        first.release(); second.release()
    font = base/'root/.local/share/fonts/Aptos-regular.ttf'
    font.parent.mkdir(parents=True); font.write_text('original')
    snapshot = m.snapshot_environment(base/'scratch', {'task':'fixture', 'steps':[{'phase':'environment_setup'}]})
    font.write_text('changed'); added = font.parent/'AptosDisplay-bold.ttf'; added.write_text('new')
    m.restore_fonts(snapshot)
    assert font.read_text() == 'original' and not added.exists()
    del os.environ['DOC_REPLAY_ROOT']
pathlib.Path('/results/runtime-sources.json').write_text(json.dumps({'sha256':hashes,'small_fixtures':'passed'}))
runpy.run_path(str(root/'docker/install_state_check.py'), run_name='__main__')
'''


def docker(*args, check=True):
    return subprocess.run(['docker', '--host', 'unix:///var/run/docker.sock', *args],
                          check=check, capture_output=True, text=True, timeout=180)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--build-record-dir', type=Path, required=True)
    args = parser.parse_args()
    records = args.build_record_dir.resolve()
    output = records / 'installation'
    output.mkdir(exist_ok=False)
    result = {'schema': 'docops-inspected-installation-v1', 'status': 'failed',
              'real_workload_executed': False, 'profiling_started': False}
    container = None
    try:
        expected = json.loads((records/'build-inputs.json').read_text())
        image = json.loads(docker('image', 'inspect', args.image).stdout)[0]
        image_id = image['Id']
        assert image_id == (records/'image-id.txt').read_text().strip(), 'build/image identity mismatch'
        result.update(image_reference=args.image, actual_image_id=image_id)
        (output/'image-inspect.json').write_text(json.dumps(image, indent=2)+'\n')
        name = 'docops-install-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        container = docker('create', '--name', name, '--network', 'none',
                           '-v', f'{output}:/results', '-e', 'DOC_INSTALL_STATE_OUT=/results/install-state.json',
                           '-e', f'DOC_IMAGE_REFERENCE={args.image}',
                           '--entrypoint', 'python3', image_id, '-B', '-c', PROBE).stdout.strip()
        before = json.loads(docker('inspect', container).stdout)[0]
        (output/'container-before.json').write_text(json.dumps(before, indent=2)+'\n')
        assert before['Image'] == image_id and before['HostConfig']['NetworkMode'] == 'none'
        assert len(before['Mounts']) == 1 and before['Mounts'][0]['Destination'] == '/results'
        assert Path(before['Mounts'][0]['Source']).resolve() == output
        execution = docker('start', '-a', container, check=False)
        (output/'container.log').write_text(execution.stdout + execution.stderr)
        after = json.loads(docker('inspect', container).stdout)[0]
        (output/'container-after.json').write_text(json.dumps(after, indent=2)+'\n')
        result.update(container_id=container, container_name=name,
                      container_exit_code=after['State']['ExitCode'])
        assert execution.returncode == 0 and after['State']['Status'] == 'exited' and after['State']['ExitCode'] == 0, 'container check failed; see container.log'
        installation = json.loads((output/'install-state.json').read_text())
        assert installation['status'] == 'passed' and not installation['errors'], 'installed-state check failed'
        sources = json.loads((output/'runtime-sources.json').read_text())
        for path, actual in sources['sha256'].items():
            assert expected['source_sha256'][path] == actual, f'runtime/source mismatch: {path}'
        assert expected['payload_index_sha256'] == hashlib.sha256(
            (Path(__file__).resolve().parents[1]/'payload/payload-index.json').read_bytes()).hexdigest()
        result.update(status='passed', environment=installation['environment'],
                      tools=installation['extra'], small_fixtures=sources['small_fixtures'],
                      source_binding='image bytes match frozen build inputs')
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
        if container:
            docker('stop', '-t', '2', container, check=False)
    finally:
        result['files'] = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(output.rglob('*')) if p.is_file()}
        (output/'acceptance.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'status': result['status'], 'record': str(output/'acceptance.json'),
                      'image_id': result.get('actual_image_id'), 'error': result.get('error')}, ensure_ascii=False))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
