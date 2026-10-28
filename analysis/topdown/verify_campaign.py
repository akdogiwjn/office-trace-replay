"""Offline verification of the completed campaign and repeat statistics."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics

from pilot import ROOT, HERE, sha, write
from campaign import PLAN, aggregate
from summarize import METRICS, parse


def verify(folder):
    folder=Path(folder).resolve()
    state=json.loads((folder/'campaign.json').read_text())
    if state['status']!='success':raise ValueError('campaign not complete')
    full=state['schema']=='devkit-seven-dataset-five-repeats-v1'
    datasets=('opm','irs_w4','sba1919','tlc','hr_metro','egrid','industry_productivity')
    expected=[(ds,r) for ds in datasets for r in range(1,6)] if full else PLAN
    count=len(expected)
    if [(r['dataset_id'],r['repeat']) for r in state['completed']]!=expected:
        raise ValueError('campaign differs from the approved run plan')
    rows=[];images=set();containers=set();versions={k:set() for k in ('capture.py','gate.py','workload_entry.py')}
    differences=[];archives=[]
    for entry in state['completed']:
        summary_path=ROOT/entry['summary'];raw=ROOT/entry['raw']
        if sha(summary_path)!=entry['summary_sha256']:raise ValueError('summary hash mismatch')
        result=json.loads(summary_path.read_text());launch=json.loads((raw/'launch.json').read_text())
        if launch['status']!='success' or launch['container_state']['ExitCode']!=0:raise ValueError('container failed')
        for name,digest in result['evidence_hashes'].items():
            if sha(raw/name)!=digest:raise ValueError('evidence hash mismatch: '+name)
        parsed=parse((raw/'out/devkit.stdout.txt').read_text())
        if parsed['metrics']!=result['metrics']:raise ValueError('analysis metrics differ')
        if result['workload_counts']!=dict(requested=1,completed=1,successes=1,failures=0):raise ValueError('workload failed')
        if result['business_verification']!='success':raise ValueError('business verification failed')
        images.add(result['image_id']);containers.add(launch['container_id'])
        for name in versions:versions[name].add(launch['source_sha256'][name])
        for check in parsed['arithmetic']['checks']:
            if not check['within_print_precision']:
                differences.append(dict(dataset_id=entry['dataset_id'],repeat=entry['repeat'],**check))
        index=json.loads((raw/'out/sha256-index.json').read_text())
        if len(index['files'])!=launch['indexed_files_checked']:raise ValueError('archive check count mismatch')
        archives.append(dict(dataset_id=entry['dataset_id'],repeat=entry['repeat'],
            checked_files=launch['indexed_files_checked'],index_sha256=sha(raw/'out/sha256-index.json')))
        rows.append(result)
    if len(images)!=1 or len(containers)!=count or any(len(v)!=1 for v in versions.values()):
        raise ValueError('image, container or collector consistency failure')
    stats=json.loads((folder/'statistics.json').read_text())
    if aggregate(rows)!=stats:raise ValueError('statistics cannot be reproduced')
    report=(folder/'report.md').read_text()
    for ds,v in stats.items():
        values=[v['statistics'][m]['mean'] for m in (*METRICS,'idle_pct')]
        line='| '+ds+' | '+str(v['repeats'])+' | '+' | '.join(f'{x:.2f}' for x in values)+' |'
        if line not in report:raise ValueError('report table differs: '+ds)
    qualified=json.loads((ROOT/'reports/image-qualification-agent-traces.json').read_text())
    for name,digest in qualified['file_hashes'].items():
        if sha(ROOT/name)!=digest:raise ValueError('qualified workload runtime changed')
    old=json.loads((ROOT/'document-oe/lock.json').read_text())
    for name,meta in old['workload_files'].items():
        p=ROOT/'document-oe/assets'/name
        if sha(p)!=meta['sha256'] or p.stat().st_size!=meta['size'] or p.stat().st_mode & 0o777 !=meta['mode']:
            raise ValueError('old workload changed: '+name)
    prior=json.loads((HERE/'hip09-preflight-20261027/sha256-index.json').read_text())
    for row in prior['files']:
        if sha(ROOT/row['path'])!=row['sha256']:raise ValueError('previous preflight evidence changed')
    with (folder/'statistics.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['dataset','repeats','metric','mean','sample_sd','cv_percent'])
        for ds,v in stats.items():
            for metric,r in v['statistics'].items():
                writer.writerow([ds,v['repeats'],metric,r['mean'],r['sample_standard_deviation'],r['cv_percent']])
    lines=['# PDF 五轮波动统计','',
        '单元格为「均值 ± 样本标准差（CV%）」；IPC 无单位，其他均值与标准差单位为百分点。'
        'idle 使用独立门控窗口；每轮均处理 10 份表单。','',
        '| 指标 | OPM | IRS W-4 | SBA 1919 |','|---|---:|---:|---:|']
    for metric in (*METRICS,'idle_pct'):
        values=[]
        for ds in ('opm','irs_w4','sba1919'):
            r=stats[ds]['statistics'][metric]
            values.append(f'{r["mean"]:.3f} ± {r["sample_standard_deviation"]:.3f}（{r["cv_percent"]:.2f}%）')
        lines.append('| '+metric+' | '+' | '.join(values)+' |')
    (folder/'pdf-repeat-variability.md').write_text('\n'.join(lines)+'\n')
    if full:
        lines+=['','## XLSX 五次重复的波动','',
            '| 指标 | TLC | HR Metro | eGRID | Industry Productivity |','|---|---:|---:|---:|---:|']
        for metric in (*METRICS,'idle_pct'):
            values=[]
            for ds in datasets[3:]:
                r=stats[ds]['statistics'][metric]
                cv='未定义' if r['cv_percent'] is None else f'{r["cv_percent"]:.2f}%'
                values.append(f'{r["mean"]:.3f} ± {r["sample_standard_deviation"]:.3f}（{cv}）')
            lines.append('| '+metric+' | '+' | '.join(values)+' |')
        (folder/'repeat-variability.md').write_text('\n'.join(lines)+'\n')
    result=dict(status='success',run_count=count,unique_containers=count,image_id=next(iter(images)),
        qualified_runtime_files_unchanged=len(qualified['file_hashes']),prior_evidence_unchanged=len(prior['files']),
        old_workload_files_unchanged=len(old['workload_files']),
        measurement_code_versions={k:next(iter(v)) for k,v in versions.items()},
        all_business_verification_success=True,statistics_reproduced=True,report_matches_json=True,
        archive_checks_recorded=archives,
        archive_check_scope='full files checked by image-root checker at collection completion; evidence hashes rechecked offline',
        empirical_formula_differences=differences,formal_similarity_eligible=False,
        workload_retries=0,
        orchestration_interruptions=[] if full else ['Initial sandbox Docker access rejected before workload',
            'Offline empirical formula tolerance stopped summary after successful OPM repeat 2; continued from existing raw'],
        verifier_sha256=sha(Path(__file__)),
        output_hashes={p.name:sha(p) for p in [folder/'campaign.json',folder/'statistics.json',folder/'statistics.csv',
            folder/'report.md',folder/'pdf-repeat-variability.md']})
    write(folder/'verification.json',result)
    print(json.dumps(dict(status='success',runs=count,archive_files_checked=sum(r['checked_files'] for r in archives),
                         formula_differences=len(differences)),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('folder',type=Path)
    verify(parser.parse_args().folder)
