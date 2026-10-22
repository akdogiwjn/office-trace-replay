#!/usr/bin/env python3
"""Offline analysis of one CPU-measurement campaign directory.

Inputs (produced by cpu_measurement_trial.py):
  <campaign>/<dataset>/{clock-anchor.json, monitor/, ledgers/,
                        workload/xlsx/<stamp>/{summary.json, iterations.jsonl},
                        container.log, host-bindings.json}

Method, kept honest about what is measured versus estimated:

  * ROI: the single iteration window [finished_at - elapsed_seconds,
    finished_at] converted to CLOCK_MONOTONIC via the container clock anchor.
    It contains workspace reset plus P01-P04 exactly like the existing loop;
    preflight/validation before the loop and post-loop writing are outside.
  * Denominator: sum of per-thread (utime+stime) increments over the ROI for
    every process in the workload tree (the entry.py process and all its
    descendants, which includes the runner, every recipe tool, bash and
    LibreOffice).  Each thread is counted exactly once; process-level counters
    are never added on top. All processes use polled CPU, including Python
    interpreter shutdown after atexit. A ledger's process CPU is an atexit
    snapshot, not a final counter, and must not replace larger monitor values.
  * Numerator: the ledger buckets (load_workbook, readonly_lazy_parse,
    workbook_save) of the in-ROI Python processes, summed per bucket.  Within
    one process the interval stack already de-duplicates; the union of the
    three buckets is their sum.
  * Cross-checks: signed and absolute monitor-minus-atexit differences expose
    both shutdown CPU and polling discrepancies; they do not bound CPU from
    completely unobserved processes. Negative or impossible values, missing ledgers for processes
    that must have run Python, or a numerator above the denominator all fail
    qualification.

Usage: analyze_cpu_measurement.py <campaign-dir> <dataset> [--json]
"""
import argparse
import json
import os
import shlex
import sys
from bisect import bisect_right
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CLK_TCK = os.sysconf('SC_CLK_TCK') if hasattr(os, 'sysconf') else 100


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def parse_utc(text):
    return datetime.fromisoformat(text).astimezone(timezone.utc).timestamp()


def command_argv(command):
    try:
        return shlex.split(command)
    except ValueError:
        return []


def is_python(command):
    argv = command_argv(command)
    return bool(argv) and Path(argv[0]).name.startswith('python')


def is_workload_entry(command):
    argv = command_argv(command)
    return (is_python(command) and len(argv) > 1
            and Path(argv[1]).name == 'entry.py'
            and str(Path(argv[1]).parent).endswith('/replay'))


def command_role(command, comm=''):
    """Classify executed operands, never names embedded in shell command text."""
    argv = command_argv(command)
    executable = Path(argv[0]).name if argv else comm
    if executable in ('bash', 'sh', 'dash'):
        return 'shell'
    if 'soffice' in executable or 'soffice' in comm or executable == 'oosplash':
        return 'libreoffice'
    if executable == 'cp':
        return 'copy'
    if is_python(command):
        script = Path(argv[1]).name if len(argv) > 1 else ''
        if script == 'entry.py' or script.startswith('run_document_scene_loop'):
            return 'runner'
        if script == 'monitor_procs.py':
            return 'monitor'
        if script == 'archive_results.py':
            return 'archive'
        if 'recalc' in script:
            return 'recalc'
        if 'atomic' in script:
            return 'atomic_helper'
        if 'verify' in script:
            return 'verifier'
        if 'inspect' in script:
            return 'inspect'
        if 'export' in script:
            return 'export'
        if 'summary' in script:
            return 'summary'
        if 'enhance' in script or 'build' in script:
            return 'helper'
        return 'python_other'
    return 'other'


class Monitor:
    def __init__(self, monitor_dir):
        self.identities = []      # (t_ns, pid, ppid, comm, cmdline)
        self.samples = []         # (t_ns, {pid: {tid: (tcomm, utime, stime)}})
        self.series = {}          # pid -> tid -> [(t_ns, ticks)]
        ident_path = Path(monitor_dir) / 'identity.jsonl'
        poll_path = Path(monitor_dir) / 'monitor.jsonl'
        for line in ident_path.read_text().splitlines():
            if line.strip():
                event = json.loads(line)
                self.identities.append((event['t_ns'], event['pid'], event['ppid'],
                                        event['comm'], event.get('cmdline', '')))
        for line in poll_path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            threads = {}
            for pid, tid, tcomm, utime, stime in row.get('threads', []):
                threads.setdefault(pid, {})[tid] = (tcomm, utime, stime)
                self.series.setdefault(pid, {}).setdefault(tid, []).append(
                    (row['t_ns'], utime + stime))
            self.samples.append((row['t_ns'], threads))

    def children_map(self):
        children = {}
        for _t, pid, ppid, _comm, _cmd in self.identities:
            children.setdefault(ppid, set()).add(pid)
        return children

    def find_root(self, predicate):
        for _t, pid, _ppid, _comm, cmdline in self.identities:
            if predicate(cmdline):
                return pid
        return None

    def subtree(self, root_pid):
        children = self.children_map()
        seen, stack = {root_pid}, [root_pid]
        while stack:
            for child in children.get(stack.pop(), ()):
                if child not in seen:
                    seen.add(child)
                    stack.append(child)
        return seen

    def window_ticks(self, pid, mono_start, mono_end):
        """Per-thread tick deltas inside [mono_start, mono_end]; each thread once."""
        deltas = {}
        series = self.series.get(pid, {})
        for tid, points in series.items():
            if points[-1][0] < mono_start or points[0][0] > mono_end:
                continue
            times = [point[0] for point in points]
            base_index = bisect_right(times, mono_start) - 1
            end_index = bisect_right(times, mono_end) - 1
            base = points[base_index][1] if base_index >= 0 else 0
            top = points[end_index][1]
            if top < base:
                raise ValueError(f'CPU counter decreased for pid={pid} tid={tid}')
            deltas[tid] = top - base
        return deltas



def analyse(dataset_dir):
    dataset_dir = Path(dataset_dir)
    anchor = read_json(dataset_dir / 'clock-anchor.json')
    mono_offset = anchor['real_ns'] - anchor['mono_ns']   # mono -> real

    workload_dirs = list((dataset_dir / 'workload/xlsx').glob('*/'))
    if len(workload_dirs) != 1:
        return {'status': 'failed', 'reason': 'expected exactly one workload run'}
    workload_dir = workload_dirs[0]
    iterations = [json.loads(line) for line in
                  (workload_dir / 'iterations.jsonl').read_text().splitlines() if line.strip()]
    if len(iterations) != 1:
        return {'status': 'failed', 'reason': f'expected one iteration, found {len(iterations)}'}
    iteration = iterations[0]
    summary = read_json(workload_dir / 'summary.json')
    finished_real_ns = int(parse_utc(iteration['finished_at']) * 1e9)
    mono_end = finished_real_ns - mono_offset
    mono_start = mono_end - int(iteration['elapsed_seconds'] * 1e9)

    monitor = Monitor(dataset_dir / 'monitor')
    entry_pid = monitor.find_root(is_workload_entry)
    if entry_pid is None:
        return {'status': 'failed', 'reason': 'cannot find the entry process in the monitor log'}
    workload_pids = monitor.subtree(entry_pid)

    ledgers = {}
    for path in sorted((dataset_dir / 'ledgers').glob('ledger-*.json')):
        payload = read_json(path)
        ledgers[payload['pid']] = payload

    # classify pids by the last identity command line
    last_cmd = {}
    for _t, pid, _ppid, _comm, cmdline in monitor.identities:
        last_cmd[pid] = cmdline
    comm = {}
    for _t, pid, _ppid, name, _cmd in monitor.identities:
        comm[pid] = name

    def role(pid):
        return command_role(last_cmd.get(pid, ''), comm.get(pid, ''))

    # Observed lifetime only: birth/exit times retain one-poll uncertainty.
    first_seen, last_seen = {}, {}
    for t_ns, threads in monitor.samples:
        for pid in threads:
            first_seen.setdefault(pid, t_ns)
            last_seen[pid] = t_ns

    denominator_breakdown = {}
    crosscheck = []
    numerator = {'load_workbook': 0, 'readonly_lazy_parse': 0, 'workbook_save': 0}
    ledger_pids, polled_pids = [], []
    per_process = []
    spanning_nonzero_buckets = []
    excluded_outside_roi = []
    for pid in sorted(workload_pids):
        if role(pid) == 'monitor':
            continue
        if (pid not in first_seen or last_seen[pid] < mono_start
                or first_seen[pid] > mono_end):
            excluded_outside_roi.append(pid)
            continue
        ledger = ledgers.get(pid)
        born_inside = first_seen[pid] >= mono_start
        died_inside = last_seen[pid] <= mono_end
        ticks = monitor.window_ticks(pid, mono_start, mono_end)
        polled_seconds = sum(ticks.values()) / CLK_TCK
        denominator_breakdown.setdefault(role(pid), 0.0)
        denominator_breakdown[role(pid)] += polled_seconds
        polled_pids.append(pid)
        process = {'pid': pid, 'role': role(pid), 'command': last_cmd.get(pid, ''),
                   'monitor_cpu_seconds': round(polled_seconds, 6),
                   'numerator_seconds': 0.0}
        if ledger is not None and born_inside and died_inside:
            snapshot = ledger['cpu_total_process_time_ns'] / 1e9
            difference = polled_seconds - snapshot
            ledger_pids.append(pid)
            crosscheck.append({'pid': pid, 'role': role(pid),
                               'polled_seconds': round(polled_seconds, 4),
                               'atexit_snapshot_seconds': round(snapshot, 4),
                               'monitor_minus_atexit_seconds': round(difference, 6),
                               'absolute_difference_seconds': round(abs(difference), 6),
                               'note': 'atexit precedes interpreter teardown; difference is not a loss bound'})
            for bucket in numerator:
                numerator[bucket] += ledger['buckets'][bucket]['cpu_ns'] / 1e9
            process['numerator_seconds'] = sum(
                ledger['buckets'][bucket]['cpu_ns'] for bucket in numerator) / 1e9
        else:
            if ledger is not None:
                snapshot = ledger['cpu_total_process_time_ns'] / 1e9
                crosscheck.append({'pid': pid, 'role': role(pid),
                                   'polled_window_seconds': round(polled_seconds, 4),
                                   'ledger_atexit_snapshot_seconds': round(snapshot, 4),
                                   'note': 'process spans ROI; polled window used'})
                if any(ledger['buckets'][bucket]['cpu_ns'] for bucket in numerator):
                    spanning_nonzero_buckets.append(pid)
        per_process.append(process)

    denominator = sum(denominator_breakdown.values())
    numerator_union = sum(numerator.values())
    libreoffice = denominator_breakdown.get('libreoffice', 0.0)

    # qualification checks
    verification_files = list((dataset_dir / 'workspace-parent').glob(
        '*/output/business_verification.json'))
    business_ok = False
    if len(verification_files) == 1:
        try:
            report = read_json(verification_files[0])
            business_ok = report.get('status') == 'success' and not report.get('failures')
        except ValueError:
            business_ok = False
    zero_cpu_python_without_ledgers = [
        pid for pid in sorted(workload_pids)
        if pid not in excluded_outside_roi and pid not in ledgers
        and is_python(last_cmd.get(pid, ''))
        and sum(monitor.window_ticks(pid, mono_start, mono_end).values()) == 0]
    checks = {
        'requested_completed_successes_failures': (
            summary.get('requested_iterations') == 1
            and summary.get('completed_iterations') == 1
            and summary.get('successes') == 1 and summary.get('failures') == 0),
        'iteration_success': iteration.get('status') == 'success',
        'numerator_nonnegative': all(value >= 0 for value in numerator.values()),
        'numerator_within_denominator': numerator_union <= denominator + 1e-6,
        'python_processes_have_ledgers': all(
            pid in ledgers for pid in workload_pids if pid not in excluded_outside_roi
            and is_python(last_cmd.get(pid, ''))
            and sum(monitor.window_ticks(pid, mono_start, mono_end).values()) > 0),
        'no_nonzero_unaligned_ledger_buckets': not spanning_nonzero_buckets,
        'roi_seconds_positive': mono_end > mono_start,
        'loop_business_verification': business_ok,
    }
    absolute_differences = [row['absolute_difference_seconds'] for row in crosscheck
                            if 'absolute_difference_seconds' in row]
    return {
        'schema_version': 'total-cpu-analysis-v2',
        'status': 'success' if all(checks.values()) else 'failed',
        'checks': checks,
        'roi': {'mono_start_ns': mono_start, 'mono_end_ns': mono_end,
                'elapsed_seconds': iteration['elapsed_seconds'],
                'reset_seconds': iteration.get('reset_seconds')},
        'denominator_seconds': round(denominator, 4),
        'denominator_breakdown': {k: round(v, 4) for k, v in sorted(denominator_breakdown.items())},
        'denominator_method': ('All workload threads use polled utime+stime within ROI; '
                               'Python interpreter teardown is included through final observed counters; '
                               'atexit snapshots are cross-checks only. Polling remains an estimate '
                               f'(SC_CLK_TCK={CLK_TCK})'),
        'entry_pid': entry_pid,
        'numerator_seconds': {k: round(v, 4) for k, v in numerator.items()},
        'numerator_union_seconds': round(numerator_union, 4),
        'read_write_share': round(numerator_union / denominator, 4) if denominator else None,
        'libreoffice_seconds': round(libreoffice, 4),
        'libreoffice_share': round(libreoffice / denominator, 4) if denominator else None,
        'other_cpu_seconds': round(denominator - numerator_union - libreoffice, 4),
        'other_cpu_definition': 'All CPU outside measured load/lazy/save and LibreOffice; includes Python teardown/GC, hook overhead and other work, not a script-role bucket',
        'workload_pids': len(workload_pids),
        'zero_cpu_python_processes_without_ledgers': [
            {'pid': pid, 'cmdline': last_cmd.get(pid, '')[:120]}
            for pid in zero_cpu_python_without_ledgers],
        'ledger_pids': ledger_pids,
        'polled_pids': polled_pids,
        'excluded_outside_roi_pids': excluded_outside_roi,
        'nonzero_unaligned_ledger_pids': spanning_nonzero_buckets,
        'per_process': per_process,
        'max_absolute_monitor_atexit_difference_seconds': max(absolute_differences, default=0),
        'limitations': [
            '50ms polling can miss short-lived processes and CPU after the last observed tick; no numeric loss bound is established.',
            'ROI uses the recorded realtime/monotonic anchor and rounded finish timestamp; alignment is not independently calibrated.',
            'Numerator uses whole-ledger operation buckets for processes observed inside ROI; lifecycle edges have polling uncertainty.',
            'Single run per dataset; measurement overhead has not been subtracted.',
        ],
        'crosscheck': crosscheck,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign_dir', type=Path)
    parser.add_argument('dataset')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    result = analyse(args.campaign_dir / args.dataset)
    if args.json:
        print(json.dumps(result, indent=1))
    else:
        print(json.dumps(result, indent=1))
    return 0 if result['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
