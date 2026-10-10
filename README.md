# office-trace-replay

默认 suite 保留 **document-oe 的两个旧执行用例原样不变**，增加 Retail / Manufacturing / HR / IRS W-4 / SBA 1919 五个新输入。新增用例通过版本化适配配方使用原执行器、原工具、原计时入口和相同运行环境，用于后续验证旧用例分析在其他输入上的适用性。旧用例的配方、调用顺序、helper、Skill、verifier、CSV 导出、计时入口及默认参数均从实际容器逐字节复制。

`opm` 是旧 `pdf` 的别名；`tlc` 是旧 `xlsx` 的别名。此前 15a290f 中重新生成的 OPM/TLC 配方使用了不同脚本，不能承接旧实验；现在只可通过 `opm_v2` / `tlc_v2` 显式选择，不进入默认 suite。历史验收报告保留在 `reports/history/derived-v1/`。

## 旧用例：原命令、原路径、原脚本

容器内 `/opt/document-bench` 保留原目录布局。原执行器 `run_document_scene_loop.py`、原计时入口 `run_document_scene_loop_timed.py`、两个 scene 启动脚本均未修改。

```bash
mkdir -p results
# 直接执行原程序；只换镜像名，不经过新工具执行器。
docker run --rm --network none --entrypoint /usr/bin/python3 \
  -v "$PWD/results:/results" office-trace-replay:openeuler-v3 \
  /opt/document-bench/bin/run_document_scene_loop.py \
  --scene pdf --loops 1 --results-dir /results

# 原计时入口也完全保留。
docker run --rm --network none --entrypoint /usr/bin/python3 \
  -v "$PWD/results:/results" office-trace-replay:openeuler-v3 \
  /opt/document-bench/bin/run_document_scene_loop_timed.py \
  --scene xlsx --loops 1 --results-dir /results
```

原容器默认 `python3` 为系统 3.11.6，镜像保留其 PATH 和库。若之前实验使用 `/opt/document-bench/.venv` 的 Python 3.12.3，则继续使用相同绝对解释器，并把该 venv 放在 PATH 前面，让原脚本内部的 `python3` 也保持相同版本。两种解释器都没有被替换。

便捷入口同样直接委托原程序：

```bash
make replay DATASET=pdf
make replay DATASET=xlsx
docker run --rm --network none -v "$PWD/results:/results" \
  office-trace-replay:openeuler-v3 --scene pdf --loops 1 --pdf-applicant-count 10 --results-dir /results
docker run --rm --network none -v "$PWD/results:/results" \
  office-trace-replay:openeuler-v3 --scene xlsx --loops 1 --timed --results-dir /results
# 显式选择原有 venv 模式：--legacy-python venv
```

原生 `--scene` 接口保持默认 loops=20000、PDF applicant count=1（原样支持 10）、XLSX recalc timeout=600、operation timeout=900。上面显式写 `--loops 1` 仅用于一次验证。旧循环内仍按原配方写 helper；不会提前恢复脚本、合并调用、改 shell、清理 Office profile、换 verifier、注入新 soffice 包装器或添加独立验收到旧执行链。

## 新输入与兼容旧流程的回放

五个新增输入默认使用 `compatibility/recipes/` 的配方，绑定父 canonical trace、输入、helper、兼容 contract 和 Prompt 哈希。helper 在原 build 阶段写入并执行；使用原 PDF 工具和原 XLSX `recalc.py`。HR 只构建一次，三个 XLSX 都将保护源数据所需的缓存装配明确保留为额外操作。输入表格保留自己的结构。

这是从已有 Agent trace 适配的 replay recipe，没有再次调用 LLM，也不是新的 Agent trajectory。业务 helper/verifier、原始输入复杂度和必要的源内容保护仍不同，不能仅凭成功回放声称代表性已获证明。详细边界和剩余差异见 [compatible-workflow.md](docs/compatible-workflow.md) 与 `reports/workflow-alignment.json`。

```bash
make replay DATASET=retail
# 默认七用例：先原 PDF/XLSX，再五个新增用例。
docker run --rm --network none -v "$PWD/results:/results" \
  office-trace-replay:openeuler-v3 --loops 1
# 新旧两侧使用原计时方式，PDF 默认都执行一条 fill/render。
docker run --rm --network none -v "$PWD/results:/results" \
  office-trace-replay:openeuler-v3 --loops 1 --timed
# 明确选择十条记录比较，原有十条 records 保留，单条 variant 独立冻结。
docker run --rm --network none -v "$PWD/results:/results" \
  office-trace-replay:openeuler-v3 --dataset pdf --dataset irs_w4 \
  --dataset sba1919 --pdf-applicant-count 10 --loops 1 --timed
```

默认 suite 在 `suites/default.json`。父 trace/source/配方仍冻结在 `assets/`、`recipes/`。新增适配输入和配方在 `compatibility/`；原衍生执行可以显式用 `--workflow derived-v1` 选择。旧执行副本在 `legacy/document-oe/`，其 `lock.json` 记录从真实旧容器导出的 45 个活动文件的 hash、模式和大小。运行不依赖 sibling repository，不调用 LLM。

## 构建与检查

```bash
make test
make validate
make image
```

离线基于本地固定 `document-oe-snapshot:20260827` 构建；保留原 Python、系统库、LibreOffice 和 Poppler。兼容模式的旧、新用例默认均使用系统 Python 3.11.6，可同时选择原 venv 3.12.3。两侧使用原 recalc.py 的 profile 逻辑，均不启用新 soffice 包装器。历史 `derived-v1` 模式仍使用其原 venv/profile 包装器。

完整原始资产冻结、输入/配方关联和环境版本见 `legacy/document-oe/lock.json`、`assets/project-lock.json`、`runtime/environment-lock.json`。构建及当前恢复验收见 `reports/`；旧 v1 的成功报告只能证明其衍生配方通过，不能证明旧 document-oe 执行相同。项目仍未开展 CPU/OS 性能实验。

旧 v2 的验收记录冻结在 `reports/history/native-v2/`；该版本只保留了旧执行，新增用例仍采用历史衍生流程。当前兼容版本的状态以 `reports/status.json`、`reports/qualification.json` 为准。

2026-10-10 已完成兼容版本功能验收：五个新增输入均通过；W-4/SBA 的单条和十条 variant 均通过，实际 fill/render 次数与配置一致。原两用例回归成功，最终镜像中的 45 个原文件字节/权限一致；新配方修正后复用原 XLSX 回归记录，未重复长时间运行。独立 checkout 测试为 **16 passed / 0 skipped / 0 failed / 0 errors**。

当前镜像 `office-trace-replay:openeuler-v3`，image ID `sha256:890c53efc41f5388f76a5662e4bb4751ede1cac68c26844dca4716260a93d1f4`。验收采用系统 Python 3.11.6 和原 timed wrapper；plain/venv 模式可选，但不声称本次逐一实跑了所有组合。
