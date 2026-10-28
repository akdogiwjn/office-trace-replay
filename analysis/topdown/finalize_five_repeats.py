"""Consolidate the immutable initial runs plus the 32-run extension; no sampling."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys

from pilot import ROOT,HERE,sha,write
from campaign import aggregate
from summarize import METRICS
from xlsx_extension import PLAN,DATASETS

ALL_DATASETS=('opm','irs_w4','sba1919',*DATASETS)
FULL_PLAN=[(ds,r) for ds in ALL_DATASETS for r in range(1,6)]


def combine_topdown(original,completed):
    entries=[dict(r,reused=True) for r in original]
    entries +=[dict(dataset_id=r['dataset_id'],repeat=r['repeat'],raw=r['raw'],summary=r['summary'],
        summary_sha256=r['summary_sha256'],reused=False) for r in completed if r['profiler']=='topdown']
    entries.sort(key=lambda r:(ALL_DATASETS.index(r['dataset_id']),r['repeat']))
    if [(r['dataset_id'],r['repeat']) for r in entries]!=FULL_PLAN:
        raise ValueError('incomplete or duplicate full Topdown plan')
    if len({r['raw'] for r in entries})!=35:raise ValueError('one raw capture used as multiple repeats')
    return entries


def checked(binding):
    path=ROOT/binding['path']
    if sha(path)!=binding['sha256']:raise ValueError('input changed: '+str(path))
    return json.loads(path.read_text())


def finalize(path):
    path=Path(path).resolve();extension=json.loads(path.read_text())
    if extension['status']!='success' or [{k:r[k] for k in ('dataset_id','repeat','profiler')} for r in extension['completed']]!=PLAN:
        raise ValueError('all 32 additional runs must complete before finalizing')
    baseline=checked(extension['baseline_config'])
    original=checked(baseline['topdown_campaign'])
    entries=combine_topdown(original['completed'],extension['completed'])
    rows=[checked(dict(path=r['summary'],sha256=r['summary_sha256'])) for r in entries]
    folder=HERE/'reports'/('seven-dataset-five-repeats-'+path.parent.name.removeprefix('xlsx-five-repeat-extension-'))
    folder.mkdir(parents=True,exist_ok=False)
    write(folder/'campaign.json',dict(schema='devkit-seven-dataset-five-repeats-v1',status='success',
        plan=[dict(dataset_id=ds,repeat=r) for ds,r in FULL_PLAN],completed=entries,
        extension=dict(path=str(path.relative_to(ROOT)),sha256=sha(path)),
        original_campaign=baseline['topdown_campaign'],reused_runs=19,new_runs=16,
        formal_similarity_eligible=False,pdf_applicant_count=10,workload_cpus='0-7',controller_cpu=9,
        workload_retries=extension['workload_retries']))
    stats=aggregate(rows);write(folder/'statistics.json',stats)
    lines=['# 七个数据集五次独立运行的 DevKit Topdown 统计','',
        '七例均为五次独立采集的均值，PDF 每次处理十份。复用原有结果，按预定计划补齐 XLSX 四次。','',
        '| 数据集 | 次数 | IPC | Bad Spec. | Frontend | Backend | Retiring | Core | Memory | Fetch latency | Fetch bandwidth | idle |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for ds,r in stats.items():lines.append('| '+ds+' | 5 | '+' | '.join(f'{r["statistics"][m]["mean"]:.2f}' for m in (*METRICS,'idle_pct'))+' |')
    lines+=['','所有逐轮值、样本标准差及 CV 保留在 statistics.json；保留 PMU 包络与计数语义的既有边界。']
    (folder/'report.md').write_text('\n'.join(lines)+'\n')
    native_inputs={}
    for first in extension['reused_first_repeats']:
        ds=first['dataset_id'];binding=first['native']
        evidence=checked(next(e for e in binding['evidence'] if e['path'].endswith('/evidence.json')))
        launch=ROOT/evidence['raw_directory']/'launch.json'
        native_inputs[ds]=[dict(dataset=ds,repeat=1,profile=binding['path'],profile_sha256=binding['sha256'],
            launch=str(launch.relative_to(ROOT)),launch_sha256=evidence['launch_sha256'],reused=True)]
    for row in extension['completed']:
        if row['profiler']!='native':continue
        native_inputs[row['dataset_id']].append(dict(dataset=row['dataset_id'],repeat=row['repeat'],
            profile=row['profile'],profile_sha256=row['profile_sha256'],launch=row['raw']+'/launch.json',
            launch_sha256=row['launch_sha256'],reused=False))
    write(folder/'native-inputs.json',dict(inputs=native_inputs,extension_sha256=sha(path)))
    subprocess.run([sys.executable,'-B',str(ROOT/'analysis/hotspots/xlsx_repeats.py'),
        '--inputs',str(folder/'native-inputs.json'),'--output',str(folder/'native')],check=True,cwd=ROOT)
    subprocess.run([sys.executable,'-B',str(HERE/'verify_campaign.py'),str(folder)],check=True,cwd=ROOT)
    config=dict(baseline)
    for key,name in (('topdown_campaign','campaign.json'),('topdown_statistics','statistics.json'),('topdown_verification','verification.json')):
        config[key]=dict(path=str((folder/name).relative_to(ROOT)),sha256=sha(folder/name))
    config['hotspot_profiles']=dict(baseline['hotspot_profiles'])
    for ds in DATASETS:
        p=folder/'native'/(ds+'-merged-profile.json')
        config['hotspot_profiles'][ds]=dict(path=str(p.relative_to(ROOT)),sha256=sha(p),dataset_id=ds,
            evidence=[dict(path=str((folder/'native'/name).relative_to(ROOT)),sha256=sha(folder/'native'/name))
                      for name in ('comparison.json','build.json')])
    config['repetitions_per_dataset']=dict.fromkeys(ALL_DATASETS,5)
    config['output']=str((folder/'similarity').relative_to(ROOT))
    write(folder/'comparison-inputs.json',config)
    write(HERE/'reports/latest-five-repeat-campaign.json',dict(path=str(folder.relative_to(ROOT))))
    print('CONSOLIDATED: '+str(folder),flush=True)
    return folder


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('campaign',type=Path)
    finalize(parser.parse_args().campaign)
