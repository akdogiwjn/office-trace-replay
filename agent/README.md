# 新五个 Agent 数据集组件

这是根项目的 `agent/` 组件，与 `../document-oe` 一起构建成同一个七数据集镜像。Git 分支是 `agent-traces`；原 main 工作区及其未提交修改保持不动。

本组件内只保留一个公共运行入口 **`replay.py`**。每个数据集拥有自己的 `run.py`、helper、检查/导出/摘要脚本、输入、Skill、loop verifier 和 independent auditor，运行时不导入其他数据集或共享业务模块。`tools/` 只是离线导入/代码生成工具，正式运行不调用它。

旧 TLC/OPM 单独放在根项目 `document-oe/` 目录，入口 **`document-oe/run.py --scene …`**，不由本入口调度。两套代码独立，一个镜像同时安装；无需第二个仓库或第二个镜像。

## 五个来源

| 数据集 | 主轨迹 | 实际业务 helper |
|---|---|---|
| eGRID | 第二轮 `xlsx-egrid-20261027T032347Z-225eb8e9` | `helpers/enhance_energy_report_v2.py` |
| HR Metro | 第二轮成功补跑 `xlsx-hr_metro-20261027T042913Z-2c0c625f` | `helpers/enhance_workforce_v2.py` |
| Industry Productivity | 第一轮 `xlsx-industry_productivity-20261027T015504Z-769d363e` | `helpers/enhance_workbook_v1.py` |
| IRS W-4 | 第一轮 `pdf-irs_w4-20261027T021455Z-c206db3d` | `build_field_values.py`、`run_batch.py` |
| SBA 1919 | 第一轮 `pdf-sba1919-20261027T021613Z-ccd6fc4e` | `build_field_values.py`、`run_batch.py` |

两轮 trajectory、tool events、运行身份、独立验收结果及 Python 捕获修订均保存在各自 `evidence/round-*`。主 helper 字节与捕获对象核对，不拼接两轮 helper。备用轮次作为证据保存，尚未编译成第二套可执行变体。

目录布局：

```text
replay.py                         # 唯一公共运行入口，预检/分发/可选宿主 Docker 留证
datasets/<dataset>/
  run.py                         # 私有循环/超时/归档执行器
  recipe.json                    # 四阶段 argv + 逐调用来源
  provenance.json / lock.json    # 输入、脚本、原轨迹和适配绑定
  environment.json               # 原 Agent 镜像与版本
  seed/input/                    # 原始输入、原 Agent-facing verifier
  seed/output/workbook_features.json  # 仅 XLSX；原任务已有的准备元数据
  scripts/                       # 本数据集私有业务脚本
  skills/                        # 本数据集自己的冻结 Skill
  audit.py / audit_source/        # 循环外独立深审，私有完整源码及资产
  evidence/round-{1,2}/           # 真实历史证据，不作为生成结果输入
```

## 执行步骤与适配边界

| 阶段 | 三个 XLSX | 两个 PDF |
|---|---|---|
| P01 | 所选轨迹的源表结构/特征检查，内联代码原样提取成脚本 | 原 Skill 字段检查、字段抽取、空白模板渲染 |
| P02 | 运行所选最终 Agent helper 一次；保留其内部 copy/load/save | 运行原 Agent 字段 mapping helper |
| P03 | 原 Skill `recalc.py` 一次；所选公式/缓存检查；缓存 CSV 导出 | 原 Agent batch helper，10 次填写 + 10 次填写结果渲染 |
| P04 | 私有 loop verifier（原检查＋复用缓存的 CSV 核验）；当前回放摘要 | 当前批次摘要；原数据集 loop verifier |

这是**从真实轨迹整理的最终有效工具链**，不是完整 Agent trajectory 重放：不运行 LLM、不重做修错、预览、无关抽查或 process.poll 等待。保留哪些 inspection、各自从哪个 tool call 提取，在 `recipe.json` 中逐项记录。HR 原轨迹没有单独的只读缓存打印脚本，不为凑脚本数量添加一次大表读取；缓存读取仍由原 recalc、CSV 导出和业务 verifier 完成。

三个 XLSX 的 Skill `recalc.py` 均保持原字节，SHA256 `cf419d15e02965aeaec17773c05b61303f7f520f67fa2696547e7da07502eac7`；不改其普通加载模式、超时或内部检查，不替换成 document-oe 定制版。openEuler 的私有 soffice 包装器仅将实际 profile 对准原 Skill 安装宏的标准目录，不创建临时 profile。

因此不额外清理默认 LibreOffice profile；同一容器重复运行可能复用原 Skill 安装的宏。正式比较时每个数据集单独使用新容器，避免把跨数据集的 profile 暖态当成输入差异。

唯一明确的业务发布适配：把原轨迹的 prepared CSV 复制换成本轮最终工作簿的缓存导出。文件名/表头/标签/顺序不变；指标取 B5:B9，对账和情景行分别取 B5/B6/B9、B15/B16/B9。每个导出脚本只加载一次 `data_only=True, read_only=True` 工作簿、顺序读取小 Summary，不重算指标、不扫原始大表、不保存 XLSX。循环内 verifier 复用自己的既有 Summary 缓存，读取两份小 CSV 并检查表头、标签、顺序、行列数和数值容差；不新增工作簿加载。循环外深审也检查当前缓存与 CSV 一致性，替代 prepared 字节一致性。原 CSV 和原 verifier 保留在 seed 作为历史输入证据，适配的 verifier 单独位于私有 scripts，并声明哈希与适配范围。

摘要也不复制原 Agent 声明的成功次数、hash。W-4 原 Agent write 的摘要改为根据本轮文件及 driver logs 生成；SBA 原 driver 生成的摘要保留。独立深审使用导入时明确冻结的 auditor，记录为审计版本，不冒充 Agent 当时执行版本。HR 空字符串/eGRID 合并单元格策略保留各自已有修正。

每轮 `roi.jsonl` 同时记录单调时钟/实时时钟纳秒，明确 `loop_including_reset`、`workflow` 两种区间；归档和输出哈希只在二者结束后执行，标为 `archive_excluded`。独立审计标为 `independent_audit_excluded`。实际 CPU 研究必须按这些 ROI 和 workload 进程树筛选；整段入口进程 CPU 仍包含归档，不能用墙钟时间替代 CPU 占比。两种 ROI 是替代口径，不能相加。

归档失败有独立 `archive_error`，保留原 `workload_status/error`；整体失败并停止。记录发布失败尝试写 `*.emergency.json`，连应急记录都写不了则向 stderr 写失败信息。消费者须检查退出码及这些失败记录，不能只读取旧 summary。

## 静态检查与小型测试

```bash
python3 -B replay.py --validate-only
python3 -B -m unittest discover -s tests -v
```

这两个命令不打开大表、不运行 helper/LibreOffice，不调用模型；冻结检查会流式读取输入字节以核对 SHA256。数据集目录可以单独复制到任意位置，目录名保持 dataset ID 后执行自己的 `run.py`；不需要其他四个数据集。

## 共同镜像与运行验证

默认 `--runtime document-oe` 使用根项目的共同 openEuler 环境：Python 3.12.3、openpyxl 3.1.5、LibreOffice 25.8.7.3、Poppler 23.12.0；无需另建镜像。各例 `environment.json` 保留原 Agent 镜像 `sha256:592e2675de4c9c657b6d1859893ffe72c8ce19875854c7902f405f9ea6524a65` 与原 Office 24.2.7.2 身份，`replay-environment.json` 描述当前目标环境，两者不能混称。`--runtime original` 仅供原环境诊断，不是本镜像默认配置。

镜像构建及两个入口的完整命令见根 README。正式留证推荐从宿主使用同一入口：

```bash
python3 -B agent/replay.py --docker-image office-trace-replay:agent-traces \
  --dataset irs_w4 --loops 1 --results-dir "$PWD/results"
```

此宿主模式自动保存真实启动前后 inspect，启动前材料只读挂载到容器；执行器核对 hostname 和 host launch plan 的 dataset lock，在 reset 前拒绝不一致。每次运行 `context/` 复制冻结 lock/provenance/recipe/环境及其哈希，关联实际容器和镜像。`REPLAY_ACTUAL_IMAGE_ID` 不作为 inspect 证据。手动直接 Docker 启动但未提供 inspect 时记录 unknown、`evidence_complete=false`，只能作为功能结果，不能冒充来源齐全的正式性能证据。执行器对 Python/库/Office 版本做实际探测。仅在可丢弃容器内允许 workspace reset 与 Skill 链接替换。

启动器还会固定 document-oe 的解释器与库路径，而非仅检查版本号：系统 Python 启动会 exec 到 `/opt/document-bench/.venv/bin/python`，子进程 PATH 优先使用该 venv 和 `/opt/libreoffice25.8-symbols/program`；清除外部 Python 包路径并禁用用户 site。`environment.json` 运行记录包含实际解释器、libpython、Python 包位置及 soffice 适配器路径。准备工作仍只替换本用例的 Skill 链接，未引入共享业务脚本。

单轮成功后，针对结果目录中 `iteration-0001/workspace` 使用同一入口 `--dataset … --audit-only <归档workspace>` 做循环外独立验收；它不重新生成工作簿。审计记录前后 output hash，不能声称仅靠 hash 检查就强制了只读挂载；需要强制保护时应把归档 workspace 另行只读挂载。

只从项目根目录的 Dockerfile 离线构建共同镜像；本组件没有 Dockerfile。

2026-10-27 已完成镜像构建、七用例单轮功能检查和本组件五用例的只读独立验收；本轮未采集性能。IRS W-4 的成功输出来自首次构建镜像，在最终镜像只做了修复后的独立复验，其余六个 workload 在最终镜像执行。详见[当前验收报告](../reports/image-qualification-agent-traces.md)。冻结来源中的 `compiled_static_only_not_replayed` 是导入时快照；不改写来源历史，使用单独验收记录关联当前实际镜像与执行结果。
