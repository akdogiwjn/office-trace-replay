"""Render saved unified scale results to Markdown/CSV; never publish HTML."""
import argparse
import csv
import json
from pathlib import Path

import operation_comparison as method

ROOT = method.ROOT
METRICS = method.METRICS
def PCT(value):
    return '<0.01%' if 0 < value < .0001 else method.pct(value)
TOOL_MEANING = {
    'PNG': ('PNG 输出／读取', '为页面预览选择行滤波方式、读写 PNG；旧例已有图片操作，但具体 libpng 函数未见'),
    'JPEG': ('JPEG 编码／解码', '把预览或联系表编码成 JPEG，或读取 JPEG；需按实际脚本区分'),
    'ImageMagick': ('缩略图与联系表', '缩放、横纵滤波、像素导入与拼图；旧 OPM 用 Pillow，未观察到这些 ImageMagick 函数'),
    'Poppler': ('PDF 页面渲染', '把文字、图形、图片绘制为像素；旧 OPM 已渲染 PDF，这里进入其他图像／字形子路径'),
    'LibreOffice·VCL': ('Office 图形处理', '位图缩放、卷积与模糊，可能在 Office 转 PDF 时发生；不能一概称为新增文档编辑'),
    'LibreOffice·OOXML': ('幻灯片／文档对象', 'DrawingML 表格样式、形状与属性映射；比旧表单／工作簿的对象路径更丰富'),
    'LibreOffice·Calc': ('公式与工作簿重算', '管理公式单元格、公式树和计算配置；旧 TLC 已有重算，差额是具体子路径'),
    'LibreOffice·Writer': ('文字文档布局', '文字框、段落与页面对象布局；只根据已出现的具体函数判断，不预设排版必然最重'),
    'Python': ('脚本及校验', '包含启动、源码解析、对象操作、正则与字符串搜索；不能整类称为新文档计算'),
    'LibreOffice·其他组件': ('Office 组件与公共框架', '对象属性、UNO、容器及未进一步归因的 Office 函数；统计保留，不能全部当作新增业务或全部当作无关开销'),
    'lxml': ('XML 文档结构', '解析或遍历 OOXML/XML；旧例已有 XML 工作，扩展任务使用不同库或不同路径'),
    'XML 组件': ('XML 文档结构', '解析文档结构、元素和属性；旧例已有此类工作'),
    'pixman': ('像素合成', '图像像素合成／缩放；结合执行脚本判断来自哪个渲染环节'),
    'cairo': ('二维绘制', '页面和图形绘制；可能由 Office 或页面渲染调用'),
    'libfontconfig': ('字体匹配', '查找、匹配字体和配置；不同于已经证实整个排版机制都是新热点'),
    'libfreetype': ('字形处理', '加载、变换或栅格化字形；与旧渲染共享工作类型'),
    'libharfbuzz': ('文本塑形', '把字符组织为可绘制的字形序列；需有实际函数证据才称为本次热点')}
TOOL_MEANING.update({
    'LibreOffice·文本布局': ('文本布局参数','准备布局参数；不据此认定整段排版最重'),
    'LibreOffice·文本样式': ('文本对象／属性','处理字重、颜色、编辑属性和文本对象'),
    'LibreOffice·矢量图形': ('图形几何','处理二维图形对象的范围与几何信息')})


def table(headers, rows):
    return method.table(headers, rows)


def short(value, n=100):
    return '`'+(value if len(value)<=n else value[:n-1]+'…')+'`'


def gap(case, tool):
    return sum(r['share_roi'] for r in case['hotspot_coverage']['unseen_by_tool'] if r['tool']==tool)


def coverage(case):
    return case['presence']['OPM+TLC']['observed_share_roi']


def scale_label(case):
    labels = {'records':'条记录','business_units':'业务单元','incident_cases':'事件',
        'vendors':'供应商','deduped_applications':'有效申请','regions':'地区',
        'units':'业务单元','groups':'组','notice_groups':'组','pages':'页',
        'output_pages':'输出页','model_rows':'模型行'}
    scale = case['source'].get('scale',{})
    return '，'.join(str(v)+labels[k] for k,v in scale.items() if k in labels)


def report(result, selection):
    cases, groups = result['cases'], result['groups']
    primary = selection['goals'][selection['primary_goal']]
    answer = primary['candidates']['all_36']
    selected = selection['selected']
    improved = [p for p,(_,b) in groups.items() if coverage(cases[b]) > coverage(cases[p])]
    small_up = [p for p,(a,b) in groups.items() if coverage(cases[b]) > coverage(cases[a])]
    lines = ['# 十二组任务的原始→小档→大档统一比较', '',
        '**先看判断：旧 OPM＋TLC 体现了相当多共同基础计算，但不能覆盖所有新增工具路径。** '
        f'12 组中有 {len(improved)} 组的大档旧函数覆盖权重高于原始任务，'
        f'其中 {len(small_up)} 组从小档到大档继续上升。Excel 013／014、PDF 031／037 的覆盖改善明显；'
        'ImageMagick 拼图、PPT 图形／对象处理以及 PNG 输出滤波等差额没有随放大消失。', '',
        '本次只对已有证据离线计算。范围为旧 OPM／TLC、12 个原始 DocOps 任务和 24 个合成规模变体；'
        '原始采集与历史分析文件均保留，未重跑任务、未重采 perf／DevKit、未更新正式报告或 HTML。', '',
        '## 1. 先把“覆盖”说清楚', '',
        '- **匹配对象：** 合并旧 OPM＋TLC 的完整已解析物理叶函数清单，包含低频函数，'
        '按“库文件名＋完整函数名”精确匹配，不合并克隆名或模糊相似函数。',
        '- **统计权重：** 目标任务完整 workflow ROI 内用户态 `cycles:u` 样本的 period。'
        '“已见＋已解析未见＋未解析”合计 100%；不是函数个数，也不是整轮 CPU 时间比例。',
        '- **解释规则：** 未见表示旧采样清单没有这个具体身份，不等于从未执行过、也不必然是新计算机制。'
        '未解析权重单列，既不算已见也不算未见。',
        '- **比较单位：** 每个配置单独作为分母，不把 36 个配置的 period 混合后称为某个总体覆盖率。'
        '旧基准为五次独立采集；父任务一次采集含十轮；规模任务每种模式一次采集，'
        '003-u100／037-u5 各含三轮，其余一轮。', '',
        '## 2. 十二组原始→小档→大档：覆盖是否改善', '',
        '下表只展示旧函数已见权重。右侧差额还包含未解析部分，不能直接全称为新增函数。', '',
        table(['格式／父任务','原始','小档','小档已见','大档','大档已见','原始→大档 pp'],[
            [cases[p]['format']+' '+p,PCT(coverage(cases[p])),a+'（'+scale_label(cases[a])+'）',PCT(coverage(cases[a])),
             b+'（'+scale_label(cases[b])+'）',PCT(coverage(cases[b])),f'{100*(coverage(cases[b])-coverage(cases[p])):+.2f}']
            for p,(a,b) in groups.items()]), '',
        '**如何理解这张表：**', '',
        '1. **Excel 013／014 和 PDF 031／037：覆盖提高，但原因不同。** '
        '014／031／037 主要是页面输出、压缩和渲染权重上升，较低覆盖的脚本／组件开销被摊薄；'
        '013 大档则转为 Python 构建主导（见第 3.4 节），不能归入同一种解释。'
        '结果支持“部分小输入使辅助开销更显眼”，但不支持把全部覆盖提高都归因于固定成本摊薄。',
        '2. **Word 001／003／009：覆盖有限改善，PNG 与校验差额仍在。** '
        '003 大档的 `png_write_find_filter` 单项约 22.10%；旧例已有生成图片，缺少的是此处具体 PNG 输出滤波函数。',
        '3. **pdfwf005 和 PPT：主要缺口持续存在。** pdfwf005 大档仍约一半周期未匹配；'
        '021／026／029 的大档也没有全部接近旧例，029 甚至下降。不能据此沿用“只要放大就能解决”的解释。',
        '4. **016：重算是已有操作，具体 Calc 子路径仍有差额。** 大档覆盖提高，但公式树／单元格管理等函数仍未见。'
        '它不是首次引入重算，也不能仅凭同为重算就认为所有函数均已覆盖。', '',
        '规模变体有登记的脚本参数化与校验修复：包括 003 的 XML 检查优化、009 的实际目录页码稳定、'
        '016 的完整异常表／四期图表／全量场景校验、029 的八类页恢复等。'
        '016／029 保留只渲染首页，其他任务按各自冻结规则渲染；因此本表是规模敏感性观察，'
        '不是只改变文件字节数的严格因果试验。', '',
        '## 3. 大档剩余差额：有多少，属于什么工具', '',
        table(['大档','旧函数已见','已解析未见','未解析','未见函数的前三个工具分组'],[
            [b,*[PCT(cases[b]['presence']['OPM+TLC'][k]) for k in
                ('observed_share_roi','not_observed_share_roi','unresolved_share_roi')],
             '；'.join(r['tool']+' '+PCT(r['share_roi']) for r in cases[b]['hotspot_coverage']['unseen_by_tool'][:3])]
            for _,b in groups.values()]), '',
        '工具分组仍以完整 ROI 为分母；例如“PNG 22%”不是指 PNG 内部的 22%。'
        '没有把 Python／Office 公共框架差额从分母删除，也没有把它们全部算成新的文档机制。', '',
        '本轮细分了此前落入 Office 兜底组的已知专属函数：例如 Sc 开头的 Calc 单元格／属性函数、'
        'PPT 占位符／页名导入、VCL 内图像编码，以及文本样式／图形几何。'
        '工具分组据此比上轮更细；旧函数已见权重、未见总权重及完整函数身份匹配不受分组改变影响。'
        '普通 UNO／C++ 容器仍留在公共框架组，完整规则见分析代码的 `classify_function()`。', '',
        '### 3.1 同样是未见，实际含义有三种', '',
        table(['情况','具体例子','旧例覆盖了什么／本次还缺什么'],[
            ['已有工作，换了实现或子路径','PNG 滤波；ImageMagick 缩放；Poppler 图像缩放',
             '旧例已有图片输出、缩放和页面渲染；缺的是这里的 libpng／ImageMagick／Poppler 具体函数'],
            ['扩展了实际操作','多页联系表拼图；幻灯片表格／形状样式',
             '多张预览排列合成，以及 PPT 对象样式路径；不能只用“都是图片／都是 XML”替代'],
            ['辅助执行或尚待细分','Python 源码解析、正则搜索；UNO／对象属性／公共容器',
             '统计保留，需结合脚本归属说明；不直接称为新的文档编辑机制，也不假定全部无关']]), '',
        '### 3.2 每组大档最突出的具体未见函数', '',
        '列出每组前三项；函数全名、全部低频函数及其各规模出现权重见 `unseen-functions.csv`。'
        '“执行脚本”来自采样的进程／脚本关联；含既有脚本身份推断或未归因线程时保留原标记，'
        '不把这列当作逐操作的精确计时。', '']
    for p,(_,b) in groups.items():
        c = cases[b]
        lines += ['**'+c['format']+' '+b+'：'+method.NAMES[p]+'**', '',
            table(['工具／库','函数','占完整 ROI','执行脚本'],[
                [f['tool']+' / '+f['library'],short(f['function'],110),PCT(f['share_roi']),
                 function_contexts(c,f)] for f in c['hotspot_coverage']['unseen_functions'][:3]]), '']
    lines += ['### 3.3 这些软件各自做什么、缺口由什么操作带来', '',
        table(['工具分组','通常承担的工作','本次应如何解释'],[
            [tool,*TOOL_MEANING.get(tool,('具体库内运算','已定位软件身份，操作用途待进一步细分'))]
            for tool in sorted({r['tool'] for _,b in groups.values()
                                for r in cases[b]['hotspot_coverage']['unseen_by_tool'] if r['share_roi']>=.005})]), '',
        '**几个最容易误读的归因：**', '',
        '- `png_write_find_filter` 来自生成 PNG 预览时的行滤波；不是 Word 专属排版，也不是 Excel 的公式计算。',
        '- ImageMagick 横纵滤波可能由缩略图生成／拼图触发；联系表是新增组合操作，但不能把整库每个函数都叫作拼图算法。',
        '- `ScDocument::RemoveFromFormulaTree`、`ScInterpreter::MergeCalcConfig` 来自 Calc 路径。'
        '旧 TLC 已重算，未见这些名字说明本次公式／场景处理走到了不同子路径。',
        '- Word 的正则、字符串搜索有相当部分属于验证器；Office 属性／UNO 函数也需保持具体归因，'
        '不能为了支持代表性而全删，也不能为了强调新场景而全称为新机制。', '',
        '### 3.4 013 大档的特殊变化：高覆盖主要来自 Python 构建', '',
        table(['013 配置','Python 库权重','zlib 权重','构建脚本权重','解释器主循环函数权重'],[
            [t,PCT(sum(x['share_roi'] for x in cases[t]['libraries'] if x['library']=='Python')),
             PCT(sum(x['share_roi'] for x in cases[t]['libraries'] if x['library']=='zlib')),
             PCT(sum(x['share_roi'] for x in cases[t]['script_contexts'] if x['script'] in
                 ('build_bid_evaluation_variant.py','build_public_bid_workbook.py'))),
             PCT(sum(x['share_roi'] for x in cases[t]['functions'] if x['function']=='_PyEval_EvalFrameDefault'))]
            for t in ('013','013-v100','013-v1000')]), '',
        '013-v1000 的 Python 库约 85.9%，`build_bid_evaluation_variant.py` 约 87.5%，'
        '`_PyEval_EvalFrameDefault` 单项约 51.1%。这些通用解释器／对象函数在旧例已出现，'
        '因此已见权重提高，但这不是预览压缩变成主要工作，也不能据此把整个构建算法说成与旧 TLC 相同。', '',
        '冻结构建器中，`apply_corrections()` 对每个待更正字段遍历完整纠错清单，'
        '`scores_by_vendor` 又为每个供应商扫描评分记录；当两边都随供应商数增长时，'
        '这些路径的遍历次数可能呈平方量级增长。静态代码与 Python 构建权重上升一致，'
        '本次没有 Python 行级计时，不能进一步声称某一行占了全部时间；也没有为了调整覆盖结果修改该代码。', '',
        '代码复核读取的是 recipe 绑定的冻结构建器，SHA256 已纳入本轮输入索引：`'+
        cases['013-v1000']['source']['code_review_material'][0]+'`。', '',
        '## 4. Topdown：规模改变了什么', '',
        '下表保留 IPC 和四个顶层分类；Core／Memory 是 Backend 的子项。'
        '数值取 DevKit Report-ALL 累计输出，不是过程点的算术均值。'
        '四个顶层分类合计约 100%；IPC 和子项不能再加进去。', '',
        table(['配置','IPC','Bad Spec %','Frontend %','Backend %','Retiring %','Core %','Memory %'],[
            [t]+[f'{c["metrics"][k]:.2f}' for k in (*METRICS[:5],'Core Bound','Memory Bound')]
            for t,c in list(result['references'].items())+[(b,cases[b]) for _,b in groups.values()]]), '',
        '旧两例的指标列为既有五次采集的均值；大档各只有一次独立采集。下表专门比较小档→大档，'
        '用百分点差直接说明变化，避免余弦接近 1 把差异遮住。', '',
        table(['小档→大档','ΔIPC','ΔBad Spec pp','ΔFrontend pp','ΔBackend pp','ΔRetiring pp','四 Bound 半 L1 pp'],[
            [a+'→'+b,f'{d["metrics_delta"]["IPC"]:+.2f}',
             *[f'{d["metrics_delta"][k]:+.2f}' for k in method.BOUNDS],
             f'{d["bound_total_variation_pp"]:.2f}'] for a,b in groups.values()
            for d in [result['comparisons'][a+' -> '+b]]]), '',
        '再检查原始任务→大档，以免只看小档与大档较接近，就遗漏了初始任务结构变化。', '',
        table(['原始→大档','ΔIPC','ΔBad Spec pp','ΔFrontend pp','ΔBackend pp','ΔRetiring pp','四 Bound 半 L1 pp'],[
            [p+'→'+b,f'{d["metrics_delta"]["IPC"]:+.2f}',
             *[f'{d["metrics_delta"][k]:+.2f}' for k in method.BOUNDS],
             f'{d["bound_total_variation_pp"]:.2f}'] for p,(_,b) in groups.items()
            for d in [result['comparisons'][p+' -> '+b]]]), '',
        '半 L1 = 四项顶层分类绝对差之和的一半，表示四类分配改变了多少个百分点。'
        '余弦只作辅助，所有原始→小档、原始→大档、小档→大档及 OPM／TLC→大档比较均保存在 '
        '`topdown-deltas.csv`。', '']
    biggest = sorted([(result['comparisons'][a+' -> '+b]['bound_total_variation_pp'],a,b)
                      for a,b in groups.values()],reverse=True)[:3]
    lines += ['本批小档→大档的顶层分配变化最大的是 '+
        '、'.join(f'{a}→{b}（{v:.2f} pp）' for v,a,b in biggest)+'。'
        '这说明“更多函数已见”与“微架构分配完全不变”不是同一个结论。', '',
        'Topdown 为 CPU 0–7 的完整采集包络，含边界、步间与轮间间隙；控制器在 CPU 9。'
        '保留 58 层级节点／事件、全部真实过程点及 `<not counted>` 标记；未把打印 0 当作未计数事件的真实零。'
        '它与 perf 的进程树 workflow ROI 口径分别记录，不强行当作同一窗口。'
        '本次没有从 1 秒日志插值制造新点，也不以一次采集论证稳定性。', '',
        '## 5. 最少补充哪些用例：先明确要补哪些函数', '',
        '先按既有的图片／页面／对象处理主缺口，加入本轮实际观察到的 Calc 子路径，定义核心补充目标：'
        '36 个新配置中，至少一个配置达到完整 ROI **0.5%**、旧 OPM＋TLC 未见、'
        '且属于这七组工具的已解析函数。再另列字体／XML／文本样式等更细身份的严格结果，'
        '以及包含 Python／公共框架的所有工具结果。没有只挑 Top-10，也没有把目标外的差额删除。', '',
        table(['补充目标','目标函数数','只选原始 12 项','从全部 36 个具体配置选择'],[
            [name,str(len(goal['required_functions'])),minimum_label(goal['candidates']['original_12']),
             minimum_label(goal['candidates']['all_36'])]
            for key,name in [('previous_six_tools@0.005','沿用上轮六类图像／页面／对象工具'),
                             ('core_plus_calc@0.005','核心补充目标：再加 Calc 子路径'),
                             ('document_tools@0.005','严格文档工具目标：再加字体／XML／文本样式等'),
                             ('all_resolved_tools@0.005','严格目标：所有工具，含 Python／公共框架')]
            for goal in [selection['goals'][key]]]), '',
        f'**核心补充目标精确最少为 {answer["minimum_count"]} 个具体配置。** '
        '下面展示求解器按名称排序选出的一组最小解；不是按耗时优化的最快方案。'
        '其他同样数量的方案见 `selection.json`，函数覆盖目标是采样中已出现的具体身份。', '',
        table(['建议补充的配置','任务／操作','删除它后仍缺的目标函数数','它独自补上的例子'],[
            [t,method.NAMES[cases[t]['parent']]+'；'+method.FLOWS[cases[t]['parent']],
             str(len(essential(selection,result,t))),
             '；'.join(short(f[1],85) for f in essential(selection,result,t)[:2])]
            for t in selected]), '',
        '**按任务名字看，是 '+str(len({cases[t]['parent'] for t in selected}))+' 个任务家族：'+
        '、'.join(sorted({cases[t]['parent'] for t in selected}))+'。** '
        '家族内允许合并本次各档已观测函数时，精确最少为 '+
        str(primary['family_union_cover']['minimum_count'])+' 个家族。'
        '这不等于每个家族随便选一个档就够；上面 '+str(answer['minimum_count'])+
        ' 个具体配置说明哪些档实际提供了目标函数，同一任务的原始／小档可能各有独有观测。', '',
        '这个核心方案没有要求每种文件格式各选一个。Word／PDF 预览中的许多 PNG 函数，'
        '也会被 Excel／PPT 的预览发布链触发；按函数身份可由这些配置共同补上。'
        '这不表示 Word／PDF 的完整业务流程可由它们替代。', '',
        '“最少”只针对上述函数身份、阈值与候选集成立，候选中低频出现也算见过。'
        '字体／XML／文本样式等全部显著身份逐一补齐需更多配置，数量见上表，不能把核心方案称为这些函数也已全覆盖。'
        '选入参考的配置会与自身匹配，因此下面同时给出其他配置结果，不把自身匹配称为独立验证。'
        '若只允许保留原始任务，表中的缺失身份需另加实测规模配置；不能用父任务名字替代未观测到的函数。', '',
        table(['大档目标','旧 OPM＋TLC 已见','加建议配置后已见','仍未见','未解析','与选入配置关系'],[
            [b,PCT(coverage(cases[b])),*[PCT(e[k]) for k in
              ('observed_share_roi','not_observed_share_roi','unresolved_share_roi')],
             '自身入选' if e['selected_as_reference'] else '同父任务不同档' if e['same_parent_as_selected'] else '未选家族']
            for _,b in groups.values() for e in [selection['evaluation']['targets'][b]]]), '',
        '核心方案后仍有未匹配权重，尤其是 Word 009 与 PPT 029。它们的差额没有被隐藏：', '',
        table(['大档','补充后仍未见','剩余前三工具组'],[
            [b,PCT(e['not_observed_share_roi']),
             '；'.join(x['tool']+' '+PCT(x['share_roi']) for x in e['remaining_by_tool'][:3])]
            for _,b in groups.values() for e in [selection['evaluation']['targets'][b]]
            if e['not_observed_share_roi'] >= .05]), '',
        '### 5.1 阈值敏感性：不能把一个数字当成绝对最优任务数', '',
        table(['目标阈值','核心工具缺口数','全部 36 配置中最少个数','最小解示例'],[
            [f'{threshold*100:g}%',str(len(g['required_functions'])),minimum_label(g['candidates']['all_36']),
             '、'.join(g['candidates']['all_36']['solutions'][0])]
            for threshold in (.001,.005,.01)
            for g in [selection['goals'][f'core_plus_calc@{threshold:g}']]]), '',
        '降低阈值会纳入更多低频实现细节，补充数量可能上升；这不是新增了同样多种业务机制。'
        '工具分组、阈值、全部目标函数、每个候选是否覆盖，以及移除单个推荐后的剩余权重均已保存。', '',
        '## 6. 对旧两例代表性的最终判断', '',
        '1. **旧例可继续作为共同基础计算的核心基准。** 放大后 Excel 013／014、PDF 031／037 的已见权重较高，'
        '说明解释执行、对象管理、XML、压缩／解压和页面／图片处理等共性具有实际证据。',
        '   其中 013 的高覆盖主要来自解释器／构建工作增长；014／031／037 更偏页面预览与压缩。'
        '共同函数覆盖不等于执行算法或工作量都一样。',
        '2. **“覆盖较低都是输入太小”不成立。** pdfwf005 的 ImageMagick 滤波／联系表、PPT 的图形和对象样式、'
        'PNG 输出滤波等函数在大档仍占有可观权重；旧两例不足以替代这些具体软件路径。',
        '3. **补充以操作与软件路径为单位更有效。** 需要保留真正触发图像缩放／拼图、页面输出、PPT 对象处理、'
        '以及本轮实际出现的 Calc／XML／字体子路径的配置；不必只因换行业就全部加入。'
        f'在本批明确定义的核心目标下，最少补充 {answer["minimum_count"]} 个配置（'+
        str(len({cases[t]['parent'] for t in selected}))+' 个任务家族）：'+ '、'.join(selected)+'。'
        '若要求每个字体／XML／文本样式热点身份也出现过，应采用上表的严格方案，不把两者混称。',
        '4. **辅助差额保持可见。** Python 校验搜索和 Office 公共框架不直接等同于新文档机制，'
        '也不从统计中删除；严格“所有热点身份均补齐”的成本已另列，不能与主建议混称。', '',
        '## 7. 数据与复核入口', '',
        '- `comparison.json`：38 个参考／目标配置、完整函数／工具／脚本权重、60 个成对比较、输入哈希。',
        '- `selection.json`：阈值敏感性、完整目标函数、精确最小解、不可覆盖清单、逐项消融与自身匹配标记。',
        '- `coverage.csv`：36 个配置的三分区与三种规模；`topdown.csv`／`topdown-deltas.csv`：全部共同指标和变化。'
        '`topdown-hierarchy.csv` 保留 24 个规模配置各 58 个层级节点，附近似／未计数标记；不假定每个打印值都已通过事件依赖有效性判断。',
        '- `unseen-functions.csv`：所有已解析未见函数、软件、执行脚本、周期及占比；`tool-gaps.csv`：各库组缺口。',
        '- `verification.json`：从原始函数行独立复算三分区、上下文守恒、Topdown 差值，以及最小解的第二种校验。',
        '- `analysis-build.json`：本轮脚本、输入与输出 SHA256；不修改原始采集或已有报告。', '',
        '采样丢块／丢样记录与符号不足仍按原证据保留。权重来自实际保留样本的 period，'
        '不按请求 49 Hz 倒推样本、不按样本个数估计 CPU 时间，也不补造丢样 period。', '']
    return '\n'.join(lines)


def function_contexts(case, function):
    counts = {}
    for r in case['contexts']:
        if Path(r['dso']).name==function['library'] and r['function']==function['function']:
            counts[r['script']] = counts.get(r['script'],0)+r['period']
    return '；'.join(s+' '+PCT(v/case['roi_period']) for s,v in sorted(counts.items(),key=lambda kv:-kv[1])[:3])


def minimum_label(answer):
    if answer['complete']:
        return str(answer['minimum_count'])+' 个'
    return '无法全覆盖；缺 '+str(len(answer['missing']))+' 个身份（可覆盖部分最少 '+str(answer['minimum_for_attainable'])+' 个配置）'


def essential(selection, result, removed):
    goal = selection['goals'][selection['primary_goal']]
    needed = {(r['library'],r['function']) for r in goal['required_functions']}
    others = set(selection['selected'])-{removed}
    covered = {method.key(f) for t in others for f in result['cases'][t]['functions']}
    return sorted(needed-covered)


def write_csv(path, rows):
    rows = list(rows)
    with path.open('w',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def save(folder,result,selection):
    folder = Path(folder)
    (folder/'analysis.md').write_text(report(result,selection))
    cases = result['cases']
    write_csv(folder/'coverage.csv', [dict(task=t,parent=c['parent'],format=c['format'],
        level='original' if t==c['parent'] else 'small' if t==result['groups'][c['parent']][0] else 'large',
        roi_period=c['roi_period'],roi_samples=c['roi_samples'],**{
            k:v for k,v in c['presence']['OPM+TLC'].items() if k!='not_observed_top20'},
        loops=c['source']['loops'],image_id=c['source']['image_id'])
        for t,c in cases.items()])
    write_csv(folder/'topdown.csv',[dict(task=t,**c['metrics'],
        points=c.get('source',{}).get('points'),idle_pct=c.get('source',{}).get('idle_pct'))
        for t,c in list(result['references'].items())+list(cases.items())])
    write_csv(folder/'topdown-deltas.csv',[dict(comparison=name,**d['metrics_delta'],
        bound_half_L1_pp=d['bound_total_variation_pp'],cosine_auxiliary=d['bound_cosine_auxiliary'],
        ipc_relative_change_pct=d['ipc_relative_change_pct']) for name,d in result['comparisons'].items()])
    write_csv(folder/'topdown-hierarchy.csv',[dict(task=t,path=node['path'],parent_path=node['parent_path'],
        raw_printed_value=node['value'],approximate=node['approximate'],
        event_dependency_validity='not inferred from printed value',
        capture_not_counted_markers=';'.join(c['source']['not_counted_markers']),
        evidence=c['source']['topdown_extract'],log_line=node['line'])
        for t,c in cases.items() if 'topdown_hierarchy' in c['source']
        for node in c['source']['topdown_hierarchy']])
    write_csv(folder/'tool-gaps.csv',[dict(task=t,**row) for t,c in cases.items()
        for row in c['hotspot_coverage']['unseen_by_tool']])
    write_csv(folder/'unseen-functions.csv',[dict(task=t,parent=c['parent'],**row,
        script_contexts=function_contexts(c,row)) for t,c in cases.items()
        for row in c['hotspot_coverage']['unseen_functions']])
    outputs = {p.name:method.sha(p) for p in sorted(folder.iterdir())
               if p.is_file() and p.name not in ('analysis-build.json',)}
    method.write(folder/'analysis-build.json',dict(
        schema='docops-unified-scaling-build-v1',
        source_sha256={str(p.relative_to(ROOT)):method.sha(p) for p in
            (ROOT/'analysis/docops/unified_scaling_analysis.py',Path(__file__).resolve(),
             ROOT/'analysis/docops/operation_comparison.py',ROOT/'analysis/docops/scaling_hotspot_comparison.py')},
        input_sha256=result['input_sha256'],outputs=outputs,
        formal_report_or_html_modified=False,workload_or_collector_run=False))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--analysis-dir',type=Path,required=True)
    args = p.parse_args()
    result = json.loads((args.analysis_dir/'comparison.json').read_text())
    selection = json.loads((args.analysis_dir/'selection.json').read_text())
    save(args.analysis_dir,result,selection)
    print(args.analysis_dir/'analysis.md')


if __name__=='__main__':
    main()
