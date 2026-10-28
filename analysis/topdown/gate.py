"""Measurement-only affinity/control hooks; frozen runtime files are unchanged."""
import json
import os
from pathlib import Path
import socket
import time


def exchange(path, request, timeout=60):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(path))
        client.sendall((json.dumps(request)+'\n').encode())
        response = client.makefile('r').readline(1048576)
    if not response:
        raise RuntimeError('measurement controller disconnected')
    value = json.loads(response)
    if value.get('status') != 'success':
        raise RuntimeError('measurement controller: '+str(value))
    return value


class Gate:
    def __init__(self, control, events, cpus=range(8), monitor_cpu=9):
        self.control, self.events = Path(control), Path(events)
        self.cpus, self.monitor_cpu = set(cpus), monitor_cpu
        self.active = False

    def log(self, event, **extra):
        with self.events.open('a') as stream:
            stream.write(json.dumps(dict(event=event,monotonic_ns=time.monotonic_ns(),
                pid=os.getpid(),affinity=sorted(os.sched_getaffinity(0)),**extra))+'\n')

    def begin(self):
        if self.active:
            raise ValueError('nested/duplicate measurement ROI')
        if os.sched_getaffinity(0) != {self.monitor_cpu}:
            raise ValueError('preflight must remain on monitor CPU')
        exchange(self.control,dict(action='begin'))
        os.sched_setaffinity(0,self.cpus)
        self.active = True
        self.log('workload_affinity_enabled')

    def end(self, marker):
        if not self.active:
            raise ValueError('measurement end without start')
        os.sched_setaffinity(0,{self.monitor_cpu})
        self.log('workload_affinity_disabled',roi_end_ns=marker['monotonic_ns'])
        self.active = False
        exchange(self.control,dict(action='end',marker=marker))

    def boundary(self, original):
        def observed(folder, recipe, index, scope, event):
            selected = scope == 'loop_including_reset'
            if selected and event == 'start':
                self.begin()
            marker = original(folder,recipe,index,scope,event)
            if selected and event == 'start':
                if 'record_error' in marker:
                    self.end(marker)
                    raise RuntimeError('ROI marker write failed')
                self.log('formal_roi_start',marker=marker)
            if selected and event == 'end':
                self.end(marker)
            return marker
        return observed
