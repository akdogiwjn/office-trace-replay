#!/usr/bin/env python3
"""ROI calibration marker: sets a unique comm, burns ~300 ms of CPU and prints
the CLOCK_MONOTONIC start of the burn. Its perf samples (comm=PERFROI) provide
the perf-clock anchor; the printed timestamp provides the monotonic anchor.

Run as the first command inside the perf-recorded tree, immediately before
exec'ing the workload runner.
"""
import ctypes
import time

libc = ctypes.CDLL(None)
libc.prctl(15, b"PERFROI", 0, 0, 0)  # PR_SET_NAME

t0 = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
while time.clock_gettime_ns(time.CLOCK_MONOTONIC) - t0 < 300_000_000:
    pass
print("MARKER_MONO_NS", t0, flush=True)
