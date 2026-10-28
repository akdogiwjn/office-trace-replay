# 构建与验收记录

- [当前执行镜像验收](image-qualification-agent-traces.md)：环境、七用例执行、独立审计与 43 个旧 workload 的冻结检查。
- [机器可读资格](image-qualification-agent-traces.json)：实际 image ID、构建时文件哈希及证据索引，保持原始字节。
- `image-build-*.json/.log`：当前镜像的离线构建过程与修复来源；不是另一套运行实现。
- [数据保留策略](data-retention.json)：仅保留最新七例各五次 perf 与 Topdown 采集；旧分支和试跑产物已删除。
- `repository-cleanup.json`：分支、目录与镜像整理结果，记录实测数据的保留和迁移，不替换原始采集证据。

正式评估报告在 [docs/representativeness-assessment.md](../docs/representativeness-assessment.md)，五次测量入口在 [analysis/README.md](../analysis/README.md)。
