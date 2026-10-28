"""Host launcher for one gated DevKit smoke or PDF pilot; no image build."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import uuid

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DOCKER=['docker','--host','unix:///var/run/docker.sock']


DATASETS=('smoke','opm','tlc','irs_w4','sba1919','hr_metro','egrid','industry_productivity')


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):digest.update(block)
    return digest.hexdigest()


def write(path,data):
    path=Path(path);temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');temp.replace(path)


def launch(dataset):
    qualification=json.loads((ROOT/'reports/image-qualification-agent-traces.json').read_text())
    for name,digest in qualification['file_hashes'].items():
        if sha(ROOT/name)!=digest:raise ValueError('qualified runtime changed: '+name)
    image=json.loads(subprocess.check_output(DOCKER+['image','inspect','office-trace-replay:agent-traces'],text=True))[0]
    if image['Id']!=qualification['image_id']:raise ValueError('unexpected image')
    tool=HERE/'tools/DevKit-Tuner-CLI-26.0.RC1-Linux-aarch64'
    expected=json.loads((HERE/'hip09-preflight-20261027/qualification.json').read_text())
    for name,row in expected['tool']['executable_bindings'].items():
        if sha(tool/name)!=row['sha256']:raise ValueError('DevKit material changed: '+name)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    raw=HERE/'raw'/f'{dataset}-cpu-pilot-{stamp}';raw.mkdir(parents=True,exist_ok=False)
    out=raw/'out';out.mkdir();evidence=raw/'evidence';evidence.mkdir()
    write(evidence/'image-inspect.json',image)
    if dataset!='smoke':
        write(evidence/'launch-plan.json',dict(selected_datasets=[dataset],loops=1,runtime='document-oe',
              dataset_locks={dataset:sha(ROOT/'document-oe/lock.json' if dataset in ('opm','tlc')
                                        else ROOT/'agent/datasets'/dataset/'lock.json')}))
    source=evidence/'measurement-source';source.mkdir()
    for p in HERE.glob('*.py'):shutil.copy2(p,source/p.name)
    shutil.copy2(HERE/'hip09-preflight-20261027/qualification.json',evidence/'devkit-qualification.json')
    state=dict(status='in_progress',dataset_id=dataset,image_id=image['Id'],container_started=False,workload_started=False,
               source_sha256={p.name:sha(p) for p in HERE.glob('*.py')})
    command=DOCKER+['container','create','--name',f'office-topdown-{dataset}-{stamp}',
        '--network','none','--cpuset-cpus','0-9','--cap-add','PERFMON','--security-opt','seccomp=unconfined',
        '--mount',f'type=bind,source={HERE},target=/measurement,readonly',
        '--mount',f'type=bind,source={tool},target=/devkit,readonly',
        '--mount',f'type=bind,source={out},target=/results',
        '--mount',f'type=bind,source={evidence},target=/evidence,readonly',
        '--entrypoint','/opt/document-bench/.venv/bin/python',image['Id'],
        '/measurement/capture.py','--dataset',dataset,'--output','/results']
    state['create_argv']=command;write(raw/'launch.json',state)
    print('Pilot directory: '+str(raw),flush=True)
    try:
        cid=subprocess.check_output(command,text=True,timeout=60).strip();state['container_id']=cid
        before=json.loads(subprocess.check_output(DOCKER+['container','inspect',cid],text=True))
        write(evidence/'container-inspect.before.json',before)
        assert before[0]['Image']==image['Id'] and before[0]['HostConfig']['NetworkMode']=='none'
        state['container_started']=True;write(raw/'launch.json',state)
        with (raw/'container.log').open('x') as log:
            started=subprocess.run(DOCKER+['container','start','--attach',cid],stdout=log,stderr=subprocess.STDOUT)
        after=json.loads(subprocess.check_output(DOCKER+['container','inspect',cid],text=True))
        write(evidence/'container-inspect.after.json',after)
        state.update(container_state=after[0]['State'],docker_start_returncode=started.returncode)
        if started.returncode or after[0]['State']['ExitCode']:raise RuntimeError('pilot failed; evidence and container retained')
        collection=json.loads((out/'collection.json').read_text())
        state['workload_started']=collection.get('workload_status')!='not_started'
        if collection['status']!='success':raise ValueError('collection incomplete')
        code='''import hashlib,json
from pathlib import Path
root=Path('/archive');rows=json.loads((root/'sha256-index.json').read_text())['files']
for row in rows:
 p=root/row['path'];h=hashlib.sha256()
 with p.open('rb') as stream:
  for block in iter(lambda:stream.read(1048576),b''):h.update(block)
 assert p.stat().st_size==row['size'] and h.hexdigest()==row['sha256'],str(p)
print(len(rows))
'''
        checked=subprocess.check_output(DOCKER+['run','--rm','--network','none','--read-only',
            '--mount',f'type=bind,source={out},target=/archive,readonly',
            '--entrypoint','/opt/document-bench/.venv/bin/python',image['Id'],'-c',code],text=True)
        state.update(status='success',indexed_files_checked=int(checked),collection_sha256=sha(out/'collection.json'))
    except BaseException as exc:
        state.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:write(raw/'launch.json',state)
    reports=HERE/'reports';reports.mkdir(exist_ok=True)
    write(reports/f'latest-{dataset}.json',dict(raw=str(raw.relative_to(ROOT)),launch_sha256=sha(raw/'launch.json')))
    print(json.dumps(dict(status='success',raw=str(raw.relative_to(ROOT)),container_id=cid)),flush=True)
    return raw


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',choices=DATASETS,default='smoke')
    parser.add_argument('--campaign',action='store_true',help='All seven: PDF five repeats each, XLSX once each.')
    parser.add_argument('--continue-campaign',type=Path)
    parser.add_argument('--recovered-raw',type=Path)
    parser.add_argument('--extend-xlsx',action='store_true',help='Add four XLSX repeats for native and Topdown each.')
    args=parser.parse_args()
    if args.extend_xlsx:
        if args.campaign or args.continue_campaign or args.recovered_raw:parser.error('choose only one campaign mode')
        from xlsx_extension import run
        run()
    elif args.campaign:
        from campaign import run
        run(args.continue_campaign,args.recovered_raw)
    else:launch(args.dataset)
