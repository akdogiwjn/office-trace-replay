#!/usr/bin/env python3
"""Bounded, non-overwriting export for an existing native capture.

The perf.data file is read-only input. Failed and timed-out exports retain
their partial stdout, stderr, and a machine-readable stop reason.
"""
import argparse
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time


def bounded_export(perf_data, output, status_path, timeout_seconds, *, command=None,
                   popen_factory=subprocess.Popen, terminate_grace=2,
                   force_input=False):
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError('timeout_seconds must be finite and positive')
    perf_data, output, status_path = map(Path, (perf_data, output, status_path))
    partial = output.with_name(output.name + '.partial')
    stderr = output.with_name(output.name + '.stderr.log')
    conflicts = [path for path in (output, partial, stderr, status_path) if path.exists()]
    if conflicts:
        return {'status': 'not_started',
                'reason': 'refused: destination artifact already exists; choose a new destination to preserve prior evidence',
                'existing_artifacts': [str(path) for path in conflicts],
                'output': str(output), 'partial_output': str(partial),
                'stderr_log': str(stderr), 'status_path': str(status_path),
                'perf_data': str(perf_data)}
    status_path.parent.mkdir(parents=True, exist_ok=True)
    if not perf_data.is_file():
        result = {'status': 'not_started', 'reason': 'perf.data missing',
                  'perf_data': str(perf_data)}
        if not status_path.exists():
            status_path.write_text(json.dumps(result, indent=2) + '\n')
        return result
    argv = command or ['perf', 'script', *( ['-f'] if force_input else [] ),
                       '-i', str(perf_data)]
    started = time.time()
    partial.parent.mkdir(parents=True, exist_ok=True)
    return_code = None
    reason = None
    timed_out = False
    try:
        with partial.open('wb') as stdout, stderr.open('wb') as err:
            proc = popen_factory(argv, stdout=stdout, stderr=err, start_new_session=True)
            try:
                proc.communicate(timeout=timeout_seconds)
                return_code = proc.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                reason = f'perf script exceeded {timeout_seconds}s timeout'
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    proc.communicate(timeout=terminate_grace)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    proc.communicate()
                return_code = proc.returncode
    except OSError as exc:
        reason = f'could not start perf script: {type(exc).__name__}: {exc}'
    if not timed_out and return_code == 0:
        os.replace(partial, output)
        status = 'complete'
        reason = None
    else:
        status = 'incomplete'
        if reason is None:
            reason = f'perf script exited with status {return_code}'
    result = {
        'status': status,
        'reason': reason,
        'return_code': return_code,
        'timed_out': timed_out,
        'timeout_seconds': timeout_seconds,
        'elapsed_seconds': round(time.time() - started, 3),
        'perf_data': str(perf_data),
        'output': str(output) if status == 'complete' else None,
        'partial_output': str(partial) if partial.exists() else None,
        'stderr_log': str(stderr),
        'profile_eligible': False,
    }
    status_path.write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('perf_data', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('status', type=Path)
    parser.add_argument('--timeout-seconds', type=float, default=900)
    parser.add_argument('--report-sort', choices=('comm', 'comm,dso', 'comm,dso,symbol', 'dso'),
                        help='Export a bounded derived perf report instead of perf script')
    parser.add_argument('--force-input', action='store_true',
                        help='pass perf --force for readable captures owned by another uid; input remains read-only')
    args = parser.parse_args()
    command = None
    if args.report_sort:
        command = ['perf', 'report', *( ['-f'] if args.force_input else [] ),
                   '--stdio', '--call-graph', 'none', '--no-children',
                   '--sort', args.report_sort, '--percent-limit', '0.01', '-i', str(args.perf_data)]
    result = bounded_export(args.perf_data, args.output, args.status,
                            args.timeout_seconds, command=command,
                            force_input=args.force_input)
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
