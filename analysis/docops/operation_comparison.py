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
HOTSPOT_SHARE=.005
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


def function_presence(references,target):
    """Partition target ROI by presence in complete saved reference lists.

    This measures observed function identity, not business/mechanism coverage.
    Keep unresolved weight in the denominator and deduplicate the reference union.
    """
    denominator=target['roi_period']
    if denominator<=0:raise ValueError('positive target ROI period required')
    rows=target['functions']
    if len({key(f) for f in rows})!=len(rows):raise ValueError('duplicate target function identity')
    resolved_period=sum(f['period'] for f in rows)
    if any(f['period']<0 for f in rows) or resolved_period>denominator:
        raise ValueError('resolved period exceeds complete ROI or is negative')
    scopes={name:{key(f) for f in case['functions']} for name,case in references.items()}
    scopes['OPM+TLC']=set().union(*scopes.values())
    result={}
    for name,identities in scopes.items():
        seen=[f for f in rows if key(f) in identities]
        unseen=[f for f in rows if key(f) not in identities]
        observed=sum(f['period'] for f in seen)
        not_observed=sum(f['period'] for f in unseen)
        unresolved=denominator-resolved_period
        result[name]=dict(reference_function_count=len(identities),
            observed_period=observed,not_observed_period=not_observed,unresolved_period=unresolved,
            observed_share_roi=observed/denominator,not_observed_share_roi=not_observed/denominator,
            unresolved_share_roi=unresolved/denominator,
            observed_function_count=len(seen),not_observed_function_count=len(unseen),
            not_observed_top20=sorted(unseen,key=lambda f:(-f['period'],key(f)))[:20])
        if observed+not_observed+unresolved!=denominator:raise ValueError('function partition does not conserve')
    return result


def topk_presence(references,target):
    """Match ranked target functions against the complete reference union."""
    identities={key(f) for case in references.values() for f in case['functions']}
    rows=sorted(target['functions'],key=lambda f:(-f['period'],key(f)))
    if len({key(f) for f in rows})!=len(rows):
        raise ValueError('duplicate target function identity')
    result={}
    for k in (10,20):
        selected=[dict(rank=i,library=f['library'],function=f['function'],
                       observed=key(f) in identities) for i,f in enumerate(rows[:k],1)]
        result[str(k)]=dict(requested_count=k,selected_count=len(selected),
                           observed_count=sum(f['observed'] for f in selected),functions=selected)
    return result


def unseen_function_type(row):
    """Exclusive, conservative leaf-DSO/symbol rules; no stage-time attribution."""
    dso,name=row['library'],row['function']
    if 'libpython' in dso:
        return 'Python','语言运行时／文本与对象','已有解释执行机制的具体函数变化'
    if 'libooxlo' in dso and 'drawingml' in name.lower():
        return 'LibreOffice·OOXML','文档对象／样式路径','具体对象处理函数证据；不推断独有算法'
    if 'libooxlo' in dso and 'PropertyMap' in name:
        return 'LibreOffice·OOXML','文档对象／样式路径','文档对象属性组织与传递'
    if any(x in dso for x in ('libpng','png.so','libjpeg','jpeg.so')):
        return ('PNG' if 'png' in dso else 'JPEG'),'图片编码／解码','旧任务已有图像编码，具体实现路径不同'
    if 'libMagick' in dso or '_imaging.' in dso:
        return ('ImageMagick' if 'libMagick' in dso else 'Pillow'),'图片滤波／缩放','处理类型与旧图片操作有共性；不把整库归为拼图'
    if 'libpoppler' in dso or 'libpixman' in dso or 'libcairo' in dso:
        return ('Poppler' if 'libpoppler' in dso else 'pixman' if 'libpixman' in dso else 'cairo'),'页面／像素绘制','已有渲染类型的具体子路径'
    if 'libvcllo' in dso and any(x in name for x in ('Bitmap','Convolution','Blur')):
        return 'LibreOffice·VCL','图片滤波／缩放','LibreOffice 图形层的具体图像实现'
    if any(x in dso for x in ('fontconfig','freetype','harfbuzz')):
        return dso.split('.so')[0],'字体／文本图形处理','字体选择或图形处理路径；不自动归为分页'
    if any(x in dso for x in ('etree.','_elementpath.','libxml','libexpat','pyexpat.','_elementtree.')):
        return ('lxml' if 'etree.' in dso or '_elementpath.' in dso else 'XML 组件'),'XML／结构解析','已有 XML 处理类型，具体实现或子路径不同'
    if 'libz.so' in dso:
        return 'zlib','压缩／解压','旧任务已有压缩类型'
    if 'libsclo' in dso and any(x in name for x in ('ScInterpreter','ScFormula','ScCompiler','ScDocument')):
        return 'LibreOffice·Calc','表格模型／重算路径','已有表格处理类型的具体子路径'
    if 'libswlo' in dso and any(x in name for x in ('SwText','SwFrame','SwLayout','SwTab')):
        return 'LibreOffice·Writer','文字文档模型／布局路径','具体 Writer 对象或布局函数，非整段阶段计时'
    if any(x in dso for x in ('libfreebl','libnss','libcrypto','libssl')):
        return '安全／加密组件','运行支撑／安全组件','库内运算已观察到，具体业务用途尚未定位'
    if dso.endswith('lo.so') or dso.startswith('libuno'):
        return 'LibreOffice·其他组件','运行支撑／容器与配置','公共框架、容器、属性或配置；不作为新增业务机制'
    if any(x in dso for x in ('libc.so','libstdc++','ld-linux','libgcc','libm.so','bash')):
        return ('loader' if 'ld-linux' in dso else dso.split('.so')[0]),'运行支撑／容器与配置','公共内存、字符串、容器或装载路径'
    return dso,'其他已解析／待归因','仅确认函数身份，不强行解释为新业务计算'


def hotspot_coverage(references,target):
    old_weight={}
    for case in references.values():
        for f in case['functions']:
            old_weight[key(f)]=max(old_weight.get(key(f),0.),f['share_roi'])
    buckets={k:dict(period=0,function_count=0) for k in ('old_hot','old_low','unseen')}
    hotspot_counts=Counter();hotspot_periods=Counter();unseen=[]
    tool_periods=Counter();type_periods=Counter();tool_counts=Counter();type_counts=Counter();pairs=Counter()
    for f in target['functions']:
        weight=old_weight.get(key(f))
        bucket='unseen' if weight is None else 'old_hot' if weight>=HOTSPOT_SHARE else 'old_low'
        buckets[bucket]['period']+=f['period'];buckets[bucket]['function_count']+=1
        if f['share_roi']>=HOTSPOT_SHARE:
            hotspot_counts[bucket]+=1;hotspot_periods[bucket]+=f['period']
        if bucket=='unseen':
            tool,kind,meaning=unseen_function_type(f)
            row=dict(f,tool=tool,type=kind,interpretation=meaning)
            unseen.append(row);tool_periods[tool]+=f['period'];type_periods[kind]+=f['period']
            tool_counts[tool]+=1;type_counts[kind]+=1;pairs[(tool,kind)]+=f['period']
    denominator=target['roi_period']
    unresolved=denominator-sum(b['period'] for b in buckets.values())
    if denominator<=0 or unresolved<0:raise ValueError('invalid complete ROI partition')
    partition=[dict(key=k,**v,share_roi=v['period']/denominator) for k,v in buckets.items()]
    partition.append(dict(key='unresolved',period=unresolved,share_roi=unresolved/denominator,function_count=None))
    def grouped(periods,counts,label):
        return [{label:k, 'period':v,'share_roi':v/denominator,'function_count':counts[k]}
                for k,v in sorted(periods.items(),key=lambda x:(-x[1],x[0]))]
    return dict(old_hotspot_threshold_share_roi=HOTSPOT_SHARE,target_hotspot_threshold_share_roi=HOTSPOT_SHARE,
        reference='OPM+TLC union; old weight is maximum within either individual baseline, not added or averaged',
        partition=partition,target_hotspots=dict(count=sum(hotspot_counts.values()),period=sum(hotspot_periods.values()),
            count_by_bucket={k:hotspot_counts[k] for k in buckets},period_by_bucket={k:hotspot_periods[k] for k in buckets}),
        unseen_functions=unseen,unseen_by_tool=grouped(tool_periods,tool_counts,'tool'),
        unseen_by_type=grouped(type_periods,type_counts,'type'),
        unseen_by_tool_type=[dict(tool=k[0],type=k[1],period=v,share_roi=v/denominator)
            for k,v in sorted(pairs.items(),key=lambda x:(-x[1],x[0]))])


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



PRIORITY_ADDITIONS=('013','021','029')


def weighted_topk_presence(references,target,k):
    """Keep both count and period denominators explicit for ranked functions."""
    identities={key(f) for case in references.values() for f in case['functions']}
    rows=sorted(target['functions'],key=lambda f:(-f['period'],key(f)))
    if len({key(f) for f in rows})!=len(rows):raise ValueError('duplicate target function identity')
    selected=rows[:k];period=sum(f['period'] for f in selected)
    observed=sum(f['period'] for f in selected if key(f) in identities)
    denominator=target['roi_period']
    if denominator<=0 or sum(f['period'] for f in rows)>denominator or any(f['period']<0 for f in rows):
        raise ValueError('invalid ranked period denominator')
    return dict(selected_count=len(selected),observed_count=sum(key(f) in identities for f in selected),
        selected_period=period,observed_period=observed,not_observed_period=period-observed,
        selected_share_roi=period/denominator,observed_share_roi=observed/denominator,
        observed_share_selected=observed/period if period else None)


def minimum_function_cover(candidate_sets,required):
    """Exhaustive set cover over observed identities, not a workload optimizer."""
    required=set(required)
    if not required:return dict(required_function_count=0,minimum_count=0,solutions=[[]])
    names=list(candidate_sets);indices={f:i for i,f in enumerate(sorted(required))}
    masks={name:sum(1<<indices[f] for f in identities&required) for name,identities in candidate_sets.items()}
    goal=(1<<len(indices))-1
    for size in range(1,len(names)+1):
        solutions=[]
        for choice in itertools.combinations(names,size):
            mask=0
            for name in choice:mask|=masks[name]
            if mask==goal:solutions.append(list(choice))
        if solutions:return dict(required_function_count=len(required),minimum_count=size,solutions=solutions)
    raise ValueError('required function identities cannot be covered by candidates')


def augmentation_analysis(references,tasks,selected=PRIORITY_ADDITIONS):
    if len(set(selected))!=len(selected) or any(t not in tasks for t in selected):
        raise ValueError('invalid additional task selection')
    old={key(f) for case in references.values() for f in case['functions']}
    new={t:{key(f) for f in case['functions']}-old for t,case in tasks.items()}
    top20={key(f) for case in tasks.values() for f in sorted(case['functions'],key=lambda f:(-f['period'],key(f)))[:20]}-old
    def evaluate(choice):
        ref=old|set().union(*(new[t] for t in choice))
        remaining=sorted(top20-ref);per_task={}
        for task,case in tasks.items():
            original=function_presence(references,case)['OPM+TLC']
            denominator=case['roi_period']
            observed=sum(f['period'] for f in case['functions'] if key(f) in ref)
            missing=sum(f['period'] for f in case['functions'] if key(f) not in ref)
            unresolved=denominator-observed-missing
            if unresolved<0 or unresolved!=original['unresolved_period']:raise ValueError('augmented partition changed')
            per_task[task]=dict(selected_as_reference=task in choice,roi_period=denominator,
                before_not_observed_period=original['not_observed_period'],before_not_observed_share_roi=original['not_observed_share_roi'],
                observed_period=observed,not_observed_period=missing,unresolved_period=unresolved,
                observed_share_roi=observed/denominator,not_observed_share_roi=missing/denominator,
                unresolved_share_roi=unresolved/denominator)
        return dict(selected_tasks=list(choice),top20_unseen_unique_count=len(top20),
            top20_unseen_identities_matched=len(top20)-len(remaining),
            top20_unseen_identities_remaining=[dict(library=k[0],function=k[1]) for k in remaining],tasks=per_task)
    result=evaluate(selected)
    result.update(scope='Offline identity union of measured cases; selected cases match themselves. No new workload, replay, reweighting, stability claim or claim of all-operation/minimum workload coverage.',
        alternative=evaluate(('pdfwf005','021','029')) if all(t in tasks for t in ('pdfwf005','021','029')) else None,
        exact_top20_function_cover=minimum_function_cover(new,top20),
        exact_all_function_cover=minimum_function_cover(new,set().union(*new.values())))
    return result

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
        function_presence={task:function_presence(baselines,t) for task,t in tasks.items()},
        hotspot_coverage={task:hotspot_coverage(baselines,t) for task,t in tasks.items()},
        topk_presence={task:topk_presence(baselines,t) for task,t in tasks.items()},
        weighted_topk_presence={task:{str(k):weighted_topk_presence(baselines,t,k) for k in (10,20)} for task,t in tasks.items()},
        coverage_augmentation=augmentation_analysis(baselines,tasks),
        top20_unseen_operations={task:top20_unseen_operations(baselines,t) for task,t in tasks.items()},
        function_presence_method='Complete saved resolved physical function lists for OPM, TLC and their deduplicated union; exact DSO basename plus full symbol; target full ROI period denominator includes unresolved weight. Presence does not imply representative weight, business-operation coverage or a new mechanism when absent.',
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
    figures.update(plot_coverage(result,out))
    return figures


def plot_coverage(result,out):
    """A measured-period stack; never synthesize samples or normalize known rows."""
    from matplotlib import pyplot as plt
    keys=('observed_share_roi','not_observed_share_roi','unresolved_share_roi')
    labels=('旧例已覆盖函数','旧例未覆盖函数','未解析')
    colors=('#3976a8','#e6a04b','#bcbcbc')
    fig,ax=plt.subplots(figsize=(14,8.4),layout='constrained')
    tasks=[k for ids in GROUPS.values() for k in ids]
    ys=[i+i//3*.55 for i in range(len(tasks))]
    positions={k:i for i,k in enumerate(tasks)}
    for index,bucket in enumerate(keys):
        values=[];left=[]
        for task in tasks:
            parts=result['function_presence'][task]['OPM+TLC']
            values.append(100*parts[bucket])
            left.append(100*sum(parts[k] for k in keys[:index]))
        ax.barh(ys,values,left=left,height=.7,color=colors[index],label=labels[index],edgecolor='white',linewidth=.5)
        for y,v,l in zip(ys,values,left):
            if v>=5:ax.text(l+v/2,y,f'{v:.1f}%',ha='center',va='center',fontsize=10,color='white' if index==0 else 'black')
    for task in tasks:
        unseen=result['function_presence'][task]['OPM+TLC']['not_observed_share_roi']
        ax.text(102,ys[positions[task]],f'未覆盖 {100*unseen:.2f}%',va='center',fontsize=10)
    ax.set_yticks(ys,[fmt+' '+task_label(k) for fmt,ids in GROUPS.items() for k in ids],fontsize=10)
    ax.invert_yaxis();ax.set_xlim(0,122);ax.set_xticks(range(0,101,20));ax.axvline(100,color='#aaa',linewidth=.7)
    ax.set_xlabel('占新任务完整用户态采样周期的比例（%）；每条合计 100%')
    ax.set_title('旧 OPM＋TLC 对新增任务的函数覆盖\n按库文件名＋完整物理叶函数名匹配；覆盖比例按新任务周期权重计算',fontsize=13,pad=43)
    ax.legend(ncol=3,loc='lower center',bbox_to_anchor=(.48,1.01),frameon=False,fontsize=10)
    ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
    for spine in ('top','right','left'):ax.spines[spine].set_visible(False)
    files={}
    for ext in ('svg','png'):
        path=out/'figures'/f'function-hotspot-coverage.{ext}'
        fig.savefig(path,dpi=150,metadata={'Date':None} if ext=='svg' else None)
        if ext=='svg':path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
        files[str(path.relative_to(ROOT))]=sha(path)
    plt.close(fig)
    return files


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


def presence_pct(value):
    return '<0.01%' if 0<value<.0001 else pct(value)


def function_discussion(r):
    presence=r['function_presence']
    def cell(case,symbol,dso):
        row=next((f for f in case['functions'] if f['function']==symbol and f['library']==dso),None)
        return pct(row['share_roi']) if row else '未观察到'
    examples=[
      ('longest_match','libz.so.1.2.13',('031','037','013','014'),'同一压缩函数在旧例已存在，新任务中变重'),
      ('png_write_find_filter','libpng16.so.16.40.0',('031','037','009'),'旧例已有 Pillow 图片编码；这里出现不同库的具体编码函数'),
      ('Splash::pipeRun(SplashPipe*)','libpoppler.so.133.0.0',('021','026'),'旧 OPM 已出现的页面绘制函数进入新任务前列'),
      ('VerticalFilter._omp_fn.0','libMagickCore-7.Q16HDRI.so.10.0.2',('pdfwf005','021'),'ImageMagick 缩放／滤波路径；操作类型与旧 Pillow 缩放有共性'),
      ('vcl::(anonymous namespace)::ImplScaleConvolutionVer(Bitmap const&, Bitmap&, double const&, vcl::Kernel const&)','libvcllo.so',('021',),'LibreOffice 内部图片缩放，旧例采样未见该具体函数'),
      ('oox::drawingml::table::applyTableStylePart','libooxlo.so',('029',),'幻灯片表格样式处理；此行函数名为简写'),
      ('oox::PropertyMap::fillSequences','libooxlo.so',('029',),'文档对象属性整理与传递；此行函数名为简写')]
    rows=[]
    for symbol,dso,ids,meaning in examples:
        exact=symbol
        if symbol in ('oox::drawingml::table::applyTableStylePart','oox::PropertyMap::fillSequences'):
            exact=next(f['function'] for f in r['tasks']['029']['functions'] if f['function'].startswith(symbol+'('))
        rows.append([short_function(dict(function=symbol),70),
            cell(r['baselines']['OPM'],exact,dso),cell(r['baselines']['TLC'],exact,dso),
            '；'.join(k+'：'+cell(r['tasks'][k],exact,dso) for k in ids),meaning])
    word=[presence[k]['OPM+TLC']['observed_share_roi'] for k in GROUPS['Word']]
    ppt=[presence[k]['OPM+TLC']['not_observed_share_roi'] for k in GROUPS['PPT']]
    scattered=presence['026']['OPM+TLC']
    return [
      '### 7.3.1 先看操作：哪些只是权重变化，哪些确实增加步骤','',
      '**旧 PDF／OPM** 在固定表单中填写字段，并生成页面图片、缩放和检查。原来就有 Python、zlib 压缩、Pillow 图片处理和 Poppler 渲染。**旧 Excel／TLC** 对大型工作簿做检查、增强、保存、重算及缓存／CSV 验证，原来就有 Python 对象管理、XML 解析、XLSX 内部数据解压与重新压缩，以及 Calc 重算。','',
      '- **PDF 031／037：主要基础机制延续，工作比重改变。** 表单扁平化、材料修复和发布是不同业务目标，但仍可由已有解释执行、压缩、渲染和图片编码完成。不能仅凭任务名称改变，就判定产生全新的 CPU 计算机制。',
      '- **PDF pdfwf005：明确增加了拼图步骤，也改变了缩放工具。** 原 OPM 用 Pillow 缩放各页图片；本任务使用 ImageMagick 缩放，并用 montage 将多页缩略图排成 3×2 总览图。缩放这一类计算已有，拼图操作和具体软件路径则扩展了。',
      '- **Excel 013／014：在工作簿处理后增加预览链。** 两者都导出 PDF，再用 pdftoppm 转成 PNG；013 还用 ImageMagick 生成拼图。XLSX 仍是保留的交付物。这些步骤来自 Agent 原轨迹，不是为了分析而添加。',
      '- **Excel 016：核心操作与 TLC 较接近。** 旧例已有情景、公式与重算；在测试副本上切换情景再重算，主要增加执行次数和工作量，不应单列为新机制。016 同样导出 PDF 并渲染仪表板首页，所以其 LibreOffice 周期还包含转换处理，不能全部归为公式重算。','',
      '**如果排除 Excel 的预览发布链路：** 剩余工作簿加载、修改、保存、重算和验证，与旧 TLC 共用的基础机制较多。但本表统计仍是完整已采工作流，没有扣除 PDF、图片或拼图；不能据此给出“排除后覆盖了多少周期”的数值，也不能直接扣掉某个库，因为 zlib 和 LibreOffice 同时服务多种步骤。','',
      '### 7.3.2 不只看前十：旧例完整函数清单在新任务中占多少','',
      '**表 7-5A：以旧 OPM、旧 TLC 的完整已解析函数清单分别匹配，再取两者并集。** 这里“旧例”仅指这两个原始基准。每个百分比的分母都是对应新任务完整工作流的用户态采样周期，含未解析项；合并清单去重计数，不把 OPM、TLC 两列直接相加。','',
      table(['任务','旧 OPM 已见函数','旧 TLC 已见函数','旧两例合并已见','旧两例均未见','未解析'],[
       [k+'（'+fmt+'）',*[presence_pct(presence[k][ref]['observed_share_roi']) for ref in ('OPM','TLC','OPM+TLC')],
        presence_pct(presence[k]['OPM+TLC']['not_observed_share_roi']),presence_pct(presence[k]['OPM+TLC']['unresolved_share_roi'])]
       for fmt,ids in GROUPS.items() for k in ids]),'',
      '**如何解释“已见”：** 表示旧采样中观察到相同“函数名＋库文件名”的执行路径，哪怕旧例中占比很小也算已见。因此，它回答函数是否出现过，不能单独证明旧负载已经充分突出、代表或覆盖相同计算成本。前三个已见列相互重叠，只有“旧两例合并已见＋旧两例均未见＋未解析”构成 100%。','',
      '**如何解释“未见”：** 表示旧保存清单中没有采到该具体函数，不是证明从未执行，更不是自动证明一种全新的算法。这里可能包含新的文档对象操作、不同软件实现、通用辅助函数及采样／符号差异。未解析部分单列，不算成旧例已覆盖，也不算成新机制。','',
      '### 7.3.3 具体函数举例：旧函数变重、不同实现与新对象路径','',
      '**表 7-5B：函数级实例。** 下表的百分比仍以各自完整工作流采样周期为分母；“未观察到”检索的是完整旧清单，不只是旧 Top-10。完整签名与所属库在实验数据记录及机器结果中保留。','',
      table(['函数（部分简写）','旧 OPM','旧 TLC','新任务占比','应该怎样归类'],rows),'',
      '**为什么单个新函数只有 1%～2%，总差异却不小？** 函数可以分散在许多不同路径上，不能把举例的几个函数当作全部未见项。',
      f"例如 PPT 026 有 **{scattered['not_observed_function_count']} 个**已解析函数未出现在旧两例清单中，单个最高约 **{pct(scattered['not_observed_top20'][0]['share_roi'])}**，但合计占完整采样周期 **{pct(scattered['not_observed_share_roi'])}**。这解释了为什么只看几个新增热点容易低估清单差异。",'',
      '**按格式回答“旧例有没有体现这些热点”：**','',
      '- **PDF：031／037 的大部分周期落在旧例已见函数中，不能概括为主要基础机制全新。** 既有压缩函数变重，同时出现 libpng 编码路径；pdfwf005 另有 ImageMagick 与拼图，函数清单变化更明显。',
      '- **Excel：旧读写、XML、压缩、重算机制继续存在，但完整新流程还包括预览发布。** 不能因旧 TLC 前十函数在新任务占比低就说基础工作全未覆盖，也不能因共用 openpyxl／Calc 就说所有函数热点都已覆盖。016 再次重算属于已有机制重复执行。',
      f"- **Word：共有函数占主要权重。** 旧 OPM／TLC 合并清单中的函数，在三项 Word 中占 **{pct(min(word))}～{pct(max(word))}**；其余含不同实现的图片编码和文档处理函数。当前尚不能把未见部分全部称为 Word 独有排版机制。",
      f"- **PPT：旧采样未见的具体函数合计并不低。** 三项约为 **{pct(min(ppt))}～{pct(max(ppt))}**，包括对象样式、属性、图像与渲染等路径。029 的表格样式函数提供了直接的对象处理证据；021／026 的一些 Poppler 大热点则早已存在，只是明显变重。",'',
      '**讲解时的结论：旧例已经体现相当一部分基础函数，但前十名重合度、完整函数出现范围、计算机制是否相同是三个不同问题。** 共有函数需要看权重是否充分体现；未见函数需要进一步区分业务对象处理、软件实现和辅助路径，不能把“未见周期”直接命名为“全新计算机制周期”。','']


# Editorial focus for the concise report; every remainder stays explicit.
UNSEEN_FOCUS_TOOLS={
    '031':('PNG',),'037':('PNG',),'pdfwf005':('ImageMagick','PNG'),
    '013':('ImageMagick','PNG'),'014':('PNG',),'016':('Python','LibreOffice·其他组件'),
    '001':('PNG',),'003':('PNG','lxml'),'009':('PNG',),
    '021':('ImageMagick','LibreOffice·VCL','Poppler'),
    '026':('Poppler','LibreOffice·VCL'),'029':('LibreOffice·OOXML',)}
UNSEEN_OPERATIONS={
    '031':'材料包扁平化／发布后渲染 PNG；旧 OPM 已有渲染，此处体现另一种图片编码实现。',
    '037':'修复材料并生成页面预览；已有渲染操作中出现不同的 PNG 编码函数。',
    'pdfwf005':'渲染后用 ImageMagick 缩放并拼图；旧例用 Pillow 缩放，没有这条 montage 拼图链。',
    '013':'工作簿处理后导出 PDF、渲染 PNG 并拼图，图像处理链扩展；旧 OPM 已有 PDF 渲染。',
    '014':'工作簿修补、重算后导出 PDF 和 PNG，增加 Excel 的预览发布链。',
    '016':'情景切换、再次重算及首页预览；两项是通用运行时／框架函数，不能据此分配具体操作的 CPU。',
    '001':'Word 构建／转换后生成预览；表中识别的是图片编码，不能当作 Word 排版占比。',
    '003':'元数据／结构清理及预览交付，对应 XML 处理和 PNG 编码。',
    '009':'事件手册发布与预览，较明显的未覆盖部分是 PNG 编码。',
    '021':'幻灯片整改后预览与图片处理，进入图像滤波及页面绘制的不同子路径。',
    '026':'图表重建后转换与预览，进入 Poppler 绘制和 LibreOffice 图形层的不同子路径。',
    '029':'幻灯片表格样式及属性组织；可直接定位到 OOXML 对象函数，其他差额不全部归为对象处理。'}


def unseen_explanation(result,task):
    """Select explainable tool groups without assigning their CPU to a phase."""
    coverage=result['hotspot_coverage'][task]
    functions=coverage['unseen_functions']
    groups=[]
    for tool in UNSEEN_FOCUS_TOOLS[task]:
        rows=[f for f in functions if f['tool']==tool]
        if rows:
            groups.append(dict(tool=tool,period=sum(f['period'] for f in rows),
                example=max(rows,key=lambda f:f['period'])))
    total=sum(f['period'] for f in functions)
    remainder=total-sum(g['period'] for g in groups)
    if remainder<0:raise ValueError('overlapping unseen explanation')
    return dict(groups=groups,remainder_period=remainder,total_period=total)


def selection_advice(r):
    a=r['coverage_augmentation'];exact=a['exact_top20_function_cover']
    return ['**优先补充方案：保留旧 OPM／TLC，增加 Excel 013、PPT 021、PPT 029。** 三例分别补充图片编码与拼图链、复杂页面／图像处理、幻灯片对象样式；具体函数和权重见 7.3.3。','',
      '这是面向明确操作缺口的三例建议，不是全函数最小集合。Python、文本和公共框架的剩余差异继续保留；较小输入可能放大固定开销，但尚未完成控制规模验证，不据此删除差额。','',
      '**如果要求严格覆盖当前遗漏函数，最小数量另算：** 覆盖十二项 Top-20 中全部 '+str(a['top20_unseen_unique_count'])+' 个旧例未见函数，至少补 **'+str(exact['minimum_count'])+' 例**；一套最小组合是 **'+'；'.join(r['tasks'][task]['format']+' '+task for task in exact['solutions'][0])+'**（旧 OPM／TLC 另行保留）。若连全部已解析长尾也要求覆盖，至少补 '+str(a['exact_all_function_cover']['minimum_count'])+' 例。三例是优先补操作缺口的建议，不承诺全函数覆盖。','',
      '当前方案不自动修改正式任务集合，也不将选中任务与自身匹配算作跨任务验证。候选的稳定性仍需独立重复确认。','']


def hotspot_report_section(r,out):
    rows=[]
    for fmt,ids in GROUPS.items():
        for task in ids:
            p=r['function_presence'][task]['OPM+TLC']
            rows.append([fmt+' '+task,*[presence_pct(p[k]) for k in ('observed_share_roi','not_observed_share_roi','unresolved_share_roi')]])
    chart='../'+str((out/'figures/function-hotspot-coverage.svg').relative_to(ROOT))
    def weight(task,tool):
        return pct(sum(g['share_roi'] for g in r['hotspot_coverage'][task]['unseen_by_tool'] if g['tool']==tool))
    def ranked(task):return r['weighted_topk_presence'][task]['10']
    a=r['coverage_augmentation'];alt=a['alternative']
    checks=[]
    for task in ('031','037','pdfwf005','014','016','001','003','009','026'):
        p=a['tasks'][task]
        checks.append([r['tasks'][task]['format']+' '+task,pct(p['before_not_observed_share_roi']),pct(p['not_observed_share_roi'])])
    return ['### 7.3 旧用例的基础计算代表性与值得补充的操作','',
      '**旧 OPM／TLC 仍具有基础计算代表性，补充任务应围绕明确增量选择。** 旧 OPM 已执行表单填写、页面渲染、图片缩放与检查；旧 TLC 已执行大型工作簿加载、增强、保存、重算和验证，覆盖解释执行、对象管理、XML 解析、压缩／解压、图像与渲染等多类计算。扩展任务仍有相当部分周期落在这些相同函数上；实际缺口主要需要区分操作扩展、实现差异及运行时成本。','',
      '### 7.3.1 先看计算权重：旧例实际体现了多少','',
      '**表 7-4：旧 OPM＋TLC 完整函数清单并集的周期加权覆盖。** 函数按库文件名＋完整物理叶函数名精确匹配，旧例低频出现也计为已覆盖。分母为每项新任务完整 ROI 的用户态 `cycles:u` sample period；已覆盖、未覆盖、未解析三部分合计约为 100%。它说明采样中相同函数的出现范围和当前权重，不是函数数量或整轮 CPU 时间占比。','',
      table(['新任务','旧例已覆盖周期','旧例未覆盖周期','未解析'],rows),'',
      '![旧 OPM＋TLC 对新增任务的函数覆盖]('+chart+')','',
      '**读图：** 蓝色为旧两例采样已见函数在新任务中的权重；橙色为旧采样未见，灰色为未解析。PDF 031／037 的已覆盖周期约为 79%／73%，Word 三项约为 65%～72%，说明原有负载持续体现主要基础计算。pdfwf005 与 PPT 021 约为 45%／47%，则明确提示还需解释较大的差异，不能概括为全部任务都已充分覆盖。','',
      '**为什么不以 Top-10 个数判定代表性：**','',
      '- **函数少量重合也可能覆盖主要计算。** PDF 031 匹配 '+str(ranked('031')['observed_count'])+'/10，但这些函数承担其 Top-10 周期的 **'+pct(ranked('031')['observed_share_selected'])+'**；Top-10 本身占完整周期 '+pct(ranked('031')['selected_share_roi'])+'，全部已匹配函数占完整周期 '+pct(r['function_presence']['031']['OPM+TLC']['observed_share_roi'])+'。',
      '- **数量重合较多也可能漏掉重热点。** pdfwf005 匹配 '+str(ranked('pdfwf005')['observed_count'])+'/10，却只覆盖其 Top-10 周期的 **'+pct(ranked('pdfwf005')['observed_share_selected'])+'**，因为未匹配的 ImageMagick 和 PNG 函数很重。',
      '- **热点分散时，前十不能代表整项任务。** Excel 016、PPT 029 的 Top-10 仅占完整周期 **'+pct(ranked('016')['selected_share_roi'])+'／'+pct(ranked('029')['selected_share_roi'])+'**；其余路径仍需纳入完整分母。','',
      'Top-10／Top-20 数量、权重与逐项未匹配清单完整保留在[实验数据记录](experimental-results.md#九扩展任务操作十二项-docops-完整记录)。所有任务均按相同规则计算，完整权重与未解析部分一并保留。','',
      '### 7.3.2 差异为何出现：操作、实现与输入规模分开解释','',
      '**已有函数变重，不等于出现全新计算。** 旧 OPM 已有页面渲染和图片缩放；新预览链中某些 Poppler 函数更突出，说明工作重心变化。旧 TLC 已有情景与重算，016 再次重算主要增加次数和工作量，不单列新机制。','',
      '**相同操作可以进入不同软件实现。** 新 libpng 编码、ImageMagick 缩放与旧图片操作有共性，但具体代码路径不同。尤其 montage 拼图是实际步骤扩展，不能因为旧例也输出图片就忽略。','',
      '**较小输入可能使固定开销更加显眼。** 数据处理量下降时，脚本解析、编译、导入库和组件初始化仍需完成，因而可能进入 Top-10／Top-20。增加回放轮数能改善采样，但每轮重新启动的脚本仍会重复这些开销。小输入不必然产生更多函数，而可能提高辅助函数的相对权重。当前任务还同时改变了脚本和操作，尚未通过控制规模实验确认这一因素的贡献。','',
      table(['剩余差异','当前解释与处理'],[
       ['Python 运行时（含解析／编译）','031／037 中未匹配 Python 函数合计占完整周期 '+weight('031','Python')+'／'+weight('037','Python')+'。可能受脚本源码及启动方式影响；保留权重，先核对调用位置，不直接命名为新的文档操作。'],
       ['公共框架、对象与配置','部分可能是固定初始化成本，部分可能随业务对象增长；具体调用目的未定位前，不推断新增排版、重算或加密任务。'],
       ['文本／XML 处理','大小写转换、元数据清理等可能是真实业务差异，不能全部归因于小输入；结合剩余权重和调用链继续核对。']]),'',
      '**这些差异保留统计，但暂不据此单独增补任务。** “可能受规模影响”不是删除差额的理由，也不意味着 Python／公共库的所有具体函数已由旧例充分体现。反过来，不应仅为少量零散函数未匹配就扩大任务集；先看同类函数的累计权重及其具体操作。','',
      '### 7.3.3 有价值的缺口与优先补充的三例','',
      '**建议保留旧 OPM／TLC，优先补 Excel 013、PPT 021、PPT 029。** 选择依据是可定位的实际操作与有分量的函数路径，而非文件格式数量。','',
      '**表 7-5：补什么操作、由哪个任务体现。** 下列百分比为对应工具中旧例未匹配函数占该任务完整采样周期的权重，不是所列操作阶段的独立计时。','',
      table(['补充用例','值得补充的路径及周期占比','实际操作与代表函数'],[
       ['Excel 013：投标评审发布','ImageMagick '+weight('013','ImageMagick')+'；PNG '+weight('013','PNG'),
        '工作簿重算后导出 PDF、生成 PNG 和 montage 拼图。HorizontalFilter／VerticalFilter、CompositeOverImage、png_write_find_filter。补具体缩放／合成和编码实现。'],
       ['PPT 021：庇护所无障碍整改','VCL 图像路径 '+weight('021','LibreOffice·VCL')+'；Poppler '+weight('021','Poppler')+'；JPEG '+weight('021','JPEG'),
        '幻灯片转换、页面预览与缩略图链，进入卷积缩放、像素绘制和编解码。ImplScaleConvolutionVer、Splash::scaleImage*、expandRow 等。'],
       ['PPT 029：季度业务回顾发布','明确 OOXML 对象／样式路径 '+weight('029','LibreOffice·OOXML'),
        '幻灯片表格样式应用与对象属性组织。applyTableStylePart、PropertyMap::fillSequences，补充图像处理之外的直接对象操作路径。']]),'',
      '**为什么这三例可以少量补缺口：** 使用旧两例加上这三例的完整函数清单，十二项任务 Top-20 中原来旧例未见的 **'+str(a['top20_unseen_unique_count'])+' 个去重函数**，有 **'+str(a['top20_unseen_identities_matched'])+' 个**能够匹配，剩 **'+str(len(a['top20_unseen_identities_remaining']))+' 个**。这是既有清单的离线集合核对，不是重跑结果；三例作为参考时会匹配自身，不能将此计为独立跨任务验证。','',
      '**对未入选任务，未覆盖周期也有明显缩小。** 分母仍为各目标任务完整 ROI，未解析项保留且不变，以下不列三项参考任务自身。','',
      table(['未入选目标任务','仅旧两例：未覆盖周期','加入013＋021＋029后：仍未覆盖'],checks),'',
      '**替代与剩余：** pdfwf005 也能提供 ImageMagick／PNG 链，但以其替代 013 后，上述 '+str(a['top20_unseen_unique_count'])+' 个目标函数仍剩 '+str(len(alt['top20_unseen_identities_remaining']))+' 个未匹配，因此当前先选 013。026 的 Top-20 图像／绘制未匹配函数在三例清单中已能找到，但其完整周期仍有 '+pct(a['tasks']['026']['not_observed_share_roi'])+' 未匹配；不能据此宣称 026 的全部路径都已覆盖。文本、Python 和公共框架差异继续保留，不承诺三例消除全部遗漏。','',
      '**“三例”是明确操作缺口的优先方案，不是严格全函数最小集合。** 按保存的具体函数身份枚举，覆盖全部 '+str(a['top20_unseen_unique_count'])+' 个旧例未见 Top-20 函数至少需 '+str(a['exact_top20_function_cover']['minimum_count'])+' 个新增任务；若连全部已解析长尾都要求覆盖，则需 '+str(a['exact_all_function_cover']['minimum_count'])+' 项。详细组合和剩余函数在实验数据记录中保留，不以追求全匹配作为当前选型目标。','',
      '**本节结论：旧用例具有基础计算代表性，补充应针对明确增量。** 已有表单与大型工作簿负载继续体现多类共同计算；优先用 013、021、029 补图片编码与拼图、复杂图像／页面处理、幻灯片对象样式。规模可能放大的运行时差异继续核对，既不将其全部当成新业务机制，也不抹去实际权重。','']


TOP20_OPERATION_NOTES={
    '图片编码／解码':'预览图片的读写、编码滤波或颜色转换；旧例已有图片输出，差异在具体编码实现。',
    '图像缩放／滤波／合成':'缩略图、图片缩放及合成处理；结合任务中的 montage 或转换链解释，不能把每个函数都称为拼图。',
    '页面／像素绘制':'页面图像的缩放、裁剪、抗锯齿、像素读写或合成；关联转 PDF／页面预览，属于已有渲染类型的不同子路径。',
    '字体处理':'字体匹配、替换等辅助路径；关联文档转换和预览，不据此认定新增分页算法。',
    '文档对象／样式':'表格样式应用、对象属性组织或单元格样式查询；按具体函数区分 PPT 对象处理与已有 Calc 类型。',
    'Python 运行时':'Python 代码解析、编译和代码对象处理；服务于构建、校验等脚本，具体脚本归属尚未定位，不是 PDF 文本分词。',
    '文本／XML 处理':'字符串大小写转换或 XML 字符串比较；关联构建与检查链，不能仅凭符号锁定某条元数据清理语句。',
    '公共框架／基础库':'UNO 类型／属性、配置查询、容器或字符转换等通用支撑；不能直接作为新增文档操作。',
    '安全组件':'安全库内部算术；仅确认组件路径，具体调用目的未定位，不据此宣称任务新增加密操作。',
}


def top20_operation(row):
    """Explain selected symbols; preserve generic support as a separate category."""
    tool,kind,_=unseen_function_type(row)
    name=row['function']
    if name.startswith('ScColumnData::GetMostUsedPattern'):
        return 'LibreOffice·Calc','文档对象／样式'
    if tool=='Python':
        return tool,('文本／XML 处理' if name in ('_PyUnicode_ToLowerFull','do_upper_or_lower') else 'Python 运行时')
    if tool=='LibreOffice·VCL' and 'SetPixel' in name:
        return tool,'页面／像素绘制'
    if kind=='图片编码／解码':return tool,'图片编码／解码'
    if kind=='图片滤波／缩放':return tool,'图像缩放／滤波／合成'
    if kind=='页面／像素绘制':return tool,'页面／像素绘制'
    if kind=='字体／文本图形处理':return tool,'字体处理'
    if kind=='文档对象／样式路径':return tool,'文档对象／样式'
    if kind=='XML／结构解析':return tool,'文本／XML 处理'
    if kind=='运行支撑／安全组件':return tool,'安全组件'
    return tool,'公共框架／基础库'


def top20_unseen_operations(references,target):
    selected=topk_presence(references,target)['20']
    rows=[]
    for f in selected['functions']:
        if not f['observed']:
            tool,operation=top20_operation(f)
            rows.append(dict(f,tool=tool,operation=operation,
                             interpretation=TOP20_OPERATION_NOTES[operation]))
    return rows


def top20_display_name(name):
    # Display abbreviations only; matching and machine records keep full symbols.
    if name.startswith('std::_Rb_tree<int,'):
        return 'std::_Rb_tree<int, …>::_M_get_insert_unique_pos'
    if name.startswith('std::_Rb_tree<rtl::OUString,'):
        return 'std::_Rb_tree<rtl::OUString, …>::find'
    name=name.replace('(anonymous namespace)::','').removeprefix('void ')
    return name.split('(',1)[0]


def top20_inventory_section(r):
    evidence={task:top20_unseen_operations(r['baselines'],r['tasks'][task])
              for ids in GROUPS.values() for task in ids}
    lines=['### 9.6D Top-10／Top-20 数量、权重与完整未匹配清单','',
      '旧参考为 OPM＋TLC 的完整已解析函数并集，包含旧例低频函数。下表的“已见数”按函数身份计数；“已见占 Top-10 周期”以所选十个函数的周期和为分母，“Top-10 占 ROI”以目标完整 ROI 为分母。所有排序按 period 降序，平手按库名＋完整符号排序。','',
      table(['任务','Top-10 已见数','Top-20 已见数','Top-10 占 ROI','已见占 Top-10 周期'],[
        [task,str(r['topk_presence'][task]['10']['observed_count'])+'/'+str(r['topk_presence'][task]['10']['selected_count']),
         str(r['topk_presence'][task]['20']['observed_count'])+'/'+str(r['topk_presence'][task]['20']['selected_count']),
         pct(r['weighted_topk_presence'][task]['10']['selected_share_roi']),pct(r['weighted_topk_presence'][task]['10']['observed_share_selected'])]
        for task in r['tasks']]),'',
      '以下完整列出每项 Top-20 中旧例未匹配函数。# 为新任务排名，函数数等于 Top-20 实际选取数减已匹配数。仅显示时简写参数，匹配仍使用完整符号；操作关联不代表单独测得该阶段 CPU 成本。','']
    for fmt,ids in GROUPS.items():
        for task in ids:
            missing=evidence[task];groups={}
            for f in missing:groups.setdefault((f['tool'],f['operation']),[]).append(f)
            rows=[]
            for (tool,operation),fs in groups.items():
                symbols='；'.join('#'+str(f['rank'])+' `'+top20_display_name(f['function'])+'`' for f in fs)
                rows.append([tool+'／'+operation+'（'+str(len(fs))+' 个）',symbols,TOP20_OPERATION_NOTES[operation]])
            lines += ['**'+fmt+' '+task+'：Top-20 未覆盖 '+str(len(missing))+' 个。**','',
              '实际链路：'+FLOWS[task]+'。 [冻结命令](../docops/payload/tasks/'+task+'/recipe.json)','',
              table(['工具／操作类别','全部未覆盖函数（新任务排名）','关联操作与解释'],rows),'']
    return lines

def main_section(r,out):
    lines=['## 七、扩展任务操作：与原始 PDF/XLSX 基准比较','',
      '前六节保留原七例“跨行业输入”实验及其提出的场景扩展问题。本节报告十二项 DocOps L3 的真实轨迹回放：在 PDF／Excel 中改变任务操作，并加入 Word／PPT，分别与原始 OPM／TLC 比较。',
      '**先看判断：原七例在已测跨行业输入下具有基础计算代表性；更广的操作需要有针对性地补充。** 本次既观察到原有函数继续承担主要计算，也定位了图像处理与文档对象路径的增量。以下依次说明工具、函数覆盖和 CPU 指标变化。','',
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
      *hotspot_report_section(r,out),
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
      '**结论是：保留旧 OPM／TLC 作为基础，优先用三例补充明确操作增量。** 旧例继续体现多类共同计算；扩展中的具体图像实现、拼图和幻灯片对象路径有值得补充的实际权重，未匹配数量不能直接当成新增机制数量。','',
      '- **原七例的结论继续成立。** 保持表单填写或大型工作簿增强等任务形态时，更换行业输入仍延续主要热点，已有负载有明确用途。',
      '- **函数出现范围和热点权重需要分别评价。** 旧例已经执行过的函数，在新任务中可能从很小的权重变成主要热点；旧前十排名重合少，不等于所有基础函数都未覆盖。',
      '- **操作扩展与实现变化需要分开。** 拼图、预览发布和具体幻灯片对象样式处理扩展了本批执行路径；Pillow 与 ImageMagick 的缩放有计算共性。016 再次重算主要改变次数和权重，不单列新机制。',
      '- **未见清单也需要保留。** 表 7-4 的完整周期分区包含所有已解析函数与未解析权重；较小输入可能使代码解析或框架初始化突出，但尚未控制规模验证，不据此删除差额。',
      '- **代表范围需要扩展。** 原负载可以代表已测 PDF 表单与大型工作簿任务，单独用它们代表更广的 Word、PPT 及复杂文档操作仍不充分；本次十二项补充了这部分实测证据。',
      '- **后续优先按操作选型。** 保留原有跨行业输入对照，补充能带来不同热点的文档构建、对象处理、布局与渲染任务；先对候选做独立重复，再决定最终基准集合。连续长文档分页等是否形成主导热点，还需专项实测。','',
      *selection_advice(r),
      '[完整扩展实验记录](experimental-results.md#九扩展任务操作十二项-docops-完整记录)保留九项指标、24 组基准对照、完整函数名单和全部曲线；[机器结果与来源绑定](../'+str((out/'comparison.json').relative_to(ROOT))+')可逐项追溯。','']
    from scaling_report_sections import revise_assessment
    return revise_assessment('\n'.join(lines))



def presence_detail(r):
    rows=[]
    for task,scopes in r['function_presence'].items():
        for name,p in scopes.items():
            rows.append([task,name,p['observed_period'],p['not_observed_period'],p['unresolved_period'],
                f"{100*p['observed_share_roi']:.6f}",f"{100*p['not_observed_share_roi']:.6f}",
                f"{100*p['unresolved_share_roi']:.6f}",p['not_observed_function_count']])
    lines=['### 9.6A 完整函数清单的出现范围与周期分区','',
      '该补充统计以 OPM、TLC 各自完整已解析函数清单及其去重并集为参考，按库文件名＋完整物理叶函数名精确匹配。统计目标是新任务中哪些函数已由旧采样观察到；不限定旧前十，也不将旧清单未见项等同为新业务算法或新计算机制。','',
      '对每个新任务、每个参考范围：已见 period＋未见 period＋未解析 period＝新任务完整 ROI period。以下百分比的分母均为目标完整 ROI。OPM 与 TLC 出现集合有交集，不相加；OPM+TLC 使用去重并集。旧例中极低权重函数也算已见，故“路径出现过”不证明旧负载充分体现相同成本。','',
      table(['任务','参考清单','已见 period','未见 period','未解析 period','已见 %','未见 %','未解析 %','未见函数数'],rows),'',
      '### 9.6B 旧两例均未见的主要具体函数','',
      '下表每项列旧 OPM／TLC 合并清单未见函数中的前十项，按目标完整 ROI period 排序；函数名称显示最多 180 字符，完整签名和 period 仍在 comparison.json 的函数列表及 function_presence 字段中。旧采样未见不证明永不执行；通用辅助路径、不同实现和具体对象操作分别解释。']
    for task,scopes in r['function_presence'].items():
        p=scopes['OPM+TLC']
        lines+=['',f'**{task_label(task)}：未见函数 {p["not_observed_function_count"]} 个，合计 {pct(p["not_observed_share_roi"])}。**','',
            table(['函数','库文件名','目标 period','完整 ROI 占比'],[
                [short_function(f,180),f['library'],f['period'],pct(f['share_roi'])] for f in p['not_observed_top20'][:10]])]
    lines+=['','以上只新增既有数据的集合统计，没有重跑、导出或重新采样。原任务 profile、原基准函数权重、Topdown 指标及 533 个过程点保持原样。','']
    return lines


def hotspot_detail(r):
    lines=['### 9.6C 热点权重分区、工具归属与分类规则','',
      '旧热点阈值与新热点阈值均为完整 ROI 的 0.5%。旧清单先按 DSO 文件名＋完整符号合并，同一函数只要在任一旧基准达到阈值即记为旧热点；旧权重取两者最大值作阈值判断，不把两个独立任务的占比相加或平均。以下四分区覆盖目标全部采样周期，非热点长尾和未解析项都保留。','',
      table(['任务','旧热点函数 period','旧低频函数 period','旧未见函数 period','未解析 period','新热点总数','其中旧未见热点数','未见热点 period'],[
          [task,*[p['period'] for p in c['partition']],c['target_hotspots']['count'],
           c['target_hotspots']['count_by_bucket']['unseen'],c['target_hotspots']['period_by_bucket']['unseen']]
          for task,c in r['hotspot_coverage'].items()]),'',
      '分类只对旧两例均未观察到的已解析函数进行；每个函数只归一个类型和一个工具，分别汇总为两种视图。“工具×类型”交叉分组是第三种视图，不能把三种视图的周期相加。具体规则及每个函数的工具、类型、解释在 comparison.json 的 hotspot_coverage 字段中保留。','',
      '明确 DrawingML／对象属性符号归为对象路径；PNG／JPEG 归为编码；ImageMagick、Pillow 和 VCL 的明确 Bitmap／Convolution／Blur 函数归为图像处理；Python、UNO／配置／容器、安全库分别作为运行支撑或已有处理类型。仅有库名且无法解释业务用途的部分不强行标成新操作或新算法。']
    for task,c in r['hotspot_coverage'].items():
        lines+=['',f'**{task_label(task)}：全部旧未见周期的互斥工具×类型分区。**','',
            table(['工具','类型','period','完整 ROI 占比'],[[g['tool'],g['type'],g['period'],pct(g['share_roi'])] for g in c['unseen_by_tool_type']])]
    lines+=['','统计是同一批旧数据的新增分组，不重新采样、不剔除或归一化未知权重，也不按阶段分配通用库周期。主报告的扩展建议为初选，不自动改变任务集合。','']
    return lines



def augmentation_detail(r):
    a=r['coverage_augmentation'];exact=a['exact_top20_function_cover']
    lines=['### 9.6E 三例补充方案的集合核验与严格最小组合','',
      '候选参考为旧 OPM／TLC 并集加 Excel 013、PPT 021、PPT 029 的完整已解析函数身份集合。对每个目标重新划分已见、未见、未解析 period；未解析分母不变。选中任务匹配自身属于集合构造，单独标记，不当作跨任务或未来输入验证。','',
      table(['目标','自身在新增参考中','原未见 period','新增参考后未见 period','新增参考后未见 %','未解析 period'],[
        [task,p['selected_as_reference'],p['before_not_observed_period'],p['not_observed_period'],pct(p['not_observed_share_roi']),p['unresolved_period']]
        for task,p in a['tasks'].items()]),'',
      'Top-20 目标集合：十二项已解析函数各取前二十，减去旧并集，再对身份去重。候选任务提供完整函数集合，允许函数在候选中低频出现，不能据此保证同样的热点权重。','',
      '原目标 '+str(a['top20_unseen_unique_count'])+' 个；三例匹配 '+str(a['top20_unseen_identities_matched'])+' 个，剩 '+str(len(a['top20_unseen_identities_remaining']))+' 个：','',
      table(['库文件名','仍未匹配的完整函数'],[[f['library'],'`'+f['function']+'`'] for f in a['top20_unseen_identities_remaining']]),'',
      '严格集合覆盖枚举全部候选子集，结果仅适用于已保存函数，不等于未来请求或全部操作的最小基准。Top-20 目标的最小新增数为 '+str(exact['minimum_count'])+'，共有 '+str(len(exact['solutions']))+' 套并列方案：','',
      table(['方案','新增任务'],[[i,'、'.join(choice)] for i,choice in enumerate(exact['solutions'],1)]),'',
      '若目标改为全部已解析未见函数（含长尾），目标身份数 '+str(a['exact_all_function_cover']['required_function_count'])+'，最小新增数 '+str(a['exact_all_function_cover']['minimum_count'])+'。这不是要求实际增加全部任务，而是说明全函数收集与操作级代表性是不同目标。','',
      '以 pdfwf005、021、029 替代三例组合时，原 Top-20 目标仍剩 '+str(len(a['alternative']['top20_unseen_identities_remaining']))+' 个未匹配；两套方案逐目标完整周期保留在 coverage_augmentation。各目标比例独立计算，不合并不同任务的 period 或简单平均为代表性分数。','']
    return lines

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
      *presence_detail(r),
      *hotspot_detail(r),
      *top20_inventory_section(r),
      *augmentation_detail(r),
      '### 9.7 来源与离线复算','',
      '- 原始基准：`'+BASE_CONFIG+'`。','- 原始统一环境 perf：`'+PERF_CAMPAIGN+'`。',
      '- 离线符号结果：`'+ENRICHMENT+'`。','- 统一环境 DevKit：`'+TOPDOWN+'`。',
      '- 本节机器结果：`'+str((out/'comparison.json').relative_to(ROOT))+'`。','',
      '```bash','python3 -B analysis/docops/operation_comparison.py --update --publish','```','',
      '该命令只读取既有 JSON、日志与冻结 recipe，重建比较表、曲线及追加章节，不启动 workload、容器、perf、DevKit 或模型。','']
    from scaling_report_sections import append_detail
    return append_detail('\n'.join(lines))


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
            for k in result['tasks']} | {
            '../'+str((out/'figures/function-hotspot-coverage.svg').relative_to(ROOT)):
                str((out/'figures/function-hotspot-coverage.svg').relative_to(ROOT))},
        presentation_figure_notes={
            '../'+str((out/'figures/function-hotspot-coverage.svg').relative_to(ROOT)):
            '旧 OPM＋TLC 合并参考；蓝色为已覆盖、橙色为未覆盖、灰色为未解析，按目标完整用户态采样周期计，每条合计 100%。'},
        original_seven_case_measurements_changed=False,new_measurements_executed=False)
    # Bind the supplementary scaling analysis as well as the twelve-case result.
    from scaling_report_sections import OUTPUT as SCALING_OUTPUT, SCALING
    supplement_paths=('analysis/docops/scaling_report_sections.py',SCALING,
                      SCALING_OUTPUT+'/selection.json',SCALING_OUTPUT+'/analysis-build.json')
    manifest['analysis_sources'].update({p:sha(ROOT/p) for p in supplement_paths})
    manifest['scaling_analysis']=dict(path=SCALING_OUTPUT+'/selection.json',
        sha256=sha(ROOT/SCALING_OUTPUT/'selection.json'),scope='20 configurations; 34 major operation identities')
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
