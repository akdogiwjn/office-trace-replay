#!/usr/bin/env python3
"""Restore source modes after Git checkout; never rewrite legacy contents."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from replay.common import digest, read, relative

native = Path('/opt/document-bench')
for name, spec in read(ROOT / 'legacy/document-oe/lock.json')['files'].items():
    path = native / relative(name)
    if digest(path) != spec['sha256']:
        raise ValueError('legacy installation changed bytes: ' + name)
    path.chmod(spec['mode'])
