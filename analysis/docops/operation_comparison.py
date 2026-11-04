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
    from matplotlib import pyplot as plt, font_manager
    chinese_font=Path('/usr/share/fonts/google-droid-fonts/DroidSansFallback.ttf')
    if chinese_font.exists():
        font_manager.fontManager.addfont(str(chinese_font))
        chinese_family=font_manager.FontProperties(fname=chinese_font).get_name()
    else:
        chinese_family='Noto Sans CJK SC'
        font_manager.findfont(font_manager.FontProperties(family=chinese_family),fallback_to_default=False)
    plt.rcParams.update({'font.family':['DejaVu Sans',chinese_family],
                         'svg.fonttype':'none','svg.hashsalt':'docops-operation-v1'})
    colors=('#346a9f','#cf792d','#347d55','#b3464c')
    folder=out/'figures';folder.mkdir(exist_ok=True)
    figures={}
    for number,(task,t) in enumerate(result['tasks'].items(),1):
        points=t['interval_data']['points'];xs=[p['sample_index'] for p in points]
        fig,ax=plt.subplots(figsize=(11.2,3.98),layout='constrained')
        for metric,label,color in zip(BOUNDS,('误推测','前端受限','后端受限','有效完成'),colors):
            ax.plot(xs,[p['metrics'][metric] for p in points],label=label,color=color,marker='.',markersize=2,linewidth=1)
        ax.set(xlim=(1,max(2,len(xs))),ylim=(0,100),xlabel='实际输出点编号（名义间隔 1 秒）',ylabel='顶层指标占比（%）',
            title=f'图 7-{number}：{task} {NAMES[task]}\n一次采集，内部十轮回放，共 {len(xs)} 个真实输出点')
        ax.grid(alpha=.2);ax.legend(ncol=4,fontsize=9,loc='upper right')
        for ext in ('svg','png'):
            p=folder/f'{task}-bounds.{ext}';fig.savefig(p,dpi=130,metadata={'Date':None} if ext=='svg' else None)
            if ext=='svg':p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n')
            figures[str(p.relative_to(ROOT))]=sha(p)
        plt.close(fig)
        fig,axes=plt.subplots(3,3,figsize=(12,8),layout='constrained')
        for ax,metric in zip(axes.flat,METRICS):
            ax.plot(xs,[p['metrics'][metric] for p in points],color='#346a9f',marker='.',markersize=2,linewidth=1)
            ax.set(title=metric,xlabel='实际输出点编号',ylabel='IPC' if metric=='IPC' else '%');ax.grid(alpha=.2)
        fig.suptitle(f'{task} {NAMES[task]}：九项指标的全部真实过程点（无逐点 idle 数据）')
        for ext in ('svg','png'):
            p=folder/f'{task}-all-metrics.{ext}';fig.savefig(p,dpi=130,metadata={'Date':None} if ext=='svg' else None)
            if ext=='svg':p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n')
            figures[str(p.relative_to(ROOT))]=sha(p)
        plt.close(fig)
    return figures


def task_label(task):
    return task+' '+NAMES[task]


def main_refs(fmt):
    return ('OPM',) if fmt=='PDF' else ('TLC',) if fmt=='Excel' else ('OPM','TLC')


def hotspot_meaning(function):
    if 'longest_match' in function or 'deflate' in function:
        return 'zlib：查找重复数据并压缩'
    if 'png_write' in function:
        return 'PNG：选择图像编码方式并写出图片'
    if 'HorizontalFilter' in function or 'VerticalFilter' in function:
        return 'ImageMagick：横向／纵向图像滤波、缩放'
    if 'Splash::' in function:
        return 'Poppler：将 PDF 页面内容绘制成像素'
    if '_PyEval' in function:
        return 'Python：执行脚本指令'
    if '_Py_dict_lookup' in function:
        return 'Python：查找字典中的对象'
    if '_Rb_tree' in function:
        return 'C++ 有序容器：插入或查找数据'
    if 'drawingml' in function.lower():
        return 'LibreOffice：处理幻灯片表格等对象的样式'
    return '完整软件归属与函数名称见实验数据记录'


PLOT_NOTES={
 '031':'后端受限占比较高；相对 OPM 的汇总变化为前端降低、后端增加。热点同时显示压缩占比突出。',
 '037':'后端受限是主要份额，与 031 的汇总特征接近；压缩与 PNG 编码是主要函数热点。',
 'pdfwf005':'本项加入材料包重建与拼图，热点中出现 ImageMagick 图像滤波；结合曲线观察其流水线分配。',
 '013':'本项同时执行工作簿处理和 PDF／图片交付；结合压缩、图像与 Calc 热点阅读这些过程点。',
 '014':'本项包含工作簿重算、OOXML 修补及渲染；最终指标取整段累计，曲线用于显示过程变化。',
 '016':'汇总前端受限高于 TLC，IPC 低于 TLC；函数中可见 Python 对象处理与 Calc 路径。',
 '001':'本项执行 Word 构建、转换和检查；压缩函数是主要热点，不能只凭文件格式认为排版必然最重。',
 '003':'本项包含元数据处理、审计与文档渲染；曲线需与压缩、PNG 和 Writer 工具路径一起解释。',
 '009':'本项事件手册发布的主要函数集中于压缩和 PNG 编码，图中展示这份批次的实际流水线变化。',
 '021':'本项 PDF 页面绘制与图像处理较突出；与 029 共享工具，但主要热点函数和指标分配不同。',
 '026':'本项 Poppler 页面绘制份额较高；实际过程点展示渲染相关工作流的流水线分配。',
 '029':'本项出现解释器、字典查找与 DrawingML 表格样式函数，不能用其他 PPT 的渲染热点代替。'}


def main_section(r,out):
    lines=['## 七、扩展任务操作：与原始 PDF/XLSX 基准比较','',
      '前六节保留原七例“跨行业输入”实验及其提出的场景扩展问题。本节报告十二项 DocOps L3 的真实轨迹回放：在 PDF／Excel 中改变任务操作，并加入 Word／PPT，分别与原始 OPM／TLC 比较。',
      '**先看判断：原七例能够代表已测任务形态下的跨行业输入，但没有充分覆盖更广的文档操作。本次扩展已观察到不同的热点函数和流水线分配，因此有必要按操作类型补充负载。** 以下依次说明工具做什么、旧热点保留多少、CPU 指标怎样变化。','',
      '### 7.1 样本、轨迹与测量口径','',
      table(['任务组','本次操作覆盖','主要对照'],[
       ['PDF：031／037／pdfwf005','听证材料包发布、公交绕行材料修复、结算材料包重建','原始 PDF：OPM'],
       ['Excel：013／014／016','投标评审发布、灾害补助公开发布、预测模型情景级联','原始 XLSX：TLC'],
       ['Word：001／003／009','受控发布修复、元数据清理、事件手册发布','OPM、TLC 均比较'],
       ['PPT：021／026／029','无障碍整改、图表重建、季度业务回顾发布','OPM、TLC 均比较']]),'',
      '十二项任务采用已保存 Agent 轨迹中的最终有效依赖链。各任务独立冻结脚本、输入、Skill 和命令；内联命令保留为任务私有步骤。回放不调用模型，保留最终构建、必要修补、重算、渲染及原有检查，公共入口负责调度、环境和归档。',
      '来源中的官方内容判定为四项通过、八项未通过；本次十二项工具链回放及采集均完成。两类结果分别记录，逐项来源和判定见实验数据记录。','',
      table(['项目','原始 OPM／TLC','新增 DocOps'],[
       ['环境','原七例测量镜像；Python 3.12.3、LibreOffice 25.8.7.3','基于同一测量镜像；共用 Python、LibreOffice、Poppler 和 perf 版本，补充文档、幻灯片及图像处理依赖'],
       ['重复与汇总','每路五次独立运行；热点合并周期权重，Topdown 取五次 ALL 均值','每项每路一次独立采集，内部十轮回放；热点按工作流周期权重，Topdown 取本次 ALL'],
       ['采集','perf：cycles:u、49 Hz、DWARF；DevKit：CPU 0–7、1 秒间隔','沿用相同参数；两路分开运行，控制器 CPU 9'],
       ['窗口','既有完整循环，包含 reset 和循环检查','perf 为 workflow 步骤区间并集，排除准备、reset 和归档；Topdown 为按核采集包络']]),'',
      '本节比较实际工作流，任务操作、输入组织和规模可能同时变化；结论用于识别负载差异。十轮合并采集只算一次独立运行，不套用原七例的五次稳定性结论。','',
      '### 7.2 软件分别做什么，哪些沿用、哪些扩展','',
      '**表 7-1：软件用途。** “脚本／工具”是直接调用的程序，“底层组件”是执行过程中真正消耗 CPU 的库。比如 python-docx 操作 Word，但对应 CPU 周期可能记在 Python、XML 或压缩函数中，不能把两层占比直接相加。','',
      table(['软件／组件','一般用途','在本批任务中的位置'],[
       ['Python','执行脚本，创建和管理数据对象','原有与新增任务共同的运行环境'],
       ['openpyxl','读取、修改、保存 Excel 工作簿','已有 Excel 读写工具，扩展任务继续使用'],
       ['python-docx／python-pptx','创建和修改段落、表格、形状及幻灯片','为 Word／PPT 任务补充的直接操作库'],
       ['LibreOffice：Calc／Writer／Impress','分别处理表格、文字文档和幻灯片；支持重算、排版与格式转换','沿用同一软件版本，任务进入不同文档模块'],
       ['Poppler／pdftoppm','解析 PDF，将页面绘制为图片','原 PDF 已有；新任务的预览和渲染继续使用'],
       ['Pillow／ImageMagick','图片转换、缩放、滤波和拼图','Pillow 为原有工具；DocOps 补充 ImageMagick'],
       ['ReportLab／fontTools','分别用于生成 PDF、读取和处理字体','DocOps 补充的任务依赖；安装存在不等于占主要热点'],
       ['zlib／PNG 编码库','压缩重复数据，编码并写出图片','部分新任务中成为主要 CPU 热点'],
       ['lxml／Expat／ElementTree','读取和处理文档内部的 XML 结构','原 Excel 已有 XML 路径，DocOps 增加 lxml 依赖'],
       ['libc／loader','基础内存、字符串等操作，以及装载程序依赖库','公共运行基础，不能仅由该库名判断具体文档业务']]),'',
      '**表 7-2：原始任务作为对照。** OPM 代表 PDF 表单填写与检查，TLC 代表大型工作簿检查、增强、重算和缓存验证。下面的百分比为用户态 perf 采样周期占比，包含所有保留的工作流样本，不是任务墙钟时间。','',
      table(['原始基准','主要脚本／进程','主要底层组件及周期占比'],[[k,'; '.join(x['script']+' '+pct(x['share_roi']) for x in t['processes'][:4]),'; '.join(x['library']+' '+pct(x['share_roi']) for x in t['libraries'][:4])] for k,t in r['baselines'].items()]),'',
      '**表 7-3：十二项新增任务实际执行什么。** 先看脚本链路，再看采样周期主要落在哪些底层软件；每行只列占比最高的四项组件，不要求四项合计为 100%。','',
      table(['格式／任务','实际脚本／工具链','主要底层组件及周期占比'],[
        [fmt+'／'+task_label(k),FLOWS[k],'; '.join(x['library']+' '+pct(x['share_roi']) for x in r['tasks'][k]['libraries'][:4])]
        for fmt,ids in GROUPS.items() for k in ids]),'',
      '**本节总结：**','',
      '- **共同基础仍然保留。** Python、LibreOffice、Poppler、压缩和图像处理继续构成主要工具链。',
      '- **扩展了文档操作工具和模块。** 新增 python-docx、python-pptx、lxml、ImageMagick 等依赖，并执行 Writer、Impress 和幻灯片对象处理路径。',
      '- **已有软件也会承担不同的工作。** 同样调用 LibreOffice 或 Poppler，实际可能是表格重算、文档转 PDF 或页面绘图，热点权重不会天然相同。','',
      '### 7.3 热点函数：旧热点保留多少，新热点在做什么','',
      '本节分两步阅读：表 7-4 看原有热点的延续程度，表 7-5 解释新任务最耗周期的函数。函数以“完整物理叶函数名＋所属库文件名”匹配，同名但来自不同库的函数不会混为一项。未知符号仍保留在完整周期分母中。','',
      '**两个指标的区别：**“共同函数数”比较两份前十名单，有几个相同；“旧热点函数占比”则把原基准前十个函数在新任务全部采样中的周期相加，即使该函数掉出新任务前十也计入。后者是十个具体函数的权重，不是整个任务或旧切片的覆盖率。','',
      f"**读表示例：** 031 与 OPM 的前十热点共有 {r['comparisons']['031']['OPM']['shared_top10_count']} 个函数，但 OPM 的前十函数在 031 中仍占 {pct(r['comparisons']['031']['OPM']['baseline_top10_share_in_target'])}；其中压缩函数 `longest_match` 单独占 {pct(next(f['share_roi'] for f in r['tasks']['031']['functions'] if f['function']=='longest_match'))}。所以共同函数数量少，不一定表示共同计算的权重小。",'',
      '**表 7-4：原始热点在新任务中的延续程度。** PDF 以 OPM 为主对照，Excel 以 TLC 为主对照；Word／PPT 同时列两个基准。OPM 自身前十函数合计占 57.81%，TLC 为 49.50%，并非基准全部周期。','',
      table(['新任务','对照基准','两份前十名单中相同的函数数','原基准前十函数在新任务中的周期占比'],[
       [task_label(k),ref,str(r['comparisons'][k][ref]['shared_top10_count'])+'/10',pct(r['comparisons'][k][ref]['baseline_top10_share_in_target'])]
       for fmt,ids in GROUPS.items() for k in ids for ref in main_refs(fmt)]),'',
      '**表 7-5：新任务主要在计算什么。** 列出每项前三个函数及其周期占比，并按软件说明用途。完整前二十函数、所属库及全部 OPM／TLC 对照见实验数据记录。','',
      table(['新任务','前三热点函数及周期占比','这些函数通常做什么'],[
       [task_label(k),'; '.join(short_function(f,76)+' '+pct(f['share_roi']) for f in t['functions'][:3]),'；'.join(dict.fromkeys(hotspot_meaning(f['function']) for f in t['functions'][:3]))]
       for k,t in r['tasks'].items()]),'',
      '**从函数可以读出的四点变化：**','',
      '- **新增 PDF：原来就有压缩和图片处理，现在这些工作的比重、具体实现发生变化。** 031／037 的 zlib 压缩占比达到约 **66%／53%**，高于 OPM 的约 **25%**；pdfwf005 则增加了明显的 ImageMagick 图片缩放、滤波和拼图热点。因此，是处理重点改变，不是首次出现图片处理。',
      '- **新增 Excel：从工作簿处理，扩展到工作簿处理加预览发布。** 013／014 不仅生成、重算和检查 Excel，还导出 PDF、渲染图片，因此压缩和图片处理的权重增加。016 则主要体现情景切换、重算以及 Python／Calc 内部处理。',
      '- **新增 Word：虽然操作的是 Word，最终较重的环节却是文档转换后的压缩和图片编码。** 所以它与原 PDF 的压缩热点有共性，但执行的完整任务不同。',
      '- **新增 PPT：部分任务的页面绘制更重。** 021／026 的 Poppler 页面渲染突出；029 则更多体现 Python 对象处理和 LibreOffice 幻灯片表格样式处理。','',
      '### 7.4 Topdown：四类流水线指标完整比较','',
      '热点函数回答“运行了什么代码”，Topdown 回答“CPU 流水线的资源怎样分配”。下面先解释指标，再展示原值与相对基准的变化；四项顶层指标全部保留。','',
      '**表 7-6：指标读法。** 四项 Topdown 顶层分类合计约为 100%；IPC 单独阅读，不与百分数相加。','',
      table(['指标','中文含义','如何理解'],[
       ['IPC','每周期完成的指令数','反映平均指令吞吐；单独降低不等于整项任务耗时一定更长'],
       ['Bad Speculation','误推测','分支预测错误等产生的无效执行份额'],
       ['Frontend Bound','前端受限','指令获取、解码等供应环节受限的份额'],
       ['Backend Bound','后端受限','执行资源或数据供应环节受限的份额；不能只凭此项判断是内存问题'],
       ['Retiring','有效完成','用于正常完成指令的流水线份额，不是整项任务的 CPU 利用率']]),'',
      '**表 7-7：原始基准与十二项任务的实测原值。** OPM／TLC 为五次独立采集的均值，新任务为本次十轮批次的 ALL 累计结果。除 IPC 外，单位均为百分比。','',
      table(['配置','IPC','误推测 %','前端受限 %','后端受限 %','有效完成 %'],[
       [task_label(k) if k in NAMES else k+'（原始基准）',*[f"{t['metrics'][m]:.3f}" for m in METRICS[:5]]]
       for k,t in {**r['baselines'],**r['tasks']}.items()]),'',
      '**表 7-8：与原始基准相比改变了多少。** 正号表示新任务更高，负号表示更低。IPC 用相对百分比；四项 Topdown 用百分点（pp），例如 20% 变成 25% 是 +5 pp。Word／PPT 同时对照 OPM、TLC。','',
      table(['任务（对照基准）','IPC 变化 %','误推测 Δpp','前端 Δpp','后端 Δpp','有效完成 Δpp'],[
       [k+'（'+ref+'）',f"{p['ipc_relative_change_pct']:+.1f}%",*[f"{p['metrics_delta'][m]:+.2f}" for m in BOUNDS]]
       for fmt,ids in GROUPS.items() for k in ids for ref in main_refs(fmt) for p in [r['comparisons'][k][ref]]]),'',
      '**本节结论：**','',
      '- **PDF 031／037 的变化主要体现在前后端分配。** 相比 OPM，前端份额分别降低 9.18／7.84 pp，后端增加 13.72／13.89 pp。',
      '- **Excel 016 的前端受限增加、有效完成份额降低。** 相比 TLC，前端增加 5.30 pp，有效完成降低 8.50 pp，IPC 低 41.7%；是否更耗时还需结合具体工作量。',
      '- **相同大类指标接近，不代表热点相同。** PPT 021 与 029 的四维余弦约 0.9955，但前十热点仅共享两个函数，仍需结合软件和函数比较。',
      '- **四项指标必须一起看。** 前端降低的份额可能转到后端、误推测或有效完成；只列前后端会掩盖其他变化。','',
      '**辅助相似度如何使用：** 四维 Bound 余弦描述分布方向，总变差为四项绝对百分点差之和的一半，Jaccard 描述前十函数集合重合程度。详细数值、公式和全部 24 组对照保留在实验数据记录；本节不依据“余弦超过 0.99”给出整体负载高度相似的判断。','',
      '### 7.5 十二项任务的逐点曲线与读图说明','',
      '下列十二张图每项对应一张，按 PDF、Excel、Word、PPT 排列，共 533 个真实过程点。每张有四条线，分别对应误推测、前端受限、后端受限、有效完成。横轴为实际输出点编号，纵轴为百分比；名义间隔 1 秒，不插值、不增加人工采样点。',
      '每张图是一份采集中十轮回放的过程，不是十次独立采集。曲线用于看执行过程的分布变化，最终指标取 ALL 累计报告。未建立可靠的逐点阶段对应，因此不把某个峰值直接标成“重算”或“渲染”。']
    for number,(fmt,task) in enumerate(((fmt,k) for fmt,ids in GROUPS.items() for k in ids),1):
        caption=f'图 7-{number}：{fmt}／{task_label(task)}——四项 Topdown 过程'
        rel='../'+str((out/'figures'/f'{task}-bounds.svg').relative_to(ROOT))
        lines+=['','### '+caption,'',f'![{caption}]({rel})','',
                '**读图：** '+PLOT_NOTES[task]+f" 本图共 {r['tasks'][task]['interval_points']} 个真实输出点。"]
    lines+=['','### 7.6 最终判断：原负载覆盖了什么，还需要扩展什么','',
      '**结论是：原有负载在已测任务范围内具有跨行业代表性；扩展操作实验同时发现了原任务未充分覆盖的计算路径，因此仍有必要扩充办公 Agent 的操作类型。** 这两项发现回答不同问题，能够同时成立。','',
      '- **原七例的结论继续成立。** 保持表单填写或大型工作簿增强等任务形态时，更换行业输入仍延续主要热点，已有负载有明确用途。',
      '- **覆盖缺口确实存在。** 原来没有充分体现材料包重建、图片滤波与拼图、幻灯片对象样式、不同发布和情景重算组合；本次已在具体函数与模块中观察到相应差异。',
      '- **“未充分覆盖”不等于公共软件全都缺失。** 压缩、XML、LibreOffice 和渲染原本就有；新任务可能增强已有机制，也可能进入不同模块和函数路径。不能拿旧前十名单之外的全部周期都称为全新机制。',
      '- **代表范围需要扩展。** 原负载可以代表已测 PDF 表单与大型工作簿任务，单独用它们代表更广的 Word、PPT 及复杂文档操作仍不充分；本次十二项补充了这部分实测证据。',
      '- **后续优先按操作选型。** 保留原有跨行业输入对照，补充能带来不同热点的文档构建、对象处理、布局与渲染任务；先对候选做独立重复，再决定最终基准集合。连续长文档分页等是否形成主导热点，还需专项实测。','',
      '[完整扩展实验记录](experimental-results.md#九扩展任务操作十二项-docops-完整记录)保留九项指标、24 组基准对照、完整函数名单和全部曲线；[机器结果与来源绑定](../'+str((out/'comparison.json').relative_to(ROOT))+')可逐项追溯。','']
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
            for k in result['tasks']},
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
