"""Read-only /proc identities. Runs outside the workload CPU set."""
import argparse
import json
import os
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('stop', type=Path)
    args = parser.parse_args()
    os.sched_setaffinity(0, {9})
    previous = {}
    polls = 0
    with args.output.open('x', buffering=1) as stream:
        while not args.stop.exists():
            started = time.monotonic_ns()
            current = {}
            for p in Path('/proc').iterdir():
                if not p.name.isdigit() or int(p.name) == os.getpid():
                    continue
                try:
                    stat = (p / 'stat').read_text().rsplit(') ', 1)[1].split()
                    argv = [v.decode('utf-8', 'replace') for v in (p / 'cmdline').read_bytes().split(b'\0') if v]
                    tids = sorted(int(t.name) for t in (p / 'task').iterdir() if t.name.isdigit())
                    item = dict(pid=int(p.name), ppid=int(stat[1]), start_ticks=int(stat[19]),
                                comm=(p / 'comm').read_text().strip(), argv=argv,
                                cwd=os.readlink(p / 'cwd'), tids=tids)
                except (OSError, ValueError, IndexError):
                    continue
                current[item['pid']] = item
                if previous.get(item['pid']) != item:
                    stream.write(json.dumps(dict(t_ns=time.monotonic_ns(), event='identity', **item)) + '\n')
            for pid in previous.keys() - current.keys():
                stream.write(json.dumps(dict(t_ns=time.monotonic_ns(), event='gone', pid=pid)) + '\n')
            previous = current
            polls += 1
            time.sleep(max(0, (10_000_000 - (time.monotonic_ns() - started)) / 1e9))
        stream.write(json.dumps(dict(t_ns=time.monotonic_ns(), event='monitor_end', polls=polls)) + '\n')


if __name__ == '__main__':
    main()
