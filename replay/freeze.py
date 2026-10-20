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
from .source_assets import validate_source_assets

AGENT_CLASSIFICATION = 'canonicalized_deterministic_replay_derived_from_successful_agent_executions'
MANUAL_ORIGIN = 'manual_workflow_adaptation'


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


def validate_recipe_origin(recipe, root=ROOT):
    """Validate ancestry explicitly: Agent-derived or bound manual adaptation."""
    root = Path(root)
    origin = recipe.get('origin_type')
    if origin == MANUAL_ORIGIN:
        if (recipe.get('agent_generated') is not False
                or recipe.get('requires_llm') is not False
                or recipe.get('classification') != MANUAL_ORIGIN
                or 'parent' in recipe):
            raise ValueError('manual workflow origin markers or ancestry are invalid')
        binding = recipe.get('manual_source')
        if not isinstance(binding, dict):
            raise ValueError('manual workflow source binding is missing')
        helper_rel = Path(binding.get('helper_path', ''))
        helper_file = root / helper_rel
        if (helper_rel.is_absolute() or '..' in helper_rel.parts
                or not helper_file.is_file()
                or digest(helper_file) != binding.get('helper_sha256')):
            raise ValueError('manual workflow helper hash mismatch')
        for path_key, hash_key in (('record_path', 'record_sha256'),
                                   ('manifest_path', 'manifest_sha256')):
            rel = Path(binding.get(path_key, ''))
            if rel.is_absolute() or '..' in rel.parts or not binding.get(hash_key):
                raise ValueError(f'manual workflow {path_key} is unsafe or unbound')
            path = root / rel
            if not path.is_file() or digest(path) != binding[hash_key]:
                raise ValueError(f'manual workflow {path_key} hash mismatch')
        record = read(root / binding['record_path'])
        if (record.get('origin_type') != MANUAL_ORIGIN
                or record.get('agent_generated') is not False
                or record.get('requires_llm') is not False
                or record.get('status') != 'registered_not_run'
                or record.get('dataset_id') != recipe.get('dataset_id')):
            raise ValueError('manual workflow provenance record is invalid')
        if record.get('sha256') not in recipe.get('input_hashes', {}).values():
            raise ValueError('manual workflow provenance does not bind the recipe input')
        if binding.get('references') != record.get('references'):
            raise ValueError('manual workflow reference evidence differs from provenance')
        for reference in record.get('references', []):
            for path_key, hash_key in (('recipe_path', 'recipe_sha256'),
                                       ('helper_path', 'helper_sha256')):
                rel = Path(reference.get(path_key, ''))
                path = root / rel
                if rel.is_absolute() or '..' in rel.parts or not path.is_file() or digest(path) != reference.get(hash_key):
                    raise ValueError('manual workflow reference hash mismatch: ' + path_key)
        manifest_path = root / binding['manifest_path']
        from compatibility.verification.contracts import load_manifest
        manifest = load_manifest(manifest_path, check_assets=True)
        if (manifest.get('dataset_id') != recipe.get('dataset_id')
                or manifest.get('origin_type') != MANUAL_ORIGIN
                or manifest.get('agent_generated') is not False
                or manifest.get('requires_llm') is not False):
            raise ValueError('manual workflow source manifest is invalid')
        return 'manual_workflow_adaptation'
    if origin is None and recipe.get('classification') == AGENT_CLASSIFICATION:
        parent = recipe.get('parent')
        if not isinstance(parent, dict):
            raise ValueError('Agent-derived recipe is missing strict parent binding')
        parent_path = Path(parent.get('recipe_path', ''))
        if (parent_path.is_absolute() or '..' in parent_path.parts
                or not parent.get('recipe_sha256')
                or digest(root / parent_path) != parent['recipe_sha256']):
            raise ValueError('parent recipe hash mismatch for ' + str(recipe.get('dataset_id')))
        return 'agent_derived'
    raise ValueError('unknown or missing workflow origin type')


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
    validate_recipe_origin(recipe, ROOT)
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
    validate_source_assets(recipe, ROOT)
    # Static bindings are consistent; formal execution additionally requires
    # frozen preparation artifacts for the v2 prepared workloads.  This runs
    # before any workload command, workspace reset or workbook read and never
    # opens the large input itself.
    from .readiness import check_dataset_readiness
    check_dataset_readiness(recipe, ROOT)
    return recipe
