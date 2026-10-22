> 此文描述最初的衍生配方机制。当前两个旧基线直接执行 `legacy/document-oe` 的原程序，完全不使用此机制。以 README 和 suites/default.json 为当前入口定义。

# 整理与回放约定

## 研究对象

本版本实现 final effective tool execution replay。原始 Agent trajectory/tool-chain 包括 inspect、debug、失败、重写、retry 和轮询，完整保存为来源证据。不会把有效链的耗时解释成完整 Agent 运行耗时，也不会将不同大小工作簿的耗时归因于行业。

与 document-oe 一样使用 `scene-key-operations-v2`，四个阶段只是执行分组。复用其 `load_recipe`、`reset_workspace`、`execute_step`、`execute_call`、`run_command`、进程组超时清理和 business-result 检查。新代码负责七案例配置、冻结资产校验、环境锁、路径恢复、独立验收与逐项结果。

## 依赖与选择

不是简单删除非零退出码的命令。脚本修复后，必须选取对应有效版本；中间文件必须由生产命令重新创建。HR 需要保留原成功链中重建干净底稿的步骤，Retail/TLC 则保留构建、重算和 XML 缓存装配策略，避免直接通过 LibreOffice 保存破坏原始 worksheet 内容。

`replay/selections.py` 显式绑定七个 run ID 和事件下标。编译器为每项记录真实 call ID、ATIF step ID、原调用 hash、保留或删减的方式。所有 shell 调用增加 `set -e` 和 `pipefail`，等待完成，避免日志尾部的 echo/tee 掩盖失败。这是公开记录的执行控制适配，业务脚本字节保持不变。

冻结 helper 可以包含未执行的历史版本或诊断代码；它们是可追溯材料，不代表进入测量链。新增的 helper 读取阶段用于检查已恢复代码，脚本写入发生在准备阶段。对 Agent 原写出的描述性 JSON 保留固定 write 决策，验收仍依据实际生成的工作簿/PDF/PNG。`source-suite.json` 的 `replay_ready=false` 是原生成项目的历史状态，不改写；本项目的运行报告另行证明特定配方在特定环境是否通过。

## Capture gap

当前五个 `.tmp` 缺口来自 atomic verifier report 替换。每个决定要求修订捕获中存在最终 `business_verification.json` 的 moved_to 证据、最终内容对象，并确认所选链没有读取临时路径，最终 report 会由 verifier 重新生成。未知 gap 编译失败。后续新增 trace 需要重新审核，不按扩展名一律忽略。当前文件捕获不是进程读写 syscall 记录；依赖审核与实际隔离执行共同完成资格验证。

## 每次运行

1. 验证 project-lock、recipe、canonical 和资产内容 hash；检测 Python/库/Office/Poppler 实际版本。
2. 重置案例目录、TLC 两个指定 `/tmp` 中间文件、LibreOffice profile 与 shim；恢复原绝对工作目录和 Skill 路径。准备阶段不计入有效链执行时间。
3. 按固定命令执行，记录真实 stdout/stderr 和失败；任何步骤或验收失败不能标成功。
4. 检查链内 business report，再执行冻结 verifier 的完整模式（不延迟 enhancement summary），保存独立报告与新输出。

链内 verifier 位于第四阶段，耗时包含在有效链中；额外完整独立验收另记 acceptance_seconds。日志中的墙钟时间用于定位资格验证进度，当前没有性能指标采集。LO profile 每次重置，初始化开销属于该明确配置；未来 warm-profile 实验应使用不同的版本/配置。

网络关闭，没有 API key，也没有模型输出进入编译或执行。回放稳定指输入、执行决策、脚本、依赖与顺序固定；操作系统调度、文件时间戳、Office 序列化等不能据此声称完全相同。

## openEuler Office profile 适配

snapshot 的 symbols 构建 `bootstraprc` 设置 `UserInstallation=$ORIGIN/..`，而冻结的 Skill 把重算 macro 安装到正常的 `/root/.config/libreoffice/4`。直接调用会读错 profile 并等待不存在的 macro。旧 document-oe 已使用显式临时 profile 的重算桥；本项目保留原 trace 中 recalc.py 的字节，在 `runtime/bin/soffice` 统一追加 `-env:UserInstallation=file:///root/.config/libreoffice/4`。每轮清理该 profile，因此 macro 与实际 Office 使用路径一致。这是运行环境适配，不改业务公式，也不使用旧 TLC 专属的重算脚本替换通用 Skill。

## Provenance

`assets/import-lock.json` → `assets/canonical/<dataset>/canonical.json` → 输入/Prompt/manifest/Skill/源码/成功验收/trajectory/tool-events 的对象 hash；`recipes/suite.json` → 每个 executable recipe；`assets/project-lock.json` → 资产和执行代码；`reports/image-build.json` → 固定基础镜像和实际新镜像；资格报告 → runtime、project-lock、recipe hash、原 run ID、实际输出 hash。

正式原始输入 provenance 不改写。HR 仍保留原 cache acquisition 历史；用户官方下载字节一致的补充证据随 `source-suite.json` 与导入对象保存，不能把未独立观测的官方 ZIP 下载写成已验证。SBA 仍为可填写 04/2024 旧版，W-4 仍为 2026 冻结版本。
