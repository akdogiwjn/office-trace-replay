"""Offline DevKit CPU-pilot report; never treats its envelope as exact ROI."""
import argparse
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
METRICS=('IPC','Bad Speculation','Frontend Bound','Backend Bound','Retiring',
         'Core Bound','Memory Bound','Fetch Latency Bound','Fetch Bandwidth Bound')


def arithmetic_diagnostics(text):
    """Record empirical formula differences; do not turn them into workload failure."""
    events={k:int(v.replace(',','')) for k,v in re.findall(r'^  (r[0-9a-f]+) +([0-9,]+)\s*$',text,re.M)}
    c,i,s,f=(events[k] for k in ('r0011','r0008','r001b','r2011'))
    if c<=0:raise ValueError('nonpositive cycle count')
    calc={'IPC':i/c,'Retiring':100*i/(6*c),'Bad Speculation':100*(s-i)/(6*c),'Frontend Bound':100*f/(6*c)}
    calc['Backend Bound']=100-sum(calc[k] for k in ('Retiring','Bad Speculation','Frontend Bound'))
    if 'r2012' in events:
        calc['Fetch Latency Bound']=100*events['r2012']/c
        calc['Fetch Bandwidth Bound']=calc['Frontend Bound']-calc['Fetch Latency Bound']
    if all(k in events for k in ('r7001','r7005','r7006')) and events['r7001']:
        calc['Memory Bound']=calc['Backend Bound']*(events['r7005']+events['r7006'])/events['r7001']
        calc['Core Bound']=calc['Backend Bound']-calc['Memory Bound']
    checks=[]
    for metric,value in calc.items():
        match=re.search(r'\b'+re.escape(metric)+r'\s+(-?\d+\.\d+)',text)
        if match:
            reported=float(match[1]);error=abs(value-reported)
            checks.append(dict(metric=metric,reported=reported,recalculated=value,
                absolute_error=error,within_print_precision=error<=.00501))
    uncounted=sorted(set(re.findall(r'event name: (r[0-9a-f]+), event count: <not counted>',text)))
    return dict(events=events,checks=checks,debug_not_counted_events=uncounted,
        printed_zero_is_not_independently_confirmed_zero=bool(uncounted),
        all_within_print_precision=all(row['within_print_precision'] for row in checks),
        formula_status='empirical diagnostics; raw aggregate formula may differ from DevKit aggregation/printing')


def parse(text):
    marker='TOP-DOWN Summary Report-ALL'
    if marker not in text:raise ValueError('final DevKit total report missing')
    final=text[text.rindex(marker):]
    prefix=text[:text.rindex(marker)]
    diagnostics='\n'.join(line for line in prefix.splitlines() if '<not counted>' in line)
    arithmetic=arithmetic_diagnostics(diagnostics+'\n'+final)
    metrics={}
    for metric in METRICS:
        match=re.search(r'\b'+re.escape(metric)+r'\s+(-?\d+\.\d+)',final)
        if not match:raise ValueError('metric missing: '+metric)
        value=float(match[1])
        if metric!='IPC' and not 0<=value<=100:raise ValueError('bound outside [0,100]: '+metric)
        metrics[metric]=value
    if abs(sum(metrics[k] for k in ('Bad Speculation','Frontend Bound','Backend Bound','Retiring'))-100)>.03:
        raise ValueError('top-level partition does not sum to 100')
    if abs(metrics['Core Bound']+metrics['Memory Bound']-metrics['Backend Bound'])>.03:
        raise ValueError('backend hierarchy mismatch')
    if abs(metrics['Fetch Latency Bound']+metrics['Fetch Bandwidth Bound']-metrics['Frontend Bound'])>.03:
        raise ValueError('frontend hierarchy mismatch')
    return dict(metrics=metrics,arithmetic=arithmetic)


def summarize(raw):
    raw=Path(raw).resolve();out=raw/'out'
    launch=json.loads((raw/'launch.json').read_text());state=json.loads((out/'collection.json').read_text())
    if launch['status']!='success' or state['status']!='success':raise ValueError('pilot not successful')
    for row in json.loads((out/'sha256-index.json').read_text())['files']:
        p=out/row['path']
        # Summaries use readable diagnostics; full archive was checked as container root by pilot.py.
        if row['path'] in ('collection.json','devkit.stdout.txt','profiler-record.json','affinity-events.jsonl'):
            if hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('diagnostic changed: '+str(p))
    parsed=parse((out/'devkit.stdout.txt').read_text())
    folder=HERE/'reports'/raw.name;folder.mkdir(exist_ok=False)
    result=dict(schema='devkit-gated-pilot-summary-v1',dataset_id=state['dataset_id'],
        raw=str(raw.relative_to(ROOT)),image_id=launch['image_id'],metrics=parsed['metrics'],
        idle_pct=state['cpu_window']['idle_pct'],arithmetic=parsed['arithmetic'],
        workload_status=state['workload_status'],business_verification=state.get('business_verification'),
        workload_counts=state.get('workload_counts'),roi_seconds=state['roi_seconds'],
        startup_envelope_upper_seconds=state['startup_envelope_upper_seconds'],
        tail_envelope_upper_seconds=state['tail_envelope_upper_seconds'],
        privilege_scope=state['privilege_scope'],formal_similarity_eligible=False,
        source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')},
        evidence_hashes={str(p.relative_to(raw)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [raw/'launch.json',out/'collection.json',out/'devkit.stdout.txt',out/'profiler-record.json',out/'sha256-index.json']})
    (folder/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['# DevKit 按核采集试点','',f"数据集：`{state['dataset_id']}`；镜像：`{launch['image_id']}`。",'',
        '采集 CPU 0–7，控制器在 CPU 9；正式循环期间运行 workload，预检和归档在 CPU 9。'
        '以下 PMU 指标来自 DevKit 的完整采集包络，包络含初始就绪区间及停止延迟，未冒充精确 ROI 事件过滤结果。',
        '', '| 指标 | DevKit 输出 |','|---|---:|']
    for metric,value in result['metrics'].items():lines.append(f'| {metric} | {value:.2f}'+(' |' if metric=='IPC' else '% |'))
    lines +=[f"| CPU 0–7 idle（门控窗口 /proc/stat） | {result['idle_pct']:.2f}% |",'',
        f"业务 ROI 为 {result['roi_seconds']:.3f} 秒；启动包络上界 {result['startup_envelope_upper_seconds']:.3f} 秒，"
        f"停止包络上界 {result['tail_envelope_upper_seconds']:.3f} 秒。idle 与 PMU 的窗口分别记录，不混成正式十维向量。",'',
        '顶层与前后端分区关系通过核对。原始事件经验公式复算：'+
        ('均在打印精度内。' if parsed['arithmetic']['all_within_print_precision'] else
         '存在超出打印四舍五入容差的差异；逐指标记录在 summary.json，统计采用 DevKit 原始输出，未替换或修正数值。'),
        '存在未计数诊断的事件：'+', '.join(parsed['arithmetic']['debug_not_counted_events'])+'。'
        '这些状态保留；不能仅凭最终表打印为 0 就认定真实计数为零。',
        '', '本次只验证功能与采集接线，不计算跨数据集相似度；模型、SMT、复用缩放和边界口径继续在正式采集前收敛。',
        '',f"原始记录：`{result['raw']}`。",'']
    (folder/'report.md').write_text('\n'.join(lines))
    print(str(folder.relative_to(ROOT)))
    return folder


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('raw',type=Path)
    summarize(parser.parse_args().raw)
