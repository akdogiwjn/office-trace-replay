"""Five independent PDF repetitions and offline period-weighted aggregation."""
import argparse
from collections import Counter
from datetime import datetime,timezone
from itertools import combinations
import json
from pathlib import Path
import subprocess
import sys
import uuid

from pilot import HERE,ROOT,sha,write
from compare import normalize_current,overlap,top_functions,library

DATASETS=('opm','irs_w4','sba1919')
LAYERS={'processes':('script',),'libraries':('dso',),
        'functions':('dso','function'),'contexts':('script','dso','function')}


def merge_profiles(values):
    if not values or any(p['pdf_applicant_count']!=10 for p in values):
        raise ValueError('expected N=10 PDF profiles')
    for key in ('image_id','dataset_id'):
        if len({p[key] for p in values})!=1:raise ValueError('mixed '+key)
    total=sum(p['roi_period'] for p in values)
    result={key:sum(p[key] for p in values) for key in
            ('roi_period','roi_samples','total_period','total_samples','outside_roi_period','outside_roi_samples')}
    result.update(schema='pdf-repeated-native-v1',dataset_id=values[0]['dataset_id'],
                  image_id=values[0]['image_id'],pdf_applicant_count=10,
                  repetitions=len(values),loops_per_repetition=1,
                  denominator='Sum of observed cycles:u periods inside each repetition ROI; outside intervals excluded')
    for name,fields in LAYERS.items():
        counts=Counter()
        for p in values:
            if sum(row['period'] for row in p[name])!=p['roi_period']:
                raise ValueError('incomplete layer: '+name)
            for row in p[name]:counts[tuple(row[k] for k in fields)]+=row['period']
        assert sum(counts.values())==total
        result[name]=[dict(zip(fields,key),period=period,share_roi=period/total)
                      for key,period in sorted(counts.items(),key=lambda item:(-item[1],item[0]))]
    result['quality']={key:sum(p['quality'][key]*p['roi_period'] for p in values)/total
                       for key in values[0]['quality'] if key!='unknown_categories_may_overlap'}
    result['quality']['unknown_categories_may_overlap']=True
    return result


def function_key(row):return row['library'],row['function']


def ranks(values,merged):
    normalized=[normalize_current(p) for p in values]
    sets=[{function_key(f) for f in top_functions(p,10)} for p in normalized]
    rows=[]
    for f in top_functions(normalize_current(merged),20):
        key=function_key(f)
        shares=[sum(row['share_roi'] for row in p['functions'] if function_key(row)==key) for p in normalized]
        rows.append(dict(**f,per_repetition_share=shares,min_share=min(shares),max_share=max(shares),
                         top10_appearance_count=sum(key in s for s in sets)))
    intersections=[len(a&b) for a,b in combinations(sets,2)]
    return dict(merged_top20=rows,pairwise_top10_common_counts=intersections,
                pairwise_common_min=min(intersections) if intersections else None,
                pairwise_common_max=max(intersections) if intersections else None)


def summarize(campaign_path):
    campaign_path=Path(campaign_path).resolve()
    state=json.loads(campaign_path.read_text())
    if state['status']!='success':raise ValueError('capture campaign incomplete')
    output=HERE/'reports'/campaign_path.parent.name
    output.mkdir(parents=True,exist_ok=False)
    profiles={};variability={};inputs={};quality={}
    for ds in DATASETS:
        rows=[r for r in state['completed'] if r['dataset']==ds]
        if len(rows)!=state['repetitions']:raise ValueError('missing repetitions: '+ds)
        values=[];sources=[]
        for row in rows:
            path=ROOT/row['profile'];launch=ROOT/row['launch']
            if sha(path)!=row['profile_sha256'] or sha(launch)!=row['launch_sha256']:
                raise ValueError('capture material changed')
            source=json.loads(launch.read_text())
            if source['status']!='success':raise ValueError('capture launch did not succeed')
            value=json.loads(path.read_text());values.append(value)
            sources.append(row)
        profiles[ds]=merge_profiles(values)
        variability[ds]=ranks(values,profiles[ds]);inputs[ds]=sources
        quality[ds]=[v['capture_quality'] for v in values]
    normalized={ds:normalize_current(p) for ds,p in profiles.items()}
    comparisons={ds:overlap(normalized['opm'],normalized[ds]) for ds in DATASETS[1:]}
    common=set.intersection(*[{function_key(f) for f in top_functions(normalized[ds],10)} for ds in DATASETS])
    common5=set.intersection(*[{function_key(f) for f in top_functions(normalized[ds],5)} for ds in DATASETS])
    concentration={}
    for ds in DATASETS:
        funcs=normalized[ds]['functions']
        concentration[ds]=dict(top5_share=sum(f['share_roi'] for f in top_functions(normalized[ds],5)),
            top10_share=sum(f['share_roi'] for f in top_functions(normalized[ds],10)),
            common_top10_function_share=sum(f['share_roi'] for f in funcs if function_key(f) in common))
        write(output/(ds+'-merged-profile.json'),profiles[ds])
    result=dict(schema='pdf-five-repeat-comparison-v1',repetitions=state['repetitions'],
        pdf_applicant_count_per_repetition=10,aggregation='raw period sum over disjoint per-run ROIs, not mean percentages',
        profiles=normalized,comparisons=comparisons,
        rank_variability=variability,concentration=concentration,
        common_pooled_top5_functions=[dict(library=k[0],function=k[1]) for k in sorted(common5)],
        common_top10_functions=[dict(library=k[0],function=k[1]) for k in sorted(common)],
        capture_quality=quality,inputs=inputs,campaign=str(campaign_path.relative_to(ROOT)),
        campaign_sha256=sha(campaign_path),analysis_source_sha256=sha(Path(__file__)))
    write(output/'comparison.json',result)
    pct=lambda v:f'{100*v:.2f}%'
    lines=['# PDF 五轮重复采样与热点统计','',
        'OPM、IRS W-4、SBA 1919 各独立运行五次，每次使用新容器、执行一轮并处理十份 PDF。'
        '使用同一镜像、cycles:u、49 Hz、DWARF 16384 字节、逻辑 CPU 0–7；监测进程绑定 CPU 9。',
        '每次仅选取正式循环 ROI，合并原始 sample period 后重新计算占比；保留逐轮结果用于观察排名波动。',
        '', '## 统计结论','',
        f"三例五轮合并后的 Top-5 函数共有 {len(common5)} 个共同项："+
        '、'.join('`'+key[1]+'`' for key in sorted(common5))+'。',
        '各自 Top-5 累计占比为 '+ '、'.join(f"{ds} {pct(concentration[ds]['top5_share'])}" for ds in DATASETS)+'。',
        f"五轮合并后，与 OPM 的 Top-10 共同函数数为 W-4 {comparisons['irs_w4']['common_top10_count']} 个、"
        f"SBA {comparisons['sba1919']['common_top10_count']} 个。",
        '逐轮 Top-10 仍存在排名波动；本批次合并结果更清楚地呈现了共同的解释器执行、压缩编码和图片处理热点。',
        '', '| 数据集 | 成功重复数 | ROI 样本数合计 | 各轮 ROI 样本数 |','|---|---:|---:|---|']
    for ds in DATASETS:
        count=[r['roi_samples'] for r in inputs[ds]]
        lines.append(f"| {ds} | {len(count)}/{state['repetitions']} | {profiles[ds]['roi_samples']:,} | {', '.join(map(str,count))} |")
    lines+=['','## 合并后的主要脚本／进程','', '| 脚本／程序 | OPM | W-4 | SBA 1919 |','|---|---:|---:|---:|']
    for layer,label in [('processes','script'),('libraries','library')]:
        if layer=='libraries':lines+=['','## 合并后的主要库','', '| 库 | OPM | W-4 | SBA 1919 |','|---|---:|---:|---:|']
        maps={ds:{r[label]:r['share_roi'] for r in normalized[ds][layer]} for ds in DATASETS}
        keys=set().union(*(m.keys() for m in maps.values()))
        for key in sorted(keys,key=lambda k:-max(m.get(k,0) for m in maps.values())):
            if max(m.get(key,0) for m in maps.values())>=.005:
                lines.append('| `'+key+'` | '+' | '.join(pct(maps[ds].get(key,0)) for ds in DATASETS)+' |')
    lines+=['','## 合并后的 Top-10 函数并集','', '| 库／物理叶函数 | OPM | W-4 | SBA 1919 |','|---|---:|---:|---:|']
    maps={ds:{function_key(f):f['share_roi'] for f in normalized[ds]['functions']} for ds in DATASETS}
    keys={function_key(f) for ds in DATASETS for f in top_functions(normalized[ds],10)}
    for key in sorted(keys,key=lambda k:-max(m.get(k,0) for m in maps.values())):
        label=(key[0]+' / '+key[1]).replace('|','&#124;')
        lines.append('| `'+label+'` | '+' | '.join(pct(maps[ds].get(key,0)) for ds in DATASETS)+' |')
    lines+=['','## 五轮合并共同热点','',
        '| 对照 OPM | Top-10 共同函数数 | OPM Top-10 在目标 Top-20 出现 |',
        '|---|---:|---:|']
    for ds in DATASETS[1:]:
        new=comparisons[ds]
        lines.append(f"| {ds} | {new['common_top10_count']}/10 | {new['old_top10_in_new_top20_count']}/10 |")
    lines+=['','## 热点集中度','',
        '| 数据集 | 各自 Top-5 合计 | 各自 Top-10 合计 | 三例共同 Top-10 交集函数合计 |','|---|---:|---:|---:|']
    for ds in DATASETS:
        row=concentration[ds]
        lines.append('| '+ds+' | '+' | '.join(pct(row[k]) for k in ('top5_share','top10_share','common_top10_function_share'))+' |')
    lines+=['',f'三例 Top-10 交集有 {len(common)} 个函数；交集与各自 Top-5 是不同集合。',
            '', '## 逐轮排名波动','']
    for ds in DATASETS:
        v=variability[ds]
        lines +=[f'### {ds}','',
            f"五轮两两比较的 Top-10 共同函数数范围为 {v['pairwise_common_min']}–{v['pairwise_common_max']}。",'',
            '| 合并排名前十的函数 | 五轮合并占比 | 逐轮占比范围 | 进入逐轮 Top-10 的次数 |','|---|---:|---:|---:|']
        for f in v['merged_top20'][:10]:
            lines.append(f"| `{f['function']}` | {pct(f['share_roi'])} | {pct(f['min_share'])}–{pct(f['max_share'])} | {f['top10_appearance_count']}/5 |")
        lines+=['']
    lines+=['## 采集记录','',
        '本次为预先固定的五次重复，没有根据结果选择或删除轮次。未知项保留分母；损失诊断保留原生单位。'
        '详细 period、逐轮函数列表、来源及哈希见 comparison.json。本报告仅采用五轮统计。','']
    for ds in DATASETS:
        for i,row in enumerate(quality[ds],1):
            loss=row.get('loss_recheck',row)
            lines.append(f"- {ds} r{i}：LOST={loss.get('reported_lost_records')}，LOST_SAMPLES={loss.get('reported_lost_sample_records')}，lost chunks={loss.get('perf_record_reported_lost_chunks')}。")
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    write(output/'build.json',dict(campaign_sha256=sha(campaign_path),analysis_sha256=sha(Path(__file__)),
         output_sha256={p.name:sha(p) for p in output.iterdir() if p.is_file()}))
    write(HERE/'reports/latest-pdf-repeats.json',dict(report=str(output.relative_to(ROOT)),campaign=str(campaign_path.relative_to(ROOT))))
    print(json.dumps(dict(report=str(output.relative_to(ROOT)),comparisons=comparisons)),flush=True)


def collect():
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    directory=HERE/'raw'/('pdf-five-repeats-'+stamp);directory.mkdir(parents=True)
    reference=HERE/'reports/pdf-xlsx-common-hotspots-20261027/comparison.json'
    state=dict(status='in_progress',repetitions=5,selected_datasets=list(DATASETS),completed=[],
               single_reference=dict(path=str(reference.relative_to(ROOT)),sha256=sha(reference)),
               measurement_source_sha256={p.name:sha(p) for p in HERE.glob('*.py')})
    path=directory/'campaign.json';write(path,state)
    print('Campaign: '+str(directory),flush=True)
    try:
        # Interleave datasets so that each receives all five predeclared rounds.
        for repeat in range(1,6):
            for ds in DATASETS:
                state.update(running_dataset=ds,running_repeat=repeat);write(path,state)
                print(f'Starting {ds} r{repeat}/5',flush=True)
                result=subprocess.run([sys.executable,'-B','-u',str(HERE/'pilot.py'),'--dataset',ds],cwd=ROOT)
                if result.returncode:raise RuntimeError(f'{ds} r{repeat} failed; preserved evidence; no automatic retry')
                pointer=HERE/f'reports/latest-{ds}.json';p=json.loads(pointer.read_text())
                profile_path=ROOT/p['report']/'profile.json';profile=json.loads(profile_path.read_text());launch=ROOT/p['raw']/'launch.json'
                state['completed'].append(dict(dataset=ds,repeat=repeat,profile=str(profile_path.relative_to(ROOT)),
                    profile_sha256=sha(profile_path),launch=str(launch.relative_to(ROOT)),launch_sha256=sha(launch),
                    roi_samples=profile['roi_samples'],roi_period=profile['roi_period']))
                write(path,state)
        state.update(status='success',running_dataset=None,running_repeat=None)
    except BaseException as exc:
        state.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:write(path,state)
    summarize(path)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect',action='store_true')
    parser.add_argument('--summarize',type=Path)
    args=parser.parse_args()
    if args.collect and not args.summarize:collect()
    elif args.summarize and not args.collect:summarize(args.summarize)
    else:parser.error('choose --collect or --summarize')
