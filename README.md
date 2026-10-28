# 文档解析类 Agent 轨迹回放与负载分析

**[阅读代表性评估报告](docs/representativeness-assessment.md)** · [完整实验数据](docs/experimental-results.md) · [采集与分析入口](analysis/README.md) · [镜像验收](docs/evidence/image-qualification-agent-traces.md)

本项目保存七个数据集的文档处理轨迹回放代码，并研究主要脚本、库、函数热点及 Topdown 特征。当前正式结果中，七例的 perf 热点和 DevKit Topdown 各有五次独立运行；PDF 每次处理十份记录。正式代码统一维护在 `main`。

## 数据集与执行入口

| 任务 | 数据集 | 执行入口 |
|---|---|---|
| PDF | OPM OF-306（旧基准） | `document-oe/run.py --scene pdf` |
| XLSX | TLC（旧基准） | `document-oe/run.py --scene xlsx` |
| PDF | IRS W-4、SBA 1919 | `agent/replay.py --dataset <id>` |
| XLSX | eGRID、HR Metro、Industry Productivity | `agent/replay.py --dataset <id>` |

一个镜像、两个独立入口。`document-oe/assets/` 的 43 个旧 workload 文件字节与模式冻结；新增五例在 `agent/datasets/<id>/` 中各自保存独立的 runner、recipe、输入、helper、Skill、验证和来源证据。共用入口只负责调度。真实 Agent 来源、内联代码脚本化和 CSV 缓存导出的回放适配见 [agent/README.md](agent/README.md)。

## 仓库导航

| 路径 | 用途与保留边界 |
|---|---|
| `docs/representativeness-assessment.md` | 正式评估报告，含关键发现、完整实验设计与方法、主要对比和 Word/PPT 覆盖边界 |
| `docs/experimental-results.md` | 完整实验数据记录，含逐轮指标、逐采样点曲线、热点明细、实际命令与证据索引 |
| `agent/` | 新五例的完整可执行材料；冻结文件不作目录重排 |
| `document-oe/` | 旧 OPM/TLC 的执行器与冻结 workload |
| `analysis/hotspots/` | perf 采集、解析、函数和脚本分组、逐轮与合并结果 |
| `analysis/topdown/` | HIP09/DevKit 核验、门控采集、统计、相似度和特征图 |
| `docs/` | 阅读入口：正式评估报告；`evidence/` 保存镜像构建、资格与整理证据，见 [文档导航](docs/README.md) |
| `results/` | 本地功能运行产物、独立验收和 Docker inspect，不提交 Git |
| `scripts/`、`tests/` | 离线镜像构建、环境探测和单元测试 |

本地仅保留当前七例各五次的 perf 与 Topdown 原始采集和对应产物，共 70 次运行；旧分支数据及未采用试跑已删除，保留清单见 [数据保留记录](docs/evidence/data-retention.json)。最新五次复用的首轮、必要来源索引和冻结 DevKit 工具继续保留。Git 保存代码、输入、来源、派生统计和报告，不上传大型 perf 原始文件。原始运行记录中的旧绝对路径不改写，实际材料按本仓库相对路径及 SHA256 索引定位。

## 当前镜像与环境

- 执行镜像：`office-trace-replay:agent-traces`，ID `sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。标签保留既有名称，与 Git 分支名称无绑定关系。
- 离线构建基础：`office-trace-replay:openeuler-release`，ID `sha256:e68ea4ca0e43340b09dd355b4217f756260fe4ae3d33c576fdb0b8ab4d5f437a`；继续保留。
- Python 3.12.3、openpyxl 3.1.5、LibreOffice 25.8.7.3、Poppler 23.12.0。固定 Python 为 `/opt/document-bench/.venv/bin/python`。

七例已通过当前环境的执行和循环验证，测量记录也核验实际 image ID。详细安装态与独立审计范围见[镜像资格记录](docs/evidence/image-qualification-agent-traces.json)。该历史记录冻结构建时状态，后续五次采集以[当前测量清单](analysis/topdown/CAMPAIGN.md)为准。报告和分析代码更新不要求重建执行镜像。

## 运行

```bash
# 新数据集；宿主入口自动 create → inspect → start，保存实际容器身份。
python3 -B agent/replay.py --docker-image office-trace-replay:agent-traces \
  --dataset hr_metro --loops 1 --results-dir "$PWD/results"

# 原 OPM，执行一轮、处理十份。
docker run --rm --network none -v "$PWD/results:/results" \
  --entrypoint /opt/document-bench/.venv/bin/python office-trace-replay:agent-traces \
  /opt/office-trace-replay/document-oe/run.py --scene pdf --pdf-applicant-count 10 --loops 1

# 原 TLC。
docker run --rm --network none -v "$PWD/results:/results" \
  --entrypoint /opt/document-bench/.venv/bin/python office-trace-replay:agent-traces \
  /opt/office-trace-replay/document-oe/run.py --scene xlsx --loops 1
```

新入口不传 `--dataset` 时运行新五例；旧入口独立运行 OPM/TLC。两套执行可在容器内顺序切换，共用 OS 锁拒绝重叠运行。循环内验证计入 workload；归档与独立深审位于 ROI 外。当前时间边界、采集范围和计算公式见正式报告第四至六节。

## 检查、分析与离线构建

```bash
# Git 不保存 0664/0775 的完整权限位；首次 checkout 后按冻结锁恢复元数据。
python3 -B scripts/prepare_checkout.py
make validate
make test
python3 -B -m unittest discover -s analysis/hotspots/tests
python3 -B -m unittest discover -s analysis/topdown/tests

# 只重建报告，不运行 workload 或采集器。
python3 -B analysis/hotspots/compare.py \
  --config analysis/hotspots/comparison-inputs-pdf5-20261027.json --update-report

# 离线构建必须选择尚不存在的候选标签，基础镜像不被覆盖。
make image IMAGE=office-trace-replay:candidate
```

构建不下载依赖、不调用模型、不执行正式 helper 或 LibreOffice 重算；基础镜像 ID 必须与 `container-contract.json` 一致。镜像内安装检查独立于完整 workload 运行。采集说明、数据定位及离线重算顺序见 [analysis/README.md](analysis/README.md)。
