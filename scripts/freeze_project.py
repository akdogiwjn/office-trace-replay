#!/usr/bin/env python3
"""Bind runnable assets/code independently of mutable qualification reports."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from replay.common import digest, write

files = {}
for folder in ('assets', 'recipes', 'replay', 'vendor', 'runtime', 'scripts', 'legacy', 'suites'):
    for path in (ROOT / folder).rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.name != 'project-lock.json':
            files[str(path.relative_to(ROOT))] = digest(path)
write(ROOT / 'assets/project-lock.json', {'schema_version': 'office-replay-project-lock-v1', 'files': files})
print('locked', len(files), 'files')
