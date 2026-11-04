"""Offline enrichment of existing unified-image captures, with supplemental ELF mounts."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import traceback

from campaign import check_archive
from pilot import DOCKER, HERE, ROOT, sha, write


def prepare_symbols(search, destination):
    record = json.loads((search/'search-results.json').read_text())
    rows = []
    for package in record['packages']:
        if package['status'] != 'verified':
            raise ValueError('unverified debug package')
        for item in package['targets']:
            source = search/item['path']
            build_id = item['runtime_build_id']
            if item['status'] != 'found_exact' or sha(source) != item['debug_sha256']:
                raise ValueError('debug file identity changed')
            notes = subprocess.check_output(['readelf','-n',str(source)],text=True)
            if 'Build ID: '+build_id not in notes:
                raise ValueError('debug build-id changed')
            relative = Path('.build-id')/build_id[:2]/(build_id[2:]+'.debug')
            target = destination/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
            rows.append(dict(status='downloaded',build_id=build_id,
                runtime_path=item['runtime_path'],path=str(relative),
                bytes=target.stat().st_size,sha256=sha(target),build_id_verified=True,
                package_url=package['url'],package_sha256=package['download_sha256']))
    write(destination/'index.json',dict(schema='docops-exact-unified-symbols-v1',
        search_record=str((search/'search-results.json').relative_to(ROOT)),
        search_record_sha256=sha(search/'search-results.json'),files=rows))
    return rows


def report(record, destination):
    destination.mkdir(parents=True,exist_ok=False)
    lines=['# DocOps 现有 perf 数据：离线补符号效果','',
        '同一批原始采样的补符号前后对比；没有重新运行任务、perf record 或 DevKit。','',
        '| 任务 | 格式 | 补前未解析周期 | 补后未解析周期 | 函数资格 |',
        '|---|---|---:|---:|---|']
    for task, row in sorted(record['tasks'].items()):
        if row['status'] != 'passed':
            lines.append(f'| {task} | — | — | — | 离线处理失败 |')
            continue
        lines.append(f"| {task} | {row['format']} | {100*row['quality_before']['unknown_leaf_symbol_share']:.2f}% | {100*row['quality_after']['unknown_leaf_symbol_share']:.2f}% | {row['function_qualification']['status']} |")
    lines += ['', '所有占比的分母为 workflow ROI 内完整 cycles:u 原始 sample period。未知项保留在分母中。',
        '每任务仍是原有一次独立采集、该次回放十轮；离线处理不增加重复数。',
        '使用采集时的同一镜像，以及 build-id 精确匹配的 12 个目标 ELF 调试文件。仅逐文件只读挂载补充符号，不遮蔽镜像原有调试目录。',
        '逐样本检查 key、物理叶地址及 DSO 不变，并核对样本数、ROI period、进程权重及 loss 记录。原始文件只读，前后 SHA256 一致。',
        'lxml 暂未找到精确匹配的额外符号；其余零散未知项如实保留。本次不改变原采集的 loss 和 ROI 边界。',
        '',f"[完整离线处理记录]({os.path.relpath(ROOT/record['record_path'], destination)})",'']
    (destination/'report.md').write_text('\n'.join(lines))
    write(destination/'comparison.json',record)
    write(destination/'analysis-build.json',dict(
        source_sha256=record['source_sha256'],
        enrichment_record_sha256=sha(ROOT/record['record_path']),
        output_sha256={p.name:sha(p) for p in destination.iterdir() if p.is_file()}))


def run(campaign, search, destination, report_dir):
    os.sched_setaffinity(0,{9})
    state=json.loads(campaign.read_text())
    lookup=json.loads((HERE/'processed/unified-symbol-check-20261103T1703Z/comparison.json').read_text())
    search_record=json.loads((search/'search-results.json').read_text())
    if state['status']!='passed' or state['image_id']!=search_record['image_id']:
        raise ValueError('capture/symbol image mismatch')
    if lookup['campaign_sha256']!=sha(campaign):
        raise ValueError('capture campaign changed')
    destination.mkdir(parents=True,exist_ok=False)
    sources=destination/'source';sources.mkdir()
    for name in ('recover_perf.py','quality.py','native_adapter.py','enrich_unified.py'):
        shutil.copy2(HERE/name,sources/name)
    for old,new in [('native_profile.py','native_profile.py'),('collect_native.py','native_capture_helpers.py')]:
        shutil.copy2(ROOT/'analysis/hotspots'/old,sources/new)
    symbols=destination/'symbols';symbols.mkdir()
    rows=prepare_symbols(search,symbols)
    record=dict(schema='docops-unified-offline-symbol-enrichment-v1',status='running',
        image_id=state['image_id'],campaign=str(campaign.relative_to(ROOT)),campaign_sha256=sha(campaign),
        workload_rerun=False,perf_record_rerun=False,topdown_rerun=False,
        loops_per_original_capture=state['loops_per_capture'],
        source_sha256={p.name:sha(p)for p in sources.iterdir()},
        symbol_index_sha256=sha(symbols/'index.json'),tasks={},
        record_path=str((destination/'enrichment.json').relative_to(ROOT)),
        started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    path=destination/'enrichment.json';write(path,record)
    # Small captures expose the dominant PNG/ImageMagick gaps quickly.
    order=sorted(state['tasks'],key=lambda t:(ROOT/state['tasks'][t]['out']/'perf.data').stat().st_size)
    record['task_order']=order
    try:
        for task in order:
            item=state['tasks'][task];original=ROOT/item['out']
            if sha(original/'profile.json')!=item['profile_sha256']:
                raise ValueError('original profile changed: '+task)
            print('VERIFY ORIGINAL '+task,flush=True)
            original_archive=check_archive(original)
            builds={line.split(' ',1)[1]:line.split(' ',1)[0] for line in (original/'buildids.txt').read_text().splitlines()}
            for row in rows:
                if row['runtime_path'] in builds and builds[row['runtime_path']]!=row['build_id']:
                    raise ValueError('capture ELF build-id differs: '+row['runtime_path'])
            folder=destination/task;folder.mkdir();out=folder/'out';out.mkdir()
            argv=DOCKER+['create','--name',f'docops-offline-{task}-{destination.name}'.lower(),
                '--network','none','--cpuset-cpus','9',
                '--mount',f'type=bind,source={original},target=/original,readonly',
                '--mount',f'type=bind,source={sources},target=/opt/docops-measurement,readonly',
                '--mount',f'type=bind,source={symbols},target=/analysis-symbols,readonly',
                '--mount',f'type=bind,source={out},target=/results']
            for row in rows:
                argv+=['--mount',f"type=bind,source={symbols/row['path']},target=/usr/lib/debug/{row['path']},readonly"]
            argv+=['--entrypoint','python3',state['image_id'],'-B',
                '/opt/docops-measurement/recover_perf.py','--allow-limited','--symbols','/analysis-symbols']
            cid=subprocess.check_output(argv,text=True,timeout=60).strip()
            before=json.loads(subprocess.check_output(DOCKER+['inspect',cid],text=True))[0]
            write(folder/'container-before.json',before)
            if before['Image']!=state['image_id'] or before['HostConfig']['NetworkMode']!='none':
                raise ValueError('wrong offline image/network')
            if any(m['RW'] for m in before['Mounts'] if m['Destination']!='/results'):
                raise ValueError('writable offline inputs')
            record['active_task']=task;write(path,record)
            print('OFFLINE EXPORT '+task,flush=True)
            with (folder/'container.log').open('x') as log:
                try:
                    cp=subprocess.run(DOCKER+['start','-a',cid],stdout=log,stderr=subprocess.STDOUT,timeout=480)
                except BaseException:
                    subprocess.run(DOCKER+['stop','-t','3',cid],capture_output=True,timeout=15)
                    raise
            after=json.loads(subprocess.check_output(DOCKER+['inspect',cid],text=True))[0]
            write(folder/'container-after.json',after)
            value=json.loads((out/'recovery-record.json').read_text())
            record['tasks'][task]=dict(status=value['status'],format=lookup['tasks'][task]['format'],
                out=str(out.relative_to(ROOT)),container_id=cid,original_archive=original_archive,
                record_sha256=sha(out/'recovery-record.json'))
            if cp.returncode or after['State']['ExitCode'] or value['status']!='passed':
                write(path,record);raise RuntimeError('offline export failed: '+task+' '+str(value.get('error')))
            if not value['original_evidence_unchanged']:
                raise ValueError('original evidence changed')
            record['tasks'][task].update(quality_before=value['quality_before'],quality_after=value['quality_after'],
                function_qualification=value['function_qualification'],
                roi_samples=value['roi_samples'],roi_period=value['roi_period'],
                archive=check_archive(out),profile_sha256=sha(out/'profile.json'))
            write(path,record)
            print(f"DONE {task}: {value['quality_before']['unknown_leaf_symbol_share']*100:.3f}% -> {value['quality_after']['unknown_leaf_symbol_share']*100:.3f}%",flush=True)
        record['status']='passed';record['active_task']=None
    except BaseException as exc:
        record.update(status='failed',error=f'{type(exc).__name__}: {exc}',traceback=traceback.format_exc())
    finally:
        record['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        record['not_processed']=[t for t in order if t not in record['tasks']]
        write(path,record)
    report(record,report_dir)
    print('REPORT '+str(report_dir/'report.md'),flush=True)
    return 0 if record['status']=='passed' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',type=Path,required=True)
    parser.add_argument('--search',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    raise SystemExit(run(*(p.resolve() for p in (args.campaign,args.search,args.output,args.report))))
