"""One dataset, one loop, perf around the real installed entry; no LLM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import time

from native_profile import attribute, crosscheck, loss_diagnostics, parse, profile, roi

HERE = Path(__file__).resolve().parent
PROJECT = Path('/opt/office-trace-replay')
DATASETS=('opm','tlc','egrid','hr_metro','industry_productivity','irs_w4','sba1919')


def workload_arguments(dataset,out):
    out=Path(out)
    if dataset in ('opm','tlc'):
        return [sys.executable,'-s',str(HERE/'legacy_capture.py'),'--dataset',dataset,
                '--results-dir',str(out/'runner'),'--roi',str(out/'legacy-roi.jsonl')]
    return [sys.executable,str(PROJECT/'agent/replay.py'),'--dataset',dataset,'--loops','1',
            '--results-dir',str(out/'runner'),'--container-inspect','/evidence/container-inspect.before.json']


def capture_quality(record_stderr, perf_report, export_warnings):
    return {**loss_diagnostics(record_stderr, perf_report),
            'perf_record_stderr': record_stderr,
            'export_warnings': export_warnings,
            'note': 'Loss diagnostics retain their native units; ROI attribution is unknown. No loss is converted into period.'}


def write(path, data):
    path = Path(path)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    temp.replace(path)


def bounded(argv, output, timeout=120):
    output = Path(output)
    partial = output.with_name(output.name + '.partial')
    stderr = output.with_name(output.name + '.stderr')
    status_path = output.with_name(output.name + '.status.json')
    if any(p.exists() for p in (output, partial, stderr, status_path)):
        raise ValueError('refuse to overwrite export: ' + str(output))
    started = time.monotonic()
    record = dict(argv=argv, status='in_progress', timeout_seconds=timeout)
    try:
        with partial.open('x') as out, stderr.open('x') as err:
            proc = subprocess.Popen(argv, stdout=out, stderr=err, start_new_session=True)
            try:
                code = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                record.update(status='timeout', returncode=proc.returncode)
                raise
        record.update(returncode=code, status='success' if code == 0 else 'failed')
        if code:
            raise RuntimeError('export failed: ' + repr(argv))
        partial.replace(output)
    finally:
        record['elapsed_seconds'] = time.monotonic() - started
        write(status_path, record)


def run(dataset, out):
    out = Path(out)
    if (out / 'collection.json').exists() or (out / 'perf.data').exists():
        raise ValueError('capture destination already used')
    out.mkdir(parents=True, exist_ok=True)
    os.sched_setaffinity(0, {9})
    state = dict(schema_version='agent-hotspot-native-pilot-v1', dataset_id=dataset,
                 loops=1, rate_hz=49, event='cycles:u', call_graph='dwarf,16384',
                 clock='CLOCK_MONOTONIC', workload_cpus='0-7', monitor_cpu=9,
                 status='in_progress', workload_status='not_started',
                 perf_record_status='not_started', export_status='not_started',
                 parse_status='not_started', analysis_scope='single-run descriptive pilot')
    write(out / 'collection.json', state)
    monitor = None
    stop = out / 'monitor.stop'
    try:
        state['perf_version'] = subprocess.check_output(['perf', 'version'], text=True).strip()
        legacy=dataset in ('opm','tlc')
        scene='pdf' if dataset=='opm' else 'xlsx'
        entry=PROJECT/('document-oe/run.py' if legacy else 'agent/replay.py')
        case=PROJECT/'agent/datasets'/dataset
        files=([entry,PROJECT/'document-oe/lock.json',
                Path('/opt/document-bench/bin/run_document_scene_loop.py'),
                Path('/opt/document-bench/operations')/(scene+'_key_operations.json')]
               if legacy else [entry,case/'lock.json',case/'recipe.json',case/'provenance.json'])
        state['frozen_hashes']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        preflight=([sys.executable,str(entry),'--validate-only','--installed'] if legacy else
                   [sys.executable,str(entry),'--dataset',dataset,'--validate-only'])
        with (out/'preflight.log').open('x') as log:
            subprocess.run(preflight,
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60)
        monitor = subprocess.Popen([sys.executable, str(HERE/'monitor.py'), str(out/'identities.jsonl'), str(stop)],
                                   stdout=(out/'monitor.stdout').open('x'), stderr=(out/'monitor.stderr').open('x'))
        for _ in range(100):
            if (out/'identities.jsonl').exists() and (out/'identities.jsonl').stat().st_size:
                break
            if monitor.poll() is not None:
                raise RuntimeError('identity monitor exited before workload')
            time.sleep(.01)
        else:
            raise RuntimeError('identity monitor did not become ready')
        argv = ['perf','record','-e','cycles:u','-F','49','-k','mono','--call-graph','dwarf,16384',
                '-o',str(out/'perf.data'),'--','taskset','-c','0-7',*workload_arguments(dataset,out)]
        state.update(perf_record_argv=argv, workload_status='in_progress',perf_record_status='in_progress')
        write(out/'collection.json', state)
        with (out/'workload.log').open('x') as log, (out/'perf-record.stderr').open('x') as err:
            result = subprocess.run(argv, stdout=log, stderr=err, timeout=1200)
        state['perf_record_returncode'] = result.returncode
        if (out/'perf.data').is_file():
            (out/'perf.data').chmod(0o644)
        stop.touch()
        monitor.wait(timeout=10)
        state['monitor_returncode'] = monitor.returncode
        if monitor.returncode:
            raise RuntimeError('identity monitor failed')
        summaries = list((out/'runner'/(scene if legacy else dataset)).glob('*/summary.json'))
        if len(summaries) != 1:
            raise ValueError('expected exactly one runner summary')
        summary = json.loads(summaries[0].read_text())
        state['runner_summary'] = str(summaries[0].relative_to(out))
        counts={k:summary.get({'requested':'requested_iterations','completed':'completed_iterations'}.get(k,k) if legacy else k)
                for k in ('requested','completed','successes','failures')}
        state['workload_counts'] = counts
        if legacy:
            inspected=json.loads(Path('/evidence/container-inspect.before.json').read_text())[0]
            if not inspected['Id'].startswith(os.uname().nodename):raise ValueError('legacy container identity mismatch')
            state['actual_image_id']=inspected['Image']
            workspace=Path(summary['workspace'])
            roi_path=out/'legacy-roi.jsonl'
            state['roi_observation']='read-only measurement wrapper around frozen run_iteration; runner/workload files unchanged'
        else:
            state['actual_image_id'] = summary['context']['container']['actual_image_id']
            workspace=summaries[0].parent/'iteration-0001/workspace'
            roi_path=summaries[0].parent/'iteration-0001/roi.jsonl'
        state['roi_path']=str(roi_path.relative_to(out))
        business = json.loads((workspace/'output/business_verification.json').read_text())
        ok=counts==dict(requested=1,completed=1,successes=1,failures=0)
        ok=ok and (not summary['interrupted'] if legacy else summary['status']=='success' and summary['evidence_complete'])
        ok=ok and business['status']=='success' and not business.get('failures')
        state['workload_status'] = 'success' if ok else 'failed'
        state['business_verification'] = business['status']
        if result.returncode or not ok or not (out/'perf.data').stat().st_size:
            raise RuntimeError('workload or perf recording failed')
        if legacy:
            shutil.copytree(workspace,out/'legacy-workspace')
        state['perf_record_status'] = 'success'
        state['export_status'] = 'in_progress'
        write(out/'collection.json',state)
        bounded(['perf','script','--no-inline','--ns','-F','+pid','-i',str(out/'perf.data')],out/'samples.txt')
        bounded(['perf','script','--no-inline','--ns','-G','-F','pid,tid,time,period,event',
                 '-i',str(out/'perf.data')],out/'counter-samples.txt')
        bounded(['perf','report','--stdio','--header','--stats','--no-children','--call-graph','none',
                 '--percent-limit','0.5','-i',str(out/'perf.data')],out/'perf-report.txt')
        bounded(['perf','buildid-list','-i',str(out/'perf.data')],out/'buildids.txt')
        bounded(['perf','evlist','-v','-i',str(out/'perf.data')],out/'events.txt')
        state['export_status'] = 'success'
        state['parse_status'] = 'in_progress'
        write(out/'collection.json',state)
        samples = parse(out/'samples.txt')
        state['sample_crosscheck'] = crosscheck(samples,out/'counter-samples.txt')
        values = profile(attribute(samples,out/'identities.jsonl'),roi(roi_path))
        values.update(dataset_id=dataset,
                      pdf_applicant_count=10 if dataset in ('opm','irs_w4', 'sba1919') else None,
                      image_id=state['actual_image_id'])
        text = (out/'perf-record.stderr').read_text()
        report = (out/'perf-report.txt').read_text()
        losses = loss_diagnostics(text,report)
        if losses['aggregated_sample_events'] != len(samples):
            raise ValueError('perf aggregated sample count differs from parsed samples')
        values['capture_quality'] = capture_quality(text, report, (out/'samples.txt.stderr').read_text())
        write(out/'profile.json',values)
        state.update(parse_status='success',status='success',pipeline_complete=True,
                     function_profile_quality=values['quality'],
                     independent_audit='not_run; functional image qualification already recorded separately',
                     roi_period=values['roi_period'],roi_samples=values['roi_samples'])
    except Exception as exc:
        state.update(status='failed',error=f'{type(exc).__name__}: {exc}',pipeline_complete=False)
        raise
    finally:
        stop.touch(exist_ok=True)
        if monitor is not None and monitor.poll() is None:
            monitor.terminate()
            monitor.wait(timeout=5)
        write(out/'collection.json',state)
        entries=[]
        for p in sorted(out.rglob('*')):
            if not p.is_file() or p.is_symlink() or p.name=='sha256-index.json':
                continue
            h=hashlib.sha256()
            with p.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1048576),b''): h.update(chunk)
            entries.append(dict(path=str(p.relative_to(out)),size=p.stat().st_size,sha256=h.hexdigest()))
        write(out/'sha256-index.json',dict(files=entries,file_count=len(entries)))
    print(json.dumps(dict(status=state['status'],roi_period=state.get('roi_period'),roi_samples=state.get('roi_samples'))),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',choices=DATASETS,default='irs_w4')
    parser.add_argument('--output',type=Path,default=Path('/results'))
    args=parser.parse_args()
    run(args.dataset,args.output)
