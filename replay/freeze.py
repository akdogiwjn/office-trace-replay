"""Frozen-binding validation for the selected workload before the loop.

Every normal run and direct-runner invocation validates the same set:
  - the executor/workload split (`legacy/document-oe/lock.json`),
  - the full project freeze (`assets/project-lock.json`),
  - for canonicalized datasets, the selected recipe hash against
    `compatibility/suite.json`, plus the recipe's parent / prompt / contract /
    input / helper / source-verifier bindings.

The expected hashes always come from the frozen index, never recomputed-and-
accepted, so an unauthorized change to a recipe or helper is rejected before
any workload command runs.
"""
import hashlib
import json
from pathlib import Path

from .common import ROOT, digest, read
from . import legacy


def _bytes_digest(data):
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _find_entry(dataset_id, record_count):
    index = read(ROOT / 'compatibility/suite.json')
    for entry in index['entries']:
        if entry['dataset_id'] != dataset_id:
            continue
        if record_count is None and entry['record_count'] is None:
            return index, entry
        if entry['record_count'] == record_count:
            return index, entry
    raise ValueError(f'no frozen compatibility entry for dataset {dataset_id} count {record_count}')


def expected_recipe_sha256(dataset_id, record_count):
    _, entry = _find_entry(dataset_id, record_count)
    return entry['recipe_sha256']


def resolve_variant(dataset_id, scene, record_count):
    if scene == 'pdf' and record_count is not None:
        return f'{dataset_id}-n{record_count}'
    return dataset_id


def _embedded_helper_content(recipe, helper_name):
    for step in recipe['key_operations']:
        for item in step['source_tool_calls']:
            call = item.get('tool_call', {})
            if call.get('function_name') == 'write':
                path = str(call.get('arguments', {}).get('path', ''))
                if path.endswith('/' + helper_name) or path.endswith(helper_name):
                    return call['arguments'].get('content')
    return None


def validate_dataset(scene, dataset, layout, record_count=None, check_installed=False):
    """Raise ValueError on any frozen-binding mismatch before execution."""
    legacy.validate(check_installed=check_installed)
    from replay.run import validate_project
    validate_project()
    if layout.get('source') is None:
        # Old workloads: recipes/tools/inputs are covered by the workload split.
        return
    index, entry = _find_entry(dataset, record_count)
    recipe_path = ROOT / entry['recipe_path']
    if digest(recipe_path) != entry['recipe_sha256']:
        raise ValueError(f'recipe hash mismatch for {dataset}: '
                         f'{digest(recipe_path)} != {entry["recipe_sha256"]}')
    recipe = read(recipe_path)
    if recipe['parent']['recipe_sha256'] != digest(ROOT / recipe['parent']['recipe_path']):
        raise ValueError('parent recipe hash mismatch for ' + dataset)
    if recipe['prompt_sha256'] != digest(ROOT / recipe['prompt_path']):
        raise ValueError('prompt hash mismatch for ' + dataset)
    if index['contract_sha256'] != digest(ROOT / 'compatibility/contract.json'):
        raise ValueError('compatibility contract hash mismatch')
    seed = ROOT / recipe['seed_path']
    for name, expected in recipe['input_hashes'].items():
        if digest(seed / name) != expected:
            raise ValueError(f'input hash mismatch for {dataset}: {name}')
    for helper, expected in recipe.get('helper_hashes', {}).items():
        content = _embedded_helper_content(recipe, helper)
        if content is None or _bytes_digest(content.encode('utf-8')) != expected:
            raise ValueError(f'helper hash mismatch for {dataset}: {helper}')
    source = ROOT / recipe['source_path']
    # The replay-private XLSX verifier must match the canonical copies. PDF
    # verifiers differ (parent verifier + compatible_pdf dispatcher) and are
    # covered by the project freeze above.
    if scene == 'xlsx':
        for name in ('verify.py', 'spreadsheet.py', 'contracts.py', 'workbooks.py'):
            expected = digest(ROOT / 'compatibility/verification' / name)
            if digest(source / 'office_trace_bench' / name) != expected:
                raise ValueError(f'source verifier hash mismatch for {dataset}: {name}')
    return recipe
