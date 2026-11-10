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


def capture_args(task, loops, mode, payload, workload_timeout, step_timeout):
    argv = ['--task', task, '--loops', str(loops), '--mode', mode,
            '--workload-timeout', str(workload_timeout), '--step-timeout', str(step_timeout)]
    if payload is not None:
        argv += ['--payload', payload]
    return argv


def resolve_image(ref, expected_id=None):
    """Resolve a tag or immutable image ID to the actual image dict.

    The actual immutable image ID is read back from the daemon (never taken on
    trust from the tag). If ``expected_id`` is provided, a mismatch raises
    BEFORE any workload container is created.
    """
    image = json.loads(subprocess.check_output(
        DOCKER + ['image', 'inspect', ref], text=True, timeout=120))[0]
    if expected_id is not None and image['Id'] != expected_id:
        raise ValueError(
            f'expected image id {expected_id} but {ref!r} resolved to {image["Id"]}')
    return image


def build_create(task, loops, mode, image_id, source_dir, out_dir, *,
                 payload=None, installed_payload=None,
                 workload_timeout=600, step_timeout=1200,
                 host_replay=None, host_compile=None,
                 container_name=None):
    """Pure construction of one measurement container's create argv.

    ``payload`` is a HOST directory to bind-mount at the canonical container
    path; ``installed_payload`` is a CONTAINER path already present in the image
    (no host mount). A host absolute path is never passed as the container
    payload argument. Returns (create_argv, expected_mount_destinations,
    payload_arg_for_container).

    ``container_name`` must be unique per attempt so a retained container never
    collides with a later capture (containers are never deleted to avoid that).
    """
    if payload is not None and installed_payload is not None:
        raise ValueError('use either a host payload mount or an installed payload, not both')
    if container_name is None:
        container_name = f'docops-{mode}-{task}-{uuid.uuid4().hex[:10]}'
    create = DOCKER + ['create', '--name', container_name,
                       '--network', 'none', '--cpuset-cpus', '0-9',
                       '--cap-add', 'PERFMON', '--cap-add', 'SYS_PTRACE',
                       '--security-opt', 'seccomp=unconfined',
                       '--mount', f'type=bind,source={source_dir},target=/opt/docops-measurement,readonly',
                       '--mount', f'type=bind,source={out_dir},target=/results',
                       '--entrypoint', 'python3', image_id, '-B',
                       '/opt/docops-measurement/capture.py']
    if payload is not None:
        payload_arg = '/opt/docops/scaling/payload'
    elif installed_payload is not None:
        payload_arg = installed_payload
    else:
        payload_arg = None
    create += capture_args(task, loops, mode, payload_arg, workload_timeout, step_timeout)
    expected_mounts = {'/opt/docops-measurement', '/results'}
    extra_mounts = []
    if payload is not None:
        extra_mounts += [
            f'type=bind,source={payload.resolve()},target=/opt/docops/scaling/payload,readonly',
            f'type=bind,source={host_replay},target=/opt/docops/replay.py,readonly',
            f'type=bind,source={host_compile},target=/opt/docops/compile.py,readonly']
        expected_mounts |= {'/opt/docops/scaling/payload', '/opt/docops/replay.py', '/opt/docops/compile.py'}
    for spec in extra_mounts:
        create.insert(create.index('--entrypoint'), '--mount')
        create.insert(create.index('--entrypoint'), spec)
    return create, expected_mounts, payload_arg


def launch(task, loops, modes, *, return_record=False, payload=None,
           installed_payload=None, image_ref=None, expected_image_id=None,
           campaign_dir=None, workload_timeout=600, step_timeout=1200,
           host_timeout=3600):
    if payload is not None and installed_payload is not None:
        raise ValueError('use either a host payload mount or an installed payload, not both')
    if image_ref is None:
        candidate = json.loads((ROOT / 'docops/docker/current-image.json').read_text())
        image = resolve_image(candidate['candidate_tag'],
                              expected_id=expected_image_id or candidate['candidate_id'])
        image_reference = candidate['candidate_tag']
        runtime_profile = candidate.get('runtime_profile', 'docops-debian-original')
    else:
        image = resolve_image(image_ref, expected_id=expected_image_id)
        image_reference = image_ref
        runtime_profile = 'explicit-image-selection'
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    base_dir = (campaign_dir or HERE/'raw').resolve()
    if not base_dir.is_relative_to(ROOT):
        raise ValueError('campaign must live inside the repository')
    base_dir.mkdir(parents=True, exist_ok=True)
    raw = base_dir/f'{task}-chain-pilot-{stamp}'
    raw.mkdir(parents=True, exist_ok=False)
    source = raw/'measurement-source'; source.mkdir()
    for name in ('capture.py', 'worker.py', 'monitor.py', 'quality.py', 'pilot.py','native_adapter.py'):
        shutil.copy2(HERE/name, source/name)
    for original, name in [(ROOT/'analysis/hotspots/native_profile.py', 'native_profile.py'),
                           (ROOT/'analysis/hotspots/collect_native.py', 'native_capture_helpers.py'),
                           (ROOT/'analysis/topdown/summarize.py', 'topdown_summary.py')]:
        shutil.copy2(original, source/name)
    state = dict(schema='docops-collector-chain-pilot-v1', status='running', task=task, loops=loops,
                 image_reference=image_reference, image_id=image['Id'],
                 expected_image_id=expected_image_id,
                 runtime_profile=runtime_profile,
                 source_sha256={p.name:sha(p) for p in source.iterdir()}, modes={},
                 formal_similarity_eligible=False, raw=str(raw.relative_to(ROOT)))
    if payload is not None:
        state['payload'] = str(payload.resolve())
        state['payload_source'] = 'host-mount'
    if installed_payload is not None:
        state['installed_payload'] = installed_payload
        state['payload_source'] = 'installed'
    write(raw/'image-inspect.json', image)
    write(raw/'launch.json', state)
    print('PILOT '+str(raw), flush=True)
    try:
        for mode in modes:
            folder=raw/mode; folder.mkdir();out=folder/'out';out.mkdir()
            plan=state['modes'][mode]={'status':'running'}
            create, expected_mounts, payload_arg = build_create(
                task, loops, mode, image['Id'], source, out,
                payload=payload, installed_payload=installed_payload,
                workload_timeout=workload_timeout, step_timeout=step_timeout,
                host_replay=ROOT / 'docops/replay.py', host_compile=ROOT / 'docops/compile.py',
                container_name=f'docops-{mode}-{task}-{stamp.lower()}')
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
                create.insert(create.index('--entrypoint'), '--mount')
                create.insert(create.index('--entrypoint'),
                              f'type=bind,source={symbols},target=/usr/lib/debug,readonly')
                expected_mounts.add('/usr/lib/debug')
            plan['create_argv']=create;write(raw/'launch.json',state)
            cid=subprocess.check_output(create,text=True,timeout=60).strip();plan['container_id']=cid
            inspected=json.loads(subprocess.check_output(DOCKER+['inspect',cid],text=True))[0]
            write(folder/'container-before.json',inspected)
            if inspected['Image']!=image['Id'] or inspected['HostConfig']['NetworkMode']!='none':
                raise ValueError('container identity/network mismatch')
            if {m['Destination'] for m in inspected['Mounts']}!=expected_mounts:
                raise ValueError('unexpected runtime/source mount')
            if any(m['RW'] for m in inspected['Mounts'] if m['Destination'] != '/results'):
                raise ValueError('measurement code or symbols mounted writable')
            print('START '+mode,flush=True)
            with (folder/'container.log').open('x')as log:
                try:
                    cp=subprocess.run(DOCKER+['start','-a',cid],stdout=log,stderr=subprocess.STDOUT,timeout=host_timeout)
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
    parser.add_argument('--payload',type=Path,default=None,
                        help='host scaling payload directory to mount and select')
    parser.add_argument('--installed-payload',type=str,default=None,
                        help='container payload path already installed in the image '
                             '(e.g. /opt/docops/scaling/payload-all) - no host mount')
    parser.add_argument('--image',type=str,default=None,
                        help='explicit image tag or immutable ID to inspect and use')
    parser.add_argument('--expected-image-id',type=str,default=None,
                        help='expected immutable image ID; reject before workload if different')
    parser.add_argument('--campaign-dir',type=Path,default=None,
                        help='destination root for the campaign (default: analysis/docops/raw)')
    parser.add_argument('--workload-timeout',type=int,default=600,
                        help='in-container seconds to wait for the whole worker')
    parser.add_argument('--step-timeout',type=int,default=1200,
                        help='seconds per workflow step passed to the replay entry')
    parser.add_argument('--host-timeout',type=int,default=3600,
                        help='host seconds allowed for the container run')
    args=parser.parse_args()
    if args.loops<1:parser.error('positive loops required')
    raise SystemExit(launch(args.task,args.loops,['perf','topdown']if args.mode=='both'else[args.mode],
                            payload=args.payload, installed_payload=args.installed_payload,
                            image_ref=args.image, expected_image_id=args.expected_image_id,
                            campaign_dir=args.campaign_dir,
                            workload_timeout=args.workload_timeout, step_timeout=args.step_timeout,
                            host_timeout=args.host_timeout))
