"""Read-only provenance links for the eight previously qualified scale variants.

No capture, export, analysis, or historical-evidence rewrite is performed here.
The saved analysis build supplies hashes for the selected historical artifacts;
raw capture indices remain referenced with their original identities.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HISTORICAL = ('014-n1000', '014-n10000', '021-g5', '021-g10',
              '003-u100', '003-u500', '037-u5', '037-u20')
ANALYSIS = Path('analysis/docops/processed/all-format-scaling-20261106')
ROUND1 = Path('results/docops/scaling-performance-20261105T114539Z')
ROUND2 = Path('results/docops/scaling-word-pdf-performance-20261105T170501Z-3865aae0')
ROUND1_EXTRACT = Path('results/docops/scaling-performance-recheck-20261105T124311Z/devkit-extract')
REVIEWED_BUILD = Path('docops/docker/records/20261106T074728Z-scaled-6d84f409')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def file_ref(root, path, expected=None):
    path = (root / path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('evidence path escapes repository')
    actual = digest(path)
    if expected is not None and actual != expected:
        raise ValueError('historical evidence hash mismatch: ' + str(path))
    return {'path': str(path.relative_to(root.resolve())), 'sha256': actual,
            'bytes': path.stat().st_size}


def task_tree(path):
    return {str(p.relative_to(path)): (p.stat().st_size, digest(p))
            for p in sorted(path.rglob('*')) if p.is_file()}


def historical_reuse(root, payload, reviewed_image_id):
    """Verify task identity and selected evidence hashes; preserve old image IDs.

    This rechecks the analysis inputs, collections, profile/ROI conservation and
    all task bytes. It does NOT claim a fresh full read of multi-GB raw archives:
    their immutable indices and prior complete archive checks are linked.
    """
    root, payload = Path(root).resolve(), Path(payload).resolve()
    build = load(root / ANALYSIS / 'analysis-build.json')
    analysis_ref = file_ref(root, ANALYSIS / 'comparison.json', build['outputs']['comparison.json'])
    saved = load(root / analysis_ref['path'])
    bound = saved['input_sha256']

    def bound_json(path):
        key = str(path)
        if key not in bound:
            raise ValueError('historical analysis has no hash binding for ' + key)
        ref = file_ref(root, key, bound[key])
        return load(root / key), ref

    first, first_ref = bound_json(ROUND1 / 'campaign.json')
    second, second_ref = bound_json(ROUND2 / 'campaign.json')
    v2, v2_ref = bound_json(ROUND2 / 'verification.json')
    image_build = load(root / REVIEWED_BUILD / 'closeout.json')
    if image_build['status'] != 'passed' or image_build['image_id'] != reviewed_image_id:
        raise ValueError('reviewed image does not match its build record')
    result = {}
    for task in HISTORICAL:
        early = task.startswith(('014-', '021-'))
        source_payload = Path('docops/scaling/payload' if early else 'docops/scaling/payload-word-pdf')
        recipe_path = source_payload / 'tasks' / task / 'recipe.json'
        recipe, recipe_ref = bound_json(recipe_path)
        if task_tree(root / source_payload / 'tasks' / task) != task_tree(payload / 'tasks' / task):
            raise ValueError('historical task differs from installed-payload source: ' + task)
        sv = recipe['synthetic_variant']
        expected_ref = file_ref(root, source_payload / 'tasks' / task / 'seed/root/tmp/docs/expected.json',
                                sv['expected_sha256'])
        # Input bytes and every frozen script are also covered by identical task trees.
        if not any(f['sha256'] == sv['input_sha256'] for f in recipe['files']):
            raise ValueError('historical input missing from recipe binding: ' + task)
        case = saved['cases'][task]
        profile_path = Path(case['source']['profile'])
        profile, profile_ref = bound_json(profile_path)
        recovery_path = Path(case['source']['recovery'])
        recovery, recovery_ref = bound_json(recovery_path)
        if (recovery.get('status') != 'passed' or not recovery.get('original_evidence_unchanged')
                or not recovery['function_qualification']['function_profile_eligible']):
            raise ValueError('historical function profile is not qualified: ' + task)
        campaign = first if early else second
        original_image_id = campaign.get('image_id') or campaign.get('preflight', {}).get('image_id')
        if campaign['status'] != 'passed' or original_image_id != image_build['base_id']:
            raise ValueError('historical runtime is not the reviewed image base: ' + task)
        captures = {}
        for mode in ('perf', 'topdown'):
            row = campaign['tasks'][task][mode]
            raw = Path(row['raw'])
            if row['status'] != 'passed':
                raise ValueError('historical capture failed: ' + task + ' ' + mode)
            index_path = raw / mode / 'out/sha256-index.json'
            index_ref = file_ref(root, index_path)
            index = load(root / index_path)['files']
            if not early:
                old_capture = v2['captures'][task + '-' + mode]
                if index_ref['sha256'] != old_capture['archive']['sha256']:
                    raise ValueError('historical capture index changed: ' + task + ' ' + mode)
            elif mode == 'perf':
                # The recovery record's immutable source index binds the native archive.
                source = recovery.get('original_archive')
                # Older recovery schemas keep this binding in the enrichment manifest.
                if source and source.get('sha256') and source['sha256'] != index_ref['sha256']:
                    raise ValueError('historical native index changed: ' + task)
            collection_path = raw / mode / 'out/collection.json'
            collection_ref = file_ref(root, collection_path, index['collection.json']['sha256'])
            collection = load(root / collection_path)
            if early and row.get('modes', {}).get('collection_sha256') != collection_ref['sha256']:
                raise ValueError('historical collection differs from campaign: ' + task + ' ' + mode)
            loops = case['source']['replay_loops']
            counts = dict(requested=loops, completed=loops, successes=loops, failures=0)
            if collection['status'] != 'passed' or collection['counts'] != counts:
                raise ValueError('historical counts/status mismatch: ' + task + ' ' + mode)
            captures[mode] = {'collection': collection_ref, 'archive_index': index_ref,
                              'raw': str(raw), 'loops': loops, 'image_id': original_image_id}
        original_path = Path(captures['perf']['raw']) / 'perf/out/profile.json'
        index = load(root / captures['perf']['archive_index']['path'])['files']
        file_ref(root, original_path, index['profile.json']['sha256'])
        original = load(root / original_path)
        for key in ('roi_period', 'roi_samples', 'all_recorded_period', 'all_recorded_samples'):
            if profile[key] != original[key]:
                raise ValueError('historical enrichment conservation failure: ' + task + ' ' + key)
        extract_path = ROUND1_EXTRACT / (task + '-devkit-full-extract.json') if early else Path(v2['topdown_extract'][task]['file'])
        _, extract_ref = bound_json(extract_path)
        result[task] = {
            'origin': 'historical_reuse', 'status': 'passed',
            'image_id': original_image_id, 'loops': case['source']['replay_loops'],
            'recipe': recipe_ref, 'input_sha256': sv['input_sha256'],
            'expected': expected_ref, 'captures': captures,
            'native_profile': profile_ref, 'recovery_record': recovery_ref,
            'topdown_full_extract': extract_ref,
            'function_qualification': recovery['function_qualification'],
            'runtime_compatibility': 'Original image is the exact reviewed-image base; '
                                     'toolchain inherited and all task files byte-identical. '
                                     'Original image identity and loop counts are retained.',
        }
    return {'schema': 'docops-eight-historical-links-v1', 'status': 'passed',
            'analysis': analysis_ref, 'source_campaigns': [first_ref, second_ref],
            'verification': v2_ref, 'reviewed_build': file_ref(root, REVIEWED_BUILD / 'closeout.json'),
            'verification_scope': 'Task bytes and selected analysis/collection artifacts rehashed; '
                                  'raw capture archives linked via their original indices and prior qualification.',
            'tasks': result}


def dataset_inventory(root, state, verification, historical):
    tasks = dict(historical['tasks'])
    if historical['status'] != 'passed':
        raise ValueError('historical reuse not qualified')
    for task in state['variants']:
        enrich = verification['enrichment'][task]
        profile_path = Path(enrich['out']) / 'profile.json'
        tasks[task] = {
            'origin': 'new_capture', 'status': 'passed', 'image_id': state['image_id'],
            'loops': state['loops_per_variant'][task],
            'binding': verification['variants'][task],
            'captures': {m: {'raw': verification['captures'][task + '-' + m]['raw'],
                             'archive': verification['captures'][task + '-' + m]['archive']}
                         for m in ('perf', 'topdown')},
            'native_profile': file_ref(root, profile_path),
            'topdown_full_extract': file_ref(root, verification['topdown_extract'][task]['file']),
            'function_qualification': enrich['function_qualification'],
        }
    if len(tasks) != 24 or set(state['variants']) & set(historical['tasks']):
        raise ValueError('inventory must contain 16 new and 8 distinct historical tasks')
    return {'schema': 'docops-24-scale-dataset-inventory-v1', 'status': 'passed',
            'new_tasks': len(state['variants']), 'historical_tasks': len(historical['tasks']),
            'new_captures': 2 * len(state['variants']), 'tasks': tasks,
            'note': 'Collection/provenance inventory only; no coverage or similarity calculation.'}
