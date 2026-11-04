"""First DocOps comparison batch: one capture per mode, ten replay loops per capture."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import traceback

from pilot import HERE, ROOT, launch, sha
from quality import function_qualification, verify_symbols

TASKS={'word':('001','003','009'), 'excel':('013','014','016'),
       'ppt':('021','026','029'), 'pdf':('031','037','pdfwf005')}
VALIDATION=HERE/'processed/031-collector-validation-20261103/validation.json'


def write(path,value):
    tmp=path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    tmp.replace(path)


def check_archive(folder):
    index=folder/'sha256-index.json'
    entries=json.loads(index.read_text())['files']
    for rel,row in entries.items():
        file=(folder/rel).resolve()
        if not file.is_relative_to(folder.resolve()) or file.stat().st_size!=row['bytes'] or sha(file)!=row['sha256']:
            raise ValueError('invalid archive file: '+str(file))
    return dict(index=str(index.relative_to(ROOT)),sha256=sha(index),files_verified=len(entries))


def reuse_031():
    reference=json.loads(VALIDATION.read_text())
    image=json.loads((ROOT/'docops/docker/current-image.json').read_text())['candidate_id']
    if reference['status']!='passed_with_symbol_limitations' or reference['image_id']!=image:
        raise ValueError('031 reference identity mismatch')
    perf=ROOT/reference['perf']['original'];recovery=ROOT/reference['perf']['recovery']
    td=ROOT/reference['topdown']['raw']/'topdown/out'
    for folder in (perf,recovery/'out',td):check_archive(folder)
    for rel,digest in json.loads((recovery/'out/recovery-record.json').read_text())['original_sha256'].items():
        if sha(perf/rel)!=digest:raise ValueError('031 original recovery binding changed')
    result={}
    for mode,out,record in [('perf',recovery/'out',recovery/'out/recovery-record.json'),('topdown',td,td/'collection.json')]:
        value=json.loads(record.read_text())
        if value['status']!='passed' or value['counts']!=dict(requested=10,completed=10,successes=10,failures=0):
            raise ValueError('031 reused capture incomplete')
        result[mode]={'status':'passed','origin':'reused_031_validation_not_rerun',
            'out':str(out.relative_to(ROOT)),'record':str(record.relative_to(ROOT)),'record_sha256':sha(record),
            'archive':check_archive(out),'workflow_out':str((perf if mode=='perf' else td).relative_to(ROOT)),
            'validation_record_sha256':sha(VALIDATION)}
        if mode=='perf':
            result[mode]['function_qualification']=function_qualification(reference['perf']['quality'])
    return result


def run(destination):
    destination=Path(destination).resolve()
    if not destination.is_relative_to(HERE/'raw'):
        raise ValueError('campaign must be a new directory inside analysis/docops/raw')
    destination.mkdir(exist_ok=False,parents=True)
    image=json.loads((ROOT/'docops/docker/current-image.json').read_text())
    state=dict(schema='docops-first-comparison-campaign-v1',status='preflight',loops_per_capture=10,
               independent_captures_per_mode=1, planned_new_captures=22,reused_captures=2,
               image_id=image['candidate_id'], task_groups=TASKS, tasks={},
               created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               infer_repeat_stability=False,formal_similarity_eligible=False,
               measurement_source_sha256={p.name:sha(p)for p in HERE.glob('*.py')},
               payload_index_sha256=sha(ROOT/'docops/payload/payload-index.json'))
    path=destination/'campaign.json';write(path,state)
    try:
        subprocess.run([sys.executable,'-B',str(ROOT/'docops/compile.py'),'validate','--payload',str(ROOT/'docops/payload')],check=True)
        state['debug_symbols']=verify_symbols(HERE/'symbols')
        state['tasks']['031']=reuse_031();state['status']='running';write(path,state)
        for fmt,tasks in TASKS.items():
            for task in tasks:
                if task=='031':continue
                state['tasks'][task]={}
                for mode in ('perf','topdown'):
                    state['active']={'format':fmt,'task':task,'mode':mode};write(path,state)
                    print('CAMPAIGN START '+task+' '+mode,flush=True)
                    record=launch(task,10,[mode],return_record=True)
                    if record['status']!='passed':
                        state['tasks'][task][mode]={'status':'failed','raw':record['raw'],'error':record.get('error')}
                        raise RuntimeError('capture failed: '+task+' '+mode)
                    out=ROOT/record['raw']/mode/'out';collection=out/'collection.json'
                    row={'status':'passed','origin':'new_capture','raw':record['raw'],
                         'out':str(out.relative_to(ROOT)),'workflow_out':str(out.relative_to(ROOT)),
                         'record':str(collection.relative_to(ROOT)),'record_sha256':sha(collection),
                         'archive':check_archive(out)}
                    if mode=='perf':row['function_qualification']=record['modes'][mode]['collection']['function_qualification']
                    state['tasks'][task][mode]=row;write(path,state)
        state['status']='passed';state['active']=None
        state['completed_modes']=sum(len(modes)for modes in state['tasks'].values())
    except BaseException as exc:
        state.update(status='failed',error=f'{type(exc).__name__}: {exc}',traceback=traceback.format_exc())
    finally:
        state['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();write(path,state)
    print(json.dumps({'status':state['status'],'record':str(path),'error':state.get('error')},ensure_ascii=False),flush=True)
    return 0 if state['status']=='passed'else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign-dir',required=True,type=Path)
    args=parser.parse_args();raise SystemExit(run(args.campaign_dir))
