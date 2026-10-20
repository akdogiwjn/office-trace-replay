#!/usr/bin/env python3
"""Archive-side hash index builder; runs INSIDE the measurement container.

The container writes some output files (e.g. the TLC-era CSVs) with 0600
root ownership that the host user cannot read.  Computing the archive index
inside the container, where every file is readable, keeps the evidence
complete without changing any permission or re-running anything.

Usage (in-container): archive_results.py /results
Writes /results/archive-index.json with one SHA256 per file.
"""
import hashlib
import json
import sys
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else '/results')
    files = []
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.name in ('archive-index.json', '.archive-list.tmp'):
            continue
        if path.name == 'container.log':
            # written by the HOST launcher while the container runs and after
            # it exits; hashed host-side once final, never in-container
            continue
        relative = path.relative_to(root)
        files.append({'path': str(relative), 'size_bytes': path.stat().st_size,
                      'sha256': sha256(path)})
    index = {'schema_version': 'cpu-measurement-archive-v1', 'files': files,
             'all_hashes_verified': all(
                 sha256(root / row['path']) == row['sha256'] for row in files)}
    (root / 'archive-index.json').write_text(json.dumps(index, indent=1) + '\n')
    print(json.dumps({'files': len(files),
                      'all_hashes_verified': index['all_hashes_verified']}))


if __name__ == '__main__':
    main()
