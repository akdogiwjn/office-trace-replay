"""Publish the unified scale evidence and separate function/operation decisions.

The current reader-facing order is applied after the numerical sections.
The experimental record and HTML remain unchanged. Reads saved measurements only.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import operation_comparison as method
from unified_scaling_report import PCT, scale_label

ROOT = method.ROOT
ANALYSIS = 'analysis/docops/processed/unified-scaling-final-20261108'
ASSESSMENT = 'docs/representativeness-assessment.md'
EVIDENCE = 'docs/evidence/unified-scaling-report-update-20261108.json'
OPERATION_TASK = '021'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load():
    folder = ROOT/ANALYSIS
    build = json.loads((folder/'analysis-build.json').read_text())
    for name,digest in build['outputs'].items():
        require(method.sha(folder/name)==digest, 'Unified analysis output changed: '+name)
    result = json.loads((folder/'comparison.json').read_text())
    selection = json.loads((folder/'selection.json').read_text())
    require(len(result['groups'])==12 and len(result['cases'])==36, 'Wrong configuration count')
    goal = selection['goals'][selection['primary_goal']]
    require(len(goal['required_functions'])==49 and goal['candidates']['all_36']['minimum_count']==7,
            'Function recommendation needs editorial review')
    return result,selection


def observed(c):
    return c['presence']['OPM+TLC']['observed_share_roi']


def tool(c,name):
    return sum(r['share_roi'] for r in c['hotspot_coverage']['unseen_by_tool'] if r['tool']==name)


def func(c,name):
    return sum(r['share_roi'] for r in c['functions'] if r['function']==name)


def section73(result,selection):
    cases,groups = result['cases'],result['groups']
    table = method.table
    ordered = [p for tasks in method.GROUPS.values() for p in tasks]
    selected = selection['selected']
    goal = selection['goals'][selection['primary_goal']]
    families = sorted({cases[t]['parent'] for t in selected})
    increased = sum(observed(cases[b])>observed(cases[p]) for p,(_,b) in groups.items())
    l = ['### 7.3 旧用例覆盖了多少：规模复测与函数／操作两种判断', '',
        '**结论分两层看：旧 OPM／TLC 已体现大量共同基础计算；若要求具体函数身份匹配，仍需多配置补充；'
        '若按操作类型判断，可以只优先增加一个 PPT 021 用例。** '
        '本节先比较原始任务与扩大后的实测结果，再说明哪些差额是已有操作换了实现，哪些适合作为补充操作。', '',
        '### 7.3.1 原始任务初测：函数未匹配，不一定是操作未覆盖', '',
        '旧 OPM 在 PDF 表单填写字段，生成页面图片并缩放、检查；旧 TLC 对大型工作簿检查、增强、保存、'
        '重算及核验缓存／CSV。它们已包含解释执行、对象管理、XML 解析、压缩／解压、图片缩放和页面渲染。', '',
        '**表 7-4：十二项原始任务对旧 OPM＋TLC 的函数覆盖。** 合并旧两例完整已解析函数清单，'
        '按“库文件名＋完整物理叶函数名”精确匹配，包含旧清单低频函数。分母为目标 workflow ROI 的用户态 '
        '`cycles:u` 样本 period；三部分合计约 100%，不是函数个数或总 CPU 时间比例。未解析权重单列。', '',
        table(['任务','旧清单已见函数权重','已解析但旧清单未见','未解析'],[
            [cases[p]['format']+' '+p,*[PCT(cases[p]['presence']['OPM+TLC'][k]) for k in
                ('observed_share_roi','not_observed_share_roi','unresolved_share_roi')]] for p in ordered]), '',
        '这里衡量的是**具体函数身份**。例如旧例用 Pillow、新例用 ImageMagick 缩放同类图片，'
        '函数可以不同，但“图片缩放”这类操作已经有旧例依据。因此不能把全部未匹配周期直接命名为新增操作。', '',
        '### 7.3.2 扩大规模复测：十二组原始→小档→大档', '',
        '小输入也需要启动解释器、解析脚本、初始化组件和检查结果，这些开销可能更显眼。'
        '为检验这一猜想，将全部十二项任务分别扩为小、大两档，共 24 个合成规模变体；'
        '按扩大后的实际记录、单元或页面重新构建和处理，不以重复同一轮运行代替输入扩充。', '',
        '**表 7-4A：全部规模复测结果。** 原始、小档和大档的“覆盖”均沿用上表的精确函数匹配口径；'
        '右两列说明大档剩余差额。各变体 ID 和完整规模声明见统一分析记录。', '',
        table(['任务','原始已见','小档规模／已见','大档规模／已见','大档已解析未见','大档未解析'],[
            [cases[p]['format']+' '+p,PCT(observed(cases[p])),
             scale_label(cases[a])+'／'+PCT(observed(cases[a])),
             scale_label(cases[b])+'／'+PCT(observed(cases[b])),
             PCT(cases[b]['presence']['OPM+TLC']['not_observed_share_roi']),
             PCT(cases[b]['presence']['OPM+TLC']['unresolved_share_roi'])]
             for p in ordered for a,b in [groups[p]]]), '',
        '**复测带来三点修正：**', '',
        f'1. **部分初测差额与规模有关。** {increased}/12 组的大档覆盖高于原始任务。'
        '014、031、037 大档分别达到 '+PCT(observed(cases['014-n10000']))+'、'+
        PCT(observed(cases['031-u20']))+'、'+PCT(observed(cases['037-u20']))+
        '，页面预览、压缩等共同工作更突出；这支持部分辅助开销被摊薄的解释。',
        '2. **013 的提高有不同原因。** 013-v1000 覆盖 '+PCT(observed(cases['013-v1000']))+
        '，但 Python 库约 85.9%、构建脚本约 87.5%，解释器主循环函数约 51.1%。'
        '冻结构建器会对字段遍历完整纠错清单、为供应商扫描评分记录，相关遍历次数可能随规模呈平方量级增长。'
        '通用 Python 函数变重提高了匹配权重，不能将其解释为预览压缩主导或整个算法与旧 TLC 更相同；'
        '本次未做 Python 行级计时，不进一步认定单一函数的耗时来源。',
        '3. **扩大规模没有消除所有差额。** pdfwf005 大档仍只匹配 '+PCT(observed(cases['pdfwf005-u20']))+
        '；PPT 021／026／029 大档为 '+PCT(observed(cases['021-g10']))+'／'+
        PCT(observed(cases['026-u10']))+'／'+PCT(observed(cases['029-u10']))+
        '。003、026、029、031 还出现大档低于小档的情况，不能推导为“越大越接近旧例”。', '',
        '规模变体同时做了登记的脚本参数化与检查修复；例如 003 的 XML 校验优化、009 的目录页码稳定、'
        '016 的全量异常／四期图表和情景核验、029 的八类页恢复。016／029 保留只渲染首页的范围，'
        '其余按各自规则渲染。本实验用于观察规模敏感性，不把所有变化仅归因于文件体积。'
        '各规模每种模式只有一次独立采集，003-u100 与 037-u5 各含三轮，其余一轮。', '',
        '### 7.3.3 剩余热点是什么：区分实现差异与新增操作', '',
        '**表 7-5：扩大后仍可见的具体函数／工具差额，以及按操作类型的解释。** '
        '单函数与工具内全部未匹配函数合计分别标明，均以所在任务完整 ROI 为分母。', '',
        table(['函数／软件路径','代表性实测未匹配权重','对应什么工作','按操作口径如何判断'],[
            ['`png_write_find_filter`／libpng',
             '003-u500 单函数 '+PCT(func(cases['003-u500'],'png_write_find_filter'))+'；037-u20 '+
             PCT(func(cases['037-u20'],'png_write_find_filter'))+'；014-n10000 '+PCT(func(cases['014-n10000'],'png_write_find_filter')),
             '生成 PNG 预览时选择行滤波方式，以利压缩',
             '旧例已有图片输出与编码：视为已有操作的不同实现，不为这一个函数单独新增用例'],
            ['`HorizontalFilter`／`VerticalFilter`、ImageMagick 像素处理',
             'pdfwf005-u20 工具合计 '+PCT(tool(cases['pdfwf005-u20'],'ImageMagick'))+'；021-g10 '+PCT(tool(cases['021-g10'],'ImageMagick')),
             '缩略图缩放、滤波，以及联系表制作中的像素处理',
             '单纯缩放与旧 Pillow 操作同类，算已有覆盖；多图排列、合成联系表另列为补充操作，不能把整库权重都算成拼图'],
            ['JPEG、VCL 位图处理与 Poppler 页面绘制',
             '021-g10 未匹配合计：JPEG '+PCT(tool(cases['021-g10'],'JPEG'))+'、VCL '+PCT(tool(cases['021-g10'],'LibreOffice·VCL'))+'、Poppler '+PCT(tool(cases['021-g10'],'Poppler')),
             '图片读写、位图缩放与 PDF 页面生成像素',
             '旧例已有图片处理、转换与渲染；工具或内部子路径不同，不自动判为新增操作'],
            ['Calc 公式树、计算配置与单元格属性路径',
             '016-u500 明确 Calc 未匹配函数合计 '+PCT(tool(cases['016-u500'],'LibreOffice·Calc')),
             '管理公式树、计算配置、单元格与属性',
             '旧 TLC 已有工作簿处理和重算；按操作算已有覆盖，具体函数目标下才需补齐这些子路径'],
            ['DrawingML／幻灯片对象样式，例如 `applyTableStylePart`',
             '原始 029 明确 OOXML 路径合计 '+PCT(tool(cases['029'],'LibreOffice·OOXML'))+'，其中表格样式函数约 2.00%',
             '组织幻灯片形状、文本、表格、样式与对象属性',
             '与旧 PDF 表单／XLSX 单元格的对象模型不同，适合作为补充的幻灯片对象操作'],
            ['Writer 文字／页面对象与属性路径',
             '009-u500 明确 Writer 未匹配函数合计 '+PCT(tool(cases['009-u500'],'LibreOffice·Writer')),
             'Word 文档中的文字、页面对象及属性处理',
             '保留为独立文档模型的扩展证据；若进一步研究 Word 布局应另行选型，不宣称一个 PPT 用例能覆盖它'],
            ['Python 正则／字符串搜索与 Office 公共框架',
             '003-u500 `ucs2lib__two_way` 单函数约 2.43%，其中校验脚本约 2.42%',
             '检查残留文字、执行脚本、查找属性或管理公共对象',
             '统计保留，解释为相应处理／检查差异，不仅凭未匹配就称为新的文档编辑机制']]), '',
        '**因此，“函数未覆盖”和“操作未覆盖”必须分开。** '
        '同一项图片缩放可以换库，也可以进入不同的滤波函数；这些变化确实影响底层软件热点，但按本节的操作分类，'
        '仍属于已测的缩放。联系表则把多页缩略图排列、合成为一张图，确实增加了组合操作。'
        'PPT 还引入幻灯片对象的组织和样式路径。一个联系表步骤同时包含缩放、编码和合成，不能把全部周期都算成新增工作。', '',
        '本轮还将可识别的 Calc 单元格／属性、PPT 对象、Office 图像编码及文本样式函数从此前的 Office 兜底组细分出来。'
        '分组细化不改变前两表的精确函数匹配权重；普通 UNO／C++ 容器仍单列为公共框架。', '',
        '### 7.3.4 两种补充方案：函数身份与操作类型分别选择', '',
        '**表 7-5A：在旧 OPM＋TLC 基础上，按不同目标补充用例。** 两行回答的问题不同，不互相替代。', '',
        table(['判断口径','具体目标','补充哪些用例','如何理解'],[
            ['函数覆盖',
             '扩展图像处理、页面绘制、Calc 计算和幻灯片对象／样式等具体热点路径',
             '013、016、021、026、029：五个原始用例',
             '根据规模复测定位的工具路径选择原始任务，扩展具体函数的观测范围'],
            ['操作覆盖',
             '已有缩放、编码、渲染和重算，即使换工具或内部函数，仍视为已有操作；优先补充此前没有直接体现的操作类型',
             '优先一个用例：021；029 为可选强化项',
             '021 同时包含幻灯片对象／样式处理和多页联系表组合。是精简扩展建议，不宣称覆盖所有 Word／PPT 操作']]), '',
        '**函数方案为何需要七个配置：** 49 个目标来自全部原始、小档、大档实测结果，'
        '门槛只用于选型，候选清单中的低频出现也可提供匹配。逐步枚举验证少于七个配置不能补齐目标；'
        '按家族合并各档清单时，最少家族是 '+ '、'.join(families)+'。'
        '若连字体、XML、文本样式等 66 个显著文档工具身份也逐一补齐，则需 10 个配置；'
        '所有工具的 148 个显著未见身份则需 16 个。它们是更严格的目标，不作为精简操作方案的必选范围。', '',
        '**操作方案为何 021 可以先补：** 它处理幻灯片的形状、文本、表格、备注和样式，'
        '再将 8 页预览组合为一张联系表；构建、检查、转换和拼图均有实际回放依据。'
        '这比单独换一种图片缩放库多了对象组织和多图组合操作。'
        '若希望更突出幻灯片表格样式，可再加 029，已有 `applyTableStylePart` 热点证据，但不把它列为操作方案的必需项。', '',
        '一例操作方案并不意味着其函数清单能替代七配置方案：**前面的覆盖百分比仍保持精确函数口径，'
        '不会因“操作同类”而调高。** 选入参考的配置与自身匹配也不作为独立验证。', '',
        '### 7.3.5 结论：保留旧基础，按研究目标选择补充深度', '',
        '1. **若目标是具体函数热点覆盖，采用五个任务家族、七个配置的方案。** '
        '它补齐本节定义的 49 个显著目标身份，适合检查工具实现和内部函数路径；不将其写成全部函数均已覆盖。',
        '2. **若目标是典型操作代表性，优先采用“旧 OPM／TLC＋021”。** '
        '旧例继续承载解释执行、结构解析、读写、压缩、图片缩放、页面渲染和重算等共同基础计算；'
        '021 补充幻灯片对象处理与联系表组合。029 可作为表格样式的强化项，其他工具实现差异不要求逐个加例。',
        '3. **规模复测支持旧例的基础价值，但不是操作全覆盖证明。** '
        '多数大档已见权重提高，013 的 Python 构建增长、PPT 的对象路径和 Word 的布局／属性差额仍需分别解释。'
        '本节的精简建议用于补充部分有价值的新操作，不替代所有办公场景的选型。', '',
        '[十二组统一分析](../'+ANALYSIS+'/analysis.md)保留全部 36 配置、具体函数／脚本归属与规模 Topdown 变化；'
        '[函数选择结果](../'+ANALYSIS+'/selection.json)保留 49 个目标、候选组合和删例检查。'
        '此前[首批规模记录](experimental-results.md#十规模复测与补充用例选择)中的 20 配置／34 身份／三例方案按历史范围保留，'
        '不作为本节新增规模任务后的当前结论。', '']
    require(selected==['013','013-v100','016-u500','021','026-u10','029','029-u5'], 'Update selection prose')
    return '\n'.join(l)


def section76():
    return '\n'.join(['### 7.6 最终判断：旧负载的代表性与两种补充方案', '',
        '**保留旧 OPM／TLC 作为共同基础计算的核心，按研究目标选择函数方案或操作方案。**', '',
        '- **跨行业输入实验的结论保持不变。** 原七例在相近任务形态下延续主要热点；扩展任务和规模实验进一步说明哪些工具路径与操作还需补充。',
        '- **函数身份目标采用七配置方案。** 013、013-v100、016-u500、021、026-u10、029、029-u5，涉及五个任务家族，精确补齐 7.3 定义的 49 个显著未见函数身份；不是全部函数的全覆盖。',
        '- **操作类型目标优先采用一例方案。** 旧例已有缩放、编码、页面渲染和重算，不因换库或内部函数就逐一新增用例；优先补充 021 的幻灯片对象处理和多页联系表组合，029 作为表格样式强化项可选。Word 布局等其他扩展仍保留为后续研究方向。',
        '- **覆盖权重与瓶颈分别阅读。** 7.4 用七维余弦与欧氏距离比较十二项原始新用例与旧例的接近程度，7.5 保留原十二项过程曲线；完整指标见[统一分析](../'+ANALYSIS+'/analysis.md)。009、026 的分区相对接近，其他任务仍有程度不同的偏离，不能仅凭高函数匹配率认定完整算法或 CPU 瓶颈相同。', '',
        '具体操作、未匹配权重、规模变化和两种方案的适用范围见 7.3。本轮只更新分析与建议，不自动调整正式任务集合。', ''])


def revise_assessment(text):
    from chapter7_editorial import normalize_sections, revise
    text=normalize_sections(text)
    result,selection = load()
    require(text.count('### 7.3 ')==1 and text.count('### 7.4 ')==1 and text.count('### 7.6 ')==1,
            'Ambiguous assessment section boundaries')
    a,b = text.index('### 7.3 '),text.index('### 7.4 ')
    result_text = text[:a]+section73(result,selection)+'\n'+text[b:]
    a = result_text.index('### 7.6 ')
    end = result_text.index(method.END,a) if method.END in result_text[a:] else len(result_text)
    result_text=result_text[:a]+section76()+('\n'+result_text[end:] if end<len(result_text) else '')
    from topdown_hierarchy_comparison import revise_section
    return revise(revise_section(result_text))


def publish():
    report_path = ROOT/ASSESSMENT
    before = report_path.read_bytes()
    old_text = before.decode()
    after = revise_assessment(old_text).encode()
    new_text = after.decode()
    boundaries_unchanged = (
        old_text[:old_text.index('### 7.3 ')]==new_text[:new_text.index('### 7.3 ')] and
        old_text[old_text.index('### 7.4 '):old_text.index('### 7.6 ')]==
        new_text[new_text.index('### 7.4 '):new_text.index('### 7.6 ')] and
        old_text[old_text.index(method.END):]==new_text[new_text.index(method.END):])
    require(boundaries_unchanged, 'Protected report sections changed')
    protected = {p:method.sha(ROOT/p) for p in ('docs/representativeness-assessment.html',
        'docs/experimental-results.md')}
    result,selection = load()
    # Verify raw-origin bindings read-only, without running replay or collectors.
    for path,digest in result['input_sha256'].items():
        require(method.sha(ROOT/path)==digest, 'Analysis input changed: '+path)
    op_recipe_path = 'docops/payload/tasks/021/recipe.json'
    op_recipe = json.loads((ROOT/op_recipe_path).read_text())
    require('synthetic_variant' not in op_recipe, 'Expected original operation example')
    require(any('montage' in str(s['argv']) for s in op_recipe['steps']), 'No contact sheet command')
    extension_path = ROOT/method.PUBLICATION
    extension = json.loads(extension_path.read_text())
    doc = extension['documents'][ASSESSMENT]
    require(doc['sha256']==hashlib.sha256(before).hexdigest(), 'Existing report binding invalid')
    prefix = doc['prefix_bytes']
    require(hashlib.sha256(after[:prefix]).hexdigest()==doc['prefix_sha256'], 'Original seven-case report changed')
    doc.update(sha256=hashlib.sha256(after).hexdigest(),
               append_sha256=hashlib.sha256(after[prefix:]).hexdigest())
    sources = (str(Path(__file__).relative_to(ROOT)), 'analysis/docops/scaling_report_sections.py',
               ANALYSIS+'/comparison.json',ANALYSIS+'/selection.json',ANALYSIS+'/analysis-build.json')
    extension['analysis_sources'].update({p:method.sha(ROOT/p) for p in sources})
    extension['historical_scaling_analysis'] = extension.get('historical_scaling_analysis', extension.get('scaling_analysis'))
    extension['scaling_analysis'] = dict(path=ANALYSIS+'/selection.json',sha256=method.sha(ROOT/ANALYSIS/'selection.json'),
        scope='36 target configurations; 49 core function identities; separate qualitative operation recommendation')
    extension['coverage_decisions'] = dict(function_goal_identity_count=49,
        function_exact_cover_configurations=selection['selected'],
        function_configurations=['013','016','021','026','029'],
        original_recommendation_is_exact_cover=False,
        operation_recommendation=[OPERATION_TASK],operation_optional=['029'],operation_recommendation_is_exact_cover=False,
        function_percentages_not_relabelled=True)
    build_path = ROOT/'analysis/hotspots/reports/pdf-xlsx-common-hotspots-20261027/build.json'
    build = json.loads(build_path.read_text())
    build['document_sha256'][ASSESSMENT] = doc['sha256']
    build['output_sha256']['report.md'] = doc['sha256']
    # The original twenty-case generated section/build are historical analysis
    # inputs of the unified result. Leave them intact; the new document identity
    # and current renderer are bound by this independent publication record.
    report_path.write_bytes(after)
    method.write(extension_path,extension)
    build['document_extension']['sha256'] = method.sha(extension_path)
    method.write(build_path,build)
    require(all(method.sha(ROOT/p)==digest for p,digest in protected.items()), 'Protected Markdown/HTML changed')
    previous = json.loads((ROOT/EVIDENCE).read_text()) if (ROOT/EVIDENCE).exists() else {}
    evidence = dict(schema='unified-scaling-report-update-v1',status='passed',
        scope='Assessment 7.3 plus consistency update of 7.6; Markdown only',
        report_before_sha256=hashlib.sha256(before).hexdigest(),report_after_sha256=method.sha(report_path),
        initial_report_before_sha256=previous.get('initial_report_before_sha256',
            previous.get('report_before_sha256',hashlib.sha256(before).hexdigest())),
        protected_report_boundaries_unchanged=boundaries_unchanged,protected_files=protected,
        configurations=36,scale_variants=24,analysis_inputs_rechecked=len(result['input_sha256']),
        analysis_build=dict(path=ANALYSIS+'/analysis-build.json',sha256=method.sha(ROOT/ANALYSIS/'analysis-build.json')),
        coverage_decisions=extension['coverage_decisions'],operation_recipe=dict(path=op_recipe_path,sha256=method.sha(ROOT/op_recipe_path)),
        publication_binding_sha256=method.sha(extension_path),measurements_executed=False,html_updated=False)
    method.write(ROOT/EVIDENCE,evidence)
    print(report_path)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--publish',action='store_true',required=True)
    p.parse_args()
    publish()
