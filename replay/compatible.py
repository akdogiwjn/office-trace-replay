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


def native_child(recipe_path, results, timed, python_mode):
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
                '--scene', kind, '--loops', '1', '--results-dir', str(results),
                '--operation-timeout', str(recipe['operation_timeout']),
                '--recalc-timeout', str(recipe['recalc_timeout'])]
    if kind == 'pdf':
        sys.argv += ['--pdf-applicant-count', str(recipe['record_count'])]
    return core.main()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', action='append', choices=DATASETS)
    parser.add_argument('--loops', type=int, default=1)
    parser.add_argument('--pdf-applicant-count', type=int, choices=[1, 10], default=1)
    parser.add_argument('--legacy-python', choices=['system', 'venv'], default='system')
    parser.add_argument('--timed', action='store_true')
    parser.add_argument('--results-dir', type=Path, default=Path('/results'))
    parser.add_argument('--native-child', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.native_child:
        return native_child(args.native_child, args.results_dir, args.timed, args.legacy_python)
    if args.loops < 1:
        parser.error('loops must be positive')
    index = validate()
    if not Path('/.dockerenv').exists() or os.environ.get('OFFICE_REPLAY_CONTAINER') != '1':
        raise ValueError('execute only in a disposable replay container')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    target = args.results_dir / ('compatible-' + stamp)
    target.mkdir(parents=True, exist_ok=False)
    interpreter = legacy.native_command([], python_mode=args.legacy_python)[0]
    report = {'schema_version': 'document-oe-compatible-qualification-v1', 'status': 'in_progress',
              'project_lock_sha256': digest(ROOT / 'assets/project-lock.json'),
              'contract_sha256': index['contract_sha256'], 'legacy_lock_sha256': index['legacy_lock_sha256'],
              'python_mode': args.legacy_python, 'timed': args.timed, 'requires_llm': False,
              'classification': 'adapted_replay_recipe_not_new_agent_trace',
              'results': [], 'timing_scope': 'Native iteration/phase times only; preparation, independent acceptance and archival are separate. No CPU/OS experiment.'}
    write(target / 'summary.json', report)
    for dataset in args.dataset or DATASETS:
        entry = next(e for e in index['entries'] if e['dataset_id'] == dataset and
                     (e['record_count'] is None or e['record_count'] == args.pdf_applicant_count))
        recipe = read(ROOT / entry['recipe_path'])
        for iteration in range(1, args.loops + 1):
            destination = target / entry['variant_id'] / f'{iteration:04d}'
            destination.mkdir(parents=True)
            command = [interpreter, str(ROOT / 'replay/compatible.py'), '--native-child', str(ROOT / entry['recipe_path']),
                       '--results-dir', str(destination), '--legacy-python', args.legacy_python]
            if args.timed:
                command.append('--timed')
            item = {'dataset_id': dataset, 'variant_id': entry['variant_id'], 'iteration': iteration,
                    'recipe_sha256': entry['recipe_sha256'], 'parent': recipe['parent'], 'status': 'in_progress'}
            report['results'].append(item)
            try:
                subprocess.run(command, check=True)
                native_path = next(destination.glob(recipe['case_kind'] + '/*/summary.json'))
                native = read(native_path)
                if native['successes'] != 1 or native['failures'] != 0 or native['interrupted']:
                    raise ValueError('native execution failed')
                item['native_summary'] = str(native_path.relative_to(target))
                item['native_summary_sha256'] = digest(native_path)
                events = read_events(native_path.with_name('iterations.jsonl'))
                item['native_iteration'] = events[0]
                start = time.perf_counter()
                subprocess.run([interpreter, str(ROOT / 'replay/accept.py'), '--source', str(ROOT / recipe['source_path']),
                                '--dataset', dataset, '--kind', recipe['case_kind'], '--workspace', recipe['workspace'],
                                '--report', str(destination / 'independent_verification.json')], check=True)
                item['independent_acceptance_seconds'] = round(time.perf_counter() - start, 6)
                item['independent_verification_sha256'] = digest(destination / 'independent_verification.json')
                shutil.copytree(Path(recipe['workspace']) / 'output', destination / 'output')
                # Preserve scripts/intermediates separately from measured native calls.
                shutil.copytree(Path(recipe['workspace']), destination / 'workspace_artifacts')
                item['artifact_hashes'] = {str(p.relative_to(destination / 'workspace_artifacts')): digest(p)
                                          for p in (destination / 'workspace_artifacts').rglob('*') if p.is_file()}
                item['status'] = 'success'
            except Exception as exc:
                item.update(status='failed', error=f'{type(exc).__name__}: {exc}')
                workspace = Path(recipe['workspace'])
                if workspace.is_dir():
                    shutil.copytree(workspace, destination / 'failure_workspace', dirs_exist_ok=True)
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
