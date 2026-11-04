# DocOps 现有 perf 数据：离线补符号效果

同一批原始采样的补符号前后对比；没有重新运行任务、perf record 或 DevKit。

| 任务 | 格式 | 补前未解析周期 | 补后未解析周期 | 函数资格 |
|---|---|---:|---:|---|
| 001 | word | 12.08% | 2.49% | passed |
| 003 | word | 15.69% | 2.88% | passed |
| 009 | word | 25.90% | 2.54% | passed |
| 013 | excel | 26.96% | 0.51% | passed |
| 014 | excel | 13.22% | 0.68% | passed |
| 016 | excel | 7.47% | 0.40% | passed |
| 021 | ppt | 20.92% | 2.07% | passed |
| 026 | ppt | 11.01% | 3.02% | passed |
| 029 | ppt | 9.06% | 1.63% | passed |
| 031 | pdf | 8.68% | 0.00% | passed |
| 037 | pdf | 10.32% | 0.05% | passed |
| pdfwf005 | pdf | 38.80% | 0.18% | passed |

所有占比的分母为 workflow ROI 内完整 cycles:u 原始 sample period。未知项保留在分母中。
每任务仍是原有一次独立采集、该次回放十轮；离线处理不增加重复数。
使用采集时的同一镜像，以及 build-id 精确匹配的 12 个目标 ELF 调试文件。仅逐文件只读挂载补充符号，不遮蔽镜像原有调试目录。
逐样本检查 key、物理叶地址及 DSO 不变，并核对样本数、ROI period、进程权重及 loss 记录。原始文件只读，前后 SHA256 一致。
lxml 暂未找到精确匹配的额外符号；其余零散未知项如实保留。本次不改变原采集的 loss 和 ROI 边界。

[完整离线处理记录](../../raw/unified-symbol-check-20261103T1703Z/offline-symbol-enrichment-v1/enrichment.json)
