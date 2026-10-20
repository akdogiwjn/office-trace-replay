"""Suite orchestration for registered compatible datasets.

Each dataset runs all requested loops inside one unified runner process. Every
iteration keeps the native business verification; no extra independent
acceptance or archival happens between iterations. After the whole loop the
completion status of every iteration is checked (an earlier failure can never
be masked by a later success), then an independent acceptance runs against the
frozen source verifier, and the final workspace, outputs and logs are archived
into a fresh per-invocation run directory so the same results root can be
reused for repeats and PDF 1/10 variants without collisions.
"""
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
import uuid

from .common import ROOT, digest, read, write
from . import context, freeze, legacy


def read_events(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def run_dataset(core, dataset_id, scene, layout, target, loops, timed,
                python_mode, pdf_applicant_count):
    """Run one unified runner process, then final acceptance and archival."""
    record_count = pdf_applicant_count if scene == 'pdf' else None
    variant_id = freeze.resolve_variant(dataset_id, scene, record_count)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    destination = target / variant_id / stamp
    destination.mkdir(parents=True, exist_ok=True)
    interpreter = legacy.native_command([], python_mode=python_mode)[0]
    command = legacy.native_command(
        ['--scene', scene, '--dataset', dataset_id, '--loops', str(loops),
         '--results-dir', str(destination),
         '--operation-timeout', str(layout['operation_timeout']),
         '--recalc-timeout', str(layout['recalc_timeout'])] +
        (['--pdf-applicant-count', str(pdf_applicant_count)] if scene == 'pdf' else []),
        timed, python_mode)
    env = context.environment(python_mode, source=layout['source'])
    item = {'dataset_id': dataset_id, 'variant_id': variant_id, 'run_stamp': stamp,
            'requested_iterations': loops, 'scene': scene,
            'record_count': record_count,
            'status': 'in_progress',
            'archive_scope': 'final_iteration_only',
            'acceptance_scope': 'native business verifier each iteration; independent verifier after entire loop',
            'run_dir': str(destination)}
    try:
        subprocess.run(command, check=True, env=env)
        native_path = _locate_native_run(destination, scene)
        native = read(native_path)
        events = read_events(native_path.with_name('iterations.jsonl'))
        expected_recipe = freeze.expected_recipe_sha256(dataset_id, record_count)
        if (native.get('dataset') != dataset_id or native.get('scene') != scene
                or (scene == 'pdf' and native.get('pdf_applicant_count') != pdf_applicant_count)
                or native.get('recipe_sha256') != expected_recipe
                or native['requested_iterations'] != loops or native['completed_iterations'] != loops
                or native['successes'] != loops or native['failures'] != 0 or native['interrupted']
                or len(events) != loops
                or any(e.get('iteration') != i or e.get('status') != 'success'
                       for i, e in enumerate(events, 1))):
            raise ValueError('native loop incomplete, failed, or dataset/recipe mismatched')
        item.update(native_run_id=native['run_id'],
                    native_summary=str(native_path.relative_to(destination)),
                    native_summary_sha256=digest(native_path),
                    native_events_sha256=digest(native_path.with_name('iterations.jsonl')),
                    native_iterations=events, completed_iterations=loops)
        item.update(_frozen_bindings(dataset_id, record_count, scene))
        item['environment'] = native.get('environment')
        item['python_mode'] = native.get('python_mode')
        try:
            item['runner_sha256'] = digest(legacy.NATIVE / 'bin' / 'run_document_scene_loop.py')
        except FileNotFoundError:
            item['runner_sha256'] = None
        for name in ('summary.json', 'iterations.jsonl'):
            source_file = native_path.with_name(name)
            if source_file.is_file():
                shutil.copy2(source_file, destination / ('native_' + name))
        for name in ('calls.jsonl', 'nested_calls.jsonl'):
            source_file = native_path.with_name(name)
            if source_file.is_file():
                shutil.copy2(source_file, destination / name)
        start = time.perf_counter()
        subprocess.run([interpreter, str(ROOT / 'replay/accept.py'),
                        '--source', str(layout['source']), '--dataset', dataset_id,
                        '--kind', scene, '--workspace', layout['workspace'],
                        '--report', str(destination / 'independent_verification.json')],
                       check=True, env=env)
        acceptance = read(destination / 'independent_verification.json')
        if acceptance['status'] != 'success' or acceptance['failures']:
            raise ValueError('independent verification failed')
        item['independent_acceptance_seconds'] = round(time.perf_counter() - start, 6)
        item['independent_verification_sha256'] = digest(destination / 'independent_verification.json')
        # Reset overwrites previous iterations. Only the final workspace is
        # archived, after all native iterations finish.
        shutil.copytree(Path(layout['workspace']) / 'output', destination / 'output')
        shutil.copytree(Path(layout['workspace']), destination / 'workspace_artifacts')
        item['artifact_hashes'] = {str(p.relative_to(destination / 'workspace_artifacts')): digest(p)
                                  for p in (destination / 'workspace_artifacts').rglob('*') if p.is_file()}
        item['status'] = 'success'
    except Exception as exc:
        item.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        workspace = Path(layout['workspace'])
        if workspace.is_dir():
            shutil.copytree(workspace, destination / 'failure_workspace', dirs_exist_ok=True)
            item['failure_workspace_scope'] = 'last available workspace; earlier iterations may have been reset'
    # Persist the full association: run id, recipe, input, helper, verifier,
    # contract, executor, environment and acceptance result.
    write(destination / 'evidence.json', item)
    return item


def _locate_native_run(destination, scene):
    matches = list((destination / scene).glob('*/summary.json'))
    if len(matches) != 1:
        raise ValueError(f'expected exactly one native run dir, got {len(matches)}')
    return matches[0]


def _frozen_bindings(dataset_id, record_count, scene):
    """Association of the actual recipe, inputs, helpers, verifier, contract,
    executor and environment for the run evidence."""
    index = read(ROOT / 'compatibility/suite.json')
    entry = next(e for e in index['entries']
                 if e['dataset_id'] == dataset_id
                 and (e['record_count'] is None or e['record_count'] == record_count))
    recipe = read(ROOT / entry['recipe_path'])
    bindings = {
        'recipe_sha256': entry['recipe_sha256'],
        'recipe_path': entry['recipe_path'],
        'prompt_sha256': recipe['prompt_sha256'],
        'contract_sha256': index['contract_sha256'],
        'input_hashes': recipe['input_hashes'],
        'helper_hashes': recipe.get('helper_hashes', {}),
        'verifier_contract': recipe.get('workflow_contract'),
        'executor_version': legacy.EXECUTOR_VERSION,
    }
    if recipe.get('origin_type') == 'manual_workflow_adaptation':
        bindings.update(origin_type=recipe['origin_type'],
                        agent_generated=recipe['agent_generated'],
                        requires_llm=recipe['requires_llm'],
                        manual_source=recipe['manual_source'])
    else:
        bindings['parent_recipe_sha256'] = recipe['parent']['recipe_sha256']
    if scene == 'xlsx':
        bindings['verifier_hashes'] = {
            name: digest(ROOT / 'compatibility/verification' / name)
            for name in ('verify.py', 'spreadsheet.py', 'contracts.py', 'workbooks.py')}
    return bindings


def run_old_dataset(dataset_id, scene, results_dir, loops, timed, python_mode, pdf_applicant_count):
    """Byte-preserved old workloads keep the original runner-only behavior."""
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    command = legacy.native_command(
        ['--scene', scene, '--loops', str(loops), '--results-dir', str(results_dir)] +
        (['--pdf-applicant-count', str(pdf_applicant_count)] if scene == 'pdf' else []),
        timed, python_mode)
    env = context.environment(python_mode, source=None)
    return subprocess.call(command, env=env)
