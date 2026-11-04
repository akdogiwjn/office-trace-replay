"""Offline supplement: component coverage, tiny-period records and raw loss facts."""
import argparse
from bisect import bisect_right
from collections import Counter
import json
from pathlib import Path

from pilot import ROOT, sha, write
from symbol_trial import BASELINE, unresolved


def counter_quality(path, intervals, dispatcher, expected_period, expected_samples):
    starts=[a for a,b in intervals]; ends=[b for a,b in intervals]
    count=total=tiny_count=tiny_period=0
    with Path(path).open() as stream:
        for line in stream:
            if not line.strip(): continue
            fields=line.split()
            if len(fields)!=4 or fields[-1]!='cycles:u:':
                raise ValueError('unexpected counter export row/event')
            pid=int(fields[0].split('/')[0]); seconds,fraction=fields[1].rstrip(':').split('.')
            ns=int(seconds)*10**9+int(fraction.ljust(9,'0'))
            index=bisect_right(starts,ns)-1
            if pid==dispatcher or index<0 or ns>=ends[index]: continue
            weight=int(fields[2]); count+=1;total+=weight
            if weight<=1: tiny_count+=1;tiny_period+=weight
    if total!=expected_period or count!=expected_samples:
        raise ValueError('counter-only ROI differs from physical-stack profile')
    return dict(roi_samples=count, roi_period=total, period_le_1_samples=tiny_count,
                period_le_1_period=tiny_period, period_le_1_share_roi=tiny_period/total)


def components(profile):
    total=Counter(); unknown=Counter()
    for row in profile['functions']:
        path=row['dso'].lower()
        name=('Python' if 'libpython' in path else 'LibreOffice' if 'libreoffice' in path
              else 'lxml' if '/lxml/' in path else 'other')
        total[name]+=row['period']
        if unresolved(row['function']): unknown[name]+=row['period']
    return {k:dict(period=v, unknown_period=unknown[k],
                   share_roi=v/profile['roi_period'], unknown_share_within_component=unknown[k]/v)
            for k,v in total.items()}


def main(output):
    output=Path(output)
    data=json.loads((output/'comparison.json').read_text());baseline=json.loads(BASELINE.read_text())
    if sha(BASELINE)!=data['baseline_sha256']:raise ValueError('baseline changed')
    details={}
    for task,row in data['tasks'].items():
        path=ROOT/row['profile'];assert sha(path)==row['profile_sha256']
        profile=json.loads(path.read_text());folder=path.parent
        collection=json.loads((folder/'collection.json').read_text())
        old_path=ROOT/row['historical_profile'];assert sha(old_path)==baseline['tasks'][task]['evidence']['profile_sha256']
        details[task]=dict(old_components=components(json.loads(old_path.read_text())),
            new_components=components(profile), capture_quality=profile['capture_quality'],
            counter_quality=counter_quality(folder/'counter-samples.txt', collection['roi_intervals_ns'],
                profile['dispatcher_pid_excluded'],profile['roi_period'],profile['roi_samples']),
            top_resolved_functions=[r for r in profile['functions'] if not unresolved(r['function'])][:15])
    write(output/'diagnostics.json',dict(tasks=details,
          note='Conditional component coverage applies only to samples with that DSO identity; unknown DSO cannot be assigned to Python or another component. Loss weights/ROI membership remain unknown.'))
    lines=['', '## Python 与 LibreOffice 内部的符号覆盖', '',
      '下表只在已识别为相应 DSO 的样本内计算未解析比例，用于区分库权重变化与库内部符号覆盖；未知 DSO 无法归属，不据此宣称全部符号齐全。', '',
      '| 任务 | Python 旧未知 | Python 新未知 | LibreOffice 旧未知 | LibreOffice 新未知 |',
      '|---|---:|---:|---:|---:|']
    def value(item,side,kind):
        row=item[side+'_components'].get(kind)
        return '—' if row is None else f"{row['unknown_share_within_component']*100:.3f}%"
    for task,r in sorted(details.items()):
        lines.append('| '+task+' | '+' | '.join(value(r,s,k)for s,k in (
            ('old','Python'),('new','Python'),('old','LibreOffice'),('new','LibreOffice')))+' |')
    lines+=['', '## 采样质量补充', '',
      '部分周期极短的记录使样本条数较多。这里独立核对 counter-only 导出的 ROI 样本数与 period，与物理栈 profile 必须完全一致；覆盖率始终按 period 加权，没有按条数均分。', '',
      '| 任务 | period≤1 的样本条数 | 这些记录占 ROI period |', '|---|---:|---:|']
    for task,row in sorted(details.items()):
        q=row['counter_quality'];lines.append(f"| {task} | {q['period_le_1_samples']:,} | {q['period_le_1_share_roi']*100:.6f}% |")
    lines+=['', '丢失记录和块的原始诊断保留在 `diagnostics.json`；无法确定其 ROI 位置及遗漏周期权重，未作补偿。单次覆盖比例不能证明无损采集，也不用于比较新旧环境执行效率。', '',
            '[组件覆盖、质量诊断与主要已解析函数](diagnostics.json)', '']
    with (output/'report.md').open('a')as stream:stream.write('\n'.join(lines))
    build=json.loads((output/'analysis-build.json').read_text())
    build['supplement_code_sha256']=sha(Path(__file__))
    build['output_sha256']={p.name:sha(p)for p in output.iterdir()if p.is_file()and p.name!='analysis-build.json'}
    write(output/'analysis-build.json',build)
    print(output/'diagnostics.json')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report-dir',type=Path,required=True)
    main(parser.parse_args().report_dir)
