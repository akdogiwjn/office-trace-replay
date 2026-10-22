#!/usr/bin/env python3
"""Explicit one-time import. Execution never depends on the source checkout."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from replay.common import digest, read, relative, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    if (ROOT / 'assets/import-lock.json').exists():
        raise ValueError('import is frozen; do not overwrite the selected suite')
    sys.path.insert(0, str(source))
    import office
    from office_trace_bench.canonical import validate_pack
    suite_path = source / 'artifacts/suite.json'
    suite = read(suite_path)
    assets = ROOT / 'assets'
    objects = assets / 'objects/sha256'
    objects.mkdir(parents=True, exist_ok=True)
    lock = {'schema_version': 'office-replay-import-v1',
            'source_suite_sha256': digest(suite_path),
            'source_commit': subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip(),
            'datasets': [], 'object_hashes': []}
    shutil.copyfile(suite_path, assets / 'source-suite.json')
    hashes = set()
    for entry in suite['datasets']:
        pack = source / 'artifacts' / relative(entry['canonical_path'])
        if digest(pack / 'canonical.json') != entry['canonical_sha256']:
            raise ValueError('suite/canonical mismatch')
        canonical = validate_pack(pack, source / 'artifacts')
        target = assets / 'canonical' / entry['dataset_id']
        shutil.copytree(pack, target)
        frozen = assets / 'cases' / entry['dataset_id'] / 'source'
        for name, spec in canonical['artifact_inventory'].items():
            blob = source / 'artifacts/objects/sha256' / spec['sha256']
            hashes.add(spec['sha256'])
            dest = objects / spec['sha256']
            if not dest.exists():
                shutil.copyfile(blob, dest)
            if name.startswith('source/'):
                path = frozen / relative(name.removeprefix('source/'))
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(blob, path)
        lock['datasets'].append({**entry, 'canonical_path': str(target.relative_to(ROOT)),
                                 'source_path': str(frozen.relative_to(ROOT)),
                                 'original_run_id': canonical['original_run_id']})
        print('imported', entry['dataset_id'], canonical['original_run_id'], flush=True)
    lock['object_hashes'] = sorted(hashes)
    evidence = dict(suite.get('provenance_evidence', {}))
    for entry in suite['datasets']:
        item = entry.get('scenario_qualification')
        if item: evidence[item['path']] = item['sha256']
    item = suite.get('agent_qualification')
    if item: evidence[item['path']] = item['sha256']
    for name, expected in evidence.items():
        src = source / relative(name)
        if digest(src) != expected: raise ValueError('suite evidence hash mismatch: ' + name)
        dest = assets / 'evidence' / relative(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    lock['evidence_hashes'] = evidence
    write(assets / 'import-lock.json', lock)


if __name__ == '__main__':
    main()
