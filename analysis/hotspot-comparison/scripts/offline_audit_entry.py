#!/usr/bin/env python3
"""In-container entry for the offline independent audit of archived outputs.

This script runs INSIDE a disposable container over read-only mounts:

  /workspace  -> the archived trial workspace (read-only bind mount)
  /opt/office-trace-replay -> the current repository (read-only bind mount)
  /results    -> an independent writable report directory (bind mount)

It performs a genuine read-only audit and nothing else:

  1. record the actual runtime identity (interpreter, openpyxl version, the
     verifier module hashes that will be executed);
  2. hash the archived output workbook BEFORE the verifier runs;
  3. run the frozen execution source's independent verifier (the exact
     package a formal acceptance would load), scope=independent;
  4. hash the output again afterwards (also on failure), so any mutation by
     the verifier is detected and reported as a hard failure;
  5. write the report and an identity/purpose record into /results only.

It never calls the runner, helpers, LibreOffice/recalc, and it never writes
into /workspace or /opt (the mounts enforce this).  The caller passes the
expected source binding hashes so the audit record can state exactly which
materials the original trial used versus what audited them.
"""
import argparse
import hashlib
import json
import platform
import sys
import traceback
from pathlib import Path

VERIFIER_PACKAGE_FILES = ('verify.py', 'spreadsheet.py', 'contracts.py', 'workbooks.py')


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_source_verifier(dataset, repo):
    """Import office_trace_bench from the frozen execution source, as accept.py does."""
    source = repo / 'compatibility/cases' / dataset / 'source'
    sys.path.insert(0, str(source))
    import office  # noqa: F401  (source identity marker, mirrors replay/accept.py)
    from office_trace_bench.contracts import dataset_path
    from office_trace_bench.verify import verify
    return verify, dataset_path, source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--repo', type=Path, default=Path('/opt/office-trace-replay'),
                        help='repository root providing the frozen execution source '
                             '(container default: the read-only repo mount)')
    parser.add_argument('--workspace', type=Path, default=Path('/workspace'))
    parser.add_argument('--report', type=Path, default=Path('/results/independent-verification.json'))
    parser.add_argument('--identity', type=Path, default=Path('/results/audit-identity.json'))
    args = parser.parse_args()

    identity = {
        'schema_version': 'offline-audit-identity-v1',
        'purpose': 'read-only independent audit of archived trial outputs',
        'runs_workload': False, 'calls_runner': False, 'calls_recalc': False,
        'writes_workspace': False,
        'python_executable': sys.executable,
        'python_version': platform.python_version(),
        'platform': platform.platform(),
        'dataset': args.dataset,
        'workspace': str(args.workspace),
    }
    try:
        import openpyxl
        identity['openpyxl_version'] = openpyxl.__version__
    except Exception:  # pragma: no cover - openpyxl always present in the image
        identity['openpyxl_version'] = 'unknown'

    status = 'failed'
    before_hash = None
    after_hash = None
    output_name = None
    report = None
    error = None
    try:
        verify, dataset_path, source = load_source_verifier(args.dataset, args.repo)
        identity['verifier_module_sha256'] = {
            name: sha256_file(source / 'office_trace_bench' / name)
            for name in VERIFIER_PACKAGE_FILES}
        identity['repo'] = str(args.repo)
        manifest_path = dataset_path('xlsx', args.dataset)
        manifest = read_json(manifest_path)
        output_name = manifest['output_workbook']
        output_file = args.workspace / 'output' / output_name
        # BEFORE the verifier: the pre-audit hash must be captured first.
        before_hash = sha256_file(output_file)
        report = verify(manifest_path, args.workspace, args.report)
        status = report.get('status')
    except BaseException as exc:  # noqa: BLE001 - record every failure mode
        error = f'{type(exc).__name__}: {exc}'
        identity['traceback'] = traceback.format_exc(limit=12)
    finally:
        # AFTER the verifier (also on failure): capture the post-audit hash so
        # a mutating or crashing verifier can never masquerade as success.
        if output_name is not None:
            try:
                after_hash = sha256_file(args.workspace / 'output' / output_name)
            except OSError as exc:
                identity['post_audit_hash_error'] = f'{type(exc).__name__}: {exc}'
        identity['output_workbook'] = output_name
        identity['output_sha256_before_audit'] = before_hash
        identity['output_sha256_after_audit'] = after_hash
        identity['output_unchanged_by_audit'] = (
            before_hash is not None and before_hash == after_hash)
        identity['verifier_status'] = status
        identity['verifier_error'] = error
        identity['status'] = ('success' if status == 'success' and error is None
                              and identity['output_unchanged_by_audit'] else 'failed')
        args.identity.parent.mkdir(parents=True, exist_ok=True)
        args.identity.write_text(json.dumps(identity, indent=2, ensure_ascii=False) + '\n',
                                 encoding='utf-8')
    print(json.dumps({k: identity[k] for k in
                      ('dataset', 'status', 'verifier_status', 'output_unchanged_by_audit',
                       'python_version', 'openpyxl_version')}), flush=True)
    return 0 if identity['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
