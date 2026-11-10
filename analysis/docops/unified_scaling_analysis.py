"""Read-only comparison of twelve parent tasks and twenty-four scale variants.

Creates a new analysis directory only. Never runs Docker, workloads, collectors,
report publishers or HTML generation. All period denominators remain intact.
"""
import argparse
from collections import Counter, defaultdict
import csv
from functools import lru_cache
import itertools
import json
import math
from pathlib import Path
import re

import operation_comparison as method
from scaling_hotspot_comparison import context_partition

ROOT = method.ROOT
ORIGINAL = 'analysis/docops/processed/task-operation-expansion-20261104/comparison.json'
CAMPAIGN = 'results/docops/scaling-reviewed-perf-20261107T054300Z-4359de4a'
PAYLOAD = 'docops/scaling/payload-all'
GROUPS = {
    '001': ('001-u100', '001-u500'), '003': ('003-u100', '003-u500'),
    '009': ('009-u100', '009-u500'), '013': ('013-v100', '013-v1000'),
    '014': ('014-n1000', '014-n10000'), '016': ('016-u100', '016-u500'),
    '021': ('021-g5', '021-g10'), '026': ('026-u5', '026-u10'),
    '029': ('029-u5', '029-u10'), '031': ('031-u5', '031-u20'),
    '037': ('037-u5', '037-u20'), 'pdfwf005': ('pdfwf005-u5', 'pdfwf005-u20')}
IMAGE_TOOLS = {'PNG', 'JPEG', 'ImageMagick', 'Poppler', 'LibreOffice·VCL', 'LibreOffice·OOXML'}
# Explicitly broader than the previous six image/page/object groups: Calc,
# Writer, font and XML paths may also matter, even if they are shared operations.
DOCUMENT_TOOLS = IMAGE_TOOLS | {'Pillow', 'pixman', 'cairo', 'lxml', 'XML 组件',
    'LibreOffice·Calc', 'LibreOffice·Writer', 'libfontconfig', 'libfreetype', 'libharfbuzz',
    'LibreOffice·文本布局', 'LibreOffice·文本样式', 'LibreOffice·矢量图形'}


def classify_function(row):
    """Refine identifiable document functions left in the former LO catch-all.

    Does not relabel generic C++/UNO functions as dedicated document algorithms.
    All exact identity/period matching is independent of this interpretation.
    """
    dso, name = row['library'], row['function']
    if dso == 'libsclo.so' and re.search(r'\bSc[A-Z]', name):
        return 'LibreOffice·Calc', '表格模型／重算路径', 'Calc 单元格、属性或公式管理；旧例已有表格与重算，具体子路径不同'
    if dso == 'libswlo.so' and re.search(r'\bSw[A-Za-z]', name):
        return 'LibreOffice·Writer', '文字文档模型／布局路径', 'Writer 文字／页面对象或属性路径；不等同于整段排版计时'
    if dso == 'libooxlo.so' and 'oox::ppt::' in name:
        return 'LibreOffice·OOXML', '文档对象／样式路径', '幻灯片导入、占位符与对象组织'
    if dso == 'libvcllo.so' and any(s in name for s in ('encode_mcu_', 'scaleUpPalette')):
        return 'LibreOffice·VCL', '图片编码／滤波', 'Office 图形层中的图像编码或缩放子路径'
    if dso == 'libvcllo.so' and 'LayoutArgs' in name:
        return 'LibreOffice·文本布局', '文本布局参数', 'Office 文本布局参数准备；不能据此把整个阶段归为排版'
    if dso == 'libbasegfxlo.so' and 'basegfx::' in name:
        return 'LibreOffice·矢量图形', '二维图形对象', 'Office 图形对象的几何范围与处理'
    if dso == 'libeditenglo.so' or (dso == 'libsvxcorelo.so' and 'TextEdit' in name):
        return 'LibreOffice·文本样式', '文本对象／属性样式', 'Office 文本对象、字重、颜色或编辑属性'
    return method.unseen_function_type(row)


def classified_hotspot_coverage(references, case):
    result = method.hotspot_coverage(references, case)
    tools, types, pairs = Counter(), Counter(), Counter()
    tc, kc = Counter(), Counter()
    for row in result['unseen_functions']:
        tool, kind, meaning = classify_function(row)
        row.update(tool=tool,type=kind,interpretation=meaning)
        tools[tool] += row['period']; types[kind] += row['period']; pairs[(tool,kind)] += row['period']
        tc[tool] += 1; kc[kind] += 1
    for key, counts, ncounts, label in [('unseen_by_tool',tools,tc,'tool'),('unseen_by_type',types,kc,'type')]:
        result[key] = [dict(**{label:k},period=v,share_roi=v/case['roi_period'],function_count=ncounts[k])
                       for k,v in counts.most_common()]
    result['unseen_by_tool_type'] = [dict(tool=k[0],type=k[1],period=v,share_roi=v/case['roi_period'])
                                    for k,v in pairs.most_common()]
    return result


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exact_cover(candidate_sets, required, limit=40):
    """Exact minimum cardinality cover using a rare-identity branch bound.

    Keeps equal/dominated candidates. The minimum is exact; stored alternatives
    are bounded by limit, with count=None if enumeration was truncated. Reports
    unattainable identities rather than calling an incomplete cover complete.
    """
    required = set(required)
    available = set().union(*candidate_sets.values()) if candidate_sets else set()
    missing = required - available
    goal = required & available
    if not goal:
        return dict(required_count=len(required), attainable_count=0,
                    missing=sorted(missing), minimum_count=0 if not missing else None,
                    minimum_for_attainable=0, solutions=[[]], solution_count=1,
                    complete=not missing)
    names = sorted(candidate_sets)
    identities = sorted(goal)
    masks = [sum(1 << i for i,f in enumerate(identities) if f in candidate_sets[n]) for n in names]
    covers = [[j for j,m in enumerate(masks) if m & (1 << i)] for i in range(len(identities))]

    @lru_cache(None)
    def solve(remaining):
        if not remaining:
            return 0, (0,), True
        indices = [i for i in range(len(identities)) if remaining & (1 << i)]
        pivot = min(indices, key=lambda i: len(covers[i]))
        best, solutions, complete = len(names)+1, set(), True
        for j in sorted(covers[pivot], key=lambda j: -(masks[j] & remaining).bit_count()):
            size, tails, all_tails = solve(remaining & ~masks[j])
            if size+1 < best:
                best, solutions, complete = size+1, set(), all_tails
            if size+1 == best:
                solutions.update(tail | (1 << j) for tail in tails)
                complete = complete and all_tails
                if len(solutions) > limit:
                    solutions = set(sorted(solutions)[:limit])
                    complete = False
        return best, tuple(sorted(solutions)), complete

    best, masks_chosen, complete_enumeration = solve((1 << len(identities))-1)
    ordered = sorted(tuple(n for j,n in enumerate(names) if mask & (1 << j)) for mask in masks_chosen)
    return dict(required_count=len(required), attainable_count=len(goal),
        missing=sorted(missing), minimum_count=best if not missing else None,
        minimum_for_attainable=best, solutions=[list(s) for s in ordered[:limit]],
        solution_count=len(ordered) if complete_enumeration else None,
        solution_enumeration_complete=complete_enumeration,
        stored_solution_limit=limit, complete=not missing)


class Reader:
    def __init__(self):
        self.bindings = {}

    def read(self, path, expected=None):
        path = str(path)
        full = ROOT / path
        require(full.resolve().is_relative_to(ROOT.resolve()), 'Path outside repository: '+path)
        digest = method.sha(full)
        require(expected is None or digest == expected, 'SHA256 mismatch: '+path)
        self.bindings[path] = digest
        return json.loads(full.read_text())

    def ref(self, row):
        return self.read(row['path'], row['sha256'])


def metrics_from_extract(extract):
    nodes = {n['path']: n['value'] for n in extract['final']['hierarchy']}
    paths = {'Core Bound': 'Backend Bound/Core Bound',
        'Memory Bound': 'Backend Bound/Memory Bound',
        'Fetch Latency Bound': 'Frontend Bound/Fetch Latency Bound',
        'Fetch Bandwidth Bound': 'Frontend Bound/Fetch Bandwidth Bound'}
    return {k: extract['final']['header']['IPC'] if k == 'IPC'
            else nodes[paths.get(k, k)] for k in method.METRICS}


def gather():
    read = Reader()
    build = read.read(str(Path(ORIGINAL).with_name('analysis-build.json')))
    original = read.read(ORIGINAL, build['output_sha256']['comparison.json'])
    baseline_config = read.read(method.BASE_CONFIG, build['input_bindings'][method.BASE_CONFIG])
    td_path = next(p for p in build['input_bindings'] if p.startswith('analysis/topdown/') and p.endswith('/similarity/comparison.json'))
    baseline_td = read.read(td_path, build['input_bindings'][td_path])
    references, raw_cases, sources = {}, {}, {}
    for name, key in [('OPM', 'opm-n10'), ('TLC', 'tlc')]:
        raw = read.ref(baseline_config['profiles'][key])
        case = method.make_case(name, original['baselines'][name]['format'], raw,
                                original['baselines'][name]['metrics'])
        require(case['functions'] == original['baselines'][name]['functions'], 'Baseline differs')
        for k in method.METRICS:
            require(case['metrics'][k] == baseline_td['statistics'][name.lower()]['statistics'][k]['mean'],
                    'Baseline Topdown mean differs: '+name+' '+k)
        references[name] = case
    old = {method.key(f) for c in references.values() for f in c['functions']}
    enrichment = read.read(method.ENRICHMENT, build['input_bindings'][method.ENRICHMENT])
    for task in GROUPS:
        path = enrichment['tasks'][task]['out']+'/profile.json'
        raw = read.read(path, enrichment['tasks'][task]['profile_sha256'])
        raw_cases[task] = raw
        saved = original['tasks'][task]
        require(method.functions(raw) == saved['functions'], 'Original functions differ: '+task)
        td = read.read(saved['evidence']['topdown_record'],
                       build['input_bindings'][saved['evidence']['topdown_record']])
        require(td['metrics'] == saved['metrics'], 'Original Topdown differs: '+task)
        sources[task] = dict(profile=path, kind='original', loops=saved['workload_loops'],
            image_id=original['docops_image_id'], topdown_record=saved['evidence']['topdown_record'],
            metrics=saved['metrics'], points=saved['interval_points'],
            roi_seconds=td['roi_seconds'], topdown_envelope_seconds=saved['topdown_envelope_seconds'],
            idle_pct=saved['idle_pct'], capture_quality=raw['capture_quality'])

    campaign = read.read(CAMPAIGN+'/campaign.json')
    index = read.read(CAMPAIGN+'/campaign.sha256-index.json')

    def archived(path):
        key = str(Path(path).relative_to(CAMPAIGN))
        return read.read(path, index['files'][key]['sha256'])

    verification = archived(CAMPAIGN+'/verification.json')
    inventory = archived(CAMPAIGN+'/dataset-inventory.json')
    historical = archived(CAMPAIGN+'/historical-reuse.json')
    require(campaign['status'] == inventory['status'] == historical['status'] == 'passed', 'Campaign failed')
    require(campaign['preflight']['frozen_before'] == campaign['frozen_after'], 'Frozen materials changed')
    require(set(inventory['tasks']) == {t for pair in GROUPS.values() for t in pair}, 'Wrong inventory')
    for task, info in inventory['tasks'].items():
        require(info['status'] == 'passed' and info['function_qualification']['function_profile_eligible'],
                'Unqualified profile: '+task)
        raw = read.ref(info['native_profile'])
        extract = read.ref(info['topdown_full_extract'])
        metrics = metrics_from_extract(extract)
        recipe_path = PAYLOAD+'/tasks/'+task+'/recipe.json'
        expected = info['recipe']['sha256'] if info['origin'] == 'historical_reuse' else info['binding']['recipe_sha256']
        recipe = read.read(recipe_path, expected)
        variant = recipe['synthetic_variant']
        code_review_material = []
        if task.startswith('013-'):
            for entry in recipe['files']:
                if entry['kind']=='script' and entry['payload'].endswith('/build_bid_evaluation_variant.py'):
                    path = PAYLOAD+'/'+entry['payload']
                    actual = method.sha(ROOT/path)
                    require(actual == entry['sha256'], 'Frozen builder changed: '+task)
                    read.bindings[path] = actual
                    code_review_material.append(path)
        cols = {}
        for mode in ('perf', 'topdown'):
            capture = info['captures'][mode]
            ref = capture.get('archive_index', capture.get('archive'))
            archive_index = read.ref(ref) if 'path' in ref else read.read(ref['index'], ref['sha256'])
            path = capture['raw']+'/'+mode+'/out/collection.json'
            col = read.read(path, archive_index['files']['collection.json']['sha256'])
            require(col['status'] == 'passed' and col['counts'] == dict(requested=info['loops'],
                    completed=info['loops'], successes=info['loops'], failures=0), 'Capture failed: '+task)
            cols[mode] = col
            if mode == 'perf':
                before = read.read(capture['raw']+'/perf/out/profile.json',
                                   archive_index['files']['profile.json']['sha256'])
                for key in ('roi_period', 'roi_samples', 'all_recorded_period', 'all_recorded_samples'):
                    require(raw[key] == before[key], 'Recovery counter changed: '+task+' '+key)
                require({r['dso']: r['period'] for r in raw['libraries']} ==
                        {r['dso']: r['period'] for r in before['libraries']}, 'Recovery DSO changed: '+task)
        require(metrics == cols['topdown']['metrics'], 'Topdown metric mismatch: '+task)
        if info['origin'] == 'historical_reuse':
            recovery = read.ref(info['recovery_record'])
        else:
            r = verification['enrichment'][task]
            recovery = read.read(r['out']+'/recovery-record.json', r['record_sha256'])
        require(recovery['status'] == 'passed' and recovery['original_evidence_unchanged'], 'Recovery failed')
        sources[task] = dict(profile=info['native_profile']['path'], kind=info['origin'],
            loops=info['loops'], image_id=info['image_id'], recipe=recipe_path,
            scale=variant['scale'], scale_metadata=variant.get('scale_metadata', {}),
            modified_steps=variant.get('modified_steps', []),
            code_review_material=code_review_material,
            topdown_extract=info['topdown_full_extract']['path'],
            topdown_hierarchy=extract['final']['hierarchy'],
            not_counted_markers=extract['not_counted_markers'],
            metrics=metrics, points=len(extract['timesteps']),
            roi_seconds=cols['perf']['roi_seconds'],
            topdown_roi_seconds=cols['topdown']['roi_seconds'],
            topdown_envelope_seconds=cols['topdown']['profiler_envelope_seconds'],
            idle_pct=cols['topdown']['cpu_window']['idle_pct'],
            capture_quality=raw['capture_quality'], quality=raw['quality'])
        raw_cases[task] = raw

    cases = {}
    for parent, pair in GROUPS.items():
        for task in (parent, *pair):
            raw, source = raw_cases[task], sources[task]
            case = method.make_case(task, original['tasks'][parent]['format'], raw, source['metrics'])
            case.update(parent=parent, source=source, contexts=raw['contexts'],
                presence=method.function_presence(references, case),
                hotspot_coverage=classified_hotspot_coverage(references, case),
                script_contexts=context_partition(raw, old),
                topk={str(k): method.weighted_topk_presence(references, case, k) for k in (10, 20)})
            # Full (not truncated) tool -> script context partition for attribution.
            counts = Counter()
            for r in raw['contexts']:
                if r['dso'] != '[unknown]' and method.resolved(r['function']) and (Path(r['dso']).name,r['function']) not in old:
                    tool = classify_function(dict(library=Path(r['dso']).name,function=r['function']))[0]
                    counts[(tool,r['script'])] += r['period']
            case['unseen_contexts'] = [dict(tool=k[0],script=k[1],period=v,share_roi=v/case['roi_period'])
                                      for k,v in counts.most_common()]
            cases[task] = case
    comparisons = {}
    for parent, (small, large) in GROUPS.items():
        for a,b in ((parent,small),(parent,large),(small,large),('OPM',large),('TLC',large)):
            d = method.compare_pair(references[a] if a in references else cases[a], cases[b])
            if a in cases:
                d['observed_delta_pp'] = 100*(cases[b]['presence']['OPM+TLC']['observed_share_roi']-
                                            cases[a]['presence']['OPM+TLC']['observed_share_roi'])
            comparisons[a+' -> '+b] = d
    return dict(schema='docops-unified-scale-analysis-v1',groups=GROUPS,
        references=references,cases=cases,comparisons=comparisons,input_sha256=read.bindings,
        function_identity='DSO basename + exact full physical leaf symbol; no clone/fuzzy merging',
        denominator='Complete target workflow ROI cycles:u sampled period, not CPU time',
        topdown_scope='DevKit CPU 0-7 envelope Report-ALL; not exact PID or ROI counter filtering',
        source_scope='Baselines: five independent captures; parents: one capture/10 loops; '
            'scales: one capture/mode, 003-u100 and 037-u5 have three loops, others one. '
            'Recipe parameterization and registered processing/validation changes accompany scale; '
            'not a pure input-size causal experiment.',
        workload_or_collector_run=False,formal_report_or_html_modified=False)


def selections(result):
    cases = result['cases']
    old = {method.key(f) for c in result['references'].values() for f in c['functions']}
    candidates = {t: {method.key(f) for f in c['functions']}-old for t,c in cases.items()}
    catalog = {}
    for task, case in cases.items():
        for f in case['functions']:
            if method.key(f) in old:
                continue
            tool, kind, meaning = classify_function(f)
            row = catalog.setdefault(method.key(f), dict(library=f['library'],function=f['function'],
                tool=tool,type=kind,meaning=meaning,occurrences=[]))
            row['occurrences'].append(dict(task=task,share_roi=f['share_roi'],period=f['period']))
    answers = {}
    for threshold in (.001, .005, .01):
        hot = {k for k,r in catalog.items() if max(x['share_roi'] for x in r['occurrences']) >= threshold}
        scopes = {'previous_six_tools': {k for k in hot if catalog[k]['tool'] in IMAGE_TOOLS},
                  'core_plus_calc': {k for k in hot if catalog[k]['tool'] in IMAGE_TOOLS | {'LibreOffice·Calc'}},
                  'document_tools': {k for k in hot if catalog[k]['tool'] in DOCUMENT_TOOLS},
                  'all_resolved_tools': hot}
        for name,required in scopes.items():
            # All-tools at the lowest threshold is retained as a catalogue only:
            # it mainly expands low-frequency framework identities.
            if name == 'all_resolved_tools' and threshold == .001:
                continue
            print(f'Selecting {name} >= {threshold:g}: {len(required)} identities', flush=True)
            choices = {'original_12': {t:candidates[t] for t in GROUPS},
                       'all_36': candidates,
                       'scaled_24': {t:candidates[t] for t in cases if t not in GROUPS}}
            answers[f'{name}@{threshold:g}'] = dict(threshold=threshold,
                required_functions=[catalog[k] for k in sorted(required)],
                family_union_cover=exact_cover({p:set().union(*(candidates[t] for t,c in cases.items()
                    if c['parent']==p)) for p in GROUPS}, required),
                candidates={scope:exact_cover(pool,required) for scope,pool in choices.items()})
    primary = answers['core_plus_calc@0.005']['candidates']['all_36']
    selected = primary['solutions'][0]
    evaluate = lambda choice: evaluate_selection(cases, old, candidates, choice)
    return dict(schema='docops-unified-scale-selection-v1', goals=answers,
        operation_tools=sorted(DOCUMENT_TOOLS),previous_tools=sorted(IMAGE_TOOLS),
        primary_goal='core_plus_calc@0.005', selected=selected,
        classification='Audited LO-specific symbol/module refinements; generic UNO/C++ retained separately. '
            'Exact identity matching unchanged. See classify_function().',
        evaluation=evaluate(selected),
        ablations={t:evaluate([s for s in selected if s != t]) for t in selected},
        scope='Exact minimum over sampled concrete profiles for declared tool/function/threshold goal. '
              'Any resolved occurrence in a candidate counts as present; it need not be a candidate hotspot. '
              'Selected profiles match themselves; same-family targets are marked. '
              'Not a guarantee of operation coverage or repeated-run stability.',
        function_catalog=list(catalog.values()))


def evaluate_selection(cases, old, candidates, selected):
    augmented = old | set().union(*(candidates[t] for t in selected))
    families = {cases[t]['parent'] for t in selected}
    rows = {}
    for t,c in cases.items():
        seen = sum(f['period'] for f in c['functions'] if method.key(f) in augmented)
        unknown = c['roi_period'] - sum(f['period'] for f in c['functions'])
        unseen = c['roi_period'] - seen - unknown
        rows[t] = dict(observed_share_roi=seen/c['roi_period'],
            not_observed_share_roi=unseen/c['roi_period'],unresolved_share_roi=unknown/c['roi_period'],
            selected_as_reference=t in selected,same_parent_as_selected=c['parent'] in families)
        left = [f for f in c['functions'] if method.key(f) not in augmented]
        tools = Counter()
        for f in left:
            tools[classify_function(f)[0]] += f['period']
        rows[t]['remaining_by_tool'] = [dict(tool=k,period=v,share_roi=v/c['roi_period']) for k,v in tools.most_common()]
        rows[t]['remaining_hot_functions'] = [dict(f,tool=classify_function(f)[0]) for f in left
                                             if f.get('share_roi',f['period']/c['roi_period'])>=.005]
    return dict(selected=selected,targets=rows)


def verify(result, selection):
    """Independent raw partition and exhaustive checks for the chosen minimum."""
    refs = json.loads((ROOT/method.BASE_CONFIG).read_text())
    valid = lambda f: f['dso'] != '[unknown]' and f['function'] not in ('[unknown]','[no-frame]') and not re.fullmatch(r'0x[0-9a-fA-F]+|[0-9a-fA-F]{12,}',f['function'])
    old = set()
    for k in ('opm-n10','tlc'):
        raw = json.loads((ROOT/refs['profiles'][k]['path']).read_text())
        old.update((Path(f['dso']).name,f['function']) for f in raw['functions'] if valid(f))
    checks = {}
    for t,c in result['cases'].items():
        raw = json.loads((ROOT/c['source']['profile']).read_text())
        amounts = Counter()
        for f in raw['functions']:
            identity = Path(f['dso']).name, f['function']
            bucket = 'unresolved' if not valid(f) else 'observed' if identity in old else 'not_observed'
            amounts[bucket] += f['period']
        require(sum(amounts.values()) == c['roi_period'], 'Raw partition total mismatch: '+t)
        for k in ('observed','not_observed','unresolved'):
            require(amounts[k] == c['presence']['OPM+TLC'][k+'_period'], 'Partition mismatch: '+t+' '+k)
        require(sum(r['period'] for r in c['contexts']) == c['roi_period'], 'Context total mismatch')
        for tool in c['hotspot_coverage']['unseen_by_tool']:
            require(tool['period'] == sum(r['period'] for r in c['unseen_contexts'] if r['tool']==tool['tool']),
                    'Tool context mismatch: '+t)
        checks[t] = dict(partition_passed=True,context_conservation=True)
    for name,d in result['comparisons'].items():
        a,b = name.split(' -> ')
        am = (result['references'] if a in result['references'] else result['cases'])[a]['metrics']
        bm = result['cases'][b]['metrics']
        require(math.isclose(sum(abs(am[k]-bm[k]) for k in method.BOUNDS)/2,
                            d['bound_total_variation_pp'],abs_tol=1e-10), 'Topdown delta mismatch')
    goal = selection['goals'][selection['primary_goal']]
    required = {(f['library'],f['function']) for f in goal['required_functions']}
    candidates = {t:{(f['library'],f['function']) for f in c['functions']} for t,c in result['cases'].items()}
    n = goal['candidates']['all_36']['minimum_count']
    # A second algorithm enumerates every smaller candidate subset for the
    # primary recommendation, proving the branch search's lower bound.
    smaller_checked = 0
    identities = sorted(required)
    masks = [sum(1 << i for i,f in enumerate(identities) if f in pool) for pool in candidates.values()]
    target_mask = (1 << len(identities))-1
    for size in range(n):
        for choice in itertools.combinations(masks,size):
            smaller_checked += 1
            covered = 0
            for mask in choice:
                covered |= mask
            require(covered != target_mask, 'Nonminimal choice')
    for choice in goal['candidates']['all_36']['solutions']:
        require(required <= set().union(*(candidates[t] for t in choice)), 'Incomplete recommendation')
    for path,digest in result['input_sha256'].items():
        require(method.sha(ROOT/path)==digest, 'Input modified during analysis: '+path)
    return dict(status='passed',case_count=len(checks),cases=checks,
        baseline_function_count=len(old),comparison_count=len(result['comparisons']),
        primary_minimum_independently_verified=True,smaller_subsets_checked=smaller_checked,
        input_files_rechecked=len(result['input_sha256']),formal_report_or_html_modified=False,
        workload_or_collector_run=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Choose a new output directory')
    result = gather()
    selection = selections(result)
    print('Primary exact minimum: '+str(selection['selected']), flush=True)
    verification = verify(result,selection)
    args.output.mkdir(parents=True)
    method.write(args.output/'comparison.json',result)
    method.write(args.output/'selection.json',selection)
    method.write(args.output/'verification.json',verification)
    from unified_scaling_report import save
    save(args.output,result,selection)
    print(json.dumps(dict(output=str(args.output),verification=verification['status'],
                          selected=selection['selected']),ensure_ascii=False))


if __name__ == '__main__':
    main()
