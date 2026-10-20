"""Compatibility suite validation and provenance bindings.

This module is no longer a runtime entry for compatible datasets; the unified runner
(`vendor/document-oe/run_document_scene_loop.py --scene <scene> --dataset <ds>`)
is the formal single-dataset entry, and post-loop acceptance/archival live in
`replay/suite.py`. `validate` keeps the frozen binding checks: compatibility
contract, legacy lock, parent recipes, prompts and input hashes.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from replay.common import digest, read, relative
from replay import legacy

DATASETS = ['irs_w4', 'sba1919', 'hr', 'manufacturing', 'retail', 'industry_productivity',
            'hr_metro', 'retail_online']


def validate_public_suite(root=ROOT):
    """Reject stale public-index bindings before an installation or suite run."""
    root = Path(root)
    path = root / 'suites/default.json'
    if not path.is_file():
        return
    public = read(path)
    default_datasets = public.get('default_datasets')
    allowed = set()
    for entry in public.get('datasets', []):
        allowed.add(entry.get('dataset_id'))
        allowed.update(entry.get('aliases', []))
    if (not isinstance(default_datasets, list) or not default_datasets
            or len(default_datasets) != len(set(default_datasets))
            or not set(default_datasets).issubset(allowed)):
        raise ValueError('public suite default_datasets is missing, duplicated, or unregistered')
    for key, filename in (
            ('legacy_lock_sha256', 'legacy/document-oe/lock.json'),
            ('compatible_contract_sha256', 'compatibility/contract.json'),
            ('compatible_suite_sha256', 'compatibility/suite.json')):
        if public.get(key) != digest(root / filename):
            raise ValueError('public suite binding mismatch: ' + key)
    for entry in public['datasets']:
        if digest(root / relative(entry['recipe_path'])) != entry['recipe_sha256']:
            raise ValueError('public suite recipe hash mismatch: ' + entry['dataset_id'])


def validate():
    index = read(ROOT / 'compatibility/suite.json')
    if digest(ROOT / 'compatibility/contract.json') != index['contract_sha256']:
        raise ValueError('compatibility contract changed')
    if digest(legacy.LEGACY / 'lock.json') != index['legacy_lock_sha256']:
        raise ValueError('compatibility baseline changed')
    from replay.run import validate_project
    validate_project()
    validate_public_suite(ROOT)
    from replay.freeze import validate_recipe_origin
    from replay.source_assets import validate_source_assets
    for entry in index['entries']:
        recipe = read(ROOT / entry['recipe_path'])
        if digest(ROOT / entry['recipe_path']) != entry['recipe_sha256']:
            raise ValueError('compatible recipe changed')
        validate_recipe_origin(recipe)
        if digest(ROOT / recipe['prompt_path']) != recipe['prompt_sha256']:
            raise ValueError('compatible prompt changed')
        for name, expected in recipe['input_hashes'].items():
            if digest(ROOT / recipe['seed_path'] / name) != expected:
                raise ValueError('compatible input changed: ' + name)
        validate_source_assets(recipe, ROOT)
    return index
