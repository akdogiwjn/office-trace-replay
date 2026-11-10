"""Recompute supplementary case selection and render the Markdown scaling discussion.

Reads saved, qualified profiles only. No workloads, collectors or HTML publishing.
The original twelve cases remain the candidates for the formal supplement.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import operation_comparison as method

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = 'analysis/docops/processed/task-operation-expansion-20261104/comparison.json'
SCALING = 'analysis/docops/processed/all-format-scaling-20261106/comparison.json'
OUTPUT = 'analysis/docops/processed/scaling-selection-20261106'
THRESHOLD = .005
OPERATION_TOOLS = {'PNG', 'JPEG', 'ImageMagick', 'Poppler', 'LibreOffice·VCL', 'LibreOffice·OOXML'}
SELECTED = ('013', '021', '029')
GROUPS = {'Excel': ('014', '014-n1000', '014-n10000'),
          'PDF': ('037', '037-u5', '037-u20'),
          'Word': ('003', '003-u100', '003-u500'),
          'PPT': ('021', '021-g5', '021-g10')}


def gather():
    bindings = {path: method.sha(ROOT/path) for path in (ORIGINAL, SCALING)}
    original, scaling = [json.loads((ROOT/path).read_text()) for path in (ORIGINAL, SCALING)]
    build_path = str(Path(SCALING).with_name('analysis-build.json'))
    build = json.loads((ROOT/build_path).read_text())
    assert build['outputs']['comparison.json'] == bindings[SCALING]
    for path, digest in build['input_sha256'].items():
        assert method.sha(ROOT/path) == digest, path
    bindings[build_path] = method.sha(ROOT/build_path)
    references = original['baselines']
    old = {method.key(f) for c in references.values() for f in c['functions']}
    cases = dict(original['tasks'])
    for task, case in scaling['cases'].items():
        if task in cases:
            assert cases[task]['functions'] == case['functions']
            assert cases[task]['roi_period'] == case['roi_period']
        cases[task] = case
    assert len(cases) == 20
    candidate_sets = {t: {method.key(f) for f in c['functions']}-old for t, c in cases.items()}
    required, all_hot = {}, set()
    for task, case in cases.items():
        for f in case['functions']:
            identity = method.key(f)
            if identity in old or f['share_roi'] < THRESHOLD:
                continue
            all_hot.add(identity)
            tool, kind, meaning = method.unseen_function_type(f)
            if tool not in OPERATION_TOOLS:
                continue
            row = required.setdefault(identity, dict(library=f['library'], function=f['function'],
                tool=tool, type=kind, occurrences=[]))
            row['occurrences'].append(dict(task=task, period=f['period'], share_roi=f['share_roi']))
    official = {t: candidate_sets[t] for t in original['tasks']}
    assert len(required) == 34 and len(all_hot) == 93
    exact = method.minimum_function_cover(official, set(required))
    assert exact['minimum_count'] == 3 and exact['solutions'] == [list(SELECTED)]

    def evaluate(selected):
        identities = old | set().union(*(candidate_sets[t] for t in selected))
        missing = set(required)-identities
        targets = {}
        for task, case in cases.items():
            period = case['roi_period']
            resolved = sum(f['period'] for f in case['functions'])
            seen = sum(f['period'] for f in case['functions'] if method.key(f) in identities)
            unseen = resolved-seen
            unknown = period-resolved
            before = method.function_presence(references, case)['OPM+TLC']
            assert unknown == before['unresolved_period'] and unknown >= 0
            targets[task] = dict(selected_as_reference=task in selected, roi_period=period,
                observed_period=seen, not_observed_period=unseen, unresolved_period=unknown,
                observed_share_roi=seen/period, not_observed_share_roi=unseen/period,
                unresolved_share_roi=unknown/period,
                before_observed_share_roi=before['observed_share_roi'],
                before_not_observed_share_roi=before['not_observed_share_roi'])
        return dict(selected=list(selected), required_count=len(required),
            required_matched=len(required)-len(missing),
            required_missing=[required[k] for k in sorted(missing)], targets=targets)

    all_available = set().union(*official.values())
    missing_official = all_hot-all_available
    context_evidence = {}
    for task, case in scaling['cases'].items():
        tools = {method.key(f): method.unseen_function_type(f)[0] for f in case['functions']
                 if method.key(f) not in old}
        counts = Counter()
        for f in case['contexts']:
            tool = tools.get((Path(f['dso']).name, f['function']))
            if tool is not None:
                counts[(tool, f['script'])] += f['period']
        context_evidence[task] = [dict(tool=k[0], script=k[1], period=v,
            share_roi=v/case['roi_period']) for k,v in counts.most_common()]
    return dict(schema='scaling-operation-selection-v1', source_sha256=bindings,
        function_identity='DSO basename + full exact physical leaf symbol',
        method='Full target ROI cycles:u period retained. Selection uses identities, not matching weights.',
        target_cases=list(cases), original_candidate_tasks=list(official),
        hotspot_threshold_share_roi=THRESHOLD, operation_tools=sorted(OPERATION_TOOLS),
        selection_scope='Resolved previously unseen functions at >=0.5% in at least one of 20 cases, '
                        'in six explicitly identified image/page/object tool groups. '
                        'Not all unseen functions, not all task operations, not independent validation.',
        operation_hotspots=[required[k] for k in sorted(required)],
        minimum_operation_cover=exact,
        minimum_operation_cover_including_synthetic=method.minimum_function_cover(candidate_sets, set(required)),
        selected=evaluate(SELECTED),
        ablations={t: evaluate(tuple(x for x in SELECTED if x != t)) for t in SELECTED},
        all_hotspot_identity_count=len(all_hot),
        all_hotspots_missing_from_original_candidates=[dict(library=k[0], function=k[1]) for k in sorted(missing_official)],
        minimum_all_hotspot_cover_including_synthetic=method.minimum_function_cover(candidate_sets, all_hot),
        unmatched_tool_script_contexts=context_evidence,
        unknown_excluded_from_unseen=True, self_reference_flagged=True)


def load():
    selection = json.loads((ROOT/OUTPUT/'selection.json').read_text())
    for path, digest in selection['source_sha256'].items():
        if method.sha(ROOT/path) != digest:
            raise ValueError('Scaling publication input changed: '+path)
    return (json.loads((ROOT/ORIGINAL).read_text()),
            json.loads((ROOT/SCALING).read_text()), selection)


def pct(value):
    return '<0.01%' if 0 < value < .0001 else method.pct(value)


def section73(original, scaling, selection):
    cases = scaling['cases']
    table = method.table
    lines = ['### 7.3 旧用例的函数覆盖：规模复测与补充用例选择', '',
        '**先看结论：旧 OPM／TLC 体现了大量共同基础计算；扩大规模后，Excel／PDF 的覆盖权重明显提高，'
        '但 PNG 输出滤波与 PPT 图像处理等缺口仍然存在。** 本节按“初测发现差额→提出规模假设→扩大后复测→'
        '定位剩余函数→选择最少补充用例”展开。', '',
        '### 7.3.1 初测：旧两例覆盖了多少，差额在哪里', '',
        '旧 OPM 在固定 PDF 表单中填写字段，生成页面图片并缩放、检查；旧 TLC 加载、增强、保存大型工作簿，'
        '执行重算及缓存／CSV 验证。两例已经体现解释执行、对象管理、XML 解析、压缩／解压、页面渲染与图片处理。', '',
        '**表 7-4：十二项原始扩展任务的函数覆盖初测。** 合并旧 OPM＋TLC 的完整已解析函数清单，'
        '按“库文件名＋完整物理叶函数名”匹配；旧清单中的低频函数也计入。分母为目标任务完整 workflow ROI '
        '的用户态 `cycles:u` 样本 period。三部分合计约 100%；这是采样周期权重，既不是函数个数，也不是整轮 CPU 时间比例。', '',
        table(['新任务','旧清单已见函数权重','已解析但旧清单未见','未解析'],
            [[original['tasks'][t]['format']+' '+t,
              *[pct(original['function_presence'][t]['OPM+TLC'][k]) for k in
                ('observed_share_roi','not_observed_share_roi','unresolved_share_roi')]]
             for t in original['tasks']]), '',
        '**初测需要解释的是差额的来源。** 例如 PDF 037 已匹配 72.77%，Word 003 为 68.65%，'
        'PPT 021 为 46.59%。旧例仍体现相当多的相同函数，但不能直接把所有未匹配权重都解释为新的文档操作。'
        '本节以完整周期加权结果为主，Top-10／Top-20 排名与函数数量保留在实验数据记录。', '',
        '### 7.3.2 检验猜想：是否因为输入太小，辅助开销显得更重', '',
        '小任务也需要启动解释器、解析脚本、导入库和初始化组件；实际处理内容较少时，这些工作更容易占据前列。'
        '因此选取 Excel 014、PDF 037、Word 003、PPT 021，分别扩大记录、业务单元或页面数量，再按原规则比较。'
        '各变体按扩大后的业务内容实际重新构建、转换和渲染。', '',
        '**表 7-4A：规模复测后的旧函数覆盖权重。** 原十二项测量仍保留；右侧是独立的合成规模变体。', '',
        table(['任务','原始任务','扩大小档：规模／覆盖','扩大大档：规模／覆盖'],
            [[fmt+' '+a,pct(cases[a]['presence']['OPM+TLC']['observed_share_roi']),
              label1+'／'+pct(cases[b]['presence']['OPM+TLC']['observed_share_roi']),
              label2+'／'+pct(cases[c]['presence']['OPM+TLC']['observed_share_roi'])]
             for fmt,(a,b,c) in GROUPS.items()
             for label1,label2 in [dict(Excel=('1000行，81页预览','10000行，753页预览'),
                  PDF=('25页','100页'),Word=('100单元，104页','500单元，504页'),
                  PPT=('40页','80页'))[fmt]]]), '',
        '- **Excel／PDF 明显改善。** 大档分别达到 91.82%／86.72%。PDF 037 中未匹配 Python 函数从 '
        '16.17% 降至 0.77%；Word 003 中从 6.82% 降至 2.65%。这些变化支持部分初测差额与小输入下辅助开销占比高有关。',
        '- **Word 的改善有限，也不是越大覆盖越高。** 100 单元为 74.59%，500 单元回到 71.58%；'
        '后者 PNG 滤波与校验器字符串搜索的权重上升。',
        '- **PPT 的主要缺口没有被放大消除。** 40／80 页分别为 49.65%／50.44%，'
        '仍有约一半周期对应旧清单未见或未解析函数。', '',
        '规模变体同时包含业务数据和脚本参数化，Word 还采用了已核验的 XML 校验器优化；'
        '因此本实验用于观察规模敏感性，不把全部变化都归因于体积。各规模每种采集模式仅有一次独立采集，'
        '小档 Word／PDF 各含三轮回放，其余规模各一轮，尚不据此估算独立重复波动。', '',
        '### 7.3.3 确认剩余缺口：什么函数、什么操作、为什么旧例未匹配', '',
        '**先区分三种容易混淆的情况：**', '',
        '1. **做的事类似，但换了工具或内部实现。** 旧例已经缩放图片，新任务改用 ImageMagick；'
        '旧例已经生成图片，新预览链进入 libpng 的 PNG 滤波。它们说明旧例体现过这类工作，'
        '但没有体现这里观察到的具体软件函数。',
        '2. **新任务确实多做了一件事。** 把多页缩略图排列、合成为一张联系表，比逐页生成图片多了拼图操作；'
        '为幻灯片表格应用样式、组织对象属性，也增加了旧表单与工作簿任务没有直接体现的操作。'
        '联系表制作同时可能使用 ImageMagick 缩图，所以一个步骤可以既增加操作，又更换实现。',
        '3. **处理与检查程序不同。** 新校验器搜索文档中是否残留私人信息，会执行字符串搜索；'
        '不同脚本启动时也会解析不同源码。这些 CPU 权重全部保留，但应解释为相应的解析或检查工作，'
        '不能仅凭函数没匹配，就命名成新的 Word 排版或 PDF 编辑机制。', '',
        '**表 7-5：复测后仍有权重的明确操作路径，以及原任务中另有依据的对象路径。** '
        '单函数与工具内未匹配函数合计分别标明；均以所在任务完整 ROI 为分母，不跨任务相加，也不是操作阶段的独立计时。', '',
        table(['路径与代表函数','什么操作带来','实测未匹配权重','旧例为何没有匹配到'],[
            ['PNG 滤波：`png_write_find_filter`（libpng）',
             'pdftoppm 将页面输出为 PNG，选择每行的滤波方式以利压缩',
             '单函数：Word 003-u500 22.10%；PDF 037-u20 11.22%；Excel 014-n10000 4.12%',
             '旧例已有图片处理；旧函数清单没有观察到这条具体 PNG 滤波实现'],
            ['图片缩放：`HorizontalFilter`／`VerticalFilter`（ImageMagick）',
             '缩略图／联系表制作中的缩放；拼图还包含排列与合成操作',
             'PPT 021-g10：该工具未匹配函数合计 11.51%',
             '旧例主要使用 Pillow 缩放；新链进入 ImageMagick，且增加 montage 拼图'],
            ['JPEG 编／解码：`encode_mcu_gather` 等（libjpeg）',
             '页面预览和联系表制作时读写 JPEG；encode_mcu_gather 实际记录于 montage',
             'PPT 021-g10：未匹配函数合计 7.45%（montage 4.81%；pdftoppm 2.64%）',
             '预览图片的编码实现路径不同，不能因旧例也输出图片就视为具体函数相同'],
            ['位图缩放／页面绘制：`ImplScaleConvolution*`、`Splash::scaleImage*`',
             '幻灯片转 PDF 与页面图片渲染中的位图、像素处理',
             'PPT 021-g10：VCL 未匹配函数 8.24%；Poppler 未匹配函数 7.92%',
             '旧例已有转换和渲染，但文档对象与内容不同，进入了不同的内部图形子路径'],
            ['幻灯片表格样式：`applyTableStylePart`、`PropertyMap::fillSequences`',
             '应用表格样式并组织对象属性',
             '原始 PPT 029：明确 OOXML 对象／样式路径合计 4.88%（本项未做规模复测）',
             '旧 PDF 表单与 XLSX 工作簿没有直接体现这条幻灯片对象路径']]), '',
        '**各函数对应的工作不同。** PNG 滤波与 JPEG 编／解码用于图片读写；'
        'ImageMagick 滤波用于图片处理，montage 才是拼图工具；VCL／Poppler 承担位图处理和页面绘制。'
        '它们可以出现在同一交付链里，却是不同的软件工作。', '',
        '**辅助差异也没有删除。** 例如 Word 003-u500 的 `ucs2lib__two_way` 占约 2.43%，'
        '其中约 2.42% 记录于 `validate_public_packet_variant.py`，属于校验器字符串搜索。'
        'Word 中剩余少量 lxml 未解析符号继续单列。完整未匹配函数、公共框架与运行时权重见数据记录。', '',
        '### 7.3.4 最少补哪些用例：先定义补什么，再验证是否能删减', '',
        '**以补齐主要、可定位的操作函数为目标，保留旧 OPM／TLC 后，最少补三例：Excel 013、PPT 021、PPT 029。** '
        '这次结论是在规模复测后重新计算，不再直接沿用初测的 Top-20 数量。', '',
        '**“主要操作函数”的具体范围：** 在十二项原任务＋八项规模变体共二十个测量配置中，'
        '任一配置达到原先使用的 **0.5% ROI 热点门槛**、旧清单未见，且可按软件归属定位到 '
        'PNG、JPEG、ImageMagick、Poppler、LibreOffice VCL 或 OOXML 对象路径的函数，共 **34 个去重身份**。'
        '门槛只用于补例选型；前面所有覆盖比例仍保留完整 ROI、全部长尾和未知权重。'
        '解释器、字符串搜索及公共框架仍统计，但不把它们直接定义为新增文档操作。', '',
        '**表 7-5A：在原十二项真实任务候选中，为什么三例各有贡献。** '
        '按组合大小穷举候选后，覆盖这 34 个身份最少需要三例，且只有下列这一套组合。', '',
        table(['补充用例','主要补充操作','删去该例后，34个目标还缺多少','缺失例子'],[
            ['Excel 013：投标评审发布','工作簿转 PDF、PNG 预览与联系表拼图',
             str(len(selection['ablations']['013']['required_missing']))+' 个',
             '`png_write_find_filter`、`png_read_filter_row_up`、ImageMagick PNG／像素读取路径'],
            ['PPT 021：庇护所无障碍整改','幻灯片预览、位图缩放、JPEG 与页面处理',
             str(len(selection['ablations']['021']['required_missing']))+' 个',
             'JPEG 编码／解码、Poppler 图像缩放与裁剪子路径'],
            ['PPT 029：季度业务回顾发布','幻灯片表格样式与对象属性组织',
             str(len(selection['ablations']['029']['required_missing']))+' 个',
             '`applyTableStylePart`（029 内约 2.00%）']]), '',
        '**加入这三例后，其他规模变体的差额也缩小。** '
        '下面只列未被直接选作参考的四个大档，分母与未知权重保持不变。', '',
        table(['大档目标','仅旧两例：已解析未匹配','旧两例＋三例：仍未匹配','未解析（不变）'],
            [[t,pct(selection['selected']['targets'][t]['before_not_observed_share_roi']),
              pct(selection['selected']['targets'][t]['not_observed_share_roi']),
              pct(selection['selected']['targets'][t]['unresolved_share_roi'])]
             for t in ('014-n10000','037-u20','003-u500','021-g10')]), '',
        'PPT 021-g10 是入选原始 021 的同父任务规模变体，其匹配用于检查扩大后路径，'
        '不能当作独立跨任务验证。013／021／029 自身匹配自身的比例不作为选型效果证据。', '',
        '**三例最少的结论有明确边界：它针对上述 34 个主要操作函数。** '
        '它不等于覆盖全部未匹配函数，也不等于覆盖全部 Word／PPT 功能。'
        '包含运行时和公共框架的全部热点集合、最少组合与剩余函数另列于数据记录。'
        '本报告按明确操作增量选型，不为收齐长尾或检查程序函数而自动扩充正式基准。', '',
        '### 7.3.5 判断：旧负载保留，补例针对剩余明确操作', '',
        '1. **旧两例仍有基础计算代表性。** 大档 Excel／PDF／Word 的旧函数覆盖权重约为 '
        '92%／87%／72%；部分初测差额确实随内容增多而下降，不能以最初前十函数重合少就否定基础负载。',
        '2. **规模因素不能解释全部缺口。** PNG 输出滤波与 PPT 图像路径在两档中都观察到；'
        '对象样式另有原任务证据，值得分别补充。',
        '3. **函数热点目标下采用“旧两例＋三例”。** 013 补 PNG／拼图链，021 补具体图像／页面处理，'
        '029 补幻灯片对象样式。无需仅因文件格式不同就额外再选一项 Word；'
        '若研究目标进一步要求完整 Word 编辑、分页或任务成功率，则需另行按操作设计实验。', '',
        '[规模复测与补例完整数据](experimental-results.md#十规模复测与补充用例选择)保留全部分区、'
        '34 个目标函数、删例检查及候选组合；[统一规模分析](../'+str(Path(SCALING).with_name('analysis.md'))+
        ')保留各执行脚本和 Topdown 对照。', '']
    return '\n'.join(lines)


def section76():
    return '\n'.join(['### 7.6 最终判断：旧负载的代表性与最少补充方案', '',
        '**结论：保留旧 OPM／TLC 作为基础；以主要函数热点为目标，最少增加 Excel 013、PPT 021、PPT 029。** '
        '规模复测提高了对旧负载基础代表性的认识，也确认了需要补充的具体操作路径。', '',
        '- **跨行业输入实验的结论保持不变。** 原七例在相近任务形态下延续主要热点；'
        '本次进一步检验改变操作后，旧函数能体现多少。',
        '- **部分初测低覆盖与规模有关。** 放大后 Excel 014 和 PDF 037 的旧函数覆盖分别达到 '
        '91.82%／86.72%，Python 等辅助路径权重下降；Word 003 为 71.58%，改善有限。',
        '- **仍然存在有价值的具体缺口。** 旧例已经输出、缩放图片，但新链出现 libpng 滤波、'
        'ImageMagick、JPEG 与 LibreOffice 位图处理；联系表拼图和幻灯片表格样式又增加了实际操作。'
        'PPT 021 大档仍有 47.45% 已解析周期未在旧清单匹配，不能仅用小输入解释。',
        '- **最少三例针对已说明的目标。** 在二十个配置中筛出的 34 个主要操作函数，'
        '从原十二项真实任务中穷举，唯一最少组合为 013＋021＋029；删去任一例都留有目标缺口。'
        '这不是全部函数或全部办公操作的最小集合，详见 7.3.4。',
        '- **函数覆盖与 CPU 瓶颈分别判断。** 7.4／7.5 保留原十二项的 Topdown 对照与过程曲线，'
        '规模变体九项指标另见完整数据记录；函数清单重合不能代替 IPC、四项 Bound 和实际工作量比较。', '',
        '正式任务集合本轮不自动变更。规模实验各模式只有一次独立采集，'
        '后续若将三例纳入正式基准，应对候选开展独立重复，确认热点权重和运行波动。', '',
        '[原十二项完整记录](experimental-results.md#九扩展任务操作十二项-docops-完整记录)与'
        '[规模复测完整记录](experimental-results.md#十规模复测与补充用例选择)分别保留原始批次和变体证据，'
        '不合并为同一组重复实验。', ''])


def revise_assessment(text):
    # Keep the historical 20-case detail/build above available for its original
    # record; current assessment publication uses all 36 measured configurations
    # and distinguishes exact function matching from operation-category advice.
    from unified_scaling_sections import revise_assessment as revise_current
    return revise_current(text)


def detail(selection, scaling):
    table = method.table
    rows = scaling['cases']
    lines = ['## 十、规模复测与补充用例选择', '',
        '本节为 7.3 的补充数据。第九节的十二项原始配置及其 Top-20 集合计算仍保留原批次口径；'
        '本节加入八项合成规模变体，重新按明确操作热点选型。原始十二项、规模变体、独立采集次数分别记录。', '',
        '### 10.1 输入规模、重复次数与完整周期分区', '',
        '旧 OPM／TLC 是各五次独立重复的函数清单并集；原始 DocOps 十二项各一次采集内十轮回放。'
        '八项规模变体各模式一次独立采集；003-u100／037-u5 内含三轮，其余一轮。'
        'perf 与 DevKit 分开运行。覆盖分母是各目标 workflow ROI 的 cycles:u period，不是 CPU 秒。', '',
        table(['配置','ROI period','ROI 样本','回放轮数','旧函数已见','已解析未见','未解析'],[
            [t,r['roi_period'],r['roi_samples'],r['source']['replay_loops'],
             *[pct(r['presence']['OPM+TLC'][k]) for k in
               ('observed_share_roi','not_observed_share_roi','unresolved_share_roi')]]
            for t,r in rows.items()]), '',
        'Word 100／500 单元实际排版 104／504 页；PDF 037 为 25／100 页；Excel 两档输出 '
        '81／753 页 PDF 与 PNG；PPT 两档 40／80 页并生成 5／10 张联系表。'
        '规模变体为合成业务内容和参数化脚本，不标为新增 Agent 轨迹。'
        'Word XML 校验器只转小写一次的修复也保留在身份记录中，不能将其效果全部当作规模作用。', '',
        '### 10.2 补例目标、门槛与精确最少集合', '',
        '目标：在二十个配置中至少一次达到完整 ROI 0.5%，旧 OPM＋TLC 未见，'
        '软件组属于 PNG／JPEG／ImageMagick／Poppler／LibreOffice VCL／LibreOffice OOXML 的已解析叶函数。'
        '六组对应已定位的图片、页面、对象操作。其他运行时、文本、XML、公共框架及未知权重仍在完整分区中保留。', '',
        '目标共 '+str(len(selection['operation_hotspots']))+' 个去重身份。候选为原十二项任务的完整函数清单，'
        '不限制候选中的函数必须达到 0.5%。枚举全部子集，最少三例，唯一组合为 013、021、029。'
        '若允许八个合成规模变体也作为候选，最少仍为三例，但有以下并列组合：', '',
        table(['组合'],[['、'.join(x)] for x in selection['minimum_operation_cover_including_synthetic']['solutions']]), '',
        '**34 个目标的完整库名和函数身份如下。** 表内函数仅显示时省略参数；selection.json 保留完整符号。', '',
        table(['软件组','库文件名','完整身份的函数名（显示简写）','达到门槛的配置／权重'],[
            [f['tool'],f['library'],'`'+method.top20_display_name(f['function'])+'`',
             '；'.join(x['task']+' '+pct(x['share_roi']) for x in f['occurrences'])]
            for f in selection['operation_hotspots']]), '',
        '### 10.3 加例后的完整分区与删例检查', '',
        'selected_as_reference=True 的三项匹配自身，不作为独立验证。'
        '021-g5／g10 与入选原始 021 同父任务，属于相关规模配置。所有目标未知 period 不变。', '',
        table(['目标','选为参考','仅旧例：未匹配','旧例＋三例：未匹配','未解析'],[
            [t,str(r['selected_as_reference']),pct(r['before_not_observed_share_roi']),
             pct(r['not_observed_share_roi']),pct(r['unresolved_share_roi'])]
            for t,r in selection['selected']['targets'].items()]), '']
    for task, removal in selection['ablations'].items():
        lines += ['**删去 '+task+'：保留 '+ '＋'.join(removal['selected'])+'，目标剩 '+
            str(len(removal['required_missing']))+' 个未匹配。**', '',
            table(['软件组','库','未匹配函数'],[[f['tool'],f['library'],
                '`'+method.top20_display_name(f['function'])+'`'] for f in removal['required_missing']]), '']
    all_hot = selection['minimum_all_hotspot_cover_including_synthetic']
    lines += ['**如果不区分操作与运行支撑：** 全部二十个配置中达到 0.5% 的旧例未见函数共 '+
        str(selection['all_hotspot_identity_count'])+' 个。允许全部配置作为候选，严格覆盖该集合最少需 '+
        str(all_hot['minimum_count'])+' 个配置，组合如下；它与正文“34 个可定位操作热点”的目标不同。', '',
        table(['全部热点最少组合'],[['、'.join(x)] for x in all_hot['solutions']]), '',
        '原十二项候选无法覆盖全部 93 个身份，缺少 '+
        '；'.join('`'+x['library']+' / '+x['function']+'`' for x in selection['all_hotspots_missing_from_original_candidates'])+
        '。不将新增变体的函数身份倒填成原任务已经执行。', '',
        '### 10.4 Topdown 与采集质量', '',
        '下面规模变体取 DevKit Report-ALL，原任务取已保存批次累计值。四个顶层 Bound 与子项分开理解。', '',
        table(['配置','IPC','Bad Spec','Frontend','Backend','Retiring','Core','Memory','Fetch Latency','Fetch BW'],[
            [t]+[f"{r['metrics'][k]:.2f}" for k in method.METRICS] for t,r in rows.items()]), '',
        'DevKit 统计 CPU 0–7 的包络，控制器位于 CPU 9，含初始读数、步间、轮间及尾部间隙；'
        '没有精确 PID／ROI 事件裁剪。perf 采用 workflow 区间并集，二者分母不同。'
        '全层级 58 节点及原始 PMU 事件另有保存；带 `<not counted>` 的依赖未证明有效时，不填零加入相似度。', '',
        'Word／PDF 已使用 build-id 匹配符号离线恢复，原样本数、period、DSO 权重不变；'
        '少量 Word lxml 未解析权重保留。Excel／PPT 的原丢样记录保留，未推算丢失 period 或补样。'
        'PDF “每个分配 CPU 的平均样本率”约 6/s 不等于任务只有 6Hz：两档总样本／workflow 秒约 '
        '47.7／48.1，与请求 49Hz 接近。', '',
        '### 10.5 证据与离线重算入口', '',
        '- [统一规模分析](../'+str(Path(SCALING).with_name('analysis.md'))+')／[机器结果](../'+SCALING+')。',
        '- [补例选择与完整身份](../'+OUTPUT+'/selection.json)／[构建绑定](../'+OUTPUT+'/analysis-build.json)。',
        '- Excel／PPT：`results/docops/scaling-performance-20261105T114539Z/`，'
        '修正提取 `scaling-performance-recheck-20261105T124311Z/`，符号恢复 `scaling-symbol-enrich-20261105T132725Z/`。',
        '- Word／PDF：`results/docops/scaling-word-pdf-performance-20261105T170501Z-3865aae0/`。', '',
        '```bash', 'python3 -B analysis/docops/scaling_report_sections.py --build',
        'python3 -B analysis/docops/operation_comparison.py --update --publish', '```', '',
        '两条命令只读取既有测量与派生数据，重建 Markdown 和来源绑定，不运行 workload、采集器或 HTML 生成器。', '']
    return '\n'.join(lines)


def append_detail(text):
    _, scaling, selection = load()
    # Preserve the original twelve-case record and its historical target universe.
    return text.rstrip()+'\n\n'+detail(selection, scaling)


def build():
    result = gather()
    output = ROOT/OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    method.write(output/'selection.json', result)
    original, scaling, result = load()
    (output/'assessment-7.3.md').write_text(section73(original, scaling, result))
    (output/'assessment-7.6.md').write_text(section76())
    (output/'experiment-section.md').write_text(detail(result, scaling))
    method.write(output/'analysis-build.json', dict(source_sha256={
        str(Path(__file__).resolve().relative_to(ROOT)):method.sha(__file__),
        str(Path(method.__file__).resolve().relative_to(ROOT)):method.sha(method.__file__)},
        input_sha256=result['source_sha256'], measurement_rerun=False,
        output_sha256={f.name:method.sha(f) for f in output.iterdir()
                       if f.is_file() and f.name!='analysis-build.json'}))
    print(output)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true', required=True)
    parser.parse_args()
    build()
