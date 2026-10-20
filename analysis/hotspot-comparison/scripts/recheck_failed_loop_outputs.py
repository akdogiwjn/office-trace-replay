#!/usr/bin/env python3
"""Recheck preserved failed-run XLSX outputs with the current loop contract.

This reads only the archived output workbooks and loop-level artifacts. It
does not run helpers, LibreOffice, input hashing, or independent deep audit.
The original acquisition/failure records are left untouched.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from compatibility.verification.spreadsheet import verify_semantic_xlsx_loop
from compatibility.verification.verify import Checks

ANALYSIS = ROOT / 'analysis/hotspot-comparison'
CAMPAIGN = ANALYSIS / 'raw/current-loop-verifier-v1'
OUT = ANALYSIS / 'processed/loop-verifier-recheck-v1.json'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def recheck(dataset):
    case = ROOT / 'compatibility/cases' / dataset
    manifest_path = case / 'source/datasets/xlsx' / dataset / 'manifest.json'
    manifest = read(manifest_path)
    expected_path = manifest_path.parent / manifest['expected_file']
    expected = read(expected_path)
    workspace = CAMPAIGN / dataset / 'r1/failure-workspace'
    output = workspace / 'output' / manifest['output_workbook']
    failure_record = CAMPAIGN / dataset / 'r1/failure-record.json'
    if not failure_record.exists():
        failure_record = CAMPAIGN / dataset / 'r1/out/collection-record.json'
    checks = Checks(manifest)
    verify_semantic_xlsx_loop(
        manifest, expected, workspace, checks,
        deferred_outputs=('xlsx_enhancement_summary.json',))
    result = checks.finish()
    return {
        'dataset': dataset,
        'scope': 'loop verifier only; preserved output artifact; no workload or independent audit',
        'status': result['status'],
        'failures': result['failures'],
        'checks': result['checks'],
        'evidence': {
            'output_workbook': str(output.relative_to(ROOT)),
            'output_workbook_sha256': sha(output),
            'manifest': str(manifest_path.relative_to(ROOT)),
            'manifest_sha256': sha(manifest_path),
            'expected': str(expected_path.relative_to(ROOT)),
            'expected_sha256': sha(expected_path),
            'original_failure_record': str(failure_record.relative_to(ROOT)),
            'original_failure_record_sha256': sha(failure_record),
            'verifier_sha256': {
                name: sha(ROOT / 'compatibility/verification' / name)
                for name in ('verify.py', 'spreadsheet.py', 'contracts.py', 'workbooks.py')},
        },
    }


def main():
    result = {
        'schema_version': 'loop-verifier-posthoc-recheck-v1',
        'datasets': {dataset: recheck(dataset) for dataset in ('retail', 'hr')},
        'limitation': 'A post-hoc verifier pass does not rewrite or promote the original failed collection/profile record.',
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(OUT)
    return 0 if all(item['status'] == 'success'
                    for item in result['datasets'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
