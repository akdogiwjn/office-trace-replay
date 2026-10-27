"""Run the two remaining XLSX captures sequentially after a successful TLC capture."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

from pilot import HERE,ROOT,write,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--after-launch',type=Path,required=True)
    args=parser.parse_args()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    directory=HERE/'raw'/('completion-campaign-'+stamp)
    directory.mkdir(parents=True)
    status_path=directory/'campaign.json'
    state=dict(status='waiting_for_tlc',selected=['egrid','industry_productivity'],completed=[],
               prerequisite=str(args.after_launch.resolve()),created_at=stamp)
    write(status_path,state)
    print('Campaign: '+str(directory),flush=True)
    try:
        deadline=time.monotonic()+1800
        while True:
            prerequisite=json.loads(args.after_launch.read_text())
            if prerequisite['status']=='failed':raise RuntimeError('TLC prerequisite failed')
            if prerequisite['status']=='success':break
            if time.monotonic()>deadline:raise TimeoutError('TLC prerequisite timeout')
            time.sleep(2)
        state.update(status='in_progress',prerequisite_sha256=sha(args.after_launch))
        for dataset in state['selected']:
            state['running']=dataset;write(status_path,state)
            print('Starting '+dataset,flush=True)
            result=subprocess.run([sys.executable,'-B','-u',str(HERE/'pilot.py'),'--dataset',dataset],cwd=ROOT)
            if result.returncode:raise RuntimeError(dataset+' capture failed; inspect raw evidence before retry')
            pointer=HERE/f'reports/latest-{dataset}.json'
            state['completed'].append(dict(dataset=dataset,pointer=str(pointer.relative_to(ROOT)),sha256=sha(pointer)))
            write(status_path,state)
        state.update(status='success',running=None)
    except BaseException as exc:
        state.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:write(status_path,state)
    print(json.dumps(state),flush=True)


if __name__=='__main__':main()
