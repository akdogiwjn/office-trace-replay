#!/usr/bin/env python3
"""One-time, explicit import. Never used by replay and never executes trace code."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SELECTION = {
    'egrid': ('xlsx', 2, 'xlsx-egrid-20261027T032347Z-225eb8e9', 'helpers/enhance_energy_report_v2.py',
              [(6, 'inspect_xlsx_structure.py'), (8, 'inspect_xlsx_features.py')],
              [(15, 'inspect_xlsx_formulas.py'), (19, 'inspect_xlsx_cached_values.py')]),
    'hr_metro': ('xlsx', 2, 'xlsx-hr_metro-20261027T042913Z-2c0c625f', 'helpers/enhance_workforce_v2.py',
                 [(6, 'inspect_xlsx_structure.py'), (8, 'inspect_xlsx_features.py')],
                 [(16, 'inspect_xlsx_formulas.py')]),
    'industry_productivity': ('xlsx', 1, 'xlsx-industry_productivity-20261027T015504Z-769d363e',
                              'helpers/enhance_workbook_v1.py',
                              [(5, 'inspect_xlsx_structure.py'), (8, 'inspect_xlsx_features.py')],
                              [(29, 'inspect_xlsx_formulas.py'), (28, 'inspect_xlsx_cached_values.py')]),
    'irs_w4': ('pdf', 1, 'pdf-irs_w4-20261027T021455Z-c206db3d', None, [], []),
    'sba1919': ('pdf', 1, 'pdf-sba1919-20261027T021613Z-ccd6fc4e', None, [], []),
}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def copy(source, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def inline_python(command):
    match = re.search(r"python3\s+-\s*<<\s*['\"]?(\w+)['\"]?\s*\n(.*?)\n\1(?:\n|$)", command, re.S)
    if match:
        code = match.group(2) + '\n'
    else:
        words = shlex.split(command)
        index = words.index('python3')
        if words[index + 1] != '-c':
            raise ValueError('not a recognized inline Python command')
        code = words[index + 2]
    ast.parse(code)
    # Materialization must not add workbook writes or change load modes.
    return code


def source_call(events, ordinal, run_id):
    event = events[ordinal - 1]
    return dict(type='trace', run_id=run_id, event_ordinal=ordinal, step_id=event['step_id'],
                tool_call_id=event['tool_call']['tool_call_id'],
                original_arguments=event['tool_call']['arguments'])


def executes_script(command, name):
    """Match a Python invocation, never a cat/echo or quoted command mention."""
    # Only inspect the command header of a heredoc. Its body is data/code,
    # not additional shell invocations (e.g. cat <<EOF writing a helper).
    header = re.search(r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1[ \t]*\n", command)
    if header:
        command = command[:header.end() - 1]
    lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|\n')
    lexer.whitespace = ' \t\r'
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return False
    segment = []
    segments = []
    for token in tokens:
        if token and all(c in ';&|\n' for c in token):
            segments.append(segment)
            segment = []
        else:
            segment.append(token)
    segments.append(segment)
    for words in segments:
        if not words or not re.fullmatch(r'python(?:3(?:\.\d+)?)?', Path(words[0]).name):
            continue
        args = words[1:]
        while args and args[0] in ('-B', '-u', '-s', '-E', '-I', '-S', '-O', '-OO', '--'):
            args = args[1:]
        if args and args[0] not in ('-c', '-m', '-') and Path(args[0]).name == name:
            return True
    return False


def script_event(events, name):
    return next(n for n, ev in enumerate(events, 1)
                if ev['tool_call']['function_name'] == 'exec'
                and executes_script(ev['tool_call']['arguments'].get('command', ''), name))


def adapted_loop_verifier(original):
    """Keep original trace input immutable; materialize a private replay adapter."""
    additions = (ROOT / 'tools/loop_csv_checks.py.template').read_text()
    anchor = '\ndef verify_cached_values(path, add):'
    check = "        add('zero_cached_formula_errors', not errors, errors[:12])"
    workspace = 'verify_workspace(Path(__file__).resolve().parents[1], args.report_json,'
    for text in (anchor, check, workspace):
        if original.count(text) != 1:
            raise ValueError('unrecognized source verifier for cache-CSV adaptation: ' + text)
    return (original.replace(anchor, '\n' + additions + '\n' + anchor)
            .replace(check, check + '\n        verify_csv_cached(path.parent, values, add)')
            .replace(workspace, 'verify_workspace(Path(__file__).resolve().parent, args.report_json,')
            .replace('dataset-local-tlc-style-v1', 'dataset-local-tlc-style-cache-csv-v2')
            .replace('One normal formula load, then one read-only cached load.',
                     'Replay adaptation: CSVs checked against the existing cached values.\n'
                     'One normal formula load, then one read-only cached load.'))


def import_one(source, dataset, index, target_root=None):
    kind, round_, run_id, helper, before, after = SELECTION[dataset]
    target = (Path(target_root) if target_root else ROOT / 'datasets') / dataset
    if target.exists():
        raise ValueError('refusing to overwrite imported dataset: ' + str(target))
    run = source / 'runs' / run_id
    manifest = read(run / 'run_manifest.json')
    selected = next(x for x in index['datasets'] if x['dataset_id'] == dataset)
    execution = next(x for x in selected['executions'] if x['run_id'] == run_id)
    if execution['qualification_status'] != 'success':
        raise ValueError('source run is not independently qualified')
    events = read(run / 'tool_events.json')['events']
    seed, scripts = target / 'seed', target / 'scripts'
    (seed / 'input').mkdir(parents=True)
    (seed / 'output').mkdir()
    scripts.mkdir()
    for name, expected in manifest['input_hashes'].items():
        path = run / 'workspace' / name
        if digest(path) != expected:
            raise ValueError('run input mismatch: ' + name)
        copy(path, seed / name)
    # Original project-provided manifest/features are frozen preparation inputs.
    copy(run / 'workspace/input/dataset_manifest.json', seed / 'input/dataset_manifest.json')
    if kind == 'xlsx':
        staged = manifest['project_staged_outputs']['output/workbook_features.json']['sha256']
        if digest(run / 'workspace/output/workbook_features.json') != staged:
            raise ValueError('project-staged feature map was changed')
        copy(run / 'workspace/output/workbook_features.json', seed / 'output/workbook_features.json')
    snapshot = read(run / 'source_snapshot.json')['files']
    for path in (source / 'vendor/skills' / kind).rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            relative = str(path.relative_to(source))
            if snapshot.get(relative) != digest(path):
                raise ValueError('Skill differs from execution snapshot: ' + relative)
            copy(path, target / 'skills' / kind / path.relative_to(source / 'vendor/skills' / kind))
    helpers = [helper] if helper else ['build_field_values.py', 'run_batch.py']
    revisions = read(run / 'artifact_revisions/revisions.json')
    bindings = []
    for name in helpers:
        path = run / 'workspace' / name
        sha = digest(path)
        captured = [x for x in revisions['events'] if x.get('sha256') == sha
                    and x.get('path') == 'workspace/' + name]
        if not captured or digest(run / 'artifact_revisions/objects' / sha) != sha:
            raise ValueError('final helper has no verified captured revision: ' + name)
        copy(path, scripts / name)
        bindings.append(dict(path=name, sha256=sha, revision_capture_verified=True,
                             revision_events=captured))
    evidence = target / 'evidence'
    for ex in selected['executions']:
        dest = evidence / ('round-' + str(ex['round']))
        for name in ['run_manifest.json', 'source_snapshot.json', 'task.prompt',
                     'trajectory.json', 'tool_events.json', 'baseline_acceptance.json',
                     'independent_verification.json']:
            path = source / ex['run_path'] / name
            if path.is_file():
                copy(path, dest / name)
        copy(source / ex['run_path'] / 'artifact_revisions/revisions.json', dest / 'revisions.json')
        # Keep code revisions from both runs, without copying generated XLSX/PDFs.
        origin_run = source / ex['run_path']
        for revision in read(origin_run / 'artifact_revisions/revisions.json')['events']:
            name = revision.get('path', '')
            sha = revision.get('sha256')
            if name.endswith('.py') and sha:
                obj = origin_run / 'artifact_revisions/objects' / sha
                target_object = dest / 'code-objects' / sha
                if obj.is_file() and not target_object.exists():
                    if digest(obj) != sha:
                        raise ValueError('corrupt alternate code revision')
                    copy(obj, target_object)
        proof = ex['qualification_evidence']
        path = source / proof['path']
        if digest(path) != proof['sha256']:
            raise ValueError('independent qualification hash mismatch')
        copy(path, dest / 'qualified-independent.json')
        write(dest / 'origin.json', ex)
    write(evidence / 'two-round-index.json', selected)
    phases = [dict(id=n, calls=[]) for n in ('P01', 'P02', 'P03', 'P04')]
    adaptations = []
    def call(phase, argv, origin, **kw):
        phases[phase - 1]['calls'].append(dict(argv=argv, origin=origin, **kw))
    def own(phase, name, description, **kw):
        call(phase, ['{python}', name], dict(type='replay_adaptation', description=description), **kw)
    for ordinal, name in before:
        code = inline_python(events[ordinal - 1]['tool_call']['arguments']['command'])
        (scripts / name).write_text(code)
        call(1, ['{python}', name], source_call(events, ordinal, run_id))
    if kind == 'xlsx':
        origin = source_call(events, {'egrid': 28, 'hr_metro': 15, 'industry_productivity': 13}[dataset], run_id)
        origin.update(type='final_captured_agent_helper', path=helper, sha256=bindings[0]['sha256'],
                      adaptation='Execute final captured helper directly; omit preceding text patch/time wrapper.')
        call(2, ['{python}', helper], origin)
        recalc_event = {'egrid': 29, 'hr_metro': 17, 'industry_productivity': 15}[dataset]
        task = read(seed / 'input/dataset_manifest.json')
        call(3, ['{python}', '/root/.openclaw/skills/xlsx/scripts/recalc.py',
                 'output/' + task['output_workbook'], '600'],
             source_call(events, recalc_event, run_id), stdout='output/formula_recalc.json', timeout=900)
        for ordinal, name in after:
            (scripts / name).write_text(inline_python(events[ordinal - 1]['tool_call']['arguments']['command']))
            call(3, ['{python}', name], source_call(events, ordinal, run_id))
        # Keep filenames, labels and row order; values come only from this run's caches.
        exports = []
        for item in task['publish_files']:
            import csv
            with (seed / 'input' / item['input']).open(newline='') as stream:
                rows = list(csv.reader(stream))
            locations = ([[f'B{r}'] for r in range(5, 10)] if len(rows[0]) == 2
                         else [['B5', 'B6', 'B9'], ['B15', 'B16', 'B9']])
            if len(rows) - 1 != len(locations):
                raise ValueError('unexpected CSV shape')
            exports.append(dict(filename=item['output'], header=rows[0],
                                rows=[dict(label=r[0], cells=coords)
                                      for r, coords in zip(rows[1:], locations)]))
        write(scripts / 'csv-contract.json', dict(dataset_id=dataset,
              workbook=task['output_workbook'], sheet=task['task_layout']['features']['summary_sheet'],
              exports=exports, numeric_relative_tolerance=1e-8, numeric_absolute_tolerance=1e-6))
        copy(ROOT / 'tools/export_xlsx_csv.py.template', scripts / 'export_xlsx_csv.py')
        own(3, 'export_xlsx_csv.py', 'Replace prepared CSV copies with one read-only final-cache load and CSV writes; no recomputation.')
        verifier = scripts / 'verify_xlsx_enhanced.py'
        verifier.write_text(adapted_loop_verifier((seed / 'input/verify_xlsx_enhanced.py').read_text()))
        call(4, ['{python}', 'verify_xlsx_enhanced.py', 'output/' + task['output_workbook'],
                 'output/formula_recalc.json', 'output/business_verification.json'],
             dict(type='replay_verifier_adaptation',
                  original_sha256=digest(seed / 'input/verify_xlsx_enhanced.py'), sha256=digest(verifier),
                  description='Private original verifier plus CSV-to-current-cache checks; reuses its cached load.'))
        copy(ROOT / 'tools/write_summary.py.template', scripts / 'write_xlsx_summary.py')
        own(4, 'write_xlsx_summary.py', 'Generate current replay counts/status; never copy historical success or hashes.')
        adaptations += ['Prepared CSV copy replaced by final-cache export; filenames, headers and row order retained.',
                        'Loop CSV validation reuses cached Summary values; independent audit also validates CSVs. No extra workbook load.',
                        'Runtime summary reports only this replay; original Agent summary remains historical evidence.']
        # Historical JSON writes are evidence only, never replay outputs.
    else:
        task = read(seed / 'input/dataset_manifest.json')
        skill = '/root/.openclaw/skills/pdf/scripts/'
        for name, argv_ in [
                ('check_fillable_fields.py', ['input/' + task['form']]),
                ('extract_form_field_info.py', ['input/' + task['form'], 'output/form_field_info.json']),
                ('convert_pdf_to_images.py', ['input/' + task['form'], 'output/rendered/template'])]:
            ordinal = script_event(events, name)
            extra = {'stdout': 'output/check_fillable_fields.log'} if name == 'check_fillable_fields.py' else {}
            call(1, ['{python}', skill + name, *argv_], source_call(events, ordinal, run_id), **extra)
        call(2, ['{python}', 'build_field_values.py'], dict(type='final_captured_agent_helper', run_id=run_id,
                                                       path='build_field_values.py', sha256=bindings[0]['sha256']))
        call(3, ['{python}', 'run_batch.py'], dict(type='final_captured_agent_helper', run_id=run_id,
                                               path='run_batch.py', sha256=bindings[1]['sha256']), timeout=900)
        copy(ROOT / 'tools/write_summary.py.template', scripts / 'write_pdf_batch_summary.py')
        own(4, 'write_pdf_batch_summary.py', 'Observe regenerated PDF/PNG/mapping counts; W-4 original summary was an Agent JSON write.')
        call(4, ['{python}', 'input/verify_pdf_batch.py', 'input/' + task['form'],
                 'input/' + task['records'], 'output', 'output/business_verification.json'],
             dict(type='frozen_dataset_verifier', sha256=digest(seed / 'input/verify_pdf_batch.py')))
        adaptations.append('Only W-4 summary JSON write is replaced with an observed-output summary; SBA driver summary is retained and checked.')
    write(scripts / 'replay-config.json', dict(dataset_id=dataset, kind=kind, source_run_id=run_id,
          source_round=round_, output_workbook=task.get('output_workbook'), form=task.get('form'),
          records=task.get('records'), requirements=task['requirements'], helper=helper))
    runner = (ROOT / 'tools/dataset_runner.py.template').read_text().replace(
        '# DATASET_RUNTIME_BOOTSTRAP', (ROOT / 'tools/runtime_bootstrap.py.template').read_text().rstrip())
    (target / 'run.py').write_text(runner)
    adapter = target / 'runtime/bin/soffice'
    copy(ROOT / 'tools/soffice-openeuler.sh.template', adapter)
    adapter.chmod(0o755)
    write(target / 'recipe.json', dict(schema_version='independent-agent-replay-v1', dataset_id=dataset,
          kind=kind, mode='effective-tool-chain', source_run_id=run_id, source_round=round_,
          required_outputs=task['required_outputs'],
          workspace=manifest['prompt_workspace'], phases=phases,
          policy='Selected inspections and effective final build; no LLM, repair, preview or Agent waits.'))
    # A complete, private source tree per case for OUTSIDE-loop independent audits.
    audit = target / 'audit_source'
    shutil.copytree(source / 'office_trace_bench', audit / 'office_trace_bench',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(source / 'runtime_context', audit / 'runtime_context',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    copy(source / 'office.py', audit / 'office.py')
    dataset_source = source / 'datasets' / kind / dataset
    audit_dataset = audit / 'datasets' / kind / dataset
    for p in dataset_source.glob('*.json'):
        copy(p, audit_dataset / p.name)
    matching = [p for p in dataset_source.glob('*manifest.json')
                if digest(p) == manifest['manifest_sha256']]
    if len(matching) != 1:
        raise ValueError('cannot uniquely recover the source manifest by its run hash')
    active = matching[0]
    # Bind to the run's actual manifest, not an unrelated old manifest.json.
    if digest(active) != manifest['manifest_sha256']:
        raise ValueError('active manifest differs from selected Agent run')
    (audit_dataset / 'input').mkdir(exist_ok=True)
    for p in (seed / 'input').iterdir():
        if p.is_file():
            os.link(p, audit_dataset / 'input' / p.name)
    copy(source / 'prompts' / task['prompt_template'], audit / 'prompts' / task['prompt_template'])
    copy(ROOT / 'tools/audit.py.template', target / 'audit.py')
    write(target / 'audit-contract.json', dict(manifest_path=str(active.relative_to(source)),
          csv_adaptation=kind == 'xlsx', source_version_policy='Frozen independent auditor as of import; separate from original runtime verifier.',
          original_manifest_sha256=digest(active)))
    write(target / 'environment.json', dict(image_id=manifest['runtime_image_id'], python='3.12.3',
          libreoffice='24.2.7.2', poppler='24.02.0',
          packages={'openpyxl':'3.1.5','pypdf':'6.10.0','pdf2image':'1.17.0','pillow':'12.2.0'}))
    write(target / 'replay-environment.json', dict(
          image_id='sha256:e68ea4ca0e43340b09dd355b4217f756260fe4ae3d33c576fdb0b8ab4d5f437a',
          python='3.12.3', libreoffice='25.8.7.3', poppler='23.12.0',
          packages={'openpyxl':'3.1.5','pypdf':'6.10.0','pdf2image':'1.17.0','pillow':'12.2.0'},
          adapter='runtime/bin/soffice selects the standard user profile used by the unmodified Skill',
          policy='Common openEuler replay environment; differs from original Agent environment and requires new functional qualification.'))
    provenance = dict(dataset_id=dataset, kind=kind, source_run_id=run_id,
          original_prompt_sha256=manifest['prompt_sha256'], original_manifest_sha256=manifest['manifest_sha256'],
          original_input_hashes=manifest['input_hashes'], agent_helpers=bindings,
          skill_recalc_sha256=digest(target / 'skills/xlsx/scripts/recalc.py') if kind == 'xlsx' else None,
          intentional_adaptations=adaptations, inspections='Trace inline Python extracted byte-for-byte; original load modes and scopes retained.',
          omitted='Other debugging, repair executions, temporary previews, model reasoning, poll waits and post-loop deep audit.',
          status='compiled_static_only_not_replayed', source_index_sha256=digest(source / 'artifacts/agent-generation-two-rounds-20261027T032149Z-b2ef950d.json'))
    provenance['replay_environment_policy'] = 'One common openEuler image with document-oe; standard-profile soffice path adapter outside the unmodified Skill.'
    write(target / 'provenance.json', provenance)
    files = {str(p.relative_to(target)): digest(p) for p in sorted(target.rglob('*'))
             if p.is_file() and p.name != 'lock.json' and '__pycache__' not in p.parts}
    write(target / 'lock.json', dict(schema_version='independent-dataset-lock-v1', files=files))
    print(dataset, 'imported', len(files), 'files; original helper and Skill bytes verified', flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--dataset', action='append', choices=tuple(SELECTION))
    args = parser.parse_args(argv)
    source = args.source.resolve()
    index = read(source / 'artifacts/agent-generation-two-rounds-20261027T032149Z-b2ef950d.json')
    staging = ROOT / '.import-staging'
    staging.mkdir(exist_ok=True)
    (ROOT / 'datasets').mkdir(exist_ok=True)
    for dataset in args.dataset or SELECTION:
        final = ROOT / 'datasets' / dataset
        if final.exists():
            raise ValueError('refusing to overwrite imported dataset: ' + str(final))
        with tempfile.TemporaryDirectory(prefix=dataset + '-', dir=staging) as temp:
            import_one(source, dataset, index, Path(temp))
            os.rename(Path(temp) / dataset, final)
    entries = []
    for case in sorted((ROOT / 'datasets').iterdir()):
        if not (case / 'lock.json').is_file():
            continue
        recipe = read(case / 'recipe.json')
        entries.append(dict(dataset_id=case.name, kind=recipe['kind'], source_run_id=recipe['source_run_id'],
                            lock_sha256=digest(case / 'lock.json'), recipe_sha256=digest(case / 'recipe.json'),
                            execution_status='compiled_static_only_not_replayed'))
    write(ROOT / 'suite.json', dict(schema_version='independent-agent-suite-v1',
          branch='agent-traces', datasets=entries,
          legacy_component='../document-oe (same image, separate entry; never dispatched here)'))


if __name__ == '__main__':
    main()
