#!/usr/bin/env python3
"""Validate the mounted source, runner, recipe and assets before sampling."""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import shutil
import sys
from pathlib import Path

REPO = Path('/opt/office-trace-replay')
RUNNER = Path('/opt/document-bench/bin/run_document_scene_loop.py')
TIMED_RUNNER = Path('/opt/document-bench/bin/run_document_scene_loop_timed.py')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--scene', choices=('xlsx', 'pdf'), default='xlsx')
    parser.add_argument('--pdf-applicant-count', type=int, choices=(1, 10), default=1)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--workspace-parent', type=Path,
                        help='optional bind-mounted parent; the dataset workspace must remain its removable child')
    parser.add_argument('--expected-operation-timeout', type=int)
    parser.add_argument('--expected-recalc-timeout', type=int)
    args = parser.parse_args()
    result = {'dataset': args.dataset, 'status': 'failed'}
    try:
        if platform.python_version() != '3.12.3':
            raise RuntimeError(f'expected Python 3.12.3, got {platform.python_version()}')
        entry = REPO / 'replay/entry.py'
        if not entry.is_file():
            raise FileNotFoundError(f'replay entry is not readable: {entry}')
        with entry.open('rb') as stream:
            stream.read(1)
        source_runner = REPO / 'legacy/document-oe/bin/run_document_scene_loop.py'
        if sha(source_runner) != sha(RUNNER):
            raise ValueError('mounted runner differs from current source runner')
        source_timed_runner = REPO / 'legacy/document-oe/bin/run_document_scene_loop_timed.py'
        if not source_timed_runner.is_file() or not TIMED_RUNNER.is_file():
            raise FileNotFoundError('current source or mounted timed runner is missing')
        if sha(source_timed_runner) != sha(TIMED_RUNNER):
            raise ValueError('mounted timed runner differs from current source timed runner')

        sys.path.insert(0, str(REPO))
        from replay.run import validate_project
        from replay import freeze
        validate_project()
        spec = importlib.util.spec_from_file_location('preflight_document_runner', RUNNER)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        layout = module.dataset_layout(args.scene, args.dataset, args.pdf_applicant_count)
        operation_timeout = int(layout['operation_timeout'])
        recalc_timeout = int(layout['recalc_timeout'])
        if (args.expected_operation_timeout is not None
                and operation_timeout != args.expected_operation_timeout):
            raise RuntimeError(f'operation timeout {operation_timeout} != expected {args.expected_operation_timeout}')
        if (args.expected_recalc_timeout is not None
                and recalc_timeout != args.expected_recalc_timeout):
            raise RuntimeError(f'recalc timeout {recalc_timeout} != expected {args.expected_recalc_timeout}')
        workspace = Path(layout['workspace'])
        if args.workspace_parent:
            parent = args.workspace_parent
            if workspace.parent != parent:
                raise RuntimeError(f'registry workspace parent {workspace.parent} != mounted parent {parent}')
            if not os.path.ismount(parent):
                raise RuntimeError(f'workspace parent is not a mount point: {parent}')
            if os.path.ismount(workspace):
                raise RuntimeError(f'dataset workspace itself must not be a mount point: {workspace}')
            probe = parent / f'.{args.dataset}-reset-probe'
            probe.mkdir(exist_ok=False)
            (probe / 'probe.txt').write_text('reset probe\n')
            shutil.rmtree(probe)
            probe.mkdir(exist_ok=False)
            probe.rmdir()
            result['workspace_parent_mount'] = str(parent)
            result['workspace_is_removable_child'] = True
        count = args.pdf_applicant_count if args.scene == 'pdf' else None
        recipe = freeze.validate_dataset(args.scene, args.dataset, layout, count,
                                         check_installed=True)
        _, entry_spec = freeze._find_entry(args.dataset, count)
        recipe_path = REPO / entry_spec['recipe_path']
        source = REPO / recipe['source_path']
        verifier_names = (('verify.py', 'spreadsheet.py', 'contracts.py', 'workbooks.py')
                          if args.scene == 'xlsx' else ('pdf.py', 'pdf_loop.py'))
        result.update({
            'status': 'success', 'python_executable': sys.executable,
            'scene': args.scene, 'record_count': count,
            'python_version': platform.python_version(),
            'entry': str(entry), 'entry_readable': True,
            'runner': str(RUNNER), 'runner_sha256': sha(RUNNER),
            'timed_runner': str(TIMED_RUNNER), 'timed_runner_sha256': sha(TIMED_RUNNER),
            'recipe': str(recipe_path), 'recipe_sha256': sha(recipe_path),
            'workspace': str(layout['workspace']),
            'operation_timeout_seconds': operation_timeout,
            'recalc_timeout_seconds': recalc_timeout,
            'verifier_sha256': {name: sha(REPO / 'compatibility/verification' / name)
                                for name in verifier_names},
            'source_verifier_sha256': {name: sha(source / 'office_trace_bench' / name)
                                       for name in verifier_names},
            'input_sha256': {name: sha(REPO / recipe['seed_path'] / name)
                             for name in recipe['input_hashes']},
            'expected_input_sha256': recipe['input_hashes'],
            'helper_sha256': recipe.get('helper_hashes', {}),
            'runtime_packages': {name: importlib.metadata.version(name)
                                 for name in ('openpyxl', 'et_xmlfile', 'pypdf', 'pillow')
                                 if _has_package(name)},
        })
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(result, ensure_ascii=False), flush=True)


def _has_package(name):
    try:
        importlib.metadata.version(name)
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


if __name__ == '__main__':
    main()
