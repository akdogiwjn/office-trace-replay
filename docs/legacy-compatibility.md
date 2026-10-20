# 旧执行兼容性

恢复的是实际 document-oe 中已经整理、适配的两个执行用例，不是最早的原始 Agent 日志，也不是重新跑 Agent 后产生的 OPM/TLC。

| 项目 | 旧基线的保留方式 |
|---|---|
| PDF recipe | 字节不变；21 个 read/write/exec 调用 |
| XLSX recipe | 字节不变；15 个 read/write/exec 调用 |
| runner 与 timed wrapper | 从原绝对路径运行，作为 executor 独立版本化；旧 workload 仍严格冻结 |
| helpers、Skill、旧 verifier | 原文件及嵌在 recipe 中的 write 内容不变 |
| CSV | 保留旧 export_xlsx_csv.py 执行，不用参考 CSV 复制替代 |
| helper 写入时间 | 原配方仍在循环内写代码，不移到准备阶段 |
| shell 与调用顺序 | 不增加 set -e/pipefail、不合并、不删减、不改 stdout |
| Office | 原 recalc.py/profile 逻辑、原 600 秒超时；不走新包装器 |
| Python | 按用户要求默认原 venv 3.12.3；系统 3.11.6 可显式选择，原脚本未修改 |
| PDF 数量 | 原默认 1、原参数支持 10；不强制改为 10 |
| 结果与计时格式 | 由原 loop/timed loop 生成，无额外 verifier 加入计时链 |

43 个 workload 文件与 2 个 executor 文件分开记录 SHA256、mode 和 size；源容器与镜像安装文件均检查。源码、recipe、输入与业务参数相同不等于每次墙钟时间相同，性能比较仍使用用户原先相同的解释器、参数和采集入口。

原源目录的缓存字节码、Office 临时锁和未执行的旧 recipe 备份没有作为活动源码冻结；所有实际执行的文本脚本和输入字节保持原样。新 OPM/TLC 的历史结果只作衍生版本参考，不能覆盖这两个基线。
