"""Measurement-only wrapper around the installed, unchanged DocOps entry."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', required=True)
    parser.add_argument('--loops', type=int, required=True)
    parser.add_argument('--mode', choices=['perf', 'topdown'], required=True)
    args = parser.parse_args()
    out = Path('/results')
    os.sched_setaffinity(0, {9})
    spec = importlib.util.spec_from_file_location('docops_measured_entry', '/opt/docops/replay.py')
    entry = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = entry
    spec.loader.exec_module(entry)
    original_step, original_popen = entry.run_step, subprocess.Popen
    phase = {'value': None}
    events = out / 'measurement-events.jsonl'

    def log(event, **values):
        with events.open('a') as stream:
            stream.write(json.dumps(dict(event=event, monotonic_ns=time.monotonic_ns(),
                                         dispatcher_pid=os.getpid(), **values))+'\n')

    def spawn(argv, *positional, **kwargs):
        measured = phase['value'] == 'workflow'
        actual = ['taskset', '-c', '0-7', *argv] if measured else argv
        proc = original_popen(actual, *positional, **kwargs)
        log('spawn', pid=proc.pid, phase=phase['value'], frozen_argv=argv, actual_argv=actual,
            inherited_dispatcher_affinity=sorted(os.sched_getaffinity(0)))
        return proc

    first = True
    def observed(step, state, timeout=None):
        nonlocal first
        if first and step.get('phase') == 'workflow':
            first = False
            (out/'measurement-ready.json').write_text(json.dumps({'pid': os.getpid(), 'clock': 'CLOCK_MONOTONIC'}))
            if args.mode == 'topdown':
                deadline = time.monotonic()+60
                while not (out/'measurement-go').exists():
                    if time.monotonic()>deadline:
                        raise TimeoutError('measurement controller did not release workload')
                    time.sleep(.01)
        phase['value'] = step.get('phase')
        try:
            return original_step(step, state, timeout=timeout)
        finally:
            phase['value'] = None

    log('worker_start', affinity=sorted(os.sched_getaffinity(0)), task=args.task, loops=args.loops)
    entry.run_step = observed
    subprocess.Popen = spawn
    sys.argv = [entry.__file__, 'run', '--task', args.task, '--loops', str(args.loops),
                '--results-dir', str(out/'runner'), '--workdir', '/workspace/docops/work']
    try:
        code = entry.cli()
        log('worker_end', returncode=code)
        return code
    finally:
        subprocess.Popen = original_popen
        entry.run_step = original_step


if __name__ == '__main__':
    raise SystemExit(main())
