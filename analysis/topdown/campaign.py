"""Sequential seven-dataset campaign: five independent PDF repeats, one XLSX."""
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import uuid

from pilot import HERE, ROOT, launch, sha, write
from summarize import METRICS, summarize

PLAN=[(dataset,repeat) for dataset in ('opm','irs_w4','sba1919') for repeat in range(1,6)] + [
    (dataset,1) for dataset in ('tlc','hr_metro','egrid','industry_productivity')]


def aggregate(rows):
    grouped={}
    for row in rows:grouped.setdefault(row['dataset_id'],[]).append(row)
    output={}
    for dataset,runs in grouped.items():
        metrics={}
        for metric in (*METRICS,'idle_pct'):
            values=[run['idle_pct'] if metric=='idle_pct' else run['metrics'][metric] for run in runs]
            mean=statistics.mean(values)
            sd=statistics.stdev(values) if len(values)>1 else None
            metrics[metric]=dict(values=values,mean=mean,sample_standard_deviation=sd,
                cv_percent=100*sd/abs(mean) if sd is not None and mean else None)
        output[dataset]=dict(repeats=len(runs),statistics=metrics,
            roi_seconds=[r['roi_seconds'] for r in runs],
            startup_envelope_upper_seconds=[r['startup_envelope_upper_seconds'] for r in runs],
            tail_envelope_upper_seconds=[r['tail_envelope_upper_seconds'] for r in runs],
            debug_not_counted_events=sorted({event for run in runs for event in run['arithmetic']['debug_not_counted_events']}))
    return output


def run(resume=None,recovered_raw=None):
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    folder=HERE/'reports'/('seven-dataset-'+stamp);folder.mkdir(parents=True,exist_ok=False)
    state=dict(schema='devkit-seven-dataset-campaign-v1',status='in_progress',
        plan=[dict(dataset_id=ds,repeat=r) for ds,r in PLAN],completed=[],
        pdf_applicant_count=10,workload_cpus='0-7',controller_cpu=9,
        formal_similarity_eligible=False,
        measurement_scope='DevKit CPU envelope; /proc/stat idle has a separate gated window',
        source_hashes={p.name:sha(p) for p in HERE.glob('*.py')})
    rows=[]
    if resume:
        previous=json.loads(Path(resume).read_text())
        if previous['plan']!=state['plan'] or previous['status']!='failed':raise ValueError('only matching failed campaign can be continued')
        state['continues']=dict(path=str(Path(resume).resolve()),sha256=sha(Path(resume)))
        for entry in previous['completed']:
            path=ROOT/entry['summary']
            if sha(path)!=entry['summary_sha256']:raise ValueError('previous summary changed')
            rows.append(json.loads(path.read_text()));state['completed'].append(entry)
        if recovered_raw:
            ds,repeat=PLAN[len(rows)]
            report=summarize(Path(recovered_raw));result=json.loads((report/'summary.json').read_text())
            if result['dataset_id']!=ds:raise ValueError('recovered dataset not next in plan')
            rows.append(result);state['completed'].append(dict(dataset_id=ds,repeat=repeat,
                raw=str(Path(recovered_raw).resolve().relative_to(ROOT)),
                summary=str((report/'summary.json').relative_to(ROOT)),summary_sha256=sha(report/'summary.json')))
    elif recovered_raw:raise ValueError('recovered raw requires previous campaign')
    write(folder/'campaign.json',state)
    print('Campaign: '+str(folder),flush=True)
    try:
        for ds,repeat in PLAN[len(rows):]:
            state['active']=dict(dataset_id=ds,repeat=repeat);write(folder/'campaign.json',state)
            print(f'START {ds} repeat {repeat}',flush=True)
            raw=launch(ds)
            state['active_raw']=str(raw.relative_to(ROOT));write(folder/'campaign.json',state)
            report=summarize(raw)
            result=json.loads((report/'summary.json').read_text());rows.append(result)
            state['completed'].append(dict(dataset_id=ds,repeat=repeat,raw=str(raw.relative_to(ROOT)),
                summary=str((report/'summary.json').relative_to(ROOT)),summary_sha256=sha(report/'summary.json')))
            write(folder/'campaign.json',state)
            write(folder/'statistics.json',aggregate(rows))
            print(f'DONE {ds} repeat {repeat}: ROI={result["roi_seconds"]:.2f}s',flush=True)
        state.update(status='success',active=None)
    except BaseException as exc:
        state.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:write(folder/'campaign.json',state)
    stats=aggregate(rows)
    lines=['# 七个数据集 DevKit Topdown 统计','',
        'PDF 每例独立运行 5 次，每次处理 10 份；XLSX 每例运行 1 次。'
        '全部使用同一镜像与 DevKit，采集 CPU 0–7，控制与归档在 CPU 9。','',
        '以下为 DevKit 最终总报告的逐轮指标均值。百分比是工具的 Topdown 指标，'
        '采集窗口包含已记录的就绪及停止包络；idle 为独立门控窗口的 /proc/stat 统计。','',
        '| 数据集 | 次数 | IPC | Bad Spec. | Frontend | Backend | Retiring | Core | Memory | Fetch latency | Fetch bandwidth | idle |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for ds,v in stats.items():
        values=[v['statistics'][m]['mean'] for m in (*METRICS,'idle_pct')]
        lines.append('| '+ds+' | '+str(v['repeats'])+' | '+' | '.join(f'{x:.2f}' for x in values)+' |')
    lines+=['','PDF 逐轮值、样本标准差及 CV 见 statistics.json；XLSX 单轮不计算标准差和 CV。'
            '尚未解决的事件未计数、SMT/复用语义及窗口边界限制继续保留，本表用于描述性对比。','',
            '完整关联见 campaign.json；各轮报告保留原始事件计数、分区检查、实际镜像 ID 和归档哈希。','']
    (folder/'report.md').write_text('\n'.join(lines))
    write(HERE/'reports/latest-campaign.json',dict(path=str(folder.relative_to(ROOT)),campaign_sha256=sha(folder/'campaign.json')))
    print('COMPLETE: '+str(folder),flush=True)


if __name__=='__main__':run()
