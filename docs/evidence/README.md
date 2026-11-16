# 构建与验收记录

- [7.3 函数与操作两种补例结论](chapter73-two-coverage-conclusions-20261116.json)：对十二项大档核算原始用例组合；具体函数选 013＋021，同类操作先选 021、Word 专项再加 009；保留逐函数依据，HTML 不变。

- [7.3 删除补例增益表与重复说明](chapter73-trim-20261116.json)：删除表 7-5A 及后续的 PPT 增益、013 构建和选型建议段落；保留其他正文、底层分析数据和 HTML。

- [7.3 原始规模→大规模→同类操作覆盖（当前）](original-to-large-coverage-review-20261116.json)：十二项原始覆盖作为起点，同表展示大规模覆盖与百分点变化，再分析大档的同类操作和剩余缺口；测量数据、7.2 表格和 HTML 不变。

- [表 7-3：旧两例与新十二项的预览和原生热点（当前）](old-new-preview-comparison-20261116.json)：十四项同表对照，补充页面预览类型和 zlib 按调用脚本的权重，区分工作簿 ZIP 与 PNG 压缩；原测量数据和 HTML 不变。

- [表 7-3：逐库热点前三名（上一版）](top-native-libraries-review-20261116.json)：从完整原生 profile 按具体库重新汇总，展示十二项原始任务的前三名及旧 OPM／TLC 出现标记；完整分母保留未解析部分，原测量数据和 HTML 不变。

- [7.2 上层工具与底层库两层对照（当前）](two-layer-software-review-20261116.json)：按四类场景列出 Python 库及外部程序，再对照主要底层库；保留脚本和热点权重，7.3 后续分析与 HTML 不变。

- [7.2 Python 库与外部程序说明](external-programs-clarification-20261116.json)：将 Pillow 归入 Python 库，分别说明 LibreOffice、Poppler 命令、ImageMagick 命令的独立进程与底层共享库。

- [7.2 新旧软件与库对照（上一版）](library-coverage-review-20261116.json)：区分 Python 库、LibreOffice 模块及原生共享库；五类 Python 文档库和十六类底层库逐项列出旧 OPM／TLC 与新任务的使用证据。7.3 之后、测量数据和 HTML 不变。

- [功能模块与共享组件说明（上一版）](component-layer-explanation-20261116.json)：说明模块、代码库及复用关系，解释函数覆盖与同类操作覆盖；旧两例为核心、PPT／Word 按需选配。测量结果和 HTML 不变。

- [7.3 公共操作深度核对](chapter73-deep-operation-review-20261115.json)：公共操作逐函数归并，追加原始 PPT 的边际覆盖；精简建议为旧两例＋021，保留 Word 专用路径与未知部分。原始数据、Topdown、曲线及 HTML 不变。

- [表 7-5 合并展示](table75-merged-functions-20261115.json)：将剩余函数的用途与权重合为一列，统计数据及 HTML 不变。

- [表 7-5 剩余函数用途说明](table75-residual-explanation-20261115.json)：说明公共组件与解释器的具体工作，区分函数差异和新增操作；所有覆盖权重及 HTML 不变。

- [7.3 同类操作进一步归并](chapter73-operation-refinement-20261115.json)：七类归并绑定旧例函数；完整保留文档路径、其它已解析和未解析权重，按操作总权重判断补例价值。HTML 未改。

- [7.3 Python 与 Word 路径说明](chapter73-runtime-explanation-20261115.json)：具体说明解释器在做什么、Word 函数来自哪些 LibreOffice 库，并对照三项 Word 的热点权重。HTML 未改。

- [7.3 逐例缺口与补例建议](chapter73-gaps-update-20261115.json)：先看大档函数覆盖，再计同类操作，逐例说明剩余部分；补例建议为 PPT 021＋Word 009。Topdown、过程图及 HTML 保持不变。

- [第七节精简与操作归并](chapter7-operation-equivalence-update-20261112.json)：十二项大档并列精确函数与同类操作权重；简化表格、说明和结论，保留十二图及原始用例 Topdown，HTML 未改。

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
