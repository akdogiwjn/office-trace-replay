#!/usr/bin/env python3
"""Negative functional checks on a copy of a completed compatible PDF workspace."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from replay.common import digest, read, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', choices=['irs_w4', 'sba1919'], required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    recipe_path = ROOT / 'compatibility/recipes' / (args.dataset + '-n1.json')
    recipe = read(recipe_path)
    results = []
    for scenario in ('clean', 'inactive_value', 'inactive_page', 'inactive_protected',
                     'missing_mapping', 'extra_mapping', 'extra_pdf', 'extra_render'):
        with tempfile.TemporaryDirectory(prefix='office-pdf-negative-') as tmp:
            workspace = Path(tmp) / 'workspace'
            shutil.copytree(args.workspace, workspace)
            manifest = read(workspace / 'input/dataset_manifest.json')
            records = read(workspace / 'input' / manifest['records'])[manifest['records_key']]
            assert manifest['pdf_execution']['record_count'] == 1 and len(records) == 10
            inactive = records[-1]['id']
            mapping = workspace / 'output/field_values' / (inactive + '.json')
            if scenario.startswith('inactive_'):
                values = read(mapping)
                if scenario == 'inactive_value':
                    values[0]['value'] = '__incorrect_inactive_value__'
                elif scenario == 'inactive_page':
                    values[0]['page'] = 999
                else:
                    values.append({'field_id': manifest['requirements']['protected_blank'][0], 'page': 1, 'value': 'bad'})
                write(mapping, values)
            elif scenario == 'missing_mapping':
                mapping.unlink()
            elif scenario == 'extra_mapping':
                shutil.copyfile(mapping, mapping.with_name('unexpected.json'))
            elif scenario == 'extra_pdf':
                selected = manifest['pdf_execution']['record_ids'][0]
                shutil.copyfile(workspace / 'output/filled' / (selected + '.pdf'), workspace / 'output/filled/unexpected.pdf')
            elif scenario == 'extra_render':
                (workspace / 'output/rendered/unexpected').mkdir()
            report = Path(tmp) / 'verification.json'
            run = subprocess.run([sys.executable, str(ROOT / 'replay/accept.py'), '--source', str(ROOT / recipe['source_path']),
                                  '--dataset', args.dataset, '--kind', 'pdf', '--workspace', str(workspace),
                                  '--report', str(report)], capture_output=True, text=True)
            actual = read(report)
            expected_failure = scenario != 'clean'
            ok = (run.returncode == (1 if expected_failure else 0)
                  and actual['status'] == ('failed' if expected_failure else 'success')
                  and bool(actual['failures']) == expected_failure)
            results.append({'scenario': scenario, 'passed': ok, 'verifier_status': actual['status'],
                            'failures': actual['failures'], 'verification_sha256': digest(report)})
            print(args.dataset, scenario, 'passed' if ok else 'FAILED', actual['failures'], flush=True)
    write(args.report, {'schema_version': 'compatible-pdf-negative-checks-v1',
                       'status': 'success' if all(r['passed'] for r in results) else 'failed',
                       'dataset': args.dataset, 'recipe_sha256': digest(recipe_path),
                       'project_lock_sha256': digest(ROOT / 'assets/project-lock.json'), 'results': results})
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
