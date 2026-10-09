#!/usr/bin/env python3
"""Run reviewed effective tool chains with the document-oe executor."""
import argparse
import copy
import fcntl
import importlib.util
import os
from pathlib import Path
import shutil
import sys
import time
from datetime import datetime, timezone
import uuid
import shlex

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from replay.common import digest, read, relative, write
from replay.environment import probe


def document_executor():
    path = ROOT / 'vendor/document-oe/run_document_scene_loop.py'
    spec = importlib.util.spec_from_file_location('frozen_document_executor', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_project(root=ROOT):
    lock = read(root / 'assets/project-lock.json')
    for name, expected in lock['files'].items():
        p = root / relative(name)
        if not p.is_file() or digest(p) != expected:
            raise ValueError('project hash mismatch: ' + name)
    suite = read(root / 'recipes/suite.json')
    if digest(root / 'assets/import-lock.json') != suite['import_lock_sha256']:
        raise ValueError('import lock differs from compiled suite')
    for entry in suite['datasets']:
        if digest(root / relative(entry['recipe_path'])) != entry['recipe_sha256']:
            raise ValueError('recipe differs from frozen suite')
        if digest(root / relative(entry['canonical_path']) / 'canonical.json') != entry['canonical_sha256']:
            raise ValueError('canonical differs from frozen suite')
    return suite


def reset(doc, recipe):
    ws = Path(recipe['workspace'])
    if ws.parent != Path('/root/.openclaw/workspace/tool-modeling'):
        raise ValueError('workspace must be a dedicated container case')
    doc.reset_workspace(ROOT / recipe['seed_path'], ws)
    for name in recipe['scratch_files']:
        if name not in ('/tmp/report_base.xlsx', '/tmp/report_recalc.xlsx'):
            raise ValueError('unreviewed scratch path')
        Path(name).unlink(missing_ok=True)
    # Fresh profile/macro/shim policy per iteration, including the first one:
    # snapshot containers can contain stale LO state and earlier output files.
    profile = Path('/root/.config/libreoffice')
    if profile.exists(): shutil.rmtree(profile)
    for name in ('/tmp/lo_socket_shim.so', '/tmp/lo_socket_shim.c'):
        Path(name).unlink(missing_ok=True)
    source = ROOT / recipe['source_path']
    skills = Path('/root/.openclaw/skills')
    if skills.is_symlink(): skills.unlink()
    elif skills.exists(): shutil.rmtree(skills)
    skills.symlink_to(source / 'vendor/skills')
    # Some captured helpers/commands address /workspace directly.
    alias = Path('/workspace')
    if alias.is_symlink(): alias.unlink()
    elif alias.exists():
        if alias.is_dir() and not any(alias.iterdir()):
            alias.rmdir()
        else:
            raise ValueError('/workspace must be empty or a replay-owned symlink; do not mount the source repository there')
    alias.symlink_to(source)
    os.environ['OFFICE_TRACE_PROJECT'] = str(source)
    # A root office.py would shadow the Skill's namespace package office/ and
    # break `from office.soffice import ...` in recalc.py. Verifiers explicitly
    # load their frozen source via OFFICE_TRACE_PROJECT instead.
    os.environ.pop('PYTHONPATH', None)
    return ws


def iteration(doc, recipe, destination):
    destination.mkdir(parents=True, exist_ok=False)
    result = {'status': 'in_progress', 'dataset_id': recipe['dataset_id'],
              'calls': [], 'step_seconds': {}, 'reset_policy': 'fresh workspace, original paths, scratch, LO profile and shim',
              'preparation_seconds': None, 'execution_seconds': None, 'acceptance_seconds': None}
    write(destination / 'iteration.json', result)
    started = time.monotonic()
    try:
        ws = reset(doc, recipe)
        result['preparation_seconds'] = round(time.monotonic() - started, 6)
        original_execute = doc.execute_call
        def logged_execute(call, operation_timeout, recalc_timeout):
            n = len(result['calls']) + 1
            call_started = time.monotonic()
            record = {'index': n, 'function': call['function_name'], 'status': 'in_progress'}
            result['calls'].append(record)
            actual = copy.deepcopy(call)
            if call['function_name'] == 'exec':
                stdout = destination / f'call-{n:02d}.stdout.log'
                stderr = destination / f'call-{n:02d}.stderr.log'
                actual['arguments']['command'] = '(\n' + call['arguments']['command'] + '\n) > ' + shlex.quote(str(stdout)) + ' 2> ' + shlex.quote(str(stderr))
                record.update(stdout=stdout.name, stderr=stderr.name)
            try:
                original_execute(actual, operation_timeout, recalc_timeout)
                record['status'] = 'success'
            except Exception as exc:
                record.update(status='failed', error=str(exc))
                raise
            finally:
                record['elapsed_seconds'] = round(time.monotonic() - call_started, 6)
                write(destination / 'iteration.json', result)
        doc.execute_call = logged_execute
        execution_start = time.monotonic()
        try:
            for step in recipe['key_operations']:
                print(recipe['dataset_id'], step['operation_id'], flush=True)
                doc.execute_step(step, recipe['operation_timeout'], recipe['recalc_timeout'], result['step_seconds'])
            doc.validate_business_result(ws)
        finally:
            doc.execute_call = original_execute
            result['execution_seconds'] = round(time.monotonic() - execution_start, 6)
        acceptance_start = time.monotonic()
        args = [sys.executable, str(ROOT / 'replay/accept.py'), '--source', str(ROOT / recipe['source_path']),
                '--dataset', recipe['dataset_id'], '--kind', recipe['case_kind'], '--workspace', str(ws),
                '--report', str(destination / 'independent_verification.json')]
        try:
            doc.run_command(shlex.join(args), recipe['operation_timeout'])
        finally:
            result['acceptance_seconds'] = round(time.monotonic() - acceptance_start, 6)
        result['output_hashes'] = {str(p.relative_to(ws / 'output')): digest(p) for p in (ws / 'output').rglob('*') if p.is_file()}
        # Persist newly generated outputs for review; canonical outputs are never
        # restored into the working seed and are never used as replay inputs.
        shutil.copytree(ws / 'output', destination / 'output')
        result['status'] = 'success'
    except Exception as exc:
        result.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        if isinstance(exc, doc.StepFailure): result['failure'] = exc.as_dict()
        ws = Path(recipe['workspace'])
        if ws.is_dir():
            shutil.copytree(ws, destination / 'failure_workspace', symlinks=True)
    finally:
        result['elapsed_seconds'] = round(time.monotonic() - started, 6)
        write(destination / 'iteration.json', result)
    print(recipe['dataset_id'], result['status'], result.get('error', ''), flush=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', action='append', choices=['irs_w4', 'opm', 'sba1919', 'hr', 'manufacturing', 'retail', 'tlc'])
    parser.add_argument('--loops', type=int, default=1)
    parser.add_argument('--runtime', choices=['original', 'openeuler'], default='openeuler')
    parser.add_argument('--results-dir', type=Path, default=Path('/results'))
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args(argv)
    if args.loops < 1: parser.error('--loops must be positive')
    suite = validate_project()
    doc = document_executor()
    entries = [e for e in suite['datasets'] if not args.dataset or e['dataset_id'] in args.dataset]
    recipes = []
    for e in entries:
        recipe = read(ROOT / e['recipe_path'])
        doc.load_recipe(ROOT / e['recipe_path'], recipe['case_kind'], recipe['workflow']['success_path'])
        recipes.append(recipe)
    if args.validate_only:
        print('hashes and recipes valid:', ', '.join(r['dataset_id'] for r in recipes))
        return 0
    if not Path('/.dockerenv').exists() or os.environ.get('OFFICE_REPLAY_CONTAINER') != '1':
        raise ValueError('execute only in a disposable replay container')
    # One chain per container; original paths/scratch/LO profile are shared.
    with Path('/tmp/office-trace-replay.lock').open('w') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        environment = probe(args.runtime)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        target = args.results_dir.resolve() / stamp
        target.mkdir(parents=True, exist_ok=False)
        report = {'schema_version': 'office-effective-replay-qualification-v1', 'status': 'in_progress',
                  'scope': 'final_effective_tool_execution', 'requires_llm': False,
                  'runtime': environment, 'project_lock_sha256': digest(ROOT / 'assets/project-lock.json'),
                  'suite_sha256': digest(ROOT / 'recipes/suite.json'), 'selected_datasets': [r['dataset_id'] for r in recipes],
                  'loops': args.loops, 'results': [],
                  'timing_scope': 'Operational progress timings only; no CPU/OS instrumentation or performance experiment.'}
        write(target / 'summary.json', report)
        for recipe in recipes:
            for number in range(1, args.loops + 1):
                item = iteration(doc, recipe, target / recipe['dataset_id'] / f'{number:04d}')
                item.update(recipe_sha256=digest(ROOT / 'recipes' / (recipe['dataset_id'] + '.json')),
                            original_run_id=recipe['source']['original_run_id'], iteration=number)
                report['results'].append(item)
                write(target / 'summary.json', report)
                if item['status'] != 'success':
                    report['status'] = 'failed'; write(target / 'summary.json', report)
                    return 1
        report['status'] = 'success'
        write(target / 'summary.json', report)
        print('report:', target / 'summary.json', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
