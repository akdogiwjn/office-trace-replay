"""Read-only process identities and affinity, sampled outside workload CPUs."""
import json
import os
from pathlib import Path
import time

os.sched_setaffinity(0, {9})
previous = {}
with Path('/results/identities.jsonl').open('x', buffering=1) as stream:
    while not Path('/results/monitor.stop').exists():
        started = time.monotonic()
        current = {}
        for path in Path('/proc').iterdir():
            if not path.name.isdigit() or int(path.name) == os.getpid():
                continue
            try:
                stat = (path/'stat').read_text().rsplit(') ', 1)[1].split()
                row = dict(pid=int(path.name), ppid=int(stat[1]), start_ticks=int(stat[19]),
                           comm=(path/'comm').read_text().strip(),
                           argv=[v.decode(errors='replace') for v in (path/'cmdline').read_bytes().split(b'\0') if v],
                           cwd=os.readlink(path/'cwd'), tids=sorted(int(p.name) for p in (path/'task').iterdir()),
                           affinity=sorted(os.sched_getaffinity(int(path.name))))
            except (OSError, ValueError, IndexError):
                continue
            current[row['pid']] = row
            if previous.get(row['pid']) != row:
                stream.write(json.dumps(dict(event='identity', t_ns=time.monotonic_ns(), **row))+'\n')
        for pid in previous.keys()-current.keys():
            stream.write(json.dumps(dict(event='gone', t_ns=time.monotonic_ns(), pid=pid))+'\n')
        previous = current
        time.sleep(max(0, .01-(time.monotonic()-started)))
    stream.write(json.dumps(dict(event='monitor_end', t_ns=time.monotonic_ns()))+'\n')
