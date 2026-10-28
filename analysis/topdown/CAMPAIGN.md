# 七个数据集五次重复的 Topdown 与热点结果

七个正式用例的两路测量均已统一为五次独立成功运行：PDF 为 OPM、IRS W-4、SBA 1919，每次处理十份；XLSX 为 TLC、HR Metro、eGRID、Industry Productivity。perf 热点与 DevKit Topdown 分别运行，各使用 35 次结果。保留既有首轮与 PDF 五次，按预定计划补齐 XLSX 的 32 项采集，新增采集零失败、零重试。

- [代表性评估报告](../../docs/representativeness-assessment.md)
- [五次特征、相似度与特征图](reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7/similarity/report.md)、[机器结果](reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7/similarity/comparison.json)、[配对 CSV](reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7/similarity/pairs.csv)
- [逐轮 Topdown 值、均值、样本标准差和 CV](reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7/statistics.json)、[统计 CSV](reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7/statistics.csv)、[波动表](reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7/repeat-variability.md)
- [五次热点汇总与逐轮排名波动](reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7/native/report.md)、[热点机器结果](reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7/native/comparison.json)
- [35 次 Topdown 来源](reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7/campaign.json)、[离线核验](reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7/verification.json)、[两路对比输入](reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7/comparison-inputs.json)

全部使用同一个已验收镜像、DevKit 26.0.RC1 和相同的核心门控采集代码。DevKit 对 CPU 0–7 计数，perf 对回放命令及其后代进程采样，控制与身份监测在 CPU 9。43 个旧 workload 文件和 22 项镜像资格绑定复核无差异；未修改业务脚本、输入或镜像。

每次保存 DevKit 最终总报告的九项指标，并从门控窗口 `/proc/stat` 另算 idle。七例均逐指标对五次结果取算术均值、样本标准差与 CV；热点则合并五次 ROI 的原始 sample period，再计算占比。正式报告不再混用单轮 XLSX 与五轮 PDF，逐轮值只用于波动分析和追溯。

四个 XLSX 的 IPC CV 为 0.44%–0.72%，Backend Bound CV 为 0.23%–0.54%。同数据集五次两两比较的 Top-10 共同函数数为 TLC 10/10、HR Metro 10/10、eGRID 8–9/10、Industry Productivity 9–10/10，支持固定环境下主要特征与热点集合的重复稳定性。PDF 的实际波动同样逐项保留；不将五次重复外推为跨硬件环境的可复现性。

特征图分别展示 PDF 和 XLSX 的四个顶层 Bound，保留全部五个独立运行点、均值和样本标准差。点表示一次运行的最终结果，不是同一轮中的每秒时间片。

Topdown 表中的 Bound 是 DevKit 的流水线指标，不是脚本 CPU 时间占比。PMU 窗口包含已记录的就绪与停止包络，idle 使用独立门控窗口。三处经验公式复算差异、未计数事件和 SMT／复用语义边界仍完整保留；数值直接采用工具输出。

最新 Topdown 35 次采集在完成时核验 2,680 个归档文件；离线再次核对关联证据、逐轮指标、统计与报告一致性。原始数据、成功运行和历史失败记录、停止容器均保留。此前 19 次汇总和旧相似度报告为历史快照，正式结果以本页链接为准。

离线复核与重建命令（不启动 workload 或采集）：

```bash
python3 -B analysis/topdown/verify_campaign.py \
  analysis/topdown/reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7
python3 -B analysis/topdown/compare_similarity.py \
  --config analysis/topdown/reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7/comparison-inputs.json --update-report
python3 -B -m unittest discover -s analysis/topdown/tests
```

如果复算改变了相似度结果哈希，应同步 `analysis/hotspots/comparison-inputs-pdf5-20261027.json` 的 `joint_comparison` 绑定，再用 `analysis/hotspots/compare.py --update-report` 重建正式报告。该配置文件保留历史名称，当前内容已全部采用五次结果。
