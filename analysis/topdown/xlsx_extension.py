"""Add exactly four independent XLSX repeats per profiler, retaining run one."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from pilot import HERE, ROOT, sha, write
from summarize import summarize

DATASETS=('tlc','hr_metro','egrid','industry_productivity')
PLAN=[dict(dataset_id=ds,repeat=repeat,profiler=mode)
      for repeat in range(2,6) for ds in DATASETS for mode in ('native','topdown')]


def checked(path,digest):
    if sha(path)!=digest:raise ValueError('source changed: '+str(path))
    return json.loads(path.read_text())


def initial_state(folder):
    config_path=HERE/'comparison-inputs-20261028.json'
    config=json.loads(config_path.read_text())
    td=checked(ROOT/config['topdown_campaign']['path'],config['topdown_campaign']['sha256'])
    if td['status']!='success':raise ValueError('initial Topdown campaign incomplete')
    reused=[]
    for ds in DATASETS:
        entry=next(r for r in td['completed'] if r['dataset_id']==ds and r['repeat']==1)
        checked(ROOT/entry['summary'],entry['summary_sha256'])
        binding=config['hotspot_profiles'][ds]
        profile=checked(ROOT/binding['path'],binding['sha256'])
        if profile['dataset_id']!=ds or profile.get('repetitions',1)!=1:raise ValueError('initial native profile invalid')
        reused.append(dict(dataset_id=ds,topdown=entry,native=binding))
    shutil.copy2(config_path,folder/'baseline-inputs.json')
    qualified=json.loads((ROOT/'reports/image-qualification-agent-traces.json').read_text())
    for name,digest in qualified['file_hashes'].items():checked_file=ROOT/name;assert sha(checked_file)==digest,name
    return dict(schema='xlsx-five-repeat-extension-v1',status='in_progress',
        image_id=qualified['image_id'],baseline_config=dict(path=str((folder/'baseline-inputs.json').relative_to(ROOT)),
            sha256=sha(folder/'baseline-inputs.json')),reused_first_repeats=reused,
        plan=PLAN,completed=[],active=None,workload_retries=0,
        ordering='For each repeat 2..5, each XLSX dataset: native then Topdown; strictly sequential',
        measurement_sources={str(p.relative_to(ROOT)):sha(p) for p in
            [HERE/'capture.py',HERE/'gate.py',HERE/'workload_entry.py',
             ROOT/'analysis/hotspots/collect_native.py',ROOT/'analysis/hotspots/native_profile.py']})


def run():
    # Host bookkeeping also stays outside the eight measured logical CPUs.
    os.sched_setaffinity(0,{9})
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    folder=HERE/'raw'/('xlsx-five-repeat-extension-'+stamp);folder.mkdir(parents=True,exist_ok=False)
    state=initial_state(folder);write(folder/'campaign.json',state)
    write(HERE/'reports/latest-xlsx-extension.json',dict(campaign=str((folder/'campaign.json').relative_to(ROOT))))
    print('Extension campaign: '+str(folder),flush=True)
    try:
        for task in PLAN:
            ds=task['dataset_id'];mode=task['profiler'];repeat=task['repeat']
            script=(ROOT/'analysis/hotspots/pilot.py') if mode=='native' else HERE/'pilot.py'
            pointer=script.parent/'reports'/f'latest-{ds}.json'
            before=sha(pointer) if pointer.exists() else None
            log=folder/f'{len(state["completed"])+1:02d}-{ds}-r{repeat}-{mode}.log'
            state['active']=dict(**task,log=str(log.relative_to(ROOT)),argv=[sys.executable,'-B',str(script),'--dataset',ds])
            write(folder/'campaign.json',state)
            print(f'START {len(state["completed"])+1}/32 {ds} r{repeat} {mode}',flush=True)
            with log.open('x') as stream:
                code=subprocess.run(state['active']['argv'],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT).returncode
            state['active']['returncode']=code;write(folder/'campaign.json',state)
            if code:raise RuntimeError(f'{ds} r{repeat} {mode} failed; preserve raw and inspect {log}')
            if not pointer.exists() or sha(pointer)==before:raise ValueError('capture did not publish a new pointer')
            p=json.loads(pointer.read_text());raw=ROOT/p['raw']
            launch=json.loads((raw/'launch.json').read_text())
            actual=launch.get('actual_image_id',launch.get('image_id'))
            if launch['status']!='success' or actual!=state['image_id']:raise ValueError('capture image/status mismatch')
            if any(row['raw']==str(raw.relative_to(ROOT)) for row in state['completed']):raise ValueError('reused capture instead of a new repeat')
            entry=dict(**task,raw=str(raw.relative_to(ROOT)),launch_sha256=sha(raw/'launch.json'),
                container_id=launch['container_id'],log=str(log.relative_to(ROOT)))
            state['active']['successful_capture']=entry;write(folder/'campaign.json',state)
            if mode=='topdown':
                report=summarize(raw);summary=report/'summary.json'
                value=json.loads(summary.read_text());entry.update(summary=str(summary.relative_to(ROOT)),summary_sha256=sha(summary))
                seconds=value['roi_seconds']
            else:
                report=ROOT/p['report'];profile=report/'profile.json';value=json.loads(profile.read_text())
                if value['dataset_id']!=ds or value['image_id']!=state['image_id']:raise ValueError('native profile mismatch')
                entry.update(profile=str(profile.relative_to(ROOT)),profile_sha256=sha(profile))
                seconds=(value['roi_end_ns']-value['roi_start_ns'])/1e9
            entry['roi_seconds']=seconds
            state['completed'].append(entry);state['active']=None;write(folder/'campaign.json',state)
            print(f'DONE {len(state["completed"])}/32 {ds} r{repeat} {mode}, ROI {seconds:.2f}s',flush=True)
        state.update(status='success',active=None,finished_at=datetime.now(timezone.utc).isoformat())
    except BaseException as exc:
        state.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:write(folder/'campaign.json',state)
    print('CAPTURES COMPLETE: '+str(folder/'campaign.json'),flush=True)
    return folder/'campaign.json'


if __name__=='__main__':run()
