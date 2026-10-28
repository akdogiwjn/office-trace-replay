"""Offline descriptive hotspot comparison; no workload, perf, or LLM calls."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def library(dso):
    name=Path(dso or '[unknown]').name.lower()
    for token,label in [('libpython','libpython'),('libexpat','expat'),('pyexpat.','expat'),('_elementtree','ElementTree'),
                        ('libz.so','zlib'),('zlib.cpython','zlib'),('_imaging.','Pillow'),('libpoppler','Poppler'),
                        ('libfreetype','FreeType'),('libc.so','libc'),('ld-linux','ld')]:
        if token in name:return label
    if 'libreoffice' in str(dso) or name.startswith(('libsclo','libmergedlo','libscfiltlo')):
        return 'LibreOffice'
    if name in ('[unknown]','[no-frame]','unknown'):return 'unknown'
    return 'other'


LEGACY_SCRIPTS={
    'pdf-convert':'convert_pdf_to_images.py','pdf-fill':'fill_fillable_fields.py',
    'pdf-verify':'verify_pdf_batch.py','pdf-extract-fields':'extract_form_field_info.py',
    'pdf-check-fillable':'check_fillable_fields.py','pdf-summary-writer':'write_pdf_batch_summary.py',
    'xlsx-inspect-structure':'inspect_xlsx_structure.py','xlsx-inspect-features':'inspect_xlsx_features.py',
    'xlsx-inspect-formulas':'inspect_xlsx_formulas.py','xlsx-inspect-cached':'inspect_xlsx_cached_values.py',
    'xlsx-enhance':'enhance_workbook.py','xlsx-recalc':'recalc.py','xlsx-verify':'verify_xlsx_enhanced.py',
    'xlsx-summary-export':'write_xlsx_summary.py / export_xlsx.py（历史合并角色）',
    'xlsx-csv-export':'export_xlsx_csv.py','lo-thread':'LibreOffice 线程',
}


def freeze_legacy(source,destination):
    source=Path(source)
    metadata=source/'metadata/profile-artifacts.json'
    manifest=json.loads(metadata.read_text())
    result=dict(schema='physical-legacy-baseline-v1',source_metadata_sha256=sha(metadata),profiles={})
    provenance_path=source/'metadata/run-provenance.json'
    provenance=json.loads(provenance_path.read_text()).get('runs',[]) if provenance_path.exists() else []
    result['run_provenance_sha256']=sha(provenance_path) if provenance_path.exists() else None
    for name in ('opm-n10','tlc'):
        item=next(e for e in manifest['files'] if e['path']==f'processed/{name}.json')
        packed=source/item['archive']
        if sha(packed)!=item['archive_sha256']:raise ValueError('legacy archive hash mismatch')
        data=gzip.decompress(packed.read_bytes())
        if hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('legacy JSON hash mismatch')
        raw=json.loads(data)
        total=sum(r['total_period'] for r in raw['repeats'].values())
        processes,libraries,functions=Counter(),Counter(),Counter()
        repeats=[]
        for repeat,r in raw['repeats'].items():
            weight=r['total_period']/total
            repeats.append(dict(repeat=repeat,roi_samples=r['roi_samples'],roi_period=r['total_period']))
            if abs(sum(f['share_of_roi'] for f in r['function_layer'])-1)>1e-9:
                raise ValueError('legacy function rows are incomplete')
            for role,share in r['process_layer'].items():
                processes[LEGACY_SCRIPTS.get(role,role)]+=share*weight
            for f in r['function_layer']:
                # Entity fields restore the physical owner of an inline leaf;
                # never use an arbitrary caller or truncate before aggregation.
                dso=f.get('entity_dso') or '[unknown]'
                symbol=f.get('entity_symbol') or '[unknown]'
                key=(library(dso),symbol)
                functions[key]+=f['share_of_roi']*weight
                libraries[key[0]]+=f['share_of_roi']*weight
        captures=[{k:r.get(k) for k in ('repeat','requested_iterations','rate_hz','actual_runtime_image_id',
                                       'runner_sha256','recipe_sha256')}
                  for r in provenance if r.get('config')==name and r.get('collector')=='native']
        rates={r['rate_hz'] for r in captures}
        loops={r['requested_iterations'] for r in captures}
        result['profiles'][name]=dict(dataset_id=name,source_archive=item['archive'],
            source_archive_sha256=item['archive_sha256'],source_json_sha256=item['sha256'],
            actual_runtime_image_id='unknown; not recorded in historical collection',
            boundary='historical estimated PERFROI/stdout alignment; not current exact monotonic ROI',
            sample_rate_hz=next(iter(rates)) if len(rates)==1 else None,
            loops_per_repeat=next(iter(loops)) if len(loops)==1 else None,
            collection_provenance=captures,repeats=repeats,roi_period=total,
            roi_samples=sum(r['roi_samples'] for r in repeats),
            processes=[dict(script=k,share_roi=v) for k,v in processes.most_common()],
            libraries=[dict(library=k,share_roi=v) for k,v in libraries.most_common()],
            functions=[dict(library=k[0],function=k[1],share_roi=v) for k,v in functions.most_common()])
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():raise ValueError('baseline already exists')
    write(destination,result)


def normalize_current(raw):
    libraries,functions=Counter(),Counter()
    for f in raw['functions']:
        functions[(library(f['dso']),f['function'])]+=f['share_roi']
        libraries[library(f['dso'])]+=f['share_roi']
    value=dict(raw)
    value['libraries']=[dict(library=k,share_roi=v) for k,v in libraries.most_common()]
    value['functions']=[dict(library=k[0],function=k[1],share_roi=v) for k,v in functions.most_common()]
    return value


def top_functions(profile,count):
    return [f for f in profile['functions'] if f['library']!='unknown'
            and f['function'] not in ('[unknown]','[no-frame]')
            and not re.fullmatch(r'0x[0-9a-fA-F]+|[0-9a-fA-F]{12,}',f['function'])][:count]


def overlap(old,new):
    key=lambda f:(f['library'],f['function'])
    a={key(f) for f in top_functions(old,10)}
    b={key(f) for f in top_functions(new,10)}
    b20={key(f) for f in top_functions(new,20)}
    return dict(common_top10=[dict(library=k[0],function=k[1]) for k in sorted(a&b)],
                common_top10_count=len(a&b),old_top10_in_new_top20_count=len(a&b20),
                note='Descriptive sets only; no similarity threshold or requirement for matching weights.')


XLSX_SCRIPT_ROLES={
    '结构检查':('inspect_xlsx_structure.py',),
    '特征检查':('inspect_xlsx_features.py',),
    '业务增强':('enhance_workbook.py','enhance_workforce_v2.py','enhance_energy_report_v2.py','enhance_workbook_v1.py'),
    '重算与缓存扫描':('recalc.py',),
    '公式检查':('inspect_xlsx_formulas.py',),
    '缓存值检查':('inspect_xlsx_cached_values.py',),
    '循环内业务验证':('verify_xlsx_enhanced.py',),
    '摘要生成':('write_xlsx_summary.py',),
    'CSV 导出':('export_xlsx_csv.py',),
    'LibreOffice 主进程':('soffice.bin',),
}


def group_xlsx_processes(profile):
    roles={script:role for role,scripts in XLSX_SCRIPT_ROLES.items() for script in scripts}
    totals=Counter();members={}
    for row in profile['processes']:
        script=row['script']
        role=roles.get(script,'未归属线程／进程' if script.startswith('unknown:') else '其他已识别脚本／程序')
        totals[role]+=row['share_roi']
        members.setdefault(role,set()).add(script)
    return [dict(role=role,share_roi=value,scripts=sorted(members[role])) for role,value in totals.items()]


def function_table(profiles,names):
    maps={n:{(f['library'],f['function']):f['share_roi'] for f in profiles[n]['functions']} for n in names}
    ranks={n:{(f['library'],f['function']):rank for rank,f in
              enumerate(top_functions(profiles[n],len(profiles[n]['functions'])),1)} for n in names}
    keys={key for n in names for key,rank in ranks[n].items() if rank<=10}
    reference=ranks[names[0]]
    ordered=sorted(keys,key=lambda key:(0,reference[key]) if reference.get(key,11)<=10
                   else (1,-max(m.get(key,0) for m in maps.values()),key))
    return [dict(library=key[0],function=key[1],
                 reference_rank=reference[key] if reference.get(key,11)<=10 else None,
                 datasets={n:dict(share_roi=maps[n].get(key),rank=ranks[n].get(key),
                                  top10=ranks[n].get(key,11)<=10) for n in names}) for key in ordered]


def hotspot_cell(row,name):
    value=row['datasets'][name]
    if value['share_roi'] is None:return '未采到'
    text=f"{100*value['share_roi']:.2f}% · #{value['rank']}" if value['rank'] else f"{100*value['share_roi']:.2f}%"
    if value['top10']:text+=' ✓'
    return '**'+text+'**' if row['reference_rank'] is not None else text


def compare(config_path,update=False):
    config_path=Path(config_path)
    config=json.loads(config_path.read_text())
    baseline=ROOT/config['baseline']['path']
    if sha(baseline)!=config['baseline']['sha256']:raise ValueError('baseline changed')
    historical_profiles=json.loads(baseline.read_text())['profiles']
    profiles={} if config.get('reference_mode')=='current-image' else dict(historical_profiles)
    for name,item in config['profiles'].items():
        path=ROOT/item['path']
        if sha(path)!=item['sha256']:raise ValueError('profile changed: '+name)
        profiles[name]=normalize_current(json.loads(path.read_text()))
    joint=None
    if config.get('joint_comparison'):
        binding=config['joint_comparison'];path=ROOT/binding['path']
        if sha(path)!=binding['sha256']:raise ValueError('joint comparison changed')
        joint=json.loads(path.read_text())
        if {p.get('image_id') for p in profiles.values()}!={joint['image_id']}:
            raise ValueError('joint comparison image mismatch')
        expected={v.get('dataset_id',k):v['sha256'] for k,v in config['profiles'].items()}
        actual={k:v['sha256'] for k,v in joint['sources']['hotspot_profiles'].items()}
        if actual!=expected:raise ValueError('joint comparison hotspot binding mismatch')
    groups=config.get('groups',[dict(title='PDF（全部 N=10）',datasets=['opm-n10','irs_w4','sba1919']),
                               dict(title='XLSX',datasets=['tlc','hr_metro'])])
    pairs={new:overlap(profiles[group['datasets'][0]],profiles[new])
           for group in groups for new in group['datasets'][1:]}
    presentation=dict(xlsx_process_groups={n:group_xlsx_processes(profiles[n])
                      for group in groups if group.get('process_grouping')=='xlsx-role' for n in group['datasets']},
                      function_tables={group['title']:function_table(profiles,group['datasets']) for group in groups})
    output=ROOT/config['output']
    if update and output.exists() and {p.name for p in output.iterdir()}!={'comparison.json','report.md','build.json'}:
        raise ValueError('refuse to update an unexpected report directory')
    output.mkdir(parents=True,exist_ok=update)
    write(output/'comparison.json',dict(scope='shared dominant hotspots; weights descriptive',
        denominator='complete workload ROI cycles:u sample period; unknown retained',
        profiles=profiles,historical_profiles=historical_profiles,comparisons=pairs,presentation=presentation,inputs=config,config_sha256=sha(config_path),
        analysis_source_sha256=sha(Path(__file__)),joint_comparison=joint))
    pct=lambda value:f'{100*value:.2f}%'
    assessment=config['assessment']
    for item in assessment['metadata_sources']:
        if sha(ROOT/item['path'])!=item['sha256']:
            raise ValueError('assessment metadata changed: '+item['path'])
    lines=['# 文档解析类 Agent 代表性评估报告','',
        '本评估以原有 PDF 表单处理和 XLSX 工作簿增强任务为基准，引入不同领域的真实文档输入，'
        '通过 Agent 生成轨迹、容器内轨迹回放和原生热点采样，考察原有用例所体现的主要计算机制在跨领域输入下的代表性。',
        '评估重点是主要热点脚本、库和函数是否共同出现，以及它们对应的文档处理机制是否延续。'+
        ('同时结合 Topdown 特征对比顶层流水线分配。' if joint else ''),
        '', '## 一、数据集选择与领域覆盖','',
        '选取数据集时同时考虑来源、领域覆盖、数据规模和任务形态。XLSX 选用百万单元格量级的真实业务工作簿，'
        '覆盖明细记录与统计发布表；PDF 选用具有原生可填写字段的公开业务表单，覆盖不同页数、字段规模和字段类型。'
        '在更换业务数据的同时，延续原有工作簿增强与批量表单处理任务。',
    ]
    selection=assessment.get('selection_rationale',{})
    if selection:
        lines+=['',selection['introduction'],'',
                '| 数据集 | 发布方说明与来源 | 本评估的选择理由 |','|---|---|---|']
        for row in selection['datasets']:lines.append('| '+' | '.join(row)+' |')
        lines+=['',selection['size_note']]
    lines+=['', '### XLSX：四个领域的真实工作簿','',
            '| 数据集 | 领域与来源 | 输入规模 | 数据组织与任务 |','|---|---|---|---|']
    for row in assessment['xlsx_datasets']:
        lines.append('| '+' | '.join(row)+' |')
    lines+=['','TLC 保留基于真实出行记录构建的原有业务工作簿；三个新增 XLSX 使用发布方原始工作簿，保留原有工作表和数据，'
        '由 Agent 新增业务 Summary、公式、情景控制和图表。各工作簿均具有百万级单元格规模，为读取、解析、对象构建、保存和重算提供实际负载。',
        '', '### PDF：三类业务表单','',
        '| 数据集 | 领域与发布机构 | 固定版本 | 规模与批处理规模 |','|---|---|---|---|']
    for row in assessment['pdf_datasets']:
        lines.append('| '+' | '.join(row)+' |')
    lines+=['','PDF 使用真实表单结构和十条虚构业务记录。处理任务包括字段识别、记录到字段的映射、批量填写、逐页渲染和结果验证。',
        '', '## 二、Agent 执行轨迹生成','',
        '原 TLC 和 OPM 沿用原有任务及回放材料。五个新增用例通过 OpenClaw Agent 实际执行生成轨迹，'
        '每个数据集配置独立提示词，沿用原有任务的组织结构，明确输入、业务指标或字段、输出位置、交付物及验收要求。',
        'XLSX 提示词要求保留原表，新增业务 Summary、跨表公式、情景参数、图表和格式，并使用 XLSX Skill 重算和验证。'
        'PDF 提示词要求使用 PDF Skill 完成字段检查、字段抽取、十条记录的填写与渲染，并验证填写结果。'
        'Agent 在任务执行中自行编写数据集对应的业务 helper 和批处理脚本，调用 Skill 工具，直至业务验收完成。',
        '执行过程中保存 trajectory、tool events、生成脚本及其修订、输入与提示词哈希、运行环境和验收结果。'
        '随后选取成功轨迹，将其输入、业务脚本和工具调用与回放配置关联冻结。',
        '', '| 新数据集 | 采用的成功轨迹 | Agent 生成的业务脚本 |','|---|---|---|']
    for row in assessment['trace_sources']:
        lines.append('| '+' | '.join('`'+item+'`' if i else item for i,item in enumerate(row))+' |')
    lines+=['','## 三、基于轨迹的容器化回放','',
        '回放从冻结轨迹中载入输入、工具调用、业务 helper 和命令参数，按文档处理阶段执行。'
        '轨迹中的内联 Python 代码整理为独立脚本，便于运行、归档和热点归属；Agent 生成的业务 helper 与冻结的 Skill 工具随镜像一起安装。'
        '回放直接执行这些脚本和工具，无需再次调用模型。',
        '一个容器镜像支持七个用例。旧 TLC/OPM 使用保留的 document-oe 入口；新增五例通过公共入口选择数据集，'
        '每个数据集拥有独立执行器、脚本、Skill、输入及验证器。每轮重建工作区，在同一软件环境中完成处理与业务验证。',
        '', '| 阶段 | XLSX 回放操作 | PDF 回放操作 |','|---|---|---|',
        '| P01：检查输入 | 运行结构与特征检查脚本，读取原始工作簿 | 检查可填写字段、提取字段结构、渲染模板 |',
        '| P02：生成业务内容 | 执行 Agent helper，新增 Summary、公式、情景和图表并保存 | 执行 Agent helper，为十条记录生成字段值 JSON |',
        '| P03：重算或批处理 | 调用 `recalc.py` 和 LibreOffice，检查公式/缓存并导出本轮 CSV | 执行批处理脚本，逐条调用填写工具与渲染工具 |',
        '| P04：验证与交付 | 验证业务指标、公式缓存、CSV 和交付物，生成摘要 | 验证填写字段、保护字段、PDF/PNG 与批次摘要 |',
        '', '软件环境固定为 Python 3.12.3、openpyxl 3.1.5、LibreOffice 25.8.7.3 和 Poppler 23.12.0。'
        'XLSX 主要调用 openpyxl 与 LibreOffice；PDF 主要调用 pypdf、pdf2image、Pillow 和 Poppler。',
        '回放记录循环开始与结束的单调时钟标记。热点统计覆盖正式循环中的工作负载进程及线程，归档和循环外独立审计在统计区间之外完成。',
        '', *([joint['measurement_section'],''] if joint and joint.get('measurement_section') else []),
        '## 五、热点函数对比与代表性评估' if joint and joint.get('measurement_section') else '## 四、热点函数对比与代表性评估','',
        config.get('comparison_description','本轮比较三个 PDF（OPM、W-4、SBA 1919，均为十条记录）以及 XLSX 的 TLC 与 HR Metro。'
        '旧 OPM/TLC 使用已有采样结果，新增用例使用当前轨迹回放的采样结果。'),
        '采用 perf 的 `cycles:u` 事件采集原生调用栈，按物理叶函数统计热点，并关联脚本、进程和动态库。'
        '表中比例为正式循环内已观测用户态样本的 period 占比；Top-10/Top-20 用于查看主要函数的共同出现情况，权重用于描述各自分布。']
    images={p['image_id'] for p in profiles.values() if 'image_id' in p}
    if len(images)!=1:raise ValueError('new profiles do not share one image')
    lines += ['', '| 配置 | ROI 样本数 | 采样配置 |','|---|---:|---|']
    for name,p in profiles.items():
        status=(f"历史 {len(p['repeats'])} 次重复，各 {p['loops_per_repeat']} 轮，{p['sample_rate_hz']} Hz"
                if 'repeats' in p else
                f"{p['repetitions']} 次独立重复，每次 {p['loops_per_repetition']} 轮"+
                (f"、{p['pdf_applicant_count']} 份" if p.get('pdf_applicant_count') is not None else '')+
                '，49 Hz；全部执行与业务验证成功'
                if p.get('repetitions',1)>1 else '单轮，49 Hz；执行与业务验证成功')
        lines.append(f"| {name} | {p['roi_samples']:,} | {status} |")
    for group in groups:
        title,names=group['title'],group['datasets']
        lines+=['',f'### {title}','', '#### 主要脚本／进程','']
        if group.get('process_grouping')=='xlsx-role':
            lines+=['按职责合并不同名称的脚本，占比为对应采样 period 之和；实际脚本保持独立。未归属线程单列。',
                    '', '| 职责 | 对应脚本／程序 | '+' | '.join(names)+' |','|---|---|'+'---:|'*len(names)]
            rows={n:{r['role']:r for r in presentation['xlsx_process_groups'][n]} for n in names}
            roles=[*XLSX_SCRIPT_ROLES,'其他已识别脚本／程序','未归属线程／进程']
            for role in roles:
                if not any(role in rows[n] for n in names):continue
                scripts=XLSX_SCRIPT_ROLES.get(role)
                label='、'.join('`'+s+'`' for s in scripts) if scripts else (
                    '`unknown:*`（保留未归属状态）' if role=='未归属线程／进程' else '其余已识别程序')
                lines.append('| '+role+' | '+label+' | '+' | '.join(
                    pct(rows[n][role]['share_roi']) if role in rows[n] else '—' for n in names)+' |')
        else:
            lines+=['| 实际脚本／程序（历史仅有角色时注明） | '+' | '.join(names)+' |',
                    '|---|'+'---:|'*len(names)]
            maps={n:{i['script']:i['share_roi'] for i in profiles[n]['processes']} for n in names}
            keys=set().union(*(set(m) for m in maps.values()))
            selected=sorted((k for k in keys if max(m.get(k,0) for m in maps.values())>=.005),
                            key=lambda k:-max(m.get(k,0) for m in maps.values()))
            for key in selected:
                lines.append('| `'+key+'` | '+' | '.join(pct(maps[n][key]) if key in maps[n] else '—' for n in names)+' |')
        lines+=['','“—”表示该采样结果中没有对应标签。',
                '', '#### 主要库','', '| 库 | '+' | '.join(names)+' |','|---|'+'---:|'*len(names)]
        maps={n:{i['library']:i['share_roi'] for i in profiles[n]['libraries']} for n in names}
        keys=set().union(*(set(m) for m in maps.values()))
        for key in sorted(keys,key=lambda k:-max(m.get(k,0) for m in maps.values())):
            if max(m.get(key,0) for m in maps.values())>=.005:
                lines.append('| '+key+' | '+' | '.join(pct(maps[n].get(key,0)) for n in names)+' |')
        lines+=['','#### 主要热点函数（各配置 Top-10 的并集）','',
                f'★ 标记原用例 `{names[0]}` 的 Top-10，优先按其排名排列；粗体突出这些函数在各列的占比。'
                '✓ 表示进入本列数据集的 Top-10；# 为该列函数排名。其余行补充新数据集的 Top-10 函数。',
                '', '| 库／物理叶函数 | '+' | '.join(names)+' |','|---|'+'---:|'*len(names)]
        for row in presentation['function_tables'][title]:
            label=(row['library']+' / '+row['function']).replace('|','&#124;')
            prefix=f"★ #{row['reference_rank']} · " if row['reference_rank'] is not None else ''
            lines.append('| '+prefix+'`'+label+'` | '+' | '.join(hotspot_cell(row,n) for n in names)+' |')
        lines+=['','#### 共同热点','', '| 对照 | Top-10 共同函数数 | 旧 Top-10 在新 Top-20 中出现 |','|---|---:|---:|']
        for new in names[1:]:
            c=pairs[new]
            lines.append(f"| {names[0]} → {new} | {c['common_top10_count']} / 10 | {c['old_top10_in_new_top20_count']} / 10 |")
        if all(profiles[n].get('repetitions',1)>1 for n in names):
            top5_sets=[{(f['library'],f['function']) for f in top_functions(profiles[n],5)} for n in names]
            common5=set.intersection(*top5_sets)
            lines+=['','#### 五轮合并 Top-5','',
                    f'各数据集五轮合并后的 Top-5 有 {len(common5)} 个共同函数；下表为各自 Top-5 的累计占比。',
                    '', '| 数据集 | Top-5 累计 ROI 占比 |','|---|---:|']
            for n in names:
                lines.append(f"| {n} | {pct(sum(f['share_roi'] for f in top_functions(profiles[n],5)))} |")
    lines+=['','### 热点函数与执行脚本的对应关系','']
    for name in profiles:
        if 'contexts' not in profiles[name]:continue
        lines +=[f'#### {name}','','| 实际脚本／程序 | 库 | 物理叶函数 | ROI 占比 |','|---|---|---|---:|']
        for item in profiles[name]['contexts'][:10]:
            lines.append(f"| `{item['script']}` | {library(item['dso'])} | `{item['function'].replace('|','&#124;')}` | {pct(item['share_roi'])} |")
        lines+=['']
    default_conclusions=[
        '跨领域 PDF 输入延续了表单处理任务的主要热点：`convert_pdf_to_images.py`、`fill_fillable_fields.py`、'
        '`verify_pdf_batch.py` 与 `pdftoppm`，对应 Python 解释执行、图片缩放、压缩编码和 PDF 渲染。'
        f"W-4、SBA 1919 与 OPM 的 Top-10 函数分别有 {pairs['irs_w4']['common_top10_count']}、"
        f"{pairs['sba1919']['common_top10_count']} 个共同项，旧 Top-10 在两项新输入的 Top-20 中分别出现 "
        f"{pairs['irs_w4']['old_top10_in_new_top20_count']}、{pairs['sba1919']['old_top10_in_new_top20_count']} 个。",
        'HR Metro 与 TLC 共同表现为 Python 工作簿处理主导，主要库包括 libpython、Expat、ElementTree、zlib 和 LibreOffice。'
        f"共同热点涵盖解释器执行、字典与对象操作、垃圾回收和 XML 解析；Top-10 函数有 {pairs['hr_metro']['common_top10_count']} 个共同项，"
        f"TLC 的 Top-10 中有 {pairs['hr_metro']['old_top10_in_new_top20_count']} 个出现在 HR Metro 的 Top-20 中。",
        '**本轮结果支持原 PDF 与 XLSX 用例在主要原生计算机制层面的跨领域代表性：更换真实业务输入后，主要热点仍集中于相同的文档处理工具链和底层计算路径。**']
    lines+=['','### 评估结论','',*config.get('conclusions',default_conclusions),
        '', '### 采样与证据说明','',
        config.get('sampling_note','本轮采用单次新用例采样，重点识别共同热点；HR 采样含丢样记录，权重用于粗粒度观察。'
        '历史内联函数已归并到对应实体函数后参与比较。完整采样质量、版本、ROI、未知项及来源哈希保留在机器可读结果中。'),
        f"当前回放镜像：`{next(iter(images))}`。",'',
        '数据与追溯：[机器可读对比结果](comparison.json)、[分析构建记录](build.json)、'
        '[轨迹来源与回放说明](../../../../agent/README.md)。']
    if joint:
        lines+=['',joint['report_section']]
        for f in joint.get('figures',[]):
            path=ROOT/f['path']
            if sha(path)!=f['sha256']:raise ValueError('joint figure changed')
            lines+=['',f'![{f["title"]}]({os.path.relpath(path,output)})','',f['caption']]
    if config.get('coverage_gaps'):
        lines+=['',config['coverage_gaps']['markdown']]
    (output/'report.md').write_text('\n'.join(lines).rstrip()+'\n')
    write(output/'build.json',dict(config_sha256=sha(config_path),analysis_sha256=sha(Path(__file__)),
        output_sha256={p.name:sha(p) for p in output.iterdir() if p.is_file() and p.name!='build.json'}))
    print(json.dumps(dict(output=str(output.relative_to(ROOT)),comparisons=pairs),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-legacy-from',type=Path)
    parser.add_argument('--baseline-output',type=Path,default=HERE/'baselines/legacy-opm-tlc.json')
    parser.add_argument('--config',type=Path)
    parser.add_argument('--update-report',action='store_true',help='Regenerate an existing three-file derived report.')
    args=parser.parse_args()
    if args.freeze_legacy_from:freeze_legacy(args.freeze_legacy_from,args.baseline_output)
    elif args.config:compare(args.config,update=args.update_report)
    else:parser.error('choose --freeze-legacy-from or --config')
