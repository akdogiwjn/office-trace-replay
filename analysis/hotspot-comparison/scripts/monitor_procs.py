#!/usr/bin/env python3
"""Lightweight process-tree + thread-CPU monitor.

Polls /proc and records:
  - identity.jsonl: one event per (first seen OR comm change) with pid, ppid,
    comm, cmdline and the CLOCK_MONOTONIC time. Re-reading cmdline on comm
    change captures exec'd processes (e.g. bash -> runner python3).
  - monitor.jsonl: one line per poll with the alive process list and per-thread
    CPU counters (utime+stime from /proc/<pid>/task/<tid>/stat), used for
    parallelism analysis and tid -> pid mapping.

The monitor excludes itself and stops when the file HOTSPOT_MONITOR_STOP/alive
is removed.

Usage: monitor_procs.py OUTDIR POLL_INTERVAL_MS
"""
import json
import os
import sys
import time

SELF = os.getpid()
PROC = "/proc"


def clock_ns():
    return time.clock_gettime_ns(time.CLOCK_MONOTONIC)


def read_cmdline(pid):
    try:
        with open(f"{PROC}/{pid}/cmdline", "rb") as fh:
            raw = fh.read()
        return raw.replace(b"\x00", b" ").decode("utf-8", "replace").strip()
    except OSError:
        return ""


def read_comm(pid):
    try:
        with open(f"{PROC}/{pid}/comm") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def snapshot():
    procs = {}
    for entry in os.listdir(PROC):
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid == SELF:
            continue
        try:
            with open(f"{PROC}/{pid}/stat") as fh:
                parts = fh.read().rsplit(") ", 1)[1].split()
            ppid = int(parts[1])
        except (OSError, IndexError, ValueError):
            continue
        comm = read_comm(pid)
        threads = []
        taskdir = f"{PROC}/{pid}/task"
        try:
            tids = os.listdir(taskdir)
        except OSError:
            tids = []
        for tid in tids:
            if not tid.isdigit():
                continue
            try:
                with open(f"{taskdir}/{tid}/stat") as fh:
                    tparts = fh.read().rsplit(") ", 1)[1].split()
                utime = int(tparts[11])
                stime = int(tparts[12])
                with open(f"{taskdir}/{tid}/comm") as fh:
                    tcomm = fh.read().strip()
            except (OSError, IndexError, ValueError):
                continue
            threads.append([int(tid), tcomm, utime, stime])
        procs[pid] = (ppid, comm, threads)
    return procs


def main():
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    outdir = sys.argv[1]
    interval_ms = float(sys.argv[2])
    ident_fh = open(os.path.join(outdir, "identity.jsonl"), "w", buffering=1)
    poll_fh = open(os.path.join(outdir, "monitor.jsonl"), "w", buffering=1)
    current = {}  # pid -> comm of the last identity event
    last_alive = {}  # pid -> last seen ns
    stop_flag = os.environ.get("HOTSPOT_MONITOR_STOP")
    while True:
        now = clock_ns()
        try:
            procs = snapshot()
        except Exception:
            procs = {}
        records = []
        threads_out = []
        for pid, (ppid, comm, threads) in procs.items():
            last_alive[pid] = now
            if pid not in current or current[pid] != comm:
                ident_fh.write(json.dumps({
                    "t_ns": now, "pid": pid, "ppid": ppid, "comm": comm,
                    "cmdline": read_cmdline(pid)}) + "\n")
                current[pid] = comm
            records.append({"pid": pid, "ppid": ppid, "comm": comm})
            for tid, tcomm, utime, stime in threads:
                threads_out.append([pid, tid, tcomm, utime, stime])
        poll_fh.write(json.dumps({"t_ns": now, "procs": records,
                                  "threads": threads_out}) + "\n")
        deadline = now + int(interval_ms * 1_000_000)
        while True:
            remaining = deadline - clock_ns()
            if remaining <= 0:
                break
            time.sleep(remaining / 1e9)
        if stop_flag and not os.path.exists(os.path.join(stop_flag, "alive")):
            break
    # last-seen table for window end computation
    with open(os.path.join(outdir, "identity-last-seen.json"), "w") as fh:
        json.dump(last_alive, fh)
    ident_fh.close()
    poll_fh.close()


if __name__ == "__main__":
    sys.exit(main())
