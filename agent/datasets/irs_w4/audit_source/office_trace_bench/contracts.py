import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID = re.compile(r'^[a-z][a-z0-9_-]*$')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def safe_relative(value):
    path = Path(value)
    if not isinstance(value, str) or not value or path.is_absolute() or '..' in path.parts:
        raise ValueError(f'unsafe relative asset path: {value!r}')
    return path


def load_manifest(path, check_assets=True):
    path = Path(path).resolve()
    data = read_json(path)
    if data.get('schema_version') not in ('office-dataset-v1', 'office-dataset-v2'):
        raise ValueError('unsupported dataset manifest schema')
    if data.get('kind') not in ('xlsx', 'pdf'):
        raise ValueError('kind must be xlsx or pdf')
    if not ID.fullmatch(data.get('dataset_id', '')):
        raise ValueError('invalid dataset_id')
    for key in ('task', 'input_files', 'requirements', 'expected_file', 'trace_rules'):
        if key not in data:
            raise ValueError(f'missing manifest field: {key}')
    if not isinstance(data['input_files'], dict) or not data['input_files']:
        raise ValueError('input_files must be a non-empty path/hash map')
    safe_relative(data['expected_file'])
    if data.get('prompt_template'):
        template = ROOT / 'prompts' / safe_relative(data['prompt_template'])
        if check_assets and (not template.is_file() or sha256(template) != data.get('prompt_template_sha256')):
            raise ValueError('prompt template hash mismatch')
    if data.get('agent_context') and check_assets:
        from .context import load_profile
        load_profile(data)
    if data.get('runtime_case') and not re.fullmatch(r'[A-Za-z0-9_-]+', data['runtime_case']):
        raise ValueError('invalid runtime_case')
    if data.get('agent_verifier'):
        filename = safe_relative(data['agent_verifier'])
        if str(Path('input') / filename) not in data['input_files']:
            raise ValueError('agent_verifier must be a frozen input')
    if data['kind'] == 'xlsx':
        safe_relative(data['workbook'])
        safe_relative(data['output_workbook'])
        required = (('metrics', 'scenario', 'charts') if data.get('workload_contract') == 'spreadsheet-semantic-v2'
                    else ('summary_sheet', 'base_sheets', 'raw_sheets', 'metrics', 'scenario', 'charts'))
    else:
        safe_relative(data['form'])
        safe_relative(data['records'])
        required = ('page_count', 'field_count', 'record_count', 'field_rules', 'protected_blank')
    for key in required:
        if key not in data['requirements']:
            raise ValueError(f'missing {data["kind"]} requirement: {key}')
    if data.get('task_contract') == 'dataset-specific-agent-v1' and data['kind'] == 'xlsx':
        from .task_verification import validate_task_manifest
        validate_task_manifest(data)
    for relative, expected_hash in data['input_files'].items():
        asset = path.parent / safe_relative(relative)
        if check_assets and (not asset.is_file() or sha256(asset) != expected_hash):
            raise ValueError(f'input hash mismatch: {relative}')
    if check_assets:
        expected = path.parent / data['expected_file']
        if not expected.is_file() or sha256(expected) != data.get('expected_sha256'):
            raise ValueError('expected results hash mismatch')
        for relative, digest in data.get('analysis_metadata', {}).items():
            asset = path.parent / safe_relative(relative)
            if not asset.is_file() or sha256(asset) != digest:
                raise ValueError('analysis metadata hash mismatch: ' + relative)
        for field, filename in [('provenance_sha256', 'provenance.json'), ('records_contract_sha256', 'records_contract.json')]:
            if field in data and sha256(path.parent / filename) != data[field]:
                raise ValueError(field + ' mismatch')
    return data


def dataset_path(kind, dataset_id):
    if kind not in ('xlsx', 'pdf') or not ID.fullmatch(dataset_id):
        raise ValueError('invalid dataset selection')
    # A task revision selects a small manifest; it never copies or rewrites its
    # original workbook/form. The original TLC/OPM contracts cannot be redirected.
    index = ROOT / 'suites/agent.json'
    if index.is_file():
        selection = read_json(index)
        matches = [item for item in selection['datasets']
                   if (item['kind'], item['dataset_id']) == (kind, dataset_id)]
        if len(matches) > 1:
            raise ValueError('duplicate active dataset')
        if matches:
            item = matches[0]
            path = ROOT / safe_relative(item['manifest_path'])
            directory = ROOT / 'datasets' / kind / dataset_id
            if path.parent != directory or path.name not in ('manifest.json', 'task-manifest.json'):
                raise ValueError('active manifest must belong to its dataset')
            if (kind, dataset_id) in {('xlsx', 'tlc'), ('pdf', 'opm')} and path.name != 'manifest.json':
                raise ValueError('original TLC/OPM task cannot be redirected')
            if not path.is_file() or sha256(path) != item['manifest_sha256']:
                raise ValueError('active task manifest hash mismatch')
            return path
    return ROOT / 'datasets' / kind / dataset_id / 'manifest.json'


def selected_datasets():
    index = ROOT / 'suites/agent.json'
    if index.is_file():
        entries = read_json(index)['datasets']
        identities = [(entry['kind'], entry['dataset_id']) for entry in entries]
        if len(identities) != len(set(identities)):
            raise ValueError('duplicate active dataset')
        return [dataset_path(*identity) for identity in identities]
    return sorted((ROOT / 'datasets').glob('*/*/manifest.json'))
