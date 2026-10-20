#!/usr/bin/env python3
"""No-workload acceptance checks for an installed, source-independent image."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from replay.common import digest, read
from replay.environment import probe
from replay import compatible, legacy
from replay.freeze import _embedded_helper_content
from replay.run import validate_project
from replay.readiness import readiness_report
from replay.entry import DEFAULT as ENTRY_DEFAULT


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    checks = {}
    environment = probe('openeuler')
    checks['locked_runtime'] = environment

    legacy_lock = legacy.validate(check_installed=True)
    checks['legacy_workload_files_and_installed_modes'] = {
        'workload_file_count': len(legacy_lock['workload']),
        'status': 'success',
    }
    project = validate_project()
    compatible_index = compatible.validate()
    checks['project_lock_and_compatibility_index'] = {
        'project_lock_file_count': len(read(ROOT / 'assets/project-lock.json')['files']),
        'compatibility_entries': len(compatible_index['entries']),
        'status': 'success',
    }

    default_index = read(ROOT / 'suites/default.json')
    require(default_index['legacy_lock_sha256'] == digest(ROOT / 'legacy/document-oe/lock.json'),
            'default suite legacy lock hash mismatch')
    require(default_index['compatible_contract_sha256'] == digest(ROOT / 'compatibility/contract.json'),
            'default suite contract hash mismatch')
    require(default_index['compatible_suite_sha256'] == digest(ROOT / 'compatibility/suite.json'),
            'default suite compatibility index hash mismatch')
    for entry in default_index['datasets']:
        require(digest(ROOT / entry['recipe_path']) == entry['recipe_sha256'],
                'default suite recipe hash mismatch: ' + entry['dataset_id'])

    import importlib.util
    executor = ROOT / 'vendor/document-oe/run_document_scene_loop.py'
    spec = importlib.util.spec_from_file_location('installed_document_executor', executor)
    core = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = core
    spec.loader.exec_module(core)

    registry = []
    xlsx_sources = []
    for entry in compatible_index['entries']:
        dataset = entry['dataset_id']
        require(dataset in core.DATASET_SCENE, 'dataset missing from runner registry: ' + dataset)
        scene = core.DATASET_SCENE[dataset]
        layout = core.dataset_layout(scene, dataset, entry['record_count'])
        recipe = read(ROOT / entry['recipe_path'])
        require(layout['source'] == ROOT / recipe['source_path'],
                'registry source differs from frozen recipe: ' + dataset)
        require(layout['seed'] == ROOT / recipe['seed_path'],
                'registry seed differs from frozen recipe: ' + dataset)
        require(digest(ROOT / entry['recipe_path']) == entry['recipe_sha256'],
                'recipe binding mismatch: ' + dataset + '/' + str(entry['record_count']))
        for helper_name, expected in recipe.get('helper_hashes', {}).items():
            content = _embedded_helper_content(recipe, helper_name)
            require(content is not None and hashlib.sha256(content.encode('utf-8')).hexdigest() == expected,
                    f'embedded helper binding mismatch: {dataset}/{helper_name}')
        registry.append({'dataset_id': dataset, 'scene': scene,
                         'record_count': entry['record_count'],
                         'variant_id': entry['variant_id'],
                         'recipe_path': entry['recipe_path'],
                         'recipe_sha256': entry['recipe_sha256'],
                         'seed_path': recipe['seed_path'], 'source_path': recipe['source_path']})
        if scene == 'xlsx':
            for name in ('verify.py', 'spreadsheet.py', 'contracts.py', 'workbooks.py'):
                central = ROOT / 'compatibility/verification' / name
                source_copy = ROOT / recipe['source_path'] / 'office_trace_bench' / name
                require(digest(source_copy) == digest(central),
                        f'source verifier mismatch: {dataset}/{name}')
                xlsx_sources.append({'dataset_id': dataset, 'file': name,
                                     'sha256': digest(source_copy)})
        else:
            source_dir = ROOT / recipe['source_path'] / 'office_trace_bench'
            for name in ('verify.py', 'pdf_loop.py'):
                central = ROOT / 'compatibility/verification' / name
                source_copy = source_dir / name
                require(digest(source_copy) == digest(central),
                        f'PDF source verifier mismatch: {dataset}/{name}')
            dispatch = source_dir / 'compatible_pdf.py'
            require(dispatch.is_file(), 'PDF dispatcher is missing: ' + dataset)

    industry_entry = next(e for e in compatible_index['entries']
                          if e['dataset_id'] == 'industry_productivity')
    industry = read(ROOT / industry_entry['recipe_path'])
    require(industry['input_hashes']['input/labor-productivity-detailed-industries.xlsx']
            == '9c1213923977e6dcefd20b6185537434e9057428cb9a16b3329a8ccb4dd117dd',
            'Industry Productivity input binding changed')
    parent_canonical = ROOT / industry['parent']['canonical_path'] / 'canonical.json'
    require(digest(parent_canonical) == industry['parent']['canonical_sha256'],
            'Industry Productivity parent canonical binding mismatch')

    help_result = subprocess.run([sys.executable, str(ROOT / 'replay/entry.py'), '--help'],
                                 check=True, capture_output=True, text=True)
    require('--dataset' in help_result.stdout and '--loops' in help_result.stdout,
            'entry help does not expose expected arguments')
    validation = subprocess.run([sys.executable, str(ROOT / 'replay/entry.py'), '--validate-only'],
                                check=True, capture_output=True, text=True)
    checks['registry_and_dataset_bindings'] = registry
    checks['xlsx_source_verifiers'] = xlsx_sources
    checks['pdf_source_dispatchers'] = [
        {'dataset_id': e['dataset_id'],
         'verify_sha256': digest(ROOT / read(ROOT / e['recipe_path'])['source_path'] /
                                 'office_trace_bench/verify.py'),
         'pdf_loop_sha256': digest(ROOT / read(ROOT / e['recipe_path'])['source_path'] /
                                   'office_trace_bench/pdf_loop.py'),
         'dispatcher_sha256': digest(ROOT / read(ROOT / e['recipe_path'])['source_path'] /
                                     'office_trace_bench/compatible_pdf.py')}
        for e in compatible_index['entries'] if e['dataset_id'] in ('irs_w4', 'sba1919')
    ]
    checks['industry_productivity'] = {
        'input_sha256': industry['input_hashes']['input/labor-productivity-detailed-industries.xlsx'],
        'helper_hashes': industry.get('helper_hashes', {}),
        'canonical_path': industry['parent']['canonical_path'],
        'canonical_sha256': industry['parent']['canonical_sha256'],
        'recipe_path': industry_entry['recipe_path'],
        'recipe_sha256': industry_entry['recipe_sha256'],
        'status': 'success',
    }
    manual_adaptations = []
    for entry in compatible_index['entries']:
        recipe = read(ROOT / entry['recipe_path'])
        if recipe.get('origin_type') != 'manual_workflow_adaptation':
            continue
        require(recipe.get('agent_generated') is False and recipe.get('requires_llm') is False,
                'manual adaptation origin markers changed: ' + entry['dataset_id'])
        require('parent' not in recipe,
                'manual adaptation must not claim an Agent parent: ' + entry['dataset_id'])
        source_record = ROOT / recipe['manual_source']['record_path']
        require(digest(source_record) == recipe['manual_source']['record_sha256'],
                'manual provenance record mismatch: ' + entry['dataset_id'])
        record = read(source_record)
        require(record.get('status') == 'registered_not_run'
                and record.get('dataset_id') == entry['dataset_id'],
                'manual adaptation status is not registered_not_run: ' + entry['dataset_id'])
        manual_adaptations.append({'dataset_id': entry['dataset_id'],
                                   'origin_type': recipe['origin_type'],
                                   'status': record['status'],
                                   'record_sha256': digest(source_record)})
    checks['manual_workflow_adaptations'] = manual_adaptations
    checks['entry_help'] = {'status': 'success', 'stdout_sha256': hashlib.sha256(
        help_result.stdout.encode()).hexdigest()}
    checks['entry_validate_only'] = {'status': 'success', 'stdout': validation.stdout.strip()}

    excluded = ['analysis', 'reports', 'results', 'qualification', '.build', '.git', 'tests']
    present_excluded = [name for name in excluded if (ROOT / name).exists()]
    require(not present_excluded, 'excluded host-only content is present in image: '
            + ', '.join(present_excluded))
    checks['excluded_host_only_content'] = {'status': 'success', 'checked_absent': excluded}
    expected_default = ['opm', 'tlc', 'irs_w4', 'sba1919', 'hr_metro',
                        'retail_online', 'industry_productivity']
    require(default_index.get('default_datasets') == expected_default,
            'public default dataset selection differs from the seven formal datasets')
    require(ENTRY_DEFAULT == expected_default,
            'entry dispatcher default differs from the public suite selection')
    require(default_index.get('historical_only_datasets') == ['hr', 'retail', 'manufacturing'],
            'historical XLSX selection is missing or changed')
    new_defaults = [name for name in expected_default if name in
                    ('irs_w4', 'sba1919', 'hr_metro', 'retail_online', 'industry_productivity')]
    readiness = readiness_report(new_defaults)
    require(all(item.get('status') == 'ready' for item in readiness.values()),
            'a formal default dataset is not ready: ' + repr(readiness))
    checks['default_dataset_selection'] = {
        'status': 'success', 'datasets': ENTRY_DEFAULT,
        'historical_only': default_index['historical_only_datasets'],
        'readiness': readiness,
        'aliases': {'pdf': 'opm', 'xlsx': 'tlc'},
    }
    print(json.dumps({'status': 'success', 'workload_executed': False,
                      'project_lock_sha256': digest(ROOT / 'assets/project-lock.json'),
                      'environment_lock_sha256': digest(ROOT / 'runtime/environment-lock.json'),
                      'checks': checks}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
