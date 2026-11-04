"""In-container DocOps collector pilot; perf and DevKit are separate passes."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback

from quality import file_sha256, function_qualification, select_samples, workload_records

HERE = Path(__file__).resolve().parent
OUT = Path('/results')


def write(path, value):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    temporary.replace(path)


def cpu_snapshot():
    return {line.split()[0]: list(map(int, line.split()[1:]))
            for line in Path('/proc/stat').read_text().splitlines()
            if line.split()[0] in {f'cpu{i}' for i in range(8)}}


def archive_evidence(out, state):
    """Bind final evidence without loading multi-GB perf files into memory.

    Archiving failure must not leave collection.json claiming final success.
    Preserve the acquisition facts and publish a separate failure record.
    """
    files = {}
    try:
        for path in sorted(out.rglob('*')):
            if path.is_file() and path.name not in ('sha256-index.json', 'archive-error.json'):
                files[str(path.relative_to(out))] = {
                    'bytes': path.stat().st_size, 'sha256': file_sha256(path)}
        write(out/'sha256-index.json', {'files': files})
        return True
    except Exception as exc:
        failure = dict(error=f'{type(exc).__name__}: {exc}', indexed_files_before_failure=files)
        state.update(status='failed', archive_error=failure['error'])
        write(out/'collection.json', state)
        write(out/'archive-error.json', failure)
        return False


def stop(proc):
    if proc and proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', required=True)
    parser.add_argument('--loops', type=int, required=True)
    parser.add_argument('--mode', choices=['perf', 'topdown'], required=True)
    args = parser.parse_args()
    if args.loops < 1:
        parser.error('positive loops required')
    os.sched_setaffinity(0, {9})
    state = dict(schema='docops-collector-pilot-v1', task=args.task, loops=args.loops,
                 mode=args.mode, status='in_progress', workload_cpus='0-7', controller_cpu=9,
                 formal_similarity_eligible=False, workflow_status='not_started')
    write(OUT/'collection.json', state)
    worker = monitor = profiler = None
    handles = []
    try:
        monitor_log = (OUT/'monitor.log').open('x'); handles.append(monitor_log)
        monitor = subprocess.Popen([sys.executable, '-B', str(HERE/'monitor.py')],
                                   stdout=monitor_log, stderr=subprocess.STDOUT, start_new_session=True)
        workload = [sys.executable, '-B', str(HERE/'worker.py'), '--task', args.task,
                    '--loops', str(args.loops), '--mode', args.mode]
        log = (OUT/'workload.log').open('x'); handles.append(log)
        if args.mode == 'perf':
            from native_capture_helpers import bounded
            from native_adapter import attribute, crosscheck, loss_diagnostics, parse, profile
            argv = ['perf', 'record', '-e', 'cycles:u', '-F', '49', '-k', 'mono',
                    '--call-graph', 'dwarf,16384', '-o', str(OUT/'perf.data'), '--', *workload]
            state['record_argv'] = argv
            err = (OUT/'perf-record.stderr').open('x'); handles.append(err)
            state['workflow_status'] = 'running'; write(OUT/'collection.json', state)
            worker = subprocess.Popen(argv, stdout=log, stderr=err, start_new_session=True)
            code = worker.wait(timeout=600)
            state['record_returncode'] = code
            if (OUT/'perf.data').exists():
                (OUT/'perf.data').chmod(0o644)
            if code:
                raise RuntimeError('perf/workload returned nonzero')
            (OUT/'monitor.stop').touch(); monitor.wait(timeout=10)
            if monitor.returncode:
                raise RuntimeError('identity monitor failed')
            counts, records, intervals = workload_records(OUT, args.task, args.loops)
            state.update(workflow_status='passed', counts=counts, roi_intervals_ns=intervals,
                         roi_seconds=sum(end-start for start,end in intervals)/1e9)
            write(OUT/'collection.json', state)
            bounded(['perf', 'script', '--no-inline', '--ns', '-F', '+pid', '-i', str(OUT/'perf.data')], OUT/'samples.txt')
            bounded(['perf', 'script', '--no-inline', '--ns', '-G', '-F', 'pid,tid,time,period,event',
                     '-i', str(OUT/'perf.data')], OUT/'counter-samples.txt')
            bounded(['perf', 'report', '--stdio', '--header', '--stats', '--no-children', '--call-graph', 'none',
                     '--percent-limit', '0.5', '-i', str(OUT/'perf.data')], OUT/'perf-report.txt')
            bounded(['perf', 'buildid-list', '-i', str(OUT/'perf.data')], OUT/'buildids.txt')
            samples = parse(OUT/'samples.txt')
            state['sample_crosscheck'] = crosscheck(samples, OUT/'counter-samples.txt')
            dispatcher = json.loads((OUT/'measurement-ready.json').read_text())['pid']
            selected, excluded = select_samples(samples, intervals, dispatcher)
            if not selected:
                raise ValueError('no workflow samples')
            attribute(selected, OUT/'identities.jsonl')
            result = profile(selected, (intervals[0][0], intervals[-1][1]))
            result.update(denominator='Union of workflow intervals and non-dispatcher descendants; raw cycles:u sample period',
                          all_recorded_samples=len(samples), all_recorded_period=sum(s['period'] for s in samples),
                          excluded_period=excluded, exact_interval_filtering=True,
                          dispatcher_pid_excluded=dispatcher)
            result['capture_quality'] = loss_diagnostics((OUT/'perf-record.stderr').read_text(),
                                                        (OUT/'perf-report.txt').read_text())
            if result['capture_quality']['aggregated_sample_events'] not in (None, len(samples)):
                raise ValueError('perf aggregate sample count differs from parsed count')
            write(OUT/'profile.json', result)
            state.update(roi_samples=result['roi_samples'], roi_period=result['roi_period'], quality=result['quality'])
            state['function_qualification'] = function_qualification(result['quality'])
            if not state['function_qualification']['stack_eligible']:
                raise ValueError('unusable stack quality; raw retained')
        else:
            from topdown_summary import parse as parse_topdown
            worker = subprocess.Popen(workload, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic()+60
            while not (OUT/'measurement-ready.json').exists():
                if worker.poll() is not None or time.monotonic()>deadline:
                    raise RuntimeError('workload did not reach first workflow boundary')
                time.sleep(.01)
            stdout = (OUT/'devkit.stdout.txt').open('x'); stderr = (OUT/'devkit.stderr.txt').open('x')
            handles += [stdout, stderr]
            argv = ['stdbuf', '-oL', '-eL', 'devkit', 'tuner', 'top-down', '-c', '0-7', '-L', '0', '-i', '1', '-l', '0']
            state['profiler_argv'] = argv
            state['profiler_spawn_ns'] = time.monotonic_ns()
            state['cpu_before'] = cpu_snapshot()
            profiler = subprocess.Popen(argv, stdout=stdout, stderr=stderr, start_new_session=True,
                                        cwd='/opt/devkit/DevKit-Tuner-CLI-26.0.RC1-Linux-aarch64')
            deadline = time.monotonic()+30
            while 'time of PmuRead:' not in (OUT/'devkit.stdout.txt').read_text(errors='replace'):
                if profiler.poll() is not None or time.monotonic()>deadline:
                    raise RuntimeError('DevKit exited or failed to become ready')
                time.sleep(.02)
            state['profiler_ready_ns'] = time.monotonic_ns()
            state['profiler_affinity'] = sorted(os.sched_getaffinity(profiler.pid))
            if state['profiler_affinity'] != [9]:
                raise ValueError('DevKit controller not on CPU 9')
            (OUT/'measurement-go').touch()
            state['workflow_status'] = 'running'; write(OUT/'collection.json', state)
            code = worker.wait(timeout=600)
            if code:
                raise RuntimeError('Topdown workload failed')
            state['profiler_stop_requested_ns'] = time.monotonic_ns()
            os.killpg(profiler.pid, signal.SIGINT)
            rc = profiler.wait(timeout=20)
            state['profiler_exited_ns'] = time.monotonic_ns()
            state['profiler_returncode'] = rc
            state['cpu_after'] = cpu_snapshot()
            deltas = [[b-a for a,b in zip(state['cpu_before'][cpu], state['cpu_after'][cpu])]
                      for cpu in state['cpu_before']]
            ticks = sum(sum(delta[:8]) for delta in deltas)
            state['cpu_window'] = {'idle_pct': 100*sum(delta[3] for delta in deltas)/ticks,
                                   'total_ticks': ticks,
                                   'scope': 'CPU 0-7 complete profiler envelope; guest not double-counted; iowait not idle'}
            if rc:
                raise RuntimeError('DevKit returned nonzero')
            parsed = parse_topdown((OUT/'devkit.stdout.txt').read_text())
            counts, records, intervals = workload_records(OUT, args.task, args.loops)
            state.update(workflow_status='passed', counts=counts, roi_intervals_ns=intervals,
                         roi_seconds=sum(end-start for start,end in intervals)/1e9,
                         exact_roi_event_filtering=False,
                         measurement_scope='CPU-scoped envelope includes initial read, inter-step/round gaps and tail; excluded work is affinity-isolated on CPU 9',
                         metrics=parsed['metrics'])
            envelope = (state['profiler_exited_ns']-state['profiler_spawn_ns'])/1e9
            state['profiler_envelope_seconds'] = envelope
            state['outside_workflow_envelope_seconds'] = envelope-state['roi_seconds']
            write(OUT/'topdown-summary.json', {**parsed, 'exact_roi_event_filtering': False,
                                               'formal_similarity_eligible': False,
                                               'scope': state['measurement_scope']})
        state['status'] = 'passed'
    except BaseException as exc:
        state.update(status='failed', error=f'{type(exc).__name__}: {exc}', traceback=traceback.format_exc())
    finally:
        stop(worker); stop(profiler)
        (OUT/'monitor.stop').touch()
        if monitor and monitor.poll() is None:
            try: monitor.wait(timeout=10)
            except subprocess.TimeoutExpired: stop(monitor)
        if monitor and monitor.returncode:
            state.update(status='failed', monitor_error=f'returncode {monitor.returncode}')
        for handle in handles: handle.close()
        write(OUT/'collection.json', state)
        archive_evidence(OUT, state)
    print(json.dumps(state, ensure_ascii=False), flush=True)
    return 0 if state['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
