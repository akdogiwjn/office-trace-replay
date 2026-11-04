"""Offline first-batch DocOps comparison, with explicit sampling and symbol limits."""
import argparse
from collections import Counter
import csv
import itertools
import json
import math
from pathlib import Path
import re
import platform

from campaign import TASKS, check_archive, write
from pilot import HERE, ROOT, sha
from quality import function_qualification, workload_records

METRICS=('IPC','Bad Speculation','Frontend Bound','Backend Bound','Retiring',
         'Core Bound','Memory Bound','Fetch Latency Bound','Fetch Bandwidth Bound')
BOUNDS=METRICS[1:5]
VECTOR=(*METRICS,'idle_pct')
NAMES={'001':'受控文档发布修复','003':'公开记录元数据清理','009':'事件手册发布',
       '013':'采购投标评审发布','014':'灾害补助公开发布','016':'预测模型情景级联',
       '021':'庇护所无障碍整改','026':'气候披露图表重建','029':'季度业务回顾发布',
       '031':'听证材料包扁平化发布','037':'公交绕行材料修复','pdfwf005':'结算材料包重建'}


def cosine(a,b):
    if len(a)!=len(b)or not a or not all(math.isfinite(v)for v in (*a,*b)):
        raise ValueError('invalid vectors')
    norm=math.sqrt(sum(v*v for v in a)*sum(v*v for v in b))
    if not norm:raise ValueError('zero vector')
    return max(-1.,min(1.,sum(x*y for x,y in zip(a,b))/norm))


def library(dso):
    name=Path(dso).name
    for token,label in [('libpython','Python'),('libz.so','zlib'),('libpng','PNG'),
                        ('libpoppler','Poppler'),('libMagick','ImageMagick'),('libjpeg','JPEG'),
                        ('etree.','lxml'),('_elementpath.','lxml'),('libxml2','libxml2'),
                        ('libpixman','pixman'),('libcairo','cairo'),('libfreetype','FreeType'),
                        ('libharfbuzz','HarfBuzz'),('libexpat','expat'),('libc.so','libc'),
                        ('ld-linux','loader'),('libfontconfig','fontconfig')]:
        if token in name:return label
    if '/libreoffice/'in dso:return 'LibreOffice'
    return name


def resolved(symbol):
    return symbol not in ('[unknown]','[no-frame]')and re.fullmatch(r'0x[0-9a-fA-F]+|[0-9a-fA-F]{12,}',symbol)is None


def normalized_functions(profile):
    counts=Counter()
    for row in profile['functions']:
        if resolved(row['function'])and row['dso']not in ('[unknown]','[no-frame]'):
            counts[(Path(row['dso']).name,row['function'])]+=row['period']
    return [dict(library=k[0],function=k[1],period=v,share_roi=v/profile['roi_period'])
            for k,v in sorted(counts.items(),key=lambda kv:(-kv[1],kv[0]))]


def pair(a,b):
    x,y=a['topdown'],b['topdown']
    av,bv=([r['metrics'][k]for k in BOUNDS]for r in (x,y))
    aset={(r['library'],r['function'])for r in a['resolved_top10']}
    bset={(r['library'],r['function'])for r in b['resolved_top10']}
    comparable=len(aset)==10 and len(bset)==10
    quality=a['function_qualification']['function_profile_eligible']and b['function_qualification']['function_profile_eligible']
    return dict(a=a['task'],b=b['task'],format_a=a['format'],format_b=b['format'],same_format=a['format']==b['format'],
                bound_cosine=cosine(av,bv),
                raw_euclid_auxiliary=math.dist(x['vector'],y['vector']),
                observed_resolved_top10_common=len(aset&bset)if comparable else None,
                observed_resolved_top10_jaccard=len(aset&bset)/len(aset|bset)if comparable else None,
                function_comparison_quality='within_pilot_symbol_threshold'if quality and comparable else'limited_symbols_or_short_list',
                shared_functions=[dict(library=k[0],function=k[1])for k in sorted(aset&bset)],
                bound_delta_b_minus_a={k:y['metrics'][k]-x['metrics'][k]for k in BOUNDS})


def load_task(task,fmt,modes,enrichment):
    out=ROOT/enrichment['tasks'][task]['out'];profilepath=out/'profile.json'
    recordpath=out/'recovery-record.json';r=json.loads(recordpath.read_text())
    if sha(recordpath)!=enrichment['tasks'][task]['record_sha256']or r['status']!='passed':raise ValueError('recovery binding mismatch')
    checks=[check_archive(out)]
    original=ROOT/modes['perf']['workflow_out']
    for name,digest in r['original_sha256'].items():
        if sha(original/name)!=digest:raise ValueError('original perf evidence changed')
    counts,_,intervals=workload_records(original,task,10)
    profile=json.loads(profilepath.read_text())
    for key in ('functions','libraries','processes'):
        if sum(row['period']for row in profile[key])!=profile['roi_period']:raise ValueError('period conservation failed')
    tdout=ROOT/modes['topdown']['out'];tdpath=tdout/'collection.json';td=json.loads(tdpath.read_text())
    if sha(tdpath)!=modes['topdown']['record_sha256']or td['status']!='passed':raise ValueError('Topdown binding mismatch')
    checks.append(check_archive(tdout))
    workload_records(tdout,task,10)
    detail=json.loads((tdout/'topdown-summary.json').read_text())
    if detail['metrics']!=td['metrics']:raise ValueError('metric summary differs')
    metrics=td['metrics']
    if abs(sum(metrics[k]for k in BOUNDS)-100)>.03:raise ValueError('invalid Bound partition')
    if abs(metrics['Core Bound']+metrics['Memory Bound']-metrics['Backend Bound'])>.03:raise ValueError('invalid backend partition')
    if abs(metrics['Fetch Latency Bound']+metrics['Fetch Bandwidth Bound']-metrics['Frontend Bound'])>.03:raise ValueError('invalid frontend partition')
    libraries=Counter()
    for row in profile['libraries']:libraries[library(row['dso'])]+=row['period']
    recipepath=ROOT/'docops/payload/tasks'/task/'recipe.json';recipe=json.loads(recipepath.read_text())
    functions=normalized_functions(profile)
    return {'task':task,'name':NAMES[task],'format':fmt,'historical_score':recipe['historical_score'],
            'recipe_sha256':sha(recipepath),'workflow_steps':[{k:s[k]for k in ('id','name','phase','argv','cwd')}for s in recipe['steps']],
            'counts':counts,'roi_seconds':sum(end-start for start,end in intervals)/1e9,
            'roi_samples':profile['roi_samples'],'roi_period':profile['roi_period'],
            'quality':profile['quality'],'capture_quality':profile['capture_quality'],
            'notable_function_contexts':[r for r in profile['contexts']if r['function']=='blas_thread_server'],
            'function_qualification':function_qualification(profile['quality']),
            'processes':profile['processes'],'libraries':[dict(library=k,period=v,share_roi=v/profile['roi_period'])for k,v in libraries.most_common()],
            'functions':functions,'resolved_top10':functions[:10],
            'resolved_top10_share_roi':sum(r['share_roi']for r in functions[:10]),
            'topdown':{'metrics':metrics,'idle_pct':td['cpu_window']['idle_pct'],
                       'vector':[metrics[k]for k in METRICS]+[td['cpu_window']['idle_pct']],
                       'roi_seconds':td['roi_seconds'],'profiler_envelope_seconds':td['profiler_envelope_seconds'],
                       'outside_workflow_envelope_seconds':td['outside_workflow_envelope_seconds'],
                       'pmu_reads':(tdout/'devkit.stdout.txt').read_text().count('time of PmuRead:'),
                       'arithmetic':detail['arithmetic']},
            'evidence':{'perf_raw':str(original.relative_to(ROOT)),'profile':str(profilepath.relative_to(ROOT)),
                        'profile_sha256':sha(profilepath),'recovery_record':str(recordpath.relative_to(ROOT)),
                        'topdown_record':str(tdpath.relative_to(ROOT)),'topdown_record_sha256':sha(tdpath),
                        'perf_origin':modes['perf']['origin'],'topdown_origin':modes['topdown']['origin']},
            'archive_checks':checks}


def md_escape(value):
    return str(value).replace('|','&#124;').replace('\n',' ')


def report(result,folder):
    tasks=result['tasks'];pairs=result['pairs']
    lines=['# DocOps L3：十二任务首批热点与 Topdown 对比','',
      '本轮覆盖 Word、Excel、PPT、PDF 各三项。每任务每路一次独立采集，批内执行十轮最终有效回放；两路共 24 个 profile。031 复用已验证的两路，其余新增 22 路，新增采集均成功，没有 workload 重试。',
      '本报告用于初步观察同格式任务内部及不同格式间的差异；十轮批次不是十次独立采集，不计算重复稳定性或 CV。','',
      '**首批观察：同格式任务也存在负载差异，共用格式和工具并不保证函数热点相同。** Word 三项主要集中于渲染和 PNG 压缩；Excel 016 的重算／检查路径比另两项更突出；PPT 029 与另两项的 Python／LibreOffice 和 Poppler 权重不同；PDF 的结算材料包更多落在 ImageMagick 拼图路径。下文分别给出进程、库、函数和 PMU 证据，符号有限的比较单列。','',
      '## 1. 数据与质量','','| 格式 | 任务 | 内容 | perf 十轮 ROI 秒 | ROI 样本 | 未解析叶符号权重 | 已解析 Top-10 占 ROI |',
      '|---|---|---|---:|---:|---:|---:|']
    for task,t in tasks.items():lines.append(f"| {t['format']} | {task} | {t['name']} | {t['roi_seconds']:.2f} | {t['roi_samples']:,} | {t['quality']['unknown_leaf_symbol_share']*100:.2f}% | {t['resolved_top10_share_roi']*100:.2f}% |")
    limited=[k for k,v in tasks.items()if not v['function_qualification']['function_profile_eligible']]
    lines+=['',f"符号质量超过试点 20% 未解析门槛的任务：{'、'.join(limited)or'无'}。门槛没有放宽，采集成功与函数对比资格分别记录。所有未知权重保留在完整 ROI 分母；下文的“Top-10”均指已解析函数的前十项，不是把未知部分补成已知函数。",'',
      '## 2. 测量与计算方法','',
      f"实际镜像 `{result['image_id']}`；Python 3.12.14、openpyxl 3.1.5、LibreOffice 7.4.7.2、perf 6.1.190、DevKit 26.0.RC1。镜像与原七例的环境不同，本轮不将其百分比拼接成原七例的同环境对照。",'',
      'perf 对测量入口及后代采集 `cycles:u`，49 Hz、DWARF 16384、CLOCK_MONOTONIC；同镜像 `perf script --no-inline --ns -F +pid` 导出。统计只保留 workflow 步骤区间并集，排除调度器。分母为 ROI 原始 sample period；它不是整轮 CPU 秒。',
      '业务步骤 CPU affinity 为 0–7；调度、监测、准备和归档在 CPU 9。DevKit 在另一次批次按 CPU 0–7 采集，控制器在 CPU 9，命令为 `devkit tuner top-down -c 0-7 -L 0 -i 1 -l 0`。其最终 ALL 指标来自整个 PMU 包络，保留启动、间隙、结束及宿主活动；不冒充精确进程 ROI。',
      '独立官方评分未重跑；原始历史内容判定保持不变。回放成功指选定的最终依赖链和原有检查完成，不将其升级为官方任务内容通过。',
      '采集后的补符号只读挂载匹配 build-id 的调试文件；逐样本确认采样键、地址和物理 DSO 未变。旧解析器若把 C++ 函数括号误拆成 DSO，单列纠正记录；原始文本与旧 JSON 均保留。不改业务库、脚本和工作簿，也没有重录 perf 或重跑 workload。','',
      '| 比较量 | 输入与解释 |','|---|---|',
      '| Bound 余弦 | 四维 `[Bad Speculation, Frontend Bound, Backend Bound, Retiring]`；点积除以模长积 |',
      '| 已解析热点 Jaccard | 各任务已解析 Top-10，键为“DSO 文件名＋物理叶函数”；交集数除以并集数。符号有限时仅描述当前可解析名单 |',
      '| 十维欧氏距离 | IPC、四顶层 Bound、Core、Memory、Fetch Latency、Fetch Bandwidth、idle；只作辅助，混合单位且包含父子层级 |','',
      '十维向量每项取该批最终汇总；idle 从同批 PMU 包络的 `/proc/stat` 另算。与旧七例采用循环门控 idle 的窗口不同，不与旧十维向量直接计算距离。不使用逐秒曲线的简单均值替代 DevKit ALL，不用两种 profiler 的比例相互折算。','',
      '## 3. Topdown 特征','','除 IPC 外均为百分数。每行是一批十轮工作的最终结果，不是五次独立均值。','',
      '| 格式 | 任务 | IPC | Bad Spec. | Frontend | Backend | Retiring | Core | Memory | Fetch latency | Fetch bandwidth | idle |',
      '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for task,t in tasks.items():lines.append('| '+t['format']+' | '+task+' | '+' | '.join(f'{v:.2f}'for v in t['topdown']['vector'])+' |')
    lines+=['','## 4. 同格式任务的两两对比','','| 格式 | 配对 | Bound 余弦 | 已解析 Top-10 共同数 | Jaccard | 函数质量 |','|---|---|---:|---:|---:|---|']
    for p in pairs:
        if p['same_format']:
            common='不足十项'if p['observed_resolved_top10_common']is None else str(p['observed_resolved_top10_common'])+'/10'
            jac='—'if p['observed_resolved_top10_jaccard']is None else f"{p['observed_resolved_top10_jaccard']:.3f}"
            label='门槛内，仍有未知项'if p['function_comparison_quality']=='within_pilot_symbol_threshold'else'符号有限'
            lines.append(f"| {p['format_a']} | {p['a']} ↔ {p['b']} | {p['bound_cosine']:.6f} | {common} | {jac} | {label} |")
    lines+=['','四项顶层分类接近不等于具体函数、脚本或绝对 CPU 工作量相同。本轮不套用未经本任务集校准的高／中／低相似阈值；先结合下列函数与库、脚本组成解释。','',
      '| 格式 | 同格式 Bound 余弦范围 | 已解析 Top-10 共同数范围 |','|---|---:|---:|']
    for fmt in TASKS:
        rows=[p for p in pairs if p['same_format']and p['format_a']==fmt];cos=[p['bound_cosine']for p in rows];common=[p['observed_resolved_top10_common']for p in rows if p['observed_resolved_top10_common']is not None]
        lines.append(f"| {fmt} | {min(cos):.6f}–{max(cos):.6f} | "+(f'{min(common)}–{max(common)}/10'if common else'不足十项')+' |')
    lines+=['','### 跨格式配对范围','','以下每行包含两类格式的 3×3＝9 个配对。范围不等于类别总体分布，也不要求跨格式一定比同格式更远。','',
            '| 格式配对 | Bound 余弦范围 | 已解析 Top-10 共同数范围 |','|---|---:|---:|']
    for fmt_a,fmt_b in itertools.combinations(TASKS,2):
        rows=[p for p in pairs if {p['format_a'],p['format_b']}=={fmt_a,fmt_b}]
        cos=[p['bound_cosine']for p in rows];common=[p['observed_resolved_top10_common']for p in rows if p['observed_resolved_top10_common']is not None]
        lines.append(f"| {fmt_a} ↔ {fmt_b} | {min(cos):.6f}–{max(cos):.6f} | "+(f'{min(common)}–{max(common)}/10'if common else'不足十项')+' |')
    blas=[]
    for task in TASKS['excel']:
        value=sum(r['share_roi']for r in tasks[task]['functions']if r['function']=='blas_thread_server')
        blas.append(task+f'：{value*100:.2f}%')
    lines+=['','### Excel 的数值库线程路径','',
            '`blas_thread_server` 的 ROI 占比分别为'+ '；'.join(blas)+'。它分布于构建、重算及检查脚本，具体上下文在 JSON 中单列。镜像中的 openpyxl 兼容模块会导入 NumPy；该热点按数值库线程服务路径列出，不能直接解释成工作簿执行了矩阵算法或相同比例的公式计算。']
    lines+=['','## 5. 各格式的脚本、库与热点函数','']
    for fmt,ids in TASKS.items():
        lines+=['### '+fmt.upper(),'','| 项目 | '+' | '.join(ids)+' |','|---|'+'---|'*len(ids)]
        for title,key,name in [('主要进程／脚本','processes','script'),('主要库','libraries','library')]:
            vals=['<br>'.join(md_escape(r[name])+f" {r['share_roi']*100:.1f}%"for r in tasks[t][key][:5])for t in ids]
            lines.append('| '+title+' | '+' | '.join(vals)+' |')
        lines+=['','| 已解析函数排名 | '+' | '.join(ids)+' |','|---:|'+'---|'*len(ids)]
        for rank in range(10):
            vals=[]
            for task in ids:
                rows=tasks[task]['resolved_top10']
                if rank>=len(rows):vals.append('—');continue
                row=rows[rank];label=row['function']if len(row['function'])<=150 else row['function'][:147]+'…'
                vals.append('`'+md_escape(label)+'`<br>'+md_escape(row['library'])+f" · {row['share_roi']*100:.2f}%")
            lines.append('| '+str(rank+1)+' | '+' | '.join(vals)+' |')
        lines+=['','超长 C++ 符号在表中截短，完整名称见机器结果。']
    lines+=['## 6. 窗口、质量与后续','','| 任务 | Topdown workflow 秒 | PMU 包络秒 | 包络内非 workflow 秒 | PMU read 次数 |','|---|---:|---:|---:|---:|']
    for task,t in tasks.items():
        td=t['topdown'];lines.append(f"| {task} | {td['roi_seconds']:.2f} | {td['profiler_envelope_seconds']:.2f} | {td['outside_workflow_envelope_seconds']:.2f} | {td['pmu_reads']} |")
    lines+=['','021 每轮字体环境准备在 workflow 外；控制程序位于 CPU 9，但这些间隙仍属于 DevKit 完整包络。各任务的全部未计数事件、公式复算、未知项和 perf loss 原单位记录在 comparison.json，不把缺失样本换算成周期。',
      '本轮部分 PMU 采集期间，宿主同时进行了调试符号下载／校验，其 CPU affinity 未记录，也未从按核计数中扣除。首批结果保留这一宿主活动边界；后续独立重复应在采集前备齐符号并将宿主控制固定到目标 CPU 集合外。下载工具已补上 CPU 9 绑定，不能追溯声称本轮旧下载进程也已绑定。',
      '目前每任务每路仅一份独立 profile，因此不计算稳定性、标准差或 CV。需要研究重复波动时，再补齐独立采集，而不是把批内十轮拆成十份独立测量。',
      '', '## 证据与复算','',
      '- [机器结果与完整函数清单](comparison.json)','- [全部 66 个配对](pairs.csv)','- [来源与分析代码哈希](analysis-build.json)',
      '- 采集清单：`'+result['campaign_path']+'`',
      '- 离线补符号清单：`'+result['enrichment_path']+'`','',
      '只离线重算，不启动 workload 或 profiler：','',
      '```bash','python3 -B analysis/docops/compare.py --campaign '+result['campaign_path']+' --enrichment '+result['enrichment_path']+' --output <新的输出目录>','```','']
    (folder/'report.md').write_text('\n'.join(lines))


def main(campaign,enrichment,output):
    campaign=Path(campaign).resolve();enrichment=Path(enrichment).resolve();output=Path(output).resolve()
    c=json.loads(campaign.read_text());e=json.loads(enrichment.read_text())
    if c['status']!='passed'or e['status']!='passed'or e['campaign_sha256']!=sha(campaign):raise ValueError('unbound or incomplete campaign')
    expected={t for rows in TASKS.values()for t in rows}
    if set(c['tasks'])!=expected or set(e['tasks'])!=expected:raise ValueError('expected exactly twelve tasks')
    tasks={task:load_task(task,fmt,c['tasks'][task],e)for fmt,ids in TASKS.items()for task in ids}
    for key in tasks:
        for mode in ('perf','topdown'):
            row=c['tasks'][key][mode]
            if row['status']!='passed'or sha(ROOT/row['record'])!=row['record_sha256']:raise ValueError('capture record changed')
    output.mkdir(parents=True,exist_ok=False)
    result=dict(schema='docops-first-batch-comparison-v1',status='complete_preliminary',
                image_id=c['image_id'],campaign_path=str(campaign.relative_to(ROOT)),campaign_sha256=sha(campaign),
                enrichment_path=str(enrichment.relative_to(ROOT)),enrichment_sha256=sha(enrichment),
                captures_per_mode_per_task=1,loops_per_capture=10,formal_similarity_eligible=False,
                vector_order=VECTOR,bound_order=BOUNDS,tasks=tasks,
                pairs=[pair(a,b)for a,b in itertools.combinations(tasks.values(),2)])
    midr=Path('/sys/devices/system/cpu/cpu0/regs/identification/midr_el1')
    result['hardware_closeout']={'kernel':platform.release(),'machine':platform.machine(),
                                'cpu0_midr':midr.read_text().strip()if midr.exists()else'unknown',
                                'scope':'Host facts read at offline analysis closeout; image identity is verified per capture'}
    result['host_auxiliary_overlap']={'symbol_download_or_verification_during_some_captures':True,
        'historical_fetch_process_affinity':'not_recorded', 'background_pmu_events_subtracted':False,
        'followup':'Prepare symbols before independent repeats and pin auxiliary work outside target CPUs'}
    write(output/'comparison.json',result)
    with (output/'pairs.csv').open('w',newline='')as stream:
        keys=('a','b','format_a','format_b','same_format','bound_cosine','raw_euclid_auxiliary',
              'observed_resolved_top10_common','observed_resolved_top10_jaccard','function_comparison_quality')
        writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader();writer.writerows({k:r[k]for k in keys}for r in result['pairs'])
    report(result,output)
    build={'schema':'docops-comparison-build-v1','campaign_sha256':sha(campaign),'enrichment_sha256':sha(enrichment),
           'code_sha256':{str(p.relative_to(ROOT)):sha(p)for p in HERE.glob('*.py')},
           'output_sha256':{p.name:sha(p)for p in output.iterdir()if p.is_file()}}
    write(output/'analysis-build.json',build)
    print(output,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('campaign','enrichment','output'):parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args();main(args.campaign,args.enrichment,args.output)
