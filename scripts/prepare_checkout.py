#!/usr/bin/env python3
"""Restore frozen permission metadata that Git cannot encode (e.g. 0664)."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare(root=ROOT):
    root = Path(root)
    record = json.loads((root / 'document-oe/lock.json').read_text())
    assets = root / 'document-oe/assets'
    checked = []
    # Validate every byte first. Permission restoration must not mask corruption.
    for name, meta in record['workload_files'].items():
        path = assets / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('missing or symlink workload: ' + name)
        if (path.stat().st_size != meta['size'] or
                hashlib.sha256(path.read_bytes()).hexdigest() != meta['sha256']):
            raise ValueError('changed workload: ' + name)
        checked.append((path, meta['mode']))
    restored = 0
    for path, mode in checked:
        if path.stat().st_mode & 0o777 != mode:
            path.chmod(mode)
            restored += 1
    return {'checked': len(checked), 'permissions_restored': restored,
            'workload_bytes_changed': False}


if __name__ == '__main__':
    print(json.dumps(prepare()))
