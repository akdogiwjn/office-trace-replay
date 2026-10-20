# 新 XLSX 热点与读写特征（v1）

## 主要结论

本报告复用合格的 TLC、Industry Productivity 与 HR Metro profile，并加入 Retail Online 的同镜像 native 离线恢复和本轮唯一 py-spy 单轮。Native 为完整 ROI `cycles:u` sample period；py-spy 为独立样本计数，二者不互相换算。每个新数据集仅一次采集，结论是描述性画像。

### Native 进程/脚本热点

| 数据集 | ROI samples | ROI period | 重复数 | 主要进程/脚本（占完整 ROI） |
|---|---:|---:|---:|---|
| tlc | 73,622 | 1,392,173,918,517 | 2 | xlsx-enhance 21.87%; xlsx-inspect-structure 12.46%; xlsx-recalc 11.49%; xlsx-inspect-features 10.41%; xlsx-verify 10.24% |
| industry_productivity | 51,330 | 1,424,298,137,746 | 1 | xlsx-inspect-tool 36.92%; xlsx-enhance 20.01%; xlsx-recalc 13.10%; xlsx-summary-export 10.14%; xlsx-verify 10.09% |
| hr_metro | 41,122 | 1,049,103,685,173 | 1 | xlsx-inspect-tool 38.03%; xlsx-enhance 22.83%; xlsx-recalc 12.31%; xlsx-verify 9.91%; xlsx-summary-export 9.56% |
| retail_online | 35,493 | 1,453,535,128,571 | 1 | xlsx-inspect-tool 30.58%; soffice.bin 21.00%; xlsx-enhance 18.01%; xlsx-recalc 10.13%; xlsx-verify 8.24% |

### 主要库与物理叶函数

函数名按实体帧归一化：仅在 `inline_recovered=true` 时以 `entity_sym/entity_dso` 代替内联叶帧；Retail Online 的 `--no-inline` 叶帧直接使用。未知 DSO/符号仍在分母内，不继承其他地址的调用者库。

| 数据集 | 主要库（占完整 ROI） | 代表性物理叶函数（占完整 ROI） |
|---|---|---|
| tlc | libpython 78.45%; expat-xml 5.86%; libreoffice 5.38%; elementtree-xml 3.11%; unknown 2.09% | xlsx-enhance::_PyEval_EvalFrameDefault (libpython) 6.35%; xlsx-recalc::_PyEval_EvalFrameDefault (libpython) 3.26%; xlsx-inspect-structure::_PyEval_EvalFrameDefault (libpython) 3.19%; xlsx-verify::_PyEval_EvalFrameDefault (libpython) 2.34%; xlsx-inspect-features::_PyEval_EvalFrameDefault (libpython) 2.19% |
| industry_productivity | libpython 76.67%; libreoffice 6.77%; expat-xml 5.77%; elementtree-xml 3.39%; unknown 1.97% | xlsx-inspect-tool::_PyEval_EvalFrameDefault (libpython) 7.71%; xlsx-enhance::_PyEval_EvalFrameDefault (libpython) 6.04%; xlsx-inspect-tool::gc_collect_main (libpython) 3.61%; xlsx-recalc::_PyEval_EvalFrameDefault (libpython) 3.40%; xlsx-inspect-tool::subtype_traverse (libpython) 2.18% |
| hr_metro | libpython 78.22%; expat-xml 5.56%; libreoffice 4.72%; elementtree-xml 3.79%; zlib 2.29% | xlsx-inspect-tool::_PyEval_EvalFrameDefault (libpython) 7.43%; xlsx-enhance::_PyEval_EvalFrameDefault (libpython) 7.12%; xlsx-inspect-tool::gc_collect_main (libpython) 3.93%; xlsx-recalc::_PyEval_EvalFrameDefault (libpython) 3.49%; xlsx-inspect-tool::subtype_traverse (libpython) 2.52% |
| retail_online | libpython 64.53%; libreoffice 20.30%; expat-xml 4.51%; libc 3.43%; elementtree-xml 2.87% | xlsx-inspect-tool::_PyEval_EvalFrameDefault (libpython) 6.02%; xlsx-enhance::_PyEval_EvalFrameDefault (libpython) 5.67%; soffice.bin::void rtl::str::release<_rtl_uString>(_rtl_uString*) (libreoffice) 3.38%; soffice.bin::rtl_uString_acquire (libreoffice) 3.35%; xlsx-inspect-tool::gc_collect_main (libpython) 2.64% |

### 与 TLC 的热点差异

| 数据集 | 进程/脚本 share 变化较大项（百分点，vs TLC） | 库 share 变化较大项（百分点，vs TLC） | TLC 未观察且本数据集 ≥0.5% 的物理叶函数 |
|---|---|---|---|
| industry_productivity | xlsx-inspect-tool +36.92pp; xlsx-inspect-structure -12.46pp; xlsx-inspect-features -10.41pp; xlsx-inspect-formulas -8.22pp | libpython -1.78pp; libreoffice +1.39pp; elementtree-xml +0.28pp; other +0.27pp | 无（按观察集合定义） |
| hr_metro | xlsx-inspect-tool +38.03pp; xlsx-inspect-structure -12.46pp; xlsx-inspect-features -10.41pp; xlsx-inspect-formulas -8.22pp | elementtree-xml +0.68pp; libreoffice -0.66pp; zlib +0.56pp; expat-xml -0.30pp | 无（按观察集合定义） |
| retail_online | xlsx-inspect-tool +30.58pp; soffice.bin +16.41pp; xlsx-inspect-structure -12.46pp; xlsx-inspect-features -10.41pp | libreoffice +14.92pp; libpython -13.92pp; unknown -2.03pp; libc +1.93pp | ScMatrixImpl::ExecuteBinaryOp(unsigned long, unsigned long, ScMatrix const&, ScMatrix const&, ScInterpreter*, std::function<double (double, double)> const&) 1.04%; ScInterpreter::Interpret() 0.69%; ScInterpreter::PushWithoutError(formula::FormulaToken const&) 0.65% |

### Native 采样与符号质量

丢失样本与丢失 chunks 按采集日志分别记录；其 ROI 归属未知。`addr2line` 计数标明日志来源，不代表对应 ROI 权重。未知 DSO、未知符号和空栈分别按完整 ROI period 计算，未知 DSO 与未知符号可重叠。

| 数据集 | lost samples | lost chunks | addr2line warnings | ROI unknown DSO | ROI unknown symbol | ROI empty stack |
|---|---:|---:|---:|---:|---:|---:|
| tlc | 57/115 | 5/10 | 未记录/未记录 | 2.09% | 0.14% | 0.00% |
| industry_productivity | 63 | 11 | 334 | 1.97% | 0.14% | 0.00% |
| hr_metro | 38 | 7 | 197 | 2.04% | 0.13% | 0.00% |
| retail_online | 31 | 5 | 826/0（partial/no-inline） | 0.06% | 0.08% | 0.00% |

### XLSX load / lazy scan / save（py-spy）

分母是全部解析到的 py-spy stack count，保留 process-only/no-Python-frame 样本；明确排除了 parser 标记为已知预检的少量样本。百分比是 Python 采样活动估计，不是函数墙钟时间、I/O 等待或 native cycles。每个样本主分类互斥：load、lazy、save、other、no-python-frames。

| 数据集 | 分母 samples | load_workbook 内部 A | read_only 延迟扫描 B | 加载并集 A∪B | Workbook.save D | 加载+保存并集 | 其他 | 无 Python 函数栈 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| tlc | 11,050 | 67.98% | 10.44% | 78.43% | 12.43% | 90.85% | 3.72% | 5.43% |
| industry_productivity | 22,065 | 64.17% | 12.99% | 77.16% | 13.39% | 90.55% | 2.81% | 6.63% |
| hr_metro | 16,893 | 62.46% | 12.43% | 74.89% | 14.96% | 89.85% | 2.84% | 7.30% |
| retail_online | 18,763 | 64.25% | 13.01% | 77.26% | 12.98% | 90.25% | 3.67% | 6.08% |

#### 脚本贡献

`全部 Python 样本贡献` 是该脚本 samples / 全部保留 samples；`脚本内` 是该脚本内各类样本占比。

| 数据集 | 主要脚本 | 占全体 Python 样本 | 脚本内 load / lazy / save / other / no-stack |
|---|---|---:|---|
| tlc | xlsx-enhance | 23.70% | 42.92%/0.00%/52.42%/0.27%/4.39% |
| tlc | xlsx-inspect-structure | 12.78% | 85.20%/0.00%/0.00%/14.80%/0.00% |
| tlc | xlsx-recalc | 12.54% | 12.05%/83.19%/0.00%/4.55%/0.22% |
| tlc | xlsx-inspect-features | 11.48% | 90.54%/0.00%/0.00%/2.44%/7.02% |
| tlc | xlsx-verify | 10.90% | 88.63%/0.00%/0.00%/6.06%/5.31% |
| tlc | xlsx-inspect-formulas | 9.19% | 91.82%/0.00%/0.00%/0.00%/8.18% |
| industry_productivity | xlsx-inspect-tool | 40.20% | 88.18%/0.00%/0.00%/2.00%/9.82% |
| industry_productivity | xlsx-enhance | 22.43% | 36.40%/0.00%/59.68%/0.44%/3.47% |
| industry_productivity | xlsx-recalc | 14.24% | 0.10%/91.18%/0.00%/8.66%/0.06% |
| industry_productivity | xlsx-verify | 11.75% | 86.96%/0.08%/0.00%/5.44%/7.52% |
| industry_productivity | xlsx-summary-export | 11.38% | 90.72%/0.00%/0.00%/0.36%/8.92% |
| hr_metro | xlsx-inspect-tool | 40.85% | 87.13%/0.00%/0.00%/1.93%/10.94% |
| hr_metro | xlsx-enhance | 25.02% | 35.96%/0.00%/59.81%/1.25%/2.98% |
| hr_metro | xlsx-recalc | 13.39% | 0.18%/92.84%/0.00%/6.98%/0.00% |
| hr_metro | xlsx-verify | 10.56% | 84.47%/0.00%/0.00%/7.06%/8.46% |
| hr_metro | xlsx-summary-export | 10.16% | 87.88%/0.00%/0.00%/0.47%/11.66% |
| hr_metro | xlsx-atomic-helper | 0.02% | 0.00%/0.00%/0.00%/50.00%/50.00% |
| retail_online | xlsx-inspect-tool | 39.31% | 91.09%/0.00%/0.00%/1.68%/7.23% |
| retail_online | xlsx-enhance | 24.06% | 36.29%/0.00%/53.97%/6.98%/2.77% |
| retail_online | xlsx-recalc | 13.83% | 0.27%/94.14%/0.00%/5.55%/0.04% |
| retail_online | xlsx-verify | 10.98% | 89.71%/0.00%/0.00%/4.66%/5.63% |
| retail_online | xlsx-summary-export | 10.82% | 90.69%/0.00%/0.00%/0.39%/8.91% |
| retail_online | other | 1.00% | 0.00%/0.00%/0.00%/1.07%/98.93% |

### 当前旧 TLC 与历史报告

OPM N=1：当前两次 native 的 Python 进程占 87.44%、pdftoppm 占 12.38%（另有 pdfinfo 0.18%）；历史报告为 Python 90.64%、pdftoppm 9.23%。库层当前/历史 libpython 50.35%/53.58%、zlib 15.80%/18.14%、Pillow 15.46%/15.21%；属于描述性 N=1 对照，历史仅报告级且缺少逐函数身份。TLC：历史报告级 libpython=79.65%、ElementTree=3.49%、expat=5.61%、zlib=1.42%；当前 TLC 两次 native 样本按 period 合并后 libpython=78.45%、ElementTree=3.11%、expat=5.86%、zlib=1.73%。当前聚合 Python XLSX scripts=91.30%，LibreOffice process/threads=7.93%。TLC 的库层比例总体接近；历史没有逐函数 profile/hash，不能声称逐函数复现。上述旧用例历史数据均复用 v2 报告，本轮未重采。

## 解释与证据边界

- 共同的 libpython、expat/ElementTree、zlib、GC/解释器路径只证明运行时成本共有，不证明相同 Python 业务算法。具名函数相同也不证明调用语义或算法收益相同。
- Retail Online native 恢复采用同镜像 `perf script --no-inline`。原容器 partial 保留；宿主恢复的 94.31% 空栈输出不进入本报告。跨采集函数比较用实体帧口径；未恢复 owner 的样本保留未知。
- TLC/Industry 来自 v9/current-loop 旧 runner 数据；HR Metro/Retail Online 是 v11/current runner。输入、执行版本及轻量验证 contract 不完全相同。
- ROI 对齐基于 PERFROI 中点与 stdout 到达时刻估计，尚未独立校准；lost samples/chunks 和 addr2line 警告保持原记录，ROI 归属未知。
- TLC 有两次 native repeats；Industry、HR Metro、Retail Online 各仅一次。新样本无法估算重复波动或证明稳定性。
- py-spy 统计不是整轮墙钟时间。load/lazy/save 是调用栈分类，不等同磁盘读写等待、带宽或 LibreOffice 的 store 操作。

## 证据文件

- `tlc` pyspy: `raw/tlc/pyspy/raw/tlc.pyspy.raw` (qualified=True)
- `industry_productivity` pyspy: `raw/current-loop-hotspots-v2/20261019T124014Z-845e640e-remaining-modes/industry_productivity/pyspy/raw/industry_productivity.pyspy.raw` (qualified=True)
- `hr_metro` pyspy: `raw/new-xlsx-performance-v1/campaign-20261020T0210Z/hr_metro/pyspy/raw/hr_metro.pyspy.raw` (qualified=True)
- `retail_online` pyspy: `raw/new-xlsx-performance-v1/20261020T032424Z-retail-online-pyspy/retail_online/pyspy/raw/retail_online.pyspy.raw` (qualified=True)
- `tlc` native: `raw/tlc/r1/out/samples.jsonl` (qualified=True)
- `tlc` native: `raw/tlc/r2/out/samples.jsonl` (qualified=True)
- `industry_productivity` native: `raw/current-loop-hotspots-v2/20261019T124014Z-845e640e-remaining-modes/industry_productivity/r1/out/samples.jsonl` (qualified=True)
- `hr_metro` native: `raw/new-xlsx-performance-v1/campaign-20261020T0210Z/hr_metro/r1/out/samples.jsonl` (qualified=True)
- `retail_online` native: `raw/new-xlsx-performance-v1/recovery/20261020T030642Z-retail-online-native-same-image-noinline/retail/r1/out/samples.jsonl` (qualified=True)

分析代码 SHA256：`4947183f286373e66cfa6ae1898dab3419629a7a16153c5ba47f40b0b3361186`。机器结果：`comparison.json`。
