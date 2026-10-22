# 当前执行流程与维护边界

本说明对应 v12 正式 suite；实际验收和使用入口见 [README](../README.md)。本项目比较不同真实输入下相近工具机制，允许原始文件复杂度不同，不以行业名称解释 CPU 因果关系。

## 入口与运行环境

`replay/entry.py` 的默认数据集来自 `suites/default.json`：OPM、TLC、W-4、SBA、HR Metro、Retail Online、Industry Productivity。每个数据集在一个统一 runner 进程内完成指定轮数。默认容器命令为一轮；底层直接 runner 保留旧 20,000 轮默认值。

正式容器入口支持 `--dataset`、`--loops`、`--pdf-applicant-count 1|10`、`--legacy-python venv|system`、`--timed`。使用 `--scene` 会进入直接 runner 兼容入口，只有 loop 验证，不自动执行 suite 的循环外验收。

runner 在循环前校验 executor、workload、recipe、input、helper、source、manifest、Prompt 与准备工件绑定，准备 Skill 链接和 source context，统一实际解释器及 PATH。默认 Python 3.12.3，与 openpyxl 3.1.5、锁定 Office/Poppler 环境一起冻结。系统 Python 3.11.6 仅为显式历史选项。

## 四阶段

| 场景 | 循环内流程 | 保留的差异 |
|---|---|---|
| XLSX | 完整输入检查/复制 → 原子 helper 加少量 KPI、情景和图表并保存 → 原 Skill 原位重算、公式/缓存检查及 CSV → loop verifier 与 summary | 输入数据、表结构、引用位置、样式与 Office 工作量 |
| PDF | 字段检查/提取/模板渲染 → 生成十份 mappings → 按选择记录交替 fill/render → summary 和 loop verifier | 表单页数、字段、业务内容；实际执行 N=1 或 N=10 |

新 XLSX 不执行旧 assemble_output/inject_caches/patch 保存回填链；LibreOffice 保存之后不再用 openpyxl 保存。helper 在循环内按 recipe 写入和执行。HR Metro/Retail Online 的业务选择/聚合由循环外冻结的小工件提供，但循环内仍完整加载和保存原始工作簿。

TLC 的冻结基线原本具有预汇总结构；Industry 使用已知源单元格。它们与 prepared-v2 HR/Retail 的共同机制是完整读写、有限单元格引用/计算、图表/格式、重算与验证，不要求所有公式或 sheet 相同。

## 准备与验证

`scripts/prepare_xlsx_selection.py` 只用于显式输入/workload 版本变更。它扫描输入、核对独立 expected 后原子发布准备工件。正式运行读取已有工件，不现场回退聚合。仅在确实需要更新准备数据时执行：

```bash
python3 scripts/prepare_xlsx_selection.py --dataset hr_metro --dataset retail_online
python3 scripts/compile_compatible.py --dataset hr_metro --dataset retail_online
python3 scripts/freeze_project.py
python3 replay/entry.py --validate-only
```

这不是日常运行步骤。生成器支持 `--help` 与选择性生成；无参数是全量生成，应避免误触。

loop verifier 检查当前工作负载必需的结构、KPI/情景/公式/缓存、图表特征、重算错误与交付一致性。新 XLSX 使用共同 loop contract；旧 TLC 保留原 verifier。新 PDF 对实际执行记录详细检查字段和代表页变化，未执行 mappings 的深查在 independent scope。

suite 先核验所有轮次，再对新用例末轮执行 independent acceptance，归档末轮产物和全部轮次日志；一轮失败不能被末轮成功掩盖。旧 OPM/TLC 不自动追加独立 verifier，其完整 workspace 需要单独归档。直接 runner 的 output 不应与 suite 归档布局混淆。

独立审计包含源数据/公式/图表/名称/格式保护及深层依赖检查。可对已有输出离线验收，不必重新生成工作簿；使用独立只读 workspace 和报告目录，记录审计前后 hash。`functional_trial.py --accept-archived` 适用于该脚本生成且通过来源校验的同 campaign 双数据集归档，不是任意 suite 目录的通用审计命令。

## 冻结与证据

`legacy/document-oe/lock.json` 分离 43 个冻结 workload 文件与版本化 executor。旧 OPM/TLC 的实际 recipe、helper、Skill 和 verifier 不变，不能通过刷新预期 hash 掩盖改动。

Agent-derived recipe 绑定原 canonical/parent；`hr_metro`、`retail_online` 是人工适配，不产生 Agent trace。输入、准备工件、Prompt、manifest、helper、source 和 verifier 仍须按各自冻结身份关联。

v12 七项裸镜像功能证据见 [release index](../reports/evidence/v12/index.json)。它不包含完整 output/raw；原始工作目录保留在本地。性能证据来自独立采集，按版本和测量口径登记在 [分析选择配置](../analysis/hotspot-comparison/config/next-comparison-suite.json)，不能用功能通过替代性能重测。
