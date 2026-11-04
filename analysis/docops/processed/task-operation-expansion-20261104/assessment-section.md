## 七、扩展任务操作：与原始 PDF/XLSX 基准比较

前六节保留原七例“跨行业输入”实验及其提出的场景扩展问题。本节接续这些问题，报告后续十二项 DocOps L3 的真实轨迹回放测量：在 PDF／Excel 中改变任务操作，并加入 Word／PPT，分别与原始 OPM／TLC 比较。
**本节的主线是操作、工具链和热点函数如何变化，Topdown 用于描述这些工作流的流水线特征。** 四顶层 Bound 余弦作为辅助形状指标，不以超过 0.99 判定整体负载高度相似。

### 7.1 样本、轨迹与测量口径

| 任务组 | 本次操作覆盖 | 主要对照 |
|---|---|---|
| PDF：031／037／pdfwf005 | 听证材料包发布、公交绕行材料修复、结算材料包重建 | 原始 PDF：OPM |
| Excel：013／014／016 | 投标评审发布、灾害补助公开发布、预测模型情景级联 | 原始 XLSX：TLC |
| Word：001／003／009 | 受控发布修复、元数据清理、事件手册发布 | OPM、TLC 均比较 |
| PPT：021／026／029 | 无障碍整改、图表重建、季度业务回顾发布 | OPM、TLC 均比较 |

十二项任务采用已保存 Agent 轨迹中的最终有效依赖链。各任务独立冻结脚本、输入、Skill 和命令；内联命令保留为任务私有执行步骤，公共入口只负责调度、环境和归档。回放不调用模型，保留最终构建、必要修补、重算、渲染及原有检查。
原始 Agent 内容判定与回放完成分开记录：来源中四项内容通过、八项未通过；本次十二项冻结工具链及采集均完成。逐项来源、历史判定与实际脚本见实验数据记录。

| 项目 | 原始 OPM／TLC | 新增 DocOps |
|---|---|---|
| 环境 | 原七例测量镜像；Python 3.12.3、LibreOffice 25.8.7.3 | 基于同一测量镜像；共用 Python、LibreOffice、Poppler 和 perf 版本，增加 docx／pptx／lxml／ImageMagick 等任务依赖 |
| 重复与汇总 | 每路五次独立运行；热点合并原始 period，Topdown 取五次 ALL 均值 | 每项每路一次独立采集，内部十轮回放；热点按 ROI period，Topdown 取本次 ALL |
| 采集 | perf：cycles:u、49 Hz、DWARF；DevKit：CPU 0–7、1 秒间隔 | 沿用相同工具参数，perf 与 DevKit 分开执行，控制器 CPU 9 |
| 窗口 | 既有完整循环 ROI，包含 reset 和循环检查 | perf 仅 workflow 区间并集，排除 reset、准备、归档；Topdown 为完整按核包络 |

本节描述扩展工作流后的负载变化；新任务也带来输入组织和文档规模变化，结果不作为仅改变一个操作的控制实验。单次 DocOps 采集不套用原七例的五次稳定性结论。

### 7.2 实际脚本与工具软件栈

原 OPM 主要经过 PDF 字段检查、填写、Pillow 转换与渲染检查；TLC 主要经过工作簿检查、增强、openpyxl 保存、Calc 重算与缓存／CSV 验证。实际脚本与原生库组成如下，百分比均为完整 perf ROI 的叶 DSO 原始周期权重。

| 原始基准 | 主要脚本／进程 | 主要原生组件 |
|---|---|---|
| OPM | convert_pdf_to_images.py 38.85%; fill_fillable_fields.py 38.44%; verify_pdf_batch.py 12.26%; pdftoppm 8.03% | Python 50.41%; zlib 25.18%; Pillow 14.61%; Poppler 6.23% |
| TLC | enhance_workbook.py 22.01%; inspect_xlsx_structure.py 12.69%; recalc.py 11.60%; inspect_xlsx_features.py 10.57% | Python 79.26%; LibreOffice 6.43%; Expat 5.65%; ElementTree 3.68% |

| 任务与操作 | 实际脚本／工具链 | 主要原生组件 |
|---|---|---|
| 031 听证材料包扁平化发布 | build_public_packet.py；PDF 渲染；validate_public_packet.py | zlib 66.25%; Python 20.08%; PNG 8.68%; Poppler 2.56% |
| 037 公交绕行材料修复 | build_bus_detour_packet.py；PDF 渲染；validate_bus_detour_packet.py | zlib 52.92%; Python 29.90%; PNG 10.27%; Poppler 4.61% |
| pdfwf005 结算材料包重建 | rebuild_closeout_binder.py；PDF 检查；图片／拼图／诊断 | Python 31.74%; ImageMagick 25.96%; zlib 23.67%; PNG 11.60% |

| 任务与操作 | 实际脚本／工具链 | 主要原生组件 |
|---|---|---|
| 013 采购投标评审发布 | build_public_bid_workbook.py；recalc.py；verify_public_bid_workbook.py；PDF／拼图 | zlib 31.66%; Python 19.77%; ImageMagick 13.43%; LibreOffice 10.20% |
| 014 灾害补助公开发布 | build_disaster_release_v1.py；recalc.py；finalize_disaster_release_ooxml_v3.py；validate_disaster_release_v1.py／渲染 | zlib 30.54%; Python 25.49%; LibreOffice 17.51%; PNG 7.57% |
| 016 预测模型情景级联 | build_forecast_dashboard_v1.py；recalc.py；测试副本切换情景并重算 | Python 47.65%; LibreOffice 27.74%; libc 8.81%; loader 3.62% |

| 任务与操作 | 实际脚本／工具链 | 主要原生组件 |
|---|---|---|
| 001 受控文档发布修复 | create_packet.py；render_docx.py；结构与渲染检查 | zlib 44.27%; Python 18.74%; LibreOffice 11.65%; libc 7.16% |
| 003 公开记录元数据清理 | build_public_packet.py；audit_public_packet.py；render_docx.py | zlib 44.62%; Python 14.91%; LibreOffice 14.23%; PNG 9.05% |
| 009 事件手册发布 | build_incident_manual_publication.py；render_docx.py；validate_incident_manual_publication.py | zlib 44.39%; PNG 19.00%; LibreOffice 9.11%; Python 8.86% |

| 任务与操作 | 实际脚本／工具链 | 主要原生组件 |
|---|---|---|
| 021 庇护所无障碍整改 | build_public_shelter_briefing.py；validate_public_shelter_briefing.py；soffice.py／图片／拼图 | Poppler 27.74%; LibreOffice 24.32%; Python 15.95%; ImageMagick 10.59% |
| 026 气候披露图表重建 | build_climate_disclosure.py；转 PDF／图片；qa_climate_disclosure.py | Poppler 36.90%; Python 20.97%; LibreOffice 19.20%; libc 6.60% |
| 029 季度业务回顾发布 | build_release_deck.py；validate_release_deck.py；转 PDF／图片 | Python 36.96%; LibreOffice 32.15%; libc 7.61%; Poppler 5.08% |

### 7.3 热点函数：原基准清单还覆盖哪些工作

函数按“物理叶函数完整名称＋DSO 文件名”精确匹配。共同 Top-10 数比较两份前十名单；“基准清单在新任务的占比”则统计原基准 Top-10 函数在新任务全部采样中的周期权重，匹配函数即使掉出新 Top-10 仍计入该清单占比。该占比只说明这十个具体函数的权重，不等于任务或切片覆盖率。

| 基准 | 原基准前五热点 | 原 Top-10 合计占比 |
|---|---|---|
| OPM | `_PyEval_EvalFrameDefault` 16.52%; `longest_match` 10.07%; `deflate_slow` 7.04%; `ImagingResampleHorizontal_8bpc` 5.41%; `ImagingZipEncode` 4.70% | 57.81% |
| TLC | `_PyEval_EvalFrameDefault` 23.65%; `gc_collect_main` 5.13%; `subtype_traverse` 3.90%; `_Py_dict_lookup` 3.57%; `deduce_unreachable` 3.23% | 49.50% |

| 任务 | OPM Top-10 共同数 | OPM 清单在新任务占比 |
|---|---|---|
| 031 | 3/10 | 67.11% |
| 037 | 4/10 | 56.07% |
| pdfwf005 | 5/10 | 25.93% |

| 任务 | 新任务前三热点及周期占比 |
|---|---|
| 031 | `longest_match` 56.95%; `png_write_find_filter` 8.68%; `deflate_slow` 6.83% |
| 037 | `longest_match` 45.90%; `png_write_find_filter` 10.27%; `deflate_slow` 4.64% |
| pdfwf005 | `HorizontalFilter._omp_fn.0` 12.59%; `VerticalFilter._omp_fn.0` 11.46%; `png_write_find_filter` 10.57% |

| 任务 | TLC Top-10 共同数 | TLC 清单在新任务占比 |
|---|---|---|
| 013 | 1/10 | 6.12% |
| 014 | 2/10 | 8.37% |
| 016 | 2/10 | 12.06% |

| 任务 | 新任务前三热点及周期占比 |
|---|---|
| 013 | `longest_match` 21.24%; `png_write_find_filter` 8.38%; `HorizontalFilter._omp_fn.0` 8.05% |
| 014 | `longest_match` 22.52%; `png_write_find_filter` 7.57%; `deflate_slow` 4.90% |
| 016 | `_PyEval_EvalFrameDefault` 4.57%; `_Py_dict_lookup` 3.70%; `std::_Rb_tree<int, int, std::_Identity<int>, std::less<int>, std::allocator<int> >::_M_get_insert_u…` 3.11% |

| 任务 | OPM Top-10 共同数 | OPM 清单在新任务占比 | TLC Top-10 共同数 | TLC 清单在新任务占比 |
|---|---|---|---|---|
| 001 | 4/10 | 45.33% | 2/10 | 4.61% |
| 003 | 3/10 | 44.19% | 0/10 | 2.00% |
| 009 | 4/10 | 45.80% | 1/10 | 3.89% |

| 任务 | 新任务前三热点及周期占比 |
|---|---|
| 001 | `longest_match` 36.05%; `deflate_slow` 5.87%; `png_write_find_filter` 5.34% |
| 003 | `longest_match` 33.55%; `png_write_find_filter` 9.05%; `deflate_slow` 5.91% |
| 009 | `longest_match` 27.62%; `png_write_find_filter` 19.00%; `deflate_slow` 10.59% |

| 任务 | OPM Top-10 共同数 | OPM 清单在新任务占比 | TLC Top-10 共同数 | TLC 清单在新任务占比 |
|---|---|---|---|---|
| 021 | 1/10 | 2.59% | 1/10 | 3.90% |
| 026 | 2/10 | 4.96% | 2/10 | 6.34% |
| 029 | 1/10 | 7.36% | 2/10 | 12.53% |

| 任务 | 新任务前三热点及周期占比 |
|---|---|
| 021 | `Splash::pipeRun(SplashPipe*)` 9.94%; `VerticalFilter._omp_fn.0` 6.96%; `Splash::pipeRunAARGB8(SplashPipe*)` 6.12% |
| 026 | `Splash::pipeRunAARGB8(SplashPipe*)` 12.81%; `Splash::pipeRun(SplashPipe*)` 11.74%; `_PyEval_EvalFrameDefault` 2.75% |
| 029 | `_PyEval_EvalFrameDefault` 5.31%; `_Py_dict_lookup` 3.45%; `oox::drawingml::table::applyTableStylePart(oox::core::XmlFilterBase const&, oox::drawingml::FillPro…` 2.00% |

PDF 扩展后，031／037 的 zlib 压缩与 PNG 编码更突出；pdfwf005 的 ImageMagick 横向、纵向滤波进入前列。它们与 OPM 保留解释执行和压缩共性，同时从表单填写扩展到材料包处理、渲染与拼图。
Excel 的 013／014 加入较重的 PDF／图片交付路径，出现 zlib、PNG 与 ImageMagick 热点；016 更突出 Python 对象处理与 Calc。相同 XLSX 格式并不自动延续 TLC 的大型工作簿读写热点权重。
Word 三项以压缩和 PNG 编码为主要热点，与 OPM 的压缩路径有共性；PPT 的 021／026 更突出 Poppler 栅格化和图像处理，029 则出现解释器、字典查找和 DrawingML 表格样式处理。共享 LibreOffice、Python 或 Poppler，仍可进入不同业务模块和函数路径。

### 7.4 Topdown：先看指标变化，再看辅助相似度

下表先列出基准五次均值（除 IPC 外为百分数），随后以新任务减去基准均值展示变化；完整十四个配置的九项指标见实验数据记录。

| 基准 | IPC | Bad Spec. | Frontend | Backend | Retiring |
|---|---|---|---|---|---|
| OPM | 1.226 | 4.676 | 18.120 | 56.762 | 20.440 |
| TLC | 1.234 | 2.478 | 18.100 | 58.846 | 20.572 |

IPC 展示相对变化，其余展示百分点变化。Bound 总变差＝四顶层 Bound 绝对差之和的一半，范围为 0–100 个百分点；它描述四类分布的差异，不代表相同比例的 CPU 工作或函数发生了改变。

| 任务 | 对照 | IPC 变化 | Frontend Δpp | Backend Δpp | Bound 总变差 pp |
|---|---|---|---|---|---|
| 031 | OPM | -13.5% | -9.18 | +13.72 | 13.72 |
| 037 | OPM | -19.2% | -7.84 | +13.89 | 13.89 |
| pdfwf005 | OPM | -8.6% | -6.15 | +7.87 | 7.87 |

| 任务 | 对照 | IPC 变化 | Frontend Δpp | Backend Δpp | Bound 总变差 pp |
|---|---|---|---|---|---|
| 013 | TLC | -23.0% | -3.05 | +6.81 | 7.74 |
| 014 | TLC | -31.9% | +0.31 | +5.24 | 6.54 |
| 016 | TLC | -41.7% | +5.30 | +1.51 | 8.50 |

| 任务 | 对照 | IPC 变化 | Frontend Δpp | Backend Δpp | Bound 总变差 pp |
|---|---|---|---|---|---|
| 001 | OPM | -27.4% | -3.26 | +10.43 | 10.43 |
| 001 | TLC | -27.9% | -3.24 | +8.34 | 8.90 |
| 003 | OPM | -23.3% | -2.94 | +9.13 | 9.12 |
| 003 | TLC | -23.8% | -2.92 | +7.04 | 7.77 |
| 009 | OPM | -11.9% | -0.50 | +4.75 | 4.75 |
| 009 | TLC | -12.5% | -0.48 | +2.66 | 3.06 |

| 任务 | 对照 | IPC 变化 | Frontend Δpp | Backend Δpp | Bound 总变差 pp |
|---|---|---|---|---|---|
| 021 | OPM | -6.2% | -1.85 | +5.33 | 5.33 |
| 021 | TLC | -6.8% | -1.83 | +3.24 | 3.25 |
| 026 | OPM | -16.8% | +0.90 | +4.28 | 5.18 |
| 026 | TLC | -17.3% | +0.92 | +2.19 | 3.58 |
| 029 | OPM | -25.8% | +2.86 | +3.79 | 6.65 |
| 029 | TLC | -26.3% | +2.88 | +1.70 | 5.36 |

031／037 相比 OPM，Frontend 分别下降约 9.18／7.84 pp，Backend 上升约 13.72／13.89 pp；016 相比 TLC，Frontend 上升约 5.30 pp，IPC 下降约 41.7%。这些差异通过指标原值和百分点变化能够直接看到，不被接近 1 的余弦值掩盖。
PPT 021 与 029 的四维 Bound 余弦约 0.9955，但已解析 Top-10 仅共享两个函数。四维余弦反映粗粒度分布方向，不能代替对软件模块和具体函数的比较；详细余弦、Jaccard 与全部指标差值仍保留在数据记录。

### 7.5 逐点过程与本节结论

本批共保存 533 个真实过程点，每项 20–110 个。以下展示材料包、级联重算和两种演示文稿任务的四顶层 Bound 过程；完整十二项九指标曲线在实验数据记录。每项仍是一次独立采集，编号点不作为独立重复。

![扩展操作 031 的真实 Topdown 过程点](../analysis/docops/processed/task-operation-expansion-20261104/figures/031-bounds.svg)

![扩展操作 016 的真实 Topdown 过程点](../analysis/docops/processed/task-operation-expansion-20261104/figures/016-bounds.svg)

![扩展操作 021 的真实 Topdown 过程点](../analysis/docops/processed/task-operation-expansion-20261104/figures/021-bounds.svg)

![扩展操作 029 的真实 Topdown 过程点](../analysis/docops/processed/task-operation-expansion-20261104/figures/029-bounds.svg)

**跨行业输入与扩展任务操作回答两个层次的问题。** 原七例表明，保持任务形态时，更换行业输入仍延续主要热点；本节进一步表明，改变发布、渲染、重算或文稿对象处理流程后，即使文件格式或公共工具相同，具体热点和流水线特征也会变化。
Word／PPT 已从待测场景进入实测覆盖。当前证据支持按实际操作和执行路径扩展负载：保留已有解释执行、XML、压缩等共性，并补充材料包、图像滤波、幻灯片栅格化、DrawingML 对象与情景重算等路径。连续长文档分页等机制是否成为主导，仍由具体任务的实测结果判断。
[完整扩展实验记录](experimental-results.md#九扩展任务操作十二项-docops-完整记录)；[机器结果与来源绑定](../analysis/docops/processed/task-operation-expansion-20261104/comparison.json)。
