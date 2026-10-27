# 文档解析类 Agent 代表性评估报告

本评估以原有 PDF 表单处理和 XLSX 工作簿增强任务为基准，引入不同领域的真实文档输入，通过 Agent 生成轨迹、容器内轨迹回放和原生热点采样，考察原有用例所体现的主要计算机制在跨领域输入下的代表性。
评估重点是主要热点脚本、库和函数是否共同出现，以及它们对应的文档处理机制是否延续。

## 一、数据集选择与领域覆盖

选取数据集时同时考虑来源、领域覆盖、数据规模和任务形态。XLSX 选用百万单元格量级的真实业务工作簿，覆盖明细记录与统计发布表；PDF 选用具有原生可填写字段的公开业务表单，覆盖不同页数、字段规模和字段类型。在更换业务数据的同时，延续原有工作簿增强与批量表单处理任务。

### XLSX：四个领域的真实工作簿

| 数据集 | 领域与来源 | 输入规模 | 数据组织与任务 |
|---|---|---|---|
| TLC（原基准） | 交通出行；NYC TLC | 7 个工作表；主表 100,000 行 × 25 列，约 250 万单元格 | 真实出租车行程样本及分组汇总；新增运营 Summary、指标、情景和图表 |
| eGRID | 电力能源；美国 EPA | 11 个工作表；约 273 万非空单元格 | 机组、发电机、电厂与区域统计；新增能源业务 Summary |
| HR Metro | 就业与工资；美国 BLS OEWS | 4 个工作表；主表 150,023 条记录、32 列；约 421 万非空单元格 | 都会区／非都会区职业就业与工资统计；新增 Workforce Summary |
| Industry Productivity | 产业生产率；美国 BLS | 3 个工作表；长表约 56.7 万条记录、9 列；约 580 万非空单元格 | 年度宽表与机器可读长表，涵盖生产率、产出、工时、就业和劳动补偿；新增产业 Summary |

TLC 保留基于真实出行记录构建的原有业务工作簿；三个新增 XLSX 使用发布方原始工作簿，保留原有工作表和数据，由 Agent 新增业务 Summary、公式、情景控制和图表。各工作簿均具有百万级单元格规模，为读取、解析、对象构建、保存和重算提供实际负载。

### PDF：三类业务表单

| 数据集 | 领域与发布机构 | 固定版本 | 规模与批处理规模 |
|---|---|---|---|
| OPM OF-306（原基准） | 联邦雇佣申报；美国 OPM | 08/2023 | 3 页、38 个字段；10 条记录 |
| IRS W-4 | 员工税务预扣；美国 IRS | 2026 | 5 页、48 个字段；10 条记录 |
| SBA Form 1919 | 小企业贷款申请；美国 SBA | 04/2024 可填写版本 | 7 页、127 个字段；10 条记录 |

PDF 使用真实表单结构和十条虚构业务记录。处理任务包括字段识别、记录到字段的映射、批量填写、逐页渲染和结果验证。

## 二、Agent 执行轨迹生成

原 TLC 和 OPM 沿用原有任务及回放材料。五个新增用例通过 OpenClaw Agent 实际执行生成轨迹，每个数据集配置独立提示词，沿用原有任务的组织结构，明确输入、业务指标或字段、输出位置、交付物及验收要求。
XLSX 提示词要求保留原表，新增业务 Summary、跨表公式、情景参数、图表和格式，并使用 XLSX Skill 重算和验证。PDF 提示词要求使用 PDF Skill 完成字段检查、字段抽取、十条记录的填写与渲染，并验证填写结果。Agent 在任务执行中自行编写数据集对应的业务 helper 和批处理脚本，调用 Skill 工具，直至业务验收完成。
执行过程中保存 trajectory、tool events、生成脚本及其修订、输入与提示词哈希、运行环境和验收结果。随后选取成功轨迹，将其输入、业务脚本和工具调用与回放配置关联冻结。

| 新数据集 | 采用的成功轨迹 | Agent 生成的业务脚本 |
|---|---|---|
| eGRID | `xlsx-egrid-20261027T032347Z-225eb8e9` | `helpers/enhance_energy_report_v2.py` |
| HR Metro | `xlsx-hr_metro-20261027T042913Z-2c0c625f` | `helpers/enhance_workforce_v2.py` |
| Industry Productivity | `xlsx-industry_productivity-20261027T015504Z-769d363e` | `helpers/enhance_workbook_v1.py` |
| IRS W-4 | `pdf-irs_w4-20261027T021455Z-c206db3d` | `build_field_values.py、run_batch.py` |
| SBA 1919 | `pdf-sba1919-20261027T021613Z-ccd6fc4e` | `build_field_values.py、run_batch.py` |

## 三、基于轨迹的容器化回放

回放从冻结轨迹中载入输入、工具调用、业务 helper 和命令参数，按文档处理阶段执行。轨迹中的内联 Python 代码整理为独立脚本，便于运行、归档和热点归属；Agent 生成的业务 helper 与冻结的 Skill 工具随镜像一起安装。回放直接执行这些脚本和工具，无需再次调用模型。
一个容器镜像支持七个用例。旧 TLC/OPM 使用保留的 document-oe 入口；新增五例通过公共入口选择数据集，每个数据集拥有独立执行器、脚本、Skill、输入及验证器。每轮重建工作区，在同一软件环境中完成处理与业务验证。

| 阶段 | XLSX 回放操作 | PDF 回放操作 |
|---|---|---|
| P01：检查输入 | 运行结构与特征检查脚本，读取原始工作簿 | 检查可填写字段、提取字段结构、渲染模板 |
| P02：生成业务内容 | 执行 Agent helper，新增 Summary、公式、情景和图表并保存 | 执行 Agent helper，为十条记录生成字段值 JSON |
| P03：重算或批处理 | 调用 `recalc.py` 和 LibreOffice，检查公式/缓存并导出本轮 CSV | 执行批处理脚本，逐条调用填写工具与渲染工具 |
| P04：验证与交付 | 验证业务指标、公式缓存、CSV 和交付物，生成摘要 | 验证填写字段、保护字段、PDF/PNG 与批次摘要 |

软件环境固定为 Python 3.12.3、openpyxl 3.1.5、LibreOffice 25.8.7.3 和 Poppler 23.12.0。XLSX 主要调用 openpyxl 与 LibreOffice；PDF 主要调用 pypdf、pdf2image、Pillow 和 Poppler。
回放记录循环开始与结束的单调时钟标记。热点统计覆盖正式循环中的工作负载进程及线程，归档和循环外独立审计在统计区间之外完成。

## 四、热点函数对比与代表性评估

本轮比较三个 PDF（OPM、W-4、SBA 1919，均为十条记录）以及 XLSX 的 TLC 与 HR Metro。旧 OPM/TLC 使用已有采样结果，新增用例使用当前轨迹回放的采样结果。
采用 perf 的 `cycles:u` 事件采集原生调用栈，按物理叶函数统计热点，并关联脚本、进程和动态库。表中比例为正式循环内已观测用户态样本的 period 占比；Top-10/Top-20 用于查看主要函数的共同出现情况，权重用于描述各自分布。

| 配置 | ROI 样本数 | 采样配置 |
|---|---:|---|
| opm-n10 | 6,413 | 历史 2 次重复，各 3 轮，99 Hz |
| tlc | 73,622 | 历史 2 次重复，各 1 轮，49 Hz |
| irs_w4 | 711 | 单轮，49 Hz；执行与业务验证成功 |
| sba1919 | 927 | 单轮，49 Hz；执行与业务验证成功 |
| hr_metro | 40,840 | 单轮，49 Hz；执行与业务验证成功 |

### PDF（全部 N=10）

#### 主要脚本／进程

| 实际脚本／程序（历史仅有角色时注明） | opm-n10 | irs_w4 | sba1919 |
|---|---:|---:|---:|
| `convert_pdf_to_images.py` | 36.69% | 44.32% | 44.97% |
| `fill_fillable_fields.py` | 35.05% | 35.81% | 25.72% |
| `pdftoppm` | 13.33% | 6.25% | 16.42% |
| `verify_pdf_batch.py` | 11.11% | 13.36% | 11.74% |
| `extract_form_field_info.py` | 1.71% | — | 0.00% |
| `check_fillable_fields.py` | 1.66% | 0.00% | 1.12% |

“—”表示该采样结果中没有对应标签。

#### 主要库

| 库 | opm-n10 | irs_w4 | sba1919 |
|---|---:|---:|---:|
| libpython | 48.49% | 46.72% | 36.12% |
| zlib | 16.55% | 26.44% | 22.47% |
| Pillow | 16.97% | 19.23% | 23.57% |
| Poppler | 8.58% | 3.82% | 7.09% |
| FreeType | 2.79% | 1.32% | 8.49% |
| libc | 3.04% | 1.94% | 1.62% |
| unknown | 2.60% | 0.23% | 0.14% |
| other | 0.54% | 0.21% | 0.43% |

#### 主要热点函数（各配置 Top-10 的并集）

| 库／物理叶函数 | opm-n10 | irs_w4 | sba1919 |
|---|---:|---:|---:|
| `libpython / _PyEval_EvalFrameDefault` | 15.33% | 22.85% | 13.73% |
| `zlib / longest_match` | 7.63% | 9.88% | 10.77% |
| `Pillow / ImagingResampleHorizontal_8bpc` | 7.12% | 9.06% | 9.57% |
| `zlib / deflate_slow` | 4.88% | 6.58% | 6.73% |
| `Pillow / ImagingZipEncode` | 4.17% | 4.53% | 6.29% |
| `zlib / compress_block` | 0.97% | 4.67% | 1.91% |
| `Pillow / ImagingResampleVertical_8bpc` | 3.31% | 4.05% | 4.21% |
| `FreeType / gray_render_line` | 0.65% | 未采到 | 2.82% |
| `zlib / slide_hash` | 1.35% | 2.60% | 1.90% |
| `libpython / do_super_lookup` | 0.15% | 未采到 | 2.55% |
| `zlib / inflate_fast` | 1.06% | 2.26% | 0.44% |
| `Poppler / Splash::pipeRunAARGB8(SplashPipe*)` | 1.84% | 1.25% | 1.99% |
| `libpython / gc_collect_main` | 1.95% | 1.93% | 1.24% |
| `FreeType / gray_set_cell` | 0.42% | 未采到 | 1.94% |
| `libc / __memcpy_generic` | 1.65% | 0.46% | 0.43% |
| `Poppler / Splash::compositeBackground(unsigned char const*)` | 1.60% | 0.68% | 1.45% |

#### 共同热点

| 对照 | Top-10 共同函数数 | 旧 Top-10 在新 Top-20 中出现 |
|---|---:|---:|
| opm-n10 → irs_w4 | 7 / 10 | 9 / 10 |
| opm-n10 → sba1919 | 7 / 10 | 9 / 10 |

### XLSX

#### 主要脚本／进程

| 实际脚本／程序（历史仅有角色时注明） | tlc | hr_metro |
|---|---:|---:|
| `recalc.py` | 11.49% | 24.80% |
| `enhance_workforce_v2.py` | — | 24.74% |
| `enhance_workbook.py` | 21.87% | — |
| `inspect_xlsx_structure.py` | 12.46% | 10.39% |
| `verify_xlsx_enhanced.py` | 10.24% | 11.30% |
| `inspect_xlsx_formulas.py` | 8.22% | 10.75% |
| `inspect_xlsx_features.py` | 10.41% | 10.25% |
| `write_xlsx_summary.py / export_xlsx.py（历史合并角色）` | 8.49% | — |
| `inspect_xlsx_cached_values.py` | 8.12% | — |
| `soffice.bin` | 4.59% | 3.65% |
| `LibreOffice 线程` | 3.34% | — |
| `unknown:thread-pool` | — | 2.54% |
| `unknown:Parser` | — | 1.54% |
| `python-unknown-script` | 0.77% | — |

“—”表示该采样结果中没有对应标签。

#### 主要库

| 库 | tlc | hr_metro |
|---|---:|---:|
| libpython | 78.45% | 79.63% |
| LibreOffice | 6.42% | 6.52% |
| expat | 5.86% | 4.97% |
| ElementTree | 3.11% | 3.52% |
| libc | 1.50% | 2.35% |
| unknown | 2.09% | 0.09% |
| zlib | 1.73% | 2.04% |

#### 主要热点函数（各配置 Top-10 的并集）

| 库／物理叶函数 | tlc | hr_metro |
|---|---:|---:|
| `libpython / _PyEval_EvalFrameDefault` | 23.04% | 21.95% |
| `libpython / gc_collect_main` | 5.28% | 7.22% |
| `libpython / _Py_dict_lookup` | 3.64% | 4.92% |
| `libpython / subtype_traverse` | 3.84% | 4.70% |
| `libpython / deduce_unreachable` | 3.27% | 4.35% |
| `libpython / visit_reachable` | 2.79% | 3.26% |
| `libpython / _PyObject_GenericGetAttrWithDict` | 1.87% | 1.16% |
| `libpython / tupledealloc` | 1.65% | 1.70% |
| `libpython / dictiter_iternextkey` | 1.59% | 0.88% |
| `libpython / PyObject_GC_Del` | 1.53% | 0.99% |
| `expat / storeAtts` | 1.41% | 1.19% |
| `ElementTree / checkpath` | 0.97% | 1.13% |

#### 共同热点

| 对照 | Top-10 共同函数数 | 旧 Top-10 在新 Top-20 中出现 |
|---|---:|---:|
| tlc → hr_metro | 8 / 10 | 10 / 10 |

### 热点函数与执行脚本的对应关系

#### irs_w4

| 实际脚本／程序 | 库 | 物理叶函数 | ROI 占比 |
|---|---|---|---:|
| `fill_fillable_fields.py` | libpython | `_PyEval_EvalFrameDefault` | 16.21% |
| `convert_pdf_to_images.py` | zlib | `longest_match` | 9.88% |
| `convert_pdf_to_images.py` | Pillow | `ImagingResampleHorizontal_8bpc` | 9.06% |
| `verify_pdf_batch.py` | libpython | `_PyEval_EvalFrameDefault` | 6.63% |
| `convert_pdf_to_images.py` | zlib | `deflate_slow` | 6.58% |
| `convert_pdf_to_images.py` | zlib | `compress_block` | 4.67% |
| `convert_pdf_to_images.py` | Pillow | `ImagingZipEncode` | 4.53% |
| `convert_pdf_to_images.py` | Pillow | `ImagingResampleVertical_8bpc` | 4.05% |
| `convert_pdf_to_images.py` | zlib | `slide_hash` | 2.60% |
| `verify_pdf_batch.py` | zlib | `inflate_fast` | 2.26% |

#### sba1919

| 实际脚本／程序 | 库 | 物理叶函数 | ROI 占比 |
|---|---|---|---:|
| `convert_pdf_to_images.py` | zlib | `longest_match` | 10.77% |
| `convert_pdf_to_images.py` | Pillow | `ImagingResampleHorizontal_8bpc` | 9.57% |
| `fill_fillable_fields.py` | libpython | `_PyEval_EvalFrameDefault` | 8.24% |
| `convert_pdf_to_images.py` | zlib | `deflate_slow` | 6.73% |
| `convert_pdf_to_images.py` | Pillow | `ImagingZipEncode` | 6.29% |
| `verify_pdf_batch.py` | libpython | `_PyEval_EvalFrameDefault` | 5.33% |
| `convert_pdf_to_images.py` | Pillow | `ImagingResampleVertical_8bpc` | 4.21% |
| `pdftoppm` | FreeType | `gray_render_line` | 2.82% |
| `fill_fillable_fields.py` | libpython | `do_super_lookup` | 2.55% |
| `pdftoppm` | Poppler | `Splash::pipeRunAARGB8(SplashPipe*)` | 1.99% |

#### hr_metro

| 实际脚本／程序 | 库 | 物理叶函数 | ROI 占比 |
|---|---|---|---:|
| `enhance_workforce_v2.py` | libpython | `_PyEval_EvalFrameDefault` | 7.39% |
| `recalc.py` | libpython | `_PyEval_EvalFrameDefault` | 6.31% |
| `verify_xlsx_enhanced.py` | libpython | `_PyEval_EvalFrameDefault` | 2.27% |
| `inspect_xlsx_formulas.py` | libpython | `_PyEval_EvalFrameDefault` | 2.12% |
| `inspect_xlsx_features.py` | libpython | `_PyEval_EvalFrameDefault` | 1.97% |
| `inspect_xlsx_structure.py` | libpython | `_PyEval_EvalFrameDefault` | 1.90% |
| `recalc.py` | libpython | `_Py_dict_lookup` | 1.87% |
| `recalc.py` | libpython | `gc_collect_main` | 1.86% |
| `recalc.py` | libpython | `subtype_traverse` | 1.29% |
| `enhance_workforce_v2.py` | libpython | `gc_collect_main` | 1.15% |


### 评估结论

跨领域 PDF 输入延续了表单处理任务的主要热点：`convert_pdf_to_images.py`、`fill_fillable_fields.py`、`verify_pdf_batch.py` 与 `pdftoppm`，对应 Python 解释执行、图片缩放、压缩编码和 PDF 渲染。W-4、SBA 1919 与 OPM 的 Top-10 函数分别有 7、7 个共同项，旧 Top-10 在两项新输入的 Top-20 中分别出现 9、9 个。
HR Metro 与 TLC 共同表现为 Python 工作簿处理主导，主要库包括 libpython、Expat、ElementTree、zlib 和 LibreOffice。共同热点涵盖解释器执行、字典与对象操作、垃圾回收和 XML 解析；Top-10 函数有 8 个共同项，TLC 的 Top-10 中有 10 个出现在 HR Metro 的 Top-20 中。
**本轮结果支持原 PDF 与 XLSX 用例在主要原生计算机制层面的跨领域代表性：更换真实业务输入后，主要热点仍集中于相同的文档处理工具链和底层计算路径。**

### 采样与证据说明

本轮采用单次新用例采样，重点识别共同热点；HR 采样含丢样记录，权重用于粗粒度观察。历史内联函数已归并到对应实体函数后参与比较。完整采样质量、版本、ROI、未知项及来源哈希保留在机器可读结果中。
当前回放镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。

数据与追溯：[机器可读对比结果](comparison.json)、[分析构建记录](build.json)、[轨迹来源与回放说明](../../../../agent/README.md)。
