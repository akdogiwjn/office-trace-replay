# 新旧数据集计算热点对比分析（hotspot-comparison）

研究目标：进程—库—函数/调用栈三层热点画像，判断旧切片（OPM/TLC 的 6+8 个
选中切片）覆盖了多少新增 workload 的计算，以及旧结论在新数据集上的适用性。

最终结论见 [reports/final-conclusions.md](reports/final-conclusions.md)。
完整对比表见 [reports/comparison-report.md](reports/comparison-report.md)，
余量解释见 [reports/unconfirmed-residual-report.md](reports/unconfirmed-residual-report.md)。

## 从提交恢复详细画像

详细 profiles 以 `processed/packed/*.json.gz` 提交，原始 JSON 展开副本被忽略。
压缩文件及解压后内容的 SHA256/大小记录在 `metadata/profile-artifacts.json`。
在仓库根目录运行：

```bash
python3 analysis/hotspot-comparison/scripts/profile_artifacts.py restore
python3 analysis/hotspot-comparison/scripts/profile_artifacts.py verify
python3 -m unittest discover -s analysis/hotspot-comparison/tests
```

恢复脚本拒绝覆盖内容不同的本地 JSON。恢复后可读取全部详细画像、重新生成
汇总报告；重新解析采样或计算余量仍需本地 `raw/`。原始 perf 数据不包含在压缩
profiles 中。发布后更新派生 profiles 时，运行 `profile_artifacts.py pack` 刷新压缩包。

## 冻结版本

`history/residual-baseline-v1/` 保存指纹质量修正前的报告、覆盖率、metadata 和
压缩的完整 profiles，并记录原始 SHA256。当前发布统一采用排除未恢复内联帧的
指纹规则；原路径/机制覆盖和余量保持不变，指纹统计重新计算。
`metadata/release-validation.json` 记录版本迁移的数值核对与发布验证。

## 目录

- `config/run-plan.json` — 采集计划（镜像、CPU 预算、采样率、重复次数、ROI 定义）。
- `config/mechanism-taxonomy.json` — 当前冻结的机制分类与覆盖规则，修正历史由 metadata 和历史基线记录。
- `legacy/legacy-slices.json` — 旧选中切片清单（脚本、输入状态、机制、历史权重）。
- `legacy/legacy-claims.json` — 旧结论清单（原文、适用条件、所需新证据）。
- `legacy/evidence/` — 旧报告快照（ANALYSIS.md 等 5 份，含来源路径与 hash）。
- `scripts/` — 采集与分析脚本（容器内采集器 + 宿主机解析/分析）。
- `metadata/` — 每次运行的元数据（镜像、hash、配置、采集质量）。
- `processed/` — 处理后的画像表、覆盖率、新热点、结论验证表。
- `reports/` — 最终对比报告。
- `raw/` — 原始采集数据（gitignore），`raw/index.json` 记录 SHA256 与配置绑定。

## 当前复现边界

以下分析命令在仓库根目录执行，路径均以 `analysis/hotspot-comparison/` 为基准：

```bash
python3 analysis/hotspot-comparison/scripts/parse_native.py analysis/hotspot-comparison/raw/<config>/<r1-or-r2> <config>
python3 analysis/hotspot-comparison/scripts/parse_pyspy.py analysis/hotspot-comparison/raw/<config>/pyspy/raw/<config>.pyspy.raw analysis/hotspot-comparison/raw/<config>/pyspy/out
python3 analysis/hotspot-comparison/scripts/rename_parallelism_schema.py
python3 analysis/hotspot-comparison/scripts/build_profiles.py
python3 analysis/hotspot-comparison/scripts/analyze_comparison.py
python3 analysis/hotspot-comparison/scripts/generate_report.py
python3 analysis/hotspot-comparison/scripts/analyze_unconfirmed_residuals.py
python3 analysis/hotspot-comparison/scripts/build_raw_index.py
```

`raw/` 被 git 忽略，含原始 perf.data、perf script、monitor 和独立 py-spy/strace 文件；只有保留这些文件的采集机可复核采样解析。clone 仓库可复核已提交的配置、脚本、metadata、派生表和报告，但不能凭 clone 重建缺失的原始样本。历史环境中未记录的镜像 digest、环境变量或 stdout 缓冲误差均标为未知，不作追溯推断。

旧切片来源匹配从 Python argv 中只取脚本操作数，再按实际运行入口解析：Skill 绝对路径经 runner 创建的链接指向 `/opt/document-bench/skills`，其内容由 Dockerfile 的 `COPY legacy/document-oe/` 安装；旧 OPM/TLC `source=None`，由 `/opt/document-bench/pdf|xlsx` seed 复制到 workspace；兼容数据集使用各自 `DATASETS.seed`。如果冻结 recipe 对脚本目标有精确 `write`，写入来源优先于 seed。`source` 快照只提供数据/辅助上下文，不能替代 argv 实际指向的运行文件。v9 image acceptance 验证了所声明镜像和 workload 文件，但这批采集没有记录实际运行 image ID 或进程文件 hash，所以来源 hash 是按 Docker/runner/recipe 重建的，不冒充当时直接采集值。完整 14 个切片映射和逐条来源链见 `processed/legacy-slice-source-map.json` 与 `metadata/source-resolution-audit.json`。

原生采样点机制只按叶函数及其所属 DSO 分类（`native-mechanisms-v3-leaf-context-separated`）；其他栈帧单独作为可重叠调用上下文，不能覆盖叶函数含义，也不进入互斥机制分母。调用栈相似度称为“规范化栈前缀指纹匹配”：最多 8 帧、至少 4 个已解析帧，符号去掉偏移，DSO 映射为类别并对同地址内联帧恢复所属类别。未知帧和短栈保留作诊断，不参与匹配；不同实际库可能归入同一 DSO 类别，且栈前缀截断，因此指纹既不是完整调用路径，也不是代码身份。叶函数相同、栈前缀匹配、脚本来源匹配分栏报告；它们都不能单独证明相同 Python 业务算法或优化收益。分类规则和边界见 `config/mechanism-taxonomy.json`。

### 未确认覆盖余量（只读离线分析）

`scripts/analyze_unconfirmed_residuals.py` 从既有 `raw/<dataset>/<repeat>/out/samples.jsonl` 重建 Retail、Manufacturing、HR 的互斥余量分解；只写入 `processed/unconfirmed-residual-decomposition.json` 与 `reports/unconfirmed-residual-report.md`，不改写 `processed/coverage.json`。首次运行会把覆盖率、profiles、配置、旧切片清单和 raw index 的 SHA256 固定到 `metadata/unconfirmed-residual-baseline.json`；后续若这些输入变化，脚本会停止，需建立新的基线版本。旧机制、叶函数和栈前缀参考只由旧 workload 中已匹配的切片进程样本构造；未知叶函数与弱栈前缀排除在相似匹配之外。无同地址实体帧的 inline DSO 作为未知帧处理。R1–R5 解释原路径∪机制余量，不自动增加确定覆盖率；展示阈值只控制热点列表，完整权重均保留。

本次发布的残余基线升级为 v2，并在 manifest 中指向保留的 v1。
升级核对了所有数据集的路径覆盖、机制覆盖、交集、并集和余量逐次不变；
只有指纹相关统计按修正后的规则统一刷新，不将历史来源 hash 冒充运行时观测。

当前 ROI 是估计边界：用 300 ms PERFROI 标记进程的样本中位时刻近似标记中点，再与 runner stdout 中单调时钟时间对齐。stdout 到达时刻可能受缓冲影响，现有采集没有独立校准偏移的第二时钟；边界附近的样本可能错分，不能声称严格排除了所有预运行活动。

轮询区间内观察到多个线程 CPU 计数增长只表明各线程曾运行，不能证明同时运行；不把此值称作峰值并行度，也不据此下串行结论。monitor CPU 时间是独立交叉核对，不参与 cycles 覆盖率。

## 采集命令（仅确需补采时）

```bash
# 1) 采集（每 config 独立容器，镜像取自 run-plan.json）
analysis/hotspot-comparison/scripts/run_collection2.sh native
analysis/hotspot-comparison/scripts/run_collection2.sh pyspy
analysis/hotspot-comparison/scripts/run_collection2.sh stat
analysis/hotspot-comparison/scripts/run_collection2.sh syscalls

# 2) 解析与索引（在仓库根目录运行）
python3 analysis/hotspot-comparison/scripts/parse_native.py analysis/hotspot-comparison/raw/<config>/<rep> <config>
python3 analysis/hotspot-comparison/scripts/parse_pyspy.py analysis/hotspot-comparison/raw/<config>/pyspy/raw/<config>.pyspy.raw analysis/hotspot-comparison/raw/<config>/pyspy/out
python3 analysis/hotspot-comparison/scripts/build_raw_index.py

# 3) 分析
python3 analysis/hotspot-comparison/scripts/build_profiles.py
python3 analysis/hotspot-comparison/scripts/analyze_comparison.py
python3 analysis/hotspot-comparison/scripts/generate_report.py
```

## 口径要点

- 计量：完整 workload ROI 的 `cycles:u`，按原始 perf sample period 求和估算；
  频率模式的 period 是内核估计，不是精确硬件周期总数。重复结果逐次保留。
- ROI：runner 输出 `[scene/dataset] start:` 行（预运行全项目 hash 校验与环境
  探测之后、循环开始之前）到进程结束。预运行阶段用 PERFROI 标记进程做
  perf 时钟到 CLOCK_MONOTONIC 的对齐后剔除。业务 verifier 在 ROI 内。
- 采集统一在 v9 镜像、Python 3.12.3、workload 绑定 CPU 0-7（8 核，新旧同
  预算；旧 PDF 证据是单核绑定，不能据此证明天然串行，故新证据统一放宽到 8 核）。
- 独立 py-spy 只作为 Python 路径的旁证；不用于把比例分配给 perf 原生样本。
