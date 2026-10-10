# office-trace-replay

默认 suite 保留 **document-oe 的两个旧执行用例原样不变**，增加 Retail / Manufacturing / HR / IRS W-4 / SBA 1919 五个新用例。旧用例的配方、调用顺序、helper、Skill、verifier、CSV 导出、计时入口及默认参数均从实际容器逐字节复制。

`opm` 是旧 `pdf` 的别名；`tlc` 是旧 `xlsx` 的别名。此前 15a290f 中重新生成的 OPM/TLC 配方使用了不同脚本，不能承接旧实验；现在只可通过 `opm_v2` / `tlc_v2` 显式选择，不进入默认 suite。历史验收报告保留在 `reports/history/derived-v1/`。

## 旧用例：原命令、原路径、原脚本

容器内 `/opt/document-bench` 保留原目录布局。原执行器 `run_document_scene_loop.py`、原计时入口 `run_document_scene_loop_timed.py`、两个 scene 启动脚本均未修改。

```bash
mkdir -p results
# 直接执行原程序；只换镜像名，不经过新工具执行器。
docker run --rm --network none --entrypoint /usr/bin/python3 \
  -v "$PWD/results:/results" office-trace-replay:openeuler-v2 \
  /opt/document-bench/bin/run_document_scene_loop.py \
  --scene pdf --loops 1 --results-dir /results

# 原计时入口也完全保留。
docker run --rm --network none --entrypoint /usr/bin/python3 \
  -v "$PWD/results:/results" office-trace-replay:openeuler-v2 \
  /opt/document-bench/bin/run_document_scene_loop_timed.py \
  --scene xlsx --loops 1 --results-dir /results
```

原容器默认 `python3` 为系统 3.11.6，镜像保留其 PATH 和库。若之前实验使用 `/opt/document-bench/.venv` 的 Python 3.12.3，则继续使用相同绝对解释器，并把该 venv 放在 PATH 前面，让原脚本内部的 `python3` 也保持相同版本。两种解释器都没有被替换。

便捷入口同样直接委托原程序：

```bash
make replay DATASET=pdf
make replay DATASET=xlsx
docker run --rm --network none -v "$PWD/results:/results" \
  office-trace-replay:openeuler-v2 --scene pdf --loops 1 --pdf-applicant-count 10 --results-dir /results
docker run --rm --network none -v "$PWD/results:/results" \
  office-trace-replay:openeuler-v2 --scene xlsx --loops 1 --timed --results-dir /results
# 显式选择原有 venv 模式：--legacy-python venv
```

原生 `--scene` 接口保持默认 loops=20000、PDF applicant count=1（原样支持 10）、XLSX recalc timeout=600、operation timeout=900。上面显式写 `--loops 1` 仅用于一次验证。旧循环内仍按原配方写 helper；不会提前恢复脚本、合并调用、改 shell、清理 Office profile、换 verifier、注入新 soffice 包装器或添加独立验收到旧执行链。

## 新用例与 trace 整理

五个新增用例使用冻结的 canonical trace，固定输入、最终 helper 版本和有效执行决策：检查并选取依赖链，去掉调试/失败/轮询，将代码在准备阶段恢复，再执行构建、重算/填表/渲染和验收。这种整理方式只适用于新用例，不用于改写两个旧配方。

```bash
make replay DATASET=retail
# 默认七用例：先原 PDF/XLSX，再五个新增用例。
docker run --rm --network none -v "$PWD/results:/results" \
  office-trace-replay:openeuler-v2 --loops 1
```

默认 suite 在 `suites/default.json`。新用例源码/输入/Skill/轨迹在 `assets/`，配方在 `recipes/`。旧执行副本在 `legacy/document-oe/`，其 `lock.json` 记录从真实旧容器导出的 45 个活动文件的 hash、模式和大小。运行不依赖 sibling repository，不调用 LLM。

## 构建与检查

```bash
make test
make validate
make image
```

离线基于本地固定 `document-oe-snapshot:20260827` 构建；保留原 Python、系统库、LibreOffice 和 Poppler。新用例使用原 venv 的 Python 3.12.3，且只在新执行器子进程中启用新 soffice profile 包装器。旧执行入口使用原 recalc.py 自己的 profile 逻辑。

完整原始资产冻结、输入/配方关联和环境版本见 `legacy/document-oe/lock.json`、`assets/project-lock.json`、`runtime/environment-lock.json`。构建及当前恢复验收见 `reports/`；旧 v1 的成功报告只能证明其衍生配方通过，不能证明旧 document-oe 执行相同。项目仍未开展 CPU/OS 性能实验。

2026-10-10 已验收 `office-trace-replay:openeuler-v2`（image ID `sha256:9ed449fe6613c20d390ea203376583ea723e7154b2db7d38f3e334bcc1b96ba7`）：安装后的 45 个原文件与旧容器内容、权限一致，默认七用例各执行一次均成功，原 PDF 10 条记录计时入口也成功。独立 checkout 测试为 **11 passed / 0 skipped / 0 failed / 0 errors**，机器可核对的汇总见 `reports/qualification.json`。
