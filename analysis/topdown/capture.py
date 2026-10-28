"""One CPU-scoped DevKit pilot; CPU affinity separates measured and excluded work."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import socket
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
TOOL=Path('/devkit')
DATASETS=('smoke','opm','tlc','irs_w4','sba1919','hr_metro','egrid','industry_productivity')


def file_sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):digest.update(block)
    return digest.hexdigest()


def validate_business(out,dataset):
    legacy=dataset in ('opm','tlc')
    scene='pdf' if dataset=='opm' else 'xlsx'
    summaries=list((out/'runner'/(scene if legacy else dataset)).glob('*/summary.json'))
    if len(summaries)!=1:raise ValueError('expected one workload summary')
    summary=json.loads(summaries[0].read_text())
    keys=('requested_iterations','completed_iterations','successes','failures') if legacy else ('requested','completed','successes','failures')
    counts=dict(zip(('requested','completed','successes','failures'),(summary[k] for k in keys)))
    if counts!=dict(requested=1,completed=1,successes=1,failures=0):raise ValueError('unsuccessful workload')
    if legacy:
        # Post-ROI archive on CPU 9; the original runner has no workspace archive.
        workspace=Path(summary['workspace'])
        shutil.copytree(workspace/'output',out/'legacy-output')
        business=out/'legacy-output/business_verification.json'
    else:business=summaries[0].parent/'iteration-0001/workspace/output/business_verification.json'
    value=json.loads(business.read_text())
    if value['status']!='success' or value.get('failures'):raise ValueError('business verification failed')
    if legacy:
        inspect=json.loads(Path('/evidence/container-inspect.before.json').read_text())
        image=inspect[0]['Image']
    else:image=summary['context']['container']['actual_image_id']
    return dict(workload_counts=counts,business_verification='success',
                runner_summary=str(summaries[0].relative_to(out)),actual_image_id=image)


def write(path,value):
    path=Path(path);temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temp.replace(path)


def cpu_snapshot():
    return {line.split()[0]:list(map(int,line.split()[1:]))
            for line in Path('/proc/stat').read_text().splitlines()
            if line.split() and line.split()[0] in {f'cpu{i}' for i in range(8)}}


def idle(before,after):
    total=idle_ticks=0
    for cpu in before:
        delta=[b-a for a,b in zip(before[cpu],after[cpu])]
        if any(n<0 for n in delta):raise ValueError('CPU ticks moved backwards')
        # guest and guest_nice are already included in user and nice.
        total+=sum(delta[:8]);idle_ticks+=delta[3]
    if total<=0:raise ValueError('empty CPU accounting window')
    return dict(total_ticks=total,idle_ticks=idle_ticks,idle_pct=100*idle_ticks/total,
                definition='idle field / sum(user,nice,system,idle,iowait,irq,softirq,steal), CPUs 0-7; guest not double counted',
                includes_iowait_as_idle=False)


class Profiler:
    def __init__(self,out):
        self.out=out;self.proc=None;self.record={};self.handles=[]

    def start(self):
        if self.proc is not None:raise ValueError('profiler already started')
        self.record=dict(spawn_requested_ns=time.monotonic_ns(),
            argv=['stdbuf','-oL','-eL',str(TOOL/'devkit'),'tuner','top-down','-c','0-7','-L','0','-i','1','-l','0'])
        stdout=(self.out/'devkit.stdout.txt').open('x');stderr=(self.out/'devkit.stderr.txt').open('x')
        self.handles=[stdout,stderr]
        self.proc=subprocess.Popen(self.record['argv'],cwd=TOOL,stdout=stdout,stderr=stderr,start_new_session=True)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            text=(self.out/'devkit.stdout.txt').read_text(errors='replace')
            # A completed PMU read proves actual counting, unlike PmuOpen alone.
            if 'time of PmuRead:' in text:
                self.record.update(ready_observed_ns=time.monotonic_ns(),pid=self.proc.pid,
                    collector_affinity=sorted(os.sched_getaffinity(self.proc.pid)),
                    readiness='first completed PmuRead; initial interval remains in profiler envelope')
                if set(self.record['collector_affinity'])!={9}:raise ValueError('profiler not on CPU 9')
                return
            if self.proc.poll() is not None:raise RuntimeError('DevKit exited before readiness')
            time.sleep(.01)
        raise TimeoutError('DevKit readiness timeout')

    def stop(self):
        if self.proc is None:raise ValueError('profiler not started')
        self.record['stop_requested_ns']=time.monotonic_ns()
        if self.proc.poll() is None:os.killpg(self.proc.pid,signal.SIGINT)
        try:code=self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(self.proc.pid,signal.SIGKILL);self.proc.wait()
            raise TimeoutError('DevKit did not finish after SIGINT')
        self.record.update(returncode=code,exited_ns=time.monotonic_ns())
        for f in self.handles:f.close()
        write(self.out/'profiler-record.json',self.record)
        if code:raise RuntimeError('DevKit returned '+str(code))
        if 'TOP-DOWN Summary Report-ALL' not in (self.out/'devkit.stdout.txt').read_text():
            raise ValueError('DevKit final summary missing')


def capture(dataset,out):
    out=Path(out)
    if (out/'collection.json').exists():raise ValueError('refuse to overwrite capture')
    out.mkdir(parents=True,exist_ok=True)
    os.sched_setaffinity(0,{9})
    state=dict(schema='devkit-cpu-gated-pilot-v1',dataset_id=dataset,status='in_progress',
        workload_cpus='0-7',collector_cpu=9,profile_level=0,privilege_scope='DevKit default all; no claim of user-only filtering',
        loops=1,pdf_applicant_count=10 if dataset in ('opm','irs_w4','sba1919') else None,
        measurement_scope='CPU-scoped profiler envelope contains gated workload ROI plus recorded idle/background margins',
        exact_roi_event_filtering=False,workload_status='not_started',profiler_status='not_started')
    write(out/'collection.json',state)
    prof=Profiler(out);worker=None;begun=ended=False
    control=out/'control.sock'
    try:
        if dataset!='smoke':
            if dataset in ('opm','tlc'):
                command=[sys.executable,'/opt/office-trace-replay/document-oe/run.py','--validate-only','--installed']
            else:command=[sys.executable,'/opt/office-trace-replay/agent/replay.py','--dataset',dataset,'--validate-only']
            with (out/'preflight.log').open('x') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server:
            server.bind(str(control));server.listen(1);server.settimeout(.1)
            with (out/'workload.log').open('x') as log:
                env=dict(os.environ,OFFICE_AGENT_REPLAY_CONTAINER='1')
                worker=subprocess.Popen([sys.executable,'-s',str(HERE/'workload_entry.py'),'--dataset',dataset,'--output',str(out)],
                                        stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
                state.update(workload_status='running',worker_pid=worker.pid);write(out/'collection.json',state)
                deadline=time.monotonic()+3600
                while worker.poll() is None:
                    if time.monotonic()>deadline:raise TimeoutError('workload deadline')
                    try:connection,_=server.accept()
                    except socket.timeout:continue
                    with connection:
                        connection.settimeout(60)
                        request=json.loads(connection.makefile('r').readline(1048576))
                        try:
                            if request['action']=='begin' and not begun:
                                prof.start();begun=True;state['profiler_status']='running'
                                state['roi_cpu_before']=cpu_snapshot()
                            elif request['action']=='end' and begun and not ended:
                                state['roi_cpu_after']=cpu_snapshot()
                                state['roi_end_marker']=request['marker']
                                prof.stop();ended=True;state['profiler_status']='success'
                            else:raise ValueError('unexpected measurement control sequence')
                            connection.sendall(b'{"status":"success"}\n')
                        except Exception as exc:
                            connection.sendall((json.dumps(dict(status='failed',error=str(exc)))+'\n').encode());raise
                    write(out/'collection.json',state)
                state['workload_returncode']=worker.wait()
        if worker.returncode or not (begun and ended):raise RuntimeError('workload or gate failed')
        state['workload_status']='success'
        events=[json.loads(l) for l in (out/'affinity-events.jsonl').read_text().splitlines()]
        starts=[e for e in events if e['event']=='formal_roi_start']
        ends=[e for e in events if e['event']=='workload_affinity_disabled']
        if len(starts)!=1 or len(ends)!=1:raise ValueError('expected one affinity-gated ROI')
        start=starts[0]['marker']['monotonic_ns'];end=ends[0]['roi_end_ns']
        if end<=start:raise ValueError('invalid ROI')
        state.update(roi_start_ns=start,roi_end_ns=end,roi_seconds=(end-start)/1e9,
            startup_envelope_upper_seconds=(start-prof.record['spawn_requested_ns'])/1e9,
            tail_envelope_upper_seconds=(prof.record['exited_ns']-end)/1e9,
            cpu_window=idle(state['roi_cpu_before'],state['roi_cpu_after']))
        if dataset!='smoke':
            state.update(validate_business(out,dataset))
        state.update(status='success',formal_similarity_eligible=False,
            eligibility_note='Pilot only: profiler envelope is wider than exact ROI; deep event and multiplexing qualification remains pending')
    except BaseException as exc:
        state.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        if worker and worker.poll() is None:
            os.killpg(worker.pid,signal.SIGTERM)
            try:worker.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(worker.pid,signal.SIGKILL);worker.wait()
        raise
    finally:
        if prof.proc is not None and prof.proc.poll() is None:
            try:prof.stop()
            except Exception as exc:state['profiler_cleanup_error']=str(exc)
        if control.exists():control.unlink()
        write(out/'collection.json',state)
        files=[]
        for p in sorted(out.rglob('*')):
            if not p.is_file() or p.is_symlink() or p.name=='sha256-index.json':continue
            files.append(dict(path=str(p.relative_to(out)),size=p.stat().st_size,sha256=file_sha(p)))
        write(out/'sha256-index.json',dict(files=files))
    print(json.dumps(state,ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',choices=DATASETS,required=True)
    parser.add_argument('--output',type=Path,default=Path('/results'))
    args=parser.parse_args();capture(args.dataset,args.output)
