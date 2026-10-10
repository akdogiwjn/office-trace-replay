# 以旧执行为基线验证其他输入

此版本固定原 document-oe PDF/XLSX，新增输入使用 `document-oe-compatible-workflow-v1`。目标是检查旧用例中的瓶颈、热点或系统配置趋势是否在其他真实输入上重现。功能验收本身不证明代表性；尚未开展 CPU/OS 性能实验。

## 执行和计时边界

`entry.py` 对旧用例仍委托原程序。对五个新增用例启动 `compatible.py`，默认与旧用例一样使用原 venv Python 3.12.3、带该 venv 前缀的 PATH、原 PDF/XLSX Skill 工具、原 LibreOffice 重算实现。容器默认 `python3` 及脚本内部子进程也使用 3.12.3。`--legacy-python system` 会同时为旧、新用例显式选择历史系统 Python 3.11.6 环境。比较两侧必须使用同一模式。

兼容 launcher 导入安装在 `/opt/document-bench/bin` 的原执行器，只在新子进程内配置 `SCENES[kind]` 的 seed、workspace、recipe 路径，再调用原 `main()`。没有修改原文件或替换 `execute_call`、Shell、超时、workspace reset 和业务状态检查。新用例的配方和业务 helper 是显式适配版本。

`--timed` 对两侧均使用原 `run_document_scene_loop_timed.py` 和原 `timing_hooks/sitecustomize.py`。plain 与 timed 的结果应分别比较。新增用例没有额外的逐调用 stdout/stderr 文件重定向。

原 iteration 总时间包含 workspace reset、四阶段、最终业务状态读取；扣除 reset_seconds 是原有净时间定义。哈希检查、环境记录、额外独立验收、输出/脚本归档在原 iteration 外执行，单独记录。配方内 semantic verifier 仍在 verify_deliver 中，业务验收代码不同，应单独分析该阶段。原工具超时均保留，XLSX recalc=600 秒、operation=900 秒。

## 流程与剩余差异

| 类型 | 共同流程 | 明确保留的数据差异 |
|---|---|---|
| PDF | 检查/提取/模板渲染 → 写并执行 mapping helper → 单个 Python driver 按记录交替 fill/render → 从输出生成 summary → semantic verifier | 表单页数、字段、映射内容、记录规模；SBA 保留 mapping dry run |
| XLSX | 原式结构/特征检查 → 写并执行一次 openpyxl 构建 → 一次原 recalc → 公式/缓存检查及 CSV 导出 → semantic verifier/summary | 原始 workbook 复杂度、业务公式/图表、必要的缓存装配和源内容恢复 |

HR 不再重建第二次。三个新 XLSX 都保留 clean build，在副本上重算，再通过冻结的原 Agent assembly helper 保留源数据和新公式缓存。此额外处理标为 `source_preservation`，不会声称原 TLC 也执行了同样步骤。公式/缓存装配阶段可从配方角色和原 per-call/nested log 单独识别。

新 XLSX 导出真实 metric 与 scenario projection CSV。没有生成 TLC 的 Reconciliation Sheet，也没有将原始 spreadsheet 重写成统一模板。不同业务的 CSV 行数仍不同。

PDF 冻结两套明确输入：n10 沿用原 synthetic records；n1 从原文件取第一条，不重新生成个人数据。subset 具有独立 records/manifest/expected/records-contract hash，原十条输入不变。旧 PDF 默认执行一条 fill/render，但它的原 mapping helper 仍生成十份 field-values；新 n1 生成一份。这是 build 阶段剩余差异，需要纳入解释。单条模式对齐的是 fill/render 数量，不能宣称全部准备工作等量。

各 input 的大小、Sheet/页数、cell、formula、chart/style、字段数量均是 workload 特征。不要把总 CPU 差异直接归因于行业。推荐先按阶段、调用角色和复杂度解释，再检查旧结论是否重现。

## Trace、配方及 Prompt 身份

`assets/canonical`、`assets/cases`、`recipes/*.json` 和 `legacy/document-oe` 是冻结历史，不覆盖。新增 `compatibility/recipes` 绑定父 canonical/run/trajectory、父 recipe hash、实际 input hash、兼容 contract/Prompt hash 和显式 adaptations。所有运行代码及 helper 内容受 project-lock 约束。

这些是从真实 Agent trace 的最终 helper 适配出的 replay recipes，**不是重新运行 Agent 得到的新 trajectory**。未再次调用 LLM，模型/Prompt provenance 是父 trace 的证据；新 workflow Prompt 是后续生成相同流程任务的冻结定义，不能声称父 trace 使用了它。若未来需要研究 Agent 决策本身，应依据该 Prompt 重新生成并冻结新的 Agent trace。

helper 在 native build 阶段通过配方 write 写入，而非在未计入执行的准备阶段提前恢复。输入 seed 只包含输入。执行后的脚本、中间工作簿、配置和最终输出会归档到 `workspace_artifacts/` 并记录 hash，方便后续追溯。

## 使用

```bash
# 默认七用例，单条 PDF，plain。
docker run --rm --network none -v "$PWD/results:/results" \
  office-trace-replay:openeuler-v4 --loops 1

# 两侧均使用原计时方式。
docker run --rm --network none -v "$PWD/results:/results" \
  office-trace-replay:openeuler-v4 --loops 1 --timed

# 原 PDF 和新增 PDF 同为十条 fill/render。
docker run --rm --network none -v "$PWD/results:/results" \
  office-trace-replay:openeuler-v4 --dataset pdf --dataset irs_w4 \
  --dataset sba1919 --pdf-applicant-count 10 --loops 1 --timed

# 保留历史衍生配方的明确入口。
docker run --rm --network none -v "$PWD/results:/results" \
  office-trace-replay:openeuler-v4 --dataset retail --workflow derived-v1 --loops 1
```

兼容运行记录位于 `/results/compatible-<run-id>/<variant>/0001/`：原 `pdf|xlsx/<native-run-id>/summary.json`、`iterations.jsonl`；timed 模式另有原 calls/nested_calls。外层保存 `environment.json`、独立验收、output 和 workspace_artifacts。外层 summary 绑定所有输入、配方、父 trace 和归档文件，方便明确选择性能实验的具体 recipe/variant。
