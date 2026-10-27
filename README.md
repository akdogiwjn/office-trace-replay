# 七数据集、双入口的文档回放镜像

目标是**一个新容器支持全部七个数据集**，容器内分开保存两套执行代码；不是两个镜像或两个独立发布项目。

| 代码目录 | 对外入口 | 数据集 |
|---|---|---|
| `document-oe/` | `document-oe/run.py --scene …` | 旧 TLC、OPM |
| `agent/` | `agent/replay.py --dataset …` | eGRID、HR Metro、Industry Productivity、IRS W-4、SBA 1919 |

这是 `office-trace-replay` 的 `agent-traces` 分支。当前 worktree `/home/lcq/office-trace-replay-agent` 用于保留原 main 的未提交修改。之前误建的 `/home/lcq/document-oe-replay` 已移入本项目，不再是顶层独立仓库；其初始化 Git 元数据仅保留在忽略的 `.local/` 下，不作为运行依赖。

```text
Dockerfile                         # 唯一镜像构建入口
container-contract.json            # 七用例、双入口、共同环境
document-oe/
  run.py / lock.json                # 旧用例入口和冻结绑定
  assets/                          # 43 个旧 workload 文件，原字节不动
agent/
  replay.py / suite.json            # 新五例共用的调度入口
  datasets/<dataset>/              # 每个数据集完全独立的执行材料
    run.py / recipe.json / lock.json
    seed/ scripts/ skills/ audit_source/ evidence/
tests/                              # 单镜像打包和新旧上下文检查
```

没有改动原 document-oe 容器或原 replay main 工作区。两个入口不导入彼此的业务代码。每个新数据集都有自己的 helper、Skill、检查、CSV 导出、摘要、loop verifier 和 independent auditor。

旧 43 个 workload 文件与已有冻结记录一致；只有旧入口/executor 的独立封装单列记录。新五例保留真实 Agent helper 和原 Skill `recalc.py`；CSV 发布改成从本轮最终工作簿缓存导出，明确记录为人工回放适配。

## 共用环境与上下文

唯一 Dockerfile 离线继承锁定的正式 openEuler 镜像：Python 3.12.3、openpyxl 3.1.5、LibreOffice 25.8.7.3、Poppler 23.12.0。原 Agent 的 Ubuntu/LibreOffice 24.2.7.2 环境仍单独冻结在各例 `environment.json`；目标环境在 `replay-environment.json`，不把两者写成相同。

启动设置沿用 document-oe 切片脚本的实际路径：`/opt/document-bench/.venv/bin/python`（底层 `/opt/python-3.12.3/bin/python3.12`）以及 `/opt/libreoffice25.8-symbols/program`。两个入口和五个私有 runner 在正式执行前固定 venv/PATH；误用系统 Python 启动时自动 exec 到固定解释器。清除外部 `PYTHONHOME/PYTHONPATH/PYTHONUSERBASE`，禁用用户 site-packages，子进程继承同一环境；静态 `--validate-only` 仍可在宿主运行。新例记录并校验实际 Python、libpython、包加载路径。XLSX 私有 soffice 适配器继续优先于公共 Office 路径，以保留原 Skill 的标准 profile 规则。

新 Skill 原样保留。每个新数据集自带 `soffice` 路径适配器，只让 symbols 版 Office 使用 Skill 原本安装宏的标准 `/root/.config/libreoffice/4`；不替换 `recalc.py`，不添加 TLC 缓存检查，也不改成每次临时 profile。环境迁移需要新一轮真实功能验证，不能拿原环境成功证据替代。

新三例的 XLSX loop verifier 在原数据集检查基础上，复用已读取的 Summary 缓存核验两份 CSV，不额外打开工作簿。原 Agent-facing verifier 保留在 `seed/input/`，回放适配版本单独位于各自 `scripts/verify_xlsx_enhanced.py`，其来源和哈希写入 recipe，原始轨迹不改写。

原脚本使用固定 `/root/.openclaw/skills/...` 路径。新入口安装该用例 Skill 链接，旧入口恢复 document-oe 链接；两边使用同一个非阻塞 OS 锁，支持同一容器顺序运行，拒绝并行切换上下文。结果目录与 reset workspace 分开。

## 检查与构建

```bash
make validate
make test
# 先核对本地基础镜像 ID；目标标签已存在时拒绝覆盖。
make image IMAGE=office-trace-replay:agent-traces
```

构建不下载依赖、不调用模型、不执行正式 helper 或重算；构建阶段只检查冻结绑定和安装文件。构建入口使用本地基础镜像标签，并先核对其 ID 与 `container-contract.json` 一致；不将裸 image ID 当作 Dockerfile 的远程镜像名。后续构建请使用新的候选标签，通过验收后再更新正式标签。

## 同一镜像的两个入口

以下为两套独立入口的使用示例。当前镜像的功能资格与实际执行身份见文末验收记录：

```bash
mkdir -p results

# 新例正式留证推荐从宿主使用同一个入口；自动 create → inspect → start，保留容器。
# 无源码挂载；宿主与镜像的 dataset lock 不一致时在 reset 前拒绝。
python3 -B agent/replay.py --docker-image office-trace-replay:agent-traces \
  --dataset hr_metro --loops 1 --results-dir "$PWD/results"

# 默认 ENTRYPOINT 是新五例的入口。
# 此手动方式未提供 inspect 时只证明功能结果，evidence_complete=false。
docker run --rm --network none -v "$PWD/results:/results" \
  office-trace-replay:agent-traces --dataset hr_metro --loops 1

# 同一镜像切换到旧入口；无需另建镜像。
docker run --rm --network none -v "$PWD/results:/results" \
  --entrypoint /opt/document-bench/.venv/bin/python \
  office-trace-replay:agent-traces \
  /opt/office-trace-replay/document-oe/run.py --scene xlsx --loops 1

# 旧 OPM 的 10 份模式，与新 PDF trace 的规模对应。
docker run --rm --network none -v "$PWD/results:/results" \
  --entrypoint /opt/document-bench/.venv/bin/python \
  office-trace-replay:agent-traces \
  /opt/office-trace-replay/document-oe/run.py --scene pdf --pdf-applicant-count 10 --loops 1
```

也可启动一个保留容器，再依次 `docker exec` 上述两个 Python 入口。不要并行运行两个入口。默认新入口无 `--dataset` 时只运行新五例，不暗中合并调用旧入口。

新例每次运行在 `context/` 保存 lock、provenance、recipe、环境声明及哈希索引。宿主启动模式还保存启动前后真实 Docker inspect，并把启动前 inspect 与 launch plan 只读提供给执行器；执行器核对容器 hostname 和该用例 lock。宿主证据在 `results/.launch/<stamp>/`。不依赖手填的 image ID。

每轮 `roi.jsonl` 使用实际 `CLOCK_MONOTONIC` 纳秒记录 `loop_including_reset` 与 `workflow` 起止；前者包含 reset，后者只包含 P01–P04 和循环内检查。两者是替代口径，不能相加。`archive_excluded`、`independent_audit_excluded` 单独标记，归档复制与哈希位于两个测量区间结束之后。采集端仍须按 ROI 和 workload 进程/线程筛选；直接统计整个入口的 CPU 会包括这些额外工作。

记录分开保存 `workload_status`、`archive_status`、整体 `status`。归档失败不抹掉 workload 结果，整体失败并停止后续轮次；原子写入失败时输出 `*.emergency.json`，应连同退出码检查。若连应急文件也无法写入，错误输出是最后的失败证据，不能据旧 `in_progress`/success 文件认定完成。

## 当前镜像资格

2026-10-27 已构建并验收 `office-trace-replay:agent-traces`，实际 ID 为 `sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。七个用例均有单轮成功与循环验证证据；五个新用例的只读独立验收通过，输出前后哈希一致。PDF 实际填写规模均为 N=10。52 项测试通过，旧 43 个 workload 文件未修改，537 个归档文件的大小和 SHA256 复核通过。

IRS W-4 复用本轮首次构建镜像中成功生成的产物，再由最终镜像的修复版独立验收器复验；两版该用例的冻结材料仅 `audit.py` 不同，未重跑填写和渲染。其余六项在最终镜像真实执行。完整范围与证据见[验收报告](reports/image-qualification-agent-traces.md)和[机器记录](reports/image-qualification-agent-traces.json)。

`provenance.json` / `suite.json` 中的 `compiled_static_only_not_replayed` 保留为冻结导入时的状态快照，当前执行资格以以上报告为准。镜像内 README 是构建前快照，不包含构建后的验收结论。原环境和“双仓库”历史报告继续保留，不替代本轮记录。

本轮未采集热点、Topdown 或其他性能数据，未生成新 Agent trace，未提交或推送。
