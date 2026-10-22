#!/usr/bin/env python3
"""Compile reviewed selections; this does not infer dependencies using a model."""
import copy
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from replay.common import digest, read, relative, write
from replay.selections import NOTES, RUNS, SELECTIONS


def main():
    imported = read(ROOT / 'assets/import-lock.json')
    index = {'schema_version': 'office-effective-replay-suite-v1',
             'scope': 'final_effective_tool_execution', 'requires_llm': False,
             'import_lock_sha256': digest(ROOT / 'assets/import-lock.json'), 'datasets': []}
    for entry in imported['datasets']:
        dataset = entry['dataset_id']
        pack = ROOT / entry['canonical_path']
        canonical = read(pack / 'canonical.json')
        if canonical['original_run_id'] != RUNS[dataset]:
            raise ValueError('selection is for a different frozen run')
        events = read(pack / 'tool_events.json')['events']
        inventory = canonical['artifact_inventory']
        objects = ROOT / 'assets/objects/sha256'
        def blob(name):
            return objects / inventory[name]['sha256']
        manifest = read(blob('workspace/input/dataset_manifest.json'))
        ws = '/root/.openclaw/workspace/tool-modeling/' + manifest['runtime_case']
        case = ROOT / 'assets/cases' / dataset
        seed = case / 'seed'
        seed.mkdir(parents=True, exist_ok=True)
        helpers = {}
        for name, spec in inventory.items():
            if not name.startswith('workspace/'):
                continue
            rel = relative(name.removeprefix('workspace/'))
            # Inputs and text helper code only: no frozen final/intermediate XLSX,
            # filled PDF, PNG, calculated caches, or prior acceptance result.
            is_input = rel.parts[0] == 'input'
            is_helper = rel.parts[0] != 'output' and rel.suffix in ('.py', '.sh', '.md')
            if not (is_input or is_helper):
                continue
            dest = seed / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob(name).read_bytes())
            if is_helper:
                helpers[str(rel)] = spec['sha256']
        (seed / 'output').mkdir(exist_ok=True)
        stages = ['inspect_prepare', 'build', 'process_publish', 'verify_deliver']
        steps = []
        selected = []
        for number, (phase, selections) in enumerate(zip(stages, SELECTIONS[dataset]), 1):
            step = {'operation_id': f'{manifest["kind"].upper()}-P0{number}-{phase}', 'source_tool_calls': []}
            for pos, override in selections:
                original = events[pos]['tool_call']
                call = copy.deepcopy(original)
                action = 'archived_call'
                if override and override.startswith('read:'):
                    call = {'function_name': 'read', 'arguments': {'path': ws + '/' + override[5:]}}
                    action = 'read_final_helper_after_staging'
                elif override and override.startswith('frozen-write:'):
                    rel = relative(override.removeprefix('frozen-write:'))
                    if rel.name not in ('batch_summary.json', 'xlsx_enhancement_summary.json', 'workbook_features.json'):
                        raise ValueError('only Agent-authored descriptive metadata may use frozen writes')
                    call = {'function_name': 'write', 'arguments': {'path': ws + '/' + str(rel),
                            'content': blob('workspace/' + str(rel)).read_text()}}
                    action = 'emit_captured_final_agent_metadata'
                elif override:
                    call = {'function_name': 'exec', 'arguments': {'command': f'cd {ws} && {override}'}}
                    action = 'explicit_shell_reduction'
                if call['function_name'] not in ('read', 'write', 'exec'):
                    raise ValueError('effective recipes only use read/write/exec')
                if call['function_name'] == 'exec':
                    # Synchronize archived async exec and expose pipeline failures.
                    call['arguments'] = {'command': 'set -e\nset -o pipefail\n' + call['arguments']['command']}
                item = {'tool_call_id': original['tool_call_id'], 'source_event_index': pos,
                        'source_step_id': events[pos]['step_id'], 'adaptation': action,
                        'source_call_sha256': hashlib.sha256(__import__('json').dumps(original, sort_keys=True).encode()).hexdigest(),
                        'tool_call': call}
                step['source_tool_calls'].append(item)
                selected.append(original['tool_call_id'])
            steps.append(step)
        gaps = []
        for gap in canonical['revision_capture']['gaps']:
            path = gap['path']
            if path != 'workspace/output/business_verification.json.tmp':
                raise ValueError('unreviewed capture gap: ' + path)
            record = read(blob('artifact_revisions/revisions.json'))
            # Require a captured final-file rename and final snapshot, not merely
            # a .tmp suffix. The report is regenerated by the retained verifier.
            final = 'workspace/output/business_verification.json'
            rename = [e for e in record['events'] if e.get('path') == final and e.get('event') == 'moved_to']
            if not rename or final not in inventory:
                raise ValueError('missing rename evidence for temporary report gap')
            gaps.append({**gap, 'classification': 'ephemeral_in_selected_recipe',
                         'final_artifact_sha256': inventory[final]['sha256'],
                         'evidence': 'captured moved_to final report; selected verifier regenerates it; no selected consumer reads the tmp path'})
        recipe = {'schema_version': 'scene-key-operations-v2', 'case_id': manifest['runtime_case'],
                  'case_kind': manifest['kind'], 'dataset_id': dataset, 'scope': index['scope'],
                  'operation_count': 4, 'workflow': {'success_path': [s['operation_id'] for s in steps]},
                  'key_operations': steps, 'requires_llm': False,
                  'source': {'canonical_sha256': entry['canonical_sha256'],
                             'original_run_id': canonical['original_run_id'],
                             'trajectory_sha256': canonical['trace_sha256'],
                             'tool_events_sha256': canonical['tool_events_sha256'],
                             'manifest_sha256': canonical['manifest_sha256'],
                             'prompt_sha256': canonical['prompt_sha256'],
                             'skill_and_context_hashes': canonical['skill_and_context_hashes'],
                             'input_hashes': canonical['input_hashes'],
                             'original_runtime_image_id': canonical['runtime_image_id'],
                             'original_runtime_versions': canonical['agent_runtime_versions']},
                  'helper_hashes': helpers, 'review': {'method': 'explicit per-run manual selection, frozen final helper staging, dependency reconstruction and executable qualification',
                  'note': NOTES[dataset], 'selected_call_ids': selected,
                  'excluded_call_ids': [e['tool_call']['tool_call_id'] for e in events if e['tool_call']['tool_call_id'] not in selected],
                  'capture_gap_decisions': gaps,
                  'qualifications': 'Recipe existence alone is not replay qualification. Read reports/qualification.json for runtime-specific results.'},
                  'workspace': ws, 'source_path': entry['source_path'],
                  'seed_path': str(seed.relative_to(ROOT)),
                  'scratch_files': ['/tmp/report_base.xlsx', '/tmp/report_recalc.xlsx'] if dataset == 'tlc' else [],
                  'operation_timeout': 1800 if dataset == 'tlc' else 900,
                  'recalc_timeout': 180}
        target = ROOT / 'recipes' / (dataset + '.json')
        write(target, recipe)
        index['datasets'].append({'dataset_id': dataset, 'kind': manifest['kind'],
                                 'recipe_path': str(target.relative_to(ROOT)), 'recipe_sha256': digest(target),
                                 'canonical_path': entry['canonical_path'], 'canonical_sha256': entry['canonical_sha256']})
        print('compiled', dataset, 'calls', len(selected), 'helpers', len(helpers), flush=True)
    write(ROOT / 'recipes/suite.json', index)


if __name__ == '__main__':
    main()
