# 第三轮规模扩充只读复核

结论：确认真实输出规模增加、十六项回放均记录成功、归档完整，业务验收和规模对照仍需修正。

- 完整回读1337个归档文件的大小及SHA256，均匹配。
- 官方十二项与统一24项payload静态校验通过；已有八项的100个任务文件逐字节一致。
- 本轮没有执行helper、LibreOffice、workload或性能采集，没有修改代码或历史证据。

## 1. 016验收存在已复现的漏检

在/tmp临时副本仅改变OOXML缓存，调用现有生产check()：

| 改动 | 检查结果 |
|---|---|
| Forecast Model!E2001：1006.86 → 999999999 | 全部checks通过，caches_present=true |
| Dashboard!B539：3991.55 → 缺失缓存 | 全部checks通过，caches_present=true |

宿主Python3.11.6、openpyxl3.1.5；未调用重算。本次证据直接针对check()；没有冒充在镜像内重跑完整CLI。原正式工作簿哈希保持b7a718159b6a2f3a5d42b773abe9cd9582a102cec54ba852e24f07d6e068a9d6。

需要验证全模型数值与图表数据区的缓存值。两个场景也应验证完整数值，而不只验证标记和异常数量；复用相同check()的post-verify不能补足这一盲区。

## 2. 016图表与异常表偏离方案

大档向同一图表放入500个业务单元，而方案要求四期汇总；已有dashboard.png显示横轴拥挤。还新增每单元SUMIF聚合，改变原计划的计算组织。

默认场景有252/1292条异常，但两档Exception Review均仅十条。所有模型行的标记已有计算，不能因此声称完整异常明细也已输出；应完整生成异常表，首页只展示摘要。

## 3. 009目录页码错误

009-u500的已有page-2.png显示Control Exceptions位于第4页，实际page-4.png仍是Response Timeline续表。构建脚本保留静态3/4/5/6/7页码，验证器只检查TOC字段存在。应按实际分页更新目录并验证标题目标。

## 4. 029不只是规模变化

父任务八类公开页为title/agenda/market_context/kpi/risks/mitigation/decision/appendix。

变体八类变成market_context/kpi/risks/mitigation/decision/action_register/data_notes/unit_summary。封面、议程和附录被替换，部分页面对象构成也改变。应恢复父任务页面类型并逐单元参数化，或明确登记成操作改造，不能直接以纯规模扩充解释后续热点差异。

## 5. 新镜像采集入口尚未接线

pilot.py仍读取docops/docker/current-image.json，其中candidate是57483856…，不是新scaled镜像6b32b0…；CLI也没有单独镜像选择参数。后续应显式选择并核验scaled镜像与内置payload路径，不将旧candidate加挂载采集写成新镜像采集。

## 后续处理

保留所有成功和失败记录，先修受影响脚本、验证器、绑定及镜像选择；针对受影响变体重验，其他已通过任务不机械重跑。业务脚本改变后需重新打包新镜像。随后再开始正式性能采集。
