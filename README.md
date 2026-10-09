# office-trace-replay

从 `office-trace-bench` 冻结的七条成功 Agent trace 整理有效工具执行链，再在本地 openEuler 镜像中回放。沿用 `document-oe` 的四阶段配方和执行器：检查与准备、构建、处理与发布、验证与交付。每个数据集保留自己的实际脚本、输入结构和调用数量。

当前范围：XLSX TLC / Retail / Manufacturing / HR；PDF OPM / IRS W-4 / SBA 1919。运行不调用 LLM，不重新生成 helper，不重新做自然语言决策。完整 Agent 轨迹回放不属于第一版。项目用于工具 workload 回放资格验证；当前没有开展 CPU/OS 性能实验。

## Trace 如何整理

1. 通过原仓库 `artifacts/suite.json` 选择准确的 canonical run，验证输入、Prompt、manifest、Skill、源码、轨迹和验收的 hash 关联。
2. 导入完整 canonical pack 和对象闭包，保存每条 trace 对应的冻结源码。后续运行不再依赖旧仓库。
3. 检查最终结果需要的命令、脚本版本、中间文件和工作目录。排除探测、失败尝试、临时调试及重复轮询，保留生成合格输出的依赖链。
4. 冻结有效 helper 版本，准备阶段恢复代码；`edit` 不再执行。执行命令并等待结束，替代 `process.poll`。仍保留工具的真实构建、Office 重算、填表、渲染、缓存注入和验收。
5. 编译为 `read/write/exec` 四阶段配方。每次运行清理工作目录和指定临时文件，重新生成输出，再用原 trace 的冻结 verifier 做完整独立验收。

具体选择在 [selections.py](replay/selections.py)，逐条来源/排除调用、适配说明和 helper hash 在 `recipes/<dataset>.json`。这是一条经过审核的有效执行链，不等同于原 Agent 的完整工具调用过程。TLC 配方组合了最终修复的 cache injector，明确记录与原 pipeline 首次调用时脚本版本的区别。

Agent 直接写出的 batch summary、feature index 和 enhancement summary 作为冻结执行决策保留，按配方重新写出。不会把旧输出工作簿、已填写 PDF、PNG、公式缓存或成功验收报告放进工作区。它们只有在工具重新执行后才能生成。

## 使用

已导入的数据在 `assets/`；单项和全部执行都不要求存在 `../office-trace-bench`。一次性导入命令需要显式指定来源，不能静默替换已有 suite：

```bash
python3 scripts/import_suite.py --source /path/to/office-trace-bench
python3 scripts/compile_recipes.py
python3 scripts/freeze_project.py
make test
make validate
make image
make replay DATASET=retail
```

全部执行或重复执行：

```bash
mkdir -p results
docker run --rm --network none -v "$PWD/results:/results" \
  office-trace-replay:openeuler-v1 --loops 1
docker run --rm --network none -v "$PWD/results:/results" \
  office-trace-replay:openeuler-v1 --dataset retail --dataset manufacturing --loops 2
```

每次命令生成独立结果目录，保存总报告、分阶段与分调用日志、独立验收和实际新输出 hash。默认只运行一次。当前每个容器串行执行；可以为不同实验使用独立容器。固定脚本与输入不代表 ZIP/PDF 时间戳或运行时间逐字节相同。

## 环境

第一版复用本地 `document-oe-snapshot:20260827`，构建器先核对锁定镜像 ID，关闭网络和拉取。容器实际路径是 `/opt/document-bench`。明确使用 `/opt/document-bench/.venv/bin/python`（Python 3.12.3），不会使用系统默认 Python 3.11.6。

Python 库冻结为 openpyxl 3.1.5、et_xmlfile 2.0.0、pypdf 6.10.0、pdf2image 1.17.0、Pillow 12.2.0；平台为 Linux ARM64。openEuler LibreOfficeDev 25.8.7.3 / Poppler 23.12.0 与 trace 原 Ubuntu 环境 LibreOffice 24.2.7.2 / Poppler 24.02.0 不同，两种环境分别做功能验收，不声称输出字节一致。完整观察及固定版本在 `runtime/environment-lock.json`。

现有 snapshot 基础层约 18.7 GB，第一版采用增量复制以保留已验证的 Python 前缀、系统库和 Office 环境；后续可以另做精简镜像。运行仅恢复所需输入、helper、Skill 和冻结 verifier，不启动 snapshot 中的旧 Agent。

构建和资格验证结果见 `reports/`。通过状态只对应报告中的具体 recipe hash、project lock 和镜像 ID；配方存在或镜像构建成功本身不代表全部回放已经通过。

已完成验证：全新 Git 导出副本的 7 项测试通过，0 skipped / failed / errors；七个数据集均在原 trace 环境及新 openEuler 镜像中重新生成输出，并通过冻结 verifier 的完整独立验收。汇总见 [qualification.json](reports/qualification.json)，输入/配方/输出与环境绑定均包含 hash。

已构建镜像为 `office-trace-replay:openeuler-v1`，固定 ID `sha256:d9b6fc8c07909e80124df83e239460446feef8be2db502a78f7a8a8c62fcf8cb`。正式资格报告记录的是这一镜像；未来重新构建产生的新 image ID 应另行绑定对应验收，不用浮动 tag 代替实验身份。
