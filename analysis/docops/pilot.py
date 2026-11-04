"""Host launcher for one DocOps task and selected independent collection modes."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DOCKER = ['docker', '--host', 'unix:///var/run/docker.sock']


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def launch(task, loops, modes, *, return_record=False):
    candidate = json.loads((ROOT/'docops/docker/current-image.json').read_text())
    image = json.loads(subprocess.check_output(DOCKER+['image', 'inspect', candidate['candidate_tag']], text=True))[0]
    if image['Id'] != candidate['candidate_id']:
        raise ValueError('candidate tag changed')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    raw = HERE/'raw'/f'{task}-chain-pilot-{stamp}'
    raw.mkdir(parents=True, exist_ok=False)
    source = raw/'measurement-source'; source.mkdir()
    for name in ('capture.py', 'worker.py', 'monitor.py', 'quality.py', 'pilot.py','native_adapter.py'):
        shutil.copy2(HERE/name, source/name)
    for original, name in [(ROOT/'analysis/hotspots/native_profile.py', 'native_profile.py'),
                           (ROOT/'analysis/hotspots/collect_native.py', 'native_capture_helpers.py'),
                           (ROOT/'analysis/topdown/summarize.py', 'topdown_summary.py')]:
        shutil.copy2(original, source/name)
    state = dict(schema='docops-collector-chain-pilot-v1', status='running', task=task, loops=loops,
                 image_reference=candidate['candidate_tag'], image_id=image['Id'],
                 runtime_profile=candidate.get('runtime_profile', 'docops-debian-original'),
                 source_sha256={p.name:sha(p) for p in source.iterdir()}, modes={},
                 formal_similarity_eligible=False, raw=str(raw.relative_to(ROOT)))
    write(raw/'image-inspect.json', image)
    write(raw/'launch.json', state)
    print('PILOT '+str(raw), flush=True)
    try:
        for mode in modes:
            folder=raw/mode; folder.mkdir();out=folder/'out';out.mkdir()
            plan=state['modes'][mode]={'status':'running'}
            create=DOCKER+['create','--name',f'docops-{mode}-{task}-{stamp.lower()}',
                '--network','none','--cpuset-cpus','0-9','--cap-add','PERFMON','--cap-add','SYS_PTRACE',
                '--security-opt','seccomp=unconfined',
                '--mount',f'type=bind,source={source},target=/opt/docops-measurement,readonly',
                '--mount',f'type=bind,source={out},target=/results',
                '--entrypoint','python3',image['Id'],'-B','/opt/docops-measurement/capture.py',
                '--task',task,'--loops',str(loops),'--mode',mode]
            symbols = HERE/'symbols'
            # Debian enrichment belongs to the original candidate's build-ids.
            # Unified images already contain their matching seven-case symbols;
            # do not mask their /usr/lib/debug with a historical Debian tree.
            if (mode == 'perf' and state['runtime_profile'] == 'docops-debian-original'
                    and (symbols/'index.json').is_file()):
                from quality import verify_symbols
                verified = verify_symbols(symbols)
                state['debug_symbols'] = verified
                # Analysis-only symbols: business ELF/shared-library bytes stay unchanged.
                create[create.index('--entrypoint'):create.index('--entrypoint')] = [
                    '--mount',f'type=bind,source={symbols},target=/usr/lib/debug,readonly']
            plan['create_argv']=create;write(raw/'launch.json',state)
            cid=subprocess.check_output(create,text=True,timeout=60).strip();plan['container_id']=cid
            inspected=json.loads(subprocess.check_output(DOCKER+['inspect',cid],text=True))[0]
            write(folder/'container-before.json',inspected)
            if inspected['Image']!=image['Id'] or inspected['HostConfig']['NetworkMode']!='none':
                raise ValueError('container identity/network mismatch')
            expected_mounts = {'/opt/docops-measurement','/results'}
            if mode == 'perf' and 'debug_symbols' in state:
                expected_mounts.add('/usr/lib/debug')
            if {m['Destination'] for m in inspected['Mounts']}!=expected_mounts:
                raise ValueError('unexpected runtime/source mount')
            if any(m['RW'] for m in inspected['Mounts'] if m['Destination'] != '/results'):
                raise ValueError('measurement code or symbols mounted writable')
            print('START '+mode,flush=True)
            with (folder/'container.log').open('x')as log:
                try:
                    cp=subprocess.run(DOCKER+['start','-a',cid],stdout=log,stderr=subprocess.STDOUT,timeout=900)
                except BaseException:
                    subprocess.run(DOCKER+['stop','-t','3',cid],capture_output=True,timeout=15)
                    raise
            after=json.loads(subprocess.check_output(DOCKER+['inspect',cid],text=True))[0]
            write(folder/'container-after.json',after)
            plan.update(docker_returncode=cp.returncode,container_exit_code=after['State']['ExitCode'])
            if cp.returncode or after['State']['ExitCode']:
                plan['status']='failed'
                raise RuntimeError(f'{mode} failed; see {folder}/out/collection.json and container.log')
            collection=json.loads((out/'collection.json').read_text())
            if collection['status']!='passed':raise ValueError('collection not passed')
            files=json.loads((out/'sha256-index.json').read_text())['files']
            for relative,entry in files.items():
                p=out/relative
                if p.stat().st_size!=entry['bytes'] or sha(p)!=entry['sha256']:
                    raise ValueError('archive changed: '+relative)
            plan.update(status='passed',collection=collection,indexed_files_verified=len(files),
                        collection_sha256=sha(out/'collection.json'))
            write(raw/'launch.json',state)
            print(mode+' PASSED '+json.dumps({k:collection.get(k)for k in ['counts','roi_seconds','roi_samples','quality','metrics']},ensure_ascii=False),flush=True)
        state['status']='passed'
    except BaseException as exc:
        state.update(status='failed',error=f'{type(exc).__name__}: {exc}')
    finally:
        write(raw/'launch.json',state)
    print(json.dumps({'status':state['status'],'raw':str(raw),'error':state.get('error')},ensure_ascii=False),flush=True)
    if return_record:
        return state
    return 0 if state['status']=='passed' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task',default='031')
    parser.add_argument('--loops',type=int,default=10)
    parser.add_argument('--mode',choices=['perf','topdown','both'],default='both')
    args=parser.parse_args()
    if args.loops<1:parser.error('positive loops required')
    raise SystemExit(launch(args.task,args.loops,['perf','topdown']if args.mode=='both'else[args.mode]))
