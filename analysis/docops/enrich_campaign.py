"""Offline, same-image symbol enrichment of a completed campaign; no workload executes."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

from campaign import check_archive, write
from pilot import DOCKER, HERE, ROOT, sha
from quality import verify_symbols


def main(campaign,symbols,output=None):
    campaign=Path(campaign).resolve();symbols=Path(symbols).resolve()
    state=json.loads(campaign.read_text())
    if state['status']!='passed':raise ValueError('campaign acquisition incomplete')
    verified=verify_symbols(symbols)
    folder=Path(output).resolve()if output else campaign.parent/'offline-symbol-enrichment'
    folder.mkdir(exist_ok=False)
    sources=folder/'source';sources.mkdir()
    for name in ('recover_perf.py','quality.py','native_adapter.py'):shutil.copy2(HERE/name,sources/name)
    for old,new in [('native_profile.py','native_profile.py'),('collect_native.py','native_capture_helpers.py')]:
        shutil.copy2(ROOT/'analysis/hotspots'/old,sources/new)
    record=dict(schema='docops-campaign-symbol-enrichment-v1',status='running',
                campaign_path=str(campaign.relative_to(ROOT)),campaign_sha256=sha(campaign),
                image_id=state['image_id'],symbols=verified,symbol_root=str(symbols.relative_to(ROOT)),
                workload_rerun=False,perf_record_rerun=False,tasks={},
                source_sha256={p.name:sha(p)for p in sources.iterdir()})
    write(folder/'enrichment.json',record)
    try:
        for task,modes in state['tasks'].items():
            original=ROOT/modes['perf']['workflow_out'];taskdir=folder/task;taskdir.mkdir();out=taskdir/'out';out.mkdir()
            name=f'docops-enrich-{task}-{folder.name}-{folder.parent.name}'.lower()
            argv=DOCKER+['create','--name',name,'--network','none','--cpuset-cpus','9',
                         '--mount',f'type=bind,source={original},target=/original,readonly',
                         '--mount',f'type=bind,source={sources},target=/opt/docops-measurement,readonly',
                         '--mount',f'type=bind,source={symbols},target=/usr/lib/debug,readonly',
                         '--mount',f'type=bind,source={out},target=/results',
                         '--entrypoint','python3',state['image_id'],'-B',
                         '/opt/docops-measurement/recover_perf.py','--allow-limited']
            cid=subprocess.check_output(argv,text=True,timeout=60).strip()
            before=json.loads(subprocess.check_output(DOCKER+['inspect',cid],text=True))[0]
            write(taskdir/'container-before.json',before)
            if before['Image']!=state['image_id']or before['HostConfig']['NetworkMode']!='none':raise ValueError('wrong recovery identity')
            if any(m['RW']for m in before['Mounts']if m['Destination']!='/results'):raise ValueError('recovery inputs writable')
            with (taskdir/'container.log').open('x')as log:
                try:cp=subprocess.run(DOCKER+['start','-a',cid],stdout=log,stderr=subprocess.STDOUT,timeout=240)
                except BaseException:
                    subprocess.run(DOCKER+['stop','-t','3',cid],capture_output=True,timeout=15);raise
            after=json.loads(subprocess.check_output(DOCKER+['inspect',cid],text=True))[0];write(taskdir/'container-after.json',after)
            if cp.returncode or after['State']['ExitCode']:raise RuntimeError('offline recovery failed: '+task)
            recovery=out/'recovery-record.json';value=json.loads(recovery.read_text())
            if value['status']!='passed' or not value['original_evidence_unchanged']:raise ValueError('invalid recovery')
            record['tasks'][task]={'record':str(recovery.relative_to(ROOT)),'record_sha256':sha(recovery),
                'out':str(out.relative_to(ROOT)),'archive':check_archive(out),
                'function_qualification':value['function_qualification'],'quality_before':value['quality_before'],
                'quality_after':value['quality_after'],'container_id':cid}
            write(folder/'enrichment.json',record)
            print('ENRICHED',task,'unknown',round(value['quality_after']['unknown_leaf_symbol_share']*100,2),'%',flush=True)
        record['status']='passed'
    except BaseException as exc:
        record.update(status='failed',error=f'{type(exc).__name__}: {exc}',traceback=traceback.format_exc())
    finally:write(folder/'enrichment.json',record)
    print(json.dumps({'status':record['status'],'record':str(folder/'enrichment.json'),'error':record.get('error')},ensure_ascii=False),flush=True)
    return 0 if record['status']=='passed'else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',required=True,type=Path)
    parser.add_argument('--symbols',required=True,type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();raise SystemExit(main(args.campaign,args.symbols,args.output))
