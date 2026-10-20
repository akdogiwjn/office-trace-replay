# 文档入口

当前使用与验收状态以 [项目 README](../README.md) 为准；执行、准备、验证和维护规则见 [compatible-workflow.md](compatible-workflow.md)。分析口径与历史结果见 [分析 README](../analysis/hotspot-comparison/README.md)。

以下材料保留为历史设计或兼容性依据，不作为当前构建/运行命令：

- [replay-contract.md](replay-contract.md)：最初 derived-v1 引擎的轨迹选择与回放机制。
- [document-oe-reuse.md](document-oe-reuse.md)：初次导入 document-oe 时的来源和环境说明；runner 后续已版本化。
- [legacy-compatibility.md](legacy-compatibility.md)：旧 workload 的字节保护边界；executor 是独立版本化文件。

历史审计失败、旧性能结果及早期镜像记录保留原文，当前状态由 `reports/evidence/v12/index.json` 和版本化分析选择关联确定。README 不重复列出历次调试过程，完整输入/产物与 perf raw 不随说明文档提交。
