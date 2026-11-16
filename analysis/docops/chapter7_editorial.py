"""Render chapter 7 from frozen results; leave the earlier report and HTML intact."""
import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

import operation_comparison as method
import operation_equivalence_deep as equivalence
import supplement_selection as selection
import topdown_hierarchy_comparison as topdown

ROOT=method.ROOT
EVIDENCE='docs/evidence/chapter73-two-coverage-conclusions-20261116.json'
WORD_REVIEW='analysis/docops/processed/word009-coverage-review-20261113/review.json'
ORDER=[p for group in method.GROUPS.values() for p in group]
SIZES={'001':'500条记录','003':'500单元','009':'500事件','013':'1000供应商',
       '014':'10000申请','016':'500单元／2000行','021':'80页','026':'90页','029':'81页',
       '031':'100页','037':'100页','pdfwf005':'120页'}
PREVIEWS={'OPM':'PNG','TLC':'不生成页面预览',
    '031':'PNG','037':'PNG','pdfwf005':'PNG＋拼图',
    '013':'PNG＋拼图','014':'PNG','016':'PNG：首页',
    '001':'PNG','003':'PNG','009':'PNG',
    '021':'JPEG＋拼图','026':'JPEG','029':'JPEG：首页'}
SOFTWARE=[
    ['PDF：旧 OPM＋新任务',
     'pypdf（表单、页面、书签）；ReportLab（新 031／037 绘制 PDF）；Pillow（旧 OPM 图片处理）',
     'Poppler 命令；ImageMagick（新 pdfwf005）'],
    ['Excel：旧 TLC＋新任务','openpyxl（单元格、公式、样式和图表）',
     'LibreOffice；新三项还用 Poppler，013 还用 ImageMagick'],
    ['Word：新任务','python-docx（段落、表格和样式）','LibreOffice、Poppler 命令'],
    ['PPT：新任务','python-pptx（幻灯片、文本框、形状和图表）',
     'LibreOffice、Poppler 命令；021 还用 ImageMagick']]

PYTHON_LIBRARIES=[
    ('openpyxl','openpyxl','读写单元格、公式、样式和图表',
     [('TLC','document-oe/assets/xlsx/enhance_workbook.py')],
     [('013','build_public_bid_workbook.py'),('014','build_disaster_release_v1.py'),('016','build_forecast_dashboard_v1.py')]),
    ('python-docx','docx','读写 Word 段落、表格和样式',[],
     [('001','create_packet.py'),('003','build_public_packet.py'),('009','build_incident_manual_publication.py')]),
    ('python-pptx','pptx','读写幻灯片、文本框、形状和图表',[],
     [('021','build_public_shelter_briefing.py'),('026','build_climate_disclosure.py'),('029','build_release_deck.py')]),
    ('pypdf','pypdf','填写表单，读写 PDF 页面、书签和元数据',
     [('OPM','document-oe/assets/skills/pdf/scripts/fill_fillable_fields.py')],
     [('031','validate_public_packet.py'),('037','build_bus_detour_packet.py'),('pdfwf005','rebuild_closeout_binder.py')]),
    ('ReportLab','reportlab','绘制文字、表格和图形，生成 PDF',[],
     [('031','build_public_packet.py'),('037','build_bus_detour_packet.py')])]

NATIVE_LIBRARIES=[
    ('Python：`libpython3.12.so`','执行 Python 脚本和库代码',('libpython3.12.so',)),
    ('C 运行库：`libc.so`','内存分配、字符串和文件操作',('libc.so',)),
    ('zlib：`libz.so`','压缩／解压文档与图片数据',('libz.so',)),
    ('XML：`libxml2.so`','解析和修改 XML',('libxml2.so',)),
    ('lxml 扩展：`etree.*.so`','让 Python 调用 XML 处理代码',('etree.cpython-',)),
    ('UNO：`libuno_cppu.so`','传递和管理 Office 组件数据',('libuno_cppu.so',)),
    ('VCL：`libvcllo.so`','文字、图片和页面绘制',('libvcllo.so',)),
    ('OOXML：`libooxlo.so`','Office 文件导入、属性和图形处理',('libooxlo.so',)),
    ('Calc：`libsclo.so`／`libscfiltlo.so`','表格模型、公式重算和 Excel 导入',('libsclo.so','libscfiltlo.so')),
    ('Writer：`libswlo.so`／`libsw_writerfilterlo.so`','Word 导入、段落、表格和分页',('libswlo.so','libsw_writerfilterlo.so')),
    ('Impress／Draw：`libsdlo.so`','幻灯片／绘图文档的页面和对象',('libsdlo.so',)),
    ('Poppler：`libpoppler.so`','读取 PDF、生成页面预览',('libpoppler.so',)),
    ('字体：`libfreetype.so`','读取字体和生成文字字形',('libfreetype.so',)),
    ('Pillow：`_imaging.*.so`','图片读取、缩放和像素处理',('_imaging.cpython-',)),
    ('PNG：`libpng16.so`','PNG 图片编解码',('libpng16.so',)),
    ('JPEG：`libjpeg.so`','JPEG 图片编解码',('libjpeg.so',)),
    ('ImageMagick：`libMagickCore*.so`','图片缩放、滤波和拼图',('libMagickCore-',))]


def task_groups(tasks,scale):
    """Name whole format groups compactly, retaining IDs for partial groups."""
    result=[]
    for label in ('PDF','Excel','Word','PPT'):
        members=[p for p in ORDER if scale['cases'][p]['format']==label]
        found=[p for p in members if p in tasks]
        if found:result.append(label if found==members else label+' '+ '／'.join(found))
    return '；'.join(result)


def library_inventory(scale):
    """Two evidence levels: invoked scripts' imports and observed native leaves."""
    python=[]
    for name,module,purpose,old,new in PYTHON_LIBRARIES:
        witnesses=[]
        for task,path in old+new:
            if task in ('OPM','TLC'):
                source=ROOT/path
                require(source.name in {r['script'] for r in scale['references'][task]['processes']},
                        'Old Python witness was not observed executing: '+path)
                lock_path=ROOT/'document-oe/lock.json'
                lock=json.loads(lock_path.read_text())
                entry=lock['workload_files'][str(source.relative_to(ROOT/'document-oe/assets'))]
                require(method.sha(source)==entry['sha256'],'Old frozen Python script changed: '+path)
                binding=dict(kind='captured_script',lock='document-oe/lock.json',lock_sha256=method.sha(lock_path))
            else:
                recipe_path=ROOT/f'docops/payload/tasks/{task}/recipe.json'
                recipe=json.loads(recipe_path.read_text())
                selected=[f for f in recipe['files'] if f.get('kind')=='script' and Path(f['payload']).name==path]
                require(len(selected)==1,'Ambiguous Python library witness: '+task+'/'+path)
                source=ROOT/'docops/payload'/selected[0]['payload']
                require(method.sha(source)==selected[0]['sha256'],'Frozen Python script changed: '+str(source))
                steps=[s['id'] for s in recipe['steps'] if s['phase']=='workflow'
                       and selected[0]['destination'] in ' '.join(s['argv'])]
                require(steps,'Python witness not in workflow command: '+str(source))
                require(source.name in {r['script'] for r in scale['cases'][task]['processes']},
                        'New Python witness was not observed executing: '+str(source))
                binding=dict(kind='frozen_workflow_script',recipe=str(recipe_path.relative_to(ROOT)),
                             recipe_sha256=method.sha(recipe_path),steps=steps)
            imports=set()
            for node in ast.walk(ast.parse(source.read_text())):
                if isinstance(node,ast.Import):imports.update(a.name.split('.')[0] for a in node.names)
                elif isinstance(node,ast.ImportFrom) and node.module:imports.add(node.module.split('.')[0])
            require(module in imports,'Python library import missing: '+str(source))
            witnesses.append(dict(task=task,path=str(source.relative_to(ROOT)),sha256=method.sha(source),**binding))
        python.append(dict(library=name,module=module,purpose=purpose,
                           old_tasks=[p for p,_ in old],new_tasks=[p for p,_ in new],witnesses=witnesses))
    owners={**scale['references'],**{p:scale['cases'][p] for p in ORDER}}
    native=[]
    for name,purpose,prefixes in NATIVE_LIBRARIES:
        matches={p:sorted({f['library'] for f in c['functions']
                          if any(f['library'].startswith(prefix) for prefix in prefixes)}) for p,c in owners.items()}
        require(any(matches.values()),'Native library not observed: '+name)
        native.append(dict(library=name,purpose=purpose,observed_dsos=matches,
                           old_tasks=[p for p in ('OPM','TLC') if matches[p]],
                           new_tasks=[p for p in ORDER if matches[p]]))
    return dict(scope='12 original tasks; OPM and TLC references',
                python_basis='Imports in frozen workflow scripts; old witnesses also observed as captured processes',
                native_basis='Native leaf DSO presence in retained perf profiles; not installation or inclusive library time',
                python=python,native=native)


def rank_native_libraries(profile):
    """Rank concrete shared objects; keep unresolved symbols in their owning DSO."""
    total=profile['roi_period']
    require(total>0,'Empty native profile')
    require(sum(r['period'] for r in profile['libraries'])==total,'Native DSO periods do not conserve ROI')
    counts=Counter()
    for row in profile['libraries']:
        require(row['period']>=0,'Negative native DSO period')
        name=Path(row['dso']).name
        if re.search(r'\.so(?:\.|$)',name):counts[name]+=row['period']
    return [dict(library=name,period=period,share_roi=period/total)
            for name,period in sorted(counts.items(),key=lambda x:(-x[1],x[0])) if period>0]


def native_library_hotspots(scale):
    """Reaggregate the complete original profiles, not resolved-function subsets."""
    def read(path):
        require(path in scale['input_sha256'],'Native profile not bound to frozen analysis: '+path)
        require(method.sha(ROOT/path)==scale['input_sha256'][path],'Native profile changed: '+path)
        return json.loads((ROOT/path).read_text())
    config=read(method.BASE_CONFIG)
    sources={name:config['profiles'][key]['path'] for name,key in [('OPM','opm-n10'),('TLC','tlc')]}
    sources.update({p:scale['cases'][p]['source']['profile'] for p in ORDER})
    records={}
    for task,path in sources.items():
        raw=read(path);case=scale['references'][task] if task in ('OPM','TLC') else scale['cases'][task]
        require(raw['roi_period']==case['roi_period'],'Native ROI differs: '+task)
        rows=rank_native_libraries(raw)
        zlib=Counter()
        for row in raw['contexts']:
            if Path(row['dso']).name.startswith('libz.so'):zlib[row['script']]+=row['period']
        require(sum(zlib.values())==sum(r['period'] for r in rows if r['library'].startswith('libz.so')),
                'zlib caller periods do not conserve library weight: '+task)
        records[task]=dict(profile=path,sha256=scale['input_sha256'][path],roi_period=raw['roi_period'],
            libraries=rows,unranked_period=raw['roi_period']-sum(r['period'] for r in rows),
            processes=case['processes'],preview=PREVIEWS[task],
            zlib=dict(period=sum(zlib.values()),share_roi=sum(zlib.values())/raw['roi_period'],
                by_script=[dict(script=k,period=v,share_roi=v/raw['roi_period']) for k,v in zlib.most_common()]))
    old={r['library'] for p in ('OPM','TLC') for r in records[p]['libraries']}
    for task,record in records.items():
        for row in record['libraries']:row['observed_in_old']=row['library'] in old
        record['top3']=record['libraries'][:3]
    return dict(identity='exact DSO basename, including version; display omits trailing ABI version',
        denominator='complete original-task workflow ROI cycles:u period; unresolved symbols retain their DSO weight',
        ranking='Top 3 individual shared libraries by period; executables/unknown DSO excluded from ranking, retained in denominator',
        old_marker='observed in full OPM or TLC native library list; does not assert identical functions',tasks=records)


def native_library_cell(row,zlib_purpose=None):
    name=row['library'];purpose=None
    short_purposes={
        'libpython3.12.so':'Python 执行','libc.so':'内存／字符串等',
        'libz.so':'压缩／解压','libpng16.so':'PNG 编解码',
        'libMagickCore-':'图片缩放／滤波／拼图','libsclo.so':'表格模型／重算',
        'libvcllo.so':'文字／图片绘制','libpoppler.so':'PDF 页面渲染',
        'libooxlo.so':'Office 结构／图形'}
    for prefix,label in short_purposes.items():
        if name.startswith(prefix):purpose=label;break
    if purpose is None:
        purpose=next((purpose for _,purpose,prefixes in NATIVE_LIBRARIES
                      if any(name.startswith(prefix) for prefix in prefixes)),'原生代码执行')
    if name.startswith('libz.so') and zlib_purpose:purpose=zlib_purpose
    shown=re.sub(r'(\.so)(?:\.\d+)+$',r'\1',name)
    for prefix,label in [('pyexpat.cpython-','pyexpat.*.so'),('_elementtree.cpython-','_elementtree.*.so'),
                         ('_imaging.cpython-','_imaging.*.so')]:
        if name.startswith(prefix):shown=label;break
    if name.startswith('pyexpat.cpython-'):purpose='XML 解析'
    elif name.startswith('_elementtree.cpython-'):purpose='XML 节点处理'
    return '`'+shown+'`'+(' ★' if row['observed_in_old'] else '')+'（'+purpose+'）'+method.pct(row['share_roi'])


def native_hotspot_table(scale,data):
    rows=[]
    for p in ['OPM','TLC']+ORDER:
        record=data['tasks'][p]
        label={'OPM':'旧 PDF／OPM','TLC':'旧 Excel／TLC'}.get(p)
        if label is None:label='[新 '+scale['cases'][p]['format']+' '+p+'](../docops/payload/tasks/'+p+'/recipe.json)'
        z=record['zlib']
        png_period=sum(r['period'] for r in z['by_script']
                       if r['script']=='pdftoppm' or (p=='OPM' and r['script']=='convert_pdf_to_images.py'))
        purpose='PNG 压缩为主' if record['preview'].startswith('PNG') and png_period>z['period']/2 else None
        rows.append([label,record['preview']]+[native_library_cell(r,purpose) for r in record['top3']])
    return method.table(['用例','页面预览','第 1 大原生库','第 2 大原生库','第 3 大原生库'],rows)


def software_section(scale):
    data=library_inventory(scale);t=method.table
    def rows(kind):
        return [[r['library'],r['purpose'],'✓' if 'OPM' in r['old_tasks'] else '—',
                 '✓' if 'TLC' in r['old_tasks'] else '—',task_groups(r['new_tasks'],scale) or '—'] for r in data[kind]]
    return '\n'.join([
        '### 7.2 软件与库：哪些旧用例已有，哪些是新增', '',
        '本节先比较使用的软件和库，7.3 再比较库内实际执行的函数及操作。', '',
        '任务脚本可以在 Python 中调用文档库，也可以启动 LibreOffice 等外部程序。'
        '它们处理的文档不同，但可能调用相同的底层库，因此会出现共同的 CPU 热点。', '',
        '#### 7.2.1 上层：由什么工具处理文档', '',
        '**表 7-1：各场景的主要处理工具。**', '',
        t(['场景','Python 库（主要工作）','另外启动的程序'],SOFTWARE), '',
        'Python 库在 Python 进程内执行，外部程序由脚本另外启动。'
        'LibreOffice 负责重算、排版和格式转换；Poppler 提供 `pdftoppm`（页面转图片）、`pdftotext`（提取文字）等命令；'
        'ImageMagick 提供 `montage` 等图片缩放与拼图命令。', '',
        '**上层变化：** 新 Excel 继续使用 openpyxl，新 PDF 继续使用 pypdf 并增加 ReportLab；'
        'Word、PPT 分别增加 python-docx、python-pptx。', '',
        '#### 7.2.2 底层：使用了哪些计算库', '',
        '底层库提供压缩／解压、XML 解析、字体和绘图等具体功能，由上层工具调用。'
        '其中 `.so` 文件是编译好的共享库，供程序加载和调用。'
        '例如，Python 文档库和 LibreOffice 都可能把实际压缩工作交给 zlib：', '',
        '```text',
        'Python 文档库 → Python 的 ZIP 处理代码 → zlib',
        'LibreOffice  → 自己的 ZIP 处理代码    → zlib',
        '```', '',
        '**表 7-1A：主要底层库的新旧对照。** 根据 perf 记录核对。'
        '✓ 表示该库中出现了执行样本，— 表示未观测到；'
        '新用例列中仅写格式名表示该类三项均观测到，附编号表示部分任务。', '',
        t(['底层库','主要用途','旧 OPM','旧 TLC','新用例'],rows('native')), '',
        '**底层变化：** Python、zlib、Poppler 和字体库在旧例中已有；'
        '新 Excel／Word／PPT 继续使用 TLC 已有的 XML、UNO 和 VCL 组件。'
        '新增路径包括 Writer、Impress／Draw、lxml 扩展，以及 libpng、libjpeg 和 ImageMagick。'
        '表中 Calc 库负责 Excel 表格与重算，Writer 库负责 Word 导入与布局，'
        'Impress／Draw 共用库负责幻灯片和绘图文档的页面对象；它们属于 LibreOffice。', '',
        '表中的重合表示使用了相同的库；是否执行相同函数或同类操作，见 7.3。'
        'Python 文档库的计算会落在解释器、XML 或压缩等底层库中，因此下表的 Python 权重不是某一个 Python 文档库的单独占比。', '',
        '#### 7.2.3 主要热点落在哪些库', ''])


def require(ok,message):
    if not ok:raise ValueError(message)


def normalize_sections(text):
    """Legacy helpers can still request curves before the final conclusion."""
    a,b=text.index('### 7.5 '),text.index('### 7.6 ')
    end=text.index(method.END) if method.END in text else len(text)
    if '逐点曲线' in text[a:text.index('\n',a)]:return text
    return text[:a]+text[b:end].replace('### 7.6 ','### 7.5 ',1)+text[a:b].replace('### 7.5 ','### 7.6 ',1)+text[end:]


def pct(value):
    if 99.99<value<100:return '>99.99%'
    return '<0.01%' if 0<value<.01 else f'{value:.2f}%'


def tool_short(tool):
    return {'LibreOffice·其他组件':'Office','LibreOffice·VCL':'位图','libfreetype':'字体'}.get(tool,tool)


def equivalent_cell(c):
    names=[r['operation'].replace(' 编解码','') for r in c['same_operations'] if r['share_pct']>=.05]
    label='、'.join(names[:3])+('等' if len(names)>3 else '')
    return pct(c['shares_pct']['same_operation'])+('：'+label if label else '')


def remaining_cell(c):
    shown=[r for r in c['separate_operations'] if r['share_pct']>=.05]
    other=c['shares_pct']['other_resolved']+sum(r['share_pct'] for r in c['separate_operations'] if r['share_pct']<.05)
    parts=[r['operation']+' '+pct(r['share_pct']) for r in shown]
    tools='／'.join(tool_short(r['tool']) for r in c['other_tools'][:2])
    parts.append(tools+'等 '+pct(other))
    return '；'.join(parts)


def operation_pct(c,name):
    return sum(g['share_pct'] for g in c['separate_operations'] if g['operation']==name)


def conclusion(eq):
    return '\n'.join([
        '### 7.5 结论：建议增加哪些用例', '',
        '**保留旧 OPM／TLC 作为核心，再按研究目标补充。** '
        '它们覆盖了本批任务的大部分共同操作；具体函数实现仍有差异。', '',
        '| 研究目标 | 建议补充的原始用例 |',
        '|---|---|',
        '| 覆盖更多具体函数 | Excel 013＋PPT 021 |',
        '| 补充不同操作 | 先选 PPT 021；研究 Word 导入与长文档排版时，再加 Word 009 |',
        '| 专门研究幻灯片表格样式 | 再选 PPT 029 |', '',
        '013 主要补 PNG 预览与图片处理实现，021 补 JPEG、图片处理和幻灯片相关路径，'
        '009 补 Word 导入、表格、分页与目录页码确认。组合效果见 7.3.4。', ''])


def gap_rows(eq):
    """Keep residual weights; describe their purposes without declaring new operations."""
    purposes={
        '031':'Shell 初始化等',
        '037':'Shell 初始化、字符编码等',
        'pdfwf005':'ImageMagick 图像参数／链表管理等',
        '013':'图像链表、进程与 Shell 支撑等',
        '014':'绘图指令、图形边框、加密等',
        '016':'图形边框／坐标、区域配置、加密等',
        '001':'加密、URI 字符处理、连字符处理等',
        '003':'加密、文档状态、图形属性等',
        '009':'绘图指令、PDF 字形登记、加密／证书等',
        '021':'幻灯片对象、图形路径、文字方向与加密等',
        '026':'幻灯片对象、图形属性、文字方向与加密等',
        '029':'幻灯片对象／属性、文字方向与加密等'}
    rows=[]
    for p in ORDER:
        c=eq['cases'][p]
        parts=[g['operation']+' '+pct(g['share_pct']) for g in c['separate_operations']]
        parts.append(('其余 ' if parts else '')+purposes[p]+' '+pct(c['shares_pct']['other_resolved']))
        rows.append([c['format']+' '+p,'；'.join(parts),pct(c['shares_pct']['unresolved'])])
    return rows


def candidate_support(scale,c,selected):
    keys={method.key(f) for p in selected for f in scale['cases'][p]['functions']}
    gain=sum(f['period'] for f in c['functions'] if f['bucket'] in ('separate_operation','other_resolved')
             and method.key(f) in keys)
    return c['supported_share_pct']+100*gain/c['roi_period']


def word_comparison(scale,eq):
    result=[]
    for p in ('001','003','009'):
        c=scale['cases'][eq['cases'][p]['task']]
        result.append(dict(task=p,
            compression_png_pct=100*sum(x['share_roi'] for x in c['libraries'] if x['library'] in ('zlib','PNG')),
            writer_pct=100*sum(f['period'] for f in c['functions']
                if f['library'] in ('libswlo.so','libsw_writerfilterlo.so'))/c['roi_period'],
            supported_pct=eq['cases'][p]['supported_share_pct']))
    return result


def word_review():
    path=ROOT/WORD_REVIEW;data=json.loads(path.read_text())
    index=json.loads(path.with_name('sha256-index.json').read_text())
    for name,h in index.items():require(method.sha(path.with_name(name))==h,'Word review changed: '+name)
    for name,h in data['inputs'].items():require(method.sha(ROOT/name)==h,'Word review input changed: '+name)
    return data


def scale_coverage_comparison(scale,eq):
    result=[]
    for p in ORDER:
        large=scale['groups'][p][1]
        old=scale['cases'][p]['presence']['OPM+TLC']
        new=scale['cases'][large]['presence']['OPM+TLC']
        require(eq['cases'][p]['task']==large,'Operation accounting uses a different large variant: '+p)
        require(abs(100*new['observed_share_roi']-eq['cases'][p]['shares_pct']['exact'])<1e-9,
                'Large function coverage differs from operation accounting: '+p)
        for presence in (old,new):
            require(abs(sum(presence[k] for k in ('observed_share_roi','not_observed_share_roi','unresolved_share_roi'))-1)<1e-9,
                    'Function coverage does not retain the full denominator: '+p)
        original=100*old['observed_share_roi'];expanded=100*new['observed_share_roi']
        result.append(dict(parent=p,format=scale['cases'][p]['format'],original_task=p,large_task=large,
            original_roi_period=scale['cases'][p]['roi_period'],large_roi_period=scale['cases'][large]['roi_period'],
            original_coverage_pct=original,large_coverage_pct=expanded,change_pp=expanded-original,
            original_unresolved_pct=100*old['unresolved_share_roi'],large_unresolved_pct=100*new['unresolved_share_roi']))
    return result


def section73(scale,eq):
    rows=eq['cases'];t=method.table;word=word_review();ppt=eq['ppt021']
    high=sum(c['supported_share_pct']>=85 for c in rows.values())
    nonword=[p for p in scale['groups'] if scale['cases'][p]['format']!='Word']
    compared=scale_coverage_comparison(scale,eq)
    original=[r['original_coverage_pct'] for r in compared]
    increased=sum(r['change_pp']>0 for r in compared)
    return '\n'.join([
        '### 7.3 旧用例覆盖了哪些函数与操作', '',
        '先看十二项原始任务的函数覆盖，再比较扩大规模后的变化，最后检查剩余函数是否属于旧例已有的操作。'
        '以 OPM＋TLC 为旧参考，百分比均按热点采样权重计算。', '',
        '#### 7.3.1 从原始规模出发，再比较扩大规模后的变化', '',
        '新任务调用的函数，在旧 OPM 或 TLC 记录中出现过，就计为“函数已覆盖”；比较时同时核对所属库。'
        '“未匹配”是已识别但旧记录中没有的函数，“未解析”是尚不能确定函数名的部分。', '',
        '**原始规模的发现：** 使用 Agent 任务原有的冻结输入回放，函数覆盖为 '
        +pct(min(original))+'–'+pct(max(original))+'。例如 Excel 016 为 '
        +pct(100*scale['cases']['016']['presence']['OPM+TLC']['observed_share_roi'])+'，PPT 029 为 '
        +pct(100*scale['cases']['029']['presence']['OPM+TLC']['observed_share_roi'])+'，仍有较多函数未在旧例中匹配。', '',
        '**为什么扩大规模：** 小输入中，解释器启动、脚本解析和检查的权重可能更显眼。'
        '为观察输入规模变化后的结果，将十二项任务各扩为两档，共 24 个规模变体。'
        '下表保留原始规模作为起点，与大档对照；小档结果见本节末的完整记录。', '',
        '**表 7-4：原始规模与大规模的函数覆盖对比。** 变化为“大规模－原始规模”，单位为百分点，按未舍入原值计算。', '',
        t(['用例','原始规模函数覆盖','大规模函数覆盖','变化（百分点）'],[
            [r['format']+' '+r['parent'],pct(r['original_coverage_pct']),pct(r['large_coverage_pct']),
             f"{r['change_pp']:+.2f}"] for r in compared]), '',
        '**规模复测的结果：** '+str(increased)+'/12 项大档高于原始任务。Excel 016 从 56.25% 提高到 80.03%，'
        'PPT 029 则从 55.51% 降至 46.29%。在规模复测中，多数任务的匹配权重提高，变化方向并不完全相同。'
        '剩余差额继续按实际操作核对。', '',
        '#### 7.3.2 把同类操作也算上，覆盖了多少', '',
        '以下使用上表的大规模结果，具体规模列在表 7-4A 中。', '',
        '旧例用 Pillow、新例用 ImageMagick 缩放图片，函数不同，操作同类。'
        'Python 容器与对象管理、脚本解析／编译、XML 节点处理和 UNO 组件数据管理，也按具体用途逐项对应。', '',
        '**公共操作按具体用途对应。** 每类都保留旧 OPM／TLC 的实际依据，'
        '包括字典／列表操作、对象调用、XML 文本比较与节点查询、组件引用管理、字体和像素格式处理。'
        '例如 ElementTree 与 lxml 都会查询 XML 节点，Pillow 与 VCL 都会读写图片像素。'
        '旧 OPM 的冻结脚本还实际调用 `PdfWriter.write`，提供 PDF 对象写出的操作依据。', '',
        '**合计覆盖＝已覆盖函数＋未匹配函数中的同类操作。** 同一部分只计算一次。'
        'JPEG 编解码、图像模糊、多图合成和 Word／PPT 文档对象路径分别保留。', '',
        '**表 7-4A：大规模复测中，计入同类操作后的覆盖。**', '',
        t(['用例','函数已覆盖','同类操作补充','合计覆盖'],[
            [rows[p]['format']+' '+p+'（'+SIZES[p]+'）',pct(rows[p]['shares_pct']['exact']),
             equivalent_cell(rows[p]),'**'+pct(rows[p]['supported_share_pct'])+'**'] for p in ORDER]), '',
        '**计入同类操作后：** Word 009 从函数匹配的 '+pct(rows['009']['shares_pct']['exact'])+' 提高到 '+pct(rows['009']['supported_share_pct'])+'，'
        'PPT 021 从 '+pct(rows['021']['shares_pct']['exact'])+' 提高到 '+pct(rows['021']['supported_share_pct'])+'，'
        'PPT 029 从 '+pct(rows['029']['shares_pct']['exact'])+' 提高到 '+pct(rows['029']['supported_share_pct'])+'。'
        +str(high)+'/12 项大档合计超过 85%。', '',
        '#### 7.3.3 剩下的是什么，还有必要增加用例吗', '',
        '公共组件中能确认属于旧例同类操作的部分，已计入表 7-4A。'
        '下表合并列出剩余函数的用途和权重。'
        '**函数尚未匹配，不等于操作是新增的；只有已明确识别的不同操作，才作为补充用例的依据。**', '',
        '**表 7-5：大规模复测后，逐例说明剩余部分。** 各百分比均按整轮保留样本的周期权重计算；'
        '各行列出的函数权重加上未解析部分，等于表 7-4A 合计覆盖之外的部分。', '',
        t(['用例','尚未匹配的函数主要在做什么','未解析'],gap_rows(eq)), '',
        'Office 公共组件承担属性、数据、文字和位图处理；例如 `libsvllo.so` 管理属性／样式，'
        'UNO 库管理组件数据，`libvcllo.so` 处理文字与位图。'
        '同一个库可以执行不同工作，所以按具体操作判断覆盖。'
        'Python 项来自 CPython 解释器库 `libpython3.12.so.1.0`；“其余”列举主要用途，权重包含未逐项展开的全部剩余函数。', '',
        '**PPT 的公共工作已计入，剩余主要看具体图片与幻灯片操作。** '
        '021 的 JPEG 编解码合计 '+pct(operation_pct(rows['021'],'JPEG 编解码'))+'，'
        '其中 `encode_mcu_gather` 约占 '+pct(ppt['top_function']['period']/rows['021']['roi_period']*100)+'；'
        '另有模糊 '+pct(operation_pct(rows['021'],'图像模糊'))+'、图文对象／样式 '
        +pct(operation_pct(rows['021'],'图文对象／样式'))+' 和多图合成 '
        +pct(operation_pct(rows['021'],'多图合成'))+'。这些比通用 Python／XML 函数更能说明补充价值。', '',
        '**Word 009 的公共计算已计入覆盖。** Python 对象管理、XML 比较等已按同类操作对应；'
        '其余 '+pct(rows['009']['shares_pct']['other_resolved'])+' 为绘图指令、PDF 字形登记、加密／证书等函数差异。', '',
        '**Word 专用工作仍单独保留。** LibreOffice Writer 的 `libswlo.so` 负责段落、表格与布局，'
        '`libsw_writerfilterlo.so` 负责 Word／DOCX 导入。扣除两库中的通用容器和运行支撑后，'
        '尚未覆盖的 Word 导入／对象布局为 '+pct(operation_pct(rows['009'],'Word 导入／对象布局'))+
        '。001、003 同样有 Word 路径；009 的反复排版与目录页码确认使这部分更突出。', '',
        selection_conclusion(),
        '[原始、小档、大档完整结果](../analysis/docops/processed/unified-scaling-final-20261108/analysis.md)｜'
        '[本次归并与旧例函数依据](../'+equivalence.OUTPUT+'/analysis.md)｜'
        '[补充组合核算](../'+selection.OUTPUT+'/analysis.md)｜'
        '[早期 Word 009 交叉核对](../analysis/docops/processed/word009-coverage-review-20261113/review.md)', ''])


def selection_conclusion():
    data=selection.load();exact=data['modes']['exact'];op=data['modes']['operation']
    require(exact['primary']['selected']==['013','021'] and exact['minimum_count']==2,
            'Exact-function selection no longer supports the two-task recommendation')
    require(op['primary']['selected']==['009','021'],'Operation selection changed')
    return '\n'.join([
        '#### 7.3.4 结论：按函数或按操作，分别补哪些用例', '',
        '**只看具体函数：优先增加 Excel 013＋PPT 021。** '
        '新出现的库主要包括 PNG 编解码的 libpng、图片处理的 ImageMagick、JPEG 编解码的 libjpeg，'
        '以及 lxml 扩展和 Word 的 Writer 库；旧例已有的 VCL、OOXML 等库中也出现了不同函数。'
        '013 可补 PNG 预览和图片处理函数，021 可补 JPEG、图片处理及幻灯片相关函数。', '',
        '**把同类操作也算上：先补 PPT 021，需要研究 Word 导入与排版时再加 009。** '
        '旧两例已涵盖 Python、XML、压缩／解压、图片缩放、页面渲染和表格重算等共同操作。'
        '021 重点补 JPEG 编解码、模糊和多图合成；009 重点补 Writer 的 Word 导入、段落、表格和分页。', '',
        method.table(['判断口径','补充的原始用例','十二项大档的平均覆盖'],[
            ['具体函数匹配','013＋021',pct(exact['base']['mean_pct'])+' → **'+pct(exact['primary']['mean_pct'])+'**'],
            ['计入同类操作','021',pct(op['base']['mean_pct'])+' → **'+pct(op['ppt_only']['mean_pct'])+'**'],
            ['计入同类操作','021＋009',pct(op['base']['mean_pct'])+' → **'+pct(op['primary']['mean_pct'])+'**']]), '',
        '平均覆盖先分别计算十二项大档的覆盖率，再等权取平均；未解析部分仍计入分母。'
        '候选均为十二项原始用例，不增加规模变体。', '',
        '**少量补例能补多少：** 若以平均覆盖达到 90% 为精简选型目标，具体函数口径至少需两项；'
        '最好的单项 013 为 '+pct(exact['frontier'][1]['mean_pct'])+'，013＋021 达到 '
        +pct(exact['primary']['mean_pct'])+'。计入同类操作时，旧两例本身已达到 '+pct(op['base']['mean_pct'])+'，'
        '补 021、009 是为增加图片处理和 Word 路径。', '',
        '**仍值得单独看的是 PPT 029。** 加入 013＋021 后，其具体函数覆盖为 '
        +pct(exact['primary']['cases']['029']['coverage_pct'])+'；加入 021＋009 后，计入同类操作的覆盖为 '
        +pct(op['primary']['cases']['029']['coverage_pct'])+'。若关注幻灯片表格样式，再补原始 029。', ''])


def section74(td):
    rows=td['targets'];t=method.table;scale=td['reference_scale_pp']
    return '\n'.join([
        '### 7.4 Topdown 相似性：CPU 瓶颈分布是否接近', '',
        '本节只比较十二项原始新用例。函数和操作覆盖回答“执行了什么”，Topdown 回答“CPU 的瓶颈份额如何分配”。'
        '采用七维、不重复计权的向量，IPC 单独列相对变化，idle 不加入距离。', '',
        '**表 7-6：七维向量。** 误推测、前端和后端由各自子项替换，七项合计约 100%。', '',
        t(['向量分量','含义'],[
            ['Retiring','有效完成'],['Branch Mispredicts','分支误判'],['Machine Clears','流水线清空'],
            ['Fetch Latency Bound','前端延迟受限'],['Fetch Bandwidth Bound','前端带宽受限'],
            ['Core Bound','核心执行受限'],['Memory Bound','缓存／内存供数受限']]), '',
        '向量顺序为 `[Retiring, Branch Mispredicts, Machine Clears, Fetch Latency, Fetch Bandwidth, Core, Memory]`。'
        '所有分量均取 0–100 的百分数，不额外标准化。', '',
        t(['指标','公式','读法'],[
            ['七维余弦','`Σ(AᵢBᵢ) / [√ΣAᵢ² × √ΣBᵢ²]`','越接近 1，形状越接近'],
            ['七维欧氏距离','`√Σ(Aᵢ−Bᵢ)²`','越小，占比差异越小']]), '',
        '**算例：** A=`[20,4,1,15,5,45,10]`，B=`[20,4,1,10,5,50,10]`；前端延迟减少 5 pp、Core 增加 5 pp，'
        '余弦为 0.9933，欧氏距离为 √(5²＋5²)=7.07。两项结合阅读，避免高余弦掩盖分项变化。', '',
        '**比较参照：** 旧 OPM／TLC 各取五次采集均值，两者余弦为 0.9962、欧氏距离为 '+f'{scale:.2f}。'
        '新例分别对照两例，表中列欧氏距离较近的一路。以 '+f'{scale:.2f}'+' 为本批参照，范围内记为“相对接近”；这不是统计检验阈值。', '',
        '**表 7-7：十二项原始新用例的 Topdown 比较。**', '',
        t(['新用例','较近旧例','七维余弦 ↑','七维欧氏距离 ↓','判断','IPC 变化'],[
            [rows[p]['format']+' '+p,rows[p]['nearest_reference'],f'{rows[p]["nearest"]["cosine_similarity"]:.4f}',
             f'{rows[p]["nearest"]["euclidean_pp"]:.2f}','相对接近' if rows[p]['within_reference_scale'] else '超出参照',
             f'{rows[p]["nearest"]["ipc_relative_change_pct"]:+.1f}%'] for p in ORDER]), '',
        '**表 7-8：差异最大的三项。** 单位为百分点，正号表示新例更高。', '',
        t(['新用例','对照','主要变化（pp）'],[
            [p,rows[p]['nearest_reference'],'；'.join(d['metric'].replace('存储受限','内存受限')+' '+f'{d["delta_pp"]:+.2f}' for d in rows[p]['nearest']['largest_differences'])] for p in ORDER]), '',
        '**结果：** 009、026 相对接近旧例，距离为 3.40／4.04；021 为 4.91，接近参照边界。'
        '031、037、016 的距离为 13.39／12.38／11.41，分项差异更明显。共同函数和同类操作可以承担不同权重，'
        '因此 7.3 的操作归并与本节的瓶颈比较分别判断。', '',
        '**统计口径：** 新例每项一次采集、内部十轮；采用 Report-ALL。CPU 0–7 包络包含步间间隙及可能的同核宿主活动。'
        '旧 OPM／TLC 到自身均值的最大距离为 1.89／0.55；新例均高于对应重复波动范围。', '',
        '[完整七维对照](../'+topdown.OUTPUT+'/analysis.md)保留 24 组新旧配对、原值及未计数标记。', ''])


def render(scale,eq,td,original):
    top_libraries=native_library_hotspots(scale)
    t=method.table;lines=['## 七、扩展任务操作：旧用例的代表性与补充建议','',
        '前六章考察跨行业输入，本章进一步扩展实际任务操作。', '',
        '**结论：旧 OPM／TLC 保留为核心；具体函数优先补 013＋021，不同操作优先补 021、按需加 009。** '
        '本节先说明样本与软件栈，再用规模复测区分函数实现差异和操作差额，最后结合 Topdown 给出补充建议。', '',
        '### 7.1 测了什么，如何回放与采集', '',
        t(['格式','任务','主要操作'],[
            ['PDF','031／037／pdfwf005','材料包修复、发布、预览'],['Excel','013／014／016','评审发布、补助发布、情景重算'],
            ['Word','001／003／009','发布修复、元数据清理、手册构建'],['PPT','021／026／029','无障碍整改、图表重建、样式发布']]), '',
        '十二项任务来自已保存的 Agent 轨迹，每项冻结最终有效脚本、输入、Skill 和命令。回放直接执行构建、修补、重算、渲染和原有检查，'
        '公共入口负责调度与归档，不调用模型。原始 Agent 官方内容判定为四项通过、八项未通过；十二项工具链回放均完成，来源判定另记。', '',
        t(['项目','旧 OPM／TLC','十二项原始新用例'],[
            ['环境','Python 3.12.3、LibreOffice 25.8.7.3','共用基础版本，补充文档与图像依赖'],
            ['采集次数','每路五次独立采集','每项每路一次，内部十轮'],
            ['perf','cycles:u、49 Hz、DWARF 16384','同参数；工作流 ROI 区间并集'],
            ['Topdown','DevKit，CPU 0–7，1 秒间隔','同参数；控制器 CPU 9'],
            ['边界','完整循环，含 reset／检查','perf 排除准备、reset、归档；Topdown 为按核包络']]), '',
        'perf 与 DevKit 分开运行。热点合并保留样本的周期权重；旧例 Topdown 取五次 ALL 均值，新例取本次 ALL。'
        '7.3 比较原始规模与大规模复测；7.4 和 7.6 使用十二项原始任务。', '',
        software_section(scale),
        '**表 7-2：旧基准概览。** 组件按软件归属汇总，比例为用户态 perf 周期权重。', '',
        t(['基准','主要脚本／进程','主要组件'],[
            [name,'；'.join(r['script']+' '+method.pct(r['share_roi']) for r in c['processes'][:4]),
             '；'.join(r['library']+' '+method.pct(r['share_roi']) for r in c['libraries'][:4])]
            for name,c in scale['references'].items()]), '',
        '**表 7-3：旧两例与十二项原始新任务的前三个原生库。** 每格为“库名、用途、占比”，库名简写。', '',
        native_hotspot_table(scale,top_libraries), '',
        '★ 表示旧 OPM 或 TLC 中也观测到该库。占比为该库在整轮保留样本中的周期权重，不将前三项重新归一化。'
        '任务编号链接到冻结脚本与命令，进程明细见[详细记录](experimental-results.md)；'
        '逐库权重、zlib 调用来源与采集记录见[表格依据](evidence/old-new-preview-comparison-20261116.json)。', '',
        '**预览区别：** 旧 OPM 已生成 PNG，旧 TLC 不生成页面预览；十二项新任务均生成预览图片。', '',
        '**新 Excel 仍有 XML 等文件的压缩／解压。** XLSX 是 ZIP 包，读取时解压其中的 XML 等内容，'
        '保存时重新压缩；XML 解析本身由解析库执行。新任务在工作簿处理之外，又把工作簿转为 PDF 并生成 PNG。', '',
        '**新 Excel 的高压缩权重主要来自 PNG 预览。** 旧 TLC 的 zlib 权重为 '
        +method.pct(top_libraries['tasks']['TLC']['zlib']['share_roi'])+'，主要服务于工作簿读写。'
        '新 Excel 014 的 zlib 为 '+method.pct(top_libraries['tasks']['014']['zlib']['share_roi'])+'，其中 '
        +method.pct(next(r['share_roi'] for r in top_libraries['tasks']['014']['zlib']['by_script'] if r['script']=='pdftoppm'))+
        ' 是 `pdftoppm` 生成 PNG 所占的整轮权重。PPT 的 JPEG 编码主要使用 libjpeg，与 PNG 的 zlib 压缩不同。', '',
        '**本节小结：上层文档库按格式分工，底层计算库大量复用。** '
        '旧 OPM／TLC 已包含 Python 执行、XML 处理、压缩／解压、表格重算和页面渲染所用的主要组件；'
        '新任务增加 Word／PPT 文档模型及部分图片处理实现。下一节进一步检查这些库中实际执行的函数。', '',
        section73(scale,eq),section74(td),conclusion(eq),
        '### 7.6 十二项任务的逐点曲线与读图说明','',
        '十二图共 533 个实际过程点。四条线表示误推测、前端受限、后端受限和有效完成；横轴为输出点编号，纵轴为百分比，名义间隔 1 秒。'
        '每图来自一次采集、内部十轮，展示过程变化；7.4 使用最终累计指标。','']
    notes=dict(method.PLOT_NOTES,**{'001':'Word 构建、转换与检查；主要函数热点集中在压缩。',
        '029':'解释器、字典查找与 DrawingML 表格样式共同参与。'})
    for number,p in enumerate(ORDER,1):
        caption=f'图 7-{number}：{scale["cases"][p]["format"]}／{method.task_label(p)}——四项 Topdown 过程'
        rel='../'+method.DEFAULT_OUTPUT+'/figures/'+p+'-bounds.svg'
        lines.extend(['#### '+caption,'',f'![{caption}]({rel})','',
            '**读图：** '+notes[p]+f' 本图共 {original["tasks"][p]["interval_points"]} 个实际输出点。',''])
    return '\n'.join(lines)


def revise(text):
    import unified_scaling_sections as source
    scale,_=source.load();eq=equivalence.load();td=topdown.load_result()
    original=json.loads((ROOT/method.DEFAULT_OUTPUT/'comparison.json').read_text())
    a=text.index('## 七、');end=text.index(method.END) if method.END in text else len(text)
    return text[:a]+render(scale,eq,td,original)+'\n'+text[end:]


def publish():
    path=ROOT/'docs/representativeness-assessment.md';before=path.read_text();after=revise(before)
    begin=before.index(method.BEGIN);end=before.index(method.END)
    require(before[:begin]==after[:after.index(method.BEGIN)] and before[end:]==after[after.index(method.END):], 'Outside chapter 7 changed')
    images=lambda t:[l for l in t.splitlines() if l.startswith('![图 7-')]
    require(images(before)==images(after) and len(images(after))==12,'Figure references changed')
    protected={p:method.sha(ROOT/p) for p in ('docs/representativeness-assessment.html','docs/experimental-results.md')}
    eq=equivalence.load();extension_path=ROOT/method.PUBLICATION;extension=json.loads(extension_path.read_text())
    doc=extension['documents']['docs/representativeness-assessment.md'];digest=lambda s:hashlib.sha256(s.encode()).hexdigest()
    require(doc['sha256']==digest(before),'Current report binding changed')
    doc.update(sha256=digest(after),append_sha256=hashlib.sha256(after.encode()[doc['prefix_bytes']:]).hexdigest())
    import unified_scaling_sections as source
    scale,_=source.load();libraries=library_inventory(scale)
    sources=[str(Path(__file__).relative_to(ROOT)),'analysis/docops/unified_scaling_sections.py',
        'analysis/docops/operation_equivalence.py','analysis/docops/operation_equivalence_refined.py',
        'analysis/docops/operation_equivalence_deep.py',
        'analysis/docops/supplement_selection.py',selection.OUTPUT+'/comparison.json',selection.OUTPUT+'/analysis-build.json',
        equivalence.OUTPUT+'/comparison.json',equivalence.OUTPUT+'/analysis-build.json',
        WORD_REVIEW,str(Path(WORD_REVIEW).with_name('sha256-index.json'))]
    extension['analysis_sources'].update({p:method.sha(ROOT/p) for p in sources})
    extension['software_library_comparison']=dict(path=EVIDENCE,scope='12 original tasks; Python workflow evidence and native perf library presence')
    extension['operation_equivalence_analysis']=dict(path=equivalence.OUTPUT+'/comparison.json',sha256=method.sha(ROOT/equivalence.OUTPUT/'comparison.json'),
        target_scope='12 large inputs',same_operation_policy=equivalence.POLICY,jpeg_separate=True,full_roi_denominator=True)
    extension['chapter7_reader_order']=dict(sections=['samples','software','original_and_scaled_operation_coverage','original_topdown','recommendations','curves'],
        base_cases=['OPM','TLC'],exact_function_extensions=['013','021'],operation_extensions=['021'],
        operation_optional=['009','029'],
        selection_mode='exact native functions versus evidenced equivalent operations; original-task supplements',figures=12)
    extension['supplement_selection']=dict(path=selection.OUTPUT+'/comparison.json',
        sha256=method.sha(ROOT/selection.OUTPUT/'comparison.json'),targets='12 large inputs',candidates='12 original tasks',
        average='equal-task arithmetic mean',exact_mean_reference_pct=selection.TARGET_MEAN)
    extension['word009_gap_review']=dict(path=WORD_REVIEW,sha256=method.sha(ROOT/WORD_REVIEW),
        scope='009-u500 residual functions compared against other measured task configurations')
    path.write_text(after);method.write(extension_path,extension)
    buildpath=ROOT/'analysis/hotspots/reports/pdf-xlsx-common-hotspots-20261027/build.json';build=json.loads(buildpath.read_text())
    build['document_sha256']['docs/representativeness-assessment.md']=digest(after);build['output_sha256']['report.md']=digest(after)
    build['document_extension']['sha256']=method.sha(extension_path);method.write(buildpath,build)
    for p,h in protected.items():require(method.sha(ROOT/p)==h,'Protected document changed: '+p)
    selected=selection.load()
    method.write(ROOT/EVIDENCE,dict(status='passed',scope='Chapter 7.3: exact-function and equivalent-operation supplement conclusions; full-report consistency review',
        report_before_sha256=digest(before),report_after_sha256=digest(after),protected_files=protected,
        figure_references_unchanged=True,analysis=dict(path=equivalence.OUTPUT+'/analysis-build.json',sha256=method.sha(ROOT/equivalence.OUTPUT/'analysis-build.json')),
        word009_review=dict(path=WORD_REVIEW,sha256=method.sha(ROOT/WORD_REVIEW)),
        library_inventory=libraries,native_library_hotspots=native_library_hotspots(scale),
        function_scale_comparison=scale_coverage_comparison(scale,eq),
        library_profile_source=dict(path='analysis/docops/processed/unified-scaling-final-20261108/comparison.json',
            sha256=method.sha(ROOT/'analysis/docops/processed/unified-scaling-final-20261108/comparison.json')),
        word_comparison=word_comparison(scale,eq),
        supplement_selection=extension['supplement_selection'],
        supplement_results={mode:dict(minimum_count=data['minimum_count'],reference_mean_pct=data['reference_mean_pct'],
            summaries={label:{k:v for k,v in data[label].items() if k!='cases'}
                       for label in ('base','primary','ppt_only')}) for mode,data in selected['modes'].items()},
        original_tasks_recommended=['013','021'],operation_tasks_recommended=['021'],optional_tasks=['009','029'],
        recommendation_scope='OPM/TLC core; exact functions 013+021; operations 021 with optional Writer 009 or table styles 029',
        ppt_supplements=eq['supplements']['009'],
        workload_or_collector_run=False,html_updated=False))
    print(path)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--publish',action='store_true',required=True)
    p.parse_args();publish()
