"""Compatibility suite validation and provenance bindings.

This module is no longer a runtime entry for new datasets; the unified runner
(`vendor/document-oe/run_document_scene_loop.py --scene <scene> --dataset <ds>`)
is the formal single-dataset entry, and post-loop acceptance/archival live in
`replay/suite.py`. `validate` keeps the frozen binding checks: compatibility
contract, legacy lock, parent recipes, prompts and input hashes.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from replay.common import digest, read
from replay import legacy

DATASETS = ['irs_w4', 'sba1919', 'hr', 'manufacturing', 'retail']


def validate():
    index = read(ROOT / 'compatibility/suite.json')
    if digest(ROOT / 'compatibility/contract.json') != index['contract_sha256']:
        raise ValueError('compatibility contract changed')
    if digest(legacy.LEGACY / 'lock.json') != index['legacy_lock_sha256']:
        raise ValueError('compatibility baseline changed')
    from replay.run import validate_project
    validate_project()
    for entry in index['entries']:
        recipe = read(ROOT / entry['recipe_path'])
        if digest(ROOT / entry['recipe_path']) != entry['recipe_sha256']:
            raise ValueError('compatible recipe changed')
        parent = recipe['parent']
        if digest(ROOT / parent['recipe_path']) != parent['recipe_sha256']:
            raise ValueError('parent recipe changed')
        if digest(ROOT / recipe['prompt_path']) != recipe['prompt_sha256']:
            raise ValueError('compatible prompt changed')
        for name, expected in recipe['input_hashes'].items():
            if digest(ROOT / recipe['seed_path'] / name) != expected:
                raise ValueError('compatible input changed: ' + name)
    return index
