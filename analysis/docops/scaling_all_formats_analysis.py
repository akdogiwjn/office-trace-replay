"""Offline, append-only analysis of saved Word/PDF and Excel/PPT scaling profiles."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re

import operation_comparison as method
import scaling_hotspot_comparison as prior

ROOT = method.ROOT
CAMPAIGN = 'results/docops/scaling-word-pdf-performance-20261105T170501Z-3865aae0'
ROUND1_EXTRACT = 'results/docops/scaling-performance-recheck-20261105T124311Z/devkit-extract'
GROUPS = {'Word': ('003', '003-u100', '003-u500'),
          'PDF': ('037', '037-u5', '037-u20'),
          'Excel': ('014', '014-n1000', '014-n10000'),
          'PPT': ('021', '021-g5', '021-g10')}


def gather():
    first = prior.gather()
    bindings = dict(first['input_sha256'])

    def read(path, expected=None):
        digest = method.sha(ROOT/path)
        if expected is not None and digest != expected:
            raise ValueError('SHA256 mismatch: '+path)
        bindings[path] = digest
        return json.loads((ROOT/path).read_text())

    published = read(prior.PUBLISHED)
    references = published['baselines']
    identities = {method.key(f) for c in references.values() for f in c['functions']}
    original_enrichment = read(method.ENRICHMENT)
    campaign = read(CAMPAIGN+'/campaign.json')
    index = read(CAMPAIGN+'/campaign.sha256-index.json')

    def archived(path):
        relative = str(Path(path).relative_to(CAMPAIGN))
        return read(path, index['files'][relative]['sha256'])

    verification = archived(CAMPAIGN+'/verification.json')
    assert campaign['status'] == 'passed'
    assert campaign['image_id'] == published['docops_image_id']
    assert set(campaign['tasks']) == {'003-u100', '003-u500', '037-u5', '037-u20'}
    raw_cases, cases, rows = {}, {}, dict(first['cases'])
    for fmt, tasks in GROUPS.items():
        parent = tasks[0]
        record = original_enrichment['tasks'][parent]
        raw = read(record['out']+'/profile.json', record['profile_sha256'])
        raw_cases[parent] = raw
        cases[parent] = method.make_case(parent, fmt, raw, published['tasks'][parent]['metrics'])
        assert cases[parent]['functions'] == published['tasks'][parent]['functions']
        if parent not in rows:
            rows[parent] = dict(source=dict(profile=record['out']+'/profile.json',
                replay_loops=10, independent_captures=1, kind='original_docops_task'))
        for task in tasks[1:]:
            if fmt in ('Word', 'PDF'):
                enriched = verification['enrichment'][task]
                raw = archived(enriched['out']+'/profile.json')
                recovery = archived(enriched['out']+'/recovery-record.json')
                assert method.sha(ROOT/(enriched['out']+'/profile.json')) == enriched['profile_sha256']
                assert recovery['status'] == 'passed' and recovery['original_evidence_unchanged']
                assert recovery['function_qualification']['function_profile_eligible']
                capture = verification['captures'][task+'-perf']
                assert capture['status'] == 'passed'
                original_index = read(capture['archive']['index'], capture['archive']['sha256'])
                original = read(capture['raw']+'/perf/out/profile.json',
                                original_index['files']['profile.json']['sha256'])
                for k in ('roi_samples', 'roi_period', 'all_recorded_samples', 'all_recorded_period'):
                    assert raw[k] == original[k] == capture[k], (task, k)
                assert {f['dso']: f['period'] for f in raw['libraries']} == {
                    f['dso']: f['period'] for f in original['libraries']}
                extract_record = verification['topdown_extract'][task]
                extract = archived(extract_record['file'])
                assert method.sha(ROOT/extract_record['file']) == extract_record['sha256']
                recipe_path = 'docops/scaling/payload-word-pdf/tasks/'+task+'/recipe.json'
                recipe = read(recipe_path, verification['variants'][task]['recipe_sha256'])
                rows[task] = dict(source=dict(profile=enriched['out']+'/profile.json',
                    replay_loops=verification['variants'][task]['loops'], independent_captures=1,
                    kind='synthetic_scale_variant', scale=recipe['synthetic_variant']['scale'],
                    recipe=recipe_path, recovery=enriched['out']+'/recovery-record.json'),
                    capture_quality=raw['capture_quality'])
                metrics = extract_record['final_metrics']
            else:
                raw = read(rows[task]['source']['profile'], bindings[rows[task]['source']['profile']])
                extract = read(ROUND1_EXTRACT+'/'+task+'-devkit-full-extract.json')
                metric_map = {n['name']: n['value'] for n in extract['final']['hierarchy']}
                metrics = {k: extract['final']['header']['IPC'] if k == 'IPC' else metric_map[k]
                           for k in method.METRICS}
            metric_map = {n['path']: n['value'] for n in extract['final']['hierarchy']}
            for metric in method.BOUNDS:
                assert metrics[metric] == metric_map[metric]
            assert metrics['IPC'] == extract['final']['header']['IPC']
            rows[task]['topdown_evidence'] = dict(
                timesteps=len(extract['timesteps']),
                hierarchy_nodes=len(extract['final']['hierarchy']),
                not_counted_markers=extract['not_counted_markers'],
                exact_roi_event_filtering=False)
            raw_cases[task] = raw
            cases[task] = method.make_case(task, fmt, raw, metrics)

    for task, case in cases.items():
        raw = raw_cases[task]
        presence = method.function_presence(references, case)
        roles = prior.context_partition(raw, identities)
        for field, key in [('observed_period', 'observed_period'),
                           ('unseen_period', 'not_observed_period'),
                           ('unresolved_period', 'unresolved_period')]:
            assert sum(r[field] for r in roles) == presence['OPM+TLC'][key]
        unseen = method.hotspot_coverage(references, case)
        assert sum(g['period'] for g in unseen['unseen_by_tool']) == presence['OPM+TLC']['not_observed_period']
        png_contexts = [dict(r, share_roi=r['period']/raw['roi_period']) for r in raw['contexts']
                        if r['function'] == 'png_write_find_filter' and 'libpng' in r['dso']]
        rows[task].update(task=task, format=case['format'], roi_period=case['roi_period'],
            roi_samples=case['roi_samples'], metrics=case['metrics'], presence=presence,
            functions=case['functions'], hotspot_coverage=unseen,
            topk={str(k): method.weighted_topk_presence(references, case, k) for k in (10, 20)},
            script_contexts=roles, png_filter_contexts=png_contexts,
            libraries=case['libraries'], contexts=raw['contexts'], quality=raw['quality'])

    comparisons = {}
    for fmt, (parent, small, large) in GROUPS.items():
        for a, b in ((parent, small), (parent, large), (small, large)):
            delta = method.compare_pair(cases[a], cases[b])
            delta['observed_delta_pp'] = 100*(rows[b]['presence']['OPM+TLC']['observed_share_roi']-
                                              rows[a]['presence']['OPM+TLC']['observed_share_roi'])
            comparisons[a+' -> '+b] = delta
        for task in (small, large):
            for base in ('OPM', 'TLC'):
                comparisons[base+' -> '+task] = method.compare_pair(references[base], cases[task])
    return dict(schema='docops-all-format-scaling-analysis-v1', groups=GROUPS, cases=rows,
        references={k: dict(metrics=v['metrics'], roi_period=v['roi_period'],
                           function_count=len(v['functions'])) for k, v in references.items()},
        function_identity='DSO basename + exact full physical leaf symbol',
        denominator='Complete target workflow ROI cycles:u sampled period; not CPU seconds',
        source_scope='Original DocOps: one capture / ten loops. Scaling: one capture per mode; '
                     'Word u100 and PDF u5 three loops, others one. No independent scale repeats.',
        comparisons=comparisons, input_sha256=bindings)


def report(r):
    rows = r['cases']
    def pct(value):
        return '<0.01%' if 0 < value < .0001 else method.pct(value)
    table = method.table
    lines = ['# 规模扩大后，旧 OPM＋TLC 能覆盖多少热点函数？', '',
        '## 主要判断', '',
        '规模扩大后，Excel 014 和 PDF 037 的旧函数覆盖权重明显提高；Word 003 仅小幅提高，'
        'PPT 021 的图像处理缺口仍然突出。本批结果支持部分低覆盖与小输入下公共开销占比高有关，'
        '但它不能解释全部未覆盖热点。', '',
        '这里的“覆盖”指新任务中的叶函数，在旧 OPM＋TLC 的完整已解析函数清单中出现过。'
        '按库文件名＋完整物理函数名精确匹配，包含旧清单低频函数。'
        '百分比以新任务完整 workflow ROI 的 cycles:u 样本 period 为分母；它是采样周期权重，'
        '不是总 CPU 时间，也不表示旧例覆盖了全部业务操作。未解析部分单列。', '',
        '## 1. 四类任务的规模变化与覆盖结果', '']
    sizes = {'003':'原始任务', '003-u100':'100 单元／104 页', '003-u500':'500 单元／504 页',
             '037':'原始 5 页', '037-u5':'5 组／25 页', '037-u20':'20 组／100 页',
             '014':'原始任务', '014-n1000':'1000 行／81 页预览', '014-n10000':'10000 行／753 页预览',
             '021':'原始 8 页', '021-g5':'5 地区／40 页', '021-g10':'10 地区／80 页'}
    lines += [table(['类型／任务','规模','旧函数已见','旧清单未见','未解析','Top-10 占 ROI','Top-10 已见数'], [
        [fmt+' '+t,sizes[t],*[pct(rows[t]['presence']['OPM+TLC'][k]) for k in
            ('observed_share_roi','not_observed_share_roi','unresolved_share_roi')],
         pct(rows[t]['topk']['10']['selected_share_roi']),str(rows[t]['topk']['10']['observed_count'])+'/10']
        for fmt, tasks in GROUPS.items() for t in tasks]), '',
        'Word／PDF 的大档分别比原始任务提高约 2.9／13.9 个百分点；'
        'Word 从 100 到 500 单元反而下降约 3.0 个百分点，因此不是输入越大，覆盖率必然越高。', '',
        '## 2. Word：固定开销下降，但 PNG 滤波仍是主要缺口', '',
        '本任务先清理修订、评论、元数据和私人信息，再重建公开 DOCX，最后经 LibreOffice 转 PDF，'
        '由 pdftoppm 渲染 PNG。新增页数同时增加文档处理与预览生成工作。', '']
    def tool(t, name):
        return sum(x['share_roi'] for x in rows[t]['hotspot_coverage']['unseen_by_tool'] if x['tool']==name)
    def role(t, name):
        return sum(x['share_roi'] for x in rows[t]['script_contexts'] if x['script']==name)
    lines += [table(['任务','pdftoppm 权重','未见 PNG 函数','未见 Python 函数','未见 LO 公共组件函数'],
        [[t,pct(role(t,'pdftoppm')),pct(tool(t,'PNG')),pct(tool(t,'Python')),
          pct(tool(t,'LibreOffice·其他组件'))] for t in GROUPS['Word']]), '',
        '- Python 未匹配函数从 6.82% 降至 2.65%，LibreOffice 公共组件从 5.62% 降至约 1.14%。'
        '这一变化与公共开销被摊薄的解释一致。',
        '- 500 单元中 `png_write_find_filter` 单个函数约占 22.10%，记录的执行脚本为 pdftoppm。'
        '它为输出 PNG 选择行滤波方式，以利后续压缩；不是 Word 排版函数，也不是新出现了图片处理需求。'
        '旧 OPM 已有图片处理，但旧清单未观察到这个具体 libpng 函数。',
        '- 100→500 单元时，该滤波函数从约 20.45% 升至 22.10%，字符串搜索函数 '
        '`ucs2lib__two_way` 从约 0.90% 升至 2.43%，抵消了其他开销的下降。'
        '其中大档约 2.42% 记录于 validate_public_packet_variant.py，主要属于校验器的字符串搜索，'
        '不能自动归为 Word 编辑专属机制。',
        '- Word 参数化变体还采用了已核验的校验器优化（整段 XML 只转小写一次），'
        '父任务与变体间并非只改变输入体积；这部分变化不能全归因于规模。', '',
        '## 3. PDF：覆盖提高，主要剩余缺口集中到 PNG 滤波', '',
        '037 是 ReportLab 按业务数据绘制材料页、pypdf 写书签和元数据、pdftoppm 渲染 PNG。'
        '扩大的是实际绘制内容和页数，不是复制既有 PDF 页面；两档 seed PDF 字节相同不代表工作量相同。', '',
        table(['任务','pdftoppm 权重','未见 Python 函数','未见 PNG 函数'],
              [[t,pct(role(t,'pdftoppm')),pct(tool(t,'Python')),pct(tool(t,'PNG'))] for t in GROUPS['PDF']]), '',
        '- 未见 Python 函数从 16.17% 降至 0.77%，旧函数覆盖从 72.77% 提高到 86.72%。'
        '这一方向支持“小输入会让解释器启动、源码解析等公共工作显得更突出”的解释。',
        '- 大档仍有 13.28% 已解析函数未在旧清单出现，其中 `png_write_find_filter` 占 11.22%。'
        '剩余以少量字体、页面绘制和解释器函数为主；不能把整个差额称为全新 PDF 计算。',
        '- 大档 `longest_match` 占约 66.04%，主要由 pdftoppm 执行，体现预览 PNG 的压缩。'
        '它已在旧 OPM／TLC 中出现，是旧两例能够覆盖的重要基础热点。', '',
        '## 4. 与 Excel／PPT 规模实验合并看', '',
        '- Excel 014：旧函数覆盖达到 91.82%，主要是大量 PDF 页面渲染与 PNG 压缩权重上升；'
        '不能据此说工作簿编辑本身占了这些周期。大档未见函数约 7.12%，PNG 滤波约 4.12%。',
        '- PPT 021：大档仅覆盖 50.44%，仍有约 47.45% 已解析未匹配。'
        'ImageMagick 横纵向滤波、libjpeg 编码、LibreOffice 位图处理和 Poppler 子路径持续存在，'
        '规模扩大并没有消除这些具体实现差异。', '',
        '## 5. 大档缺口具体是什么、来自哪里？', '']
    for fmt, tasks in GROUPS.items():
        t=tasks[-1]
        missing=sorted(rows[t]['hotspot_coverage']['unseen_functions'],key=lambda f:-f['period'])[:5]
        lines += ['### '+fmt+'：'+t, '',table(['库','旧清单未见的函数','占完整 ROI'],
            [[f['library'],'`'+f['function']+'`',pct(f['share_roi'])] for f in missing]), '']
    lines += ['表中函数的完整脚本归属保存在 comparison.json 的 contexts 与 png_filter_contexts 中。'
              'Word／PDF／Excel 的主要 PNG 缺口有共同实现；PPT 的 ImageMagick、JPEG 和 LO 图像路径另成一组。', '',
        '## 6. Topdown：规模改变了瓶颈权重，函数重合不等于所有特征相同', '',
        '规模变体采用 DevKit Report-ALL 累计值，旧 OPM／TLC 列为既有五次结果的指标均值。'
        'IPC 为每周期指令数，四个顶层 Bound 为流水线分类百分比；'
        'Core／Memory 是 Backend 子项，Fetch Latency／Bandwidth 是 Frontend 子项，不能把九列相加。', '',
        table(['任务','IPC','Bad Spec','Frontend','Backend','Retiring','Core','Memory','Fetch Latency','Fetch BW'],
            [[t+'（五次均值）']+[f"{r['references'][t]['metrics'][k]:.2f}" for k in method.METRICS]
             for t in ('OPM','TLC')]+[[t]+[f"{rows[t]['metrics'][k]:.2f}" for k in method.METRICS]
             for tasks in GROUPS.values() for t in tasks]), '',
        table(['比较：小档→大档','ΔIPC','ΔBad Spec pp','ΔFrontend pp','ΔBackend pp','ΔRetiring pp',
               '四 Bound 半 L1 pp','余弦（辅助）'],
            [[small+' → '+large,f"{d['metrics_delta']['IPC']:+.2f}",
              *[f"{d['metrics_delta'][k]:+.2f}" for k in method.BOUNDS],
              f"{d['bound_total_variation_pp']:.2f}",f"{d['bound_cosine_auxiliary']:.6f}"]
             for tasks in GROUPS.values() for small,large in [tasks[1:]]
             for d in [r['comparisons'][small+' -> '+large]]]), '',
        '再直接与旧两例比较大档。下表的半 L1 是四个顶层分类绝对差之和的一半，'
        '单位为百分点；不与函数已见权重混为一项分数。', '',
        table(['旧例→大档','ΔIPC','ΔBad Spec pp','ΔFrontend pp','ΔBackend pp','ΔRetiring pp',
               '四 Bound 半 L1 pp','余弦（辅助）'],
            [[base+' → '+large,f"{d['metrics_delta']['IPC']:+.2f}",
              *[f"{d['metrics_delta'][k]:+.2f}" for k in method.BOUNDS],
              f"{d['bound_total_variation_pp']:.2f}",f"{d['bound_cosine_auxiliary']:.6f}"]
             for tasks in GROUPS.values() for large in [tasks[-1]] for base in ('OPM','TLC')
             for d in [r['comparisons'][base+' -> '+large]]]), '',
        '- Word 100／500 单元的 IPC 为 1.82／1.86，四顶层分类接近；'
        '相对父任务，前端占比下降、Retiring 上升、Memory Bound 降低，与执行权重发生明显变化一致。',
        '- PDF 25／100 页的 IPC 为 1.12／1.15，Backend 仍约 73%–74%。'
        '扩大后主要函数更集中，但与旧 OPM 的 Backend 仍相差约 +16.09 个百分点；'
        'Word 大档相对 OPM 的 Retiring 约高 10.55 个百分点。因此函数覆盖提高不等于微架构分配完全一致。',
        '- 余弦只作辅助；请结合四项各自的百分点变化、IPC 和函数工具归属。'
        '它很接近 1 时，也可能存在有意义的权重差异。', '',
        'DevKit 采 CPU 0–7 的采集包络，包括步间、轮间和尾部间隙，未做精确 PID／ROI 事件裁剪。'
        'perf 则按 workflow 区间并集过滤。两者分母不同，不将其数值直接相乘。'
        '深层 58 节点／事件虽已保存，含 `<not counted>` 的依赖未逐项证明有效，本次不将它们填零参加相似度。', '',
        '## 7. 对旧用例代表性的结论', '',
        '1. **旧 OPM＋TLC 覆盖了相当多的基础原生计算。** '
        '本批大档在 Excel／PDF／Word 中分别覆盖约 92%／87%／72% 的采样周期权重；'
        '原来部分低覆盖确实受到小输入下公共开销权重的影响。',
        '2. **不能把所有差额解释为小输入。** '
        'PNG 滤波在 Word／PDF 放大后仍明显，PPT 也持续存在大块图像处理实现差异。'
        '这些是旧函数清单的实测缺口。旧任务已有图片处理，缺的是这里观察到的具体库函数／子路径。',
        '3. **如果目标是补函数热点，优先补预览 PNG 滤波路径及 PPT 图像发布路径。** '
        '前者在这批 Word／PDF／Excel 中重复出现；后者涉及 ImageMagick 滤波、JPEG 编码、'
        'LibreOffice 位图处理等，不能只靠放大旧 OPM／TLC 推定覆盖。'
        '这不是本轮已经完成的最小集合优化，也不意味着两条路径覆盖了全部 Word／PPT 操作。', '',
        '## 8. 来源、重复次数与复核', '',
        '旧 OPM／TLC 使用既有五次重复的合并函数清单；原始 DocOps 父任务是一次采集内十轮回放。'
        '本批各规模各模式均只有一次独立采集，003-u100／037-u5 内含三轮，其余规模一轮。'
        '因此本轮能判断已观察到的权重变化，不能估算规模实验的独立重复波动。'
        '所有变体均标为合成规模实验，不是新增真实 Agent 轨迹。', '',
        '读取补符号后 profile，并验证与原始 profile 的样本数、period、DSO 权重守恒。'
        '已见／未见／未知三部分以及脚本上下文均守恒；源文件和派生结果摘要见 analysis-build.json。'
        'PPT／Excel 既有丢样及 Word lxml 少量未知保持原样，未知未计为未覆盖。', '',
        '本次仅离线分析，未修改原始证据、正式报告或 HTML，未重跑工作负载或采集。', '']
    return '\n'.join(lines)


def verify_result(result):
    """Recompute partitions directly from saved raw rows, apart from report helpers."""
    config=json.loads((ROOT/method.BASE_CONFIG).read_text())
    def valid(dso,symbol):
        return (dso!='[unknown]' and symbol not in ('[unknown]','[no-frame]') and
                not re.fullmatch(r'0x[0-9a-fA-F]+|[0-9a-fA-F]{12,}',symbol))
    identities=set()
    for name in ('opm-n10','tlc'):
        raw=json.loads((ROOT/config['profiles'][name]['path']).read_text())
        identities.update((Path(f['dso']).name,f['function']) for f in raw['functions']
                          if valid(f['dso'],f['function']))
    checks={}
    for task,row in result['cases'].items():
        raw=json.loads((ROOT/row['source']['profile']).read_text())
        amounts=Counter()
        for f in raw['functions']:
            bucket=('unresolved' if not valid(f['dso'],f['function']) else
                    'observed' if (Path(f['dso']).name,f['function']) in identities else 'not_observed')
            amounts[bucket]+=f['period']
        assert sum(amounts.values())==raw['roi_period']
        for key in ('observed','not_observed','unresolved'):
            assert amounts[key]==row['presence']['OPM+TLC'][key+'_period'],(task,key)
        assert sum(x['period'] for x in row['contexts'])==row['roi_period']
        checks[task]=dict(roi_period=raw['roi_period'],partition_independently_recomputed=True,
                         context_conservation=True)
    for pair,delta in result['comparisons'].items():
        a,b=pair.split(' -> ')
        am=(result['references'][a] if a in result['references'] else result['cases'][a])['metrics']
        bm=result['cases'][b]['metrics']
        expected=sum(abs(bm[k]-am[k]) for k in method.BOUNDS)/2
        assert math.isclose(expected,delta['bound_total_variation_pp'],abs_tol=1e-10)
    for path,digest in result['input_sha256'].items():
        assert method.sha(ROOT/path)==digest,path
    return dict(schema='scaling-analysis-checks-v1',case_count=len(checks),cases=checks,
        exact_identity_union_count=len(identities),comparison_count=len(result['comparisons']),
        bound_differences_independently_recomputed=True,input_files_rechecked=len(result['input_sha256']),
        formal_report_and_html_modified=False,workload_or_collector_run=False)


def save(output,result):
    checks=verify_result(result)
    method.write(output/'comparison.json',result)
    (output/'analysis.md').write_text(report(result))
    method.write(output/'verification.json',checks)
    method.write(output/'analysis-build.json',dict(
        source_sha256={str(Path(p).resolve().relative_to(ROOT)):method.sha(p)
                       for p in (__file__,method.__file__,prior.__file__)},
        input_sha256=result['input_sha256'],input_files_rechecked=len(result['input_sha256']),
        outputs={name:method.sha(output/name)
                 for name in ('comparison.json','analysis.md','verification.json')}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise SystemExit('Output directory exists; choose a new directory')
    result=gather()
    args.output.mkdir(parents=True)
    save(args.output,result)
    print(args.output/'analysis.md')


if __name__=='__main__':
    main()
