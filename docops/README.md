# DocOps L3 最终有效执行回放

本目录在 `office-trace-replay` 中维护十二项 DocOps L3 的回放材料与镜像接入。
原始 Agent 执行、轨迹和任务证据仍保存在 `/home/lcq/agent_workload_characterization`；它只在导入时作为来源仓库。
回放使用的输入、脚本、命令与 Skill 已冻结在本目录，静态检查及未来镜像打包不需要访问来源仓库。
正式测量采用用户选定的“最终有效执行”，保留最终构建、必要修复、重算、最终渲染及 Agent 自写检查，排除探索、失败尝试和被替代版本。

当前候选已切换为 **`docops-replay:openeuler-unified-candidate-04`**，安装态、四种格式微型兼容性检查和十二项各一轮正式回放通过；统一环境十二项 perf 与 DevKit Topdown 均已完成，每路每项一份采集、内部十轮回放。此前 candidate-05 的十二项真实功能回放与首批 perf/DevKit 数据保留为原 Debian 环境证据；[初步结果](../analysis/docops/processed/first-comparison-batch-20261103/report.md)不改写为新环境结果。
原轨迹脚本版本与执行的关联是按事件顺序重建的推断；新包明确冻结所选字节，不把它说成历史逐进程运行时哈希。

## 当前统一环境

- 新镜像：`docops-replay:openeuler-unified-candidate-04`，实际 ID `sha256:57483856a27942ffd4aef853950ca66b00c12b0787aae6c1dac74371d03e6164`。基于原七例实际测量镜像 `office-trace-replay:measured-five-repeats`（`sha256:4baef136…301499`）离线构建；所有旧标签保留。
- Python 3.12.3、openpyxl 3.1.5、pypdf 6.10.0、Pillow 12.2.0、LibreOffice 25.8.7.3、Poppler 23.12.0、perf 6.6.0-145.3.23.154、DevKit 26.0.RC1。Python、Calc、Writer、Impress、Poppler、perf 的 SHA256/build-id 与七例基础镜像逐一一致；Python 及三个 LO 模块保留完整 `.symtab` 和 `.debug_info`。
- DocOps 专用 `/opt/docops/venv` 补充 python-docx 1.2.0、python-pptx 1.0.2、lxml 6.1.2、fontTools 4.68.0、reportlab 5.0.1；不改原七例 venv。所选脚本不直接导入 NumPy/pandas，新环境不安装它们。新增 lxml 仍是 wheel 的发布符号状态，没有完整调试信息；未声称所有扩展均已补齐符号。
- openEuler 原生 RPM 补充 ImageMagick 7.1.2.9、unzip 及依赖；`rg` 13.0.0 复用原 DocOps 工具，放在专用 venv/bin，动态依赖经检查并使用 openEuler 现有库，不覆盖系统库。core ELF 未升级，额外库、字体及 lxml 可用性随新环境独立记录；不把新环境视作历史 DocOps 环境的原样复刻。
- `bash -lc` 和子进程 `python`/`python3` 使用专用 venv。LO 开发构建默认 profile 位于安装目录，与上游 Skill 写入宏的 Linux 用户目录不同；专用 `soffice`/`libreoffice` 启动器将默认目录绑定到 `~/.config/libreoffice/4`，保留显式 `UserInstallation`，不修改冻结 Skill、任务脚本或共享 LO 二进制。
- 微型检查完成 DOCX/PPTX 创建、读取及 PDF 转换，PDF 创建/读写/渲染、拼图、ZIP 检查，以及全新用户目录下原 Skill 的 XLSX 重算（`3+4=7` 缓存正确）。十二任务的正式单轮功能结果另见下方记录。
- [构建输入](docker/records/20261103T165648Z-unified-0b728bad/build-inputs.json)、[安装态验收](docker/records/20261103T165648Z-unified-0b728bad/installation/acceptance.json)、[微型兼容性与符号核对](docker/records/20261103T165648Z-unified-0b728bad/compatibility/unified-smoke.json)、[原候选完整关联快照](docker/records/20261103T165648Z-unified-0b728bad/previous-candidate.json)。`current-image.json` 分别关联功能试跑、perf 与 Topdown 的实际记录。最新结果见[扩展任务操作对照](../analysis/docops/processed/task-operation-expansion-20261104/comparison.json)。
- 首个 unified candidate-01 的微型重算因上述 profile 不匹配超时；其镜像与失败记录保留，不作为当前候选。

最终安装门槛覆盖冻结命令实际使用的全部工具，包括 `rg`、`unzip`、`fc-match`、`pdfinfo`、`pdftotext` 和 `libreoffice`，避免原脚本的 `|| true` 将缺命令掩盖成成功。

**正式单轮结果：** Word 001/003/009、Excel 013/014/016、PPT 021/026/029、PDF 031/037/pdfwf005，全部 1/1/1/0；217 个归档索引项的大小与 SHA256 复核通过。每项独立无网络容器，停止容器保留。[功能报告](../results/docops/unified-functional-20261103T165818Z-4808c908/summary.md)、[十二项底表](../results/docops/unified-functional-20261103T165818Z-4808c908/twelve-task-status.json)。

首轮 candidate-03 在 021 字体准备失败：冻结脚本引用原 Debian 的 LiberationSans 字体路径。已从原镜像恢复相同的 Regular/Bold 字体，绑定 SHA256 并纳入执行前预检；candidate-04 完整重跑十二项通过。只适配环境，不改任务脚本，原失败记录及镜像保留。该功能试跑阶段未重评外部官方内容分数，也未采集 perf/DevKit；随后独立测量的记录见当前状态。

后续构建使用已经冻结的离线材料，指定未使用过的标签：

```bash
python3 -B docops/docker/build_unified.py --image <新候选标签>
python3 -B docops/docker/check_image.py --image <新候选标签> --build-record-dir <本次构建记录目录>
```

现有原始 perf 必须使用其原始镜像/匹配 build-id 符号解析。切换环境后产生的是新测量；采集入口不再为统一环境挂载旧 Debian 符号树。原首批 `campaign.py` 包含旧 031 复用约束，属于历史批次入口，不能直接拿来启动新环境全批次。

## 任务与保留链

|任务|格式|最终脚本版本与执行链|
|---|---|---|
|001|Word|`create_packet.py` v2 → LibreOffice/Poppler 最终渲染 → 原有内联结构、ZIP/XML 与渲染文本检查|
|003|Word|`build_public_packet.py` v4 → `audit_public_packet.py` v2 → Skill `render_docx.py`|
|009|Word|`build_incident_manual_publication.py` → Skill 渲染 → `validate_incident_manual_publication.py`|
|013|Excel|`build_public_bid_workbook.py` v3 → Skill `recalc.py` → `verify_public_bid_workbook.py` → PDF/图片与拼图|
|014|Excel|`build_disaster_release_v1.py` → Skill 重算 → `finalize_disaster_release_ooxml_v3.py` → 最终 validator v2 → PDF/图片|
|016|Excel|`build_forecast_dashboard_v1.py` v4 → Skill 重算 → PDF/首张图片 → 独立测试副本切换 Base 情景并重算核验|
|021|PPT|环境准备：Agent 的字体替代脚本与字体缓存；正式链：`build_public_shelter_briefing.py` v6 → validator → PDF/图片/拼图|
|026|PPT|`build_climate_disclosure.py` v2 → Skill 转 PDF（保留 `/root/tmp/docs` cwd）→ 图片 → `qa_climate_disclosure.py`|
|029|PPT|`build_release_deck.py` v6 → `validate_release_deck.py` → Skill 转 PDF → 最终首张图片|
|031|PDF|任务私有 `build_public_packet.py` → 图片 → `validate_public_packet.py`|
|037|PDF|`build_bus_detour_packet.py` v2 → 最终图片 → `validate_bus_detour_packet.py`|
|pdfwf005|PDF|`rebuild_closeout_binder.py` v2 → pdfinfo/文本/标签/书签诊断 → 图片/拼图 → 禁词诊断|

全部业务脚本逐字节取自已保存版本，没有改写。十四号的最终 OOXML 修补脚本已包含前两版的完整修复，前两次修补可省略；这个精简已在功能回放及本次十轮批次中执行通过。
二十一号的源码审查输出 `source_audit.json` 没有被最终构建脚本读取，因此属于探索，不是最终依赖。
一号、九号、二十一号、三十一号等脚本可能使用轨迹中已确定并写入脚本的内容创建新文档；不人为补上额外输入扫描以统一流程。

每任务独立保存输入、脚本和命令，即使脚本同名也不共用。公共部分只负责调度、环境和测量。
现有官方评分保留：四项通过、八项未通过；Agent 自写检查退出 0 不等同于官方内容通过。
历史打印型检查和 `|| true` 诊断照原样保留，不伪称严格断言。

## 静态编译与检查

```bash
cd /home/lcq/office-trace-replay
python3 -B docops/compile.py validate --payload docops/payload
python3 -B -m unittest discover -s docops/tests -p test_compile.py

# 仅重新导入时需要指定来源仓库。必须使用尚不存在的输出目录。
# 不会启动 workload、容器或采集器。
python3 -B docops/compile.py compile \
  --source-root /home/lcq/agent_workload_characterization \
  --output /tmp/docops-import-review
```

编译器只读取已选主样本、SQLite 事件、脚本版本及原注入文件；使用 `bash -n` 检查语法，**不执行归档命令**。
输出目录已存在则拒绝；先生成到临时 staging，全部校验后发布。失败只清理本次 staging。
输出包含十二份 `recipe.json`、逐任务 seed、原始 shell body、官方四类 Skill、catalog 和完整字节/SHA256 索引。
每个选择步骤记录原事件 ID、命令、cwd、脚本版本、前序依赖；未选事件有排除记录。
`static_valid` 只表示上述检查通过；`replay_validated` 仍为 false。

## 目录与归属

|位置|用途|
|---|---|
|`docops/config/selection.json`|十二项任务的最终有效依赖选择及排除理由|
|`docops/compile.py`、`docops/tests/`|来源导入、冻结材料检查与定向测试|
|`docops/payload/tasks/<id>/`|每个任务独立的 recipe、原始输入、冻结脚本和命令|
|`docops/payload/skills/`|从来源仓库冻结的四类官方 Skill|
|`docops/payload/provenance/`|导入时的主样本、脚本版本和选择快照|
|`docops/provenance/`|最初准备记录与本次迁移核验；历史记录中的原路径保持不变|
|`analysis/docops/`|本仓库内的 perf/DevKit 测量、统计与结果入口|
|`results/docops/`|未来本地功能回放和容器证据，不提交 Git|

本次将原先放在来源仓库中的临时回放准备代码和约 3.4 MB 冻结材料迁入这里，没有复制大型原始轨迹。
已有七例的执行器、镜像配置、性能数据和正式报告保持原状；DocOps 的环境和测量结果独立关联，不能套用原七例的镜像身份或性能结论。

## 测量边界与历史 Debian 接入

以下环境版本与首批状态描述原 Debian 接入阶段；当前统一环境版本及测量状态以本文开头为准。

历史基础环境为原 DocOps 的 `docops-l3-shared-tools:arm64-v3`，ID 见 `selection.json`。
该历史镜像 Python 为 3.12.14；当前统一镜像使用上文列出的 Python 3.12.3 与 LibreOffice 25.8.7.3。
安装依赖放在镜像构建阶段；回放网络关闭，不包含 Agent 凭据和模型请求。

已准备的离线依赖及待验证边界：

1. `fontTools 4.68.0` 已冻结到 vendor；来源是原容器当前安装材料，不声称历史逐次安装身份已直接核验。
2. Debian/arm64 `perf 6.1.190` 与所需 deb 已冻结；十二项已验证物理调用栈与计数；匹配 build-id 补符号后，八项达到试点符号门槛，016/021/026/029 仍标为符号有限。
3. DevKit CLI 26.0.RC1 使用独立启动包装器设置私有库路径，不把私有 LD_LIBRARY_PATH 注入文档业务进程；十二项 CPU 0–7 首批采集通过，主控制器位于 CPU 9；完整包络并非精确步骤 ROI。

一个镜像支持十二任务、一个公共入口；顺序执行时必须隔离任务工作区、字体状态及 LibreOffice 后台进程，不能让同名脚本或中间产物串入下一项。
正式 ROI 只覆盖所选 workflow 命令；依赖安装、字体环境准备、reset/种子恢复、归档哈希及官方评分在 ROI 外。
perf 采用任务进程及其后代采集，在同一镜像内导出物理调用栈；DevKit 另一次运行按固定 CPU 集合采集，控制器放到集合之外，保留启动/结束包络说明。
不同时启动两路 profiler，不把按核 DevKit 结果说成严格按进程结果。
短任务后续可使用多轮实际工作批次延长测量窗，不能用 sleep 补采样点。

十二项均已完成一轮功能验证，且每项两路首批测量已完成；后续独立重复另行安排。

## 公共回放入口 `docops/replay.py`

入口只负责调度、环境隔离、状态落盘、ROI 计时与归档；不合并业务逻辑，不执行冻结脚本之外的任何命令。

```bash
# 列出十二任务与格式
python3 -B docops/replay.py list --payload docops/payload
# 宿主只检查冻结材料和计划；--env-check 应在修复版镜像内执行。
python3 -B docops/replay.py validate-only --payload docops/payload
```

- 每任务使用各自冻结脚本/recipe/seed；同名脚本（如 003 与 031 的 `build_public_packet.py`）按任务独立放置，互不混用。
- 冻结校验在任何正式命令执行前完成；缺材料、哈希不符、命令体不一致即拒绝，不允许现场安装、在线下载或回退脚本版本。
- ROI 内＝`phase=workflow` 的步骤（最终构建、修补、重算、渲染、原有检查），用单调时钟逐步骤记录；ROI 外＝材料校验、工作区复位、种子放置、字体环境准备（021，environment_setup）、LibreOffice profile 复位、归档复制、哈希及外部官方评分。
- 026 的 `convert_pdf` 保留原 `cwd=/root/tmp/docs`（无 `--outdir`），由 recipe 的 cwd 字段驱动。
- 每轮状态即时落盘（`results/<task>/round-<seq>/run.json`），summary 累积 requested/completed/successes/failures，失败轮不被后续成功掩盖；round 目录全局递增避免覆盖。
- 按共享绝对工作空间固定 `flock` 路径，不同 --workdir 也不能绕过；宿主 run 被拒绝。
- reset 只删除明确的 seed 文件和临时工作目录，不递归删除 `/root`。拒绝软链接及结果/材料路径重叠。字体、字体缓存、LO profile 在 finally 中恢复原快照，包括被覆盖的已有字体。
- 准备、工作流或归档失败时返回非零并停止后续轮次/任务。超时终止本步骤创建的进程组，不全局按名称杀 soffice。
- Agent 自写 verifier 返回 0 不等于官方内容验收通过；历史四项通过、八项未通过的原判定保留，回放执行/采集资格与内容判定分开。

## 定向验证与安装态检查

- 当前定向检查包含静态编译、执行器以及安装/构建拒绝门槛，全部使用合成/微型 fixture，不执行真实 workload。命令：`python3 -B -m unittest discover -s docops/tests -v`。
- 覆盖：材料缺失与哈希篡改在正式命令前拒绝、命令与 cwd 正确传递、同名脚本任务隔离、顺序两任务无输出/字体串扰、loops/步骤失败/超时/归档失败正确落盘、工作区 reset 不影响结果、ROI 排除准备与归档、并发互斥拒绝、不访问来源仓库可校验、`--help/--list/--validate-only` 不触发 workload。
- candidate-04 的旧安装探测仅证明当时记录的库/工具存在；旧检查没有完整失败门槛，不作为修复版验收。当前安装检查会核对版本、实际 Skill 字节与依赖解析，任一失败返回非零；不启动 perf record。实际镜像 ID 由宿主 inspect 另行绑定，容器内不硬编码标签。
- 尚未验证：独立重复运行稳定性及本次产物的外部官方评分。十二项首批对比已完成，保持初步描述性口径。
- 修复版 candidate-05 在无网络、无宿主源码/来源仓库挂载的容器中安装检查通过；只挂载结果目录。实际容器退出码 0，镜像内源码与构建输入哈希一致；临时目录 fixture 验证真实 recipe 的 reset 不删 Skill、不同 workdir 互斥、覆盖字体后准确恢复。检查记录见下方链接，不包含真实任务执行或 PMU 采样。

## 历史候选镜像（Debian）

- 基础：`docops-l3-shared-tools:arm64-v3` = `sha256:b0d0e6038597b41c08f7fbba8d3e5cb2ff515e0e2602c31528c9e3fe80a90106`（arm64）。
- 旧候选（待修复版替代）：`docops-replay:l3-candidate-04` = `sha256:3c17f77047d3bb6ccd31cd74261a78f71429c6a6508c4d07d91d6d62d8f1f5d2`。本次未覆盖或重建它。
- 原 Debian 候选：`docops-replay:l3-candidate-05` = `sha256:bda6808f5b05feff831fb1700a24ee90f42c5b332f5411c80a752cf960baf617`，linux/arm64。基础镜像仍为上面的 b0d0e603…。
- [构建与输入哈希](docker/records/20261103T130313Z-docops-ctx-7TjPBL/build-inputs.json)、[完整构建日志](docker/records/20261103T130313Z-docops-ctx-7TjPBL/build.log)、[实际容器安装态验收](docker/records/20261103T130313Z-docops-ctx-7TjPBL/installation/acceptance.json)。停止容器已保留。
- 构建：`bash docops/docker/build.sh <新候选标签>`（离线；不覆盖既有镜像/基础镜像；记录见 `docops/docker/records/`）。
- 构建前强制核对基础镜像 ID/架构、payload、全部 vendor 字节与 SHA256、DevKit 核心及私有库。缺任一依赖即拒绝；使用已核对的本地基础标签，构建后再次核对 ID，每次使用独立记录目录，保留完整日志及 image inspect。
- 镜像内含冻结 12 任务 payload（`/opt/docops/payload`）、公共入口（`/opt/docops/replay.py`）、Debian/arm64 perf 及依赖、fontTools 4.68.0 冻结包、DevKit Tuner CLI（`/opt/devkit`）。运行时不需要挂载宿主源码或来源仓库。
- 依赖来源：`docops/vendor/debs-sha256.json`（linux-perf 6.1.190-1 及运行时库，Debian bookworm，固定版本+SHA256）、`docops/vendor/fonttools-sha256.json`（4.68.0，来自 docops-formal-01 当前 site-packages 的只读副本，当前环境证据，非历史逐次安装身份）。

## 原 Debian 环境的运行记录

原修复版镜像构建、安装检查及十二项各一轮试跑已完成。031 已完成 perf/DevKit 采集、ROI 过滤及栈解析试点；[验证记录](../analysis/docops/processed/031-collector-validation-20261103/report.md)保留了符号与包络边界，后续再安排十二项正式测量。

### 十二项功能汇总

|格式|任务|结果|
|---|---|---|
|Word|001、003、009|各 1/1/1/0|
|Excel|013、014、016|各 1/1/1/0|
|PPT|021、026、029|各 1/1/1/0|
|PDF|031、037、pdfwf005|各 1/1/1/0|

031 复用前次单轮证据，其余十一项本轮各跑一次，无失败、无重试；每项使用独立无网络容器，只挂载其结果目录，停止容器保留。
本轮 202 个归档文件的大小和 SHA256 回读通过，原始输入未被改写，所执行业务脚本与冻结版本一致。
[十二项汇总](../results/docops/functional-remaining-11-20261103T141917Z-216451d1/twelve-task-status.json)、[本轮运行清单](../results/docops/functional-remaining-11-20261103T141917Z-216451d1/campaign.json)。
输出字节与历史是否相同逐项记录，未要求 OOXML 容器文件逐字节相同；本次结论是执行和原 Agent 自写检查通过，不替代官方内容评分。历史四项通过、八项未通过的判定不变。
payload 内的编译状态保留导入快照，实际回放资格以当前镜像绑定的运行记录为准，不通过修改冻结材料来更新状态。

### PDF 031 单轮结果

candidate-05、无网络、仅挂载独立结果目录；请求/完成/成功/失败为 **1/1/1/0**，构建、五页图片渲染与原 Agent 自写检查均退出 0。
ROI 工作流约 **1.52 秒**，产物为五页 PDF 与五张 PNG，14 个归档文件大小和 SHA256 回读通过；输出 PDF 与原轨迹归档逐字节相同。
[运行记录](../results/docops/functional-031-20261103T131236Z-e5cd6192/trial-record.json)保存实际镜像、容器和命令，停止容器保留。
这次只验证回放执行；未重跑外部官方评分，原任务 reward=0 的历史判定不变，未启动任何 profiler。

安装检查入口为 `docops/docker/check_image.py`，参数为 `--image` 与 `--build-record-dir`。
每次新构建完成后，用构建输出的记录目录进行首次检查；已有 `installation/` 的目录拒绝覆盖。

撤回旧版直接包住 replay.py 的 perf 示例：它采到整个入口，且缺少固定采样频率及 DWARF 参数，不能作为正式统计命令。
后续采集须明确设置 `-e cycles:u -F 49 --clockid mono --call-graph dwarf,16384`，同镜像导出，并按 run.json 的 `roi_intervals` 及 workload 进程身份过滤。
时间记录本身不会自动过滤 perf；`analysis/docops/pilot.py` 已在 031 上验证：perf 按 workflow 时间区间并集过滤并排除调度器，DevKit 则保留按核采集的完整包络。全部任务和重复运行稳定性仍待正式测量。
两路 profiler 分别运行同一冻结配方，不同时采集；按核 DevKit 结果不作严格按进程描述。

## 十二任务首批测量（历史 Debian）

[首批报告](../analysis/docops/processed/first-comparison-batch-20261103/report.md)包含十二项的进程／脚本、库、已解析函数、九项 Topdown 与 idle，以及同格式 12 对和跨格式 54 对的配对数据。每路仅一次独立采集，批内十轮不视作十次独立重复。031 复用已通过的验证资料，其余 22 次新采集全部成功。补符号与 C++ 解析修复均在原数据上离线完成，没有重跑业务。

## 当前统一环境测量与发表入口

- [代表性评估报告：扩展任务操作](../docs/representativeness-assessment.md#七扩展任务操作与原始-pdfxlsx-基准比较)、[实验数据汇总](../docs/experimental-results.md)：24 组原始 OPM／TLC 对照及 533 个真实过程点。
- [十二任务离线补符号结果](../analysis/docops/processed/unified-symbol-enrichment-20261104-v1/report.md)：未解析 period 为 0.0018%–3.02%，原采集数据不变。
- [十二任务 Topdown](../analysis/docops/processed/unified-topdown-20261104-v1/report.md)：每项一次独立采集，内部十轮，不能当作十次独立重复。
- `vendor/` 是镜像离线构建所需的冻结输入，随代码保留。`analysis/docops/raw/` 及补符号下载、解压缓存仅在本机保留，不提交 Git；来源 URL、版本、build-id 与 SHA256 记录保留在仓库。离线复算原始采样需具备这些本地证据文件；已有文档与 HTML 可从已提交的汇总结果重建。
