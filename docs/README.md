# 文档导航

- [文档解析类 Agent 代表性评估报告](representativeness-assessment.md)：原七例跨行业输入实验保持原文，末尾追加十二项扩展任务操作与原始 OPM／TLC 对照。
- [HTML 放映版](representativeness-assessment.html)：按正式报告原文分页，白底黑字；单文件离线放映，方向键翻页、F 全屏，目录可跳页。
- [文档解析类 Agent 实验数据汇总记录](experimental-results.md)：七例五轮明细，以及十二项扩展操作的完整指标、24 组基准对照、逐点曲线与来源。
- [构建与验收证据](evidence/README.md)：镜像资格、构建日志、源码绑定和目录整理记录。
- [采集与分析入口](../analysis/README.md)：采集脚本、分析代码、原始数据位置与离线重算步骤。

`docs/` 用于阅读与核对证据；`analysis/` 保存采集分析程序及其数据产物。根目录不再单独设置 `reports/`。

HTML 放映版保留其发布时的报告文字与表格，曲线来自绑定的逐采样点数据；全部样式与图表内嵌，不含装饰性效果。仅在明确要求更新 HTML 时重新生成：

```bash
python3 -B scripts/build_presentation.py
```

扩展任务操作采用[统一环境的新十二项结果](../analysis/docops/processed/task-operation-expansion-20261104/comparison.json)，原 Debian 首批对比仅作为[历史记录](../analysis/docops/processed/first-comparison-batch-20261103/report.md)。不同批次分别汇总，不混算重复次数。

第七节增加软件用途、热点表读法、四项 Topdown 原值与变化、十二张中文过程图和最终覆盖判断；此前 HTML 为 63 页。[修订核验](evidence/task-operation-readable-revision-v2.json)确认测量数值不变、原七例章节不变，并记录浏览器排版检查。

此前 Markdown 的 7.3.1–7.3.3 补充了旧 OPM／TLC 完整函数清单的出现范围，[函数出现范围核验](evidence/function-hotspot-presence-v1.json)记录当时三分区守恒与来源；上一轮 HTML 同步至 68 页。

当前 Markdown 第七节按“样本口径→软件栈→原始规模与大规模覆盖对比→同类操作与缺口→原始用例 Topdown→补充建议→过程曲线”组织。7.3 先展示原始任务覆盖与规模复测，再对公共操作逐函数归并，表 7-5 合并说明剩余函数用途。7.4 保留十二项原始任务的七维余弦与欧氏距离，7.6 保留十二张过程图。旧 OPM／TLC 为核心：具体函数口径优先补 `013＋021`；计入同类操作后先补 `021`，长文档研究再加 `009`。组合平均覆盖及逐例明细见[双口径选型核算](../analysis/docops/processed/supplement-selection-20261116/analysis.md)；7.2 按“上层处理工具、底层计算库”两层展示，表 7-3 同表列出旧两例与新十二项的页面预览、原生库前三名及旧例已有标记，并说明工作簿 ZIP 与 PNG 压缩来源；7.3 再分析函数和操作覆盖。[预览与逐库热点核验](evidence/old-new-preview-comparison-20261116.json)、[原始与规模复测对照](evidence/original-to-large-coverage-review-20261116.json)和[操作归并核验](evidence/chapter73-deep-operation-review-20261115.json)、[公共操作依据与 PPT 交叉对照](../analysis/docops/processed/operation-equivalence-deep-20261115/analysis.md)提供当前入口。原始、小档、大档的完整 36 配置保留在[统一分析](../analysis/docops/processed/unified-scaling-final-20261108/analysis.md)。HTML 保留上一轮发布快照。

仅更新当前 Markdown 第七节，保留数据与原七例内容：

```bash
python3 -B analysis/docops/chapter7_editorial.py --publish
```

该命令不生成 HTML；只有明确要求同步放映版时，才另行调用上文的 `scripts/build_presentation.py`。

[Python 与 Word 说明核对](evidence/chapter73-runtime-explanation-20261115.json)记录表 7-5 的具体运行时操作、Writer 库来源，以及三项 Word 大档的压缩／PNG 和 Word 函数权重对照。

[追加章节绑定](evidence/task-operation-extension.json)记录两份原文前缀的长度与 SHA256，并绑定新章节、图表与数据源；放映版会同时核验原文和新增内容。
