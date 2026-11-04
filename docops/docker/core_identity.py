"""Read-only ELF and original seven-case identity probe (no workload/profiler)."""
import hashlib
import json
from pathlib import Path
import re
import subprocess


CORE = [
    '/opt/python-3.12.3/lib/libpython3.12.so.1.0',
    '/opt/libreoffice25.8-symbols/program/libsclo.so',
    '/opt/libreoffice25.8-symbols/program/libswlo.so',
    '/opt/libreoffice25.8-symbols/program/libsdlo.so',
    '/usr/lib64/libpoppler.so.133.0.0', '/usr/bin/perf',
    '/opt/office-trace-replay/agent/replay.py',
    '/opt/office-trace-replay/document-oe/run.py',
]


def identity():
    result = {}
    for name in CORE:
        path = Path(name)
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        item = {'sha256': digest.hexdigest(), 'bytes': path.stat().st_size}
        if path.suffix != '.py':
            notes = subprocess.check_output(['readelf', '-n', name], text=True)
            sections = subprocess.check_output(['readelf', '-SW', name], text=True)
            match = re.search(r'Build ID:\s*(\w+)', notes)
            item.update(build_id=match.group(1) if match else None,
                        symtab='.symtab' in sections, debug_info='.debug_info' in sections)
        result[name] = item
    return result


if __name__ == '__main__':
    print(json.dumps(identity(), indent=2))
