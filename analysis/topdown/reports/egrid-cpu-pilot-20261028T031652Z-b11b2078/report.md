# DevKit 按核采集试点

数据集：`egrid`；镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。

采集 CPU 0–7，控制器在 CPU 9；正式循环期间运行 workload，预检和归档在 CPU 9。以下 PMU 指标来自 DevKit 的完整采集包络，包络含初始就绪区间及停止延迟，未冒充精确 ROI 事件过滤结果。

| 指标 | DevKit 输出 |
|---|---:|
| IPC | 1.24 |
| Bad Speculation | 2.03% |
| Frontend Bound | 15.53% |
| Backend Bound | 61.84% |
| Retiring | 20.60% |
| Core Bound | 45.68% |
| Memory Bound | 16.16% |
| Fetch Latency Bound | 13.21% |
| Fetch Bandwidth Bound | 2.32% |
| CPU 0–7 idle（门控窗口 /proc/stat） | 86.23% |

业务 ROI 为 262.084 秒；启动包络上界 1.114 秒，停止包络上界 0.070 秒。idle 与 PMU 的窗口分别记录，不混成正式十维向量。

顶层与前后端分区关系通过核对。原始事件经验公式复算：均在打印精度内。
存在未计数诊断的事件：r1010, r1013, r1016, r2004, r2005, r2006, r2007, r2008, r2009, r200a, r200b, r200c, r200d, r200f, r2010, r2011, r2012, r5090, r5091, r5092, r5093, r5094, r5095, r5096, r50a0, r7002, r7006, r701e。这些状态保留；不能仅凭最终表打印为 0 就认定真实计数为零。

本次只验证功能与采集接线，不计算跨数据集相似度；模型、SMT、复用缩放和边界口径继续在正式采集前收敛。

原始记录：`analysis/topdown/raw/egrid-cpu-pilot-20261028T031652Z-b11b2078`。
