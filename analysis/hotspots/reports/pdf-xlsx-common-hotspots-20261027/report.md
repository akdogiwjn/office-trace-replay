# 文档解析类 Agent 代表性评估报告

本评估以原有 PDF 表单处理和 XLSX 工作簿增强任务为基准，引入不同领域的真实文档输入，通过 Agent 生成轨迹、容器内轨迹回放和原生热点采样，考察原有用例所体现的主要计算机制在跨领域输入下的代表性。
评估重点是主要热点脚本、库和函数是否共同出现，以及它们对应的文档处理机制是否延续。

## 一、数据集选择与领域覆盖

选取数据集时同时考虑来源、领域覆盖、数据规模和任务形态。XLSX 选用百万单元格量级的真实业务工作簿，覆盖明细记录与统计发布表；PDF 选用具有原生可填写字段的公开业务表单，覆盖不同页数、字段规模和字段类型。在更换业务数据的同时，延续原有工作簿增强与批量表单处理任务。

这组输入按“业务领域不同、文档处理任务相近”选择。XLSX 从原有交通出行扩展到电力能源、就业工资和产业生产率，选择具有真实指标、分类维度和既有数据表的公开工作簿，便于继续执行保留原表、新增 Summary、公式、情景和图表的任务。PDF 从雇佣申报扩展到税务预扣和企业贷款申请，保留字段映射、批量填写、渲染与验证的共同任务形态。下表左侧资料说明输入本身的特征，右侧给出本评估据此作出的选择。

| 数据集 | 发布方说明与来源 | 本评估的选择理由 |
|---|---|---|
| TLC | 官方行程数据包含上下车时间与地点、里程、分项车费和乘客数。[NYC TLC 数据说明](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) | 保留原交通业务基准；行程明细与已有分组汇总可以自然支撑运营指标、收入情景和图表。 |
| eGRID | EPA 数据涵盖发电量、排放、排放率、热输入与能源结构，并提供详细 XLSX。[EPA 数据介绍](https://www.epa.gov/egrid)、[详细数据下载](https://www.epa.gov/egrid/detailed-data) | 引入能源领域和多层级数据表；发电、排放等现成业务量适合新增跨表指标与能源 Summary。 |
| HR Metro | BLS 提供都会区／非都会区职业就业与工资估计及 XLSX，包括工资分位数。[BLS 地区数据说明](https://www.bls.gov/OES/current/oessrcma.htm)、[下载表目录](https://www.bls.gov/oes/tables.htm) | 引入区域×职业的劳动市场统计，覆盖分类编码、就业量、工资和抑制标记；可自然构建 Workforce Summary。 |
| Industry Productivity | BLS 发布细分行业生产率 XLSX，含就业、工时、产出、劳动补偿的水平与指数序列。[BLS 表格目录](https://www.bls.gov/productivity/tables/home.htm)、[指标说明](https://www.bls.gov/news.release/prin.nr0.htm) | 引入产业长期序列及宽表／长表两种组织形式；现成指标支持年度选择、变化率、情景和产业 Summary。 |
| OPM OF-306 | 用于联邦雇佣适任性申报，包含身份信息与背景问题。[OPM 表单说明](https://www.opm.gov/forms/pdf_fill/of0306.pdf) | 保留原 PDF 基准，覆盖身份文本、日期、选择项及背景声明的填写与验证。 |
| IRS W-4 | 用于向雇主声明联邦所得税预扣信息。[IRS 用途说明](https://www.irs.gov/forms-pubs/about-form-w-4) | 加入税务领域的身份、申报状态、金额与扣除项，继续执行逐条字段映射、填写和逐页渲染。 |
| SBA 1919 | 收集小企业 7(a) 贷款申请人、所有人、贷款需求及债务等信息。[SBA 用途说明](https://www.sba.gov/document/sba-form-1919-borrower-information-form) | 加入企业融资领域与更长的多页表单，覆盖企业／个人信息及更多选择项；使用仓库冻结的 04/2024 可填写版本。 |

XLSX 的规模同时考虑实际文档负载：本仓库四例约为 250 万至 580 万单元格，使各领域均具有百万级工作簿的读取、对象构建和保存工作量。PDF 保留 3／5／7 页及 38／48／127 个字段的结构差异，每轮统一处理十条虚构记录。以下精确规模、表单版本和字段数来自仓库冻结输入；官方链接用于支撑业务用途和数据内容。

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

本轮覆盖七个正式用例。PDF 为 OPM、W-4、SBA 1919，各在五个独立容器中执行一轮，每轮处理十条记录，共 15 次成功运行；按各轮正式 ROI 的原始 sample period 合并统计。XLSX 为 TLC、HR Metro、eGRID 和 Industry Productivity，沿用已有同镜像单轮采样。主表以五轮合并 OPM 和单轮 TLC 为基准；七例使用同一回放镜像和 49 Hz 采样配置，工作负载绑定逻辑 CPU 0–7，监测进程绑定 CPU 9。
采用 perf 的 `cycles:u` 事件采集原生调用栈，按物理叶函数统计热点，并关联脚本、进程和动态库。表中比例为正式循环内已观测用户态样本的 period 占比；Top-10/Top-20 用于查看主要函数的共同出现情况，权重用于描述各自分布。

| 配置 | ROI 样本数 | 采样配置 |
|---|---:|---|
| opm-n10 | 2,736 | 5 次独立重复，每次 1 轮、10 份，49 Hz；全部执行与业务验证成功 |
| irs_w4 | 3,443 | 5 次独立重复，每次 1 轮、10 份，49 Hz；全部执行与业务验证成功 |
| sba1919 | 4,275 | 5 次独立重复，每次 1 轮、10 份，49 Hz；全部执行与业务验证成功 |
| tlc | 33,584 | 单轮，49 Hz；执行与业务验证成功 |
| hr_metro | 40,840 | 单轮，49 Hz；执行与业务验证成功 |
| egrid | 50,874 | 单轮，49 Hz；执行与业务验证成功 |
| industry_productivity | 54,048 | 单轮，49 Hz；执行与业务验证成功 |

### PDF（每例五轮合并，每轮 N=10）

#### 主要脚本／进程

| 实际脚本／程序（历史仅有角色时注明） | opm-n10 | irs_w4 | sba1919 |
|---|---:|---:|---:|
| `convert_pdf_to_images.py` | 38.85% | 44.17% | 44.92% |
| `fill_fillable_fields.py` | 38.44% | 36.41% | 29.00% |
| `pdftoppm` | 8.03% | 6.89% | 14.57% |
| `verify_pdf_batch.py` | 12.26% | 12.40% | 10.64% |
| `check_fillable_fields.py` | 2.16% | 0.00% | 0.61% |

“—”表示该采样结果中没有对应标签。

#### 主要库

| 库 | opm-n10 | irs_w4 | sba1919 |
|---|---:|---:|---:|
| libpython | 50.41% | 45.21% | 37.28% |
| zlib | 25.18% | 23.75% | 23.89% |
| Pillow | 14.61% | 21.71% | 21.22% |
| Poppler | 6.23% | 3.47% | 6.93% |
| FreeType | 1.02% | 2.25% | 6.27% |
| libc | 1.86% | 2.55% | 3.74% |
| ld | 0.18% | 0.73% | 0.35% |

#### 主要热点函数（各配置 Top-10 的并集）

★ 标记原用例 `opm-n10` 的 Top-10，优先按其排名排列；粗体突出这些函数在各列的占比。✓ 表示进入本列数据集的 Top-10；# 为该列函数排名。其余行补充新数据集的 Top-10 函数。

| 库／物理叶函数 | opm-n10 | irs_w4 | sba1919 |
|---|---:|---:|---:|
| ★ #1 · `libpython / _PyEval_EvalFrameDefault` | **16.52% · #1 ✓** | **18.57% · #1 ✓** | **15.02% · #1 ✓** |
| ★ #2 · `zlib / longest_match` | **10.07% · #2 ✓** | **11.14% · #2 ✓** | **12.96% · #2 ✓** |
| ★ #3 · `zlib / deflate_slow` | **7.04% · #3 ✓** | **6.22% · #5 ✓** | **6.12% · #4 ✓** |
| ★ #4 · `Pillow / ImagingResampleHorizontal_8bpc` | **5.41% · #4 ✓** | **8.18% · #3 ✓** | **8.51% · #3 ✓** |
| ★ #5 · `Pillow / ImagingZipEncode` | **4.70% · #5 ✓** | **7.54% · #4 ✓** | **5.78% · #5 ✓** |
| ★ #6 · `libpython / deduce_unreachable` | **3.42% · #6 ✓** | **1.56% · #10 ✓** | **1.47% · #12** |
| ★ #7 · `libpython / gc_collect_main` | **2.92% · #7 ✓** | **1.81% · #9 ✓** | **1.52% · #11** |
| ★ #8 · `zlib / slide_hash` | **2.74% · #8 ✓** | **3.07% · #7 ✓** | **2.82% · #7 ✓** |
| ★ #9 · `Pillow / ImagingResampleVertical_8bpc` | **2.52% · #9 ✓** | **3.26% · #6 ✓** | **4.88% · #6 ✓** |
| ★ #10 · `zlib / inflate_fast` | **2.47% · #10 ✓** | **1.06% · #14** | **0.46% · #33** |
| `Poppler / Splash::pipeRunAARGB8(SplashPipe*)` | 1.08% · #17 | 0.95% · #16 | 2.55% · #8 ✓ |
| `Poppler / Splash::compositeBackground(unsigned char const*)` | 2.44% · #11 | 0.79% · #19 | 1.96% · #9 ✓ |
| `libpython / _Py_dict_lookup` | 0.47% · #31 | 2.44% · #8 ✓ | 1.30% · #13 |
| `FreeType / gray_render_line` | 0.11% · #95 | 0.36% · #42 | 1.93% · #10 ✓ |

#### 共同热点

| 对照 | Top-10 共同函数数 | 旧 Top-10 在新 Top-20 中出现 |
|---|---:|---:|
| opm-n10 → irs_w4 | 9 / 10 | 10 / 10 |
| opm-n10 → sba1919 | 7 / 10 | 9 / 10 |

#### 五轮合并 Top-5

各数据集五轮合并后的 Top-5 有 5 个共同函数；下表为各自 Top-5 的累计占比。

| 数据集 | Top-5 累计 ROI 占比 |
|---|---:|
| opm-n10 | 43.74% |
| irs_w4 | 51.65% |
| sba1919 | 48.40% |

### XLSX（四个领域）

#### 主要脚本／进程

按职责合并不同名称的脚本，占比为对应采样 period 之和；实际脚本保持独立。未归属线程单列。

| 职责 | 对应脚本／程序 | tlc | hr_metro | egrid | industry_productivity |
|---|---|---:|---:|---:|---:|
| 结构检查 | `inspect_xlsx_structure.py` | 12.50% | 10.39% | 0.31% | 8.52% |
| 特征检查 | `inspect_xlsx_features.py` | 10.73% | 10.25% | 10.72% | 8.41% |
| 业务增强 | `enhance_workbook.py`、`enhance_workforce_v2.py`、`enhance_energy_report_v2.py`、`enhance_workbook_v1.py` | 22.12% | 24.74% | 25.25% | 20.38% |
| 重算与缓存扫描 | `recalc.py` | 11.74% | 24.80% | 23.44% | 22.77% |
| 公式检查 | `inspect_xlsx_formulas.py` | 8.08% | 10.75% | 11.43% | 10.07% |
| 缓存值检查 | `inspect_xlsx_cached_values.py` | 7.95% | — | 11.18% | 10.25% |
| 循环内业务验证 | `verify_xlsx_enhanced.py` | 9.98% | 11.30% | 11.87% | 10.29% |
| 摘要生成 | `write_xlsx_summary.py` | 8.57% | 0.00% | 0.00% | 0.00% |
| CSV 导出 | `export_xlsx_csv.py` | 0.77% | 0.00% | 0.19% | 0.00% |
| LibreOffice 主进程 | `soffice.bin` | 4.63% | 3.65% | 3.03% | 4.56% |
| 其他已识别脚本／程序 | 其余已识别程序 | 0.00% | 0.01% | 0.00% | 0.00% |
| 未归属线程／进程 | `unknown:*`（保留未归属状态） | 2.93% | 4.11% | 2.57% | 4.75% |

“—”表示该采样结果中没有对应标签。

#### 主要库

| 库 | tlc | hr_metro | egrid | industry_productivity |
|---|---:|---:|---:|---:|
| libpython | 79.33% | 79.63% | 82.13% | 78.82% |
| LibreOffice | 6.44% | 6.52% | 4.77% | 8.15% |
| expat | 5.65% | 4.97% | 4.84% | 5.36% |
| ElementTree | 3.72% | 3.52% | 3.07% | 2.99% |
| libc | 2.52% | 2.35% | 2.08% | 2.33% |
| zlib | 1.45% | 2.04% | 1.96% | 1.44% |
| other | 0.42% | 0.47% | 0.62% | 0.46% |

#### 主要热点函数（各配置 Top-10 的并集）

★ 标记原用例 `tlc` 的 Top-10，优先按其排名排列；粗体突出这些函数在各列的占比。✓ 表示进入本列数据集的 Top-10；# 为该列函数排名。其余行补充新数据集的 Top-10 函数。

| 库／物理叶函数 | tlc | hr_metro | egrid | industry_productivity |
|---|---:|---:|---:|---:|
| ★ #1 · `libpython / _PyEval_EvalFrameDefault` | **23.83% · #1 ✓** | **21.95% · #1 ✓** | **22.45% · #1 ✓** | **21.58% · #1 ✓** |
| ★ #2 · `libpython / gc_collect_main` | **5.07% · #2 ✓** | **7.22% · #2 ✓** | **7.17% · #2 ✓** | **7.05% · #2 ✓** |
| ★ #3 · `libpython / subtype_traverse` | **3.77% · #3 ✓** | **4.70% · #4 ✓** | **5.40% · #3 ✓** | **4.23% · #4 ✓** |
| ★ #4 · `libpython / _Py_dict_lookup` | **3.71% · #4 ✓** | **4.92% · #3 ✓** | **4.97% · #4 ✓** | **4.91% · #3 ✓** |
| ★ #5 · `libpython / deduce_unreachable` | **3.27% · #5 ✓** | **4.35% · #5 ✓** | **4.48% · #5 ✓** | **4.13% · #5 ✓** |
| ★ #6 · `libpython / visit_reachable` | **2.88% · #6 ✓** | **3.26% · #6 ✓** | **3.21% · #6 ✓** | **3.20% · #6 ✓** |
| ★ #7 · `libpython / _PyObject_GenericGetAttrWithDict` | **2.01% · #7 ✓** | **1.16% · #9 ✓** | **1.28% · #9 ✓** | **1.45% · #8 ✓** |
| ★ #8 · `libpython / dictiter_iternextkey` | **1.90% · #8 ✓** | **0.88% · #16** | **0.70% · #23** | **0.78% · #21** |
| ★ #9 · `libpython / PyObject_GC_Del` | **1.65% · #9 ✓** | **0.99% · #12** | **1.34% · #8 ✓** | **0.98% · #12** |
| ★ #10 · `libpython / tupledealloc` | **1.59% · #10 ✓** | **1.70% · #7 ✓** | **1.51% · #7 ✓** | **1.58% · #7 ✓** |
| `expat / storeAtts` | 1.38% · #11 | 1.19% · #8 ✓ | 1.26% · #10 ✓ | 1.20% · #10 ✓ |
| `libpython / dict_dealloc` | 0.79% · #19 | 0.99% · #11 | 1.01% · #15 | 1.22% · #9 ✓ |
| `ElementTree / checkpath` | 1.05% · #14 | 1.13% · #10 ✓ | 1.09% · #12 | 1.00% · #11 |

#### 共同热点

| 对照 | Top-10 共同函数数 | 旧 Top-10 在新 Top-20 中出现 |
|---|---:|---:|
| tlc → hr_metro | 8 / 10 | 10 / 10 |
| tlc → egrid | 9 / 10 | 9 / 10 |
| tlc → industry_productivity | 8 / 10 | 9 / 10 |

### 热点函数与执行脚本的对应关系

#### opm-n10

| 实际脚本／程序 | 库 | 物理叶函数 | ROI 占比 |
|---|---|---|---:|
| `fill_fillable_fields.py` | libpython | `_PyEval_EvalFrameDefault` | 10.27% |
| `convert_pdf_to_images.py` | zlib | `longest_match` | 10.07% |
| `convert_pdf_to_images.py` | zlib | `deflate_slow` | 7.04% |
| `verify_pdf_batch.py` | libpython | `_PyEval_EvalFrameDefault` | 5.97% |
| `convert_pdf_to_images.py` | Pillow | `ImagingResampleHorizontal_8bpc` | 5.41% |
| `convert_pdf_to_images.py` | Pillow | `ImagingZipEncode` | 4.70% |
| `convert_pdf_to_images.py` | zlib | `slide_hash` | 2.74% |
| `fill_fillable_fields.py` | libpython | `gc_collect_main` | 2.66% |
| `convert_pdf_to_images.py` | Pillow | `ImagingResampleVertical_8bpc` | 2.52% |
| `pdftoppm` | Poppler | `Splash::compositeBackground(unsigned char const*)` | 2.44% |

#### irs_w4

| 实际脚本／程序 | 库 | 物理叶函数 | ROI 占比 |
|---|---|---|---:|
| `fill_fillable_fields.py` | libpython | `_PyEval_EvalFrameDefault` | 12.79% |
| `convert_pdf_to_images.py` | zlib | `longest_match` | 11.14% |
| `convert_pdf_to_images.py` | Pillow | `ImagingResampleHorizontal_8bpc` | 8.18% |
| `convert_pdf_to_images.py` | Pillow | `ImagingZipEncode` | 7.54% |
| `convert_pdf_to_images.py` | zlib | `deflate_slow` | 6.22% |
| `verify_pdf_batch.py` | libpython | `_PyEval_EvalFrameDefault` | 5.79% |
| `convert_pdf_to_images.py` | Pillow | `ImagingResampleVertical_8bpc` | 3.26% |
| `convert_pdf_to_images.py` | zlib | `slide_hash` | 3.07% |
| `fill_fillable_fields.py` | libpython | `gc_collect_main` | 1.57% |
| `fill_fillable_fields.py` | libpython | `_Py_dict_lookup` | 1.33% |

#### sba1919

| 实际脚本／程序 | 库 | 物理叶函数 | ROI 占比 |
|---|---|---|---:|
| `convert_pdf_to_images.py` | zlib | `longest_match` | 12.96% |
| `fill_fillable_fields.py` | libpython | `_PyEval_EvalFrameDefault` | 9.14% |
| `convert_pdf_to_images.py` | Pillow | `ImagingResampleHorizontal_8bpc` | 8.51% |
| `convert_pdf_to_images.py` | zlib | `deflate_slow` | 6.12% |
| `convert_pdf_to_images.py` | Pillow | `ImagingZipEncode` | 5.78% |
| `verify_pdf_batch.py` | libpython | `_PyEval_EvalFrameDefault` | 5.66% |
| `convert_pdf_to_images.py` | Pillow | `ImagingResampleVertical_8bpc` | 4.88% |
| `convert_pdf_to_images.py` | zlib | `slide_hash` | 2.82% |
| `pdftoppm` | Poppler | `Splash::pipeRunAARGB8(SplashPipe*)` | 2.55% |
| `pdftoppm` | Poppler | `Splash::compositeBackground(unsigned char const*)` | 1.96% |

#### tlc

| 实际脚本／程序 | 库 | 物理叶函数 | ROI 占比 |
|---|---|---|---:|
| `enhance_workbook.py` | libpython | `_PyEval_EvalFrameDefault` | 6.82% |
| `recalc.py` | libpython | `_PyEval_EvalFrameDefault` | 3.40% |
| `inspect_xlsx_structure.py` | libpython | `_PyEval_EvalFrameDefault` | 3.35% |
| `inspect_xlsx_features.py` | libpython | `_PyEval_EvalFrameDefault` | 2.53% |
| `verify_xlsx_enhanced.py` | libpython | `_PyEval_EvalFrameDefault` | 2.25% |
| `inspect_xlsx_formulas.py` | libpython | `_PyEval_EvalFrameDefault` | 1.84% |
| `write_xlsx_summary.py` | libpython | `_PyEval_EvalFrameDefault` | 1.74% |
| `inspect_xlsx_cached_values.py` | libpython | `_PyEval_EvalFrameDefault` | 1.72% |
| `inspect_xlsx_structure.py` | libpython | `dictiter_iternextkey` | 1.32% |
| `enhance_workbook.py` | libpython | `gc_collect_main` | 0.88% |

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

#### egrid

| 实际脚本／程序 | 库 | 物理叶函数 | ROI 占比 |
|---|---|---|---:|
| `enhance_energy_report_v2.py` | libpython | `_PyEval_EvalFrameDefault` | 8.00% |
| `recalc.py` | libpython | `_PyEval_EvalFrameDefault` | 6.05% |
| `verify_xlsx_enhanced.py` | libpython | `_PyEval_EvalFrameDefault` | 2.40% |
| `inspect_xlsx_formulas.py` | libpython | `_PyEval_EvalFrameDefault` | 2.15% |
| `inspect_xlsx_cached_values.py` | libpython | `_PyEval_EvalFrameDefault` | 1.97% |
| `inspect_xlsx_features.py` | libpython | `_PyEval_EvalFrameDefault` | 1.79% |
| `recalc.py` | libpython | `gc_collect_main` | 1.75% |
| `recalc.py` | libpython | `_Py_dict_lookup` | 1.73% |
| `recalc.py` | libpython | `subtype_traverse` | 1.25% |
| `enhance_energy_report_v2.py` | libpython | `gc_collect_main` | 1.13% |

#### industry_productivity

| 实际脚本／程序 | 库 | 物理叶函数 | ROI 占比 |
|---|---|---|---:|
| `enhance_workbook_v1.py` | libpython | `_PyEval_EvalFrameDefault` | 6.17% |
| `recalc.py` | libpython | `_PyEval_EvalFrameDefault` | 5.89% |
| `inspect_xlsx_formulas.py` | libpython | `_PyEval_EvalFrameDefault` | 2.25% |
| `inspect_xlsx_cached_values.py` | libpython | `_PyEval_EvalFrameDefault` | 2.18% |
| `verify_xlsx_enhanced.py` | libpython | `_PyEval_EvalFrameDefault` | 1.98% |
| `recalc.py` | libpython | `_Py_dict_lookup` | 1.63% |
| `recalc.py` | libpython | `gc_collect_main` | 1.62% |
| `inspect_xlsx_structure.py` | libpython | `_PyEval_EvalFrameDefault` | 1.57% |
| `inspect_xlsx_features.py` | libpython | `_PyEval_EvalFrameDefault` | 1.54% |
| `recalc.py` | libpython | `subtype_traverse` | 1.00% |


### 评估结论

PDF 三例的主要热点脚本共同集中在 convert_pdf_to_images.py、fill_fillable_fields.py、verify_pdf_batch.py 和 pdftoppm。五轮合并后，三例的 Top-5 函数集合完全相同：_PyEval_EvalFrameDefault、longest_match、deflate_slow、ImagingResampleHorizontal_8bpc 和 ImagingZipEncode，累计占比分别为 OPM 43.74%、W-4 51.65%、SBA 48.40%。W-4、SBA 与 OPM 的 Top-10 分别有 9、7 个共同函数；OPM 的 Top-10 在两者 Top-20 中分别出现 10、9 个。共同热点对应 Python 解释执行、zlib 压缩编码和 Pillow 图像处理；Poppler 渲染路径亦在三例中持续出现。
XLSX 四例共同以 libpython 为主要原生库，并集中出现 Expat、ElementTree、zlib 和 LibreOffice 路径。共同热点包括解释器执行、字典查找、对象遍历、垃圾回收、对象释放与 XML 解析。hr_metro：Top-10 共同函数 8 个，TLC Top-10 在其 Top-20 中出现 10 个；egrid：Top-10 共同函数 9 个，TLC Top-10 在其 Top-20 中出现 9 个；industry_productivity：Top-10 共同函数 8 个，TLC Top-10 在其 Top-20 中出现 9 个。
四个 XLSX 的 libpython 周期占比分别为 TLC 79.33%、HR Metro 79.63%、eGRID 82.13%、Industry Productivity 78.82%。不同领域输入下，工作簿检查、增强、重算和验证仍呈现共同的主要原生计算机制。
**完整七例对比支持原 PDF/XLSX 用例在主要热点类型和底层文档处理机制层面的跨领域代表性。领域变化带来具体函数排名和权重的变化，而解释器、对象管理、XML 解析、压缩编码及文档渲染等主要路径持续出现。**

### 采样与证据说明

PDF 每例固定五次独立重复，每次执行一轮、处理十份记录，汇总全部五次正式 ROI 的原始 period 后计算占比；表内仅采用五轮合并 PDF 结果。XLSX 沿用已有单轮结果，采样存在丢样记录，权重用于粗粒度结构观察。七例均按 49 Hz 采集用户态物理调用栈，以单调时钟标记正式循环区间。原始采样质量、未知项、ROI、容器身份及哈希见机器可读结果。
当前回放镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。

数据与追溯：[机器可读对比结果](comparison.json)、[分析构建记录](build.json)、[轨迹来源与回放说明](../../../../agent/README.md)。
