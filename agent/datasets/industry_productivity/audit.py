#!/usr/bin/env python3
"""Private outside-loop auditor, with explicit cache-CSV policy adaptation."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'audit_source'))
# Imported bench auditors use extract_form_field_info as a top-level module.
# Skills are kept dataset-private rather than duplicated under audit_source/vendor.
if (HERE / 'skills/pdf/scripts').is_dir():
    sys.path.insert(0, str(HERE / 'skills/pdf/scripts'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    from office_trace_bench.contracts import load_manifest, read_json, write_json
    from office_trace_bench.verify import verify
    contract = read_json(HERE / 'audit-contract.json')
    manifest_path = HERE / 'audit_source' / contract['manifest_path']
    if not contract['csv_adaptation']:
        report = verify(manifest_path, args.workspace, args.report, scope='independent')
    else:
        from office_trace_bench.task_verification import verify_task
        # Validate the ORIGINAL manifest and its original assets before applying
        # the one reviewed replay policy: reference bytes -> regenerated caches.
        manifest = load_manifest(manifest_path)
        # csv_mode stays copy_prepared for layout validation and its old generic
        # metrics.csv/scenario.csv checks; actual named CSVs are checked below.
        # validate_task_manifest requires two exports, so retain declarations and
        # suppress only byte-publication checks via a private Checks subclass.
        import office_trace_bench.industry_verification.verify as semantic
        Original = semantic.Checks
        class CacheExportChecks(Original):
            def add(self, name, ok, detail=None):
                if name.startswith('published:'):
                    self.diag('replay_policy:' + name,
                              {'replaced_by': 'csv_matches_current_cache', 'old_byte_check_result': bool(ok)})
                    return
                super().add(name, ok, detail)
        semantic.Checks = CacheExportChecks
        try:
            report = verify_task(manifest_path, manifest, args.workspace, None,
                                 deferred_outputs=(), scope='independent')
        finally:
            semantic.Checks = Original
        module_path = HERE / 'scripts/export_xlsx_csv.py'
        spec = importlib.util.spec_from_file_location('dataset_private_csv_audit', module_path)
        csv_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(csv_module)
        try:
            csv_module.validate_csv(args.workspace, read_json(HERE / 'scripts/csv-contract.json'))
            report['checks']['csv_matches_current_cache'] = {'ok': True}
        except Exception as exc:
            report['checks']['csv_matches_current_cache'] = {'ok': False, 'detail': str(exc)}
            report['failures'].append('csv_matches_current_cache')
        report['status'] = 'failed' if report['failures'] else 'success'
        report['base_validation_contract'] = report.get('validation_contract')
        report['validation_contract'] = 'agent-derived-cache-csv-independent-v1'
        report['replay_adaptation'] = 'Original assets remain bound; named CSVs checked against regenerated final caches, not prepared bytes.'
        write_json(args.report, report)
    print(report['status'], flush=True)
    return 0 if report['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
