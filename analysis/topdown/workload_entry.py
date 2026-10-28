"""Load the frozen executor and observe its existing boundaries in memory."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from gate import Gate

DATASETS = ('smoke','opm','tlc','irs_w4','sba1919','hr_metro','egrid','industry_productivity')


def load_module(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def legacy(gate, out, dataset):
    """Observe the original iteration call in memory; workload bytes stay frozen."""
    entry=load_module('observed_document_entry','/opt/office-trace-replay/document-oe/run.py')
    entry.configure_runtime()
    entry.validate(installed=True)
    entry.restore_skill_links()
    runner=load_module('observed_document_executor','/opt/document-bench/bin/run_document_scene_loop.py')
    original=runner.run_iteration
    def observed(*args, **kwargs):
        gate.begin()
        start=dict(scope='loop_including_reset',event='start',monotonic_ns=time.monotonic_ns())
        gate.log('formal_roi_start',marker=start)
        try:return original(*args,**kwargs)
        finally:gate.end(dict(scope='loop_including_reset',event='end',monotonic_ns=time.monotonic_ns()))
    runner.run_iteration=observed
    scene='pdf' if dataset=='opm' else 'xlsx'
    sys.argv=[str(Path(runner.__file__)),'--scene',scene,'--loops','1',
              '--results-dir',str(out/'runner'),'--pdf-applicant-count','10']
    return runner.main()


def smoke(gate, out):
    def boundary(folder,recipe,index,scope,event):
        marker=dict(dataset_id='synthetic_smoke',scope=scope,event=event,
                    monotonic_ns=time.monotonic_ns())
        with (out/'roi.jsonl').open('a') as stream:stream.write(json.dumps(marker)+'\n')
        return marker
    observed=gate.boundary(boundary)
    gate.log('excluded_preflight');time.sleep(.2)
    observed(out,{},1,'loop_including_reset','start')
    command=[sys.executable,'-B','-c',
        'import time; end=time.monotonic()+1.5; x=1\nwhile time.monotonic()<end: x=(x*1664525+1013904223)&0xffffffff']
    subprocess.run(command,check=True)
    observed(out,{},1,'loop_including_reset','end')
    gate.log('excluded_archive');time.sleep(.2)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',choices=DATASETS,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    os.sched_setaffinity(0,{9})
    gate=Gate(args.output/'control.sock',args.output/'affinity-events.jsonl')
    if args.dataset=='smoke':
        smoke(gate,args.output)
        return 0
    if args.dataset in ('opm','tlc'):
        return legacy(gate,args.output,args.dataset)
    # The normal common entry validates the same dataset-local executor. Use
    # its main() here so the in-memory boundary hook survives subprocess launch.
    path=Path('/opt/office-trace-replay/agent/datasets')/args.dataset/'run.py'
    module=load_module('topdown_observed_dataset',path)
    module.boundary=gate.boundary(module.boundary)
    return module.main(['--loops','1','--runtime','document-oe','--results-dir',str(args.output/'runner'),
                        '--container-inspect','/evidence/container-inspect.before.json'])


if __name__=='__main__':raise SystemExit(main())
