"""Observe an unmodified document-oe iteration with monotonic ROI markers."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import sys
import time


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def observe_iteration(original,dataset,path):
    def observed(*args,**kwargs):
        def mark(event):
            item=dict(dataset_id=dataset,scope='loop_including_reset',event=event,
                      monotonic_ns=time.monotonic_ns(),realtime_ns=time.time_ns())
            with Path(path).open('a') as stream:stream.write(json.dumps(item)+'\n')
        mark('start')
        try:return original(*args,**kwargs)
        finally:mark('end')
    return observed


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',choices=['opm','tlc'],required=True)
    parser.add_argument('--results-dir',type=Path,required=True)
    parser.add_argument('--roi',type=Path,required=True)
    args=parser.parse_args()
    if args.roi.exists():raise ValueError('refuse to overwrite ROI')
    entry=load('/opt/office-trace-replay/document-oe/run.py','measured_document_entry')
    entry.configure_runtime()
    entry.validate(installed=True)
    with Path('/tmp/office-agent-replay.lock').open('w') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        entry.restore_skill_links()
        runner=load('/opt/document-bench/bin/run_document_scene_loop.py','measured_legacy_runner')
        runner.run_iteration=observe_iteration(runner.run_iteration,args.dataset,args.roi)
        sys.argv=[str(runner.__file__),'--scene','pdf' if args.dataset=='opm' else 'xlsx',
                  '--loops','1','--results-dir',str(args.results_dir)]
        if args.dataset=='opm':sys.argv+=['--pdf-applicant-count','10']
        return runner.main()


if __name__=='__main__':raise SystemExit(main())
