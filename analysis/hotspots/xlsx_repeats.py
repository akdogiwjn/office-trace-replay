"""Offline aggregation of exactly five XLSX captures, preserving run-level variation."""
import argparse
import json
from pathlib import Path
import statistics

from pilot import ROOT,HERE,sha,write
from pdf_repeats import merge_profiles,ranks
from compare import normalize_current,overlap

DATASETS=('tlc','hr_metro','egrid','industry_productivity')


def aggregate(inputs_path,output):
    inputs_path=Path(inputs_path).resolve();inputs=json.loads(inputs_path.read_text())
    merged={};variability={};quality={}
    for ds in DATASETS:
        entries=inputs['inputs'][ds]
        if [r['repeat'] for r in entries]!=[1,2,3,4,5]:raise ValueError('expected all five predeclared repeats')
        values=[]
        for row in entries:
            path=ROOT/row['profile'];launch=ROOT/row['launch']
            if sha(path)!=row['profile_sha256'] or sha(launch)!=row['launch_sha256']:raise ValueError('native input changed')
            l=json.loads(launch.read_text());v=json.loads(path.read_text())
            if l['status']!='success' or v['dataset_id']!=ds:raise ValueError('capture did not succeed')
            values.append(v)
        merged[ds]=merge_profiles(values,pdf_required=False)
        variability[ds]=ranks(values,merged[ds])
        for row in variability[ds]['merged_top20']:
            x=row['per_repetition_share'];mean=statistics.mean(x);sd=statistics.stdev(x)
            row.update(mean_share=mean,sample_sd=sd,cv_percent=100*sd/mean if mean else None)
        quality[ds]=[v['capture_quality'] for v in values]
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    normalized={ds:normalize_current(v) for ds,v in merged.items()}
    for ds,v in merged.items():write(output/(ds+'-merged-profile.json'),v)
    result=dict(schema='xlsx-five-repeat-comparison-v1',repetitions=5,
        aggregation='raw period sum over five disjoint per-run ROIs, not mean percentages',
        profiles=normalized,rank_variability=variability,capture_quality=quality,inputs=inputs['inputs'],
        comparisons={ds:overlap(normalized['tlc'],normalized[ds]) for ds in DATASETS[1:]},
        analysis_source_sha256=sha(Path(__file__)),merge_source_sha256=sha(HERE/'pdf_repeats.py'),
        inputs_sha256=sha(inputs_path))
    write(output/'comparison.json',result)
    lines=['# XLSX 五次独立热点采集汇总','',
        '各数据集复用已有第一轮，新增四轮；全部五轮合并原始 period 计算热点，逐轮结果全部保留。','',
        '| 数据集 | 次数 | ROI 样本总数 | 两两重复的 Top-10 共同数范围 |','|---|---:|---:|---:|']
    for ds in DATASETS:
        r=variability[ds]
        lines.append(f'| {ds} | 5 | {merged[ds]["roi_samples"]:,} | {r["pairwise_common_min"]}–{r["pairwise_common_max"]}/10 |')
    for ds in DATASETS:
        lines+=['',f'## {ds} 主要函数的重复波动','',
            '| 合并 Top-10 函数 | 合并周期占比 | 逐轮最小–最大 | 逐轮占比 CV | 进入 Top-10 次数 |','|---|---:|---:|---:|---:|']
        for r in variability[ds]['merged_top20'][:10]:
            lines.append(f'| `{r["library"]} / {r["function"].replace("|","&#124;")}` | {r["share_roi"]:.2%} | '
                f'{r["min_share"]:.2%}–{r["max_share"]:.2%} | {r["cv_percent"]:.2f}% | {r["top10_appearance_count"]}/5 |')
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    write(output/'build.json',dict(inputs_sha256=sha(inputs_path),
        analysis_sources={str(Path(__file__).relative_to(ROOT)):sha(Path(__file__)),
                          str((HERE/'pdf_repeats.py').relative_to(ROOT)):sha(HERE/'pdf_repeats.py')},
        output_sha256={p.name:sha(p) for p in output.iterdir() if p.is_file()}))
    print(json.dumps(dict(output=str(output.relative_to(ROOT)),datasets=list(merged))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    aggregate(args.inputs,args.output)
