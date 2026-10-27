# 文档入口

当前使用与验收状态以 [项目 README](../README.md) 为准；执行、准备、验证和维护规则见 [compatible-workflow.md](compatible-workflow.md)。分析口径与历史结果见 [分析 README](../analysis/hotspot-comparison/README.md)。

数据集介绍与热点进程占比对比见 [跨领域真实输入下文档解析类agent负载的代表性评估](representativeness-assessment.md)。该报告复用已有证据，明确区分 XLSX 总 CPU 与 PDF 用户态周期口径。

三个新增 XLSX 的入口统一命名及历史证据边界见 [xlsx-script-names.md](xlsx-script-names.md)。正式镜像为 `office-trace-replay:openeuler-release`，已通过安装态检查和七项用例的新单轮执行（PDF N=1/N=10 分开，共十个配置），新进程 CPU 结果单独记录；历史 v12 功能结果仍按原版本保留。

以下材料保留为历史设计或兼容性依据，不作为当前构建/运行命令：

- [replay-contract.md](replay-contract.md)：最初 derived-v1 引擎的轨迹选择与回放机制。
- [document-oe-reuse.md](document-oe-reuse.md)：初次导入 document-oe 时的来源和环境说明；runner 后续已版本化。
- [legacy-compatibility.md](legacy-compatibility.md)：旧 workload 的字节保护边界；executor 是独立版本化文件。

历史审计失败、旧性能结果及早期镜像记录保留原文。当前正式镜像安装状态见 `reports/formal-image-release.json`；历史 v12 功能结果见 `reports/evidence/v12/index.json`，性能版本由分析选择单独关联。README 不重复列出历次调试过程，完整输入/产物与 perf raw 不随说明文档提交。
