# DevKit 按核采集试点

数据集：`opm`；镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。

采集 CPU 0–7，控制器在 CPU 9；正式循环期间运行 workload，预检和归档在 CPU 9。以下 PMU 指标来自 DevKit 的完整采集包络，包络含初始就绪区间及停止延迟，未冒充精确 ROI 事件过滤结果。

| 指标 | DevKit 输出 |
|---|---:|
| IPC | 1.26 |
| Bad Speculation | 4.46% |
| Frontend Bound | 18.77% |
| Backend Bound | 55.80% |
| Retiring | 20.97% |
| Core Bound | 45.78% |
| Memory Bound | 10.02% |
| Fetch Latency Bound | 16.13% |
| Fetch Bandwidth Bound | 2.65% |
| CPU 0–7 idle（门控窗口 /proc/stat） | 86.25% |

业务 ROI 为 10.885 秒；启动包络上界 1.108 秒，停止包络上界 0.010 秒。idle 与 PMU 的窗口分别记录，不混成正式十维向量。

原始事件复算与工具输出精度一致，顶层与前后端分区关系通过核对。
存在未计数诊断的事件：r2007, r2008, r2009, r200a, r200c, r7002, r7006。这些状态保留；不能仅凭最终表打印为 0 就认定真实计数为零。

本次只验证功能与采集接线，不计算跨数据集相似度；模型、SMT、复用缩放和边界口径继续在正式采集前收敛。

原始记录：`analysis/topdown/raw/opm-cpu-pilot-20261027T152830Z-ffe55771`。
