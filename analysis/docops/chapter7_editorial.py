"""Render chapter 7 from frozen results; leave the earlier report and HTML intact."""
import argparse
import hashlib
import json
from pathlib import Path
import re

import operation_comparison as method
import operation_equivalence as equivalence
import topdown_hierarchy_comparison as topdown

ROOT=method.ROOT
EVIDENCE='docs/evidence/chapter7-operation-equivalence-update-20261112.json'
ORDER=[p for group in method.GROUPS.values() for p in group]
SIZES={'001':'500条记录','003':'500单元','009':'500事件','013':'1000供应商',
       '014':'10000申请','016':'500单元／2000行','021':'80页','026':'90页','029':'81页',
       '031':'100页','037':'100页','pdfwf005':'120页'}
SOFTWARE=[
    ['Python','脚本、对象管理','共用'],
    ['openpyxl','Excel 读写','共用'],
    ['python-docx／python-pptx','Word／PPT 对象编辑','新增'],
    ['Calc／Writer／Impress','重算／文字排版／幻灯片转换','LibreOffice 文档模块'],
    ['Poppler／pdftoppm','PDF 解析、页面渲染','共用'],
    ['Pillow／ImageMagick','图片缩放、滤波、合成','原有 Pillow；新增 ImageMagick'],
    ['ReportLab／fontTools','PDF 生成／字体处理','新增'],
    ['zlib／PNG、JPEG 编码库','压缩解压／图片编解码','编码路径分别统计'],
    ['Expat／ElementTree／lxml','XML 解析、结构处理','原有 Expat／ElementTree；新增 lxml'],
    ['libc／loader','内存、字符串、库装载','公共运行组件']]


def require(ok,message):
    if not ok:raise ValueError(message)


def normalize_sections(text):
    """Legacy helpers can still request curves before the final conclusion."""
    a,b=text.index('### 7.5 '),text.index('### 7.6 ')
    end=text.index(method.END) if method.END in text else len(text)
    if '逐点曲线' in text[a:text.index('\n',a)]:return text
    return text[:a]+text[b:end].replace('### 7.6 ','### 7.5 ',1)+text[a:b].replace('### 7.5 ','### 7.6 ',1)+text[end:]


def pct(value):
    return '<0.01%' if 0<value<.01 else f'{value:.2f}%'


def tool_short(tool):
    return {'LibreOffice·其他组件':'Office','LibreOffice·VCL':'位图','libfreetype':'字体'}.get(tool,tool)


def equivalent_cell(c):
    names=[r['operation'].replace(' 编解码','') for r in c['same_operations'] if r['share_pct']>=.05]
    return pct(c['shares_pct']['same_operation'])+'：'+'、'.join(names)


def remaining_cell(c):
    shown=[r for r in c['separate_operations'] if r['share_pct']>=.05]
    other=c['shares_pct']['other_resolved']+sum(r['share_pct'] for r in c['separate_operations'] if r['share_pct']<.05)
    parts=[r['operation']+' '+pct(r['share_pct']) for r in shown]
    tools='／'.join(tool_short(r['tool']) for r in c['other_tools'][:2])
    parts.append(tools+'等 '+pct(other))
    return '；'.join(parts)


def conclusion():
    return '''### 7.5 结论：建议增加哪些用例

**保留旧 OPM／TLC，优先增加 PPT 021。** 旧例承载共同的文档读写、解析、PNG 编码、图片缩放、PDF 渲染和表格重算；021 补充幻灯片对象处理与多图组合。

1. **优先增加 021（庇护所无障碍整改）。** 补充形状、文本、表格、样式和联系表合成。
2. **按需增加 029（季度业务回顾发布）。** 强化幻灯片表格与对象样式处理。
3. **若要扩展更多具体函数路径，增加五个原始用例：`013、016、021、026、029`。** 分别侧重预览发布、Calc、幻灯片对象、页面绘制和表格样式。
'''


def section73(scale,eq):
    cases=scale['cases'];rows=eq['cases'];t=method.table
    increased=sum(cases[b]['presence']['OPM+TLC']['observed_share_roi']>cases[p]['presence']['OPM+TLC']['observed_share_roi'] for p,(_,b) in scale['groups'].items())
    high=sum(c['supported_share_pct']>=85 for c in rows.values())
    return '\n'.join([
        '### 7.3 大规模任务中，旧用例覆盖了哪些计算', '',
        '**先比较具体函数，再检查未匹配部分属于什么操作。** 原始十二项的精确函数匹配为 45.41%–79.15%。'
        '小输入中的解释器启动、脚本解析和检查可能更显眼，因此为每项构建两档输入，共 24 个合成规模变体。', '',
        '**规模复测：** '+str(increased)+'/12 组的大档匹配高于原始任务。016 从 56.25% 提高到 80.03%，'
        '031 从 79.15% 提高到 86.49%；029 则从 55.51% 降至 46.29%。扩大规模影响权重，但不同任务的变化方向不同。'
        '原始、小档、大档的完整表见[统一分析](../analysis/docops/processed/unified-scaling-final-20261108/analysis.md)。', '',
        '#### 7.3.1 归并口径', '',
        '精确匹配按“库文件名＋完整函数名”判断，旧参考为 OPM＋TLC 完整函数清单的并集。'
        '同类操作仅从未匹配函数中识别：PNG 编解码、明确的图片缩放、PDF 渲染、压缩解压及 Calc 模型／重算。'
        '例如旧例使用 Pillow、新例使用 ImageMagick 缩放图片，函数不同，操作同类。', '',
        '**计入同类操作后的覆盖权重＝精确匹配权重＋同类操作差额。** 分母始终为目标工作流全部保留样本的 `cycles:u` 周期权重，'
        '不是函数个数或总 CPU 时间比例。JPEG 与 PNG 编码不同，JPEG 单列；Python／XML 和公共框架不自动归并。', '',
        '#### 7.3.2 大规模结果与操作归属', '',
        '**表 7-4：十二项大规模任务的覆盖与未匹配部分。** “其余已解析函数”列出未计入覆盖的操作及公共组件；'
        '对象／布局样式包含 Writer、PPT 和文本图形路径，公共组件不直接视作新增文档操作。'
        '精确匹配、同类操作、其他已解析、未解析四部分合计约 100%；四舍五入可能产生尾差。', '',
        t(['大规模用例','精确函数覆盖','同类操作（函数不同）','其余已解析函数','未解析','函数＋同类操作'],[
            [rows[p]['format']+' '+p+'（'+SIZES[p]+'）',pct(rows[p]['shares_pct']['exact']),
             equivalent_cell(rows[p]),remaining_cell(rows[p]),pct(rows[p]['shares_pct']['unresolved']),
             '**'+pct(rows[p]['supported_share_pct'])+'**'] for p in ORDER]), '',
        '#### 7.3.3 如何解释这些结果', '',
        '1. **旧例对共同基础计算具有代表性。** '+str(high)+'/12 项大档计入同类操作后的权重超过 85%。'
        '其中 PDF 031／037 为 97.79%／98.55%，Excel 014 为 96.63%。',
        '2. **016 计入同类操作后达到 87.33%。** 其中精确函数匹配 80.03%，Calc 模型／重算 6.80%，PNG 等约 0.51%。',
        '3. **图片处理的实现差异解释了部分低匹配。** pdfwf005 精确匹配 48.94%，计入明确缩放与 PNG 路径后为 94.07%；'
        '拼图合成 1.17% 单列。缩放和把多图排列合成是两类操作。',
        '4. **PPT 仍有值得补充的对象与样式路径。** 021／026 按严格口径为 74.21%／74.80%，JPEG 分别单列 8.03%／5.85%；'
        '029 为 47.80%，对象／布局样式占 7.56%，另有 Office、位图等差额。', '',
        '**013 的特殊性：** 其大档 Python 库约 85.9%、构建脚本约 87.5%。构建器反复遍历纠错清单和评分记录，'
        '通用 Python 函数变重是匹配提高的重要背景；不单凭高匹配率判断算法接近。', '',
        '**表 7-5：主要函数路径与操作。**', '',
        t(['函数／路径','操作','归类'],[
            ['`png_write_find_filter`','PNG 行滤波、编码','旧例同类'],
            ['`HorizontalFilter`／`VerticalFilter`','图片缩放','旧例同类'],
            ['`ScDocument::RemoveFromFormulaTree`','公式树管理','旧例同类'],
            ['`encode_mcu_*`／JPEG 库','JPEG 编解码','单列'],
            ['`CompositeOverImage`','多图合成','单列'],
            ['DrawingML／`applyTableStylePart`','幻灯片对象、表格样式','单列'],
            ['Writer／文本图形组件','文档对象、布局样式','单列'],
            ['Python／Office 公共组件','解析、对象、配置、运行支撑','其他差额']]), '',
        '**测量口径：** 各规模每路采集一次；Word 003 小档和 PDF 037 小档各含三轮，其余一轮。'
        '016／029 保留只渲染首页的范围。采样丢失及未解析权重保留，未推算补齐缺失周期；'
        '归并规则只描述已观测的操作类型。', '',
        '[归并明细](../'+equivalence.OUTPUT+'/analysis.md)保留逐函数分类、全部权重及质量标记；'
        '[规模记录](../analysis/docops/processed/unified-scaling-final-20261108/analysis.md)保留输入规模、脚本变更和全部 36 配置。', ''])


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
    t=method.table;lines=['## 七、扩展任务操作：旧用例的代表性与补充建议','',
        '**结论：保留旧 OPM／TLC 作为共同基础负载，优先增加 PPT 021。** '
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
        '7.3 使用大规模复测，7.4 和 7.6 使用十二项原始任务。', '',
        '### 7.2 执行了哪些软件与脚本', '',
        '**表 7-1：软件用途。** 脚本负责组织任务，底层库承担具体计算，两层分别阅读。', '',
        t(['软件／组件','用途','来源'],SOFTWARE), '',
        '**表 7-2：旧基准。** 以下比例为用户态 perf 周期权重。', '',
        t(['基准','主要脚本／进程','主要组件'],[
            [name,'；'.join(r['script']+' '+method.pct(r['share_roi']) for r in c['processes'][:4]),
             '；'.join(r['library']+' '+method.pct(r['share_roi']) for r in c['libraries'][:4])]
            for name,c in scale['references'].items()]), '',
        '**表 7-3：十二项原始任务。** 每行组件列展示前四项。', '',
        t(['任务','脚本／工具链','主要组件'],[
            [scale['cases'][p]['format']+'／'+method.task_label(p),method.FLOWS[p],
             '；'.join(r['library']+' '+method.pct(r['share_roi']) for r in scale['cases'][p]['libraries'][:4])] for p in ORDER]), '',
        '**软件栈变化：** Python、压缩、XML 和页面渲染继续共用；新增 python-docx、python-pptx、ImageMagick 等工具。'
        'LibreOffice 分别进入 Calc、Writer、Impress 的表格、文字和幻灯片模块。', '',
        section73(scale,eq),section74(td),conclusion(),
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
    sources=[str(Path(__file__).relative_to(ROOT)),'analysis/docops/unified_scaling_sections.py',
        'analysis/docops/operation_equivalence.py',equivalence.OUTPUT+'/comparison.json',equivalence.OUTPUT+'/analysis-build.json']
    extension['analysis_sources'].update({p:method.sha(ROOT/p) for p in sources})
    extension['operation_equivalence_analysis']=dict(path=equivalence.OUTPUT+'/comparison.json',sha256=method.sha(ROOT/equivalence.OUTPUT/'comparison.json'),
        target_scope='12 large inputs',same_operation_policy=equivalence.POLICY,jpeg_separate=True,full_roi_denominator=True)
    extension['chapter7_reader_order']=dict(sections=['samples','software','large_operation_coverage','original_topdown','recommendations','curves'],
        operation_priority=['021'],operation_optional=['029'],figures=12)
    path.write_text(after);method.write(extension_path,extension)
    buildpath=ROOT/'analysis/hotspots/reports/pdf-xlsx-common-hotspots-20261027/build.json';build=json.loads(buildpath.read_text())
    build['document_sha256']['docs/representativeness-assessment.md']=digest(after);build['output_sha256']['report.md']=digest(after)
    build['document_extension']['sha256']=method.sha(extension_path);method.write(buildpath,build)
    for p,h in protected.items():require(method.sha(ROOT/p)==h,'Protected document changed: '+p)
    method.write(ROOT/EVIDENCE,dict(status='passed',scope='Chapter 7: concise tables, large-input operation accounting, original-input Topdown',
        report_before_sha256=digest(before),report_after_sha256=digest(after),protected_files=protected,
        figure_references_unchanged=True,analysis=dict(path=equivalence.OUTPUT+'/analysis-build.json',sha256=method.sha(ROOT/equivalence.OUTPUT/'analysis-build.json')),
        original_tasks_recommended=True,workload_or_collector_run=False,html_updated=False))
    print(path)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--publish',action='store_true',required=True)
    p.parse_args();publish()
