"""Offline seven-component Topdown comparison and bounded Markdown publication.

No workload, model, container, PMU collection or HTML generation is invoked.
Uses DevKit Report-ALL output, preserving partial not-counted diagnostics.
"""
import argparse
import csv
import itertools
import json
import math
from pathlib import Path
import statistics
import sys

import operation_comparison as method

ROOT = method.ROOT
sys.path.insert(0,str(ROOT/'analysis/topdown'))
from devkit_full_extract import extract
from summarize import arithmetic_diagnostics

SCALE = 'analysis/docops/processed/unified-scaling-final-20261108'
BASE = 'analysis/topdown/reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7'
OUTPUT = 'analysis/docops/processed/topdown-original-cosine-euclidean-20261108'
PATHS = ('Retiring','Bad Speculation/Branch Mispredicts','Bad Speculation/Machine Clears',
    'Frontend Bound/Fetch Latency Bound','Frontend Bound/Fetch Bandwidth Bound',
    'Backend Bound/Core Bound','Backend Bound/Memory Bound')
LABELS = ('有效完成','分支误判','流水线清空','前端延迟','前端带宽','核心执行受限','存储受限')
DEPENDENCIES = ('r0008','r0010','r0011','r001b','r2011','r2012','r7001','r7005','r7006')


def require(ok,message):
    if not ok:
        raise ValueError(message)


def distance(a,b):
    require(len(a)==len(b)>0 and all(math.isfinite(x) and 0<=x<=100 for x in (*a,*b)),
            'Invalid percentage vectors')
    return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))


def compare(a,b):
    euclidean = distance(a['vector'],b['vector'])
    delta = [y-x for x,y in zip(a['vector'],b['vector'])]
    norm = math.sqrt(sum(x*x for x in a['vector'])*sum(x*x for x in b['vector']))
    require(norm>0,'Cosine requires nonzero vectors')
    require(a['IPC']>0 and math.isfinite(a['IPC']) and math.isfinite(b['IPC']), 'Invalid IPC')
    return dict(reference=a['task'],target=b['task'],euclidean_pp=euclidean,
        deltas_pp=dict(zip(LABELS,delta)),
        cosine_similarity=min(1.,sum(x*y for x,y in zip(a['vector'],b['vector']))/norm),
        ipc_relative_change_pct=100*(b['IPC']/a['IPC']-1),
        largest_differences=[dict(metric=LABELS[i],delta_pp=delta[i])
            for i in sorted(range(len(delta)),key=lambda i:(-abs(delta[i]),i))[:3]])


class Reader:
    def __init__(self):
        self.bindings={}

    def bind(self,path,expected=None):
        path=str(path)
        actual=method.sha(ROOT/path)
        require(expected is None or expected==actual,'Input hash mismatch: '+path)
        self.bindings[path]=actual
        return ROOT/path

    def json(self,path,expected=None):
        return json.loads(self.bind(path,expected).read_text())


def vector_from_extract(data):
    nodes={n['path']:n for n in data['final']['hierarchy']}
    require(len(nodes)==len(data['final']['hierarchy']),'Duplicate metric path')
    v=[nodes[p]['value'] for p in PATHS]
    require(all(math.isfinite(x) and 0<=x<=100 for x in v),'Invalid metric values')
    checks = {
        'speculation': abs(v[1]+v[2]-nodes['Bad Speculation']['value']),
        'frontend': abs(v[3]+v[4]-nodes['Frontend Bound']['value']),
        'backend': abs(v[5]+v[6]-nodes['Backend Bound']['value']),
        'partition': abs(sum(v)-100)}
    require(max(checks.values())<=.04,'Reported hierarchy does not conserve: '+str(checks))
    return v,checks


def quality(data,raw):
    events=data['final']['pmu_events']
    missing=[e for e in DEPENDENCIES if e not in events or events[e]<=0]
    require(not missing,'Missing/nonpositive cumulative basis events: '+str(missing))
    reports=[p for p in data['timesteps'] if p.get('hierarchy')]
    counts={e:sum(any(f['event']==e for f in p['event_flags']) for p in reports)
            for e in DEPENDENCIES}
    final_start=raw.rindex('TOP-DOWN Summary Report-ALL')
    flags='\n'.join(line for line in raw[:final_start].splitlines() if '<not counted>' in line)
    diagnostic=arithmetic_diagnostics(flags+'\n'+raw[final_start:])
    return dict(status='reported_aggregate_consistent',report_points=len(reports),
        cumulative_basis_events={e:events[e] for e in DEPENDENCIES},
        flags_in_report_points=counts,
        non_counted_events=sorted({f['event'] for p in data['timesteps'] for f in p['event_flags']}),
        event_status_diagnostics_preserved=True,not_counted_filled_as_zero=False,
        all_intervals_fully_counted=not any(counts.values()),
        empirical_formula_checks=diagnostic['checks'],
        formula_scope='Empirical checks of the nine previously compared metrics; not an independent formula for every hierarchy node.',
        independent_complete_pmu_semantics_validation=False,
        interpretation='Compare emitted cumulative profiles descriptively. Partial interval flags remain; positive totals do not prove every interval was fully counted.')


def gather():
    reader=Reader()
    build=reader.json(SCALE+'/analysis-build.json')
    scale=reader.json(SCALE+'/comparison.json',build['outputs']['comparison.json'])
    old_comparison=reader.json(BASE+'/similarity/comparison.json',
        scale['input_sha256'][BASE+'/similarity/comparison.json'])
    old_campaign=reader.json(BASE+'/campaign.json',old_comparison['sources']['topdown_campaign']['sha256'])
    require(old_campaign['status']=='success','Old reference campaign failed')
    original_build=reader.json('analysis/docops/processed/task-operation-expansion-20261104/analysis-build.json',
        scale['input_sha256']['analysis/docops/processed/task-operation-expansion-20261104/analysis-build.json'])
    original=reader.json('analysis/docops/processed/task-operation-expansion-20261104/comparison.json',
                         original_build['output_sha256']['comparison.json'])

    def one(task,stdout_path,expected,**extra):
        raw=reader.bind(stdout_path,expected).read_text()
        data=extract(raw)
        vector,checks=vector_from_extract(data)
        row=dict(task=task,vector=vector,IPC=data['final']['header']['IPC'],
            hierarchy_checks_pp=checks,quality=quality(data,raw),
            source=dict(stdout=stdout_path,sha256=reader.bindings[stdout_path],
                        final_report_line=data['final']['report_line']),**extra)
        return row,data

    baselines={}
    for key in ('opm','tlc'):
        runs=[]
        entries=[e for e in old_campaign['completed'] if e['dataset_id']==key]
        require([e['repeat'] for e in entries]==[1,2,3,4,5],'Five old reference captures required')
        for e in entries:
            summary=reader.json(e['summary'],e['summary_sha256'])
            path=e['raw']+'/out/devkit.stdout.txt'
            row,_=one(key.upper()+'-r'+str(e['repeat']),path,
                summary['evidence_hashes']['out/devkit.stdout.txt'],repeat=e['repeat'])
            require(row['IPC']==summary['metrics']['IPC'],'Old IPC mismatch')
            runs.append(row)
        mean=[statistics.mean(values) for values in zip(*(r['vector'] for r in runs))]
        mean_ipc=statistics.mean(r['IPC'] for r in runs)
        expected=old_comparison['statistics'][key]['statistics']
        require(mean_ipc==expected['IPC']['mean'],'Old mean IPC changed')
        for index,name in [(0,'Retiring'),(3,'Fetch Latency Bound'),(4,'Fetch Bandwidth Bound'),
                           (5,'Core Bound'),(6,'Memory Bound')]:
            require(math.isclose(mean[index],expected[name]['mean'],abs_tol=1e-10),'Old mean metric changed')
        baselines[key.upper()]=dict(task=key.upper(),vector=mean,IPC=mean_ipc,runs=runs,
            repeats=5,own_radius_pp=max(distance(r['vector'],mean) for r in runs),
            own_pair_max_pp=max(distance(a['vector'],b['vector']) for a,b in itertools.combinations(runs,2)))
    reference_scale=distance(baselines['OPM']['vector'],baselines['TLC']['vector'])
    targets={}
    for task,case in scale['cases'].items():
        if task != case['parent']:
            continue
        source=case['source']
        if source['kind']=='original':
            path=original['tasks'][task]['evidence']['topdown_stdout']
            expected=original_build['input_bindings'][path]
        else:
            # Raw stdout is immutable in the original capture's own archive;
            # collection/index are separately linked through the scale sources.
            extract_data=reader.json(source['topdown_extract'],scale['input_sha256'][source['topdown_extract']])
            path=extract_data.get('source',{}).get('path')
            if not path:
                inv_path='results/docops/scaling-reviewed-perf-20261107T054300Z-4359de4a/dataset-inventory.json'
                inv=reader.json(inv_path,scale['input_sha256'][inv_path])
                info=inv['tasks'][task]
                capture=info['captures']['topdown']
                path=capture['raw']+'/topdown/out/devkit.stdout.txt'
            archive_path=str(Path(path).with_name('sha256-index.json'))
            archive=reader.json(archive_path,scale['input_sha256'][archive_path])
            expected=archive['files']['devkit.stdout.txt']['sha256']
        row,data=one(task,path,expected,parent=case['parent'],format=case['format'],
            level='original' if task==case['parent'] else 'small' if task==scale['groups'][case['parent']][0] else 'large',
            loops=source['loops'],image_id=source['image_id'])
        require(row['IPC']==case['metrics']['IPC'],'Target IPC differs: '+task)
        for index,key in [(0,'Retiring'),(3,'Fetch Latency Bound'),(4,'Fetch Bandwidth Bound'),
                          (5,'Core Bound'),(6,'Memory Bound')]:
            require(row['vector'][index]==case['metrics'][key],'Target metric differs: '+task+' '+key)
        pairs={name:compare(base,row) for name,base in baselines.items()}
        closest=min(pairs,key=lambda b:(pairs[b]['euclidean_pp'],b))
        row.update(comparisons=pairs,nearest_reference=closest,
            nearest=pairs[closest],within_reference_scale=pairs[closest]['euclidean_pp']<=reference_scale,
            within_nearest_own_repeat_range=pairs[closest]['euclidean_pp']<=baselines[closest]['own_radius_pp'])
        targets[task]=row
    return dict(schema='docops-seven-component-cosine-euclidean-v2',vector_paths=PATHS,vector_labels=LABELS,
        baselines=baselines,targets=targets,groups={},reference_scale_pp=reference_scale,
        target_scope='Twelve original DocOps tasks only; no synthetic scaling variants.',
        reference_scale_definition='Seven-component Euclidean distance between the means of old OPM and TLC; a descriptive comparison scale, not a significance/high-medium-low threshold.',
        distance_definition='sqrt(sum((target_i-reference_i)**2)); seven percentage-point coordinates, no standardization or parent-child duplication.',
        cosine_definition='dot(reference,target)/(norm(reference)*norm(target)); same seven dimensions; IPC and idle excluded.',
        scope='DevKit Report-ALL CPU 0-7 envelope; IPC and idle not in distance. Old reference means from five independent captures; each target has one capture/mode.',
        higher_dimension_scope='Seven nonoverlapping tree-frontier components only. No flattening of all 58 nodes; ten-dimensional cache/Store refinement not used because event dependencies have not all been independently verified.',
        input_sha256=reader.bindings,workload_or_collector_run=False,html_generated=False)


def load_result():
    folder=ROOT/OUTPUT
    build=json.loads((folder/'analysis-build.json').read_text())
    require(method.sha(folder/'comparison.json')==build['outputs']['comparison.json'],'Topdown comparison changed')
    return json.loads((folder/'comparison.json').read_text())


def near_label(row):
    pair=row['nearest']
    return f'{pair["cosine_similarity"]:.4f} / {pair["euclidean_pp"]:.2f}（{row["nearest_reference"]}）'


def section74(result):
    rows=result['targets'];order=[p for values in method.GROUPS.values() for p in values]
    scale=result['reference_scale_pp'];table=method.table
    require(set(rows)==set(order),'Section 7.4 requires exactly twelve original tasks')
    original_close=[p for p in order if rows[p]['within_reference_scale']]
    farthest=sorted((rows[p] for p in order),key=lambda c:-c['nearest']['euclidean_pp'])[:3]
    base_pair=compare(result['baselines']['OPM'],result['baselines']['TLC'])
    l=['### 7.4 Topdown 相似性：用余弦与欧氏距离比较瓶颈分布', '',
       '**本节比较 CPU 的瓶颈分配是否接近，函数与操作是否覆盖仍按 7.3 判断。** '
       '本节只比较十二项新用例的原始任务，不纳入合成规模变体。采用七维、不重复计权的分区：'
       '同为后端受限，还要区分更偏执行资源还是缓存／内存数据供应。'
       '余弦看整体分布形状，欧氏距离看各项占比的数值差异，两者并列展示。', '',
       '**表 7-6：七维指标及其读法。** 向量固定为 '
       '`[Retiring, Branch Mispredicts, Machine Clears, Fetch Latency, Fetch Bandwidth, Core Bound, Memory Bound]`。'
       '七项合计约 100%；父项 Bad Speculation、Frontend、Backend 已被下面子项替换，不再重复加入向量。', '',
       table(['指标组','实际进入比较的指标','看什么'],[
           ['有效工作','Retiring（有效完成）','正常完成指令的流水线份额'],
           ['无效执行','Branch Mispredicts（分支误判）＋Machine Clears（流水线清空）','误推测的具体构成'],
           ['指令供应','Fetch Latency＋Fetch Bandwidth（前端延迟／带宽受限）','前端供应问题偏延迟还是吞吐'],
           ['执行与数据供应','Core Bound＋Memory Bound（核心执行／存储受限）','后端更偏执行资源还是缓存／内存供数']]), '',
       '**怎么算：** 对旧例向量 A、新例向量 B，同时计算以下两项。所有输入均按百分数记为 0–100，'
       '不混入不同单位，不额外标准化。IPC 单独列相对变化，idle 不加入距离。', '',
       table(['指标','公式（i 遍历七项）','读法'],[
           ['七维余弦相似度','`cos(A,B) = Σ(AᵢBᵢ) / [√ΣAᵢ² × √ΣBᵢ²]`','越接近 1，整体分布形状越接近'],
           ['七维欧氏距离','`d(A,B) = √Σ(Aᵢ−Bᵢ)²`','越小，各项占比差异越小；坐标单位为百分点（pp）']]), '',
       '**简单例子：** A=`[20,4,1,15,5,45,10]`，B=`[20,4,1,10,5,50,10]`；'
       '前端延迟减少 5 pp、Core 增加 5 pp。余弦为 **0.9933**，欧氏距离为 '
       '**√(5²＋5²)=7.07**。余弦仍很高，但数值分配已有变化，因此不单凭“超过 0.99”判定相似；'
       '欧氏距离也不是可以直接换算成相似百分比的数值。', '',
       '**用什么参照：** 旧 OPM／TLC 各五次独立采集，先逐项求均值，再与新例比较。'
       '两例均值的余弦为 **'+f'{base_pair["cosine_similarity"]:.4f}**，欧氏距离为 **{scale:.2f}**。'
       '正文按欧氏距离选择较近的旧例，并展示对同一旧例的余弦与 IPC 变化；完整记录保留两路对照。'
       '距离不超过 '+f'{scale:.2f}'+'，称为“旧两场景差异尺度内／相对接近”；超过称为“超出旧尺度”。'
       '这是一条本批实验的参照线，不是通用相似性阈值或统计显著性判据。', '',
       '**表 7-7：十二项新用例与旧 OPM／TLC 的七维比较。** '
       '余弦越大越近，欧氏距离越小越近；每行列出按欧氏距离确定的较近旧例，余弦与 IPC 也使用同一对照。'
       '较近旧例可跨格式选择，表示瓶颈数值接近，不表示业务相同。', '',
       table(['新用例','较近旧例','七维余弦 ↑','七维欧氏距离 ↓','分区判断','IPC 变化'],[
           [rows[p]['format']+' '+p,rows[p]['nearest_reference'],
            f'{rows[p]["nearest"]["cosine_similarity"]:.4f}',f'{rows[p]["nearest"]["euclidean_pp"]:.2f}',
            '旧尺度内／相对接近' if rows[p]['within_reference_scale'] else '超出旧尺度',
            f'{rows[p]["nearest"]["ipc_relative_change_pct"]:+.1f}%'] for p in order]), '',
       '**表 7-8：每项新用例相对较近旧例，差异最大的三项。** '
       '正号表示新例份额更高，负号更低；用于解释上表差异来自哪里，不是额外的相似度评分。', '',
       table(['新用例','对照旧例','差异最大的三项（pp）'],[
           [p,rows[p]['nearest_reference'],'；'.join(f'{d["metric"]} {d["delta_pp"]:+.2f}'
               for d in rows[p]['nearest']['largest_differences'])] for p in order]), '',
       '**本节结论：哪些接近，哪些存在差异？**', '',
       '1. **相对接近旧例的是 '+ '、'.join(original_close)+'。** 对各自较近旧例，余弦分别为 '+
       '／'.join(f'{rows[t]["nearest"]["cosine_similarity"]:.4f}' for t in original_close)+
       '，欧氏距离为 '+'／'.join(f'{rows[t]["nearest"]["euclidean_pp"]:.2f}' for t in original_close)+
       '，均在旧例之间的 '+f'{scale:.2f}'+' 尺度内。这说明部分 Word／PPT 任务仍与旧负载有接近的流水线分配。',
       '2. **其余十项超出旧尺度，差异程度各不相同。** 021 的距离为 '+
       f'{rows["021"]["nearest"]["euclidean_pp"]:.2f}，略高于参照线；欧氏距离最大的三项是 '+
       '、'.join(r['task']+'（'+f'{r["nearest"]["euclidean_pp"]:.2f}）' for r in farthest)+
       '。不能将它们统一称为与旧例相似，也不将略超参照线与明显偏离视为同等差异。',
       '3. **余弦较高，仍可能有具体瓶颈变化。** 例如 013 的余弦为 '+
       f'{rows["013"]["nearest"]["cosine_similarity"]:.4f}，欧氏距离仍为 {rows["013"]["nearest"]["euclidean_pp"]:.2f}；'+
       '表 7-8 用分项解释这些差异。函数是否被覆盖按 7.3 判断，本节判断瓶颈份额是否接近。',
       '4. **旧例可以代表共同基础计算，不能替代所有新增任务的 CPU 瓶颈分布。** '
       '按操作选补例仍采用 7.3 的方案；本节用余弦、欧氏距离和分项变化说明补入任务的 CPU 行为差异。', '',
       '统计取 DevKit 最终 Report-ALL：旧两例为五次独立采集的逐项均值，十二项新用例各有一次 Topdown 采集，每份内部回放十轮；'
       'CPU 0–7 包络未按 PID 裁剪，可能包含同核宿主活动；部分时间点未计数和经验公式复算差异均保留。'
       '旧例各次采集到自身均值的最大欧氏距离为 OPM '+
       f'{result["baselines"]["OPM"]["own_radius_pp"]:.2f}／TLC {result["baselines"]["TLC"]["own_radius_pp"]:.2f}，'
       '十二项新用例均超出相应旧例的自身范围；“相对接近”不表示重复运行意义上的等价。'
       '深层十维暂不作为判据，不把未计数值填零。', '',
       '[完整七维数据与对照](../'+OUTPUT+'/analysis.md)保留全部原值、24 组新旧配对、余弦、欧氏距离、IPC 及质量核验；'
       '[机器结果](../'+OUTPUT+'/comparison.json)按原始日志行号与 SHA256 追溯。', '']
    return '\n'.join(l)


def revise_section(text,result=None):
    result=load_result() if result is None else result
    require(text.count('### 7.4 ')==1 and text.count('### 7.5 ')==1,'Ambiguous 7.4 boundaries')
    a,b=text.index('### 7.4 '),text.index('### 7.5 ')
    return text[:a]+section74(result)+'\n'+text[b:]


def save(result,folder):
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=False)
    method.write(folder/'comparison.json',result)
    # Independently check both formulas with math.dist / math.hypot.
    for t,row in result['targets'].items():
        for name,pair in row['comparisons'].items():
            base=result['baselines'][name]['vector'];target=row['vector']
            require(math.isclose(math.dist(base,target),pair['euclidean_pp'],abs_tol=1e-12),'Distance mismatch')
            expected=sum((a/math.hypot(*base))*(b/math.hypot(*target)) for a,b in zip(base,target))
            require(math.isclose(expected,pair['cosine_similarity'],abs_tol=1e-12),'Cosine mismatch')
        require(not row['within_nearest_own_repeat_range'],'Report repeat-range conclusion needs review')
    checks=dict(status='passed',baseline_runs=10,target_configurations=len(result['targets']),
        paired_comparisons=sum(len(r['comparisons']) for r in result['targets'].values()),
        every_vector_has_seven_unique_tree_paths=True,reported_hierarchies_conserved=True,
        independent_euclidean_and_cosine_recalculation=True,partial_event_diagnostics_retained=True,
        unseen_or_uncounted_values_not_filled=True,deep_ten_dimensions_not_used=True)
    method.write(folder/'verification.json',checks)
    with (folder/'metrics.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['task','IPC',*LABELS,'kind'])
        for b in result['baselines'].values():
            writer.writerow([b['task'],b['IPC'],*b['vector'],'five_capture_mean'])
            for run in b['runs']:writer.writerow([run['task'],run['IPC'],*run['vector'],'reference_capture'])
        for row in result['targets'].values():writer.writerow([row['task'],row['IPC'],*row['vector'],'target_capture'])
    with (folder/'pairs.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['reference','target','euclidean_pp','cosine_similarity','IPC_relative_change_pct',*['delta_'+x for x in LABELS]])
        for row in result['targets'].values():
            for name,pair in row['comparisons'].items():writer.writerow([name,row['task'],pair['euclidean_pp'],pair['cosine_similarity'],pair['ipc_relative_change_pct'],*[pair['deltas_pp'][x] for x in LABELS]])
    lines=['# 七维 Topdown 新旧用例对照记录','',
        '使用七个互不重复的层级前沿指标，计算完整累计分布的余弦相似度与欧氏距离。'
        '这是工具累计输出的描述性比较，不是所有 PMU 事件完整有效的声明。', '',
        section74(result).replace('### 7.4 ','## 结果：',1).replace('../'+OUTPUT+'/', ''), '',
        '## 完整原值', '', method.table(['任务','IPC',*LABELS],[
            [row['task'],f'{row["IPC"]:.3f}',*[f'{x:.3f}' for x in row['vector']]]
            for row in [*result['baselines'].values(),*result['targets'].values()]]), '',
        '## 每份记录的质量标记', '',
        '表中“带未计数诊断的报告点”只统计所列累计基础事件在有报告的区间内出现的标记，'
        '不能转换为丢失周期权重，也不能据此声称最终值已无缺口。所有最终累计基础事件均为正数；'
        '经验复算仅覆盖已有九项指标，分支／清空子项只核对层级守恒，不冒充已独立验证完整官方公式。', '',
        method.table(['任务','报告点数','带基础事件未计数标记的事件／次数','经验公式超打印误差数'],[
            [row['task'],row['quality']['report_points'],
             '；'.join(e+':'+str(v) for e,v in row['quality']['flags_in_report_points'].items() if v) or '无',
             sum(not c['within_print_precision'] for c in row['quality']['empirical_formula_checks'])]
            for row in [*[run for b in result['baselines'].values() for run in b['runs']],*result['targets'].values()]]), '',
        '基准尺度来自 OPM／TLC 之间的距离，仅作可解释比较线。没有按目标结果挑选新阈值；'
        '较近参考由完整七维距离确定。主报告不将余弦超过 0.99 当作高相似结论。', '']
    (folder/'analysis.md').write_text('\n'.join(lines))
    for path,digest in result['input_sha256'].items():
        require(method.sha(ROOT/path)==digest,'Input changed during analysis: '+path)
    method.write(folder/'analysis-build.json',dict(schema='seven-component-topdown-build-v1',
        source_sha256={str(Path(__file__).relative_to(ROOT)):method.sha(__file__),
                       'analysis/topdown/devkit_full_extract.py':method.sha(ROOT/'analysis/topdown/devkit_full_extract.py'),
                       'analysis/topdown/summarize.py':method.sha(ROOT/'analysis/topdown/summarize.py')},
        input_sha256=result['input_sha256'],outputs={p.name:method.sha(p) for p in folder.iterdir() if p.is_file()},
        workload_or_collector_run=False,html_generated=False))
    print(folder/'analysis.md')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/OUTPUT)
    args=parser.parse_args()
    require(not args.output.exists(),'Choose a new output directory')
    save(gather(),args.output)
