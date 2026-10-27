# 跨领域真实输入下文档解析类agent负载的代表性评估

本报告通过数据集介绍和热点进程占比对比，评估原 TLC/XLSX、OPM/PDF 用例在更换领域及真实输入后的适用范围。报告只使用已保存的实验结果，没有新增运行或性能采集。这里的 agent 负载指从文档任务整理出的固定工具执行负载，回放时不调用 LLM；HR Metro、Retail Online 是人工适配，其余用例保留各自的历史或 Agent 来源。

## 1. 数据集介绍

### 1.1 领域覆盖与 XLSX 规模

XLSX 以原 TLC 用例为基线，扩展到人力资源、在线零售及工业生产率。四个工作簿均保留完整输入，没有通过复制记录或 synthetic shard 扩大新数据集。

| 数据集 | 领域与来源 | 数据内容与输入形态 | 文件大小（MiB） | 工作表数 | 主要工作表规模（行 × 列） | 全工作簿非空单元格数 |
|---|---|---|---:|---:|---|---:|
| TLC（旧基线） | 交通出行；NYC TLC 原始行程数据 | 真实行程样本与预先汇总构建的 benchmark 工作簿；不是官方原生 XLSX | 11.71 | 7 | Raw_Sample：100,001 × 25 | 2,501,211 |
| HR Metro | 人力资源／劳动力；BLS OEWS | May 2025 metropolitan/nonmetropolitan 区域职业、就业和工资统计原始 XLSX | 29.21 | 4 | MSA_M2025_dl：150,024 × 32 | 4,208,869 |
| Retail Online | 零售；UCI Machine Learning Repository | 真实在线零售交易原始 XLSX；541,909 条交易明细，覆盖 2010-12-01 至 2011-12-09 | 22.62 | 1 | Online Retail：541,910 × 8 | 4,198,746 |
| Industry Productivity | 工业生产率；BLS | 保留详细行业长期序列原始 XLSX，任务选择制造业序列；含 Annual 和 MachineReadable 两种表示 | 21.59 | 3 | Annual：15,183 × 46；MachineReadable：566,659 × 9 | 5,798,274 |

表中行数包含表头或说明行；非空单元格数是文件内容规模，不等于独立业务记录数或有效数值数量。Industry Productivity 的长表和宽表是同一发布数据的不同表示，任务计算不重复汇总两者。各输入的原有 Sheet、类型、公式和样式没有统一成相同模板，因此本组是同数量级的真实工作簿比较，不是严格控制所有输入变量的行业实验。

HR Metro 的选区和 Retail Online 的全表过滤、聚合在正式循环外一次准备，冻结为小 JSON。正式循环仍完整加载大工作簿、增加少量摘要／情景／图表、保存、重算及验证；输入准备时间不进入后文的 CPU 分母。TLC 使用预先存在的汇总表，Industry Productivity 引用原始 Annual 表中的选定单元格。

输入来源边界：HR Metro、Retail Online 为用户提供的官方发布渠道下载文件；Industry Productivity 为用户确认从 BLS 官方下载的文件，独立重下载曾返回 HTTP 403，未宣称独立验证官网字节一致。输入字节和来源说明由各自 manifest/provenance 冻结。

### 1.2 PDF 数据集与规模

PDF 以 OPM 的 OF-306 为基线，扩展到工资税务和小企业申请表。表单使用真实发布文件；填写记录是冻结的虚构测试数据，不是实际申请人的个人信息。

| 数据集 | 领域／发布机构 | 冻结版本 | 文件大小（KiB） | 页数 | 可填写字段数 | 准备记录数 | 画像中的实际填写规模 |
|---|---|---|---:|---:|---:|---:|---|
| OPM（旧基线） | 联邦雇佣申报／OPM | OF-306，August 2023 | 248.5 | 3 | 38 | 10 | N=1、N=10 分别比较 |
| IRS W-4 | 工资税务预扣／IRS | Form W-4，2026 | 204.0 | 5 | 48 | 10 | N=1、N=10 分别比较 |
| SBA 1919 | 小企业借款申请／SBA | Form 1919，04/2024，可填写旧版 | 529.7 | 7 | 127 | 10 | N=1、N=10 分别比较 |

N 表示实际填写和渲染的记录数，不是循环次数。两种模式都准备 10 份字段映射，每轮渲染一次模板，并分别填写、渲染实际选择的 N 份记录。SBA 输入实际来自公开的 SBA Box 链接，规范化文字曾与 SBA.gov 旧版核对；没有宣称文件与官网字节一致，也不将其标为当前最新版。

数据集规模与来源依据：[XLSX 输入元数据](../assets/cases/)、[正式用例集合](../suites/default.json)及各用例 `source/datasets/{xlsx,pdf}/<dataset>/` 中的 `manifest.json`、`provenance.json`、`complexity.json`（XLSX）。

## 2. 热点进程占比对比

进程按实际执行脚本职责归类，避免将全部 Python 进程合并为一个 `python3`。同一职责可以由多个进程执行；不同用例同名职责不表示源码或每项验证完全相同。父进程与子进程只计算各自消耗，不把子进程成本重复计入父进程。

### 2.1 XLSX：整轮 workload CPU 占比

本表分母为正式循环 ROI 内所有已观察 workload 线程的 user+sys CPU，包含 Python、LibreOffice 及其他辅助进程；按 50 ms 轮询估计，包含已观察的解释器退出清理。准备、执行前预检、独立深审、归档和采集器自身不计入。每个数据集仅测量一轮，使用 v11 镜像加只读挂载的测量期代码；不是 v12 裸镜像性能采集。

| 进程职责 | TLC（旧基线） | HR Metro | Retail Online | Industry Productivity |
|---|---:|---:|---:|---:|
| 工作簿检查 Python 进程（输入／副本／公式／缓存检查合并） | 38.78% | 38.13% | 34.90% | 34.06% |
| 增强 helper Python 进程 | 21.30% | 22.59% | 18.59% | 18.28% |
| 重算检查 Python 进程（不含 LibreOffice 子进程） | 11.76% | 12.46% | 12.51% | 12.90% |
| LibreOffice 进程及线程 | 8.97% | 7.33% | 15.29% | 16.21% |
| 循环内业务验证 Python 进程 | 10.04% | 9.71% | 9.36% | 9.31% |
| 摘要生成 Python 进程 | 8.32% | 9.71% | 9.28% | 9.20% |
| CSV 导出 Python 进程 | 0.76% | 0.03% | 0.04% | 0.02% |
| 其他进程（原子执行器、runner 等） | 0.07% | 0.03% | 0.03% | 0.02% |
| 整轮 workload CPU（秒） | 244.72 | 367.94 | 441.85 | 536.42 |

检查、增强、重算和验证是四个用例共有的主要进程职责。检查进程约占 34.06%～38.78%，增强进程约占 18.28%～22.59%；循环内验证约占 9.31%～10.04%。新输入没有把主要 CPU 工作转移到另一套完全不同的进程链。

LibreOffice 占比存在明确差异：TLC 为 8.97%，HR Metro 为 7.33%，Retail Online 为 15.29%，Industry Productivity 为 16.21%。因此可支持“主要执行进程及职责相近”，不能写成“各热点权重相同”。进程角色之间的占比变化不是行业本身的因果证据；完整文件内容、样式、重算及保存工作都可能影响结果。

脚本职责对应关系如下。新用例入口 basename 已与 TLC 对齐，并打包为 `office-trace-replay:openeuler-release`，共用处理逻辑和业务 helper 内容保留；新镜像通过安装态检查，尚未真实 replay。上表仍来自改名前的测量，不把这些采样改称新命名版本的结果。具体对应关系见 [命名变更说明](xlsx-script-names.md)。

| 职责 | TLC 冻结脚本 | 新用例在本报告采集时的脚本 | 新用例统一后的执行入口（源码） |
|---|---|---|---|
| 工作簿检查 | `inspect_xlsx_structure.py`、`inspect_xlsx_features.py`、`inspect_xlsx_formulas.py`、`inspect_xlsx_cached_values.py` | `inspect_xlsx.py source/copy/formula/cached` | 与 TLC 相同的四个 basename，调用既有通用实现 |
| 增强 | `enhance_workbook.py` | `hr_metro_build.py`、`retail_online_build.py`、`industry_productivity_build.py` | `enhance_workbook.py`，仍写入各数据集原 helper 内容 |
| 重算／缓存检查 | XLSX Skill `recalc.py` | 同一 XLSX Skill `recalc.py` | 不变 |
| LibreOffice | `soffice`/`soffice.bin` 及线程、启动进程 | 同类 LibreOffice 子进程与线程 | 不变 |
| 循环内验证 | `input/verify_xlsx_enhanced.py` | `input/verify_office.py`，通用 loop verifier | `input/verify_xlsx_enhanced.py`，实现字节保留 |
| 摘要 | `write_xlsx_summary.py` | `summary.py` | `write_xlsx_summary.py` |
| CSV 导出 | `export_xlsx_csv.py` | `export_xlsx.py` | `export_xlsx_csv.py` |

数据依据：[总 CPU 离线重算 v2 JSON](../analysis/hotspot-comparison/reports/total-cpu-recalculation-v2-20261020T104020Z/comparison.json)的 `denominator_breakdown / denominator_seconds`。表格以未舍入数据计算后保留两位小数，显示值之和可能有舍入误差。轮询可能漏掉短命进程及退出前最后一段 CPU，尚无整体误差上限；本表是该次执行的描述性结果，不是稳定性检验。

### 2.2 PDF：用户态周期占比

PDF 使用已有 native 画像：分母为完整 ROI 的 `cycles:u` 样本 period 之和，不是整轮 user+sys CPU 时间，也不是 Python 内部采样比例。下表沿用其历史采集版本：OPM 为较早 runner 的两次重复合并，IRS W-4、SBA 1919 使用 v9/current-loop 采集代码，各 N 配置一条 profile。OPM 当时的实际镜像 ID 未记录；这些数据不冒充 v12 新采集。三种表单只在同一 N 内比较，不与上面的 XLSX 总 CPU 百分比横向比较。

**N=1：实际填写 1 份记录**

| 进程职责 | OPM（旧基线） | IRS W-4 | SBA 1919 |
|---|---:|---:|---:|
| 字段可填写检查（`check_fillable_fields.py`） | 7.64% | 4.32% | 5.66% |
| 字段提取（`extract_form_field_info.py`） | 8.88% | 4.15% | 5.89% |
| 字段映射生成／驱动 | 0.53% | 0.82% | 0.95% |
| PDF 填写（`fill_fillable_fields.py`） | 18.85% | 17.48% | 13.72% |
| 转换脚本 Python 进程（`convert_pdf_to_images.py`） | 34.47% | 34.06% | 35.19% |
| 渲染子进程（`pdftoppm`） | 12.38% | 13.53% | 14.76% |
| 循环内业务验证 | 14.20% | 19.77% | 18.30% |
| 摘要生成 | 0.41% | 0.48% | 0.32% |
| 其他进程（runner、pdfinfo、内联命令、未识别 Python 等） | 2.64% | 5.39% | 5.20% |

**N=10：实际填写 10 份记录**

| 进程职责 | OPM（旧基线） | IRS W-4 | SBA 1919 |
|---|---:|---:|---:|
| 字段可填写检查（`check_fillable_fields.py`） | 1.66% | 0.72% | 0.98% |
| 字段提取（`extract_form_field_info.py`） | 1.71% | 0.43% | 1.06% |
| 字段映射生成／驱动 | 0.06% | 0.13% | 0.28% |
| PDF 填写（`fill_fillable_fields.py`） | 35.05% | 31.93% | 27.29% |
| 转换脚本 Python 进程（`convert_pdf_to_images.py`） | 36.69% | 39.41% | 41.62% |
| 渲染子进程（`pdftoppm`） | 13.33% | 14.12% | 17.88% |
| 循环内业务验证 | 11.11% | 7.72% | 10.34% |
| 摘要生成 | 0.10% | 0.04% | 0.04% |
| 其他进程（runner、pdfinfo、内联命令、未识别 Python 等） | 0.28% | 5.50% | 0.51% |

三种表单的主要热点均落在 Python 转换、PDF 填写、验证和 `pdftoppm` 渲染。N=1 时，Python 转换进程占比约为 34.06%～35.19%；N=10 时约为 36.69%～41.62%，填写进程约为 27.29%～35.05%。相同 N 下主要热点职责一致，表单变化主要表现为这些职责之间的权重调整。

`pdf-convert` 仅表示转换脚本进程自身消耗，`pdftoppm` 子进程单列，两者不重复计数。OPM 使用 `generate_and_run_batch.py` 生成映射，W-4/SBA 使用 `build_field_values.py`（SBA 位于 `helpers/`）；实际填写和渲染均由 `run_batch_fill_render.py` 依次调用 Skill 工具。OPM 验证器为 `verify_pdf_batch.py`，新增表单为 `verify_office.py`，同属验证职责但实现不完全相同。

数据依据：[native 进程画像 JSON](../analysis/hotspot-comparison/reports/hotspot-version-comparison-v2/comparison.json)的 `native_profiles.<dataset>.process_share`。OPM 两次重复按 ROI period 加权；新表单每配置仅一次采集，未证明占比差异稳定。历史 ROI 对齐和符号／采样质量限制沿用[原分析报告](../analysis/hotspot-comparison/reports/hotspot-version-comparison-v2/comparison-report.md)，没有因重新制表而消除。

综合这些表格，在选定的真实输入和对齐后的工具流程中，原 TLC/OPM 的主要热点进程职责在新增用例中继续出现，支持其作为这类固定工具负载的分析起点。该结论限定于这里的用例、执行方式及证据版本；不等同于覆盖所有文档解析 agent，也不表示具体函数权重或优化收益相同。
