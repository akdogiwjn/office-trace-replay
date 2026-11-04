## 七、扩展任务操作：与原始 PDF/XLSX 基准比较

前六节保留原七例“跨行业输入”实验及其提出的场景扩展问题。本节报告十二项 DocOps L3 的真实轨迹回放：在 PDF／Excel 中改变任务操作，并加入 Word／PPT，分别与原始 OPM／TLC 比较。
**先看判断：原七例能够代表已测任务形态下的跨行业输入，但没有充分覆盖更广的文档操作。本次扩展已观察到不同的热点函数和流水线分配，因此有必要按操作类型补充负载。** 以下依次说明工具做什么、旧热点保留多少、CPU 指标怎样变化。

### 7.1 样本、轨迹与测量口径

| 任务组 | 本次操作覆盖 | 主要对照 |
|---|---|---|
| PDF：031／037／pdfwf005 | 听证材料包发布、公交绕行材料修复、结算材料包重建 | 原始 PDF：OPM |
| Excel：013／014／016 | 投标评审发布、灾害补助公开发布、预测模型情景级联 | 原始 XLSX：TLC |
| Word：001／003／009 | 受控发布修复、元数据清理、事件手册发布 | OPM、TLC 均比较 |
| PPT：021／026／029 | 无障碍整改、图表重建、季度业务回顾发布 | OPM、TLC 均比较 |

十二项任务采用已保存 Agent 轨迹中的最终有效依赖链。各任务独立冻结脚本、输入、Skill 和命令；内联命令保留为任务私有步骤。回放不调用模型，保留最终构建、必要修补、重算、渲染及原有检查，公共入口负责调度、环境和归档。
来源中的官方内容判定为四项通过、八项未通过；本次十二项工具链回放及采集均完成。两类结果分别记录，逐项来源和判定见实验数据记录。

| 项目 | 原始 OPM／TLC | 新增 DocOps |
|---|---|---|
| 环境 | 原七例测量镜像；Python 3.12.3、LibreOffice 25.8.7.3 | 基于同一测量镜像；共用 Python、LibreOffice、Poppler 和 perf 版本，补充文档、幻灯片及图像处理依赖 |
| 重复与汇总 | 每路五次独立运行；热点合并周期权重，Topdown 取五次 ALL 均值 | 每项每路一次独立采集，内部十轮回放；热点按工作流周期权重，Topdown 取本次 ALL |
| 采集 | perf：cycles:u、49 Hz、DWARF；DevKit：CPU 0–7、1 秒间隔 | 沿用相同参数；两路分开运行，控制器 CPU 9 |
| 窗口 | 既有完整循环，包含 reset 和循环检查 | perf 为 workflow 步骤区间并集，排除准备、reset 和归档；Topdown 为按核采集包络 |

本节比较实际工作流，任务操作、输入组织和规模可能同时变化；结论用于识别负载差异。十轮合并采集只算一次独立运行，不套用原七例的五次稳定性结论。

### 7.2 软件分别做什么，哪些沿用、哪些扩展

**表 7-1：软件用途。** “脚本／工具”是直接调用的程序，“底层组件”是执行过程中真正消耗 CPU 的库。比如 python-docx 操作 Word，但对应 CPU 周期可能记在 Python、XML 或压缩函数中，不能把两层占比直接相加。

| 软件／组件 | 一般用途 | 在本批任务中的位置 |
|---|---|---|
| Python | 执行脚本，创建和管理数据对象 | 原有与新增任务共同的运行环境 |
| openpyxl | 读取、修改、保存 Excel 工作簿 | 已有 Excel 读写工具，扩展任务继续使用 |
| python-docx／python-pptx | 创建和修改段落、表格、形状及幻灯片 | 为 Word／PPT 任务补充的直接操作库 |
| LibreOffice：Calc／Writer／Impress | 分别处理表格、文字文档和幻灯片；支持重算、排版与格式转换 | 沿用同一软件版本，任务进入不同文档模块 |
| Poppler／pdftoppm | 解析 PDF，将页面绘制为图片 | 原 PDF 已有；新任务的预览和渲染继续使用 |
| Pillow／ImageMagick | 图片转换、缩放、滤波和拼图 | Pillow 为原有工具；DocOps 补充 ImageMagick |
| ReportLab／fontTools | 分别用于生成 PDF、读取和处理字体 | DocOps 补充的任务依赖；安装存在不等于占主要热点 |
| zlib／PNG 编码库 | 压缩重复数据，编码并写出图片 | 部分新任务中成为主要 CPU 热点 |
| lxml／Expat／ElementTree | 读取和处理文档内部的 XML 结构 | 原 Excel 已有 XML 路径，DocOps 增加 lxml 依赖 |
| libc／loader | 基础内存、字符串等操作，以及装载程序依赖库 | 公共运行基础，不能仅由该库名判断具体文档业务 |

**表 7-2：原始任务作为对照。** OPM 代表 PDF 表单填写与检查，TLC 代表大型工作簿检查、增强、重算和缓存验证。下面的百分比为用户态 perf 采样周期占比，包含所有保留的工作流样本，不是任务墙钟时间。

| 原始基准 | 主要脚本／进程 | 主要底层组件及周期占比 |
|---|---|---|
| OPM | convert_pdf_to_images.py 38.85%; fill_fillable_fields.py 38.44%; verify_pdf_batch.py 12.26%; pdftoppm 8.03% | Python 50.41%; zlib 25.18%; Pillow 14.61%; Poppler 6.23% |
| TLC | enhance_workbook.py 22.01%; inspect_xlsx_structure.py 12.69%; recalc.py 11.60%; inspect_xlsx_features.py 10.57% | Python 79.26%; LibreOffice 6.43%; Expat 5.65%; ElementTree 3.68% |

**表 7-3：十二项新增任务实际执行什么。** 先看脚本链路，再看采样周期主要落在哪些底层软件；每行只列占比最高的四项组件，不要求四项合计为 100%。

| 格式／任务 | 实际脚本／工具链 | 主要底层组件及周期占比 |
|---|---|---|
| PDF／031 听证材料包扁平化发布 | build_public_packet.py；PDF 渲染；validate_public_packet.py | zlib 66.25%; Python 20.08%; PNG 8.68%; Poppler 2.56% |
| PDF／037 公交绕行材料修复 | build_bus_detour_packet.py；PDF 渲染；validate_bus_detour_packet.py | zlib 52.92%; Python 29.90%; PNG 10.27%; Poppler 4.61% |
| PDF／pdfwf005 结算材料包重建 | rebuild_closeout_binder.py；PDF 检查；图片／拼图／诊断 | Python 31.74%; ImageMagick 25.96%; zlib 23.67%; PNG 11.60% |
| Excel／013 采购投标评审发布 | build_public_bid_workbook.py；recalc.py；verify_public_bid_workbook.py；PDF／拼图 | zlib 31.66%; Python 19.77%; ImageMagick 13.43%; LibreOffice 10.20% |
| Excel／014 灾害补助公开发布 | build_disaster_release_v1.py；recalc.py；finalize_disaster_release_ooxml_v3.py；validate_disaster_release_v1.py／渲染 | zlib 30.54%; Python 25.49%; LibreOffice 17.51%; PNG 7.57% |
| Excel／016 预测模型情景级联 | build_forecast_dashboard_v1.py；recalc.py；测试副本切换情景并重算 | Python 47.65%; LibreOffice 27.74%; libc 8.81%; loader 3.62% |
| Word／001 受控文档发布修复 | create_packet.py；render_docx.py；结构与渲染检查 | zlib 44.27%; Python 18.74%; LibreOffice 11.65%; libc 7.16% |
| Word／003 公开记录元数据清理 | build_public_packet.py；audit_public_packet.py；render_docx.py | zlib 44.62%; Python 14.91%; LibreOffice 14.23%; PNG 9.05% |
| Word／009 事件手册发布 | build_incident_manual_publication.py；render_docx.py；validate_incident_manual_publication.py | zlib 44.39%; PNG 19.00%; LibreOffice 9.11%; Python 8.86% |
| PPT／021 庇护所无障碍整改 | build_public_shelter_briefing.py；validate_public_shelter_briefing.py；soffice.py／图片／拼图 | Poppler 27.74%; LibreOffice 24.32%; Python 15.95%; ImageMagick 10.59% |
| PPT／026 气候披露图表重建 | build_climate_disclosure.py；转 PDF／图片；qa_climate_disclosure.py | Poppler 36.90%; Python 20.97%; LibreOffice 19.20%; libc 6.60% |
| PPT／029 季度业务回顾发布 | build_release_deck.py；validate_release_deck.py；转 PDF／图片 | Python 36.96%; LibreOffice 32.15%; libc 7.61%; Poppler 5.08% |

**本节总结：**

- **共同基础仍然保留。** Python、LibreOffice、Poppler、压缩和图像处理继续构成主要工具链。
- **扩展了文档操作工具和模块。** 新增 python-docx、python-pptx、lxml、ImageMagick 等依赖，并执行 Writer、Impress 和幻灯片对象处理路径。
- **已有软件也会承担不同的工作。** 同样调用 LibreOffice 或 Poppler，实际可能是表格重算、文档转 PDF 或页面绘图，热点权重不会天然相同。

### 7.3 热点函数：旧热点保留多少，新热点在做什么

本节分两步阅读：表 7-4 看原有热点的延续程度，表 7-5 解释新任务最耗周期的函数。函数以“完整物理叶函数名＋所属库文件名”匹配，同名但来自不同库的函数不会混为一项。未知符号仍保留在完整周期分母中。

**两个指标的区别：**“共同函数数”比较两份前十名单，有几个相同；“旧热点函数占比”则把原基准前十个函数在新任务全部采样中的周期相加，即使该函数掉出新任务前十也计入。后者是十个具体函数的权重，不是整个任务或旧切片的覆盖率。

**读表示例：** 031 与 OPM 的前十热点共有 3 个函数，但 OPM 的前十函数在 031 中仍占 67.11%；其中压缩函数 `longest_match` 单独占 56.95%。所以共同函数数量少，不一定表示共同计算的权重小。

**表 7-4：原始热点在新任务中的延续程度。** PDF 以 OPM 为主对照，Excel 以 TLC 为主对照；Word／PPT 同时列两个基准。OPM 自身前十函数合计占 57.81%，TLC 为 49.50%，并非基准全部周期。

| 新任务 | 对照基准 | 两份前十名单中相同的函数数 | 原基准前十函数在新任务中的周期占比 |
|---|---|---|---|
| 031 听证材料包扁平化发布 | OPM | 3/10 | 67.11% |
| 037 公交绕行材料修复 | OPM | 4/10 | 56.07% |
| pdfwf005 结算材料包重建 | OPM | 5/10 | 25.93% |
| 013 采购投标评审发布 | TLC | 1/10 | 6.12% |
| 014 灾害补助公开发布 | TLC | 2/10 | 8.37% |
| 016 预测模型情景级联 | TLC | 2/10 | 12.06% |
| 001 受控文档发布修复 | OPM | 4/10 | 45.33% |
| 001 受控文档发布修复 | TLC | 2/10 | 4.61% |
| 003 公开记录元数据清理 | OPM | 3/10 | 44.19% |
| 003 公开记录元数据清理 | TLC | 0/10 | 2.00% |
| 009 事件手册发布 | OPM | 4/10 | 45.80% |
| 009 事件手册发布 | TLC | 1/10 | 3.89% |
| 021 庇护所无障碍整改 | OPM | 1/10 | 2.59% |
| 021 庇护所无障碍整改 | TLC | 1/10 | 3.90% |
| 026 气候披露图表重建 | OPM | 2/10 | 4.96% |
| 026 气候披露图表重建 | TLC | 2/10 | 6.34% |
| 029 季度业务回顾发布 | OPM | 1/10 | 7.36% |
| 029 季度业务回顾发布 | TLC | 2/10 | 12.53% |

**表 7-5：新任务主要在计算什么。** 列出每项前三个函数及其周期占比，并按软件说明用途。完整前二十函数、所属库及全部 OPM／TLC 对照见实验数据记录。

| 新任务 | 前三热点函数及周期占比 | 这些函数通常做什么 |
|---|---|---|
| 031 听证材料包扁平化发布 | `longest_match` 56.95%; `png_write_find_filter` 8.68%; `deflate_slow` 6.83% | zlib：查找重复数据并压缩；PNG：选择图像编码方式并写出图片 |
| 037 公交绕行材料修复 | `longest_match` 45.90%; `png_write_find_filter` 10.27%; `deflate_slow` 4.64% | zlib：查找重复数据并压缩；PNG：选择图像编码方式并写出图片 |
| pdfwf005 结算材料包重建 | `HorizontalFilter._omp_fn.0` 12.59%; `VerticalFilter._omp_fn.0` 11.46%; `png_write_find_filter` 10.57% | ImageMagick：横向／纵向图像滤波、缩放；PNG：选择图像编码方式并写出图片 |
| 013 采购投标评审发布 | `longest_match` 21.24%; `png_write_find_filter` 8.38%; `HorizontalFilter._omp_fn.0` 8.05% | zlib：查找重复数据并压缩；PNG：选择图像编码方式并写出图片；ImageMagick：横向／纵向图像滤波、缩放 |
| 014 灾害补助公开发布 | `longest_match` 22.52%; `png_write_find_filter` 7.57%; `deflate_slow` 4.90% | zlib：查找重复数据并压缩；PNG：选择图像编码方式并写出图片 |
| 016 预测模型情景级联 | `_PyEval_EvalFrameDefault` 4.57%; `_Py_dict_lookup` 3.70%; `std::_Rb_tree<int, int, std::_Identity<int>, std::less<int>, std::allocator…` 3.11% | Python：执行脚本指令；Python：查找字典中的对象；C++ 有序容器：插入或查找数据 |
| 001 受控文档发布修复 | `longest_match` 36.05%; `deflate_slow` 5.87%; `png_write_find_filter` 5.34% | zlib：查找重复数据并压缩；PNG：选择图像编码方式并写出图片 |
| 003 公开记录元数据清理 | `longest_match` 33.55%; `png_write_find_filter` 9.05%; `deflate_slow` 5.91% | zlib：查找重复数据并压缩；PNG：选择图像编码方式并写出图片 |
| 009 事件手册发布 | `longest_match` 27.62%; `png_write_find_filter` 19.00%; `deflate_slow` 10.59% | zlib：查找重复数据并压缩；PNG：选择图像编码方式并写出图片 |
| 021 庇护所无障碍整改 | `Splash::pipeRun(SplashPipe*)` 9.94%; `VerticalFilter._omp_fn.0` 6.96%; `Splash::pipeRunAARGB8(SplashPipe*)` 6.12% | Poppler：将 PDF 页面内容绘制成像素；ImageMagick：横向／纵向图像滤波、缩放 |
| 026 气候披露图表重建 | `Splash::pipeRunAARGB8(SplashPipe*)` 12.81%; `Splash::pipeRun(SplashPipe*)` 11.74%; `_PyEval_EvalFrameDefault` 2.75% | Poppler：将 PDF 页面内容绘制成像素；Python：执行脚本指令 |
| 029 季度业务回顾发布 | `_PyEval_EvalFrameDefault` 5.31%; `_Py_dict_lookup` 3.45%; `oox::drawingml::table::applyTableStylePart(oox::core::XmlFilterBase const&,…` 2.00% | Python：执行脚本指令；Python：查找字典中的对象；LibreOffice：处理幻灯片表格等对象的样式 |

**从函数可以读出的四点变化：**

- **新增 PDF：原来就有压缩和图片处理，现在这些工作的比重、具体实现发生变化。** 031／037 的 zlib 压缩占比达到约 **66%／53%**，高于 OPM 的约 **25%**；pdfwf005 则增加了明显的 ImageMagick 图片缩放、滤波和拼图热点。因此，是处理重点改变，不是首次出现图片处理。
- **新增 Excel：从工作簿处理，扩展到工作簿处理加预览发布。** 013／014 不仅生成、重算和检查 Excel，还导出 PDF、渲染图片，因此压缩和图片处理的权重增加。016 则主要体现情景切换、重算以及 Python／Calc 内部处理。
- **新增 Word：虽然操作的是 Word，最终较重的环节却是文档转换后的压缩和图片编码。** 所以它与原 PDF 的压缩热点有共性，但执行的完整任务不同。
- **新增 PPT：部分任务的页面绘制更重。** 021／026 的 Poppler 页面渲染突出；029 则更多体现 Python 对象处理和 LibreOffice 幻灯片表格样式处理。

### 7.4 Topdown：四类流水线指标完整比较

热点函数回答“运行了什么代码”，Topdown 回答“CPU 流水线的资源怎样分配”。下面先解释指标，再展示原值与相对基准的变化；四项顶层指标全部保留。

**表 7-6：指标读法。** 四项 Topdown 顶层分类合计约为 100%；IPC 单独阅读，不与百分数相加。

| 指标 | 中文含义 | 如何理解 |
|---|---|---|
| IPC | 每周期完成的指令数 | 反映平均指令吞吐；单独降低不等于整项任务耗时一定更长 |
| Bad Speculation | 误推测 | 分支预测错误等产生的无效执行份额 |
| Frontend Bound | 前端受限 | 指令获取、解码等供应环节受限的份额 |
| Backend Bound | 后端受限 | 执行资源或数据供应环节受限的份额；不能只凭此项判断是内存问题 |
| Retiring | 有效完成 | 用于正常完成指令的流水线份额，不是整项任务的 CPU 利用率 |

**表 7-7：原始基准与十二项任务的实测原值。** OPM／TLC 为五次独立采集的均值，新任务为本次十轮批次的 ALL 累计结果。除 IPC 外，单位均为百分比。

| 配置 | IPC | 误推测 % | 前端受限 % | 后端受限 % | 有效完成 % |
|---|---|---|---|---|---|
| OPM（原始基准） | 1.226 | 4.676 | 18.120 | 56.762 | 20.440 |
| TLC（原始基准） | 1.234 | 2.478 | 18.100 | 58.846 | 20.572 |
| 031 听证材料包扁平化发布 | 1.060 | 2.980 | 8.940 | 70.480 | 17.600 |
| 037 公交绕行材料修复 | 0.990 | 2.580 | 10.280 | 70.650 | 16.490 |
| pdfwf005 结算材料包重建 | 1.120 | 4.660 | 11.970 | 64.630 | 18.740 |
| 013 采购投标评审发布 | 0.950 | 3.400 | 15.050 | 65.660 | 15.880 |
| 014 灾害补助公开发布 | 0.840 | 3.470 | 18.410 | 64.090 | 14.040 |
| 016 预测模型情景级联 | 0.720 | 4.170 | 23.400 | 60.360 | 12.070 |
| 001 受控文档发布修复 | 0.890 | 3.040 | 14.860 | 67.190 | 14.910 |
| 003 公开记录元数据清理 | 0.940 | 3.210 | 15.180 | 65.890 | 15.730 |
| 009 事件手册发布 | 1.080 | 2.870 | 17.620 | 61.510 | 17.990 |
| 021 庇护所无障碍整改 | 1.150 | 2.490 | 16.270 | 62.090 | 19.150 |
| 026 气候披露图表重建 | 1.020 | 2.940 | 19.020 | 61.040 | 16.990 |
| 029 季度业务回顾发布 | 0.910 | 3.260 | 20.980 | 60.550 | 15.210 |

**表 7-8：与原始基准相比改变了多少。** 正号表示新任务更高，负号表示更低。IPC 用相对百分比；四项 Topdown 用百分点（pp），例如 20% 变成 25% 是 +5 pp。Word／PPT 同时对照 OPM、TLC。

| 任务（对照基准） | IPC 变化 % | 误推测 Δpp | 前端 Δpp | 后端 Δpp | 有效完成 Δpp |
|---|---|---|---|---|---|
| 031（OPM） | -13.5% | -1.70 | -9.18 | +13.72 | -2.84 |
| 037（OPM） | -19.2% | -2.10 | -7.84 | +13.89 | -3.95 |
| pdfwf005（OPM） | -8.6% | -0.02 | -6.15 | +7.87 | -1.70 |
| 013（TLC） | -23.0% | +0.92 | -3.05 | +6.81 | -4.69 |
| 014（TLC） | -31.9% | +0.99 | +0.31 | +5.24 | -6.53 |
| 016（TLC） | -41.7% | +1.69 | +5.30 | +1.51 | -8.50 |
| 001（OPM） | -27.4% | -1.64 | -3.26 | +10.43 | -5.53 |
| 001（TLC） | -27.9% | +0.56 | -3.24 | +8.34 | -5.66 |
| 003（OPM） | -23.3% | -1.47 | -2.94 | +9.13 | -4.71 |
| 003（TLC） | -23.8% | +0.73 | -2.92 | +7.04 | -4.84 |
| 009（OPM） | -11.9% | -1.81 | -0.50 | +4.75 | -2.45 |
| 009（TLC） | -12.5% | +0.39 | -0.48 | +2.66 | -2.58 |
| 021（OPM） | -6.2% | -2.19 | -1.85 | +5.33 | -1.29 |
| 021（TLC） | -6.8% | +0.01 | -1.83 | +3.24 | -1.42 |
| 026（OPM） | -16.8% | -1.74 | +0.90 | +4.28 | -3.45 |
| 026（TLC） | -17.3% | +0.46 | +0.92 | +2.19 | -3.58 |
| 029（OPM） | -25.8% | -1.42 | +2.86 | +3.79 | -5.23 |
| 029（TLC） | -26.3% | +0.78 | +2.88 | +1.70 | -5.36 |

**本节结论：**

- **PDF 031／037 的变化主要体现在前后端分配。** 相比 OPM，前端份额分别降低 9.18／7.84 pp，后端增加 13.72／13.89 pp。
- **Excel 016 的前端受限增加、有效完成份额降低。** 相比 TLC，前端增加 5.30 pp，有效完成降低 8.50 pp，IPC 低 41.7%；是否更耗时还需结合具体工作量。
- **相同大类指标接近，不代表热点相同。** PPT 021 与 029 的四维余弦约 0.9955，但前十热点仅共享两个函数，仍需结合软件和函数比较。
- **四项指标必须一起看。** 前端降低的份额可能转到后端、误推测或有效完成；只列前后端会掩盖其他变化。

**辅助相似度如何使用：** 四维 Bound 余弦描述分布方向，总变差为四项绝对百分点差之和的一半，Jaccard 描述前十函数集合重合程度。详细数值、公式和全部 24 组对照保留在实验数据记录；本节不依据“余弦超过 0.99”给出整体负载高度相似的判断。

### 7.5 十二项任务的逐点曲线与读图说明

下列十二张图每项对应一张，按 PDF、Excel、Word、PPT 排列，共 533 个真实过程点。每张有四条线，分别对应误推测、前端受限、后端受限、有效完成。横轴为实际输出点编号，纵轴为百分比；名义间隔 1 秒，不插值、不增加人工采样点。
每张图是一份采集中十轮回放的过程，不是十次独立采集。曲线用于看执行过程的分布变化，最终指标取 ALL 累计报告。未建立可靠的逐点阶段对应，因此不把某个峰值直接标成“重算”或“渲染”。

### 图 7-1：PDF／031 听证材料包扁平化发布——四项 Topdown 过程

![图 7-1：PDF／031 听证材料包扁平化发布——四项 Topdown 过程](../analysis/docops/processed/task-operation-expansion-20261104/figures/031-bounds.svg)

**读图：** 后端受限占比较高；相对 OPM 的汇总变化为前端降低、后端增加。热点同时显示压缩占比突出。 本图共 21 个真实输出点。

### 图 7-2：PDF／037 公交绕行材料修复——四项 Topdown 过程

![图 7-2：PDF／037 公交绕行材料修复——四项 Topdown 过程](../analysis/docops/processed/task-operation-expansion-20261104/figures/037-bounds.svg)

**读图：** 后端受限是主要份额，与 031 的汇总特征接近；压缩与 PNG 编码是主要函数热点。 本图共 26 个真实输出点。

### 图 7-3：PDF／pdfwf005 结算材料包重建——四项 Topdown 过程

![图 7-3：PDF／pdfwf005 结算材料包重建——四项 Topdown 过程](../analysis/docops/processed/task-operation-expansion-20261104/figures/pdfwf005-bounds.svg)

**读图：** 本项加入材料包重建与拼图，热点中出现 ImageMagick 图像滤波；结合曲线观察其流水线分配。 本图共 20 个真实输出点。

### 图 7-4：Excel／013 采购投标评审发布——四项 Topdown 过程

![图 7-4：Excel／013 采购投标评审发布——四项 Topdown 过程](../analysis/docops/processed/task-operation-expansion-20261104/figures/013-bounds.svg)

**读图：** 本项同时执行工作簿处理和 PDF／图片交付；结合压缩、图像与 Calc 热点阅读这些过程点。 本图共 53 个真实输出点。

### 图 7-5：Excel／014 灾害补助公开发布——四项 Topdown 过程

![图 7-5：Excel／014 灾害补助公开发布——四项 Topdown 过程](../analysis/docops/processed/task-operation-expansion-20261104/figures/014-bounds.svg)

**读图：** 本项包含工作簿重算、OOXML 修补及渲染；最终指标取整段累计，曲线用于显示过程变化。 本图共 43 个真实输出点。

### 图 7-6：Excel／016 预测模型情景级联——四项 Topdown 过程

![图 7-6：Excel／016 预测模型情景级联——四项 Topdown 过程](../analysis/docops/processed/task-operation-expansion-20261104/figures/016-bounds.svg)

**读图：** 汇总前端受限高于 TLC，IPC 低于 TLC；函数中可见 Python 对象处理与 Calc 路径。 本图共 55 个真实输出点。

### 图 7-7：Word／001 受控文档发布修复——四项 Topdown 过程

![图 7-7：Word／001 受控文档发布修复——四项 Topdown 过程](../analysis/docops/processed/task-operation-expansion-20261104/figures/001-bounds.svg)

**读图：** 本项执行 Word 构建、转换和检查；压缩函数是主要热点，不能只凭文件格式认为排版必然最重。 本图共 31 个真实输出点。

### 图 7-8：Word／003 公开记录元数据清理——四项 Topdown 过程

![图 7-8：Word／003 公开记录元数据清理——四项 Topdown 过程](../analysis/docops/processed/task-operation-expansion-20261104/figures/003-bounds.svg)

**读图：** 本项包含元数据处理、审计与文档渲染；曲线需与压缩、PNG 和 Writer 工具路径一起解释。 本图共 27 个真实输出点。

### 图 7-9：Word／009 事件手册发布——四项 Topdown 过程

![图 7-9：Word／009 事件手册发布——四项 Topdown 过程](../analysis/docops/processed/task-operation-expansion-20261104/figures/009-bounds.svg)

**读图：** 本项事件手册发布的主要函数集中于压缩和 PNG 编码，图中展示这份批次的实际流水线变化。 本图共 26 个真实输出点。

### 图 7-10：PPT／021 庇护所无障碍整改——四项 Topdown 过程

![图 7-10：PPT／021 庇护所无障碍整改——四项 Topdown 过程](../analysis/docops/processed/task-operation-expansion-20261104/figures/021-bounds.svg)

**读图：** 本项 PDF 页面绘制与图像处理较突出；与 029 共享工具，但主要热点函数和指标分配不同。 本图共 110 个真实输出点。

### 图 7-11：PPT／026 气候披露图表重建——四项 Topdown 过程

![图 7-11：PPT／026 气候披露图表重建——四项 Topdown 过程](../analysis/docops/processed/task-operation-expansion-20261104/figures/026-bounds.svg)

**读图：** 本项 Poppler 页面绘制份额较高；实际过程点展示渲染相关工作流的流水线分配。 本图共 68 个真实输出点。

### 图 7-12：PPT／029 季度业务回顾发布——四项 Topdown 过程

![图 7-12：PPT／029 季度业务回顾发布——四项 Topdown 过程](../analysis/docops/processed/task-operation-expansion-20261104/figures/029-bounds.svg)

**读图：** 本项出现解释器、字典查找与 DrawingML 表格样式函数，不能用其他 PPT 的渲染热点代替。 本图共 53 个真实输出点。

### 7.6 最终判断：原负载覆盖了什么，还需要扩展什么

**结论是：原有负载在已测任务范围内具有跨行业代表性；扩展操作实验同时发现了原任务未充分覆盖的计算路径，因此仍有必要扩充办公 Agent 的操作类型。** 这两项发现回答不同问题，能够同时成立。

- **原七例的结论继续成立。** 保持表单填写或大型工作簿增强等任务形态时，更换行业输入仍延续主要热点，已有负载有明确用途。
- **覆盖缺口确实存在。** 原来没有充分体现材料包重建、图片滤波与拼图、幻灯片对象样式、不同发布和情景重算组合；本次已在具体函数与模块中观察到相应差异。
- **“未充分覆盖”不等于公共软件全都缺失。** 压缩、XML、LibreOffice 和渲染原本就有；新任务可能增强已有机制，也可能进入不同模块和函数路径。不能拿旧前十名单之外的全部周期都称为全新机制。
- **代表范围需要扩展。** 原负载可以代表已测 PDF 表单与大型工作簿任务，单独用它们代表更广的 Word、PPT 及复杂文档操作仍不充分；本次十二项补充了这部分实测证据。
- **后续优先按操作选型。** 保留原有跨行业输入对照，补充能带来不同热点的文档构建、对象处理、布局与渲染任务；先对候选做独立重复，再决定最终基准集合。连续长文档分页等是否形成主导热点，还需专项实测。

[完整扩展实验记录](experimental-results.md#九扩展任务操作十二项-docops-完整记录)保留九项指标、24 组基准对照、完整函数名单和全部曲线；[机器结果与来源绑定](../analysis/docops/processed/task-operation-expansion-20261104/comparison.json)可逐项追溯。
