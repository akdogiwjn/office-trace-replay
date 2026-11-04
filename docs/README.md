# 文档导航

- [文档解析类 Agent 代表性评估报告](representativeness-assessment.md)：原七例跨行业输入实验保持原文，末尾追加十二项扩展任务操作与原始 OPM／TLC 对照。
- [HTML 放映版](representativeness-assessment.html)：按正式报告原文分页，白底黑字；单文件离线放映，方向键翻页、F 全屏，目录可跳页。
- [文档解析类 Agent 实验数据汇总记录](experimental-results.md)：七例五轮明细，以及十二项扩展操作的完整指标、24 组基准对照、逐点曲线与来源。
- [构建与验收证据](evidence/README.md)：镜像资格、构建日志、源码绑定和目录整理记录。
- [采集与分析入口](../analysis/README.md)：采集脚本、分析代码、原始数据位置与离线重算步骤。

`docs/` 用于阅读与核对证据；`analysis/` 保存采集分析程序及其数据产物。根目录不再单独设置 `reports/`。

HTML 放映版保留正式报告的完整文字与表格，曲线来自绑定的逐采样点数据；全部样式与图表内嵌，不含装饰性效果。重新生成：

```bash
python3 -B scripts/build_presentation.py
```

扩展任务操作采用[统一环境的新十二项结果](../analysis/docops/processed/task-operation-expansion-20261104/comparison.json)，原 Debian 首批对比仅作为[历史记录](../analysis/docops/processed/first-comparison-batch-20261103/report.md)。不同批次分别汇总，不混算重复次数。

第七节增加软件用途、热点表读法、四项 Topdown 原值与变化、十二张中文过程图和最终覆盖判断；当前 HTML 为 63 页。[修订核验](evidence/task-operation-readable-revision-v2.json)确认测量数值不变、原七例章节不变，并记录浏览器排版检查。

只更新追加章节和对应曲线，不重新生成原七例内容：

```bash
python3 -B analysis/docops/operation_comparison.py --update --publish
python3 -B scripts/build_presentation.py
```

[追加章节绑定](evidence/task-operation-extension.json)记录两份原文前缀的长度与 SHA256，并绑定新章节、图表与数据源；放映版会同时核验原文和新增内容。
