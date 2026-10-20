#!/usr/bin/env python3
"""Public suite dispatcher over the unified document-oe runner.

Formal single-dataset entry is the runner itself:

    python run_document_scene_loop.py --scene pdf --dataset opm
    python run_document_scene_loop.py --scene pdf --dataset irs_w4
    python run_document_scene_loop.py --scene pdf --dataset sba1919
    python run_document_scene_loop.py --scene xlsx --dataset tlc
    python run_document_scene_loop.py --scene xlsx --dataset retail
    python run_document_scene_loop.py --scene xlsx --dataset manufacturing
    python run_document_scene_loop.py --scene xlsx --dataset hr
    python run_document_scene_loop.py --scene xlsx --dataset hr_metro
    python run_document_scene_loop.py --scene xlsx --dataset retail_online
    python run_document_scene_loop.py --scene xlsx --dataset industry_productivity

`--scene pdf` defaults to the byte-preserved `opm` workload and `--scene xlsx`
defaults to the byte-preserved `tlc` workload. This module is the high-level
suite/old-interface compatibility layer: it selects datasets, prepares the
environment, starts one unified runner process per dataset, and for the
registered compatible datasets perform post-loop acceptance and archival.

Historical aliases `--dataset opm_v2` / `--dataset tlc_v2` replay the frozen
parent recipes through the derived-v1 engine (replay/run.py). They are kept for
provenance comparisons only: they run LAST in any invocation (the derived
engine replaces Skill links / source context), ignore formal-suite-only
parameters, and `--timed` with them is rejected before execution.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from replay.common import read
from replay import legacy
from replay.run import document_executor
from replay import suite

OLD = {'pdf': 'pdf', 'opm': 'pdf', 'xlsx': 'xlsx', 'tlc': 'xlsx'}
NEW = {'irs_w4': 'irs_w4', 'sba1919': 'sba1919', 'hr': 'hr',
       'manufacturing': 'manufacturing', 'retail': 'retail',
       'industry_productivity': 'industry_productivity',
       'hr_metro': 'hr_metro', 'retail_online': 'retail_online'}
# Historical aliases replay the frozen parent recipes (recipes/opm.json,
# recipes/tlc.json) through the derived-v1 engine (replay/run.py). They are
# not canonicalized workloads, have no compatibility entries, and ignore
# formal-suite-only parameters such as --timed / --pdf-applicant-count.
HISTORICAL = {'opm_v2': 'opm', 'tlc_v2': 'tlc'}
# The default formal selection is recorded in the public suite index so the
# dispatcher, installation acceptance and documentation share one source.
DEFAULT = read(ROOT / 'suites/default.json')['default_datasets']


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # Native compatibility interface. Its original default loops=20000,
    # PDF count=1 (supports 10), and XLSX recalc timeout=600 are kept exactly.
    if '--scene' in argv:
        timed = '--timed' in argv
        if timed:
            argv.remove('--timed')
        python_mode = 'venv'
        if '--legacy-python' in argv:
            i = argv.index('--legacy-python')
            python_mode = argv[i + 1]
            if python_mode not in ('system', 'venv'):
                raise ValueError('legacy Python must be system or venv')
            del argv[i:i + 2]
        legacy.launch(argv, timed, python_mode)
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', action='append', choices=list(OLD) + list(NEW) + list(HISTORICAL))
    parser.add_argument('--loops', type=int, default=1)
    parser.add_argument('--pdf-applicant-count', type=int, choices=[1, 10], default=1)
    parser.add_argument('--timed', action='store_true', help='Original document-oe timing wrapper for all datasets')
    parser.add_argument('--legacy-python', choices=['system', 'venv'], default='venv')
    parser.add_argument('--workflow', choices=['compatible', 'derived-v1'], default='compatible',
                        help='derived-v1 retains the historical parent-recipe engine for new inputs')
    parser.add_argument('--results-dir', type=Path, default=Path('/results'))
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args(argv)
    if args.loops < 1:
        parser.error('--loops must be positive')
    selected = args.dataset or DEFAULT
    manual_only = {'hr_metro', 'retail_online'}
    if args.workflow == 'derived-v1' and manual_only.intersection(selected):
        parser.error('manual workflow adaptations do not have Agent parent recipes for derived-v1')
    historical = [name for name in selected if name in HISTORICAL]
    # Reject unsupported parameter combinations before any workload runs; the
    # historical derived-v1 engine has no timing mode.
    if args.timed and (historical or args.workflow == 'derived-v1'):
        parser.error('--timed is not supported by the historical derived-v1 engine'
                     + (' (selected: ' + ', '.join(historical) + ')' if historical else ''))
    legacy.validate(check_installed=Path('/.dockerenv').exists())
    if args.validate_only:
        from replay.run import validate_project
        validate_project()
        from replay.compatible import validate
        validate()
        print('executor, workload and compatible workflow bindings valid')
        # Static binding validity and formal-execution readiness are separate
        # statements.  Report readiness per requested dataset and fail loudly
        # (without touching any workload) when a prepared v2 workload is not
        # ready to execute.
        from replay.readiness import readiness_report
        selected_datasets = [NEW[name] for name in selected if name in NEW]
        report = readiness_report(selected_datasets)
        ready = [name for name, item in report.items() if item['status'] == 'ready']
        not_ready = [name for name, item in report.items() if item['status'] != 'ready']
        for name in not_ready:
            item = report[name]
            print(f'formal execution NOT ready for {name}: {item["reason"]}: {item["detail"]}')
        if not_ready:
            print('static bindings are valid; formal preparation is missing. Generate the '
                  'frozen preparation artifacts (approved run of '
                  'scripts/prepare_xlsx_selection.py) before executing these workloads.')
            return 1
        if ready:
            print('formal preparation ready for: ' + ', '.join(sorted(ready)))
        return 0
    core = document_executor()
    # Execution order: old byte-preserved workloads first, then the
    # compatible formal datasets, and the historical derived-v1 engine LAST,
    # because the derived engine replaces the Skill links and source context
    # and must never run before a unified-runner workload in the same
    # invocation.
    results_root = args.results_dir.resolve()
    selected = dict.fromkeys(selected)
    for name in list(selected):
        if name in OLD:
            scene = OLD[name]
            dataset = name if name in ('opm', 'tlc') else ({'pdf': 'opm', 'xlsx': 'tlc'}[scene])
            code = suite.run_old_dataset(dataset, scene, results_root, args.loops,
                                         args.timed, args.legacy_python, args.pdf_applicant_count)
            if code:
                return code
            del selected[name]
    derived_names = []
    for name in list(selected):
        if args.workflow == 'derived-v1':
            derived_names.append(NEW.get(name, HISTORICAL.get(name)))
            del selected[name]
        elif name in HISTORICAL:
            derived_names.append(HISTORICAL[name])
            del selected[name]
    for name in selected:
        dataset = NEW[name]
        scene = core.DATASET_SCENE[dataset]
        layout = core.dataset_layout(scene, dataset, args.pdf_applicant_count)
        item = suite.run_dataset(core, dataset, scene, layout, results_root, args.loops,
                                 args.timed, args.legacy_python, args.pdf_applicant_count)
        if item['status'] != 'success':
            print(dataset, item.get('error', ''), flush=True)
            return 1
    if derived_names:
        command = [sys.executable, str(ROOT / 'replay/run.py'), '--loops', str(args.loops),
                   '--results-dir', str(results_root)]
        for n in derived_names:
            command += ['--dataset', n]
        env = os.environ.copy()
        env['PATH'] = str(ROOT / 'runtime/bin') + ':/opt/document-bench/.venv/bin:' + env['PATH']
        env['VIRTUAL_ENV'] = '/opt/document-bench/.venv'
        return subprocess.call(command, env=env)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
