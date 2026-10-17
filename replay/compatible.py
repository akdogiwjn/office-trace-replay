"""Run new input adapters through the byte-preserved document-oe main()."""
import argparse
import json
import importlib.metadata
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from replay.common import digest, read, write
from replay import legacy

DATASETS = ['irs_w4', 'sba1919', 'hr', 'manufacturing', 'retail']


def validate():
    index = read(ROOT / 'compatibility/suite.json')
    if digest(ROOT / 'compatibility/contract.json') != index['contract_sha256']:
        raise ValueError('compatibility contract changed')
    if digest(legacy.LEGACY / 'lock.json') != index['legacy_lock_sha256']:
        raise ValueError('compatibility baseline changed')
    from replay.run import validate_project
    validate_project()
    for entry in index['entries']:
        recipe = read(ROOT / entry['recipe_path'])
        if digest(ROOT / entry['recipe_path']) != entry['recipe_sha256']:
            raise ValueError('compatible recipe changed')
        parent = recipe['parent']
        if digest(ROOT / parent['recipe_path']) != parent['recipe_sha256']:
            raise ValueError('parent recipe changed')
        if digest(ROOT / recipe['prompt_path']) != recipe['prompt_sha256']:
            raise ValueError('compatible prompt changed')
        for name, expected in recipe['input_hashes'].items():
            if digest(ROOT / recipe['seed_path'] / name) != expected:
                raise ValueError('compatible input changed: ' + name)
    return index


def native_child(recipe_path, results, timed, python_mode, loops):
    """Only SCENES paths change in memory; original execution/timing code stays untouched."""
    recipe = read(recipe_path)
    legacy.validate(check_installed=True)
    os.environ['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
    os.environ.pop('PYTHONPATH', None)
    os.environ.pop('VIRTUAL_ENV', None)
    if python_mode == 'venv':
        os.environ['PATH'] = '/opt/document-bench/.venv/bin:' + os.environ['PATH']
        os.environ['VIRTUAL_ENV'] = '/opt/document-bench/.venv'
    # Same installed tools as the old baselines, including recalc/profile logic.
    for kind in ('pdf', 'xlsx'):
        link = Path('/root/.openclaw/skills') / kind
        if not link.is_symlink() or link.resolve() != Path('/opt/document-bench/skills') / kind:
            raise ValueError('use a fresh container with original Skill links')
    source = ROOT / recipe['source_path']
    os.environ['OFFICE_TRACE_PROJECT'] = str(source)
    alias = Path('/workspace')
    if alias.is_symlink():
        alias.unlink()
    elif alias.exists():
        raise ValueError('/workspace must be empty or a source symlink')
    alias.symlink_to(source)
    contract = read(ROOT / 'compatibility/contract.json')
    actual = {'python': sys.version.split()[0], 'executable': sys.executable,
              'packages': {n: importlib.metadata.version(n) for n in read(ROOT / 'runtime/environment-lock.json')['packages']},
              'path': os.environ['PATH'], 'skills_root': '/opt/document-bench/skills',
              'soffice_target': str(Path('/usr/local/bin/soffice').resolve())}
    if actual['python'] != contract['python'][python_mode + '_version']:
        raise ValueError('Python version differs from comparison contract')
    if actual['packages'] != read(ROOT / 'runtime/environment-lock.json')['packages']:
        raise ValueError('Python libraries differ from comparison contract')
    results.mkdir(parents=True, exist_ok=True)
    write(results / 'environment.json', actual)
    sys.path.insert(0, '/opt/document-bench/bin')
    if timed:
        import run_document_scene_loop_timed as wrapper
        core = wrapper.core
    else:
        import run_document_scene_loop as core
    kind = recipe['case_kind']
    # All native timeouts, error handling, shell semantics, reset and status
    # checks remain provided by the original main(), not a new execution loop.
    core.SCENES[kind] = {**core.SCENES[kind], 'seed': ROOT / recipe['seed_path'],
                        'workspace': Path(recipe['workspace']), 'recipe': recipe_path}
    sys.argv = [str(Path('/opt/document-bench/bin/run_document_scene_loop.py')),
                '--scene', kind, '--loops', str(loops), '--results-dir', str(results),
                '--operation-timeout', str(recipe['operation_timeout']),
                '--recalc-timeout', str(recipe['recalc_timeout'])]
    if kind == 'pdf':
        sys.argv += ['--pdf-applicant-count', str(recipe['record_count'])]
    return core.main()


def run_dataset(entry, target, loops, timed, python_mode):
    """Run the entire native loop before final acceptance and archival."""
    recipe_path = ROOT / entry['recipe_path']
    recipe = read(recipe_path)
    destination = target / entry['variant_id'] / 'series'
    destination.mkdir(parents=True)
    interpreter = legacy.native_command([], python_mode=python_mode)[0]
    command = [interpreter, str(ROOT / 'replay/compatible.py'), '--native-child', str(recipe_path),
               '--results-dir', str(destination), '--legacy-python', python_mode,
               '--loops', str(loops)]
    if timed:
        command.append('--timed')
    item = {'dataset_id': entry['dataset_id'], 'variant_id': entry['variant_id'],
            'requested_iterations': loops, 'recipe_sha256': entry['recipe_sha256'],
            'parent': recipe['parent'], 'status': 'in_progress',
            'archive_scope': 'final_iteration_only',
            'acceptance_scope': 'native business verifier each iteration; independent verifier after entire loop'}
    try:
        subprocess.run(command, check=True)
        native_path = next(destination.glob(recipe['case_kind'] + '/*/summary.json'))
        native = read(native_path)
        events = read_events(native_path.with_name('iterations.jsonl'))
        if (native['requested_iterations'] != loops or native['completed_iterations'] != loops
                or native['successes'] != loops or native['failures'] != 0 or native['interrupted']
                or native['recipe_sha256'] != entry['recipe_sha256']
                or len(events) != loops
                or any(e['iteration'] != i or e['status'] != 'success' for i, e in enumerate(events, 1))):
            raise ValueError('native loop incomplete, failed, or recipe mismatched')
        item.update(native_summary=str(native_path.relative_to(target)),
                    native_summary_sha256=digest(native_path),
                    native_events_sha256=digest(native_path.with_name('iterations.jsonl')),
                    native_iterations=events, completed_iterations=loops)
        start = time.perf_counter()
        subprocess.run([interpreter, str(ROOT / 'replay/accept.py'), '--source', str(ROOT / recipe['source_path']),
                        '--dataset', entry['dataset_id'], '--kind', recipe['case_kind'], '--workspace', recipe['workspace'],
                        '--report', str(destination / 'independent_verification.json')], check=True)
        acceptance = read(destination / 'independent_verification.json')
        if acceptance['status'] != 'success' or acceptance['failures']:
            raise ValueError('independent verification failed')
        item['independent_acceptance_seconds'] = round(time.perf_counter() - start, 6)
        item['independent_verification_sha256'] = digest(destination / 'independent_verification.json')
        shutil.copytree(Path(recipe['workspace']) / 'output', destination / 'output')
        # Like the native baseline, reset overwrites previous iterations. Only
        # the final workspace is archived, after all native iterations finish.
        shutil.copytree(Path(recipe['workspace']), destination / 'workspace_artifacts')
        item['artifact_hashes'] = {str(p.relative_to(destination / 'workspace_artifacts')): digest(p)
                                  for p in (destination / 'workspace_artifacts').rglob('*') if p.is_file()}
        item['status'] = 'success'
    except Exception as exc:
        item.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        workspace = Path(recipe['workspace'])
        if workspace.is_dir():
            shutil.copytree(workspace, destination / 'failure_workspace', dirs_exist_ok=True)
            item['failure_workspace_scope'] = 'last available workspace; earlier iterations may have been reset'
    return item


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', action='append', choices=DATASETS)
    parser.add_argument('--loops', type=int, default=1)
    parser.add_argument('--pdf-applicant-count', type=int, choices=[1, 10], default=1)
    parser.add_argument('--legacy-python', choices=['system', 'venv'], default='venv')
    parser.add_argument('--timed', action='store_true')
    parser.add_argument('--results-dir', type=Path, default=Path('/results'))
    parser.add_argument('--native-child', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.loops < 1:
        parser.error('loops must be positive')
    if args.native_child:
        return native_child(args.native_child, args.results_dir, args.timed, args.legacy_python, args.loops)
    index = validate()
    if not Path('/.dockerenv').exists() or os.environ.get('OFFICE_REPLAY_CONTAINER') != '1':
        raise ValueError('execute only in a disposable replay container')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    target = args.results_dir / ('compatible-' + stamp)
    target.mkdir(parents=True, exist_ok=False)
    report = {'schema_version': 'document-oe-compatible-qualification-v2', 'status': 'in_progress',
              'project_lock_sha256': digest(ROOT / 'assets/project-lock.json'),
              'contract_sha256': index['contract_sha256'], 'legacy_lock_sha256': index['legacy_lock_sha256'],
              'python_mode': args.legacy_python, 'timed': args.timed, 'requires_llm': False,
              'classification': 'adapted_replay_recipe_not_new_agent_trace',
              'results': [], 'loop_policy': 'one native process per dataset; no outer work between iterations',
              'archive_scope': 'final_iteration_only',
              'timing_scope': 'Native iteration/phase times only; independent acceptance and archival occur after the entire loop. No CPU/OS experiment.'}
    write(target / 'summary.json', report)
    for dataset in args.dataset or DATASETS:
        entry = next(e for e in index['entries'] if e['dataset_id'] == dataset and
                     (e['record_count'] is None or e['record_count'] == args.pdf_applicant_count))
        item = run_dataset(entry, target, args.loops, args.timed, args.legacy_python)
        report['results'].append(item)
        if item['status'] != 'success':
            report['status'] = 'failed'
            write(target / 'summary.json', report)
            print(dataset, item['error'], flush=True)
            return 1
        write(target / 'summary.json', report)
    report['status'] = 'success'
    write(target / 'summary.json', report)
    print('compatible report:', target / 'summary.json', flush=True)
    return 0


def read_events(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


if __name__ == '__main__':
    raise SystemExit(main())
