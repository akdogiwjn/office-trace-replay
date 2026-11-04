"""Freeze reviewed final-effective DocOps traces without executing their commands.

The output is a packaging input, not proof that a replay works. Historical
execution-to-script associations remain inferred; the new payload binds bytes.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shlex
import shutil
import sqlite3
import subprocess
import tempfile


INDEX = Path("reports/analysis/DOCOPS-L3-12-TASK-SAMPLE-INDEX-01")
SELECTION = Path("docops/config/selection.json")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes source root: {relative}")
    return path


def destination(path: str) -> str:
    p = PurePosixPath(path)
    if not p.is_absolute() or ".." in p.parts or not p.is_relative_to("/root"):
        raise ValueError(f"invalid task destination: {path}")
    if p == PurePosixPath('/root'):
        raise ValueError("task destination cannot be /root")
    return str(p.relative_to('/'))


def command_argv(command: str) -> list[str]:
    argv = shlex.split(command)
    if len(argv) != 3 or argv[0] != '/bin/bash' or argv[1] not in ('-c', '-lc'):
        raise ValueError('expected exactly bash, -c/-lc, and one shell body')
    result = subprocess.run(['/bin/bash', '-n', '-c', argv[2]],
                            capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError(f"shell syntax error: {result.stderr}")
    return argv


def trace_items(path: Path) -> list[dict]:
    uri = path.resolve().as_uri() + '?mode=ro&immutable=1'
    with sqlite3.connect(uri, uri=True) as db:
        rows = db.execute('SELECT item_id,item_type,item_json FROM thread_items '
                          'ORDER BY created_at_ms,rowid').fetchall()
    return [dict(id=ident, type=kind, value=json.loads(raw))
            for ident, kind, raw in rows]


def record_file(stage: Path, relative: str, data: bytes, inventory: dict):
    if relative in inventory:
        raise ValueError(f'duplicate payload path: {relative}')
    path = inside(stage, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    inventory[relative] = {'bytes': len(data), 'sha256': digest(data)}


def checked_source(root: Path, relative: str, sha: str, size: int | None = None) -> bytes:
    data = inside(root, relative).read_bytes()
    if digest(data) != sha or (size is not None and len(data) != size):
        raise ValueError(f'source identity mismatch: {relative}')
    return data


def compile_payload(root: Path, selection: dict, stage: Path) -> dict:
    samples = load(root / INDEX / 'samples.json')['samples']
    sample_by_task = {s['task']: s for s in samples}
    if set(selection['tasks']) != set(sample_by_task):
        raise ValueError('selection must cover the twelve indexed samples exactly')
    with (root / INDEX / 'script_versions.csv').open(newline='') as f:
        versions = list(csv.DictReader(f))
    inventory: dict = {}
    package = {'schema': 'docops-final-effective-payload-v1',
               'status': 'source_reviewed_pending_replay_validation',
               'scope': 'final_effective_execution', 'tasks': [],
               'environment': selection['environment'],
               'historical_script_binding': 'inferred_not_runtime_byte_proof',
               'measurement_policy': selection['measurement_policy']}
    for task, plan in selection['tasks'].items():
        sample = sample_by_task[task]
        items = trace_items(inside(root, sample['trace']['sqlite']))
        by_id = {item['id']: item for item in items}
        if len(by_id) != len(items):
            raise ValueError(f'duplicate trace ID: {task}')
        recipe = {'schema': 'docops-final-effective-recipe-v1', 'task': task,
                  'task_id': sample['task_id'], 'format': sample['format'],
                  'source_run_id': sample['run_id'],
                  'historical_score': sample['score'],
                  'output_path': None, 'files': [], 'steps': [],
                  'review': plan['review'], 'excluded_items': []}
        run_env_path = str(Path(sample['score']['source_summary']).with_name('run-env.json'))
        run_env = load(inside(root, run_env_path))
        recipe['output_path'] = run_env['OUTPUT_PATH']
        destination(recipe['output_path'])
        task_dir = Path(sample['input']['path']).parent
        for injected in run_env['injected_files']:
            dest = injected['path']
            source = (sample['input']['path'] if dest == run_env['INPUT_PATH'] else
                      sample['instruction'] if Path(dest).name == 'instruction.md' else
                      str(task_dir / Path(dest).name))
            data = checked_source(root, source, injected['sha256'], injected['bytes'])
            rel = f'tasks/{task}/seed/{destination(dest)}'
            record_file(stage, rel, data, inventory)
            recipe['files'].append({'kind': 'input', 'payload': rel,
                                    'destination': dest, 'source': source,
                                    'sha256': digest(data)})
        chosen_versions = []
        for script in plan['scripts']:
            matches = [v for v in versions if v['task'] == task
                       and v['original_path'] == script['path']
                       and int(v['version']) == script['version']]
            if len(matches) != 1:
                raise ValueError(f'nonunique script version: {task} {script}')
            v = matches[0]
            data = checked_source(root, v['preserved_path'], v['sha256'], int(v['bytes']))
            ast.parse(data, filename=v['original_path'])
            rel = f'tasks/{task}/seed/{destination(v["original_path"])}'
            record_file(stage, rel, data, inventory)
            recipe['files'].append({'kind': 'script', 'payload': rel,
                                    'destination': v['original_path'],
                                    'source': v['preserved_path'],
                                    'sha256': digest(data), 'version': int(v['version']),
                                    'source_item_id': v['source_item_id'],
                                    'historical_binding': v['execution_binding']})
            chosen_versions.append(v)
        kept = set()
        previous_workflow = None
        for step_num, step in enumerate(plan['steps'], 1):
            ident = step['source_item_id']
            item = by_id[ident]
            value = item['value']
            if ident in kept or item['type'] != 'commandExecution' or value.get('exitCode') != 0:
                raise ValueError(f'selected command is not unique/successful: {task} {ident}')
            kept.add(ident)
            argv = command_argv(value['command'])
            cwd = value.get('cwd', '/root')
            destination(cwd) if cwd != '/root' else None
            # Bind the exact historical code active at each selected invocation.
            # This is an ordered-trace reconstruction, not a historical runtime hash.
            order = [entry['id'] for entry in items]
            for v in chosen_versions:
                if v['original_path'] not in argv[2]:
                    continue
                preceding = [row for row in versions if row['task'] == task
                             and row['original_path'] == v['original_path']
                             and row['source_item_id'] in by_id
                             and order.index(row['source_item_id']) < order.index(ident)]
                active = max(preceding, key=lambda x: order.index(x['source_item_id']), default=None)
                if active is None or active['sha256'] != v['sha256']:
                    raise ValueError(f'script not active at selected command: {task} {ident}')
            body_path = f'tasks/{task}/commands/{step_num:02d}.sh'
            record_file(stage, body_path, argv[2].encode(), inventory)
            entry = {'id': f'{step_num:02d}', **step, 'cwd': cwd,
                     'argv': argv, 'shell_body': body_path,
                     'shell_sha256': digest(argv[2].encode()),
                     'source_command_sha256': digest(value['command'].encode()),
                     'source_exit_code': value['exitCode'],
                     'depends_on': [] if previous_workflow is None else [previous_workflow]}
            recipe['steps'].append(entry)
            previous_workflow = entry['id']
        for item in items:
            if item['id'] in kept:
                continue
            override = plan.get('exclusion_reasons', {}).get(item['id'])
            reason = override or ('script_materialized_as_frozen_bytes' if item['type'] == 'fileChange'
                       else 'agent_visual_interaction_not_executable_replay' if item['type'] == 'imageView'
                       else 'not_in_reviewed_final_dependency_chain')
            recipe['excluded_items'].append({'source_item_id': item['id'],
                                              'type': item['type'], 'reason': reason})
        trace_data = inside(root, sample['trace']['sqlite']).read_bytes()
        recipe['provenance'] = {'trace': sample['trace']['sqlite'],
                                'trace_sha256': digest(trace_data),
                                'run_env': run_env_path,
                                'run_env_sha256': digest(inside(root, run_env_path).read_bytes())}
        rel = f'tasks/{task}/recipe.json'
        record_file(stage, rel, (json.dumps(recipe, ensure_ascii=False, indent=2)+'\n').encode(), inventory)
        package['tasks'].append({'task': task, 'recipe': rel,
                                 'steps': len(recipe['steps']),
                                 'scripts': len(chosen_versions),
                                 'historical_reward': sample['score']['reward']})
    # Freeze official skills separately from generated scripts. No credentials,
    # histories, submissions, environment Dockerfiles or agent configuration.
    for skill in ('doc', 'xlsx', 'pptx', 'pdf'):
        source = root / 'references/repos/DocOps/skills' / skill
        for path in sorted(source.rglob('*')):
            if path.is_symlink():
                raise ValueError(f'symlink in skill payload: {path}')
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                record_file(stage, f'skills/{skill}/{path.relative_to(source)}', path.read_bytes(), inventory)
    for rel in (INDEX / 'samples.json', INDEX / 'script_versions.csv'):
        record_file(stage, 'provenance/' + rel.name, (root / rel).read_bytes(), inventory)
    record_file(stage, 'provenance/selection.json',
                (json.dumps(selection, ensure_ascii=False, indent=2)+'\n').encode(), inventory)
    record_file(stage, 'catalog.json', (json.dumps(package, ensure_ascii=False, indent=2)+'\n').encode(), inventory)
    (stage / 'payload-index.json').write_text(json.dumps({'schema': 'docops-payload-index-v1',
                                                        'files': inventory}, indent=2)+'\n')
    validate_payload(stage)
    return package


def validate_payload(root: Path) -> dict:
    index = load(root / 'payload-index.json')['files']
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    if actual != set(index) | {'payload-index.json'}:
        raise ValueError('unexpected or missing payload files')
    for relative, expected in index.items():
        checked_source(root, relative, expected['sha256'], expected['bytes'])
    catalog = load(root / 'catalog.json')
    for task in catalog['tasks']:
        recipe = load(inside(root, task['recipe']))
        for step in recipe['steps']:
            if inside(root, step['shell_body']).read_bytes() != step['argv'][2].encode():
                raise ValueError('command body and argv differ')
    return {'files': len(index), 'tasks': len(catalog['tasks']), 'status': 'static_valid',
            'replay_validated': False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    build = sub.add_parser('compile', help='freeze reviewed sources; never executes workload')
    build.add_argument('--source-root', type=Path, required=True,
                       help='original Agent trace repository; used only during import')
    build.add_argument('--output', type=Path, required=True)
    check = sub.add_parser('validate', help='check a previously frozen payload')
    check.add_argument('--payload', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'validate':
        result = validate_payload(args.payload.resolve())
    else:
        output = args.output.absolute()
        if output.exists() or output.is_symlink():
            parser.error(f'refusing existing output: {output}')
        output.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.docops-stage-', dir=output.parent))
        try:
            selection_path = Path(__file__).resolve().parent / 'config/selection.json'
            compile_payload(args.source_root.resolve(), load(selection_path), stage)
            # No force/overwrite mode: a failed compile never replaces a payload.
            if output.exists() or output.is_symlink():
                raise FileExistsError(output)
            os.rename(stage, output)
            result = validate_payload(output)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
