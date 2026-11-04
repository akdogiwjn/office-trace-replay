"""One independent perf capture per task, then compare symbol coverage offline."""
import argparse
from collections import Counter
import datetime
import json
import math
import os
from pathlib import Path
import re

from pilot import HERE, ROOT, launch, sha, write
from quality import function_qualification

BASELINE = HERE/'processed/first-comparison-batch-20261103/comparison.json'
# Check the most symbol-limited tasks first; collect each selected task once.
TASKS = ('029', '016', '021', '026', '001', '003', '009', '013', '014', '031', '037', 'pdfwf005')


def unresolved(symbol):
    return symbol in ('[unknown]', '[no-frame]') or re.fullmatch(r'0x[0-9a-fA-F]+|[0-9a-fA-F]{12,}', symbol) is not None


def symbol_partition(profile):
    total = profile['roi_period']
    rows = profile['functions']
    if total <= 0 or sum(row['period'] for row in rows) != total:
        raise ValueError('function periods do not partition the complete ROI')
    unknown = Counter()
    for row in rows:
        if unresolved(row['function']):
            unknown[row['dso']] += row['period']
    share = sum(unknown.values())/total
    if not math.isclose(share, profile['quality']['unknown_leaf_symbol_share'], abs_tol=1e-12):
        raise ValueError('unknown-function period differs from parser quality')
    return dict(unknown_period=sum(unknown.values()), unknown_share=share,
                resolved_share=1-share,
                unresolved_dsos=[dict(dso=k, period=v, share_roi=v/total)
                                 for k,v in unknown.most_common()])


def summarize(campaign_path, output):
    campaign_path = Path(campaign_path); output = Path(output)
    campaign = json.loads(campaign_path.read_text())
    baseline = json.loads(BASELINE.read_text())
    if sha(BASELINE) != campaign['baseline_sha256']:
        raise ValueError('historical comparison changed')
    output.mkdir(parents=True, exist_ok=False)
    rows = {}
    for task in TASKS:
        item = campaign['tasks'].get(task)
        if not item or item['status'] != 'passed':
            continue
        folder = ROOT/item['out']; profile_path = folder/'profile.json'
        if sha(profile_path) != item['profile_sha256']:
            raise ValueError('new profile changed')
        profile = json.loads(profile_path.read_text())
        old = baseline['tasks'][task]
        old_profile_path = ROOT/old['evidence']['profile']
        if sha(old_profile_path) != old['evidence']['profile_sha256']:
            raise ValueError('historical profile changed')
        old_profile = json.loads(old_profile_path.read_text())
        previous = symbol_partition(old_profile); current = symbol_partition(profile)
        rows[task] = dict(format=old['format'], name=old['name'], old=previous, new=current,
                         unknown_share_change_pp=100*(current['unknown_share']-previous['unknown_share']),
                         quality=profile['quality'], capture_quality=profile['capture_quality'],
                         qualification=function_qualification(profile['quality']),
                         roi_samples=profile['roi_samples'], roi_period=profile['roi_period'],
                         profile=str(profile_path.relative_to(ROOT)), profile_sha256=sha(profile_path),
                         historical_profile=str(old_profile_path.relative_to(ROOT)),
                         old_python_unknown_share=sum(r['share_roi'] for r in previous['unresolved_dsos'] if 'libpython' in r['dso']),
                         new_python_unknown_share=sum(r['share_roi'] for r in current['unresolved_dsos'] if 'libpython' in r['dso']))
    result = dict(schema='docops-unified-symbol-comparison-v1', status=campaign['status'],
                  image_id=campaign['image_id'], old_image_id=baseline['image_id'],
                  captures_per_task=1, loops_per_capture=10, topdown_collected=False,
                  campaign=str(campaign_path.relative_to(ROOT)), campaign_sha256=sha(campaign_path),
                  baseline=str(BASELINE.relative_to(ROOT)), baseline_sha256=sha(BASELINE), tasks=rows,
                  interpretation='New runtime captures, not a re-symbolization of the same perf.data; changed versions, optional dependencies and workload weights can affect unresolved shares. One capture does not estimate repeat variability.')
    write(output/'comparison.json', result)
    lines=['# DocOps 统一环境：一轮 perf 符号覆盖检查', '',
           '每任务一份独立 perf profile，每份回放十轮；仅采 perf，未采 DevKit。', '',
           f"旧镜像 `{result['old_image_id']}`；新镜像 `{result['image_id']}`。", '',
           '| 格式 | 任务 | 旧未解析符号 | 新未解析符号 | 变化 pp | 新空栈权重 | ROI 样本 | 函数资格 |',
           '|---|---|---:|---:|---:|---:|---:|---|']
    for task in sorted(rows):
        r=rows[task]
        lines.append(f"| {r['format']} | {task} | {r['old']['unknown_share']*100:.2f}% | {r['new']['unknown_share']*100:.2f}% | {r['unknown_share_change_pp']:+.2f} | {r['quality']['empty_stack_share']*100:.4f}% | {r['roi_samples']:,} | {r['qualification']['status']} |")
    lines += ['', '## 口径与证据', '',
              '- 分母是 workflow 区间并集内、排除调度器后全部 `cycles:u` 原始 sample period；未知项未从分母删除。',
              '- perf 按入口及后代采集，49 Hz、DWARF 16384、CLOCK_MONOTONIC；业务 CPU 0–7、控制/准备/归档 CPU 9；在同镜像中以 `--no-inline` 导出物理调用栈。',
              '- 原始 perf、导出文本、build-id、实际容器 inspect、ROI、loss、逐项哈希和代码快照保留；不挂载旧 Debian 符号树，不在线补符号。',
              '- 旧列采用上一批已补过精确匹配符号的最终 profile。两列属于不同运行环境和不同次采样，变化不能全解释为同一批样本补符号的收益。',
              '- Python、Calc、Writer、Impress 使用与原七例相同、包含完整符号的二进制；新增 lxml 等扩展仍可能缺少完整符号。',
              '- loss 保留原单位，ROI 归属未知，不换算为周期；当前仅一次独立采集，未计算稳定性或 CV。',
              '', '[完整结果及未解析 DSO 分解](comparison.json)', '',
              f"采集清单：`{result['campaign']}`。"]
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    write(output/'analysis-build.json', dict(code_sha256=sha(Path(__file__)),
          output_sha256={p.name:sha(p) for p in output.iterdir() if p.is_file()}))
    print('REPORT '+str(output/'report.md'), flush=True)
    return result


def collect(folder, report):
    folder = Path(folder).resolve()
    if not folder.is_relative_to(HERE/'raw'):
        raise ValueError('campaign must be a fresh directory under analysis/docops/raw')
    folder.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {9})
    candidate = json.loads((ROOT/'docops/docker/current-image.json').read_text())
    if candidate['runtime_profile'] != 'seven-case-openeuler-unified' or candidate['functional_summary']['status'] != 'passed':
        raise ValueError('unified runtime functional trials must pass first')
    state=dict(schema='docops-unified-perf-symbol-campaign-v1', status='running',
               image_id=candidate['candidate_id'], image_reference=candidate['candidate_tag'],
               runtime_profile=candidate['runtime_profile'], loops_per_capture=10,
               independent_captures_per_task=1, modes=['perf'], task_order=list(TASKS), tasks={},
               controller_cpu=9, workload_cpus='0-7', baseline_sha256=sha(BASELINE),
               driver_sha256=sha(Path(__file__)), candidate_snapshot=candidate,
               started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    path=folder/'campaign.json';write(path,state)
    print('CAMPAIGN '+str(folder),flush=True)
    try:
        for task in TASKS:
            active=json.loads((ROOT/'docops/docker/current-image.json').read_text())
            if active['candidate_id'] != state['image_id']:
                raise ValueError('current image changed during campaign')
            state['active_task']=task;write(path,state)
            record=launch(task,10,['perf'],return_record=True)
            if record['image_id'] != state['image_id'] or record['status'] != 'passed':
                state['tasks'][task]=dict(status='failed',raw=record['raw'],error=record.get('error'))
                raise RuntimeError('perf capture failed: '+task)
            out=ROOT/record['raw']/'perf/out'
            state['tasks'][task]=dict(status='passed',raw=record['raw'],out=str(out.relative_to(ROOT)),
                launch_sha256=sha(ROOT/record['raw']/'launch.json'),
                collection_sha256=sha(out/'collection.json'),profile_sha256=sha(out/'profile.json'),
                function_qualification=record['modes']['perf']['collection']['function_qualification'])
            write(path,state)
        state['status']='passed';state['active_task']=None
    except BaseException as exc:
        state.update(status='failed',error=f'{type(exc).__name__}: {exc}')
    finally:
        state['not_started']=[task for task in TASKS if task not in state['tasks']]
        state['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();write(path,state)
    summarize(path,report)
    return 0 if state['status']=='passed' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['collect','summarize'])
    parser.add_argument('--campaign-dir',type=Path,required=True)
    parser.add_argument('--report-dir',type=Path,required=True)
    args=parser.parse_args()
    if args.action=='collect':raise SystemExit(collect(args.campaign_dir,args.report_dir))
    summarize(args.campaign_dir/'campaign.json',args.report_dir)
