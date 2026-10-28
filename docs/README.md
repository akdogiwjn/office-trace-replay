# 文档导航

- [文档解析类 Agent 代表性评估报告](representativeness-assessment.md)：数据集、轨迹、回放、采集方法及七例五轮对比。
- [HTML 放映版](representativeness-assessment.html)：按正式报告原文分页，白底黑字；单文件离线放映，方向键翻页、F 全屏，目录可跳页。
- [文档解析类 Agent 实验数据汇总记录](experimental-results.md)：完整方法、五轮明细、逐采样点曲线、完整排名与逐次采集来源。
- [构建与验收证据](evidence/README.md)：镜像资格、构建日志、源码绑定和目录整理记录。
- [采集与分析入口](../analysis/README.md)：采集脚本、分析代码、原始数据位置与离线重算步骤。

`docs/` 用于阅读与核对证据；`analysis/` 保存采集分析程序及其数据产物。根目录不再单独设置 `reports/`。

HTML 放映版保留正式报告的完整文字与表格，曲线来自绑定的逐采样点数据；全部样式与图表内嵌，不含装饰性效果。重新生成：

```bash
python3 -B scripts/build_presentation.py
```
