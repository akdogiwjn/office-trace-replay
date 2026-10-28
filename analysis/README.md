# 采集与分析导航

正式结论统一在 [代表性评估报告](../docs/representativeness-assessment.md)。以下目录负责代码与证据，不是多套正式报告。

| 目录／文件 | 用途 |
|---|---|
| `hotspots/pilot.py` | 单数据集 perf 采集；49 Hz、cycles:u、后代进程树、正式循环 ROI |
| `hotspots/native_profile.py`、`monitor.py` | 物理函数解析、身份关联、period 与质量检查 |
| `hotspots/pdf_repeats.py`、`xlsx_repeats.py` | 五次原始 period 合并与逐轮排名波动 |
| `hotspots/compare.py` | 生成正式报告、脚本分组和热点集合对比 |
| `topdown/pilot.py`、`capture.py`、`gate.py` | DevKit CPU 0–7 采集与循环门控 |
| `topdown/summarize.py`、`verify_campaign.py` | 单次最终指标、五次统计及来源验证 |
| `topdown/compare_similarity.py`、`repeat_plots.py` | 十维向量、四 Bound 余弦、热点 Jaccard 与特征图 |
| `topdown/CAMPAIGN.md` | 当前五次结果的完整索引和离线复核命令 |
| `topdown/README.md`、`hip09-preflight-20261027/` | 预检时冻结的说明与证据，原字节受 SHA256 索引保护；其中阶段状态是历史快照，当前状态以 CAMPAIGN 为准 |

## 当前数据

- 热点：PDF 五次结果在 `hotspots/reports/pdf-five-repeats-20261027T122345Z-06367392/`；XLSX 五次结果在 `topdown/reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7/native/`。
- Topdown：七例各五次，使用 `topdown/reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7/`。
- 正式报告源配置：`hotspots/comparison-inputs-pdf5-20261027.json`，名称沿用历史命名，内容已统一为七例五次。
- 每次实际执行的 profile、summary、输入绑定和质量诊断在各自日期目录中。这些目录用于溯源，不能仅因日期较早就删除；当前五次结果仍引用最初首轮。
- `hotspots/raw/`、`topdown/raw/` 是本地原始采集；`topdown/tools/`、`downloads/` 是冻结工具及安装包，均不提交 Git。
- `hotspot-comparison/` 保留旧版本的实测数据与解释材料，仅作历史数据定位；新五次报告不会混用其结果。

不要把 perf 用户周期比例、py-spy Python 样本比例、CPU 时间账本和 DevKit 按核指标相互换算。当前报告逐项说明对象、窗口和分母。

## 离线重算

1. 使用 `topdown/CAMPAIGN.md` 的命令核验已有五次结果并重算相似度；不重新采集。
2. 如果相似度 JSON 改变，将新 SHA256 更新到热点配置的 `joint_comparison`。
3. 运行根 README 中的报告生成命令。正式 Markdown 在 `docs/`；原深层 `report.md` 仅是指向它的兼容链接，报告内容只有一份。

搬迁项目不改写原始运行记录、raw 文件或冻结 SHA256。优先按 JSON 中仓库相对路径定位数据，而不是把历史宿主绝对路径当作当前路径。
