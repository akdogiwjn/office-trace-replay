# 构建与验收记录

- [第七节精简与操作归并（当前）](chapter7-operation-equivalence-update-20261112.json)：十二项大档并列精确函数与同类操作权重；简化表格、说明和结论，保留十二图及原始用例 Topdown，HTML 未改。

- [原始任务推荐调整](original-task-recommendations-update-20261108.json)：函数路径扩展推荐 013／016／021／026／029，操作扩展优先 021；保留规模数据与原精确组合记录。

- [原始 021 推荐调整](original-021-recommendation-update-20261108.json)：操作扩展建议改为原始任务 021；规模复测编号与数据保留，HTML 未改。

- [第七节阅读顺序与文字审阅](chapter7-reading-order-review-20261108.json)：7.5 先给补充用例建议，7.6 展示十二张过程图；数据表、测量结果与 HTML 保持不变。

- [规模复测与补例报告核验](scaling-hotspot-report-update-20261106.json)：7.3 按初测、规模复测、操作归因和最少补例重写，7.6 同步结论；34 个主要操作函数的三例最少组合、删例检查与完整差额分别保留。原七例正文、十二项 Topdown 图表、payload 和 HTML 未改。
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
- [扩展报告可读性修订核验（历史快照）](task-operation-readable-revision-v2.json)：软件用途与表格读法、完整四项 Topdown 变化、十二张曲线；63 页 HTML 布局通过，全部比较数值及 533 个过程点不变。
- [扩展报告首版核验（历史快照）](task-operation-validation.json)：首版 24 组对照、533 个过程点及当时 50 页 HTML 的布局检查，保留原记录。
- [最终仓库审计](repository-audit-20261104.json)：191 项测试、冻结材料与离线依赖核对、隔离 checkout 检查，以及本次收尾修复。
- [完整函数出现范围补充（上一轮快照）](function-hotspot-presence-v1.json)：旧 OPM、旧 TLC 及其并集与十二项新任务的 36 组三分区；当轮文档和 HTML 均已同步。
- [热点代表性视图（历史快照）](hotspot-representativeness-view-v1.json)：完整周期加权覆盖、输入规模解释边界、013／021／029三例方案与严格七例集合覆盖核验；原测量与 HTML 字节保持不变。
