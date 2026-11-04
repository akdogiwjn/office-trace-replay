"""Single-loop functional trials in isolated, retained, offline containers.

No profiler or external scoring. Existing results and containers are never reused.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
DOCKER = ['docker', '--host', 'unix:///var/run/docker.sock']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    temp = path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    temp.replace(path)


def docker(*args, **kwargs):
    return subprocess.run(DOCKER+list(args), check=True, capture_output=True,
                          text=True, timeout=60, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign-dir', type=Path)
    parser.add_argument('--task', action='append')
    args = parser.parse_args()
    candidate = json.loads((ROOT/'docops/docker/current-image.json').read_text())
    image = json.loads(docker('image', 'inspect', candidate['candidate_tag']).stdout)[0]
    assert image['Id'] == candidate['candidate_id'], 'candidate tag identity changed'
    catalog = json.loads((ROOT/'docops/payload/catalog.json').read_text())
    known = {row['task'] for row in catalog['tasks']}
    tasks = args.task or sorted(known)
    if len(set(tasks)) != len(tasks) or not set(tasks) <= known:
        raise ValueError('unknown or duplicate selected tasks')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    output = args.campaign_dir or ROOT/'results/docops'/('unified-functional-'+stamp)
    output = output.resolve(); output.mkdir(parents=True, exist_ok=False)
    state = dict(schema='docops-functional-campaign-v2', status='running', tasks={},
                 selected_tasks=tasks, image_id=image['Id'], image_reference=candidate['candidate_tag'],
                 runtime_profile=candidate.get('runtime_profile'), profiling_started=False,
                 external_official_score='not_run', driver_sha256=sha(Path(__file__)),
                 payload_index_sha256=sha(ROOT/'docops/payload/payload-index.json'))
    write(output/'campaign.json', state); write(output/'image-inspect.json', image)
    print('CAMPAIGN '+str(output), flush=True)
    for task in tasks:
        folder = output/task; folder.mkdir()
        recipe_path = ROOT/'docops/payload/tasks'/task/'recipe.json'
        recipe = json.loads(recipe_path.read_text())
        record = dict(task=task, status='running', loops=1, profiling_started=False,
                      image_id=image['Id'], runtime_profile=state['runtime_profile'],
                      external_official_score='not_run', recipe_sha256=sha(recipe_path))
        cid = None
        print('START '+task, flush=True)
        try:
            argv = ['/opt/docops/venv/bin/python3', '-B', '/opt/docops/replay.py', 'run',
                    '--task', task, '--loops', '1', '--results-dir', '/results',
                    '--workdir', '/workspace/docops/work']
            create = ['create', '--name', 'docops-unified-functional-'+task+'-'+stamp.lower(),
                      '--network', 'none', '-v', str(folder)+':/results',
                      '--entrypoint', argv[0], image['Id'], *argv[1:]]
            cid = docker(*create).stdout.strip(); record.update(container_id=cid, create_argv=create)
            before = json.loads(docker('inspect', cid).stdout)[0]
            write(folder/'container-before.json', before)
            assert before['Image'] == image['Id'] and before['HostConfig']['NetworkMode'] == 'none'
            assert len(before['Mounts']) == 1 and before['Mounts'][0]['Destination'] == '/results'
            assert Path(before['Mounts'][0]['Source']).resolve() == folder
            with (folder/'container.log').open('x') as log:
                cp = subprocess.run(DOCKER+['start', '-a', cid], stdout=log,
                                    stderr=subprocess.STDOUT, timeout=1800)
            after = json.loads(docker('inspect', cid).stdout)[0]
            write(folder/'container-after.json', after)
            record.update(docker_returncode=cp.returncode, container_exit_code=after['State']['ExitCode'])
            assert cp.returncode == 0 and after['State']['ExitCode'] == 0, 'workload failed; see container.log/run.json'
            summary = json.loads((folder/task/'summary.json').read_text())
            counts = {k: summary[k] for k in ('requested', 'completed', 'successes', 'failures')}
            assert counts == dict(requested=1, completed=1, successes=1, failures=0), counts
            run = json.loads((folder/task/'round-001/run.json').read_text())
            assert run['recipe_sha256'] == record['recipe_sha256']
            assert run['payload_index_sha256'] == state['payload_index_sha256']
            assert run['completed'] and run['successes'] == 1 and not run['failures']
            assert all(step['status'] == 'ok' and step['rc'] == 0 for step in run['steps'])
            archive = run['archive']; artifact = (folder/archive['archive_path']).resolve()
            assert artifact.is_relative_to(folder) and artifact.is_file()
            assert artifact.stat().st_size == archive['bytes'] > 0 and sha(artifact) == archive['sha256']
            inputs = []
            for item in recipe['files']:
                if item['kind'] == 'input' and Path(item['destination']).suffix.lower() in ('.docx', '.xlsx', '.pptx', '.pdf'):
                    target = folder/'verified-input'/Path(item['destination']).name
                    target.parent.mkdir(exist_ok=True)
                    docker('cp', cid+':'+item['destination'], str(target))
                    assert sha(target) == item['sha256'], 'workspace source input changed'
                    inputs.append({'file': str(target.relative_to(folder)), 'sha256': sha(target)})
            # Preserve generated diagnostic JSON and rendered pages without rerunning.
            docker('cp', cid+':/root/tmp/docs', str(folder/'workspace-docs'))
            record.update(status='passed', summary=counts, roi_wall_s=run['roi_wall_s'],
                          steps=run['roi_steps'], output=archive, verified_inputs=inputs,
                          historical_official_score=recipe['historical_score'])
        except BaseException as exc:
            record.update(status='failed', error=f'{type(exc).__name__}: {exc}')
            if cid:
                subprocess.run(DOCKER+['stop', '-t', '3', cid], capture_output=True, timeout=30)
                write(folder/'container-after-failure.json', json.loads(docker('inspect', cid).stdout)[0])
        finally:
            write(folder/'trial-record.json', record)
            index = {str(p.relative_to(folder)): {'bytes': p.stat().st_size, 'sha256': sha(p)}
                     for p in sorted(folder.rglob('*')) if p.is_file()}
            write(folder/'sha256-index.json', {'files': index})
            for name, row in index.items():
                assert (folder/name).stat().st_size == row['bytes'] and sha(folder/name) == row['sha256']
            record_entry = dict(status=record['status'], record=str((folder/'trial-record.json').relative_to(ROOT)),
                                record_sha256=sha(folder/'trial-record.json'), indexed_files=len(index),
                                roi_wall_s=record.get('roi_wall_s'), error=record.get('error'))
            state['tasks'][task] = record_entry
            write(output/'campaign.json', state)
        print(task+' '+record['status'].upper()+' '+str(record.get('roi_wall_s', record.get('error'))), flush=True)
        if record['status'] != 'passed':
            break
    state['status'] = 'passed' if len(state['tasks']) == len(tasks) and all(
        r['status'] == 'passed' for r in state['tasks'].values()) else 'failed'
    state['not_started'] = [task for task in tasks if task not in state['tasks']]
    write(output/'campaign.json', state)
    print(json.dumps({'status': state['status'], 'campaign': str(output),
                      'completed': len(state['tasks']), 'not_started': state['not_started']}), flush=True)
    return 0 if state['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
