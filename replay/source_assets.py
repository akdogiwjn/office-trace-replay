"""Check assets using the selected runtime source's own manifest loader."""
from contextlib import contextmanager
import importlib
import importlib.util
from pathlib import Path
import sys
import uuid

from .common import ROOT, digest, relative


@contextmanager
def _source_contracts(source):
    # A source's contracts/context modules resolve ROOT from their own files.
    # Give each check a private package so no earlier dataset's imports leak in.
    namespace = '_office_trace_asset_check_' + uuid.uuid4().hex
    package_path = source / 'office_trace_bench'
    spec = importlib.util.spec_from_file_location(
        namespace, package_path / '__init__.py',
        submodule_search_locations=[str(package_path)])
    if spec is None or spec.loader is None:
        raise ValueError('cannot load source verifier package: ' + str(package_path))
    try:
        package = importlib.util.module_from_spec(spec)
        sys.modules[namespace] = package
        spec.loader.exec_module(package)
        yield importlib.import_module(namespace + '.contracts')
    finally:
        for name in list(sys.modules):
            if name == namespace or name.startswith(namespace + '.'):
                del sys.modules[name]


def validate_source_assets(recipe, root=ROOT):
    """Validate exactly the source assets independent acceptance will load.

    This hashes files only; it never opens a workbook or performs a business
    audit. It belongs to preflight, outside the measured iteration.
    """
    root = Path(root)
    source = root / relative(recipe['source_path'])
    kind, dataset = recipe['case_kind'], recipe['dataset_id']
    if kind not in ('xlsx', 'pdf'):
        raise ValueError('invalid source dataset kind: ' + str(kind))
    manifest_path = source / 'datasets' / kind / relative(dataset) / 'manifest.json'
    try:
        with _source_contracts(source) as contracts:
            manifest = contracts.load_manifest(manifest_path, check_assets=True)
        if manifest['kind'] != kind or manifest['dataset_id'] != dataset:
            raise ValueError('source manifest dataset identity mismatch')
        seed_manifest = root / relative(recipe['seed_path']) / 'input/dataset_manifest.json'
        if digest(manifest_path) != digest(seed_manifest):
            raise ValueError('seed and source manifests differ')
        if recipe.get('origin_type') == 'manual_workflow_adaptation':
            prompt = source / 'prompts' / relative(manifest['prompt_template'])
            if digest(prompt) != recipe['prompt_sha256']:
                raise ValueError('manual source prompt differs from recipe prompt binding')
    except (OSError, ValueError, KeyError, ImportError) as exc:
        raise ValueError(f'{dataset}: runtime source assets invalid: {exc}') from exc
    return manifest
