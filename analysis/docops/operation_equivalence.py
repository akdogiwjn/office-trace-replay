"""Account for operation-equivalent leaf samples without changing captured data."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import re

import operation_comparison as method

ROOT=method.ROOT
INPUT='analysis/docops/processed/unified-scaling-final-20261108'
OUTPUT='analysis/docops/processed/operation-equivalence-20261112'
POLICY='PNG, explicit resampling, zlib, Poppler, named Calc paths; JPEG separate; no whole-framework/runtime credit.'


def require(ok,message):
    if not ok:raise ValueError(message)


def same_operation(f):
    tool,name=f['tool'],f['function']
    if tool=='PNG':return 'PNG 编解码'
    if tool=='zlib':return '压缩／解压'
    if tool=='Poppler':return 'PDF 渲染'
    if tool=='LibreOffice·Calc':return '模型／重算'
    if tool=='ImageMagick' and re.search(r'HorizontalFilter|VerticalFilter|ResizeImage',name):
        return '图片缩放'
    if tool=='LibreOffice·VCL' and any(s in name for s in ('ImplScaleConvolution','scaleUpPalette')):
        return '图片缩放'
    return None


def separate_operation(f,fmt):
    tool,name=f['tool'],f['function']
    if tool=='JPEG' or (tool=='LibreOffice·VCL' and 'encode_mcu_' in name):return 'JPEG'
    if tool=='ImageMagick' and re.search(r'Composite\w*Image|AppendImages|SmushImages',name):return '拼图合成'
    if tool=='LibreOffice·Writer' or (fmt=='PPT' and tool=='LibreOffice·OOXML'):
        return '对象／布局样式'
    if tool in ('LibreOffice·文本布局','LibreOffice·文本样式','LibreOffice·矢量图形'):
        return '对象／布局样式'
    return None


def account(case,old):
    rows=case['functions'];total=case['roi_period'];keys=[method.key(f) for f in rows]
    require(total>0 and len(keys)==len(set(keys)),'Invalid period or duplicate function identity')
    require(all(isinstance(f['period'],int) and f['period']>=0 for f in rows),'Invalid function periods')
    classified={method.key(f):f for f in case['hotspot_coverage']['unseen_functions']}
    require(set(classified)==set(keys)-old,'Unseen classification differs from full function list')
    periods=Counter();operations=Counter();separate=Counter();other_tools=Counter();ledger=[]
    for row in rows:
        key=method.key(row);category=None;tool=None
        if key in old:bucket='exact'
        else:
            f=classified[key];tool=f['tool']
            require(row['period']==f['period'],'Classified period changed')
            category=same_operation(f)
            if category:bucket='same_operation';operations[category]+=row['period']
            else:
                category=separate_operation(f,case['format'])
                if category:bucket='separate_operation';separate[category]+=row['period']
                else:bucket='other_resolved';other_tools[tool]+=row['period']
        periods[bucket]+=row['period']
        ledger.append(dict(row,bucket=bucket,operation=category,tool=tool))
    unknown=total-sum(periods.values());require(unknown>=0,'Resolved period exceeds ROI')
    periods['unresolved']=unknown
    for k in ('exact','same_operation','separate_operation','other_resolved'):periods.setdefault(k,0)
    saved=case['presence']['OPM+TLC']
    require(periods['exact']==saved['observed_period'] and unknown==saved['unresolved_period'],
            'Exact/unknown partition differs from saved analysis')
    require(sum(periods.values())==total,'Buckets do not conserve ROI')
    return dict(task=case['task'],parent=case['parent'],format=case['format'],roi_period=total,
        periods=dict(periods),shares_pct={k:100*v/total for k,v in periods.items()},
        supported_share_pct=100*(periods['exact']+periods['same_operation'])/total,
        same_operations=[dict(operation=k,period=v,share_pct=100*v/total) for k,v in operations.most_common()],
        separate_operations=[dict(operation=k,period=v,share_pct=100*v/total) for k,v in separate.most_common()],
        other_tools=[dict(tool=k,period=v,share_pct=100*v/total) for k,v in other_tools.most_common()],
        functions=ledger)


def gather():
    build=json.loads((ROOT/INPUT/'analysis-build.json').read_text())
    source=ROOT/INPUT/'comparison.json'
    require(method.sha(source)==build['outputs']['comparison.json'],'Input comparison changed')
    data=json.loads(source.read_text());old={method.key(f) for c in data['references'].values() for f in c['functions']}
    require(len(old)==1339,'Old union changed')
    for p,h in data['input_sha256'].items():require(method.sha(ROOT/p)==h,'Measurement input changed: '+p)
    rows={};checks={}
    for parent,(_,task) in data['groups'].items():
        c=data['cases'][task];row=account(c,old)
        raw=json.loads((ROOT/c['source']['profile']).read_text());amounts=Counter()
        for f in raw['functions']:
            valid=f['dso']!='[unknown]' and method.resolved(f['function'])
            key=(Path(f['dso']).name,f['function'])
            amounts['unresolved' if not valid else 'exact' if key in old else 'unseen']+=f['period']
        require(amounts['exact']==row['periods']['exact'] and amounts['unresolved']==row['periods']['unresolved']
                and sum(amounts.values())==row['roi_period'],'Independent raw partition mismatch')
        row['quality']=dict(unresolved_share_pct=row['shares_pct']['unresolved'],
            lost_chunks=c['source']['capture_quality'].get('perf_record_reported_lost_chunks'),
            cycles_u_lost_samples=c['source']['capture_quality'].get('cycles_u_stats_lost_samples'))
        rows[parent]=row;checks[task]=dict(raw_partition_recalculated=True,disjoint_buckets=True,
            full_denominator=True,jpeg_not_credited_as_png=True,runtime_framework_not_automatically_credited=True)
    return dict(schema='operation-equivalence-accounting-v1',policy=POLICY,
        cases=rows,source_comparison=dict(path=str(source.relative_to(ROOT)),sha256=method.sha(source)),
        source_build=dict(path=INPUT+'/analysis-build.json',sha256=method.sha(ROOT/INPUT/'analysis-build.json')),
        verification=dict(status='passed',cases=checks,input_hashes_checked=len(data['input_sha256'])),
        interpretation='Exact observed functions plus declared equivalent operation types; not exact function coverage, total CPU time or algorithm/PMU equivalence.',
        report_or_html_modified=False,workload_or_collector_run=False)


def load():
    folder=ROOT/OUTPUT;build=json.loads((folder/'analysis-build.json').read_text())
    require(method.sha(folder/'comparison.json')==build['outputs']['comparison.json'],'Operation accounting changed')
    return json.loads((folder/'comparison.json').read_text())


def save(result,folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    method.write(folder/'comparison.json',result)
    with (folder/'functions.csv').open('w',newline='') as f:
        fields=['task','library','function','period','share_roi','bucket','operation','tool']
        w=csv.DictWriter(f,fields);w.writeheader()
        for c in result['cases'].values():
            for row in c['functions']:w.writerow(dict(task=c['task'],**row))
    with (folder/'coverage.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['task','exact_pct','same_operation_pct','separate_operation_pct','other_resolved_pct','unresolved_pct','supported_pct'])
        for c in result['cases'].values():w.writerow([c['task'],*[c['shares_pct'][k] for k in ('exact','same_operation','separate_operation','other_resolved','unresolved')],c['supported_share_pct']])
    (folder/'analysis.md').write_text('# 大规模任务的同类操作归并\n\n'
        '完整 ROI 分母保持不变：精确匹配＋同类操作＋单列操作＋其他已解析＋未解析＝100%。\n\n'
        '同类操作：PNG 编解码、明确缩放、zlib、Poppler、可识别 Calc 路径。JPEG 单列；Python/XML 和公共框架不自动归并。\n\n'
        '单列操作：JPEG、ImageMagick 合成、Writer/PPT 对象及布局样式。单列表示独立保留的路径，不将整组推断为新增算法。\n\n'
        'functions.csv 保留逐函数分类；comparison.json 保留全部权重、其他工具归属、丢样及未知标记。采样权重不是总 CPU 时间。\n')
    method.write(folder/'analysis-build.json',dict(source_sha256={str(Path(__file__).relative_to(ROOT)):method.sha(__file__)},
        inputs={r['path']:r['sha256'] for r in (result['source_comparison'],result['source_build'])},
        outputs={p.name:method.sha(p) for p in folder.iterdir() if p.is_file()},
        workload_or_collector_run=False,html_modified=False))
    print(folder)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/OUTPUT)
    args=p.parse_args();save(gather(),args.output)
