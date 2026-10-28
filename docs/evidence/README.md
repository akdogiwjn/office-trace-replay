# 构建与验收记录

- [当前执行镜像验收](image-qualification-agent-traces.md)：环境、七用例执行、独立审计与 43 个旧 workload 的冻结检查。
- [机器可读资格](image-qualification-agent-traces.json)：实际 image ID、构建时文件哈希及证据索引，保持原始字节。
- `image-build-*.json/.log`：当前镜像的离线构建过程与修复来源；不是另一套运行实现。
- [数据保留策略](data-retention.json)：仅保留最新七例各五次 perf 与 Topdown 采集；旧分支和试跑产物已删除。
- `repository-cleanup.json`：分支、目录与镜像整理结果，记录实测数据的保留和迁移，不替换原始采集证据。

正式评估报告在 [代表性评估报告](../representativeness-assessment.md)，五次测量入口在 [analysis/README.md](../../analysis/README.md)。

- [当前源码绑定](source-lock.json)：保留原镜像资格的原始哈希，单独记录宿主构建脚本的证据输出路径变更；不表示重建了镜像。
- [目录迁移核对](layout-migration.json)：原 `reports/` 与当前路径的映射、文件完整性及测量结果不变检查。原始 JSON/日志内的历史路径保持不变。

- [报告拆分与曲线核验](report-split.json)：两份文档的生成绑定、逐秒数据来源、测量结果不变与离线测试记录。
