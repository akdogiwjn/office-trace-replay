"""Host launcher for one selected dataset's native hotspot capture."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
DOCKER=['docker','--host','unix:///var/run/docker.sock']


def write(path,data):
    path=Path(path); temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n'); temp.replace(path)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1048576),b''): h.update(chunk)
    return h.hexdigest()


def report(raw,state,*,suffix='',profile_path=None):
    profile_path=Path(profile_path) if profile_path else raw/'out/profile.json'
    profile=json.loads(profile_path.read_text())
    # Derive diagnostics from raw text, retaining the original capture record.
    from native_profile import loss_diagnostics
    profile['capture_quality']['loss_recheck']=loss_diagnostics(
        (raw/'out/perf-record.stderr').read_text(),(raw/'out/perf-report.txt').read_text())
    profile['capture_quality'].pop('report_lost_lines',None)
    assert profile['capture_quality']['loss_recheck']['aggregated_sample_events']==profile['total_samples']
    target=HERE/'reports'/(raw.name+suffix)
    target.mkdir(parents=True,exist_ok=False)
    write(target/'profile.json',profile)
    write(target/'evidence.json',dict(raw_directory=str(raw.relative_to(ROOT)),
        launch_sha256=sha(raw/'launch.json'),profile_sha256=sha(profile_path),
        source_profile=str(profile_path.relative_to(ROOT)),
        index_sha256=sha(raw/'out/sha256-index.json'),image_id=state['actual_image_id'],
        source_files=state['measurement_source_sha256'],
        derived_profile_sha256=sha(target/'profile.json'),report_generator_sha256=sha(Path(__file__)),
        diagnostic_parser_sha256=sha(HERE/'native_profile.py')))
    dataset=state['dataset_id']
    title={'irs_w4':'IRS W-4','sba1919':'SBA 1919','hr_metro':'HR Metro'}[dataset]
    scale='N=10，' if dataset in ('irs_w4','sba1919') else ''
    lines=[f'# {title} 热点采集','',
           f'当前 Agent 轨迹版，{scale}一轮。新旧对比另见汇总报告。',
           '',f"实际镜像：`{state['actual_image_id']}`。循环执行及业务验证成功。",
           '',f"正式循环 ROI：{profile['roi_samples']:,} 个样本，period 合计 {profile['roi_period']:,}。",
           '', '以下均以完整 ROI 的用户态 `cycles:u` period 为分母，未知项未从分母排除。不是整轮 user+sys CPU 时间占比。',
           '', '## 脚本与进程','', '| 实际脚本/程序 | ROI 周期占比 |','|---|---:|']
    for item in profile['processes']:
        lines.append(f"| `{item['script']}` | {item['share_roi']:.2%} |")
    lines+=['','## 原生库','', '| DSO | ROI 周期占比 |','|---|---:|']
    for item in profile['libraries'][:15]:
        lines.append(f"| `{item['dso']}` | {item['share_roi']:.2%} |")
    lines+=['','## Top-20 物理叶函数','', '| DSO | 函数 | ROI 周期占比 |','|---|---|---:|']
    for item in profile['functions'][:20]:
        lines.append(f"| `{Path(item['dso']).name}` | `{item['function'].replace('|', '&#124;')}` | {item['share_roi']:.2%} |")
    lines+=['','## 带脚本上下文的 Top-20 函数','', '| 实际脚本/程序 | DSO | 函数 | ROI 周期占比 |','|---|---|---|---:|']
    for item in profile['contexts'][:20]:
        lines.append(f"| `{item['script']}` | `{Path(item['dso']).name}` | `{item['function'].replace('|', '&#124;')}` | {item['share_roi']:.2%} |")
    q=profile['quality']
    losses=profile['capture_quality']['loss_recheck']
    lines+=['','## 质量和边界','',
        f"- 空栈 {q['empty_stack_share']:.3%}；未知叶 DSO {q['unknown_leaf_dso_share']:.3%}；未知叶符号 {q['unknown_leaf_symbol_share']:.3%}。这些类别可能重叠。",
        f"- 无法关联脚本的 period：{q['unresolved_script_share']:.3%}；首次观察前 10 ms 内的推断归属：{q['first_observation_inference_share']:.3%}。身份来自 10 ms 名义间隔的 /proc 观察，并非精确 exec 事件。",
        '- 完整栈导出与无栈计数导出按 PID/TID/纳秒时间/period/event 的多重集合逐样本核对；ROI 内外 period 守恒。',
        '- 按 CLOCK_MONOTONIC 的实际 ROI 标记裁剪；循环外预检、归档和哈希不计入主表。采集器及 monitor 不在 perf 的目标子树中。',
        '- 同一镜像内 `--no-inline` 导出物理调用链；未知叶节点不继承调用者符号。',
        '- 用户态采样不包含内核 CPU 和阻塞等待；未进行开销校准或重复稳定性检验，也未采集 py-spy。',
        f"- perf 聚合统计 SAMPLE={losses['aggregated_sample_events']}、LOST 记录={losses['reported_lost_records']}、LOST_SAMPLES 记录={losses['reported_lost_sample_records']}；record 日志报告 lost chunks={losses['perf_record_reported_lost_chunks']}。这些诊断不构成采集绝对无损的证明。",
        '- 显示 0.00% 仅表示采样权重很小或未获得明显采样，不表示脚本未执行或实际 CPU 为零。',
        '- perf lost/符号化警告原文保存在 profile.json 的 capture_quality 与 raw 日志；其 ROI 归属未知，不换算成周期权重。',
        '',f"原始证据：`{raw.relative_to(ROOT)}`；停止容器：`{state['container_id']}`。"]
    (target/'report.md').write_text('\n'.join(lines)+'\n')
    return str(target.relative_to(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',default='office-trace-replay:agent-traces')
    parser.add_argument('--dataset',choices=['irs_w4','sba1919','hr_metro'],default='irs_w4')
    args=parser.parse_args()
    dataset=args.dataset
    qualified=json.loads((ROOT/'reports/image-qualification-agent-traces.json').read_text())
    for name,expected in qualified['file_hashes'].items():
        if sha(ROOT/name)!=expected: raise ValueError('qualified runtime source changed: '+name)
    inspected=json.loads(subprocess.check_output(DOCKER+['image','inspect',args.image],text=True))[0]
    if inspected['Id']!=qualified['image_id']: raise ValueError('image tag differs from qualified image')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    raw=HERE/'raw'/(dataset.replace('_','-')+'-native-pilot-'+stamp)
    raw.mkdir(parents=True,exist_ok=False)
    out=raw/'out'; out.mkdir()
    evidence=raw/'evidence'; evidence.mkdir()
    write(evidence/'image-inspect.json',inspected)
    write(evidence/'launch-plan.json',dict(dataset_locks={dataset:sha(ROOT/'agent/datasets'/dataset/'lock.json')},
                                          loops=1,selected_datasets=[dataset],runtime='document-oe'))
    state=dict(status='in_progress',actual_image_id=inspected['Id'],dataset_id=dataset,loops=1,
               measurement_source_sha256={p.name:sha(p) for p in sorted(HERE.glob('*.py'))},
               container_started=False,raw_directory=str(raw.relative_to(ROOT)))
    source_copy=evidence/'measurement-source'; source_copy.mkdir()
    for p in HERE.glob('*.py'): shutil.copy2(p,source_copy/p.name)
    shutil.copy2(ROOT/'reports/image-qualification-agent-traces.json',evidence/'image-qualification.json')
    write(raw/'launch.json',state)
    argv=DOCKER+['container','create','--name','office-hotspot-'+dataset.replace('_','-')+'-'+stamp.lower(),
        '--network','none','--cpuset-cpus','0-9','--cap-add','PERFMON','--cap-add','SYS_PTRACE',
        '--security-opt','seccomp=unconfined',
        '--mount',f'type=bind,source={HERE},target=/measurement,readonly',
        '--mount',f'type=bind,source={out},target=/results',
        '--mount',f'type=bind,source={evidence},target=/evidence,readonly',
        '--entrypoint','/opt/document-bench/.venv/bin/python',inspected['Id'],
        '/measurement/collect_native.py','--dataset',dataset,'--output','/results']
    state['create_argv']=argv
    print('Pilot directory: '+str(raw),flush=True)
    try:
        cid=subprocess.check_output(argv,text=True,timeout=60).strip(); state['container_id']=cid
        before=json.loads(subprocess.check_output(DOCKER+['container','inspect',cid],text=True))
        write(evidence/'container-inspect.before.json',before)
        assert before[0]['Image']==inspected['Id'] and before[0]['HostConfig']['NetworkMode']=='none'
        assert all(m['Destination'] not in ('/opt/office-trace-replay','/opt/document-bench') for m in before[0]['Mounts'])
        state['container_started']=True; write(raw/'launch.json',state)
        with (raw/'container.log').open('x') as log:
            started=subprocess.run(DOCKER+['container','start','--attach',cid],stdout=log,stderr=subprocess.STDOUT)
        after=json.loads(subprocess.check_output(DOCKER+['container','inspect',cid],text=True))
        write(evidence/'container-inspect.after.json',after)
        state.update(docker_start_returncode=started.returncode,container_state=after[0]['State'])
        if started.returncode or after[0]['State']['ExitCode']:
            raise RuntimeError('pilot failed; inspect preserved collection.json and container.log')
        collection=json.loads((out/'collection.json').read_text())
        if collection['status']!='success': raise RuntimeError('collection did not complete')
        if collection['actual_image_id']!=inspected['Id']: raise ValueError('runner image identity differs')
        index=json.loads((out/'sha256-index.json').read_text())
        # Read as container root, including artifacts intentionally created 0600.
        code='''import hashlib,json
from pathlib import Path
r=Path('/archive'); d=json.loads((r/'sha256-index.json').read_text()); n=0
for item in d['files']:
 p=r/item['path']; h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 assert p.stat().st_size==item['size'] and h.hexdigest()==item['sha256'],str(p)
 n+=1
print(n)
'''
        checked=subprocess.check_output(DOCKER+['run','--rm','--network','none','--read-only',
            '--mount',f'type=bind,source={out},target=/archive,readonly',
            '--entrypoint','/opt/document-bench/.venv/bin/python',inspected['Id'],'-c',code],text=True)
        state.update(status='success',indexed_files_checked=int(checked),collection_sha256=sha(out/'collection.json'))
    except Exception as exc:
        state.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        write(raw/'launch.json',state)
    result=report(raw,state)
    write(HERE/'reports/latest-pilot.json',dict(status='success',report=result,raw=str(raw.relative_to(ROOT)),image_id=inspected['Id']))
    write(HERE/f'reports/latest-{dataset}.json',dict(status='success',dataset_id=dataset,report=result,
          raw=str(raw.relative_to(ROOT)),image_id=inspected['Id']))
    print(json.dumps(dict(status='success',report=result,container_id=state['container_id'])),flush=True)


if __name__=='__main__': main()
