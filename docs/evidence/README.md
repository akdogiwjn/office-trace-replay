# 构建与验收记录

- [当前镜像](current-image.json)：数值缓存修复版的构建、安装检查与默认标签；本次不包含正式 workload 重跑。
- [既有测量镜像验收](image-qualification-agent-traces.md)：环境、七用例执行、独立审计与 43 个旧 workload 的冻结检查，按原 image ID 追溯。
- [机器可读资格](image-qualification-agent-traces.json)：实际 image ID、构建时文件哈希及证据索引，保持原始字节。
- `image-build-*.json/.log`：当前镜像的离线构建过程与修复来源；不是另一套运行实现。
- [数据保留策略](data-retention.json)：仅保留最新七例各五次 perf 与 Topdown 采集；旧分支和试跑产物已删除。
- `repository-cleanup.json`：分支、目录与镜像整理结果，记录实测数据的保留和迁移，不替换原始采集证据。

正式评估报告在 [代表性评估报告](../representativeness-assessment.md)，五次测量入口在 [analysis/README.md](../../analysis/README.md)。

- [当前源码绑定](source-lock.json)：保留原镜像资格，通过 `packaging_only_changes` 和 `runtime_changes` 分别记录宿主构建脚本与测量后验收修复的差异；不表示重建了镜像。数值缓存修复及定向验证见 [xlsx-numeric-cache-fix.json](xlsx-numeric-cache-fix.json)。
- [目录迁移核对](layout-migration.json)：原 `reports/` 与当前路径的映射、文件完整性及测量结果不变检查。原始 JSON/日志内的历史路径保持不变。

- [报告拆分与曲线核验](report-split.json)：两份文档的生成绑定、逐秒数据来源、测量结果不变与离线测试记录。

- [HTML 放映版来源绑定](presentation.json)：当前文字报告、机器结果、曲线点与生成器的 SHA256，放映版不改变测量数据。
- [扩展任务操作追加绑定](task-operation-extension.json)：原七例章节的字节前缀保护、统一环境十二任务与 OPM／TLC 的比较来源，以及新章节和图表 SHA256。
- [扩展报告核验](task-operation-validation.json)：24 组基准对照、533 个过程点、原文章节不变核验，以及 50 页 HTML 的实际浏览器布局检查。
- [最终仓库审计](repository-audit-20261104.json)：191 项测试、冻结材料与离线依赖核对、隔离 checkout 检查，以及本次收尾修复。
