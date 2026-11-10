"""Offline function-presence comparison for saved 014/021 scale experiments.

No workload, collector, report publisher or HTML generator is invoked.
Matching reuses the published exact DSO-basename + physical-symbol rule.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import operation_comparison as method

ROOT = Path(__file__).resolve().parents[2]
PUBLISHED = 'analysis/docops/processed/task-operation-expansion-20261104/comparison.json'
CAPTURE = 'results/docops/scaling-performance-20261105T114539Z/campaign.json'
ENRICHED = 'results/docops/scaling-symbol-enrich-20261105T132725Z'
VARIANTS = ('014-n1000', '014-n10000', '021-g5', '021-g10')
ORDER = ('014', '014-n1000', '014-n10000', '021', '021-g5', '021-g10')


def context_partition(raw, identities):
    """Attribute exact observed/unseen leaf identities to recorded script roles."""
    counts = defaultdict(Counter)
    for row in raw['contexts']:
        resolved = method.resolved(row['function']) and row['dso'] != '[unknown]'
        key = (Path(row['dso']).name, row['function'])
        bucket = 'unresolved' if not resolved else 'observed' if key in identities else 'unseen'
        counts[row['script']][bucket] += row['period']
    assert sum(sum(v.values()) for v in counts.values()) == raw['roi_period']
    result = []
    for script, buckets in counts.items():
        total = sum(buckets.values())
        result.append(dict(script=script, period=total, share_roi=total/raw['roi_period'],
                           **{k+'_period': buckets[k] for k in ('observed', 'unseen', 'unresolved')},
                           observed_share_within_script=buckets['observed']/total))
    return sorted(result, key=lambda row: (-row['period'], row['script']))


def gather():
    bindings = {}

    def read(relative, expected=None):
        digest = method.sha(ROOT/relative)
        if expected is not None and digest != expected:
            raise ValueError('Input SHA256 mismatch: '+relative)
        bindings[relative] = digest
        return json.loads((ROOT/relative).read_text())

    published = read(PUBLISHED)
    baseline_config = read(method.BASE_CONFIG)
    references = {}
    for name, profile_key in (('OPM', 'opm-n10'), ('TLC', 'tlc')):
        source = baseline_config['profiles'][profile_key]
        raw = read(source['path'], source['sha256'])
        case = method.make_case(name, published['baselines'][name]['format'], raw, {})
        assert case['functions'] == published['baselines'][name]['functions']
        references[name] = case
    original_enrichment = read(method.ENRICHMENT)
    capture = read(CAPTURE)
    enrichment = read(ENRICHED+'/enrichment.json')
    assert capture['status'] == enrichment['status'] == 'passed'
    assert enrichment['image_id'] == published['docops_image_id']
    identities = {method.key(f) for case in references.values() for f in case['functions']}
    raw_cases, sources = {}, {}
    for task in ('014', '021'):
        record = original_enrichment['tasks'][task]
        profile_path = record['out']+'/profile.json'
        raw_cases[task] = read(profile_path, record['profile_sha256'])
        sources[task] = dict(profile=profile_path, replay_loops=10,
                             independent_captures=1, kind='original_docops_task')
    for task in VARIANTS:
        record = enrichment['tasks'][task]
        recovery_path = record['out']+'/recovery-record.json'
        recovery = read(recovery_path, record['record_sha256'])
        assert recovery['status'] == 'passed' and recovery['original_evidence_unchanged']
        assert recovery['function_qualification']['function_profile_eligible']
        profile_path = record['out']+'/profile.json'
        raw = read(profile_path, record['profile_sha256'])
        original_path = capture['tasks'][task]['perf']['raw']+'/perf/out/profile.json'
        index_path = str(Path(original_path).with_name('sha256-index.json'))
        original_index = read(index_path, recovery['original_sha256']['sha256-index.json'])
        original = read(original_path, original_index['files']['profile.json']['sha256'])
        for key in ('roi_samples', 'roi_period', 'all_recorded_samples', 'all_recorded_period'):
            assert raw[key] == original[key], (task, key)
        assert {f['dso']: f['period'] for f in raw['libraries']} == {
            f['dso']: f['period'] for f in original['libraries']}
        raw_cases[task] = raw
        recipe = read('docops/scaling/payload/tasks/'+task+'/recipe.json')
        sources[task] = dict(profile=profile_path, recovery=recovery_path,
                             replay_loops=1, independent_captures=1,
                             kind='synthetic_scale_variant', scale=recipe['synthetic_variant']['scale'])

    rows = {}
    for task in ORDER:
        raw = raw_cases[task]
        case = method.make_case(task, 'Excel' if task.startswith('014') else 'PPT', raw, {})
        presence = method.function_presence(references, case)
        coverage = method.hotspot_coverage(references, case)
        roles = context_partition(raw, identities)
        for role_field, presence_field in (
            ('observed_period', 'observed_period'),
            ('unseen_period', 'not_observed_period'),
            ('unresolved_period', 'unresolved_period')):
            assert sum(r[role_field] for r in roles) == presence['OPM+TLC'][presence_field]
        rows[task] = dict(task=task, source=sources[task], roi_period=case['roi_period'],
                          roi_samples=case['roi_samples'], presence=presence,
                          hotspot_coverage=coverage,
                          topk={str(k): method.weighted_topk_presence(references, case, k)
                                for k in (10, 20)},
                          top20=[dict(f, old_observed=method.key(f) in identities)
                                 for f in case['functions'][:20]],
                          script_contexts=roles, libraries=case['libraries'],
                          quality=raw['quality'], capture_quality=raw['capture_quality'])

    deltas = {}
    for a, b in (('014', '014-n1000'), ('014', '014-n10000'),
                 ('014-n1000', '014-n10000'), ('021', '021-g5'),
                 ('021', '021-g10'), ('021-g5', '021-g10')):
        ap, bp = (rows[t]['presence']['OPM+TLC'] for t in (a, b))
        deltas[a+' -> '+b] = {
            k+'_delta_pp': 100*(bp[k]-ap[k]) for k in
            ('observed_share_roi', 'not_observed_share_roi', 'unresolved_share_roi')}
    return dict(schema='docops-scaling-hotspot-presence-v1',
                method='Exact DSO basename and full physical leaf symbol; OPM+TLC '
                       'complete resolved identity union, including low-frequency functions. '
                       'All target ROI cycles:u sample period remains in the denominator.',
                reference_functions=len(identities), cases=rows, deltas=deltas,
                quality_scope='Each scale variant is one capture/one replay; original '
                              'DocOps tasks are one capture/ten replays. Variants also '
                              'parameterize scripts and increase PDF/rendered page counts. '
                              'Presence is measured identity overlap, not CPU time, '
                              'matching weights, causal isolation or all-operation coverage.',
                input_sha256=bindings)


def report(result):
    rows = result['cases']
    lines = ['# 扩大规模后的热点函数与旧 OPM＋TLC 覆盖权重', '',
             '## 主要结果', '',
             'Excel 014 放大后旧函数覆盖权重明显提高；PPT 021 放大后仅小幅提高，'
             '图像滤波、JPEG 编码和部分页面绘制函数仍是具体缺口。', '',
             '旧参考使用 OPM＋TLC 的完整已解析函数并集（含低频函数），'
             '按库文件名＋完整物理叶函数名精确匹配。以下百分比均以目标完整 workflow ROI '
             '的 cycles:u 样本 period 为分母，不是总 CPU 秒。未知部分不算未覆盖。', '',
             '| 任务 | 旧参考已见 | 已解析但旧参考未见 | 未解析 | Top-10 占完整 ROI | Top-10 已见函数数 |',
             '|---|---:|---:|---:|---:|---:|']
    for task in ORDER:
        r = rows[task]; p = r['presence']['OPM+TLC']; k = r['topk']['10']
        lines.append('| '+task+' | '+' | '.join(method.pct(p[v]) for v in
                     ('observed_share_roi', 'not_observed_share_roi', 'unresolved_share_roi'))+
                     f" | {method.pct(k['selected_share_roi'])} | {k['observed_count']}/10 |")
    lines += ['', '## Excel：改善明显，但主要来自渲染与 PNG 压缩的权重上升', '',
              '| 任务 | pdftoppm 占 ROI | longest_match 占 ROI | 旧参考未见 Python 函数合计 | 旧参考未见 PNG 函数合计 |',
              '|---|---:|---:|---:|---:|']
    for task in ORDER[:3]:
        r = rows[task]
        render = sum(x['share_roi'] for x in r['script_contexts'] if x['script'] == 'pdftoppm')
        longest = sum(x['share_roi'] for x in r['top20'] if x['library'].startswith('libz.')
                      and x['function'] == 'longest_match')
        tools = {x['tool']: x['share_roi'] for x in r['hotspot_coverage']['unseen_by_tool']}
        lines.append(f"| {task} | {method.pct(render)} | {method.pct(longest)} | "
                     f"{method.pct(tools.get('Python', 0))} | {method.pct(tools.get('PNG', 0))} |")
    lines += ['', '1000/10000 行分别生成 81/753 页 PDF 并渲染 PNG。'
              '大档中最长匹配压缩函数主要由 pdftoppm 执行；不能将整段压缩权重解释为 XLSX 保存。'
              '较低覆盖的 Python 与 LibreOffice 框架函数占比下降，方向与部分固定成本被摊薄一致；'
              '但父任务到变体也有参数化与合成输入变化，不能将全部差异归因于规模。', '',
              '## PPT：放大不能消除图片处理实现的缺口', '',
              '| 任务 | ImageMagick 未见函数 | LibreOffice VCL 图像未见函数 | JPEG 未见函数 | Poppler 未见函数 | Python 未见函数 |',
              '|---|---:|---:|---:|---:|---:|']
    for task in ORDER[3:]:
        tools = {x['tool']: x['share_roi'] for x in rows[task]['hotspot_coverage']['unseen_by_tool']}
        lines.append('| '+task+' | '+' | '.join(method.pct(tools.get(k, 0)) for k in
                     ('ImageMagick', 'LibreOffice·VCL', 'JPEG', 'Poppler', 'Python'))+' |')
    lines += ['', '这里是未匹配函数权重，不是整库权重。PPT 继续执行转 PDF、JPEG 渲染与联系表拼图。'
              'ImageMagick 的横纵向滤波、libjpeg 编码和 LibreOffice 位图缩放随页面处理持续发生，'
              '不是单靠小输入或初始化开销能解释的。旧例已有页面渲染和 Pillow 图像处理，'
              '但未观察到这些具体工具／函数，不能用操作名称相近代替函数匹配。', '',
              '## 大档主要未匹配函数', '']
    for task in ('014-n10000', '021-g10'):
        lines += ['', '### '+task, '', '| 库 | 函数 | 占完整 ROI |', '|---|---|---:|']
        for f in sorted(rows[task]['hotspot_coverage']['unseen_functions'],
                        key=lambda f: (-f['period'], f['library'], f['function']))[:8]:
            lines.append('| '+f['library']+' | `'+f['function'].replace('|', '&#124;')+
                         '` | '+method.pct(f['share_roi'])+' |')
    lines += ['', '## 判断', '',
              '1. Excel 014：大档旧函数覆盖达到约 92%，本次结果增强了旧两例对这一发布工作流基础计算的代表性证据。'
              '保留约 7% 的已解析未匹配函数，最明显的是 PNG 滤波函数。',
              '2. PPT 021：大档仍有约 47% 已解析周期无法在旧清单中匹配，'
              '约 50% 能匹配。规模扩大没有消除覆盖缺口，PPT 图形／图片发布任务仍有补充价值。',
              '3. 两类任务不能合并得出“放大规模后缺口都消失”的结论。'
              '本批主要用于观察函数权重变化；单次规模采集与原任务十轮批次不支持稳定性或单一因素因果结论。',
              '', '所有完整函数清单、未见函数分组、脚本上下文及来源哈希见 comparison.json。', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = gather()
    args.output.mkdir(parents=True, exist_ok=False)
    method.write(args.output/'comparison.json', result)
    (args.output/'analysis.md').write_text(report(result))
    method.write(args.output/'analysis-build.json', dict(
        script_sha256=method.sha(__file__),
        method_script_sha256=method.sha(Path(method.__file__)),
        input_sha256=result['input_sha256'],
        output_sha256={name: method.sha(args.output/name)
                       for name in ('comparison.json', 'analysis.md')}))
    print(args.output/'analysis.md')


if __name__ == '__main__':
    main()
