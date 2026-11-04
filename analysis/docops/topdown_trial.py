"""One unified-environment Topdown capture per task, ten loops per capture."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import sys
import traceback

from pilot import HERE, ROOT, launch, sha, write
from quality import workload_records

sys.path.append(str(ROOT/'analysis/topdown'))
from time_series import parse_intervals
from summarize import METRICS

TASKS=('031','037','pdfwf005','001','003','009','013','014','016','021','026','029')
FORMATS={t:f for f,items in {'word':('001','003','009'),
    'excel':('013','014','016'),'ppt':('021','026','029'),
    'pdf':('031','037','pdfwf005')}.items() for t in items}


def summarize_capture(out,task):
    state=json.loads((out/'collection.json').read_text())
    if state['status']!='passed' or state['mode']!='topdown' or state['task']!=task:
        raise ValueError('Topdown capture is not successful')
    workload_records(out,task,10)
    data=parse_intervals((out/'devkit.stdout.txt').read_text())
    if data['final']['metrics']!=state['metrics']:
        raise ValueError('interval ALL and collection metrics differ')
    if not data['points'] or data['final']['cycles']<=0 or data['final']['instructions']<=0:
        raise ValueError('no counted Topdown data')
    return dict(status='passed',task=task,format=FORMATS[task],
        out=str(out.relative_to(ROOT)),record_sha256=sha(out/'collection.json'),
        stdout_sha256=sha(out/'devkit.stdout.txt'),interval_points=len(data['points']),
        pmu_reads=(out/'devkit.stdout.txt').read_text().count('time of PmuRead:'),
        metrics=state['metrics'],idle_pct=state['cpu_window']['idle_pct'],
        final_cycles=data['final']['cycles'],final_instructions=data['final']['instructions'],
        roi_seconds=state['roi_seconds'],profiler_envelope_seconds=state['profiler_envelope_seconds'],
        outside_workflow_envelope_seconds=state['outside_workflow_envelope_seconds'],
        interval_counter_deltas=data['interval_counter_deltas'],interval_data=data,
        arithmetic=json.loads((out/'topdown-summary.json').read_text())['arithmetic'])


def emit_report(state,folder):
    folder.mkdir(parents=True,exist_ok=False)
    write(folder/'comparison.json',state)
    lines=['# DocOps 统一环境：十二任务 Topdown 首轮采集','',
        f"状态：{state['status']}；成功 {len(state['completed'])}/12。实际镜像 `{state['image_id']}`。",'',
        '每任务一次独立 Topdown 采集，内部回放十轮；不是十次独立重复。只测 Topdown，没有重新采 perf。',
        'DevKit 26.0.RC1 的最小采集间隔为 1 秒；使用 `devkit tuner top-down -c 0-7 -L 0 -i 1 -l 0`。',
        '业务绑 CPU 0–7，控制器及准备、归档绑 CPU 9。PMU 为按核完整包络，包含就绪、轮间和结束间隙；不冒充精确的进程 ROI。',
        '指标使用 ALL 最终累计报告；逐点数据仅用于过程曲线，不取逐点百分比的简单平均替代 ALL。', '',
        '| 任务 | 格式 | workflow 秒 | PMU 包络秒 | 过程点数 | IPC | Bad Spec. | Frontend | Backend | Retiring |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for task,t in sorted(state['completed'].items()):
        m=t['metrics']
        lines.append(f"| {task} | {t['format']} | {t['roi_seconds']:.2f} | {t['profiler_envelope_seconds']:.2f} | {t['interval_points']} | {m['IPC']:.2f} | {m['Bad Speculation']:.2f} | {m['Frontend Bound']:.2f} | {m['Backend Bound']:.2f} | {m['Retiring']:.2f} |")
    lines+=['','完整九项指标、独立窗口 idle、逐点计数、层级与计数核验、经验公式诊断及证据哈希见 comparison.json。',
        '过程点数是 DevKit 实际输出的编号报告数。1 秒是请求间隔，不据此假定实际每秒恰好产生一张报告。',
        '当前每任务仅一次独立采集，不计算 CV 或声称重复稳定性。原始未计数事件、公式打印差异和完整采集包络如实保留。',
        '本批仅使用统一 openEuler 镜像，不混入旧 Debian Topdown；后续可与统一环境已补符号的 perf 结果关联。','']
    (folder/'report.md').write_text('\n'.join(lines))
    write(folder/'analysis-build.json',dict(source_sha256=state['source_sha256'],
        campaign=state['campaign_path'],campaign_sha256=sha(ROOT/state['campaign_path']),
        files={p.name:sha(p) for p in folder.iterdir() if p.is_file()}))


def run(folder,report):
    os.sched_setaffinity(0,{9})
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/'campaign.json'
    if path.exists():raise ValueError('refuse to reuse a campaign')
    candidate=json.loads((ROOT/'docops/docker/current-image.json').read_text())
    if candidate['runtime_profile']!='seven-case-openeuler-unified' or candidate['functional_summary']['status']!='passed':
        raise ValueError('unified functional trials not passed')
    sources=folder/'source';sources.mkdir()
    for p in HERE.glob('*.py'):shutil.copy2(p,sources/p.name)
    for name in ('time_series.py','summarize.py'):
        shutil.copy2(ROOT/'analysis/topdown'/name,sources/('topdown_'+name))
    state=dict(schema='docops-unified-topdown-campaign-v1',status='running',
        image_id=candidate['candidate_id'],candidate_snapshot=candidate,
        planned_tasks=list(TASKS),captures_per_task=1,loops_per_capture=10,
        nominal_interval_seconds=1,devkit_minimum_interval_seconds=1,
        workload_cpus='0-7',controller_cpu=9,perf_collected=False,
        completed={},not_started=list(TASKS),active_task=None,
        started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        campaign_path=str(path.relative_to(ROOT)),
        source_sha256={p.name:sha(p) for p in sources.iterdir()},
        stop_file=str((folder/'STOP').relative_to(ROOT)))
    write(path,state)
    try:
        for task in TASKS:
            if (folder/'STOP').exists():
                state['status']='stopped';break
            state['active_task']=task;write(path,state)
            print('TOPDOWN START '+task,flush=True)
            result=launch(task,10,['topdown'],return_record=True)
            if result['status']!='passed' or result['image_id']!=state['image_id']:
                state['failed_task']=dict(task=task,raw=result['raw'],error=result.get('error'))
                raise RuntimeError('Topdown capture failed: '+task)
            out=ROOT/result['raw']/'topdown/out'
            row=summarize_capture(out,task)
            row.update(launch_path=str((ROOT/result['raw']/'launch.json').relative_to(ROOT)),
                launch_sha256=sha(ROOT/result['raw']/'launch.json'),
                container_id=result['modes']['topdown']['container_id'],
                archive_files_verified=result['modes']['topdown']['indexed_files_verified'])
            state['completed'][task]=row;state['active_task']=None
            state['not_started']=[t for t in TASKS if t not in state['completed']]
            write(path,state)
            print(f"TOPDOWN DONE {task}: {row['interval_points']} interval points, IPC={row['metrics']['IPC']:.2f}",flush=True)
        else:state['status']='passed'
    except BaseException as exc:
        state.update(status='failed',error=f'{type(exc).__name__}: {exc}',traceback=traceback.format_exc())
    finally:
        state['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();write(path,state)
    emit_report(state,report)
    print('REPORT '+str(report/'report.md'),flush=True)
    return 0 if state['status']=='passed' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    raise SystemExit(run(args.campaign.resolve(),args.report.resolve()))
