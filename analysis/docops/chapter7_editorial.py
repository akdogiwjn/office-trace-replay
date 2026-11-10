"""Edit the reader-facing chapter; numerical analyses and HTML stay immutable."""
import argparse
import hashlib
import json
from pathlib import Path
import re

import operation_comparison as method

ROOT = method.ROOT
EVIDENCE = 'docs/evidence/original-task-recommendations-update-20261108.json'


def require(ok,message):
    if not ok:
        raise ValueError(message)


def normalize_sections(text):
    """Accept either chapter order; return the legacy order for existing renderers."""
    a,b = text.index('### 7.5 '),text.index('### 7.6 ')
    end=text.index(method.END) if method.END in text else len(text)
    if '逐点曲线' in text[a:text.index('\n',a)]:
        return text
    require('逐点曲线' in text[b:text.index('\n',b)], 'Ambiguous figure section')
    conclusion=text[a:b].replace('### 7.5 ','### 7.6 ',1)
    figures=text[b:end].replace('### 7.6 ','### 7.5 ',1)
    return text[:a]+figures+conclusion+text[end:]


def rewrite_paragraphs(text, replacements):
    paragraphs=text.split('\n\n')
    for prefix,replacement in replacements:
        matches=[i for i,p in enumerate(paragraphs) if p.startswith(prefix)]
        if not matches and replacement in paragraphs:
            continue
        require(len(matches)==1,'Editorial paragraph missing or ambiguous: '+str(prefix))
        paragraphs[matches[0]]=replacement
    return '\n\n'.join(p for p in paragraphs if p)


def conclusion():
    return '''### 7.5 结论：建议增加哪些用例

**建议保留旧 OPM／TLC，优先增加 PPT 021。** 旧两例已包含文档读写、结构解析、压缩／解压、图片缩放、页面渲染和表格重算；021 补充幻灯片对象处理与多页联系表组合。

1. **优先增加 021（庇护所无障碍整改）。** 处理幻灯片形状、文本、表格、备注和样式，并生成页面预览和联系表；一个用例同时补充对象处理和多图组合两类操作。
2. **需要突出幻灯片表格样式时，再增加 029（季度业务回顾发布）。** 已观察到 DrawingML 表格样式函数，可作为 PPT 样式处理的强化项。
3. **若希望扩展具体函数热点，增加五个原始用例：`013、016、021、026、029`。** 分别补充工作簿预览发布、Calc 计算、幻灯片对象、页面绘制和表格样式等路径；选型依据见 7.3.4。

按典型操作扩展，先采用 **“OPM＋TLC＋021”**；按具体函数扩展，采用五个原始用例。'''


def revise(text):
    text=normalize_sections(text)
    a=text.index(method.BEGIN) if method.BEGIN in text else 0
    b=text.index('### 7.3 ');c=text.index('### 7.4 ')
    d=text.index('### 7.5 ');e=text.index('### 7.6 ')
    end=text.index(method.END) if method.END in text else len(text)
    intro=text[a:b]
    intro=rewrite_paragraphs(intro,[
        (('前六节保留原七例','前六节考察更换行业输入'),
         '前六节考察更换行业输入后的负载特征。本节进一步比较十二项 DocOps L3 任务，覆盖 PDF／Excel 的其他操作，以及新增的 Word／PPT 操作。\n'
         '**主要发现：旧 OPM／TLC 已包含大量共同基础计算，优先增加 PPT 021，可补充幻灯片对象处理和联系表组合。** '
         '7.1 说明样本与测量口径，7.2 介绍软件栈，7.3 分析函数覆盖及规模复测，7.4 比较原始新用例的 Topdown；7.5 给出补充建议，7.6 展示过程曲线。'),
        ('本节比较实际工作流，',
         '新任务每份采集中回放十轮，用于汇总热点与指标；独立采集次数为一次，重复运行波动另行评估。'),
        ('**表 7-1：软件用途。**',
         '**表 7-1：软件用途。** “脚本／工具”是直接调用的程序，“底层组件”是执行中消耗 CPU 的库。'
         '例如 python-docx 操作 Word，其周期可能落在 Python、XML 或压缩函数中；两层分别阅读。'),
    ])
    functions=text[b:c]
    functions=rewrite_paragraphs(functions,[
        ('**结论分两层看：',
         '**要区分操作与具体函数。** 旧 OPM／TLC 已包含多类共同计算。以下先检查十二项原始任务的函数匹配，'
         '再扩大输入规模，区分已有操作的实现差异与值得补充的操作。'),
        ('这里衡量的是**具体函数身份**。',
         '这里比较**具体函数身份**。例如旧例用 Pillow、新例用 ImageMagick 缩放图片，函数不同，操作仍属于图片缩放。'),
        ('**复测带来三点修正：**','**复测结果：**'),
        ('1. **部分初测差额与规模有关。**',
         '1. **多数任务扩大后，旧函数覆盖权重提高。** 11/12 组的大档高于原始任务；014、031、037 分别达到 '
         '91.82%、86.49%、86.72%。共同的页面处理、压缩等工作更突出，与部分启动和辅助开销被摊薄的解释一致。\n'
         '2. **013 的提高主要伴随 Python 构建权重增长。** 013-v1000 覆盖 93.25%，Python 库约 85.9%、构建脚本约 87.5%，'
         '解释器主循环函数约 51.1%。构建器反复遍历纠错清单、按供应商扫描评分记录，遍历次数可能随规模呈平方量级增长。'
         '这解释了通用 Python 函数变重的可能原因，具体行级耗时需单独测量。\n'
         '3. **扩大后仍有明显的工具差额。** pdfwf005 大档匹配 48.94%；PPT 021／026／029 分别为 50.44%／63.00%／46.29%。'
         '003、026、029、031 的大档低于小档，说明扩大输入不一定使热点更接近旧例。'),
        ('规模变体同时做了登记的',
         '规模变体按实际记录、单元或页面重新处理，同时完成脚本参数化和检查修复；包括 XML 校验、目录页码、'
         '异常表与情景核验等。016／029 继续只渲染首页，其余按各自规则渲染。各规模每种模式采集一次，'
         '003-u100 与 037-u5 各含三轮，其余一轮；详细变更见统一分析记录。'),
        ('**因此，“函数未覆盖”和“操作未覆盖”必须分开。**',
         '**操作差额集中在对象组织与多图组合。** 缩放、编码、渲染和重算在旧例中已有；换库或进入不同内部函数，'
         '属于实现差异。联系表把多页缩略图排列、合成为一张图，PPT 则引入幻灯片对象及样式处理。'
         '联系表内部也包含旧例已有的缩放和编码，因此其全部周期中只有一部分属于组合操作。'),
        ('本轮还将可识别的 Calc',
         '具体函数按 Calc、Writer、幻灯片对象、图像编码和文本样式细分归属；公共 UNO／C++ 框架另列。'),
        ('**函数方案为何需要七个配置：**',
         '**函数方案：** 规模复测定位的主要工具路径涉及 013、016、021、026、029 五类任务，'
         '据此推荐这五个原始用例。复测中至少一次达到 0.5% ROI 的 49 个显著函数目标及精确组合保留在数据记录；'
         '五个原始用例用于扩展热点路径，不等同于该精确组合。'),
        ('**操作方案为何 021 可以先补：**',
         '**操作方案：** 021 处理幻灯片的形状、文本、表格、备注和样式，将 8 页预览组合为一张联系表。'
         '它同时补充幻灯片对象处理和多图组合；'
         '029 可进一步突出表格样式，已有 `applyTableStylePart` 热点依据。'),
        ('一例操作方案并不意味着',
         '**两种方案的区别：** 操作方案选择典型处理类型，函数方案扩展具体工具与内部函数路径；覆盖百分比始终按精确函数匹配计算。'),
        ('1. **若目标是具体函数热点覆盖，',
         '旧例可继续作为共同计算基础；优先增加 021 补充典型操作，需要扩展具体函数路径时增加 013、016、021、026、029 五个原始用例。'),
        ('[十二组统一分析]',
         '[十二组统一分析](../analysis/docops/processed/unified-scaling-final-20261108/analysis.md)保留全部 36 配置、'
         '具体函数／脚本归属及变更记录；[函数选择结果](../analysis/docops/processed/unified-scaling-final-20261108/selection.json)'
         '保留 49 个目标、候选组合和删例检查。'),
    ])
    functions=functions.replace('### 7.3.5 结论：保留旧基础，按研究目标选择补充深度','### 7.3.5 小结')
    functions=re.sub(r'^### (7\.3\.\d+ )',r'#### \1',functions,flags=re.M)
    topdown=text[c:d]
    topdown=rewrite_paragraphs(topdown,[
        ('**本节比较 CPU 的瓶颈分配',
         '**本节比较十二项原始新用例与旧例的 CPU 瓶颈分布。** 采用七维、不重复计权的分区，'
         '用余弦观察整体形状，用欧氏距离衡量占比差异。规模变体用于 7.3 的覆盖复测。'),
        ('**简单例子：**',
         '**简单例子：** A=`[20,4,1,15,5,45,10]`，B=`[20,4,1,10,5,50,10]`；'
         '前端延迟减少 5 pp、Core 增加 5 pp。余弦为 **0.9933**，欧氏距离为 **√(5²＋5²)=7.07**。'
         '余弦反映整体接近，距离进一步揭示具体变化量。'),
        ('**用什么参照：**',
         '**比较参照：** 旧 OPM／TLC 各五次独立采集，逐项求均值后比较。两例均值的余弦为 **0.9962**，'
         '欧氏距离为 **4.77**。每个新用例分别与两例计算，表中展示欧氏距离较近的一路；完整记录保留两路结果。'
         '本批以 4.77 为参考：范围内称为“相对接近”，超出则继续查看分项差异。该参照用于描述结果，不是统计检验阈值。'),
        ('**表 7-7：',
         '**表 7-7：十二项新用例与旧 OPM／TLC 的七维比较。** 余弦越大越近，欧氏距离越小越近；'
         '每行的余弦、距离及 IPC 均使用同一对照。基准按瓶颈分布选择，可跨文件格式。'),
        ('1. **相对接近旧例的是',
         '1. **009、026 相对接近旧例。** 对 TLC 的余弦分别为 0.9981／0.9972，距离为 3.40／4.04，均在 4.77 的参照范围内。\n'
         '2. **021 接近参照边界，031、037、016 差异较大。** 021 的距离为 4.91；后三者分别为 13.39、12.38、11.41。'
         '其变化主要落在有效完成、前端供应以及核心／存储受限份额，见表 7-8。\n'
         '3. **共同函数不等于相同瓶颈权重。** 例如 013 余弦为 0.9916，距离仍为 7.30。'
         '旧例提供共同计算基础，补充任务则能体现不同的 CPU 分配；用例建议见 7.5。'),
        ('统计取 DevKit 最终 Report-ALL：',
         '**统计口径：** 取 DevKit 最终 Report-ALL；旧例为五次采集均值，新例各采集一次、内部回放十轮。'
         'Topdown 是 CPU 0–7 的采集包络，包含步间间隙及可能的同核宿主活动。旧例各次到自身均值的最大距离为 '
         'OPM 1.89／TLC 0.55；本批十二项均高于对应旧例的重复波动范围。未计数标记及公式核验结果保留在完整记录。'),
    ])
    figures=text[d:e].replace('### 7.5 ','### 7.6 ',1)
    figures=rewrite_paragraphs(figures,[
        (('下列十二张图','以下按 PDF、Excel、Word、PPT 展示'),
         '以下按 PDF、Excel、Word、PPT 展示十二项原始新用例，共 533 个实际过程点。每图四条线分别表示误推测、'
         '前端受限、后端受限和有效完成；横轴为输出点编号，纵轴为百分比，名义间隔 1 秒。\n'
         '每张图来自一次采集、内部十轮回放，用于观察过程变化；7.4 的相似性取最终累计指标。图中过程点尚未逐一对应到具体步骤。'),
        ('**读图：** 本项执行 Word 构建、',
         '**读图：** 本项执行 Word 构建、转换和检查；本次主要函数热点集中在压缩。 本图共 31 个真实输出点。'),
        ('**读图：** 本项出现解释器、',
         '**读图：** 本项同时出现解释器、字典查找与 DrawingML 表格样式函数，体现 PPT 对象与样式处理路径。 本图共 53 个真实输出点。'),
    ])
    # The old second figure-introduction paragraph is removed after consolidation.
    figures=re.sub(r'\n\n每张图是一份采集中十轮回放的过程，[^\n]*','',figures)
    figures=re.sub(r'^### 图 7-', '#### 图 7-',figures,flags=re.M)
    return text[:a]+intro+'\n\n'+functions+'\n\n'+topdown+'\n\n'+conclusion()+'\n\n'+figures.rstrip()+'\n\n'+text[end:]


def table_rows(text):
    return [line for line in text.splitlines() if line.startswith('|')]


def publish():
    import unified_scaling_sections as renderer
    import topdown_hierarchy_comparison as topdown
    path=ROOT/renderer.ASSESSMENT;before=path.read_text();after=renderer.revise_assessment(before)
    begin=before.index(method.BEGIN);end=before.index(method.END)
    require(before[:begin]==after[:after.index(method.BEGIN)], 'Earlier report changed')
    require(before[end:]==after[after.index(method.END):], 'Report suffix changed')
    numeric_rows=lambda t:[row for row in table_rows(t) if not row.startswith(('| 操作覆盖 |','| 函数覆盖 |'))]
    require(numeric_rows(before)==numeric_rows(after),'Measurement tables changed during recommendation update')
    require('| 优先一个用例：021；029 为可选强化项 |' in after,'Original recommendation missing')
    image_lines=lambda t:[l for l in t.splitlines() if l.startswith('![图 7-')]
    require(image_lines(before)==image_lines(after) and len(image_lines(after))==12, 'Figures changed')
    protected={p:method.sha(ROOT/p) for p in ('docs/representativeness-assessment.html','docs/experimental-results.md')}
    result,_=renderer.load();metrics=topdown.load_result()
    for dataset in (result,metrics):
        for p,h in dataset['input_sha256'].items():
            require(method.sha(ROOT/p)==h,'Measured evidence changed: '+p)
    extension_path=ROOT/method.PUBLICATION;extension=json.loads(extension_path.read_text())
    doc=extension['documents'][renderer.ASSESSMENT]
    digest=lambda s:hashlib.sha256(s.encode()).hexdigest()
    require(doc['sha256']==digest(before),'Report binding changed')
    doc.update(sha256=digest(after),append_sha256=hashlib.sha256(after.encode()[doc['prefix_bytes']:]).hexdigest())
    sources=[str(Path(__file__).relative_to(ROOT)),'analysis/docops/unified_scaling_sections.py']
    extension['analysis_sources'].update({p:method.sha(ROOT/p) for p in sources})
    extension['chapter7_reader_order']=dict(sections=['samples','software','function_coverage','topdown','recommendations','curves'],
        operation_priority=['021'],operation_optional=['029'],numeric_tables_unchanged=True,figures=12)
    decisions=extension['coverage_decisions']
    decisions['function_exact_cover_configurations']=decisions.get('function_exact_cover_configurations',decisions.get('function_configurations',[]))
    decisions['function_configurations']=['013','016','021','026','029']
    decisions['original_recommendation_is_exact_cover']=False
    decisions['operation_recommendation']=['021']
    path.write_text(after);method.write(extension_path,extension)
    buildpath=ROOT/'analysis/hotspots/reports/pdf-xlsx-common-hotspots-20261027/build.json'
    build=json.loads(buildpath.read_text());build['document_sha256'][renderer.ASSESSMENT]=digest(after)
    build['output_sha256']['report.md']=digest(after);build['document_extension']['sha256']=method.sha(extension_path)
    method.write(buildpath,build)
    for p,h in protected.items():require(method.sha(ROOT/p)==h,'Protected document changed: '+p)
    prior=json.loads((ROOT/EVIDENCE).read_text()) if (ROOT/EVIDENCE).exists() else {}
    method.write(ROOT/EVIDENCE,dict(status='passed',scope='Recommend original tasks only; retain scaling measurements and exact-cover records unchanged',
        report_before_sha256=digest(before),report_after_sha256=digest(after),numeric_tables_unchanged=True,
        operation_recommendation=['021'],function_recommendation=['013','016','021','026','029'],
        original_recommendation_is_exact_cover=False,
        operation_recipe=dict(path='docops/payload/tasks/021/recipe.json',sha256=method.sha(ROOT/'docops/payload/tasks/021/recipe.json')),
        initial_report_before_sha256=prior.get('initial_report_before_sha256',prior.get('report_before_sha256',digest(before))),
        figure_references_unchanged=True,figures=12,protected_files=protected,
        measurement_inputs_rechecked=len(set(result['input_sha256'])|set(metrics['input_sha256'])),
        publication_binding_sha256=method.sha(extension_path),html_updated=False))
    print(path)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--publish',action='store_true',required=True)
    p.parse_args();publish()
