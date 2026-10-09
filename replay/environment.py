import importlib.metadata
import platform
import subprocess
import sys
from .common import ROOT, read


def probe(family):
    lock = read(ROOT / 'runtime/environment-lock.json')
    def command(args):
        p = subprocess.run(args, capture_output=True, text=True, timeout=30)
        return (p.stdout or p.stderr).strip().splitlines()[0]
    packages = {name: importlib.metadata.version(name) for name in lock['packages']}
    actual = {'family': family, 'python': platform.python_version(), 'python_executable': sys.executable,
              'architecture': platform.machine(), 'packages': packages,
              'libreoffice': command(['soffice', '--version']),
              'poppler': command(['pdftoppm', '-v']), 'libc': platform.libc_ver(),
              'os_release': __import__('pathlib').Path('/etc/os-release').read_text()}
    failures = []
    if actual['python'] != lock['python']: failures.append('python')
    if actual['architecture'] != lock['architecture']: failures.append('architecture')
    if packages != lock['packages']: failures.append('Python packages')
    for field, expected in lock[family].items():
        if expected not in actual[field]: failures.append(field)
    if family == 'openeuler' and sys.executable != lock['openeuler_python_executable']:
        failures.append('explicit venv executable')
    if failures:
        raise ValueError('runtime does not match lock: ' + ', '.join(failures) + ' observed=' + str(actual))
    return actual
