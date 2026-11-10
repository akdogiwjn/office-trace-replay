# 十二组任务的原始→小档→大档统一比较

**先看判断：旧 OPM＋TLC 体现了相当多共同基础计算，但不能覆盖所有新增工具路径。** 12 组中有 11 组的大档旧函数覆盖权重高于原始任务，其中 8 组从小档到大档继续上升。Excel 013／014、PDF 031／037 的覆盖改善明显；ImageMagick 拼图、PPT 图形／对象处理以及 PNG 输出滤波等差额没有随放大消失。

本次只对已有证据离线计算。范围为旧 OPM／TLC、12 个原始 DocOps 任务和 24 个合成规模变体；原始采集与历史分析文件均保留，未重跑任务、未重采 perf／DevKit、未更新正式报告或 HTML。

## 1. 先把“覆盖”说清楚

- **匹配对象：** 合并旧 OPM＋TLC 的完整已解析物理叶函数清单，包含低频函数，按“库文件名＋完整函数名”精确匹配，不合并克隆名或模糊相似函数。
- **统计权重：** 目标任务完整 workflow ROI 内用户态 `cycles:u` 样本的 period。“已见＋已解析未见＋未解析”合计 100%；不是函数个数，也不是整轮 CPU 时间比例。
- **解释规则：** 未见表示旧采样清单没有这个具体身份，不等于从未执行过、也不必然是新计算机制。未解析权重单列，既不算已见也不算未见。
- **比较单位：** 每个配置单独作为分母，不把 36 个配置的 period 混合后称为某个总体覆盖率。旧基准为五次独立采集；父任务一次采集含十轮；规模任务每种模式一次采集，003-u100／037-u5 各含三轮，其余一轮。

## 2. 十二组原始→小档→大档：覆盖是否改善

下表只展示旧函数已见权重。右侧差额还包含未解析部分，不能直接全称为新增函数。

| 格式／父任务 | 原始 | 小档 | 小档已见 | 大档 | 大档已见 | 原始→大档 pp |
|---|---|---|---|---|---|---|
| Word 001 | 71.94% | 001-u100（100条记录） | 71.07% | 001-u500（500条记录） | 75.56% | +3.62 |
| Word 003 | 68.65% | 003-u100（100业务单元） | 74.59% | 003-u500（500业务单元） | 71.58% | +2.92 |
| Word 009 | 65.01% | 009-u100（100事件） | 68.02% | 009-u500（500事件） | 71.59% | +6.59 |
| Excel 013 | 59.16% | 013-v100（100供应商） | 68.80% | 013-v1000（1000供应商） | 93.25% | +34.09 |
| Excel 014 | 66.17% | 014-n1000（1000有效申请） | 88.01% | 014-n10000（10000有效申请） | 91.82% | +25.65 |
| Excel 016 | 56.25% | 016-u100（100业务单元，400模型行） | 72.39% | 016-u500（500业务单元，2000模型行） | 80.03% | +23.78 |
| PPT 021 | 46.59% | 021-g5（5地区，40页） | 49.65% | 021-g10（10地区，80页） | 50.44% | +3.85 |
| PPT 026 | 59.39% | 026-u5（5业务单元，45页） | 65.01% | 026-u10（10业务单元，90页） | 63.00% | +3.61 |
| PPT 029 | 55.51% | 029-u5（5业务单元，41页） | 59.74% | 029-u10（10业务单元，81页） | 46.29% | -9.22 |
| PDF 031 | 79.15% | 031-u5（5组，25页） | 89.29% | 031-u20（20组，100页） | 86.49% | +7.34 |
| PDF 037 | 72.77% | 037-u5（5组，25页） | 83.39% | 037-u20（20组，100页） | 86.72% | +13.95 |
| PDF pdfwf005 | 45.41% | pdfwf005-u5（5组，30输出页） | 45.99% | pdfwf005-u20（20组，120输出页） | 48.94% | +3.53 |

**如何理解这张表：**

1. **Excel 013／014 和 PDF 031／037：覆盖提高，但原因不同。** 014／031／037 主要是页面输出、压缩和渲染权重上升，较低覆盖的脚本／组件开销被摊薄；013 大档则转为 Python 构建主导（见第 3.4 节），不能归入同一种解释。结果支持“部分小输入使辅助开销更显眼”，但不支持把全部覆盖提高都归因于固定成本摊薄。
2. **Word 001／003／009：覆盖有限改善，PNG 与校验差额仍在。** 003 大档的 `png_write_find_filter` 单项约 22.10%；旧例已有生成图片，缺少的是此处具体 PNG 输出滤波函数。
3. **pdfwf005 和 PPT：主要缺口持续存在。** pdfwf005 大档仍约一半周期未匹配；021／026／029 的大档也没有全部接近旧例，029 甚至下降。不能据此沿用“只要放大就能解决”的解释。
4. **016：重算是已有操作，具体 Calc 子路径仍有差额。** 大档覆盖提高，但公式树／单元格管理等函数仍未见。它不是首次引入重算，也不能仅凭同为重算就认为所有函数均已覆盖。

规模变体有登记的脚本参数化与校验修复：包括 003 的 XML 检查优化、009 的实际目录页码稳定、016 的完整异常表／四期图表／全量场景校验、029 的八类页恢复等。016／029 保留只渲染首页，其他任务按各自冻结规则渲染；因此本表是规模敏感性观察，不是只改变文件字节数的严格因果试验。

## 3. 大档剩余差额：有多少，属于什么工具

| 大档 | 旧函数已见 | 已解析未见 | 未解析 | 未见函数的前三个工具分组 |
|---|---|---|---|---|
| 001-u500 | 75.56% | 21.04% | 3.40% | PNG 10.28%；Python 4.70%；LibreOffice·其他组件 1.93% |
| 003-u500 | 71.58% | 26.94% | 1.48% | PNG 22.12%；Python 2.65%；LibreOffice·其他组件 0.73% |
| 009-u500 | 71.59% | 24.95% | 3.46% | LibreOffice·其他组件 9.64%；LibreOffice·Writer 5.40%；PNG 4.35% |
| 013-v1000 | 93.25% | 6.73% | 0.02% | Python 3.82%；ImageMagick 1.64%；PNG 1.13% |
| 014-n10000 | 91.82% | 7.12% | 1.05% | PNG 4.12%；LibreOffice·其他组件 0.98%；Python 0.67% |
| 016-u500 | 80.03% | 19.42% | 0.55% | LibreOffice·Calc 6.80%；LibreOffice·其他组件 5.85%；Python 2.70% |
| 021-g10 | 50.44% | 47.45% | 2.11% | ImageMagick 11.51%；LibreOffice·VCL 8.98%；Poppler 7.92% |
| 026-u10 | 63.00% | 35.13% | 1.87% | Poppler 10.90%；LibreOffice·其他组件 6.32%；LibreOffice·VCL 6.11% |
| 029-u10 | 46.29% | 46.86% | 6.84% | LibreOffice·其他组件 21.07%；LibreOffice·VCL 7.36%；LibreOffice·文本样式 5.82% |
| 031-u20 | 86.49% | 13.51% | <0.01% | PNG 10.98%；Python 1.73%；libfreetype 0.49% |
| 037-u20 | 86.72% | 13.28% | <0.01% | PNG 11.22%；Python 0.77%；libfreetype 0.68% |
| pdfwf005-u20 | 48.94% | 50.64% | 0.43% | ImageMagick 33.11%；PNG 16.00%；Python 0.83% |

工具分组仍以完整 ROI 为分母；例如“PNG 22%”不是指 PNG 内部的 22%。没有把 Python／Office 公共框架差额从分母删除，也没有把它们全部算成新的文档机制。

本轮细分了此前落入 Office 兜底组的已知专属函数：例如 Sc 开头的 Calc 单元格／属性函数、PPT 占位符／页名导入、VCL 内图像编码，以及文本样式／图形几何。工具分组据此比上轮更细；旧函数已见权重、未见总权重及完整函数身份匹配不受分组改变影响。普通 UNO／C++ 容器仍留在公共框架组，完整规则见分析代码的 `classify_function()`。

### 3.1 同样是未见，实际含义有三种

| 情况 | 具体例子 | 旧例覆盖了什么／本次还缺什么 |
|---|---|---|
| 已有工作，换了实现或子路径 | PNG 滤波；ImageMagick 缩放；Poppler 图像缩放 | 旧例已有图片输出、缩放和页面渲染；缺的是这里的 libpng／ImageMagick／Poppler 具体函数 |
| 扩展了实际操作 | 多页联系表拼图；幻灯片表格／形状样式 | 多张预览排列合成，以及 PPT 对象样式路径；不能只用“都是图片／都是 XML”替代 |
| 辅助执行或尚待细分 | Python 源码解析、正则搜索；UNO／对象属性／公共容器 | 统计保留，需结合脚本归属说明；不直接称为新的文档编辑机制，也不假定全部无关 |

### 3.2 每组大档最突出的具体未见函数

列出每组前三项；函数全名、全部低频函数及其各规模出现权重见 `unseen-functions.csv`。“执行脚本”来自采样的进程／脚本关联；含既有脚本身份推断或未归因线程时保留原标记，不把这列当作逐操作的精确计时。

**Word 001-u500：受控文档发布修复**

| 工具／库 | 函数 | 占完整 ROI | 执行脚本 |
|---|---|---|---|
| PNG / libpng16.so.16.40.0 | `png_write_find_filter` | 10.28% | pdftoppm 10.28% |
| Python / libpython3.12.so.1.0 | `sre_ucs2_match` | 3.50% | validate_controlled_document_release_variant.py 3.50% |
| Python / libpython3.12.so.1.0 | `Py_UNICODE_ISALNUM.lto_priv.0` | 0.54% | validate_controlled_document_release_variant.py 0.54% |

**Word 003-u500：公开记录元数据清理**

| 工具／库 | 函数 | 占完整 ROI | 执行脚本 |
|---|---|---|---|
| PNG / libpng16.so.16.40.0 | `png_write_find_filter` | 22.10% | pdftoppm 22.10% |
| Python / libpython3.12.so.1.0 | `ucs2lib__two_way` | 2.43% | validate_public_packet_variant.py 2.42%；build_public_packet_variant.py 0.01% |
| LibreOffice·Writer / libswlo.so | `SwpHints::GetFirstPosSortedByWhichAndStart(unsigned short) const` | 0.24% | soffice.bin 0.24% |

**Word 009-u500：事件手册发布**

| 工具／库 | 函数 | 占完整 ROI | 执行脚本 |
|---|---|---|---|
| PNG / libpng16.so.16.40.0 | `png_write_find_filter` | 4.35% | pdftoppm 4.35% |
| LibreOffice·其他组件 / libsvllo.so | `SfxItemPropertyMap::getByName(std::basic_string_view<char16_t, std::char_traits<char16_t> >) const` | 1.07% | soffice.bin 1.07% |
| Python / libpython3.12.so.1.0 | `sre_ucs2_match` | 0.83% | validate_incident_manual_variant.py 0.83% |

**Excel 013-v1000：采购投标评审发布**

| 工具／库 | 函数 | 占完整 ROI | 执行脚本 |
|---|---|---|---|
| PNG / libpng16.so.16.40.0 | `png_write_find_filter` | 0.97% | pdftoppm 0.61%；montage 0.36% |
| ImageMagick / libMagickCore-7.Q16HDRI.so.10.0.2 | `HorizontalFilter._omp_fn.0` | 0.87% | montage 0.87% |
| ImageMagick / libMagickCore-7.Q16HDRI.so.10.0.2 | `VerticalFilter._omp_fn.0` | 0.47% | montage 0.47% |

**Excel 014-n10000：灾害补助公开发布**

| 工具／库 | 函数 | 占完整 ROI | 执行脚本 |
|---|---|---|---|
| PNG / libpng16.so.16.40.0 | `png_write_find_filter` | 4.12% | pdftoppm 4.12% |
| LibreOffice·Calc / libsclo.so | `ScHorizontalAttrIterator::InitForNextRow(bool)` | 0.12% | soffice.bin 0.12% |
| LibreOffice·其他组件 / libuno_sal.so.3 | `rtl_math_approxEqual` | 0.10% | soffice.bin 0.10% |

**Excel 016-u500：预测模型情景级联**

| 工具／库 | 函数 | 占完整 ROI | 执行脚本 |
|---|---|---|---|
| LibreOffice·Calc / libsclo.so | `ScHorizontalAttrIterator::InitForNextRow(bool)` | 1.66% | soffice.bin 1.66% |
| LibreOffice·Calc / libsclo.so | `ScDocument::RemoveFromFormulaTree(ScFormulaCell*)` | 1.46% | soffice.bin 1.46% |
| LibreOffice·其他组件 / libtllo.so | `toRational(int, int)` | 0.85% | soffice.bin 0.85% |

**PPT 021-g10：庇护所无障碍整改**

| 工具／库 | 函数 | 占完整 ROI | 执行脚本 |
|---|---|---|---|
| ImageMagick / libMagickCore-7.Q16HDRI.so.10.0.2 | `VerticalFilter._omp_fn.0` | 7.62% | montage 7.62% |
| ImageMagick / libMagickCore-7.Q16HDRI.so.10.0.2 | `HorizontalFilter._omp_fn.0` | 3.38% | montage 3.38% |
| JPEG / libjpeg.so.62.4.0 | `encode_mcu_gather` | 3.16% | montage 3.16% |

**PPT 026-u10：气候披露图表重建**

| 工具／库 | 函数 | 占完整 ROI | 执行脚本 |
|---|---|---|---|
| Poppler / libpoppler.so.133.0.0 | `expandRow(unsigned char*, unsigned char*, int, int, int)` | 3.06% | pdftoppm 3.06% |
| Poppler / libpoppler.so.133.0.0 | `Splash::scaleImageYdownXdown(bool (*)(void*, unsigned char*, unsigned char*), void*, SplashColorMode, int, bo…` | 1.84% | pdftoppm 1.84% |
| LibreOffice·VCL / libvcllo.so | `void (anonymous namespace)::stackBlurVertical<(anonymous namespace)::SumFunction8>((anonymous namespace)::Blu…` | 1.54% | unknown:thread-pool 1.51%；soffice.bin 0.02% |

**PPT 029-u10：季度业务回顾发布**

| 工具／库 | 函数 | 占完整 ROI | 执行脚本 |
|---|---|---|---|
| LibreOffice·其他组件 / libsvllo.so | `SfxItemSet::checkAddPoolRegistration(SfxPoolItem const*)` | 2.37% | soffice.bin 2.37% |
| LibreOffice·VCL / libvcllo.so | `void (anonymous namespace)::stackBlurVertical<(anonymous namespace)::SumFunction8>((anonymous namespace)::Blu…` | 1.95% | unknown:thread-pool 1.91%；soffice.bin 0.04% |
| LibreOffice·VCL / libvcllo.so | `void (anonymous namespace)::stackBlurHorizontal<(anonymous namespace)::SumFunction8>((anonymous namespace)::B…` | 1.50% | unknown:thread-pool 1.50% |

**PDF 031-u20：听证材料包扁平化发布**

| 工具／库 | 函数 | 占完整 ROI | 执行脚本 |
|---|---|---|---|
| PNG / libpng16.so.16.40.0 | `png_write_find_filter` | 10.89% | pdftoppm 10.89% |
| Python / libpython3.12.so.1.0 | `code_hash` | 1.17% | build_public_packet_variant.py 1.09%；validate_public_packet_variant.py 0.08% |
| libfreetype / libfreetype.so.6.20.1 | `cf2_hintmap_insertHint` | 0.08% | pdftoppm 0.08% |

**PDF 037-u20：公交绕行材料修复**

| 工具／库 | 函数 | 占完整 ROI | 执行脚本 |
|---|---|---|---|
| PNG / libpng16.so.16.40.0 | `png_write_find_filter` | 11.22% | pdftoppm 11.22% |
| libfreetype / libfreetype.so.6.20.1 | `cf2_glyphpath_pushPrevElem` | 0.14% | pdftoppm 0.14% |
| libfreetype / libfreetype.so.6.20.1 | `cf2_interpT2CharString` | 0.14% | pdftoppm 0.14% |

**PDF pdfwf005-u20：结算材料包重建**

| 工具／库 | 函数 | 占完整 ROI | 执行脚本 |
|---|---|---|---|
| ImageMagick / libMagickCore-7.Q16HDRI.so.10.0.2 | `HorizontalFilter._omp_fn.0` | 15.95% | montage 15.95% |
| ImageMagick / libMagickCore-7.Q16HDRI.so.10.0.2 | `VerticalFilter._omp_fn.0` | 13.18% | montage 13.18% |
| PNG / libpng16.so.16.40.0 | `png_write_find_filter` | 12.85% | pdftoppm 11.43%；montage 1.41% |

### 3.3 这些软件各自做什么、缺口由什么操作带来

| 工具分组 | 通常承担的工作 | 本次应如何解释 |
|---|---|---|
| ImageMagick | 缩略图与联系表 | 缩放、横纵滤波、像素导入与拼图；旧 OPM 用 Pillow，未观察到这些 ImageMagick 函数 |
| JPEG | JPEG 编码／解码 | 把预览或联系表编码成 JPEG，或读取 JPEG；需按实际脚本区分 |
| LibreOffice·Calc | 公式与工作簿重算 | 管理公式单元格、公式树和计算配置；旧 TLC 已有重算，差额是具体子路径 |
| LibreOffice·OOXML | 幻灯片／文档对象 | DrawingML 表格样式、形状与属性映射；比旧表单／工作簿的对象路径更丰富 |
| LibreOffice·VCL | Office 图形处理 | 位图缩放、卷积与模糊，可能在 Office 转 PDF 时发生；不能一概称为新增文档编辑 |
| LibreOffice·Writer | 文字文档布局 | 文字框、段落与页面对象布局；只根据已出现的具体函数判断，不预设排版必然最重 |
| LibreOffice·其他组件 | Office 组件与公共框架 | 对象属性、UNO、容器及未进一步归因的 Office 函数；统计保留，不能全部当作新增业务或全部当作无关开销 |
| LibreOffice·文本样式 | 文本对象／属性 | 处理字重、颜色、编辑属性和文本对象 |
| LibreOffice·矢量图形 | 图形几何 | 处理二维图形对象的范围与几何信息 |
| PNG | PNG 输出／读取 | 为页面预览选择行滤波方式、读写 PNG；旧例已有图片操作，但具体 libpng 函数未见 |
| Poppler | PDF 页面渲染 | 把文字、图形、图片绘制为像素；旧 OPM 已渲染 PDF，这里进入其他图像／字形子路径 |
| Python | 脚本及校验 | 包含启动、源码解析、对象操作、正则与字符串搜索；不能整类称为新文档计算 |
| libc | 具体库内运算 | 已定位软件身份，操作用途待进一步细分 |
| libcomphelper.so | 具体库内运算 | 已定位软件身份，操作用途待进一步细分 |
| libfontconfig | 字体匹配 | 查找、匹配字体和配置；不同于已经证实整个排版机制都是新热点 |
| libfreetype | 字形处理 | 加载、变换或栅格化字形；与旧渲染共享工作类型 |
| libicuuc.so.77 | 具体库内运算 | 已定位软件身份，操作用途待进一步细分 |
| libstdc++ | 具体库内运算 | 已定位软件身份，操作用途待进一步细分 |
| lxml | XML 文档结构 | 解析或遍历 OOXML/XML；旧例已有 XML 工作，扩展任务使用不同库或不同路径 |
| pixman | 像素合成 | 图像像素合成／缩放；结合执行脚本判断来自哪个渲染环节 |

**几个最容易误读的归因：**

- `png_write_find_filter` 来自生成 PNG 预览时的行滤波；不是 Word 专属排版，也不是 Excel 的公式计算。
- ImageMagick 横纵滤波可能由缩略图生成／拼图触发；联系表是新增组合操作，但不能把整库每个函数都叫作拼图算法。
- `ScDocument::RemoveFromFormulaTree`、`ScInterpreter::MergeCalcConfig` 来自 Calc 路径。旧 TLC 已重算，未见这些名字说明本次公式／场景处理走到了不同子路径。
- Word 的正则、字符串搜索有相当部分属于验证器；Office 属性／UNO 函数也需保持具体归因，不能为了支持代表性而全删，也不能为了强调新场景而全称为新机制。

### 3.4 013 大档的特殊变化：高覆盖主要来自 Python 构建

| 013 配置 | Python 库权重 | zlib 权重 | 构建脚本权重 | 解释器主循环函数权重 |
|---|---|---|---|---|
| 013 | 19.77% | 31.66% | 7.21% | 3.33% |
| 013-v100 | 9.60% | 56.62% | 6.30% | 2.37% |
| 013-v1000 | 85.93% | 8.87% | 87.50% | 51.06% |

013-v1000 的 Python 库约 85.9%，`build_bid_evaluation_variant.py` 约 87.5%，`_PyEval_EvalFrameDefault` 单项约 51.1%。这些通用解释器／对象函数在旧例已出现，因此已见权重提高，但这不是预览压缩变成主要工作，也不能据此把整个构建算法说成与旧 TLC 相同。

冻结构建器中，`apply_corrections()` 对每个待更正字段遍历完整纠错清单，`scores_by_vendor` 又为每个供应商扫描评分记录；当两边都随供应商数增长时，这些路径的遍历次数可能呈平方量级增长。静态代码与 Python 构建权重上升一致，本次没有 Python 行级计时，不能进一步声称某一行占了全部时间；也没有为了调整覆盖结果修改该代码。

代码复核读取的是 recipe 绑定的冻结构建器，SHA256 已纳入本轮输入索引：`docops/scaling/payload-all/tasks/013-v1000/seed/root/tmp/docs/build_bid_evaluation_variant.py`。

## 4. Topdown：规模改变了什么

下表保留 IPC 和四个顶层分类；Core／Memory 是 Backend 的子项。数值取 DevKit Report-ALL 累计输出，不是过程点的算术均值。四个顶层分类合计约 100%；IPC 和子项不能再加进去。

| 配置 | IPC | Bad Spec % | Frontend % | Backend % | Retiring % | Core % | Memory % |
|---|---|---|---|---|---|---|---|
| OPM | 1.23 | 4.68 | 18.12 | 56.76 | 20.44 | 46.41 | 10.35 |
| TLC | 1.23 | 2.48 | 18.10 | 58.85 | 20.57 | 44.73 | 14.12 |
| 001-u500 | 1.07 | 2.17 | 11.98 | 67.96 | 17.89 | 54.36 | 13.61 |
| 003-u500 | 1.86 | 1.45 | 7.47 | 60.10 | 30.99 | 55.72 | 4.38 |
| 009-u500 | 1.01 | 2.44 | 17.37 | 63.33 | 16.85 | 48.68 | 14.65 |
| 013-v1000 | 1.26 | 3.94 | 20.51 | 54.60 | 20.96 | 47.07 | 7.53 |
| 014-n10000 | 1.07 | 2.05 | 9.38 | 70.77 | 17.79 | 56.24 | 14.53 |
| 016-u500 | 1.07 | 3.22 | 23.02 | 55.98 | 17.78 | 42.21 | 13.78 |
| 021-g10 | 1.36 | 2.34 | 15.87 | 59.13 | 22.66 | 48.90 | 10.23 |
| 026-u10 | 1.26 | 2.20 | 17.00 | 59.72 | 21.07 | 48.47 | 11.25 |
| 029-u10 | 1.07 | 2.43 | 22.68 | 57.13 | 17.75 | 45.23 | 11.90 |
| 031-u20 | 1.13 | 1.20 | 3.96 | 75.99 | 18.84 | 61.67 | 14.33 |
| 037-u20 | 1.15 | 1.74 | 6.22 | 72.85 | 19.19 | 59.19 | 13.65 |
| pdfwf005-u20 | 1.41 | 3.57 | 7.97 | 64.90 | 23.56 | 54.92 | 9.98 |

旧两例的指标列为既有五次采集的均值；大档各只有一次独立采集。下表专门比较小档→大档，用百分点差直接说明变化，避免余弦接近 1 把差异遮住。

| 小档→大档 | ΔIPC | ΔBad Spec pp | ΔFrontend pp | ΔBackend pp | ΔRetiring pp | 四 Bound 半 L1 pp |
|---|---|---|---|---|---|---|
| 001-u100→001-u500 | +0.02 | -0.39 | +0.38 | -0.31 | +0.33 | 0.71 |
| 003-u100→003-u500 | +0.04 | -0.15 | -0.80 | +0.28 | +0.69 | 0.96 |
| 009-u100→009-u500 | +0.05 | -0.33 | -3.13 | +2.52 | +0.93 | 3.45 |
| 013-v100→013-v1000 | +0.11 | +1.43 | +11.02 | -14.31 | +1.86 | 14.31 |
| 014-n1000→014-n10000 | +0.00 | -0.03 | -1.71 | +1.76 | -0.03 | 1.76 |
| 016-u100→016-u500 | +0.21 | +0.21 | +0.96 | -4.53 | +3.37 | 4.54 |
| 021-g5→021-g10 | +0.00 | +0.27 | -1.12 | +0.83 | +0.01 | 1.12 |
| 026-u5→026-u10 | -0.02 | -0.03 | -0.33 | +0.59 | -0.25 | 0.60 |
| 029-u5→029-u10 | +0.06 | -0.57 | +1.65 | -2.08 | +1.00 | 2.65 |
| 031-u5→031-u20 | -0.03 | -0.19 | -2.52 | +3.17 | -0.47 | 3.18 |
| 037-u5→037-u20 | +0.03 | -0.01 | +0.88 | -1.43 | +0.56 | 1.44 |
| pdfwf005-u5→pdfwf005-u20 | +0.16 | -0.22 | -0.49 | -2.03 | +2.73 | 2.74 |

再检查原始任务→大档，以免只看小档与大档较接近，就遗漏了初始任务结构变化。

| 原始→大档 | ΔIPC | ΔBad Spec pp | ΔFrontend pp | ΔBackend pp | ΔRetiring pp | 四 Bound 半 L1 pp |
|---|---|---|---|---|---|---|
| 001→001-u500 | +0.18 | -0.87 | -2.88 | +0.77 | +2.98 | 3.75 |
| 003→003-u500 | +0.92 | -1.76 | -7.71 | -5.79 | +15.26 | 15.26 |
| 009→009-u500 | -0.07 | -0.43 | -0.25 | +1.82 | -1.14 | 1.82 |
| 013→013-v1000 | +0.31 | +0.54 | +5.46 | -11.06 | +5.08 | 11.07 |
| 014→014-n10000 | +0.23 | -1.42 | -9.03 | +6.68 | +3.75 | 10.44 |
| 016→016-u500 | +0.35 | -0.95 | -0.38 | -4.38 | +5.71 | 5.71 |
| 021→021-g10 | +0.21 | -0.15 | -0.40 | -2.96 | +3.51 | 3.51 |
| 026→026-u10 | +0.24 | -0.74 | -2.02 | -1.32 | +4.08 | 4.08 |
| 029→029-u10 | +0.16 | -0.83 | +1.70 | -3.42 | +2.54 | 4.24 |
| 031→031-u20 | +0.07 | -1.78 | -4.98 | +5.51 | +1.24 | 6.75 |
| 037→037-u20 | +0.16 | -0.84 | -4.06 | +2.20 | +2.70 | 4.90 |
| pdfwf005→pdfwf005-u20 | +0.29 | -1.09 | -4.00 | +0.27 | +4.82 | 5.09 |

半 L1 = 四项顶层分类绝对差之和的一半，表示四类分配改变了多少个百分点。余弦只作辅助，所有原始→小档、原始→大档、小档→大档及 OPM／TLC→大档比较均保存在 `topdown-deltas.csv`。

本批小档→大档的顶层分配变化最大的是 013-v100→013-v1000（14.31 pp）、016-u100→016-u500（4.54 pp）、009-u100→009-u500（3.45 pp）。这说明“更多函数已见”与“微架构分配完全不变”不是同一个结论。

Topdown 为 CPU 0–7 的完整采集包络，含边界、步间与轮间间隙；控制器在 CPU 9。保留 58 层级节点／事件、全部真实过程点及 `<not counted>` 标记；未把打印 0 当作未计数事件的真实零。它与 perf 的进程树 workflow ROI 口径分别记录，不强行当作同一窗口。本次没有从 1 秒日志插值制造新点，也不以一次采集论证稳定性。

## 5. 最少补充哪些用例：先明确要补哪些函数

先按既有的图片／页面／对象处理主缺口，加入本轮实际观察到的 Calc 子路径，定义核心补充目标：36 个新配置中，至少一个配置达到完整 ROI **0.5%**、旧 OPM＋TLC 未见、且属于这七组工具的已解析函数。再另列字体／XML／文本样式等更细身份的严格结果，以及包含 Python／公共框架的所有工具结果。没有只挑 Top-10，也没有把目标外的差额删除。

| 补充目标 | 目标函数数 | 只选原始 12 项 | 从全部 36 个具体配置选择 |
|---|---|---|---|
| 沿用上轮六类图像／页面／对象工具 | 45 | 无法全覆盖；缺 4 个身份（可覆盖部分最少 3 个配置） | 5 个 |
| 核心补充目标：再加 Calc 子路径 | 49 | 无法全覆盖；缺 6 个身份（可覆盖部分最少 3 个配置） | 7 个 |
| 严格文档工具目标：再加字体／XML／文本样式等 | 66 | 无法全覆盖；缺 13 个身份（可覆盖部分最少 5 个配置） | 10 个 |
| 严格目标：所有工具，含 Python／公共框架 | 148 | 无法全覆盖；缺 27 个身份（可覆盖部分最少 9 个配置） | 16 个 |

**核心补充目标精确最少为 7 个具体配置。** 下面展示求解器按名称排序选出的一组最小解；不是按耗时优化的最快方案。其他同样数量的方案见 `selection.json`，函数覆盖目标是采样中已出现的具体身份。

| 建议补充的配置 | 任务／操作 | 删除它后仍缺的目标函数数 | 它独自补上的例子 |
|---|---|---|---|
| 013 | 采购投标评审发布；build_public_bid_workbook.py；recalc.py；verify_public_bid_workbook.py；PDF／拼图 | 1 | `ScColumnData::GetMostUsedPattern(int, int) const` |
| 013-v100 | 采购投标评审发布；build_public_bid_workbook.py；recalc.py；verify_public_bid_workbook.py；PDF／拼图 | 1 | `png_read_filter_row_paeth_multibyte_pixel` |
| 016-u500 | 预测模型情景级联；build_forecast_dashboard_v1.py；recalc.py；测试副本切换情景并重算 | 2 | `ScDocument::RemoveFromFormulaTree(ScFormulaCell*)`；`ScInterpreter::MergeCalcConfig()` |
| 021 | 庇护所无障碍整改；build_public_shelter_briefing.py；validate_public_shelter_briefing.py；soffice.py／图片／拼图 | 3 | `encode_mcu_gather`；`quantize` |
| 026-u10 | 气候披露图表重建；build_climate_disclosure.py；转 PDF／图片；qa_climate_disclosure.py | 1 | `oox::ppt::PPTShape::findPlaceholder(int, int, std::optional<int> const&, std::vector…` |
| 029 | 季度业务回顾发布；build_release_deck.py；validate_release_deck.py；转 PDF／图片 | 1 | `oox::drawingml::table::applyTableStylePart(oox::core::XmlFilterBase const&, oox::dra…` |
| 029-u5 | 季度业务回顾发布；build_release_deck.py；validate_release_deck.py；转 PDF／图片 | 1 | `oox::ppt::PresentationFragmentHandler::importSlideNames(oox::core::XmlFilterBase con…` |

**按任务名字看，是 5 个任务家族：013、016、021、026、029。** 家族内允许合并本次各档已观测函数时，精确最少为 5 个家族。这不等于每个家族随便选一个档就够；上面 7 个具体配置说明哪些档实际提供了目标函数，同一任务的原始／小档可能各有独有观测。

这个核心方案没有要求每种文件格式各选一个。Word／PDF 预览中的许多 PNG 函数，也会被 Excel／PPT 的预览发布链触发；按函数身份可由这些配置共同补上。这不表示 Word／PDF 的完整业务流程可由它们替代。

“最少”只针对上述函数身份、阈值与候选集成立，候选中低频出现也算见过。字体／XML／文本样式等全部显著身份逐一补齐需更多配置，数量见上表，不能把核心方案称为这些函数也已全覆盖。选入参考的配置会与自身匹配，因此下面同时给出其他配置结果，不把自身匹配称为独立验证。若只允许保留原始任务，表中的缺失身份需另加实测规模配置；不能用父任务名字替代未观测到的函数。

| 大档目标 | 旧 OPM＋TLC 已见 | 加建议配置后已见 | 仍未见 | 未解析 | 与选入配置关系 |
|---|---|---|---|---|---|
| 001-u500 | 75.56% | 87.76% | 8.84% | 3.40% | 未选家族 |
| 003-u500 | 71.58% | 96.73% | 1.79% | 1.48% | 未选家族 |
| 009-u500 | 71.59% | 81.02% | 15.52% | 3.46% | 未选家族 |
| 013-v1000 | 93.25% | 96.41% | 3.57% | 0.02% | 同父任务不同档 |
| 014-n10000 | 91.82% | 97.02% | 1.92% | 1.05% | 未选家族 |
| 016-u500 | 80.03% | 99.45% | 0.00% | 0.55% | 自身入选 |
| 021-g10 | 50.44% | 91.06% | 6.83% | 2.11% | 同父任务不同档 |
| 026-u10 | 63.00% | 98.13% | 0.00% | 1.87% | 自身入选 |
| 029-u10 | 46.29% | 74.47% | 18.69% | 6.84% | 同父任务不同档 |
| 031-u20 | 86.49% | 98.87% | 1.13% | <0.01% | 未选家族 |
| 037-u20 | 86.72% | 98.80% | 1.20% | <0.01% | 未选家族 |
| pdfwf005-u20 | 48.94% | 97.66% | 1.91% | 0.43% | 未选家族 |

核心方案后仍有未匹配权重，尤其是 Word 009 与 PPT 029。它们的差额没有被隐藏：

| 大档 | 补充后仍未见 | 剩余前三工具组 |
|---|---|---|
| 001-u500 | 8.84% | Python 4.44%；LibreOffice·Writer 1.88%；LibreOffice·其他组件 1.20% |
| 009-u500 | 15.52% | LibreOffice·其他组件 5.68%；LibreOffice·Writer 5.40%；Python 2.12% |
| 021-g10 | 6.83% | LibreOffice·文本样式 1.77%；LibreOffice·其他组件 1.66%；LibreOffice·矢量图形 0.93% |
| 029-u10 | 18.69% | LibreOffice·其他组件 9.34%；LibreOffice·文本样式 4.37%；LibreOffice·OOXML 1.01% |

### 5.1 阈值敏感性：不能把一个数字当成绝对最优任务数

| 目标阈值 | 核心工具缺口数 | 全部 36 配置中最少个数 | 最小解示例 |
|---|---|---|---|
| 0.1% | 153 | 17 个 | 001、001-u100、009-u100、013、013-v100、016、016-u500、021-g10、021-g5、026、026-u10、026-u5、029、029-u10、029-u5、pdfwf005、pdfwf005-u5 |
| 0.5% | 49 | 7 个 | 013、013-v100、016-u500、021、026-u10、029、029-u5 |
| 1% | 33 | 6 个 | 013、013-v100、016-u500、021、026-u10、029 |

降低阈值会纳入更多低频实现细节，补充数量可能上升；这不是新增了同样多种业务机制。工具分组、阈值、全部目标函数、每个候选是否覆盖，以及移除单个推荐后的剩余权重均已保存。

## 6. 对旧两例代表性的最终判断

1. **旧例可继续作为共同基础计算的核心基准。** 放大后 Excel 013／014、PDF 031／037 的已见权重较高，说明解释执行、对象管理、XML、压缩／解压和页面／图片处理等共性具有实际证据。
   其中 013 的高覆盖主要来自解释器／构建工作增长；014／031／037 更偏页面预览与压缩。共同函数覆盖不等于执行算法或工作量都一样。
2. **“覆盖较低都是输入太小”不成立。** pdfwf005 的 ImageMagick 滤波／联系表、PPT 的图形和对象样式、PNG 输出滤波等函数在大档仍占有可观权重；旧两例不足以替代这些具体软件路径。
3. **补充以操作与软件路径为单位更有效。** 需要保留真正触发图像缩放／拼图、页面输出、PPT 对象处理、以及本轮实际出现的 Calc／XML／字体子路径的配置；不必只因换行业就全部加入。在本批明确定义的核心目标下，最少补充 7 个配置（5 个任务家族）：013、013-v100、016-u500、021、026-u10、029、029-u5。若要求每个字体／XML／文本样式热点身份也出现过，应采用上表的严格方案，不把两者混称。
4. **辅助差额保持可见。** Python 校验搜索和 Office 公共框架不直接等同于新文档机制，也不从统计中删除；严格“所有热点身份均补齐”的成本已另列，不能与主建议混称。

## 7. 数据与复核入口

- `comparison.json`：38 个参考／目标配置、完整函数／工具／脚本权重、60 个成对比较、输入哈希。
- `selection.json`：阈值敏感性、完整目标函数、精确最小解、不可覆盖清单、逐项消融与自身匹配标记。
- `coverage.csv`：36 个配置的三分区与三种规模；`topdown.csv`／`topdown-deltas.csv`：全部共同指标和变化。`topdown-hierarchy.csv` 保留 24 个规模配置各 58 个层级节点，附近似／未计数标记；不假定每个打印值都已通过事件依赖有效性判断。
- `unseen-functions.csv`：所有已解析未见函数、软件、执行脚本、周期及占比；`tool-gaps.csv`：各库组缺口。
- `verification.json`：从原始函数行独立复算三分区、上下文守恒、Topdown 差值，以及最小解的第二种校验。
- `analysis-build.json`：本轮脚本、输入与输出 SHA256；不修改原始采集或已有报告。

采样丢块／丢样记录与符号不足仍按原证据保留。权重来自实际保留样本的 period，不按请求 49 Hz 倒推样本、不按样本个数估计 CPU 时间，也不补造丢样 period。
