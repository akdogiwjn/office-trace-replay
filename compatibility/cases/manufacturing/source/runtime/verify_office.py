#!/usr/bin/env python3
"""Run the measured-loop verifier for this staged dataset."""
import os
from pathlib import Path
import sys

project = Path(os.environ.get('OFFICE_TRACE_PROJECT', '/workspace'))
sys.path.insert(0, str(project))
import office
from office_trace_bench.contracts import dataset_path, read_json
from office_trace_bench.verify import verify

if __name__ == '__main__':
    workspace = Path(__file__).resolve().parents[1]
    selection = read_json(workspace / 'input/dataset_manifest.json')
    report = verify(dataset_path(selection['kind'], selection['dataset_id']), workspace,
                    workspace / 'output/business_verification.json', scope='loop',
                    deferred_outputs=('xlsx_enhancement_summary.json',)
                    if selection['kind'] == 'xlsx' else ())
    print(report['status'])
    raise SystemExit(0 if report['status'] == 'success' else 1)
