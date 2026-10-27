# XLSX 执行入口命名

为便于按进程命令和脚本名对齐热点，源码中的 `hr_metro`、`retail_online`、
`industry_productivity` 使用与原 TLC 相同的入口 basename。旧 TLC 的文件、PDF 用例、
三个历史小 XLSX 用例及已有采样均不改名。

| 职责 | 新执行入口 | 保留的实现或来源 |
|---|---|---|
| 输入结构检查 | `inspect_xlsx_structure.py` | 同进程执行 `inspect_xlsx.py source` |
| 副本检查 | `inspect_xlsx_features.py` | 同进程执行 `inspect_xlsx.py copy` |
| 公式检查 | `inspect_xlsx_formulas.py` | 同进程执行 `inspect_xlsx.py formula` |
| 缓存检查 | `inspect_xlsx_cached_values.py` | 同进程执行 `inspect_xlsx.py cached` |
| 增强 | workspace 中的 `enhance_workbook.py` | recipe 写入原数据集 helper 的相同内容；Industry 保留 `helpers/` 目录以保护 ROOT 解析 |
| 重算 | 原 Skill `recalc.py` | 不变 |
| 业务验证 | `input/verify_xlsx_enhanced.py` | 与同 workspace 的原 `input/verify_office.py` 字节一致，通用 loop 验证实现不变 |
| 摘要 | `write_xlsx_summary.py` | 同进程执行 `summary.py` |
| CSV | `export_xlsx_csv.py` | 同进程执行 `export_xlsx.py` |

六个共用工具入口位于 `compatibility/tools/`，不会复制到每个数据集。入口使用 `runpy`
执行既有实现，不额外启动 Python 子进程，也不增加工作簿 load/save 次数。`--help` 只打印
帮助，不打开工作簿。通用实现原文件名继续保留供已有调用使用。

增强源码文件仍在 `compatibility/helpers/` 以数据集区分，内容哈希保持不变；只是 recipe
在 workspace 写出的名字统一。通用原子执行器的实际临时脚本名为
`.enhance_workbook.runtime.py`，分析识别器将其识别为增强职责，不能误列为未知进程。

同名不代表与 TLC 同一份源码。参数来自 manifest，业务 helper/验证细节的既有差异保留。
入口解释执行增加少量 Python 启动工作，本次没有测量该开销，不能宣称 CPU 数值完全不变。

## 历史证据与当前资格

v12 成功运行使用改名前的 recipe。三份完整 recipe 已按原字节保存在
`reports/evidence/v12/script-recipes/`，其原哈希与新 recipe 哈希关联在
[命名变更记录](../reports/script-entrypoint-alignment-v1.json)。v12 原运行记录、原证据索引、
原采样、性能 JSON、输入和 canonical 不改写；新快照的哈希由命名变更记录另行绑定。

`next-comparison-suite.json` 继续关联 v12 功能及既有测量版本，不自动为改名后的源码
赋予成功资格。改名版本已构建为 `office-trace-replay:openeuler-release`，通过安装态检查，
并于 2026-10-26 完成七个用例的新单轮执行（PDF N=1/N=10 分开，共十个配置）及进程 CPU
采集；三个新 XLSX 的统一命名入口已从实际进程命令核验。新数据见
[正式镜像新采集](../analysis/hotspot-comparison/reports/formal-process-cpu-20261026/comparison.json)。
本轮未重复循环外独立深审。旧 v1～v12 标签及关联停止容器已清理，原采样、报告及宿主输出保留。
正式镜像身份及后续离线构建基础见 [正式镜像记录](../reports/formal-image-release.json)。

代表性报告已使用本轮新采集的进程 CPU 表格，改名前报告的原字节快照保存在新报告目录；历史采样没有改名或改写。
