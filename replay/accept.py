#!/usr/bin/env python3
"""Independent complete verifier using this run's frozen execution source."""
import argparse
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--source', required=True, type=Path)
parser.add_argument('--dataset', required=True)
parser.add_argument('--kind', required=True)
parser.add_argument('--workspace', required=True, type=Path)
parser.add_argument('--report', required=True, type=Path)
args = parser.parse_args()
sys.path.insert(0, str(args.source))
import office
from office_trace_bench.contracts import dataset_path
from office_trace_bench.verify import verify
report = verify(dataset_path(args.kind, args.dataset), args.workspace, args.report)
print(args.dataset, report['status'], report['failures'], flush=True)
raise SystemExit(0 if report['status'] == 'success' else 1)
