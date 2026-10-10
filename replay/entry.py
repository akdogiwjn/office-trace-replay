#!/usr/bin/env python3
"""Public dispatcher: old PDF/XLSX names always mean untouched document-oe."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from replay.common import read
from replay import legacy

OLD = {'pdf': 'pdf', 'opm': 'pdf', 'xlsx': 'xlsx', 'tlc': 'xlsx'}
NEW = {'irs_w4': 'irs_w4', 'sba1919': 'sba1919', 'hr': 'hr',
       'manufacturing': 'manufacturing', 'retail': 'retail',
       'opm_v2': 'opm', 'tlc_v2': 'tlc'}
DEFAULT = ['pdf', 'xlsx', 'irs_w4', 'sba1919', 'hr', 'manufacturing', 'retail']


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # Native compatibility interface. Keep its original default loops=20000,
    # PDF count=1 (supports 10), and XLSX recalc timeout=600 exactly.
    if '--scene' in argv:
        timed = '--timed' in argv
        if timed: argv.remove('--timed')
        python_mode = 'system'
        if '--legacy-python' in argv:
            i = argv.index('--legacy-python')
            python_mode = argv[i + 1]
            if python_mode not in ('system', 'venv'): raise ValueError('legacy Python must be system or venv')
            del argv[i:i + 2]
        legacy.launch(argv, timed, python_mode)
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', action='append', choices=list(OLD) + list(NEW))
    parser.add_argument('--loops', type=int, default=1)
    parser.add_argument('--pdf-applicant-count', type=int, choices=[1, 10], default=None)
    parser.add_argument('--timed', action='store_true', help='Original document-oe timing entry for old scenes only')
    parser.add_argument('--legacy-python', choices=['system', 'venv'], default='system')
    parser.add_argument('--results-dir', type=Path, default=Path('/results'))
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args(argv)
    if args.loops < 1: parser.error('--loops must be positive')
    selected = args.dataset or DEFAULT
    if args.timed and any(name in NEW for name in selected):
        parser.error('--timed belongs to the preserved old PDF/XLSX scenes')
    legacy.validate(check_installed=Path('/.dockerenv').exists())
    if args.validate_only:
        from replay.run import validate_project
        validate_project()
        print('legacy bytes and derived pack bindings valid')
        return 0
    # Each old scene is a child running the original program with original
    # logs. Complete both old scenes before any new engine replaces Skills.
    scenes = list(dict.fromkeys(OLD[n] for n in selected if n in OLD))
    for scene in scenes:
        command = [sys.executable, str(ROOT / 'replay/entry.py'), '--scene', scene,
                   '--loops', str(args.loops), '--results-dir', str(args.results_dir),
                   '--legacy-python', args.legacy_python]
        if args.timed: command.append('--timed')
        if scene == 'pdf' and args.pdf_applicant_count is not None:
            command.extend(['--pdf-applicant-count', str(args.pdf_applicant_count)])
        code = subprocess.call(command)
        if code: return code
    chosen = list(dict.fromkeys(NEW[n] for n in selected if n in NEW))
    if chosen:
        command = [sys.executable, str(ROOT / 'replay/run.py'), '--loops', str(args.loops),
                   '--results-dir', str(args.results_dir)]
        for name in chosen: command.extend(['--dataset', name])
        env = os.environ.copy()
        env['PATH'] = str(ROOT / 'runtime/bin') + ':/opt/document-bench/.venv/bin:' + env['PATH']
        env['VIRTUAL_ENV'] = '/opt/document-bench/.venv'
        return subprocess.call(command, env=env)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
