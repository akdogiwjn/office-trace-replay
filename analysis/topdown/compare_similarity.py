"""Offline comparison of frozen DevKit metrics and separately sampled hotspots."""
import argparse
import csv
import importlib.util
import json
import math
import os
import statistics
from pathlib import Path
import sys

from pilot import ROOT, HERE, sha, write
from campaign import aggregate
from summarize import METRICS
import report_methods

BOUNDS=('Bad Speculation','Frontend Bound','Backend Bound','Retiring')
VECTOR=(*METRICS,'idle_pct')
PAIRS=(('opm','irs_w4'),('opm','sba1919'),('tlc','hr_metro'),('tlc','egrid'),('tlc','industry_productivity'))


def hotspot_tools():
    path=ROOT/'analysis/hotspots/compare.py'
    spec=importlib.util.spec_from_file_location('similarity_hotspot_tools',path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module


def checked(binding):
    path=ROOT/binding['path']
    if sha(path)!=binding['sha256']:raise ValueError('input hash mismatch: '+str(path))
    return json.loads(path.read_text())


def vector_distance(a,b):
    if len(a)!=len(b) or not a or not all(math.isfinite(x) for x in (*a,*b)):
        raise ValueError('invalid vectors')
    return math.dist(a,b)


def cosine(a,b):
    vector_distance(a,b)
    norm=math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
    if not norm:raise ValueError('zero vector is not evidence of similarity')
    return max(-1.0,min(1.0,sum(x*y for x,y in zip(a,b))/norm))


def top10_set(profile,tools):
    rows=tools.top_functions(profile,10)
    result={(r['library'],r['function']) for r in rows}
    if len(result)!=10:raise ValueError('ten distinct resolved hotspot functions required')
    return result


def pair_result(reference,target,stats,profiles,tools):
    def values(ds,keys):return [stats[ds]['statistics'][k]['mean'] for k in keys]
    a=top10_set(profiles[reference],tools);b=top10_set(profiles[target],tools)
    common=a&b;union=a|b
    return dict(reference=reference,target=target,
        bound_cosine=cosine(values(reference,BOUNDS),values(target,BOUNDS)),
        raw_euclid_auxiliary=vector_distance(values(reference,VECTOR),values(target,VECTOR)),
        hotspot_jaccard=len(common)/len(union),common_top10_count=len(common),union_top10_count=len(union),
        reference_top10=[dict(library=k[0],function=k[1]) for k in sorted(a)],
        target_top10=[dict(library=k[0],function=k[1]) for k in sorted(b)],
        common_top10=[dict(library=k[0],function=k[1]) for k in sorted(common)],
        missing_reference_top10=[dict(library=k[0],function=k[1]) for k in sorted(a-b)],
        additional_target_top10=[dict(library=k[0],function=k[1]) for k in sorted(b-a)],
        metric_deltas_target_minus_reference={k:stats[target]['statistics'][k]['mean']-
            stats[reference]['statistics'][k]['mean'] for k in VECTOR})


def section(result):
    lines=['## 六、Topdown 特征与热点集合相似度','',
        '在已有原生热点证据基础上，对七例另行采集 DevKit Topdown 指标。PDF 每例独立采集五次，每次执行一轮、处理十份；'+
        ('XLSX 每例也独立采集五次。Topdown 特征取五次逐指标算术均值；热点函数采用五次原始 sample period 合并的结果。'
         if all(v['repeats']==5 for v in result['statistics'].values()) else
         'XLSX 每例采集一次。PDF 的 Topdown 特征取五次逐指标算术均值；热点函数沿用五次原始 sample period 合并的结果。')+
        '两路数据来自同一回放镜像，分别测量。',
        '', '### 计算口径','',
        '| 度量 | 输入与计算 | 用途 |','|---|---|---|',
        '| 顶层 Bound 余弦 | `[Bad Speculation, Frontend Bound, Backend Bound, Retiring]`；`(a·b)/(‖a‖‖b‖)` | 对比顶层分配形状，接近 1 表示方向接近 |',
        '| 热点 Jaccard | 各自 Top-10 已解析物理叶函数，以「库类别＋函数名」为键；`交集数/并集数` | 对比主要函数集合，不要求权重相等 |',
        '| 原始欧氏距离 | 固定十维：IPC、四个顶层 Bound、Core、Memory、Fetch Latency、Fetch Bandwidth、idle；`√Σ(aᵢ−bᵢ)²` | 混合单位且含层级指标，仅列作辅助，不作判定 |',
        '']
    lines+=vector_section(result)
    lines+=['', '### 五组新旧对照','',
        '| 基准 → 新输入 | Bound 余弦 | Top-10 共同数 | 热点 Jaccard | 原始欧氏距离（辅助） | Frontend 变化（pp） | Backend 变化（pp） |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in result['pairs']:
        d=r['metric_deltas_target_minus_reference']
        lines.append(f'| {r["reference"]} → {r["target"]} | {r["bound_cosine"]:.6f} | {r["common_top10_count"]}/10 | '
            f'{r["hotspot_jaccard"]:.4f} | {r["raw_euclid_auxiliary"]:.3f} | {d["Frontend Bound"]:+.2f} | {d["Backend Bound"]:+.2f} |')
    lines+=['','### 七例 Topdown 特征','',
        '除 IPC 外，表中值为百分比；'+('七例均为五次独立采集的均值。' if all(v['repeats']==5 for v in result['statistics'].values()) else 'PDF 为五次均值，XLSX 为单次结果。'),
        '', '| 数据集 | 次数 | IPC | Bad Spec. | Frontend | Backend | Retiring | Core | Memory | Fetch latency | Fetch bandwidth | idle |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for ds,r in result['statistics'].items():
        lines.append('| '+ds+' | '+str(r['repeats'])+' | '+' | '.join(f'{r["statistics"][m]["mean"]:.2f}' for m in VECTOR)+' |')
    lines+=['','### PDF 五次重复的波动','',
        '| 指标 CV | OPM | IRS W-4 | SBA 1919 |','|---|---:|---:|---:|']
    for m in ('IPC',*BOUNDS,'Memory Bound','Fetch Bandwidth Bound'):
        lines.append('| '+m+' | '+' | '.join(f'{result["statistics"][ds]["statistics"][m]["cv_percent"]:.2f}%'
            for ds in ('opm','irs_w4','sba1919'))+' |')
    if all(v['repeats']==5 for v in result['statistics'].values()):
        lines+=['','### XLSX 五次重复的波动','',
            '| 指标 CV | TLC | HR Metro | eGRID | Industry Productivity |','|---|---:|---:|---:|---:|']
        for m in METRICS:
            values=[result['statistics'][ds]['statistics'][m]['cv_percent'] for ds in ('tlc','hr_metro','egrid','industry_productivity')]
            lines.append('| '+m+' | '+' | '.join('未定义' if v is None else f'{v:.2f}%' for v in values)+' |')
        lines+=repeatability_section(result)
    pairs={r['target']:r for r in result['pairs']}
    cs=[r['bound_cosine'] for r in result['pairs']]
    lines+=['',f'五组顶层 Bound 余弦为 {min(cs):.6f}–{max(cs):.6f}，均呈后端受限为主的分配；'
        f'W-4、SBA 与 OPM 的 Top-10 分别共有 {pairs["irs_w4"]["common_top10_count"]}、{pairs["sba1919"]["common_top10_count"]} 个函数，'
        f'HR Metro、eGRID、Industry Productivity 与 TLC 分别共有 {pairs["hr_metro"]["common_top10_count"]}、'
        f'{pairs["egrid"]["common_top10_count"]}、{pairs["industry_productivity"]["common_top10_count"]} 个。'
        '这两类证据共同支持主要执行机制的延续，同时保留表单渲染、工作簿组织与重算带来的权重变化。',
        f'PDF 的 Backend Bound CV 为 '+
        f'{min(result["statistics"][ds]["statistics"]["Backend Bound"]["cv_percent"] for ds in ("opm","irs_w4","sba1919")):.2f}%–'+
        f'{max(result["statistics"][ds]["statistics"]["Backend Bound"]["cv_percent"] for ds in ("opm","irs_w4","sba1919")):.2f}%；'+
        f'OPM 的 Fetch Bandwidth CV 为 {result["statistics"]["opm"]["statistics"]["Fetch Bandwidth Bound"]["cv_percent"]:.2f}%，'
        '因此逐指标保留波动，不按统一阈值把所有特征判为稳定。'+
        ('XLSX 的重复波动见对应表。' if all(v['repeats']==5 for v in result['statistics'].values()) else 'XLSX 仅有单次结果。'),
        '', '### 统计边界与追溯','',
        'DevKit 按 CPU 0–7 计数，使用默认权限范围；PMU 窗口包含已记录的就绪和停止包络，idle 为另一个门控窗口。'
        '热点来自独立 `cycles:u` ROI 采样，不与 PMU 百分比相乘或换算。未解析热点不参与 Top-10 匹配，但其权重保留在原 ROI 分母；'
        '事件未计数、SMT 和复用语义的待核验项仍保留。本节给出描述性相似度，不套用未经校准的高／中／低阈值。',
        '逐轮原始事件、公式复算差异、来源及哈希随输入清单保存；本次不重跑工作负载、不重新采集。','']
    return '\n'.join(lines)


def repeatability_section(result):
    main=[result['statistics'][ds]['statistics'][m]['cv_percent']
          for ds in result['statistics'] for m in ('IPC',*BOUNDS)]
    finite=[v for v in main if v is not None]
    xlsx=('tlc','hr_metro','egrid','industry_productivity')
    ipc=[result['statistics'][ds]['statistics']['IPC']['cv_percent'] for ds in xlsx]
    backend=[result['statistics'][ds]['statistics']['Backend Bound']['cv_percent'] for ds in xlsx]
    lines=['','### 固定环境下的重复运行稳定性','',
        '七例在同一镜像、输入和采集参数下均有五次独立成功运行。PDF 复用既有五次，XLSX 保留原第一轮并按预定计划补四轮；'
        '没有按结果挑选轮次。报告将业务执行成功、Topdown 波动和热点排名波动分开检查。',
        f'七例 IPC 与四个顶层 Bound 共 35 个指标 CV 范围为 **{min(finite):.2f}%–{max(finite):.2f}%**。'
        '具体数值用于判断本环境的重复稳定性，不预设所有子层指标都低波动。',
        f'其中四个 XLSX 的 IPC CV 为 **{min(ipc):.2f}%–{max(ipc):.2f}%**，'
        f'Backend Bound CV 为 **{min(backend):.2f}%–{max(backend):.2f}%**，'
        '说明同一固定环境下，主要流水线分配在重复执行间保持接近；热点集合的重复性另见下表。',
        '', '| 数据集 | 热点重复数 | 同数据集五次两两 Top-10 共同函数数范围 |',
        '|---|---:|---:|']
    for ds,row in result.get('hotspot_repeatability',{}).items():
        lines.append(f'| {ds} | 5 | {row["pairwise_common_min"]}–{row["pairwise_common_max"]}/10 |')
    lines+=['','两张特征图保留每次运行的最终指标点，同时显示五次均值与样本标准差。'
            '点代表独立运行，不能与 DevKit 同一轮内的每秒时间片混为一谈。','']
    return lines


def figure_markdown(figures,output):
    lines=[]
    for f in figures:
        path=ROOT/f['path']
        if sha(path)!=f['sha256']:raise ValueError('figure changed')
        relative=os.path.relpath(path,output)
        lines+=['',f'![{f["title"]}]({relative})','',f['caption']]
    return '\n'.join(lines)


def vector_section(result):
    stats=result['statistics']
    def values(ds,keys):return [stats[ds]['statistics'][k]['mean'] for k in keys]
    fmt=lambda xs:'['+', '.join(f'{v:.6f}'.rstrip('0').rstrip('.') for v in xs)+']'
    example=next(r for r in result['pairs'] if r['reference']=='tlc' and r['target']=='hr_metro')
    w4=next(r for r in result['pairs'] if r['target']=='irs_w4')
    return ['### 从逐轮结果构造向量与集合','',
        '对每个数据集，按以下固定顺序构造十维向量；IPC 无量纲，其余维度使用 0–100 的百分数数值，'
        '例如 58.84% 写成 58.84，不写成 0.5884。十维不做标准化。',
        '', '```text',
        'v = [IPC, Bad Speculation, Frontend Bound, Backend Bound, Retiring,',
        '     Core Bound, Memory Bound, Fetch Latency Bound, Fetch Bandwidth Bound, idle_pct]',
        '```','',
        ('七例' if all(r.get('repeats',1)==5 for r in stats.values()) else 'PDF')+'对每个维度使用五次独立采集结果的算术均值：`μ=Σxᵣ/5`；'
        '样本标准差 `s=√[Σ(xᵣ−μ)²/4]`，`CV=100×s/|μ|`。'+
        ('' if all(r.get('repeats',1)==5 for r in stats.values()) else 'XLSX 使用单次值，不填标准差或 CV。')+
        '顶层 Bound 是四个父项；Backend 的 Core/Memory、Frontend 的 Latency/Bandwidth 是子项，'
        '因此余弦只抽取四个顶层维度，避免重复计入父子层级。',
        '', '以下是本次 TLC 与 HR Metro 的实际构造，idle 展示到六位小数；计算使用 JSON 中保存的原值：',
        '', '```text',
        'TLC 十维       = '+fmt(values('tlc',VECTOR)),
        'HR Metro 十维  = '+fmt(values('hr_metro',VECTOR)),
        'TLC Bound      = '+fmt(values('tlc',BOUNDS)),
        'HR Metro Bound = '+fmt(values('hr_metro',BOUNDS)),
        '```','',
        f'由这两个四维 Bound 向量计算的余弦为 **{example["bound_cosine"]:.6f}**；'
        f'十维原始欧氏距离为 **{example["raw_euclid_auxiliary"]:.3f}**。余弦不加入 IPC、子项或 idle；'
        '欧氏距离含混合单位及父子重复，只保留作辅助，三个量不加权拼成总分。',
        '热点集合按“库类别＋物理叶函数名”取各自合并结果的前十个已解析函数。'
        f'例如 OPM 与 W-4 共有 {w4["common_top10_count"]} 个，交集为 {w4["common_top10_count"]}、并集为 '
        f'{w4["union_top10_count"]}，故 Jaccard=`{w4["common_top10_count"]}/{w4["union_top10_count"]}`='
        f'**{w4["hotspot_jaccard"]:.4f}**。函数的原始 period 先用于排序；选出的集合只比较成员，权重不进入 Jaccard。',
        '']


def run(config_path,update=False):
    config_path=Path(config_path);config=json.loads(config_path.read_text())
    campaign=checked(config['topdown_campaign']);stats=checked(config['topdown_statistics'])
    verified=checked(config['topdown_verification'])
    expected_repeats=config.get('repetitions_per_dataset',
        {ds:5 if ds in ('opm','irs_w4','sba1919') else 1 for ds in config['hotspot_profiles']})
    if campaign['status']!='success' or verified['status']!='success' or verified['run_count']!=sum(expected_repeats.values()):
        raise ValueError('incomplete Topdown evidence')
    for name,key in (('campaign.json','topdown_campaign'),('statistics.json','topdown_statistics')):
        if verified['output_hashes'].get(name)!=config[key]['sha256']:
            raise ValueError('verification belongs to a different Topdown campaign/statistics')
    rows=[];images=set()
    for entry in campaign['completed']:
        value=checked(dict(path=entry['summary'],sha256=entry['summary_sha256']))
        if value['business_verification']!='success':raise ValueError('workload verification failed')
        if value['workload_counts']!=dict(requested=1,completed=1,successes=1,failures=0):raise ValueError('unexpected workload counts')
        images.add(value['image_id']);rows.append(value)
    if aggregate(rows)!=stats:raise ValueError('Topdown statistics do not reproduce from repeats')
    methods=report_methods.load(config,campaign)
    tools=hotspot_tools();profiles={};excluded={};repeatability={}
    for ds,binding in config['hotspot_profiles'].items():
        raw=checked(binding)
        if raw['dataset_id']!=ds:raise ValueError('hotspot dataset association mismatch')
        for evidence in binding.get('evidence',[]):
            value=checked(evidence)
            if evidence['path'].endswith('/comparison.json') and ds in value.get('rank_variability',{}):
                repeatability[ds]=value['rank_variability'][ds]
        for evidence_name in ('pointer',):
            if evidence_name in binding:checked(binding[evidence_name])
        if raw.get('repetitions',1)!=expected_repeats[ds]:
            raise ValueError('unexpected hotspot repeat count')
        if ds in ('opm','irs_w4','sba1919') and raw['pdf_applicant_count']!=10:raise ValueError('wrong PDF scale')
        images.add(raw['image_id']);profiles[ds]=tools.normalize_current(raw)
        eligible=tools.top_functions(profiles[ds],len(profiles[ds]['functions']))
        excluded[ds]=max(0,sum(r['share_roi'] for r in profiles[ds]['functions'])-sum(r['share_roi'] for r in eligible))
    if len(images)!=1 or next(iter(images))!=verified['image_id']:raise ValueError('mixed replay image versions')
    if set(profiles)!=set(stats) or set(stats)!={'opm','irs_w4','sba1919','tlc','hr_metro','egrid','industry_productivity'}:
        raise ValueError('expected seven aligned datasets')
    for ds,row in stats.items():
        if row['repeats']!=expected_repeats[ds]:raise ValueError('unexpected Topdown repeats')
    result=dict(schema='topdown-hotspot-similarity-v1',image_id=next(iter(images)),
        vector_order=list(VECTOR),bound_order=list(BOUNDS),statistics=stats,hotspot_repeatability=repeatability,
        pairs=[pair_result(a,b,stats,profiles,tools) for a,b in PAIRS],
        excluded_hotspot_matching_weight=excluded,formal_similarity_eligible=False,
        sources=config,config_sha256=sha(config_path),
        analysis_sources={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),
            ROOT/'analysis/topdown/report_methods.py',ROOT/'analysis/hotspots/compare.py']},
        scope='Descriptive independent CPU-scoped DevKit envelope metrics and cycles:u ROI hotspot sets; no composite score')
    output=ROOT/config['output']
    allowed={'comparison.json','report.md','pairs.csv','build.json',
             'pdf-bound-five-repeats.svg','pdf-bound-five-repeats.png','xlsx-bound-five-repeats.svg','xlsx-bound-five-repeats.png'}
    if update and output.exists() and not {p.name for p in output.iterdir()}<=allowed:
        raise ValueError('refuse to update an unexpected similarity report directory')
    output.mkdir(parents=True,exist_ok=update)
    if all(r['repeats']==5 for r in stats.values()):
        from repeat_plots import export
        result['figures'],result['matplotlib_version']=export(stats,output)
        result['analysis_sources']['analysis/topdown/repeat_plots.py']=sha(HERE/'repeat_plots.py')
    result['report_section']=section(result)
    result['measurement_methodology']=methods
    result['measurement_section']=report_methods.section(methods,verified)
    write(output/'comparison.json',result)
    (output/'report.md').write_text('# 新旧文档负载特征相似度对比\n\n'+
        result['measurement_section'].replace('## 四、','## ',1)+'\n'+result['report_section'].replace('## 六、','## ',1)+
        figure_markdown(result.get('figures',[]),output)+'\n')
    with (output/'pairs.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['reference','target','bound_cosine','hotspot_jaccard','common_top10','raw_euclid_auxiliary'])
        for r in result['pairs']:writer.writerow([r['reference'],r['target'],r['bound_cosine'],r['hotspot_jaccard'],r['common_top10_count'],r['raw_euclid_auxiliary']])
    write(output/'build.json',dict(config_sha256=sha(config_path),analysis_sources=result['analysis_sources'],
        output_sha256={p.name:sha(p) for p in output.iterdir() if p.is_file() and p.name!='build.json'}))
    print(json.dumps(dict(output=str(output.relative_to(ROOT)),pairs=[{k:r[k] for k in
        ('reference','target','bound_cosine','hotspot_jaccard','common_top10_count')} for r in result['pairs']]),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--update-report',action='store_true')
    args=parser.parse_args();run(args.config,update=args.update_report)
