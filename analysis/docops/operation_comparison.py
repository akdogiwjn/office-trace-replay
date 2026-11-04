"""Publish an append-only task-operation comparison from qualified, saved data."""
import argparse
from collections import Counter
import hashlib
import itertools
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE_CONFIG='analysis/hotspots/comparison-inputs-pdf5-20261027.json'
PERF_CAMPAIGN='analysis/docops/raw/unified-symbol-check-20261103T1703Z/campaign.json'
ENRICHMENT='analysis/docops/raw/unified-symbol-check-20261103T1703Z/offline-symbol-enrichment-v1/enrichment.json'
TOPDOWN='analysis/docops/raw/unified-topdown-20261104-v1/campaign.json'
DEFAULT_OUTPUT='analysis/docops/processed/task-operation-expansion-20261104'
PUBLICATION='docs/evidence/task-operation-extension.json'
BEGIN='<!-- BEGIN DOCOPS TASK OPERATION EXTENSION -->'
END='<!-- END DOCOPS TASK OPERATION EXTENSION -->'
BOUNDS=('Bad Speculation','Frontend Bound','Backend Bound','Retiring')
METRICS=('IPC',*BOUNDS,'Core Bound','Memory Bound','Fetch Latency Bound','Fetch Bandwidth Bound')
GROUPS={'PDF':('031','037','pdfwf005'),'Excel':('013','014','016'),
        'Word':('001','003','009'),'PPT':('021','026','029')}
NAMES={'001':'受控文档发布修复','003':'公开记录元数据清理','009':'事件手册发布',
       '013':'采购投标评审发布','014':'灾害补助公开发布','016':'预测模型情景级联',
       '021':'庇护所无障碍整改','026':'气候披露图表重建','029':'季度业务回顾发布',
       '031':'听证材料包扁平化发布','037':'公交绕行材料修复','pdfwf005':'结算材料包重建'}
FLOWS={
 '001':'create_packet.py；render_docx.py；结构与渲染检查',
 '003':'build_public_packet.py；audit_public_packet.py；render_docx.py',
 '009':'build_incident_manual_publication.py；render_docx.py；validate_incident_manual_publication.py',
 '013':'build_public_bid_workbook.py；recalc.py；verify_public_bid_workbook.py；PDF／拼图',
 '014':'build_disaster_release_v1.py；recalc.py；finalize_disaster_release_ooxml_v3.py；validate_disaster_release_v1.py／渲染',
 '016':'build_forecast_dashboard_v1.py；recalc.py；测试副本切换情景并重算',
 '021':'build_public_shelter_briefing.py；validate_public_shelter_briefing.py；soffice.py／图片／拼图',
 '026':'build_climate_disclosure.py；转 PDF／图片；qa_climate_disclosure.py',
 '029':'build_release_deck.py；validate_release_deck.py；转 PDF／图片',
 '031':'build_public_packet.py；PDF 渲染；validate_public_packet.py',
 '037':'build_bus_detour_packet.py；PDF 渲染；validate_bus_detour_packet.py',
 'pdfwf005':'rebuild_closeout_binder.py；PDF 检查；图片／拼图／诊断'}


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)


def resolved(symbol):
    import re
    return symbol not in ('[unknown]','[no-frame]') and not re.fullmatch(r'0x[0-9a-fA-F]+|[0-9a-fA-F]{12,}',symbol)


def functions(profile):
    counts=Counter()
    if sum(f['period'] for f in profile['functions'])!=profile['roi_period']:
        raise ValueError('function periods do not conserve the complete ROI')
    for f in profile['functions']:
        if resolved(f['function']) and f['dso']!='[unknown]':
            counts[(Path(f['dso']).name,f['function'])]+=f['period']
    return [dict(library=k[0],function=k[1],period=v,share_roi=v/profile['roi_period'])
            for k,v in sorted(counts.items(),key=lambda x:(-x[1],x[0]))]


def key(row):return row['library'],row['function']


def library(dso):
    name=Path(dso).name
    if 'libreoffice' in dso:return 'LibreOffice'
    for token,label in [('libpython','Python'),('libz.so','zlib'),('libpng','PNG'),
        ('libpoppler','Poppler'),('libMagick','ImageMagick'),('libjpeg','JPEG'),
        ('etree.','lxml'),('_elementpath.','lxml'),('_imaging.','Pillow'),
        ('libexpat','Expat'),('pyexpat.','Expat'),('_elementtree.','ElementTree'),
        ('libpixman','pixman'),('libfontconfig','fontconfig'),('libcairo','cairo'),
        ('libc.so','libc'),('ld-linux','loader')]:
        if token in name:return label
    return name


def compare_pair(base,target):
    a,b=base['functions'][:10],target['functions'][:10]
    sa,sb={key(f) for f in a},{key(f) for f in b}
    if len(sa)!=10 or len(sb)!=10:
        raise ValueError('comparison requires ten distinct resolved functions per case')
    am,bm=base['metrics'],target['metrics']
    av,bv=([m[k] for k in BOUNDS] for m in (am,bm))
    norm=math.sqrt(sum(x*x for x in av)*sum(x*x for x in bv))
    if not norm:raise ValueError('zero Bound vector')
    delta={k:bm[k]-am[k] for k in METRICS}
    return dict(baseline=base['task'],target=target['task'],
        shared_top10_count=len(sa&sb),jaccard=len(sa&sb)/len(sa|sb),
        shared_top10=[dict(library=k[0],function=k[1]) for k in sorted(sa&sb)],
        baseline_top10_share_in_baseline=sum(f['share_roi'] for f in a),
        baseline_top10_share_in_target=sum(f['share_roi'] for f in target['functions'] if key(f) in sa),
        target_top10_share=sum(f['share_roi'] for f in b),
        metrics_delta=delta,ipc_relative_change_pct=100*delta['IPC']/am['IPC'],
        bound_total_variation_pp=.5*sum(abs(delta[k]) for k in BOUNDS),
        maximum_bound_delta_pp=max(abs(delta[k]) for k in BOUNDS),
        bound_cosine_auxiliary=sum(x*y for x,y in zip(av,bv))/norm,
        new_target_top10_not_in_baseline_top10=[f for f in b if key(f) not in sa])


def gather():
    bindings={}
    def read(rel,expected=None):
        digest=sha(ROOT/rel)
        if expected and digest!=expected:raise ValueError('input hash mismatch: '+rel)
        bindings[rel]=digest
        return json.loads((ROOT/rel).read_text())
    config=read(BASE_CONFIG);joint=read(config['joint_comparison']['path'],config['joint_comparison']['sha256'])
    baselines={}
    for name,profile_key,stats_key in [('OPM','opm-n10','opm'),('TLC','tlc','tlc')]:
        ref=config['profiles'][profile_key];raw=read(ref['path'],ref['sha256'])
        baselines[name]=make_case(name,'PDF' if name=='OPM' else 'Excel',raw,
            {m:joint['statistics'][stats_key]['statistics'][m]['mean'] for m in METRICS})
        baselines[name]['repeats']=5
    perf=read(PERF_CAMPAIGN);enriched=read(ENRICHMENT);td=read(TOPDOWN)
    expected={t for ids in GROUPS.values() for t in ids}
    if any(x['status']!='passed' for x in (perf,enriched,td)):
        raise ValueError('incomplete measurement campaign')
    if any(set(x)!=expected for x in (perf['tasks'],enriched['tasks'],td['completed'])):
        raise ValueError('expected exactly twelve DocOps tasks')
    if len({x['image_id'] for x in (perf,enriched,td)})!=1:
        raise ValueError('DocOps image mismatch')
    if enriched['campaign_sha256']!=sha(ROOT/PERF_CAMPAIGN):raise ValueError('unbound enrichment')
    if td['candidate_snapshot']['base_image_id']!=joint['image_id']:
        raise ValueError('unified runtime is not based on the measured seven-case image')
    tasks={}
    for fmt,ids in GROUPS.items():
        for task in ids:
            er=enriched['tasks'][task];out=er['out'];raw=read(out+'/profile.json',er['profile_sha256'])
            recovery=read(out+'/recovery-record.json',er['record_sha256'])
            if recovery['status']!='passed' or not recovery['original_evidence_unchanged']:
                raise ValueError('invalid enrichment')
            row=td['completed'][task]
            collected=read(row['out']+'/collection.json',row['record_sha256'])
            if collected['counts']!=dict(requested=10,completed=10,successes=10,failures=0):
                raise ValueError('unsuccessful Topdown workload')
            if collected['metrics']!=row['metrics']:raise ValueError('Topdown metrics changed')
            textpath=row['out']+'/devkit.stdout.txt'
            if sha(ROOT/textpath)!=row['stdout_sha256']:raise ValueError('Topdown source changed')
            bindings[textpath]=row['stdout_sha256']
            if any(abs(d)>1 for d in row['interval_counter_deltas'].values()):
                raise ValueError('interval and ALL counts differ')
            case=make_case(task,fmt,raw,collected['metrics'])
            recipe=read('docops/payload/tasks/'+task+'/recipe.json')
            case.update(name=NAMES[task],script_flow=FLOWS[task],source_run_id=recipe['source_run_id'],
                historical_score=recipe['historical_score'],recipe_steps=recipe['steps'],
                source_review=recipe.get('review'),source_provenance=recipe.get('provenance'),
                workload_loops=10,independent_captures_per_mode=1,
                interval_data=row['interval_data'],interval_points=row['interval_points'],
                topdown_envelope_seconds=row['profiler_envelope_seconds'],
                topdown_workflow_seconds=row['roi_seconds'],idle_pct=row['idle_pct'],
                topdown_arithmetic=row['arithmetic'],capture_quality=raw['capture_quality'],
                evidence=dict(profile=out+'/profile.json',topdown_record=row['out']+'/collection.json',
                    topdown_stdout=textpath,source_run_id=recipe['source_run_id']))
            tasks[task]=case
    return dict(schema='docops-task-operation-expansion-v1',baselines=baselines,tasks=tasks,
        comparisons={task:{b:compare_pair(base,t) for b,base in baselines.items()} for task,t in tasks.items()},
        same_format_pairs=[compare_pair(tasks[a],tasks[b]) for ids in GROUPS.values() for a,b in itertools.combinations(ids,2)],
        reference_image_id=joint['image_id'],docops_image_id=td['image_id'],
        software=td['candidate_snapshot']['environment'],input_bindings=bindings,
        function_identity='exact physical leaf function name plus DSO basename; no fuzzy matching or clone merging',
        topdown_primary='metric values and percentage-point deltas; half L1 of four top-level Bounds',
        cosine_role='auxiliary shape indicator, no high/medium/low label or 0.99 rule',
        cross_batch_scope='Reference five independent runs versus one DocOps capture with ten replay loops; recorded ROI boundaries differ; descriptive workflow comparison, not isolated causal attribution to one operation.',
        measurement_rerun=False)


def make_case(task,fmt,raw,metrics):
    libs=Counter();modules=Counter()
    for row in raw['libraries']:
        libs[library(row['dso'])]+=row['period']
        if 'libreoffice' in row['dso']:modules[Path(row['dso']).name]+=row['period']
    return dict(task=task,format=fmt,functions=functions(raw),metrics=metrics,
        processes=raw['processes'],quality=raw['quality'],roi_period=raw['roi_period'],roi_samples=raw['roi_samples'],
        libraries=[dict(library=k,period=v,share_roi=v/raw['roi_period']) for k,v in libs.most_common()],
        libreoffice_modules=[dict(module=k,period=v,share_roi=v/raw['roi_period']) for k,v in modules.most_common()])


def table(headers,rows):
    def cell(v):return str(v).replace('|','&#124;').replace('\n',' ')
    return '\n'.join(['| '+' | '.join(map(cell,headers))+' |','|'+'---|'*len(headers),
                      *['| '+' | '.join(map(cell,row))+' |' for row in rows]])


def pct(x):return f'{100*x:.2f}%'


def short_function(f,limit=100):
    name=f['function'];name=name if len(name)<=limit else name[:limit-1]+'…'
    return '`'+name+'`'


def plot(result,out):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'none','svg.hashsalt':'docops-operation-v1'})
    colors=('#346a9f','#cf792d','#347d55','#b3464c')
    folder=out/'figures';folder.mkdir(exist_ok=True)
    figures={}
    for task,t in result['tasks'].items():
        points=t['interval_data']['points'];xs=[p['sample_index'] for p in points]
        fig,ax=plt.subplots(figsize=(11.2,3.98),layout='constrained')
        for metric,color in zip(BOUNDS,colors):
            ax.plot(xs,[p['metrics'][metric] for p in points],label=metric,color=color,marker='.',markersize=2,linewidth=1)
        ax.set(xlim=(1,max(2,len(xs))),ylim=(0,100),xlabel='Actual output point index',ylabel='Bound (%)',
            title=f'DocOps {task} | 1 capture, 10 replay loops | {len(xs)} points')
        ax.grid(alpha=.2);ax.legend(ncol=4,fontsize=9,loc='upper right')
        for ext in ('svg','png'):
            p=folder/f'{task}-bounds.{ext}';fig.savefig(p,dpi=130,metadata={'Date':None} if ext=='svg' else None)
            if ext=='svg':p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n')
            figures[str(p.relative_to(ROOT))]=sha(p)
        plt.close(fig)
        fig,axes=plt.subplots(3,3,figsize=(12,8),layout='constrained')
        for ax,metric in zip(axes.flat,METRICS):
            ax.plot(xs,[p['metrics'][metric] for p in points],color='#346a9f',marker='.',markersize=2,linewidth=1)
            ax.set(title=metric,xlabel='Output point',ylabel='IPC' if metric=='IPC' else '%');ax.grid(alpha=.2)
        fig.suptitle(f'DocOps {task}: every original output point; no per-point idle was recorded')
        for ext in ('svg','png'):
            p=folder/f'{task}-all-metrics.{ext}';fig.savefig(p,dpi=130,metadata={'Date':None} if ext=='svg' else None)
            if ext=='svg':p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n')
            figures[str(p.relative_to(ROOT))]=sha(p)
        plt.close(fig)
    return figures


def main_section(r,out):
    lines=['## 七、扩展任务操作：与原始 PDF/XLSX 基准比较','',
      '前六节保留原七例“跨行业输入”实验及其提出的场景扩展问题。本节接续这些问题，报告后续十二项 DocOps L3 的真实轨迹回放测量：在 PDF／Excel 中改变任务操作，并加入 Word／PPT，分别与原始 OPM／TLC 比较。',
      '**本节的主线是操作、工具链和热点函数如何变化，Topdown 用于描述这些工作流的流水线特征。** 四顶层 Bound 余弦作为辅助形状指标，不以超过 0.99 判定整体负载高度相似。','',
      '### 7.1 样本、轨迹与测量口径','',
      table(['任务组','本次操作覆盖','主要对照'],[
       ['PDF：031／037／pdfwf005','听证材料包发布、公交绕行材料修复、结算材料包重建','原始 PDF：OPM'],
       ['Excel：013／014／016','投标评审发布、灾害补助公开发布、预测模型情景级联','原始 XLSX：TLC'],
       ['Word：001／003／009','受控发布修复、元数据清理、事件手册发布','OPM、TLC 均比较'],
       ['PPT：021／026／029','无障碍整改、图表重建、季度业务回顾发布','OPM、TLC 均比较']]),'',
      '十二项任务采用已保存 Agent 轨迹中的最终有效依赖链。各任务独立冻结脚本、输入、Skill 和命令；内联命令保留为任务私有执行步骤，公共入口只负责调度、环境和归档。回放不调用模型，保留最终构建、必要修补、重算、渲染及原有检查。',
      '原始 Agent 内容判定与回放完成分开记录：来源中四项内容通过、八项未通过；本次十二项冻结工具链及采集均完成。逐项来源、历史判定与实际脚本见实验数据记录。','',
      table(['项目','原始 OPM／TLC','新增 DocOps'],[
       ['环境','原七例测量镜像；Python 3.12.3、LibreOffice 25.8.7.3','基于同一测量镜像；共用 Python、LibreOffice、Poppler 和 perf 版本，增加 docx／pptx／lxml／ImageMagick 等任务依赖'],
       ['重复与汇总','每路五次独立运行；热点合并原始 period，Topdown 取五次 ALL 均值','每项每路一次独立采集，内部十轮回放；热点按 ROI period，Topdown 取本次 ALL'],
       ['采集','perf：cycles:u、49 Hz、DWARF；DevKit：CPU 0–7、1 秒间隔','沿用相同工具参数，perf 与 DevKit 分开执行，控制器 CPU 9'],
       ['窗口','既有完整循环 ROI，包含 reset 和循环检查','perf 仅 workflow 区间并集，排除 reset、准备、归档；Topdown 为完整按核包络']]),'',
      '本节描述扩展工作流后的负载变化；新任务也带来输入组织和文档规模变化，结果不作为仅改变一个操作的控制实验。单次 DocOps 采集不套用原七例的五次稳定性结论。','',
      '### 7.2 实际脚本与工具软件栈','',
      '原 OPM 主要经过 PDF 字段检查、填写、Pillow 转换与渲染检查；TLC 主要经过工作簿检查、增强、openpyxl 保存、Calc 重算与缓存／CSV 验证。实际脚本与原生库组成如下，百分比均为完整 perf ROI 的叶 DSO 原始周期权重。','',
      table(['原始基准','主要脚本／进程','主要原生组件'],[[k,'; '.join(x['script']+' '+pct(x['share_roi']) for x in t['processes'][:4]),'; '.join(x['library']+' '+pct(x['share_roi']) for x in t['libraries'][:4])] for k,t in r['baselines'].items()])]
    for fmt,ids in GROUPS.items():
        lines+=['',table(['任务与操作','实际脚本／工具链','主要原生组件'],[
            [k+' '+NAMES[k],FLOWS[k],'; '.join(x['library']+' '+pct(x['share_roi']) for x in r['tasks'][k]['libraries'][:4])] for k in ids])]
    lines+=['','### 7.3 热点函数：原基准清单还覆盖哪些工作','',
      '函数按“物理叶函数完整名称＋DSO 文件名”精确匹配。共同 Top-10 数比较两份前十名单；“基准清单在新任务的占比”则统计原基准 Top-10 函数在新任务全部采样中的周期权重，匹配函数即使掉出新 Top-10 仍计入该清单占比。该占比只说明这十个具体函数的权重，不等于任务或切片覆盖率。','',
      table(['基准','原基准前五热点','原 Top-10 合计占比'],[[name,'; '.join(short_function(f)+' '+pct(f['share_roi']) for f in b['functions'][:5]),pct(sum(f['share_roi'] for f in b['functions'][:10]))] for name,b in r['baselines'].items()])]
    for fmt,ids in GROUPS.items():
        refs=('OPM',) if fmt=='PDF' else ('TLC',) if fmt=='Excel' else ('OPM','TLC')
        headers=['任务']+[title for ref in refs for title in (ref+' Top-10 共同数',ref+' 清单在新任务占比')]
        lines+=['',table(headers,[[k]+[v for ref in refs for v in (str(r['comparisons'][k][ref]['shared_top10_count'])+'/10',pct(r['comparisons'][k][ref]['baseline_top10_share_in_target']))] for k in ids]),'',
            table(['任务','新任务前三热点及周期占比'],[[k,'; '.join(short_function(f)+' '+pct(f['share_roi']) for f in r['tasks'][k]['functions'][:3])] for k in ids])]
    lines+=['',
      'PDF 扩展后，031／037 的 zlib 压缩与 PNG 编码更突出；pdfwf005 的 ImageMagick 横向、纵向滤波进入前列。它们与 OPM 保留解释执行和压缩共性，同时从表单填写扩展到材料包处理、渲染与拼图。',
      'Excel 的 013／014 加入较重的 PDF／图片交付路径，出现 zlib、PNG 与 ImageMagick 热点；016 更突出 Python 对象处理与 Calc。相同 XLSX 格式并不自动延续 TLC 的大型工作簿读写热点权重。',
      'Word 三项以压缩和 PNG 编码为主要热点，与 OPM 的压缩路径有共性；PPT 的 021／026 更突出 Poppler 栅格化和图像处理，029 则出现解释器、字典查找和 DrawingML 表格样式处理。共享 LibreOffice、Python 或 Poppler，仍可进入不同业务模块和函数路径。','',
      '### 7.4 Topdown：先看指标变化，再看辅助相似度','',
      '下表先列出基准五次均值（除 IPC 外为百分数），随后以新任务减去基准均值展示变化；完整十四个配置的九项指标见实验数据记录。','',
      table(['基准','IPC','Bad Spec.','Frontend','Backend','Retiring'],[[k,*[f"{b['metrics'][m]:.3f}" for m in METRICS[:5]]] for k,b in r['baselines'].items()]),'',
      'IPC 展示相对变化，其余展示百分点变化。Bound 总变差＝四顶层 Bound 绝对差之和的一半，范围为 0–100 个百分点；它描述四类分布的差异，不代表相同比例的 CPU 工作或函数发生了改变。']
    for fmt,ids in GROUPS.items():
        refs=('OPM',) if fmt=='PDF' else ('TLC',) if fmt=='Excel' else ('OPM','TLC')
        lines+=['',table(['任务','对照','IPC 变化','Frontend Δpp','Backend Δpp','Bound 总变差 pp'],[
            [k,ref,f"{r['comparisons'][k][ref]['ipc_relative_change_pct']:+.1f}%",f"{r['comparisons'][k][ref]['metrics_delta']['Frontend Bound']:+.2f}",f"{r['comparisons'][k][ref]['metrics_delta']['Backend Bound']:+.2f}",f"{r['comparisons'][k][ref]['bound_total_variation_pp']:.2f}"] for k in ids for ref in refs])]
    lines+=['',
      '031／037 相比 OPM，Frontend 分别下降约 9.18／7.84 pp，Backend 上升约 13.72／13.89 pp；016 相比 TLC，Frontend 上升约 5.30 pp，IPC 下降约 41.7%。这些差异通过指标原值和百分点变化能够直接看到，不被接近 1 的余弦值掩盖。',
      'PPT 021 与 029 的四维 Bound 余弦约 0.9955，但已解析 Top-10 仅共享两个函数。四维余弦反映粗粒度分布方向，不能代替对软件模块和具体函数的比较；详细余弦、Jaccard 与全部指标差值仍保留在数据记录。','',
      '### 7.5 逐点过程与本节结论','',
      '本批共保存 533 个真实过程点，每项 20–110 个。以下展示材料包、级联重算和两种演示文稿任务的四顶层 Bound 过程；完整十二项九指标曲线在实验数据记录。每项仍是一次独立采集，编号点不作为独立重复。']
    for task in ('031','016','021','029'):
        rel='../'+str((out/'figures'/f'{task}-bounds.svg').relative_to(ROOT))
        lines+=['',f'![扩展操作 {task} 的真实 Topdown 过程点]({rel})']
    lines+=['',
      '**跨行业输入与扩展任务操作回答两个层次的问题。** 原七例表明，保持任务形态时，更换行业输入仍延续主要热点；本节进一步表明，改变发布、渲染、重算或文稿对象处理流程后，即使文件格式或公共工具相同，具体热点和流水线特征也会变化。',
      'Word／PPT 已从待测场景进入实测覆盖。当前证据支持按实际操作和执行路径扩展负载：保留已有解释执行、XML、压缩等共性，并补充材料包、图像滤波、幻灯片栅格化、DrawingML 对象与情景重算等路径。连续长文档分页等机制是否成为主导，仍由具体任务的实测结果判断。',
      '[完整扩展实验记录](experimental-results.md#九扩展任务操作十二项-docops-完整记录)；[机器结果与来源绑定](../'+str((out/'comparison.json').relative_to(ROOT))+')。','']
    return '\n'.join(lines)


def detail_section(r,out):
    lines=['## 九、扩展任务操作：十二项 DocOps 完整记录','',
      '本节为后续扩展实验，原有七例五次数据与前八节保持不变。本节以原始 OPM、TLC 为对照，采用统一 openEuler 环境下的新十二项 perf 与 DevKit；旧 Debian 首批仅作历史记录，不进入本节数值。','',
      '### 9.1 样本与冻结执行链','',
      table(['任务','格式／业务','采用的来源 run','最终有效链','历史内容 reward'],[[k,t['format']+'／'+t['name'],t['source_run_id'],FLOWS[k],t['historical_score'].get('reward','unknown')] for k,t in r['tasks'].items()]),'',
      '来源判定保持原样，缺失 CTRF、summary-only 及脚本关联推断等来源边界保留在 recipe／机器结果中；回放或采集成功不升级历史内容判定。各任务采用独立冻结脚本；相同脚本名不表示共享同一个业务实现。','',
      '### 9.2 环境、窗口和采集方法','',
      f"原 OPM／TLC 的五次结果绑定镜像 `{r['reference_image_id']}`；十二项 DocOps 绑定其派生镜像 `{r['docops_image_id']}`。Python 3.12.3、openpyxl 3.1.5、LibreOffice 25.8.7.3、Poppler 23.12.0、perf 6.6.0-145.3.23.154 与 DevKit 26.0.RC1。DocOps 增加 python-docx 1.2.0、python-pptx 1.0.2、lxml 6.1.2、fontTools 4.68.0、ReportLab 5.0.1、ImageMagick 7.1.2.9 等所需依赖。",'',
      'perf 按回放入口及其后代采样，`cycles:u`、49 Hz、DWARF 16384、CLOCK_MONOTONIC；同镜像导出物理栈并加载精确 build-id 调试文件。每项原有一次采集、十轮回放；补符号只离线重解析，样本键、叶地址、DSO、进程权重、ROI 分母及原文件哈希已核对不变。',
      'DocOps perf 仅筛选 workflow 步骤区间并集，排除 dispatcher；原七例的循环 ROI 包含 reset。两者都包含各自任务的原有检查，但检查内容和输入规模不相同。未知项始终保留完整周期分母。',
      'DevKit 单独运行，按宿主 CPU 0–7 计数，业务绑 0–7，控制／监测／准备／归档绑 CPU 9。当前 CLI 最小 interval 为 1 秒，采集整份十轮批次，记录实际编号报告和 ALL。完整包络保留就绪、间隙与停止边界，可能包含对应 CPU 上其他宿主活动；不当作精确进程过滤。',
      '硬件沿用 MIDR `0x00000000480fd020` 平台；DevKit 型号横幅仍显示 unknown，采用既有硬件核验与固定工具输出口径。经验公式复算、未计数事件和打印差异保留，未将其冒称完整的官方 HIP09 语义确认。','',
      '```bash',
      'perf record -e cycles:u -F 49 -k mono --call-graph dwarf,16384 -- <测量包装入口>',
      'perf script --no-inline --ns -F +pid -i /original/perf.data',
      'devkit tuner top-down -c 0-7 -L 0 -i 1 -l 0','```','',
      'Topdown 四顶层总变差＝0.5 × Σ|新指标−基准指标|，指标单位为百分点；IPC 相对变化＝100 × (新 IPC／基准 IPC−1)。子层 Core／Memory、Fetch Latency／Bandwidth 分别展示，避免父子分类重复加权。余弦为辅助；本节不跨不同 idle 窗口计算混合单位十维距离。函数 Jaccard 使用 DSO 文件名＋完整叶函数名；基准清单占比在目标全部已解析函数中查找，不限目标前十。','',
      '### 9.3 最终指标、窗口与采集质量','',
      table(['配置',*METRICS],[[k,*[f'{t["metrics"][m]:.3f}' for m in METRICS]] for k,t in {**r['baselines'],**r['tasks']}.items()]),'',
      table(['任务','perf ROI 样本','未解析周期占比','Topdown workflow 秒','Topdown 包络秒','编号过程点','全包络 idle %'],[[k,t['roi_samples'],f"{100*t['quality']['unknown_leaf_symbol_share']:.4f}%",f"{t['topdown_workflow_seconds']:.3f}",f"{t['topdown_envelope_seconds']:.3f}",t['interval_points'],f"{t['idle_pct']:.3f}"] for k,t in r['tasks'].items()]),'',
      '九项指标来自 ALL 最终累计报告，idle 来自本批 /proc/stat 包络；没有重建逐点 idle，也不把逐点百分比均值用作 ALL。每项一次独立采集，尚不计算重复均值、标准差或 CV。perf loss 按原始计数单位保存，ROI 归属未知，不换算为丢失周期。','',
      '### 9.4 与 OPM／TLC 的全部比较','',
      table(['新任务','基准','共同 Top-10','Jaccard','基准清单在新任务占比','IPC Δ%','Bad Δpp','FE Δpp','BE Δpp','Retiring Δpp','Bound 总变差 pp','余弦（辅助）'],[
          [k,b,p['shared_top10_count'],f"{p['jaccard']:.4f}",pct(p['baseline_top10_share_in_target']),f"{p['ipc_relative_change_pct']:+.3f}",*[f"{p['metrics_delta'][m]:+.3f}" for m in BOUNDS],f"{p['bound_total_variation_pp']:.3f}",f"{p['bound_cosine_auxiliary']:.6f}"]
          for k,ps in r['comparisons'].items() for b,p in ps.items()]),'',
      table(['新任务','基准','Core Δpp','Memory Δpp','Fetch Latency Δpp','Fetch Bandwidth Δpp'],[
          [k,b,*[f"{p['metrics_delta'][m]:+.3f}" for m in METRICS[5:]]]
          for k,ps in r['comparisons'].items() for b,p in ps.items()]),'',
      '总变差、百分点差和函数集合分别描述不同层次；不将它们拼成单一高／中／低标签。','',
      '### 9.5 十二项脚本、库与逐函数结果']
    for k,t in r['tasks'].items():
        refs={ref:{key(f) for f in b['functions'][:10]} for ref,b in r['baselines'].items()}
        lines+=['',f"### {k}：{t['format']}／{t['name']}",'',
          table(['实际进程／脚本','ROI 周期占比'],[[x['script'],pct(x['share_roi'])] for x in t['processes'][:8]]),'',
          table(['原生组件','ROI 周期占比'],[[x['library'],pct(x['share_roi'])] for x in t['libraries'][:8]]),'',
          table(['函数排名','物理叶函数','DSO 文件名','ROI 周期占比','属于 OPM Top-10','属于 TLC Top-10'],[
            [i,short_function(f,180),f['library'],pct(f['share_roi']),'✓' if key(f) in refs['OPM'] else '','✓' if key(f) in refs['TLC'] else ''] for i,f in enumerate(t['functions'][:20],1)]),'',
          '完整未截短函数名称、完整权重、原始采集 loss 与来源 hash 均在机器结果／原 profile 中。',
          f"![DocOps {k} 九项指标的全部真实过程点](../{(out/'figures'/f'{k}-all-metrics.svg').relative_to(ROOT)})"]
    lines+=['','### 9.6 新任务内部同格式对照（补充）','',
      table(['任务 A','任务 B','共同 Top-10','Jaccard','Bound 总变差 pp','余弦（辅助）'],[[p['baseline'],p['target'],p['shared_top10_count'],f"{p['jaccard']:.4f}",f"{p['bound_total_variation_pp']:.3f}",f"{p['bound_cosine_auxiliary']:.6f}"] for p in r['same_format_pairs']]),'',
      '### 9.7 来源与离线复算','',
      '- 原始基准：`'+BASE_CONFIG+'`。','- 原始统一环境 perf：`'+PERF_CAMPAIGN+'`。',
      '- 离线符号结果：`'+ENRICHMENT+'`。','- 统一环境 DevKit：`'+TOPDOWN+'`。',
      '- 本节机器结果：`'+str((out/'comparison.json').relative_to(ROOT))+'`。','',
      '```bash','python3 -B analysis/docops/operation_comparison.py --update --publish','```','',
      '该命令只读取既有 JSON、日志与冻结 recipe，重建比较表、曲线及追加章节，不启动 workload、容器、perf、DevKit 或模型。','']
    return '\n'.join(lines)


def original_prefix(data,expected):
    marker=BEGIN.encode()
    base=data.split(marker,1)[0] if marker in data else data
    if hashlib.sha256(base).hexdigest()!=expected:
        raise ValueError('original report prefix changed')
    return base


def publish(result,out,figures):
    buildpath=ROOT/'analysis/hotspots/reports/pdf-xlsx-common-hotspots-20261027/build.json'
    build=json.loads(buildpath.read_text())
    base_documents=build.get('base_document_sha256',build['document_sha256'])
    original_build=out/'base-publication-build.json'
    if not original_build.exists():
        if 'base_document_sha256' in build:
            raise ValueError('original publication snapshot is missing')
        original_build.write_bytes(buildpath.read_bytes())
    original=json.loads(original_build.read_text())
    if original['document_sha256']!=base_documents:
        raise ValueError('original publication document identity differs')
    sections={'docs/representativeness-assessment.md':main_section(result,out),
              'docs/experimental-results.md':detail_section(result,out)}
    records={};writes=[]
    for rel,section in sections.items():
        path=ROOT/rel;base=original_prefix(path.read_bytes(),base_documents[rel])
        tail=(BEGIN+'\n\n'+section+'\n'+END+'\n').encode()
        complete=base+tail
        records[rel]=dict(prefix_bytes=len(base),prefix_sha256=hashlib.sha256(base).hexdigest(),
            append_sha256=hashlib.sha256(tail).hexdigest(),sha256=hashlib.sha256(complete).hexdigest())
        writes.append((path,complete))
    manifest=dict(schema='append-only-task-operation-report-v1',status='passed',documents=records,
        base_publication_build=dict(path=str(original_build.relative_to(ROOT)),sha256=sha(original_build)),
        analysis=dict(path=str((out/'comparison.json').relative_to(ROOT)),sha256=sha(out/'comparison.json')),
        analysis_sources={str(Path(__file__).relative_to(ROOT)):sha(Path(__file__))},
        images=dict(reference=result['reference_image_id'],docops=result['docops_image_id']),
        figures=figures,presentation_figures={
            '../'+str((out/'figures'/f'{k}-bounds.svg').relative_to(ROOT)):str((out/'figures'/f'{k}-bounds.svg').relative_to(ROOT))
            for k in ('031','016','021','029')},
        original_seven_case_measurements_changed=False,new_measurements_executed=False)
    for path,content in writes:
        tmp=path.with_name(path.name+'.tmp');tmp.write_bytes(content);tmp.replace(path)
    write(ROOT/PUBLICATION,manifest)
    # This is the current publication binding, not a change to the five-run data.
    # Retain the former document/output hashes and the complete original build.
    build.setdefault('base_document_sha256',dict(build['document_sha256']))
    build.setdefault('base_output_sha256',dict(build['output_sha256']))
    build['document_sha256']={rel:x['sha256'] for rel,x in records.items()}
    build['output_sha256']['report.md']=records['docs/representativeness-assessment.md']['sha256']
    build['document_extension']=dict(path=PUBLICATION,sha256=sha(ROOT/PUBLICATION),
        generator_sha256=sha(Path(__file__)))
    write(buildpath,build)


def run(output,publish_docs=False,update=False):
    output=Path(output).resolve()
    if output.exists() and not update:raise ValueError('output exists; use --update for derived publication only')
    result=gather();output.mkdir(parents=True,exist_ok=True)
    write(output/'comparison.json',result)
    figures=plot(result,output)
    (output/'assessment-section.md').write_text(main_section(result,output))
    (output/'experiment-section.md').write_text(detail_section(result,output))
    write(output/'analysis-build.json',dict(source_sha256=sha(Path(__file__)),input_bindings=result['input_bindings'],
        output_sha256={p.name:sha(p) for p in output.iterdir() if p.is_file() and p.name!='analysis-build.json'},
        figures=figures,measurement_rerun=False))
    if publish_docs:publish(result,output,figures)
    print(json.dumps(dict(output=str(output),tasks=len(result['tasks']),baseline_pairs=24,
        original_prefixes_unchanged=publish_docs,published=publish_docs),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/DEFAULT_OUTPUT)
    parser.add_argument('--publish',action='store_true')
    parser.add_argument('--update',action='store_true')
    args=parser.parse_args();run(args.output,args.publish,args.update)
