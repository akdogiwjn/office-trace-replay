#!/usr/bin/env python3
"""Timestamping pipe reader: prefixes every line read on stdin (or a FIFO) with
its CLOCK_MONOTONIC arrival time in nanoseconds. Used to timestamp the runner's
stdout lines (notably '[scene/dataset] start:' which marks the ROI boundary).

Usage: tstamp_pipe.py INPUT_FIFO OUTPUT_LOG
"""
import sys
import time

inp, outp = sys.argv[1], sys.argv[2]
with open(inp, "r") as src, open(outp, "w", buffering=1) as dst:
    for line in src:
        dst.write("%d %s" % (time.clock_gettime_ns(time.CLOCK_MONOTONIC), line))
