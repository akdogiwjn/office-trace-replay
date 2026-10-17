#!/usr/bin/env python3
"""Freeze explicit old-workflow adaptations; never rewrite parent traces."""
import copy
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from replay.common import digest, read, write

DATASETS = ['irs_w4', 'sba1919', 'hr', 'manufacturing', 'retail']
HELPERS = {
    'irs_w4': ['build_field_values.py'],
    'sba1919': ['helpers/build_field_values.py'],
    'hr': ['helpers/build.py', 'helpers/patch.py'],
    'manufacturing': ['build_enhanced.py', 'inject_caches.py'],
    'retail': ['helpers/build_enhance.py', 'helpers/assemble_output.py'],
}
BUILD = {'irs_w4': 'build_field_values.py', 'sba1919': 'helpers/build_field_values.py',
         'hr': 'helpers/build.py', 'manufacturing': 'build_enhanced.py', 'retail': 'helpers/build_enhance.py'}


def main():
    index = {'schema_version': 'document-oe-compatible-suite-v1', 'contract_sha256': digest(ROOT / 'compatibility/contract.json'),
             'legacy_lock_sha256': digest(ROOT / 'legacy/document-oe/lock.json'), 'entries': []}
    for dataset in DATASETS:
        parent_path = ROOT / 'recipes' / (dataset + '.json')
        parent = read(parent_path)
        old_seed = ROOT / parent['seed_path']
        old_source = ROOT / parent['source_path']
        original_manifest = read(old_seed / 'input/dataset_manifest.json')
        kind = original_manifest['kind']
        for count in ([1, 10] if kind == 'pdf' else [None]):
            variant = dataset + (f'-n{count}' if count else '')
            case = ROOT / 'compatibility/cases' / variant
            seed = case / 'seed'
            source = case / 'source'
            seed.mkdir(parents=True, exist_ok=True)
            shutil.copytree(old_seed / 'input', seed / 'input', dirs_exist_ok=True)
            # A private source copy permits a versioned PDF subset contract,
            # without changing any canonical source/records/manifest bytes.
            shutil.copytree(old_source, source, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
            manifest = copy.deepcopy(original_manifest)
            adaptations = ['Use original native executor, original Skill tools and original runtime/timing boundaries.']
            if kind == 'pdf':
                record_path = seed / 'input' / manifest['records']
                records = read(record_path)
                if len(records[manifest['records_key']]) != 10:
                    raise ValueError('compatible PDF preparation requires the frozen ten-record fixture')
                ds = source / 'datasets/pdf' / dataset
                expected = read(ds / manifest['expected_file'])
                summary = copy.deepcopy(manifest['summary_contract'])
                summary.update(applicant_count=count, filled_pdf_count=count,
                               rendered_page_count=manifest['requirements']['page_count'] * (count + 1),
                               fill_script_invocations=count, render_script_invocations=count + 1,
                               prepared_record_count=10, field_values_count=10)
                expected['summary_values'] = summary
                write(ds / manifest['expected_file'], expected)
                manifest['expected_sha256'] = digest(ds / manifest['expected_file'])
                manifest['summary_contract'] = summary
                manifest['pdf_execution'] = {
                    'record_count': count,
                    'record_ids': [r['id'] for r in records[manifest['records_key']][:count]],
                    'selection': 'first records in frozen input order',
                }
                manifest['compatibility_variant'] = {'id': variant, 'method': 'prepare all records; execute selected prefix',
                    'parent_manifest_sha256': digest(old_seed / 'input/dataset_manifest.json')}
                # The original records, records contract, parent verifier and
                # canonical trace remain unchanged. Only this private source
                # dispatches to a verifier that distinguishes prepared/executed.
                shutil.copyfile(ROOT / 'compatibility/verification/pdf.py',
                                source / 'office_trace_bench/compatible_pdf.py')
                verifier = source / 'office_trace_bench/verify.py'
                original = verifier.read_text()
                marker = '            verify_pdf(manifest, expected, workspace, checks)'
                if original.count(marker) != 1:
                    raise ValueError('unexpected parent PDF verifier dispatch')
                verifier.write_text(original.replace(marker,
                    '            from .compatible_pdf import verify_pdf as verify_prepared_pdf\n'
                    '            verify_prepared_pdf(manifest, expected, workspace, checks)'))
                manifest['compatibility_variant']['verifier_sha256'] = digest(source / 'office_trace_bench/compatible_pdf.py')
                write(ds / 'manifest.json', manifest)
                write(seed / 'input/dataset_manifest.json', manifest)
                adaptations += [f'Prepare all ten original mappings; explicitly fill/render first {count} records.',
                                'Same field-ID precheck for both new PDFs; complete mapping checks remain in final verification.',
                                'One subprocess batch driver alternates fill/render per selected record, matching the old driver pattern.',
                                'Private verifier checks all prepared mappings and exactly the selected PDFs/renders.']
            else:
                adaptations += ['One build and one original recalc; retain clean build instead of rebuilding.',
                                'Keep necessary formula-cache/source-content assembly as an explicit extra call.',
                                'Export actual manifest metric/projection values to metrics.csv/scenario.csv; no fabricated TLC sheets.']

            ws = parent['workspace']
            phases = ['inspect_prepare', 'build', 'process_publish', 'verify_deliver']
            steps = [{'operation_id': f'{kind.upper()}-P0{i}-{phase}', 'source_tool_calls': []}
                     for i, phase in enumerate(phases, 1)]
            def add(stage, function, arguments, role):
                steps[stage - 1]['source_tool_calls'].append({
                    'adaptation': 'document-oe-compatible-workflow-v2', 'role': role,
                    'tool_call': {'function_name': function, 'arguments': arguments}})
            def command(stage, cmd, role):
                add(stage, 'exec', {'command': f'cd {ws} && {cmd}'}, role)
            def write_helper(name, text):
                add(2, 'write', {'path': ws + '/' + name, 'content': text}, 'write_helper')

            add(1, 'read', {'path': f'/root/.openclaw/skills/{kind}/SKILL.md'}, 'read_skill')
            if kind == 'pdf':
                add(1, 'read', {'path': '/root/.openclaw/skills/pdf/forms.md'}, 'read_skill')
                add(1, 'read', {'path': ws + '/input/verify_office.py'}, 'read_verifier')
                tools = '/root/.openclaw/skills/pdf/scripts/'
                for name in ['check_fillable_fields.py', 'extract_form_field_info.py', 'fill_fillable_fields.py', 'convert_pdf_to_images.py']:
                    add(1, 'read', {'path': tools + name}, 'read_tool')
                command(1, 'mkdir -p output/field_values output/filled output/rendered/template', 'prepare')
                command(1, f'python3 {tools}check_fillable_fields.py input/{manifest["form"]} > output/check_fillable_fields.log 2>&1', 'check_fields')
                command(1, 'cat output/check_fillable_fields.log', 'inspect_log')
                command(1, f'python3 {tools}extract_form_field_info.py input/{manifest["form"]} output/form_field_info.json', 'extract_fields')
                add(1, 'read', {'path': ws + '/output/form_field_info.json'}, 'inspect_schema')
                command(1, f'python3 {tools}convert_pdf_to_images.py input/{manifest["form"]} output/rendered/template', 'render_template')
            else:
                command(1, 'cat input/verify_office.py', 'read_verifier')
                prepare = 'mkdir -p work && ' if dataset == 'retail' else ''
                command(1, prepare + f'cp input/{manifest["workbook"]} output/{manifest["output_workbook"]}', 'copy_input')
                for mode in ['source', 'copy']:
                    command(1, f'python3 /opt/office-trace-replay/compatibility/tools/inspect_xlsx.py {mode}', 'inspect_workbook')

            for helper in HELPERS[dataset]:
                write_helper(helper, (old_seed / helper).read_text())
            command(2, 'python3 ' + BUILD[dataset], 'build')
            if kind == 'pdf':
                command(2, "python3 -c \"import json,pathlib; ids={v['field_id'] for v in json.load(open('output/form_field_info.json'))}; rows=[json.load(open(p)) for p in pathlib.Path('output/field_values').glob('*.json')]; assert all(v['field_id'] in ids for r in rows for v in r); print('mapping checked')\"", 'validate_mapping')
                write_helper('run_batch_fill_render.py', (ROOT / 'compatibility/tools/pdf_batch.py').read_text())
                command(3, 'python3 run_batch_fill_render.py', 'fill_render_batch')
                command(3, 'python3 /opt/office-trace-replay/compatibility/tools/summary.py', 'write_summary')
                command(4, 'python3 input/verify_office.py', 'semantic_verification')
                command(4, 'find output -type f | sort', 'check_deliverables')
            else:
                if dataset == 'hr':
                    base, recalc, assemble = 'helpers/pre_recalc.xlsx', 'helpers/rec_recalc.xlsx', 'helpers/patch.py'
                elif dataset == 'manufacturing':
                    base, recalc, assemble = 'build/enhanced_base.xlsx', 'build/recalc_work.xlsx', 'inject_caches.py'
                else:
                    base, recalc, assemble = 'work/build.xlsx', 'work/recalc_input.xlsx', 'helpers/assemble_output.py'
                command(3, f'cp {base} {recalc} && python3 /root/.openclaw/skills/xlsx/scripts/recalc.py {recalc} __DOCUMENT_RECALC_TIMEOUT__ > output/formula_recalc.json 2> output/formula_recalc.stderr.log', 'recalculate')
                command(3, 'python3 ' + assemble, 'source_preservation')
                # HR build emits its index itself; other indexes were authored
                # in the parent trace. Only locations are restored, not answers.
                if dataset != 'hr':
                    for step in parent['key_operations']:
                        for item in step['source_tool_calls']:
                            c = item['tool_call']
                            if c['function_name'] == 'write' and c['arguments']['path'].endswith('/workbook_features.json'):
                                add(3, 'write', copy.deepcopy(c['arguments']), 'implementation_index')
                                break
                            if c['function_name'] == 'exec' and "cat > output/workbook_features.json <<'EOF'" in c['arguments']['command']:
                                text = c['arguments']['command'].split("cat > output/workbook_features.json <<'EOF'\n", 1)[1].split('\nEOF', 1)[0]
                                add(3, 'write', {'path': ws + '/output/workbook_features.json', 'content': text + '\n'}, 'implementation_index')
                for mode in ['formula', 'cached']:
                    command(3, f'python3 /opt/office-trace-replay/compatibility/tools/inspect_xlsx.py {mode}', 'inspect_workbook')
                command(3, 'cat output/formula_recalc.json', 'inspect_log')
                command(3, 'python3 /opt/office-trace-replay/compatibility/tools/export_xlsx.py', 'export_csv')
                command(4, 'python3 input/verify_office.py', 'semantic_verification')
                command(4, 'python3 /opt/office-trace-replay/compatibility/tools/summary.py', 'write_summary')
                command(4, f'test -s output/{manifest["output_workbook"]} && test -s output/metrics.csv && test -s output/scenario.csv && test -s output/xlsx_enhancement_summary.json', 'check_deliverables')

            recipe = {'schema_version': 'scene-key-operations-v2', 'case_kind': kind,
                      'case_id': manifest['runtime_case'], 'dataset_id': dataset, 'variant_id': variant,
                      'operation_count': 4, 'workflow': {'success_path': [s['operation_id'] for s in steps]},
                      'key_operations': steps, 'workspace': ws, 'seed_path': str(seed.relative_to(ROOT)),
                      'source_path': str(source.relative_to(ROOT)), 'record_count': count,
                      'prepared_record_count': 10 if kind == 'pdf' else None,
                      'operation_timeout': 900 if kind == 'xlsx' else 300,
                      'recalc_timeout': 600 if kind == 'xlsx' else 180,
                      'requires_llm': False, 'classification': 'adapted_replay_recipe_not_new_agent_trace',
                      'parent': {'recipe_path': str(parent_path.relative_to(ROOT)), 'recipe_sha256': digest(parent_path),
                                 **parent['source']},
                      'contract_sha256': index['contract_sha256'], 'adaptations': adaptations,
                      'prompt_path': f'compatibility/prompts/{kind}.txt',
                      'prompt_sha256': digest(ROOT / f'compatibility/prompts/{kind}.txt'),
                      'input_hashes': {str(p.relative_to(seed)): digest(p) for p in (seed / 'input').rglob('*') if p.is_file()},
                      'preservation_call_roles': ['source_preservation'] if kind == 'xlsx' else []}
            target = ROOT / 'compatibility/recipes' / (variant + '.json')
            write(target, recipe)
            index['entries'].append({'dataset_id': dataset, 'variant_id': variant, 'record_count': count,
                                      'recipe_path': str(target.relative_to(ROOT)), 'recipe_sha256': digest(target)})
            print('compiled compatible', variant, sum(len(s['source_tool_calls']) for s in steps))
    write(ROOT / 'compatibility/suite.json', index)


if __name__ == '__main__':
    main()
