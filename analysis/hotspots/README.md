# perf 热点采集与分析

当前正式结果为七例各五次，见 [代表性评估报告](../../docs/representativeness-assessment.md)、[分析导航](../README.md) 和 [数据保留记录](../../reports/data-retention.json)。

## 结果与数据

- PDF：OPM、IRS W-4、SBA 1919，各五次独立容器运行，每轮处理十份。合并结果在 [PDF 五次目录](reports/pdf-five-repeats-20261027T122345Z-06367392/report.md)。
- XLSX：TLC、HR Metro、eGRID、Industry Productivity，各五次独立运行。合并结果在 [XLSX 五次目录](../topdown/reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7/native/report.md)。
- 正式报告源配置为 `comparison-inputs-pdf5-20261027.json`，名称沿用历史命名，内容仅采用当前七例五次结果，不载入旧历史基线。
- `raw/<capture>/out/` 保存 perf.data、样本、进程身份、ROI、业务产物及 SHA256 索引；`evidence/` 保存实际 inspect、启动计划和采集代码。35 次正式热点采集均完整保留。
- 旧版本数据、未采用的单轮 PDF 试点和失败结果已删除；最新五次复用的 XLSX 首轮是正式输入，仍保留。

合并采用各轮 ROI 原始 sample period 的分子、分母分别求和，不平均百分比。未知项保留分母；损失保留原始单位，不换算成 cycles。函数采用物理叶函数独占归属，按库类别和符号匹配；脚本展示按职责分组，同时保留实际脚本名。完整方法和五次波动在正式报告第四至六节。

## 采集机制

`pilot.py` 使用已验收镜像，perf 启动实际回放命令并继承到后代进程／线程；用户态事件 `cycles:u`、49 Hz、DWARF 16384，workload 运行在 CPU 0–7，监测端在 CPU 9。CPU affinity 不表示独占，也不把该测量变为按核系统采样。

使用 CLOCK_MONOTONIC 的正式循环 ROI，包含 reset、P01–P04 和循环验证，排除归档及独立审计。同一镜像内以 `--no-inline` 导出物理链；完整栈与无栈导出逐样本交叉核对。旧 OPM/TLC 由 `legacy_capture.py` 观察原函数边界，不改 43 个 workload 文件。

只离线重建报告：

```bash
python3 -B analysis/hotspots/compare.py \
  --config analysis/hotspots/comparison-inputs-pdf5-20261027.json --update-report
python3 -B -m unittest discover -s analysis/hotspots/tests
```

只有另行安排新采集时才执行：

```bash
python3 -B analysis/hotspots/pilot.py --dataset sba1919
```

导出或解析失败优先从既有 raw 恢复，不自动重跑 workload。`recover_native.py` 保留这一能力；当前正式数据已全部成功，不需要执行恢复。各单次 profile 留在日期目录中以支持五次结果复算，不是额外的正式对比版本。
