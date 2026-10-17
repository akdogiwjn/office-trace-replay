# office-trace-replay

正式执行入口统一为 **document-oe 统一 runner**：

```bash
python run_document_scene_loop.py --scene pdf --dataset opm
python run_document_scene_loop.py --scene pdf --dataset irs_w4
python run_document_scene_loop.py --scene pdf --dataset sba1919
python run_document_scene_loop.py --scene xlsx --dataset tlc
python run_document_scene_loop.py --scene xlsx --dataset retail
python run_document_scene_loop.py --scene xlsx --dataset manufacturing
python run_document_scene_loop.py --scene xlsx --dataset hr
```

`--scene pdf` 默认选择旧 `opm`，`--scene xlsx` 默认选择旧 `tlc`；`scene` 与 `dataset`
不匹配的组合（如 `--scene pdf --dataset retail`）会被拒绝。runner 通过 registry
（`DATASETS`）映射 scene+dataset → seed、workspace、recipe、source context、超时与
PDF 规模变体，只选择和加载 recipe，继续按 JSON 执行 read/write/exec；数据集业务步骤
与 enhancement 逻辑不硬编码进 runner。

**runner 自行准备运行环境**：直接调用 runner 与 `entry.py`/`suite` 路径使用完全一致的
解析与准备规则。runner 在首轮开始前（不在测量区间内）会：
- 校验所选冻结 workload（见下节），
- 准备 source context（`OFFICE_TRACE_PROJECT`）、`/workspace` 链接与 Skill 链接，
- 按 `--legacy-python venv|system` 设置 PATH / `VIRTUAL_ENV`，清除外部
  `PYTHONPATH` / 旧 dataset context，
- 记录实际解释器、`python3` 版本、关键库与 LibreOffice 版本到 summary 的
  `environment`。

因此 `python run_document_scene_loop.py --scene xlsx --dataset retail` 在全新容器中可
直接运行，不需要手工 `export OFFICE_TRACE_PROJECT` 或提前执行 entry。`--timed` 由
runner 原生支持（timing hook 内置于 runner），`run_document_scene_loop_timed.py`
仅作为转发 `--timed` 的兼容入口，避免递归启动与重复打补丁。

**runner 解释器统一**：直接 runner 会先核对当前解释器与 `--legacy-python` 请求模式
是否一致；不一致时在循环开始前（验证与环境探测之前）通过 `os.execv` 切换到指定解释器
（venv 3.12.3 / system 3.11.6），使 runner 与 recipe 工具使用同一 Python 环境。带
`DOCUMENT_BENCH_REEXEC_READY` 守卫防止无限重启；指定解释器不存在或版本不符时明确
拒绝，不静默退回。`suite`、Docker `--scene` 与直接 runner 行为一致，summary 记录
实际 runner 与 recipe Python 的 executable/version。

## 完整性边界

`legacy/document-oe/lock.json` 将完整性边界分为两部分：

- **executor（版本化）**：统一 runner `run_document_scene_loop.py` 与其 timed 包装，
  记录为 `unified-dataset-runner-v1`，每次变更必须是有记录的 executor 发布。
- **workload（字节冻结）**：其余 43 个原始 document-oe 文件（旧 recipe JSON、
  PDF/XLSX 输入、Skill 工具、recalc、verifier、atomic helper、inspect/export 工具等）
  与真实旧容器导出逐字节一致，严格校验。

旧 `opm`/`tlc` 的 recipe JSON、命令、调用顺序、helper、输入与冻结 Agent trace 保持
不变；runner 的循环、workspace reset、超时、错误处理、退出状态与计时语义对旧用例
保持不变。`legacy.py` 保留完整性校验等公共能力；`compatible.py` 不再作为新数据集
的正式运行入口，仅保留 suite 绑定校验；新数据集的调度、循环完成检查、独立验收与
归档在 `replay/suite.py`。

**执行前冻结绑定校验**：`replay/freeze.py::validate_dataset` 在 runner 首轮前（以及
`--validate-recipe` 时）校验所选 workload：
- executor 版本与 43 个旧 workload 文件（`legacy/document-oe/lock.json`）；
- 全项目冻结（`assets/project-lock.json`）；
- 对 canonicalized 数据集：recipe hash 与 `compatibility/suite.json` 冻结值一致，
  并校验 parent recipe / prompt / contract / input / helper / source verifier 绑定。
预期 hash 始终来自冻结索引，绝不"新算后覆盖预期"；篡改 recipe 或 helper 会在任何
workload 命令执行前被拒绝。

**重复运行与归档**：`replay/suite.py` 为每次 invocation 创建唯一 `run_id` 与独立结果
目录（`<results>/<variant>/<stamp>/`），精确关联本次 runner 的 summary / iterations /
calls / nested_calls，不依赖"第一个匹配目录"。同一结果根目录可重复运行、也可先后运行
PDF 1/10 变体（`irs_w4-n1` 与 `irs_w4-n10` 目录可区分）而互不覆盖。循环完成后校验
dataset / scene / PDF 变体 / recipe hash / 请求与完成轮数 / 每轮事件序号与状态，再执行
独立验收并归档最后一轮 workspace；任何一轮失败都不会被最后一轮成功掩盖，失败记录
同样持久化到 `evidence.json`。

## 新 XLSX：直接重算最终输出

Retail / Manufacturing / HR 的主要流程统一为：

- **P01 Inspect / Prepare**：复制官方输入到最终输出 workbook，检查结构与特征。
- **P02 Build**：写入并执行 dataset-specific enhancement helper（经由通用原子
  helper `compatibility/tools/run_xlsx_helper_atomic.py`，通过参数显式指定目标
  workbook，不依赖 `monthly_operations_report.xlsx` 等固定字符串），直接增强最终输出。
- **P03 Process / Publish**：用原 XLSX Skill 的 `recalc.py` 重算最终输出 workbook，
  LibreOffice 直接保存计算缓存；检查公式与 cached values；导出 CSV / metrics。
  保存后不再用 openpyxl 重写最终文件。
- **P04 Verify / Deliver**：运行版本化语义验证器，写 summary，检查交付文件。

正式 recipe 不再执行 Retail `assemble_output.py`、Manufacturing `inject_caches.py`、
HR `patch.py`；这些历史 helper、父 recipe 与原始 trace 保留为 provenance，不覆盖为
新执行记录。

## 版本化语义验证 contract（spreadsheet-semantic-v3）

`compatibility/verification/{verify,spreadsheet,contracts,workbooks}.py` 是 replay 私有
的版本化验证器（父 trace 冻结 verifier 与旧 TLC verifier 未修改）。继续严格验证：官方
输入 hash、原 worksheet、业务数据值与缺失/抑制标记、原公式未删除/硬编码/错误覆盖、
原图表数据系列与引用、新增 Summary/KPI/scenario/chart 符合任务、公式使用与依赖正确、
LibreOffice 重算成功、cached values 存在且正确、无新增公式错误、交付物完整、
`business_verification.status == success`。

收紧后的明确规则：

- **公式与引用归一化**：归一化先做 token 化，区分双引号字符串字面量（逐字保留）、
  单引号 sheet/workbook 标识符（保留内容，`''` 转义取消，引号本身是序列化）与普通
  token（仅去除紧邻结构字符的空白、`$`、`_xlfn.`、大小写折叠）。`'A B'!A1` 与 `AB!A1`
  不等价；`'O''Brien'!A1` 正确处理；两个标识符之间的空白是 Excel 引用交集运算符，予以
  保留。原公式单元格必须是公式类型（不能换成相同内容的普通文本或硬编码值）。
- **defined names**：同时校验 workbook 全局名称与 worksheet 局部名称，按 (name, scope)
  建立关联；原名称的引用含义必须保持——`Data!A1` 改指 `Data!A2`、指向不存在的名称、
  缺失 sheet、`#REF!`、形成无法解析的引用链、局部名称被删除或作用域改变都必须失败
  （`source:defined_names_damaged` / `source:defined_names`）；间接引用解析带循环检测，
  不会无限递归；仅明确支持的序列化差异（目标含义相同）记为 diagnostic
  （`source:defined_names_serialization`）。源文件原本已损坏（如 `#REF!`）的名称只在
  对应内容逐字节不变时才作为历史状态保留，不允许任意改变。
- **空字符串与空单元格**：仅当 manifest 的 `empty_strings_policy` 明确列出的原始表允许
  等价并记录（政策逐数据集可核查）；未列出的表出现空字符串丢失即数据变化失败。
- **number format**：单位表达式（货币符号、百分号、单位后缀等字面量）变化必须失败
  （`source:number_formats_meaning`）；仅序列化/精度变化记为 diagnostic。
- **merged regions**：源合并被删除失败（`source:merged_regions_removed`）；输出新增合并
  记为 diagnostic（内容丢失由严格 `source:data` 检查兜底）。
- **诊断统计**：`diagnostics_total`（诊断槽位数）与 `diagnostic_diff_count`（非空差异
  项数）分开记录，不把槽位描述成真实变化。

## PDF

PDF 保持当前执行流程，仅接入统一入口与 registry：准备完整 10 份字段 mapping，按
`--pdf-applicant-count 1/10` 填充/渲染 1 份或 10 份；两个新 PDF 使用统一字段 ID
预检查；最终验证全部准备好的 mapping 与实际选择的输出；旧 OPM recipe 及其实际脚本不变。

## 使用

```bash
make test          # 仓库自包含单元测试
make validate      # replay/entry.py --validate-only
make image         # scripts/build_image.py --tag office-trace-replay:openeuler-v9
make replay DATASET=retail   # 容器内单数据集
```

默认容器入口 `replay/entry.py` 是 suite 调度层：旧 workload 先以原 runner 行为运行，
随后每个 canonicalized 数据集运行一个统一 runner 进程（`--legacy-python` 与 `--timed`
以相同规则传递给 runner），循环之间不做额外独立验收，全部循环完成后执行独立验收并归档
最后一轮产物与全部轮次日志；任何一轮失败都不会被最后一轮成功掩盖。容器 CMD 默认
`--loops 1`（直接调用 runner 时其默认 loops=20000，与原 executor 一致）。默认 Python 为
原 venv 3.12.3；`--legacy-python system` 使 runner 与 recipe 内 `python3` 一致使用系统
3.11.6。timed 模式保留 phase/call/nested process 日志。

每次运行会冻结 `evidence.json`（run id、实际 recipe / input / helper / verifier /
contract / executor / 环境版本 / 验收结果的完整关联），并复制到
`reports/evidence/<variant>/<stamp>/`；`reports/qualification.json` 记录路径与完整 64 位
SHA256。

`--workflow derived-v1` 仍可选历史父 recipe 引擎（`replay/run.py`）。历史验收记录保留
在 `reports/history/`。

### 历史别名 opm_v2 / tlc_v2

`--dataset opm_v2` / `--dataset tlc_v2` 仅用于 provenance 对比：它们把冻结的父
recipe（`recipes/opm.json`、`recipes/tlc.json`）路由到历史 derived-v1 引擎
（`replay/run.py`），不是 canonicalized workload，也没有 compatibility entry。限制：

- 它们在任何一次调用中**最后**执行——历史引擎会替换 Skill 链接与 source context，
  不能在统一 runner workload 之前运行；混选时正式 dataset 先完成。
- 不支持 `--timed`（执行前直接拒绝）；`--pdf-applicant-count`、`--legacy-python` 等
  formal-suite 参数对历史引擎不生效（历史 recipe 按冻结原样回放，opm_v2 固定填充
  全部 10 条记录）。
- 普通 `opm`/`tlc` 及 `pdf`/`xlsx` 默认别名继续执行旧 document-oe workload，不受
  历史别名影响；七个正式 dataset 的默认执行方式不变。

## 版本与研究定位

新 recipe 标记为 `canonicalized_deterministic_replay_derived_from_successful_agent_executions`
（基于成功真实 Agent 执行构建的标准化 deterministic tool replay），并记录父 Agent
trace / 父 recipe hash、新 recipe 与 helper hash、新 verifier contract/version、输入
hash、执行器/Skill/Python/库/LibreOffice 版本与取消 preservation 阶段等具体改造。
标准化 recipe 不是原 Agent 最终实现的逐条忠实回放；不同输入间的差异不能仅凭执行结构
对齐与功能通过就归因于行业差异或声称代表性已获证明。
