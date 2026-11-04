"""Read-only verification of offline build materials; never invokes Docker."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def verify_tree(directory, records, path_key):
    expected = {r[path_key]: r for r in records}
    if len(expected) != len(records):
        raise ValueError('duplicate vendor manifest entry')
    actual = {str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file()}
    if actual != set(expected):
        raise ValueError(f'vendor inventory differs: {directory}')
    for relative, record in expected.items():
        path = directory / relative
        if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError(f'vendor path escapes directory: {relative}')
        if path.stat().st_size != record['bytes'] or sha(path) != record['sha256']:
            raise ValueError(f'vendor hash mismatch: {relative}')


def verify(root, devkit):
    spec = importlib.util.spec_from_file_location('docops_compile', root / 'compile.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload = module.validate_payload(root / 'payload')
    for name, subdir, key in [('debs-sha256.json', 'debs', 'file'),
                              ('fonttools-sha256.json', 'fonttools', 'path')]:
        records = json.loads((root / 'vendor' / name).read_text())['files']
        verify_tree(root / 'vendor' / subdir, records, key)
    required = ['devkit', 'tuner/libtuner.so', 'tuner/bin/tuner_python_cli']
    for relative in required:
        if not (devkit / relative).is_file():
            raise ValueError(f'missing required DevKit file: {relative}')
    core = [(devkit / p) for p in required]
    core += [p for p in (devkit / 'tuner/lib').rglob('*') if p.is_file()]
    if len(core) == len(required):
        raise ValueError('DevKit private libraries missing')
    source_files = ['replay.py', 'compile.py', 'docker/Dockerfile', 'docker/build.sh',
                    'docker/install_state_check.py', 'docker/verify_build_inputs.py', 'docker/devkit.sh']
    return {'schema': 'docops-offline-build-inputs-v1', 'payload': payload,
            'base_image': json.loads((root / 'payload/catalog.json').read_text())['environment'],
            'payload_index_sha256': sha(root / 'payload/payload-index.json'),
            'source_sha256': {p: sha(root / p) for p in source_files},
            'vendor_manifest_sha256': {p.name: sha(p) for p in (root / 'vendor').glob('*-sha256.json')},
            'devkit_sha256': {str(p.relative_to(devkit)): sha(p) for p in core}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--devkit', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(Path(__file__).resolve().parents[1], args.devkit), indent=2))
