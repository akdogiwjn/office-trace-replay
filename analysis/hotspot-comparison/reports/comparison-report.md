# 新旧数据集计算热点对比报告

最终研究结论见 [final-conclusions.md](final-conclusions.md)；未确认覆盖余量的逐样本分解见 [unconfirmed-residual-report.md](unconfirmed-residual-report.md)。

口径：采集计划使用 v9 镜像（本批实际运行 image ID 未单独记录）、Python 3.12.3、workload 绑定 CPU 0-7（8 核预算，新旧同一设置）、`perf cycles:u` 99 Hz（PDF）/49 Hz（XLSX）DWARF 调用栈，period 加权；py-spy 独立运行只作 Python 层机制构成证据。ROI 从 runner `start:` 行（预运行 hash 校验与环境探测之后）到进程结束，业务 verifier 在内。每个 native 配置 2 次独立重复。详见 `config/run-plan.json`、`config/mechanism-taxonomy.json` 与 `README.md`。

## 1. 旧切片覆盖率（规则版本及修正依据见 taxonomy 和 metadata）

覆盖分母为完整 workload ROI 的用户态 cycles:u 样本 period 总和。执行路径与旧切片机制分别按样本求并集，并单列交集；函数/调用路径是更细的旁证，不能推断业务算法相同。‘未覆盖余量’、真未知 native、原生机制已知但业务操作未知是诊断维度，彼此可能重叠，不能相加。每个 native 样本只归入一个互斥机制。monitor CPU 时间仅作独立交叉核对。

| 配置 | 类型 | 路径∪机制 | 执行路径 | 机制证据 | 交集 | 叶函数相同 | 规范化栈前缀指纹 | 旧定义机制候选 | 未覆盖余量 | 真未知 native | 原生已知/业务操作未知 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| opm-n1 | 旧对照 N=1 | 98.4% | 96.2% | 63.4% | 61.3% | 99.6% | 86.6% | 0.0% | 1.6% | 3.3% | 85.0% |
| irs_w4-n1 | 新 N=1 | 83.0% | 75.5% | 63.6% | 56.1% | 86.6% | 52.4% | 0.0% | 17.0% | 3.0% | 86.5% |
| sba1919-n1 | 新 N=1 | 84.3% | 75.0% | 67.9% | 58.6% | 88.6% | 59.2% | 0.0% | 15.7% | 2.5% | 82.4% |
| opm-n10 | 旧对照 N=10 | 99.8% | 99.7% | 67.9% | 67.8% | 100.0% | 88.1% | 0.0% | 0.2% | 2.9% | 84.6% |
| irs_w4-n10 | 新 N=10 | 93.8% | 86.6% | 68.6% | 61.4% | 90.4% | 63.5% | 0.0% | 6.2% | 3.1% | 84.6% |
| sba1919-n10 | 新 N=10 | 92.0% | 80.6% | 72.1% | 60.8% | 94.9% | 72.0% | 0.0% | 8.0% | 2.8% | 82.5% |
| tlc | 旧对照 | 99.7% | 99.2% | 57.4% | 56.8% | 100.0% | 92.7% | 0.0% | 0.3% | 2.1% | 96.3% |
| retail | 新 | 65.1% | 25.1% | 58.7% | 18.6% | 88.1% | 61.5% | 0.0% | 34.9% | 3.1% | 94.8% |
| manufacturing | 新 | 64.4% | 27.4% | 53.5% | 16.5% | 82.1% | 41.3% | 0.0% | 35.6% | 6.9% | 88.3% |
| hr | 新 | 61.0% | 18.0% | 53.5% | 10.6% | 92.2% | 67.0% | 0.0% | 39.0% | 5.0% | 91.8% |

## 2. 进程层热点（cycles:u period，两次重复按 period 合并）

### opm-n1（旧对照 N=1）

| 进程/命令角色 | ROI cycles:u period 份额 |
|---|---|
| `pdf-convert` | 34.5% |
| `pdf-fill` | 18.8% |
| `pdf-verify` | 14.2% |
| `pdftoppm` | 12.4% |
| `pdf-extract-fields` | 8.9% |
| `pdf-check-fillable` | 7.6% |
| `runner` | 1.9% |
| `pdf-mapping-driver` | 0.5% |
| `python-inline` | 0.5% |
| `pdf-summary-writer` | 0.4% |

### irs_w4-n1（新 N=1）

| 进程/命令角色 | ROI cycles:u period 份额 |
|---|---|
| `pdf-convert` | 37.9% |
| `pdf-verify` | 21.4% |
| `pdf-fill` | 18.0% |
| `pdftoppm` | 11.2% |
| `pdf-extract-fields` | 5.0% |
| `pdf-check-fillable` | 3.5% |
| `runner` | 1.3% |
| `python-unknown-script` | 1.1% |
| `pdf-mapping-driver` | 0.3% |
| `pdf-summary-writer` | 0.2% |

### sba1919-n1（新 N=1）

| 进程/命令角色 | ROI cycles:u period 份额 |
|---|---|
| `pdf-convert` | 36.6% |
| `pdf-verify` | 24.3% |
| `pdftoppm` | 15.2% |
| `pdf-fill` | 13.7% |
| `pdf-extract-fields` | 4.9% |
| `pdf-check-fillable` | 4.4% |
| `pdf-mapping-driver` | 0.3% |
| `pdfinfo` | 0.3% |
| `pdf-summary-writer` | 0.2% |
| `python-inline` | 0.1% |

### opm-n10（旧对照 N=10）

| 进程/命令角色 | ROI cycles:u period 份额 |
|---|---|
| `pdf-convert` | 36.7% |
| `pdf-fill` | 35.0% |
| `pdftoppm` | 13.3% |
| `pdf-verify` | 11.1% |
| `pdf-extract-fields` | 1.7% |
| `pdf-check-fillable` | 1.7% |
| `pdfinfo` | 0.2% |
| `pdf-summary-writer` | 0.1% |
| `pdf-mapping-driver` | 0.1% |
| `python-inline` | 0.0% |

### irs_w4-n10（新 N=10）

| 进程/命令角色 | ROI cycles:u period 份额 |
|---|---|
| `pdf-convert` | 38.8% |
| `pdf-fill` | 33.2% |
| `pdftoppm` | 13.0% |
| `pdf-verify` | 12.3% |
| `pdf-extract-fields` | 0.9% |
| `pdf-check-fillable` | 0.8% |
| `runner` | 0.7% |
| `pdf-mapping-driver` | 0.1% |
| `pdfinfo` | 0.1% |
| `python-inline` | 0.0% |

### sba1919-n10（新 N=10）

| 进程/命令角色 | ROI cycles:u period 份额 |
|---|---|
| `pdf-convert` | 38.5% |
| `pdf-fill` | 24.5% |
| `pdf-verify` | 19.2% |
| `pdftoppm` | 15.3% |
| `pdf-extract-fields` | 1.1% |
| `pdf-check-fillable` | 1.1% |
| `pdfinfo` | 0.2% |
| `pdf-mapping-driver` | 0.1% |
| `runner` | 0.0% |
| `python-unknown-script` | 0.0% |

### tlc（旧对照）

| 进程/命令角色 | ROI cycles:u period 份额 |
|---|---|
| `xlsx-enhance` | 21.9% |
| `xlsx-inspect-structure` | 12.5% |
| `xlsx-recalc` | 11.5% |
| `xlsx-inspect-features` | 10.4% |
| `xlsx-verify` | 10.2% |
| `xlsx-summary-export` | 8.5% |
| `xlsx-inspect-formulas` | 8.2% |
| `xlsx-inspect-cached` | 8.1% |
| `soffice.bin` | 4.6% |
| `lo-thread` | 3.3% |

### retail（新）

| 进程/命令角色 | ROI cycles:u period 份额 |
|---|---|
| `xlsx-verify` | 38.0% |
| `xlsx-inspect-tool` | 19.2% |
| `soffice.bin` | 16.5% |
| `xlsx-enhance` | 11.2% |
| `xlsx-recalc` | 7.6% |
| `xlsx-summary-export` | 5.4% |
| `lo-thread` | 1.4% |
| `python-unknown-script` | 0.7% |
| `runner` | 0.0% |
| `bash` | 0.0% |

### manufacturing（新）

| 进程/命令角色 | ROI cycles:u period 份额 |
|---|---|
| `xlsx-verify` | 42.7% |
| `soffice.bin` | 19.9% |
| `xlsx-inspect-tool` | 14.0% |
| `xlsx-enhance` | 7.2% |
| `xlsx-summary-export` | 7.1% |
| `xlsx-recalc` | 6.0% |
| `lo-thread` | 2.5% |
| `python-unknown-script` | 0.5% |
| `bash` | 0.1% |
| `runner` | 0.1% |

### hr（新）

| 进程/命令角色 | ROI cycles:u period 份额 |
|---|---|
| `xlsx-verify` | 38.3% |
| `xlsx-inspect-tool` | 21.1% |
| `xlsx-enhance` | 12.1% |
| `soffice.bin` | 9.7% |
| `xlsx-recalc` | 8.0% |
| `xlsx-summary-export` | 7.1% |
| `runner` | 2.6% |
| `lo-thread` | 0.7% |
| `python-unknown-script` | 0.4% |
| `bash` | 0.0% |

### Monitor CPU 时间交叉核对（独立口径）

### 调用上下文（可重叠，不属于机制分母分区）

采样点机制由叶函数与叶 DSO 分类；调用栈中较远的函数只记为上下文证据。上下文可与采样点机制冲突并可多重出现，因此各项权重可能重叠，不能和互斥的机制层相加。它们解释采样所在路径，不证明上层 Python 算法相同。

- **opm-n1**: 叶函数/调用者类别冲突 period 29.4%；M-PY-INTERPRETER 79.1%, M-PY-TYPECHECK 16.1%, M-ZIP-COMPRESS 14.9%, M-PY-GC 8.6%, M-PY-CONTAINER 6.9%, M-PY-ALLOC 5.0%, M-PY-REFCOUNT 4.7%, M-ZIP-DECOMPRESS 0.9%
- **irs_w4-n1**: 叶函数/调用者类别冲突 period 32.0%；M-PY-INTERPRETER 74.1%, M-ZIP-COMPRESS 17.6%, M-PY-TYPECHECK 16.9%, M-PY-CONTAINER 11.2%, M-PY-GC 6.0%, M-PY-ALLOC 4.6%, M-PY-REFCOUNT 3.3%, M-ZIP-DECOMPRESS 1.0%
- **sba1919-n1**: 叶函数/调用者类别冲突 period 28.1%；M-PY-INTERPRETER 73.4%, M-ZIP-COMPRESS 16.6%, M-PY-TYPECHECK 11.9%, M-PY-CONTAINER 8.3%, M-PY-GC 4.7%, M-PY-ALLOC 3.8%, M-PY-REFCOUNT 2.6%, M-ZIP-DECOMPRESS 1.3%
- **opm-n10**: 叶函数/调用者类别冲突 period 31.1%；M-PY-INTERPRETER 81.1%, M-PY-TYPECHECK 20.4%, M-ZIP-COMPRESS 15.3%, M-PY-GC 7.0%, M-PY-CONTAINER 6.4%, M-PY-ALLOC 5.1%, M-PY-REFCOUNT 3.2%, M-ZIP-DECOMPRESS 1.3%
- **irs_w4-n10**: 叶函数/调用者类别冲突 period 33.3%；M-PY-INTERPRETER 80.8%, M-PY-TYPECHECK 25.2%, M-ZIP-COMPRESS 17.4%, M-PY-CONTAINER 7.7%, M-PY-GC 4.9%, M-PY-ALLOC 4.6%, M-PY-REFCOUNT 3.1%, M-ZIP-DECOMPRESS 1.1%
- **sba1919-n10**: 叶函数/调用者类别冲突 period 30.6%；M-PY-INTERPRETER 79.9%, M-ZIP-COMPRESS 17.2%, M-PY-TYPECHECK 14.5%, M-PY-CONTAINER 6.9%, M-PY-GC 4.3%, M-PY-ALLOC 3.2%, M-PY-REFCOUNT 2.5%, M-ZIP-DECOMPRESS 2.1%
- **tlc**: 叶函数/调用者类别冲突 period 29.5%；M-PY-INTERPRETER 87.1%, M-PY-GC 18.1%, M-PY-TYPECHECK 15.5%, M-PY-CONTAINER 14.4%, M-PY-ALLOC 6.2%, M-PY-REFCOUNT 4.9%, M-ZIP-COMPRESS 1.1%, M-ZIP-DECOMPRESS 0.6%
- **retail**: 叶函数/调用者类别冲突 period 24.7%；M-PY-INTERPRETER 76.4%, M-PY-TYPECHECK 17.3%, M-PY-CONTAINER 13.9%, M-PY-GC 11.4%, M-PY-ALLOC 5.7%, M-PY-REFCOUNT 4.9%, M-ZIP-DECOMPRESS 0.9%, M-ZIP-COMPRESS 0.5%
- **manufacturing**: 叶函数/调用者类别冲突 period 24.6%；M-PY-INTERPRETER 61.7%, M-PY-TYPECHECK 20.2%, M-PY-CONTAINER 16.1%, M-PY-GC 12.5%, M-PY-REFCOUNT 4.2%, M-PY-ALLOC 4.1%, M-ZIP-DECOMPRESS 1.1%, M-ZIP-COMPRESS 0.1%
- **hr**: 叶函数/调用者类别冲突 period 25.1%；M-PY-INTERPRETER 81.8%, M-PY-CONTAINER 15.9%, M-PY-TYPECHECK 13.9%, M-PY-GC 13.3%, M-PY-ALLOC 7.2%, M-PY-REFCOUNT 4.8%, M-ZIP-DECOMPRESS 1.4%, M-ZIP-COMPRESS 0.5%

monitor 线程 CPU 时间不参与上方 cycles 覆盖率或三层热点分母。与 cycles 进程份额的逐角色差异见 `processed/monitor-cycles-crosscheck.json`。

## 3. 库层热点（native period 加权，两次重复合并）

### opm-n1

| 库类 | period 份额 |
|---|---|
| libpython | 50.3% |
| zlib | 15.8% |
| pillow | 15.5% |
| poppler | 6.9% |
| libc | 4.0% |
| unknown | 3.1% |
| freetype | 2.8% |
| ld | 1.2% |
| other | 0.3% |
| fontconfig | 0.1% |

### irs_w4-n1

| 库类 | period 份额 |
|---|---|
| libpython | 48.5% |
| zlib | 18.6% |
| pillow | 16.9% |
| poppler | 5.5% |
| freetype | 3.8% |
| libc | 3.2% |
| unknown | 2.9% |
| ld | 0.5% |
| fontconfig | 0.1% |
| expat-xml | 0.0% |

### sba1919-n1

| 库类 | period 份额 |
|---|---|
| libpython | 44.6% |
| zlib | 17.9% |
| pillow | 17.7% |
| poppler | 9.3% |
| freetype | 5.1% |
| libc | 2.4% |
| unknown | 2.3% |
| ld | 0.4% |
| fontconfig | 0.1% |
| other | 0.1% |

### opm-n10

| 库类 | period 份额 |
|---|---|
| libpython | 48.5% |
| pillow | 17.0% |
| zlib | 16.5% |
| poppler | 8.6% |
| libc | 3.0% |
| freetype | 2.8% |
| unknown | 2.6% |
| ld | 0.4% |
| other | 0.2% |
| fontconfig | 0.2% |

### irs_w4-n10

| 库类 | period 份额 |
|---|---|
| libpython | 44.6% |
| pillow | 18.9% |
| zlib | 18.6% |
| poppler | 6.5% |
| freetype | 4.8% |
| libc | 3.1% |
| unknown | 2.7% |
| ld | 0.3% |
| other | 0.2% |
| fontconfig | 0.2% |

### sba1919-n10

| 库类 | period 份额 |
|---|---|
| libpython | 41.3% |
| pillow | 19.7% |
| zlib | 19.5% |
| poppler | 9.1% |
| freetype | 4.7% |
| unknown | 2.6% |
| libc | 2.4% |
| ld | 0.3% |
| other | 0.2% |
| python-ext | 0.1% |

### tlc

| 库类 | period 份额 |
|---|---|
| libpython | 78.4% |
| expat-xml | 5.9% |
| libreoffice | 5.4% |
| elementtree-xml | 3.1% |
| unknown | 2.1% |
| zlib | 1.7% |
| libc | 1.5% |
| other | 0.8% |
| ld | 0.4% |
| python-ext | 0.4% |

### retail

| 库类 | period 份额 |
|---|---|
| libpython | 70.2% |
| libreoffice | 12.3% |
| expat-xml | 5.3% |
| libc | 3.2% |
| unknown | 2.4% |
| elementtree-xml | 2.3% |
| other | 1.7% |
| zlib | 1.4% |
| ld | 0.6% |
| python-ext | 0.3% |

### manufacturing

| 库类 | period 份额 |
|---|---|
| libpython | 67.2% |
| libreoffice | 13.1% |
| other | 4.3% |
| unknown | 4.3% |
| expat-xml | 3.1% |
| libc | 2.2% |
| elementtree-xml | 2.1% |
| ld | 1.9% |
| zlib | 1.4% |
| fontconfig | 0.3% |

### hr

| 库类 | period 份额 |
|---|---|
| libpython | 73.9% |
| expat-xml | 5.5% |
| libreoffice | 5.4% |
| elementtree-xml | 3.6% |
| unknown | 3.4% |
| other | 2.5% |
| libc | 2.0% |
| zlib | 1.8% |
| ld | 1.3% |
| python-ext | 0.4% |

## 4. 采样点机制层（cycles:u period 权重；monitor CPU 时间不参与重加权）

互斥采样点机制只由叶函数和叶 DSO 决定；例如 libpython 中解释器、引用计数、GC、分配、容器和类型检查分别列出。调用栈较远的函数单独记为上下文，可能与叶机制冲突且相互重叠。已知运行时工作但无法恢复 Python 业务操作的样本仍计入原生机制，业务操作另列未知。py-spy 不分配到 cycles。

### 旧 joined-stack 分类器的影响诊断

本节把旧版‘叶函数+整条栈’规则重新套用到同一采样，仅量化分类改变，不参与当前覆盖率。以下比例是旧规则类别→叶函数规则类别的 ROI period。

| Dataset | 旧类别 → 叶函数类别 | period 权重 |
|---|---|---:|
| opm-n1 | M-PY-CONTAINER → M-PY-RUNTIME-OTHER | 9.6% |
| opm-n1 | M-PY-INTERPRETER → M-PY-RUNTIME-OTHER | 9.2% |
| opm-n1 | M-PY-GC → M-PY-RUNTIME-OTHER | 5.5% |
| opm-n1 | M-PY-REFCOUNT → M-PY-RUNTIME-OTHER | 2.7% |
| opm-n1 | M-PY-CONTAINER → M-PY-INTERPRETER | 2.1% |
| opm-n1 | M-ZIP-COMPRESS → M-ZIP-OPERATION-UNSPECIFIED | 1.9% |
| opm-n1 | M-PY-GC → M-PY-TYPECHECK | 1.6% |
| opm-n1 | M-PY-ALLOC → M-PY-RUNTIME-OTHER | 1.5% |
| opm-n1 | M-PY-GC → M-PY-ALLOC | 1.0% |
| opm-n1 | M-PY-CONTAINER → M-PY-TYPECHECK | 1.0% |
| opm-n1 | M-PY-GC → M-PY-CONTAINER | 0.2% |
| opm-n1 | M-PY-TYPECHECK → M-PY-RUNTIME-OTHER | 0.2% |
| opm-n1 | M-PY-GC → M-PY-REFCOUNT | 0.2% |
| opm-n1 | M-ZIP-DECOMPRESS → M-ZIP-OPERATION-UNSPECIFIED | 0.2% |
| opm-n1 | M-PY-ALLOC → M-PY-TYPECHECK | 0.1% |
| opm-n1 | M-PY-REFCOUNT → M-PY-CONTAINER | 0.1% |
| opm-n1 | M-PY-TYPECHECK → M-PY-INTERPRETER | 0.1% |
| opm-n1 | M-ZIP-COMPRESS → M-ZIP-DECOMPRESS | 0.1% |
| opm-n1 | M-PY-REFCOUNT → M-PY-ALLOC | 0.0% |
| opm-n1 | M-PY-REFCOUNT → M-PY-TYPECHECK | 0.0% |
| irs_w4-n1 | M-PY-CONTAINER → M-PY-RUNTIME-OTHER | 12.4% |
| irs_w4-n1 | M-PY-INTERPRETER → M-PY-RUNTIME-OTHER | 5.2% |
| irs_w4-n1 | M-PY-GC → M-PY-RUNTIME-OTHER | 3.7% |
| irs_w4-n1 | M-PY-CONTAINER → M-PY-INTERPRETER | 3.1% |
| irs_w4-n1 | M-ZIP-COMPRESS → M-ZIP-OPERATION-UNSPECIFIED | 2.2% |
| irs_w4-n1 | M-PY-ALLOC → M-PY-RUNTIME-OTHER | 1.7% |
| irs_w4-n1 | M-PY-REFCOUNT → M-PY-RUNTIME-OTHER | 1.6% |
| irs_w4-n1 | M-PY-CONTAINER → M-PY-TYPECHECK | 1.5% |
| irs_w4-n1 | M-PY-GC → M-PY-TYPECHECK | 1.3% |
| irs_w4-n1 | M-PY-GC → M-PY-ALLOC | 0.6% |
| irs_w4-n1 | M-ZIP-COMPRESS → M-ZIP-DECOMPRESS | 0.5% |
| irs_w4-n1 | M-PY-GC → M-PY-CONTAINER | 0.3% |
| irs_w4-n1 | M-PY-GC → M-PY-REFCOUNT | 0.1% |
| irs_w4-n1 | M-PY-ALLOC → M-PY-TYPECHECK | 0.1% |
| irs_w4-n1 | M-PY-REFCOUNT → M-PY-CONTAINER | 0.1% |
| irs_w4-n1 | M-PY-REFCOUNT → M-PY-ALLOC | 0.1% |
| irs_w4-n1 | M-PY-INTERPRETER → M-PY-TYPECHECK | 0.0% |
| irs_w4-n1 | M-ZIP-DECOMPRESS → M-ZIP-OPERATION-UNSPECIFIED | 0.0% |
| irs_w4-n1 | M-PY-TYPECHECK → M-PY-RUNTIME-OTHER | 0.0% |
| irs_w4-n1 | M-PY-TYPECHECK → M-PY-INTERPRETER | 0.0% |
| sba1919-n1 | M-PY-CONTAINER → M-PY-RUNTIME-OTHER | 10.0% |
| sba1919-n1 | M-PY-INTERPRETER → M-PY-RUNTIME-OTHER | 6.8% |
| sba1919-n1 | M-PY-GC → M-PY-RUNTIME-OTHER | 2.6% |
| sba1919-n1 | M-ZIP-COMPRESS → M-ZIP-OPERATION-UNSPECIFIED | 2.1% |
| sba1919-n1 | M-PY-CONTAINER → M-PY-INTERPRETER | 1.8% |
| sba1919-n1 | M-PY-ALLOC → M-PY-RUNTIME-OTHER | 1.5% |
| sba1919-n1 | M-PY-REFCOUNT → M-PY-RUNTIME-OTHER | 1.4% |
| sba1919-n1 | M-PY-GC → M-PY-TYPECHECK | 0.9% |
| sba1919-n1 | M-PY-CONTAINER → M-PY-TYPECHECK | 0.9% |
| sba1919-n1 | M-PY-GC → M-PY-ALLOC | 0.5% |
| sba1919-n1 | M-PY-GC → M-PY-CONTAINER | 0.2% |
| sba1919-n1 | M-ZIP-COMPRESS → M-ZIP-DECOMPRESS | 0.2% |
| sba1919-n1 | M-PY-GC → M-PY-REFCOUNT | 0.2% |
| sba1919-n1 | M-ZIP-DECOMPRESS → M-ZIP-OPERATION-UNSPECIFIED | 0.1% |
| sba1919-n1 | M-PY-TYPECHECK → M-PY-RUNTIME-OTHER | 0.1% |
| sba1919-n1 | M-PY-TYPECHECK → M-PY-INTERPRETER | 0.1% |
| sba1919-n1 | M-PY-REFCOUNT → M-PY-CONTAINER | 0.1% |
| sba1919-n1 | M-PY-REFCOUNT → M-PY-ALLOC | 0.1% |
| sba1919-n1 | M-PY-ALLOC → M-PY-TYPECHECK | 0.0% |
| opm-n10 | M-PY-CONTAINER → M-PY-RUNTIME-OTHER | 10.0% |
| opm-n10 | M-PY-INTERPRETER → M-PY-RUNTIME-OTHER | 7.7% |
| opm-n10 | M-PY-GC → M-PY-RUNTIME-OTHER | 4.5% |
| opm-n10 | M-PY-CONTAINER → M-PY-INTERPRETER | 3.1% |
| opm-n10 | M-PY-ALLOC → M-PY-RUNTIME-OTHER | 1.9% |
| opm-n10 | M-ZIP-COMPRESS → M-ZIP-OPERATION-UNSPECIFIED | 1.8% |
| opm-n10 | M-PY-REFCOUNT → M-PY-RUNTIME-OTHER | 1.5% |
| opm-n10 | M-PY-GC → M-PY-TYPECHECK | 1.3% |
| opm-n10 | M-PY-CONTAINER → M-PY-TYPECHECK | 1.2% |
| opm-n10 | M-PY-GC → M-PY-CONTAINER | 0.8% |
| opm-n10 | M-PY-GC → M-PY-ALLOC | 0.6% |
| opm-n10 | M-PY-TYPECHECK → M-PY-RUNTIME-OTHER | 0.2% |
| opm-n10 | M-ZIP-DECOMPRESS → M-ZIP-OPERATION-UNSPECIFIED | 0.1% |
| opm-n10 | M-PY-TYPECHECK → M-PY-INTERPRETER | 0.1% |
| opm-n10 | M-PY-REFCOUNT → M-PY-ALLOC | 0.1% |
| opm-n10 | M-PY-ALLOC → M-PY-TYPECHECK | 0.1% |
| opm-n10 | M-PY-REFCOUNT → M-PY-CONTAINER | 0.1% |
| opm-n10 | M-PY-GC → M-PY-REFCOUNT | 0.1% |
| opm-n10 | M-PY-INTERPRETER → M-PY-TYPECHECK | 0.1% |
| opm-n10 | M-ZIP-COMPRESS → M-ZIP-DECOMPRESS | 0.0% |
| irs_w4-n10 | M-PY-CONTAINER → M-PY-RUNTIME-OTHER | 12.1% |
| irs_w4-n10 | M-PY-CONTAINER → M-PY-INTERPRETER | 4.7% |
| irs_w4-n10 | M-PY-INTERPRETER → M-PY-RUNTIME-OTHER | 4.6% |
| irs_w4-n10 | M-PY-GC → M-PY-RUNTIME-OTHER | 3.3% |
| irs_w4-n10 | M-ZIP-COMPRESS → M-ZIP-OPERATION-UNSPECIFIED | 2.3% |
| irs_w4-n10 | M-PY-ALLOC → M-PY-RUNTIME-OTHER | 1.9% |
| irs_w4-n10 | M-PY-REFCOUNT → M-PY-RUNTIME-OTHER | 1.6% |
| irs_w4-n10 | M-PY-CONTAINER → M-PY-TYPECHECK | 1.0% |
| irs_w4-n10 | M-PY-GC → M-PY-TYPECHECK | 0.9% |
| irs_w4-n10 | M-PY-GC → M-PY-ALLOC | 0.7% |
| irs_w4-n10 | M-PY-GC → M-PY-CONTAINER | 0.3% |
| irs_w4-n10 | M-ZIP-COMPRESS → M-ZIP-DECOMPRESS | 0.2% |
| irs_w4-n10 | M-PY-GC → M-PY-REFCOUNT | 0.2% |
| irs_w4-n10 | M-PY-ALLOC → M-PY-TYPECHECK | 0.1% |
| irs_w4-n10 | M-ZIP-DECOMPRESS → M-ZIP-OPERATION-UNSPECIFIED | 0.1% |
| irs_w4-n10 | M-PY-TYPECHECK → M-PY-RUNTIME-OTHER | 0.1% |
| irs_w4-n10 | M-PY-TYPECHECK → M-PY-INTERPRETER | 0.1% |
| irs_w4-n10 | M-PY-REFCOUNT → M-PY-CONTAINER | 0.1% |
| sba1919-n10 | M-PY-CONTAINER → M-PY-RUNTIME-OTHER | 8.9% |
| sba1919-n10 | M-PY-INTERPRETER → M-PY-RUNTIME-OTHER | 6.6% |
| sba1919-n10 | M-PY-GC → M-PY-RUNTIME-OTHER | 2.8% |
| sba1919-n10 | M-PY-CONTAINER → M-PY-INTERPRETER | 2.6% |
| sba1919-n10 | M-ZIP-COMPRESS → M-ZIP-OPERATION-UNSPECIFIED | 2.5% |
| sba1919-n10 | M-PY-ALLOC → M-PY-RUNTIME-OTHER | 1.2% |
| sba1919-n10 | M-PY-REFCOUNT → M-PY-RUNTIME-OTHER | 1.1% |
| sba1919-n10 | M-PY-GC → M-PY-TYPECHECK | 0.9% |
| sba1919-n10 | M-PY-CONTAINER → M-PY-TYPECHECK | 0.7% |
| sba1919-n10 | M-PY-GC → M-PY-ALLOC | 0.5% |
| sba1919-n10 | M-ZIP-DECOMPRESS → M-ZIP-OPERATION-UNSPECIFIED | 0.2% |
| sba1919-n10 | M-PY-GC → M-PY-CONTAINER | 0.2% |
| sba1919-n10 | M-PY-TYPECHECK → M-PY-RUNTIME-OTHER | 0.2% |
| sba1919-n10 | M-PY-GC → M-PY-REFCOUNT | 0.1% |
| sba1919-n10 | M-ZIP-COMPRESS → M-ZIP-DECOMPRESS | 0.1% |
| sba1919-n10 | M-PY-REFCOUNT → M-PY-CONTAINER | 0.1% |
| sba1919-n10 | M-PY-TYPECHECK → M-PY-INTERPRETER | 0.0% |
| sba1919-n10 | M-PY-ALLOC → M-PY-TYPECHECK | 0.0% |
| sba1919-n10 | M-PY-INTERPRETER → M-PY-TYPECHECK | 0.0% |
| sba1919-n10 | M-PY-REFCOUNT → M-PY-ALLOC | 0.0% |
| sba1919-n10 | M-PY-REFCOUNT → M-PY-INTERPRETER | 0.0% |
| tlc | M-PY-CONTAINER → M-PY-RUNTIME-OTHER | 14.6% |
| tlc | M-PY-GC → M-PY-RUNTIME-OTHER | 9.8% |
| tlc | M-PY-INTERPRETER → M-PY-RUNTIME-OTHER | 9.4% |
| tlc | M-PY-GC → M-PY-TYPECHECK | 4.2% |
| tlc | M-PY-CONTAINER → M-PY-INTERPRETER | 3.6% |
| tlc | M-PY-REFCOUNT → M-PY-RUNTIME-OTHER | 2.5% |
| tlc | M-PY-ALLOC → M-PY-RUNTIME-OTHER | 2.1% |
| tlc | M-PY-GC → M-PY-ALLOC | 1.6% |
| tlc | M-PY-CONTAINER → M-PY-TYPECHECK | 1.5% |
| tlc | M-ZIP-COMPRESS → M-ZIP-DECOMPRESS | 0.6% |
| tlc | M-PY-GC → M-PY-CONTAINER | 0.4% |
| tlc | M-PY-GC → M-PY-REFCOUNT | 0.2% |
| tlc | M-PY-REFCOUNT → M-PY-CONTAINER | 0.2% |
| tlc | M-ZIP-COMPRESS → M-ZIP-OPERATION-UNSPECIFIED | 0.1% |
| tlc | M-PY-ALLOC → M-PY-TYPECHECK | 0.1% |
| tlc | M-PY-REFCOUNT → M-PY-ALLOC | 0.1% |
| tlc | M-PY-INTERPRETER → M-PY-TYPECHECK | 0.1% |
| tlc | M-PY-TYPECHECK → M-PY-RUNTIME-OTHER | 0.1% |
| tlc | M-PY-REFCOUNT → M-PY-TYPECHECK | 0.0% |
| retail | M-PY-CONTAINER → M-PY-RUNTIME-OTHER | 13.5% |
| retail | M-PY-INTERPRETER → M-PY-RUNTIME-OTHER | 9.2% |
| retail | M-PY-GC → M-PY-RUNTIME-OTHER | 7.2% |
| retail | M-PY-CONTAINER → M-PY-INTERPRETER | 5.0% |
| retail | M-PY-REFCOUNT → M-PY-RUNTIME-OTHER | 2.9% |
| retail | M-PY-ALLOC → M-PY-RUNTIME-OTHER | 2.3% |
| retail | M-PY-GC → M-PY-TYPECHECK | 1.9% |
| retail | M-PY-GC → M-PY-ALLOC | 1.5% |
| retail | M-PY-CONTAINER → M-PY-TYPECHECK | 1.4% |
| retail | M-ZIP-COMPRESS → M-ZIP-DECOMPRESS | 0.9% |
| retail | M-PY-GC → M-PY-CONTAINER | 0.4% |
| retail | M-PY-REFCOUNT → M-PY-CONTAINER | 0.2% |
| retail | M-PY-GC → M-PY-REFCOUNT | 0.2% |
| retail | M-PY-TYPECHECK → M-PY-RUNTIME-OTHER | 0.1% |
| retail | M-PY-ALLOC → M-PY-TYPECHECK | 0.1% |
| retail | M-PY-INTERPRETER → M-PY-TYPECHECK | 0.1% |
| retail | M-PY-REFCOUNT → M-PY-ALLOC | 0.1% |
| retail | M-ZIP-COMPRESS → M-ZIP-OPERATION-UNSPECIFIED | 0.0% |
| retail | M-PY-TYPECHECK → M-PY-INTERPRETER | 0.0% |
| manufacturing | M-PY-CONTAINER → M-PY-RUNTIME-OTHER | 14.2% |
| manufacturing | M-PY-GC → M-PY-RUNTIME-OTHER | 7.2% |
| manufacturing | M-PY-CONTAINER → M-PY-INTERPRETER | 6.6% |
| manufacturing | M-PY-INTERPRETER → M-PY-RUNTIME-OTHER | 6.0% |
| manufacturing | M-PY-CONTAINER → M-PY-TYPECHECK | 2.8% |
| manufacturing | M-PY-ALLOC → M-PY-RUNTIME-OTHER | 2.5% |
| manufacturing | M-PY-GC → M-PY-TYPECHECK | 2.0% |
| manufacturing | M-PY-REFCOUNT → M-PY-RUNTIME-OTHER | 1.3% |
| manufacturing | M-ZIP-COMPRESS → M-ZIP-DECOMPRESS | 1.1% |
| manufacturing | M-PY-GC → M-PY-REFCOUNT | 0.8% |
| manufacturing | M-PY-GC → M-PY-CONTAINER | 0.7% |
| manufacturing | M-PY-GC → M-PY-ALLOC | 0.5% |
| manufacturing | M-PY-REFCOUNT → M-PY-CONTAINER | 0.1% |
| manufacturing | M-PY-INTERPRETER → M-PY-TYPECHECK | 0.0% |
| manufacturing | M-PY-TYPECHECK → M-PY-RUNTIME-OTHER | 0.0% |
| hr | M-PY-CONTAINER → M-PY-RUNTIME-OTHER | 12.8% |
| hr | M-PY-INTERPRETER → M-PY-RUNTIME-OTHER | 10.2% |
| hr | M-PY-GC → M-PY-RUNTIME-OTHER | 8.2% |
| hr | M-PY-CONTAINER → M-PY-INTERPRETER | 3.0% |
| hr | M-PY-ALLOC → M-PY-RUNTIME-OTHER | 2.9% |
| hr | M-PY-REFCOUNT → M-PY-RUNTIME-OTHER | 2.6% |
| hr | M-PY-GC → M-PY-TYPECHECK | 2.4% |
| hr | M-PY-GC → M-PY-ALLOC | 1.9% |
| hr | M-ZIP-COMPRESS → M-ZIP-DECOMPRESS | 1.3% |
| hr | M-PY-CONTAINER → M-PY-TYPECHECK | 1.2% |
| hr | M-PY-GC → M-PY-CONTAINER | 0.3% |
| hr | M-PY-GC → M-PY-REFCOUNT | 0.2% |
| hr | M-PY-TYPECHECK → M-PY-RUNTIME-OTHER | 0.1% |
| hr | M-PY-REFCOUNT → M-PY-ALLOC | 0.1% |
| hr | M-PY-INTERPRETER → M-PY-TYPECHECK | 0.1% |
| hr | M-PY-REFCOUNT → M-PY-CONTAINER | 0.1% |
| hr | M-ZIP-COMPRESS → M-ZIP-OPERATION-UNSPECIFIED | 0.1% |
| hr | M-PY-ALLOC → M-PY-TYPECHECK | 0.0% |

### 栈前缀匹配质量

指纹最多取前 8 帧，至少 4 帧且没有未知符号/DSO 才参与匹配；符号去掉偏移，DSO 归并为类别，同地址内联帧使用实体帧类别。短栈、未知帧不匹配。截断会忽略更深调用者，DSO 类别会合并不同具体库；相等只表示规范化前缀相等，不表示完整路径或代码身份。

| Dataset | 可用于栈前缀匹配的 period 份额 |
|---|---:|
| opm-n1 | 88.0% |
| irs_w4-n1 | 86.7% |
| sba1919-n1 | 88.9% |
| opm-n10 | 88.2% |
| irs_w4-n10 | 86.5% |
| sba1919-n10 | 90.1% |
| tlc | 92.8% |
| retail | 88.5% |
| manufacturing | 81.7% |
| hr | 87.2% |

| 配置 | M-IMAGE-PROCESS | M-LIBC-PRIMITIVE | M-LIBREOFFICE-NATIVE | M-NATIVE-OTHER-UNSPECIFIED | M-PDF-NATIVE-OTHER | M-PDF-RASTER | M-PY-ALLOC | M-PY-CONTAINER | M-PY-GC | M-PY-INTERPRETER | M-PY-REFCOUNT | M-PY-RUNTIME-OTHER | M-PY-TYPECHECK | M-PYTHON-EXTENSION-OTHER | M-UNCLASSIFIED | M-XML-PARSE | M-ZIP-COMPRESS | M-ZIP-DECOMPRESS | M-ZIP-OPERATION-UNSPECIFIED |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| opm-n1 | 15.5% | 3.4% | 0.0% | 1.9% | 0.0% | 9.7% | 2.8% | 1.0% | 2.0% | 7.9% | 3.8% | 29.3% | 3.5% | 0.0% | 3.3% | 0.0% | 12.9% | 0.8% | 2.1% |
| irs_w4-n1 | 16.9% | 2.4% | 0.0% | 1.3% | 0.0% | 9.3% | 2.6% | 1.4% | 1.8% | 6.4% | 2.8% | 29.9% | 3.5% | 0.0% | 3.0% | 0.0% | 15.5% | 0.9% | 2.2% |
| sba1919-n1 | 17.7% | 2.1% | 0.0% | 0.8% | 0.0% | 14.4% | 2.1% | 1.1% | 1.6% | 8.5% | 2.5% | 26.5% | 2.3% | 0.0% | 2.5% | 0.0% | 14.4% | 1.2% | 2.3% |
| opm-n10 | 17.0% | 2.5% | 0.0% | 1.1% | 0.0% | 11.4% | 2.7% | 1.8% | 1.8% | 9.9% | 3.0% | 26.1% | 3.1% | 0.0% | 2.9% | 0.1% | 13.5% | 1.1% | 1.9% |
| irs_w4-n10 | 18.9% | 2.4% | 0.0% | 1.1% | 0.0% | 11.2% | 2.4% | 1.4% | 1.5% | 8.9% | 3.4% | 24.7% | 2.4% | 0.1% | 3.1% | 0.0% | 15.1% | 1.1% | 2.5% |
| sba1919-n10 | 19.7% | 2.0% | 0.0% | 0.9% | 0.0% | 13.9% | 1.7% | 1.2% | 1.4% | 10.6% | 2.7% | 21.5% | 2.2% | 0.1% | 2.8% | 0.0% | 14.7% | 2.0% | 2.7% |
| tlc | 0.0% | 1.1% | 5.4% | 1.5% | 0.0% | 0.0% | 4.5% | 2.2% | 6.2% | 14.0% | 5.9% | 38.4% | 7.3% | 0.4% | 2.1% | 9.3% | 1.0% | 0.6% | 0.2% |
| retail | 0.0% | 2.9% | 12.3% | 2.0% | 0.0% | 0.0% | 4.0% | 2.7% | 3.7% | 14.7% | 4.7% | 35.7% | 4.6% | 0.3% | 3.1% | 7.7% | 0.4% | 0.9% | 0.1% |
| manufacturing | 0.0% | 1.3% | 13.1% | 4.7% | 0.0% | 0.0% | 3.0% | 2.1% | 4.5% | 12.1% | 5.0% | 34.7% | 5.9% | 0.1% | 6.9% | 5.2% | 0.1% | 1.2% | 0.1% |
| hr | 0.0% | 1.2% | 5.4% | 3.2% | 0.0% | 0.0% | 5.3% | 2.4% | 4.7% | 13.5% | 5.2% | 37.8% | 4.9% | 0.4% | 5.0% | 9.2% | 0.4% | 1.3% | 0.1% |

## 5. 函数/调用栈层（要点，完整表在 processed/）

### opm-n1

- **r1**（ROI 2194 样本，46.3G cycles 近似）：
  - `pdf-convert` / zlib / `longest_match` — 7.1%
  - `pdf-convert` / pillow / `ImagingResampleHorizontal_8bpc` — 6.6%
  - `pdf-convert` / zlib / `deflate_slow` — 4.4%
  - `pdf-convert` / pillow / `ImagingZipEncode` — 3.8%
  - `pdf-convert` / pillow / `ImagingResampleVertical_8bpc` — 2.6%
  - `pdf-verify` / libpython / `_PyEval_EvalFrameDefault` — 2.4%
  - `pdf-fill` / libpython / `_PyEval_EvalFrameDefault` — 1.6%
  - `pdf-fill` / libpython / `_PyEval_EvalFrameDefault` — 1.5%
- **r2**（ROI 2257 样本，48.5G cycles 近似）：
  - `pdf-convert` / zlib / `longest_match` — 8.0%
  - `pdf-convert` / pillow / `ImagingResampleHorizontal_8bpc` — 7.0%
  - `pdf-convert` / zlib / `deflate_slow` — 4.1%
  - `pdf-convert` / pillow / `ImagingZipEncode` — 4.0%
  - `pdf-convert` / pillow / `ImagingResampleVertical_8bpc` — 2.9%
  - `pdf-convert` / zlib / `slide_hash` — 2.0%
  - `pdf-verify` / libpython / `_PyEval_EvalFrameDefault` — 2.0%
  - `pdf-convert` / libc / `__memcpy_generic` — 1.9%
- py-spy Python 层主要脚本：`pdf-convert` 47.4%，`pdf-fill` 19.8%，`pdf-verify` 14.1%，`pdf-extract-fields` 9.0%，`pdf-check-fillable` 8.9%，`runner` 0.5%

### irs_w4-n1

- **r1**（ROI 2980 样本，67.4G cycles 近似）：
  - `pdf-convert` / zlib / `longest_match` — 7.6%
  - `pdf-convert` / zlib / `deflate_slow` — 6.6%
  - `pdf-convert` / pillow / `ImagingResampleHorizontal_8bpc` — 6.6%
  - `pdf-convert` / pillow / `ImagingZipEncode` — 4.6%
  - `pdf-convert` / pillow / `ImagingResampleVertical_8bpc` — 4.2%
  - `pdftoppm` / poppler / `Splash::compositeBackground(unsigned char const*)` — 2.5%
  - `pdf-fill` / libpython / `_PyEval_EvalFrameDefault` — 2.4%
  - `pdf-convert` / zlib / `slide_hash` — 1.7%
- **r2**（ROI 2860 样本，66.0G cycles 近似）：
  - `pdf-convert` / zlib / `longest_match` — 9.4%
  - `pdf-convert` / pillow / `ImagingResampleHorizontal_8bpc` — 7.3%
  - `pdf-convert` / zlib / `deflate_slow` — 5.9%
  - `pdf-convert` / pillow / `ImagingZipEncode` — 4.9%
  - `pdf-convert` / pillow / `ImagingResampleVertical_8bpc` — 3.5%
  - `pdf-fill` / libpython / `_PyEval_EvalFrameDefault` — 2.0%
  - `pdftoppm` / poppler / `Splash::compositeBackground(unsigned char const*)` — 1.9%
  - `pdf-convert` / zlib / `slide_hash` — 1.7%
- py-spy Python 层主要脚本：`pdf-convert` 47.6%，`pdf-verify` 26.5%，`pdf-fill` 19.5%，`pdf-check-fillable` 2.9%，`pdf-extract-fields` 2.4%，`runner` 0.9%

### sba1919-n1

- **r1**（ROI 3407 样本，91.8G cycles 近似）：
  - `pdf-convert` / zlib / `longest_match` — 8.0%
  - `pdf-convert` / pillow / `ImagingResampleHorizontal_8bpc` — 8.0%
  - `pdf-convert` / zlib / `deflate_slow` — 5.7%
  - `pdf-convert` / pillow / `ImagingZipEncode` — 4.9%
  - `pdf-convert` / pillow / `ImagingResampleVertical_8bpc` — 3.4%
  - `pdf-verify` / libpython / `_PyEval_EvalFrameDefault` — 3.4%
  - `pdftoppm` / poppler / `Splash::pipeRunAARGB8(SplashPipe*)` — 3.0%
  - `pdftoppm` / poppler / `Splash::compositeBackground(unsigned char const*)` — 2.3%
- **r2**（ROI 3962 样本，95.7G cycles 近似）：
  - `pdf-convert` / zlib / `longest_match` — 7.9%
  - `pdf-convert` / pillow / `ImagingResampleHorizontal_8bpc` — 7.7%
  - `pdf-convert` / zlib / `deflate_slow` — 5.8%
  - `pdf-convert` / pillow / `ImagingZipEncode` — 3.9%
  - `pdf-convert` / pillow / `ImagingResampleVertical_8bpc` — 3.2%
  - `pdf-verify` / libpython / `_PyEval_EvalFrameDefault` — 3.2%
  - `pdftoppm` / poppler / `Splash::pipeRunAARGB8(SplashPipe*)` — 2.9%
  - `pdftoppm` / poppler / `Splash::compositeBackground(unsigned char const*)` — 1.8%
- py-spy Python 层主要脚本：`pdf-convert` 46.0%，`pdf-verify` 28.9%，`pdf-fill` 15.3%，`pdf-extract-fields` 5.2%，`pdf-check-fillable` 4.0%，`runner` 0.4%

### opm-n10

- **r1**（ROI 3212 样本，76.2G cycles 近似）：
  - `pdf-convert` / zlib / `longest_match` — 8.0%
  - `pdf-convert` / pillow / `ImagingResampleHorizontal_8bpc` — 6.8%
  - `pdf-convert` / zlib / `deflate_slow` — 4.7%
  - `pdf-convert` / pillow / `ImagingZipEncode` — 4.1%
  - `pdf-verify` / libpython / `_PyEval_EvalFrameDefault` — 3.2%
  - `pdf-convert` / pillow / `ImagingResampleVertical_8bpc` — 3.1%
  - `pdf-fill` / libpython / `_PyEval_EvalFrameDefault` — 2.9%
  - `pdf-fill` / libpython / `_PyEval_EvalFrameDefault` — 2.9%
- **r2**（ROI 3201 样本，79.4G cycles 近似）：
  - `pdf-convert` / pillow / `ImagingResampleHorizontal_8bpc` — 7.4%
  - `pdf-convert` / zlib / `longest_match` — 7.3%
  - `pdf-convert` / zlib / `deflate_slow` — 5.0%
  - `pdf-convert` / pillow / `ImagingZipEncode` — 4.2%
  - `pdf-convert` / pillow / `ImagingResampleVertical_8bpc` — 3.4%
  - `pdf-verify` / libpython / `_PyEval_EvalFrameDefault` — 3.0%
  - `pdf-fill` / libpython / `_PyEval_EvalFrameDefault` — 2.4%
  - `pdf-fill` / libpython / `_PyEval_EvalFrameDefault` — 2.2%
- py-spy Python 层主要脚本：`pdf-convert` 45.3%，`pdf-fill` 38.6%，`pdf-verify` 12.9%，`pdf-check-fillable` 1.6%，`pdf-extract-fields` 1.1%，`runner` 0.3%

### irs_w4-n10

- **r1**（ROI 3991 样本，108.3G cycles 近似）：
  - `pdf-convert` / zlib / `longest_match` — 7.5%
  - `pdf-convert` / pillow / `ImagingResampleHorizontal_8bpc` — 7.2%
  - `pdf-convert` / zlib / `deflate_slow` — 5.6%
  - `pdf-convert` / pillow / `ImagingZipEncode` — 5.3%
  - `pdf-fill` / libpython / `_PyEval_EvalFrameDefault` — 5.0%
  - `pdf-convert` / pillow / `ImagingResampleVertical_8bpc` — 3.1%
  - `pdftoppm` / poppler / `Splash::compositeBackground(unsigned char const*)` — 2.5%
  - `pdf-verify` / libpython / `_PyEval_EvalFrameDefault` — 2.2%
- **r2**（ROI 3919 样本，102.6G cycles 近似）：
  - `pdf-convert` / zlib / `longest_match` — 9.6%
  - `pdf-convert` / pillow / `ImagingResampleHorizontal_8bpc` — 8.2%
  - `pdf-convert` / zlib / `deflate_slow` — 5.3%
  - `pdf-convert` / pillow / `ImagingZipEncode` — 5.0%
  - `pdf-convert` / pillow / `ImagingResampleVertical_8bpc` — 3.8%
  - `pdf-fill` / libpython / `_PyEval_EvalFrameDefault` — 3.4%
  - `pdf-convert` / zlib / `slide_hash` — 2.1%
  - `pdftoppm` / poppler / `Splash::compositeBackground(unsigned char const*)` — 1.9%
- py-spy Python 层主要脚本：`pdf-convert` 48.0%，`pdf-fill` 35.5%，`pdf-verify` 14.6%，`pdf-check-fillable` 0.7%，`pdf-extract-fields` 0.5%，`pdf-mapping-driver` 0.4%

### sba1919-n10

- **r1**（ROI 5753 样本，152.4G cycles 近似）：
  - `pdf-convert` / zlib / `longest_match` — 8.1%
  - `pdf-convert` / pillow / `ImagingResampleHorizontal_8bpc` — 7.1%
  - `pdf-convert` / zlib / `deflate_slow` — 6.3%
  - `pdf-convert` / pillow / `ImagingZipEncode` — 4.8%
  - `pdf-verify` / libpython / `_PyEval_EvalFrameDefault` — 4.7%
  - `pdf-convert` / pillow / `ImagingResampleVertical_8bpc` — 3.7%
  - `pdftoppm` / poppler / `Splash::pipeRunAARGB8(SplashPipe*)` — 2.9%
  - `pdf-fill` / libpython / `_PyEval_EvalFrameDefault` — 2.5%
- **r2**（ROI 6177 样本，156.5G cycles 近似）：
  - `pdf-convert` / zlib / `longest_match` — 7.9%
  - `pdf-convert` / pillow / `ImagingResampleHorizontal_8bpc` — 7.6%
  - `pdf-convert` / zlib / `deflate_slow` — 5.3%
  - `pdf-convert` / pillow / `ImagingZipEncode` — 4.8%
  - `pdf-verify` / libpython / `_PyEval_EvalFrameDefault` — 4.6%
  - `pdf-convert` / pillow / `ImagingResampleVertical_8bpc` — 3.8%
  - `pdftoppm` / poppler / `Splash::pipeRunAARGB8(SplashPipe*)` — 3.0%
  - `pdf-fill` / libpython / `_PyEval_EvalFrameDefault` — 2.6%
- py-spy Python 层主要脚本：`pdf-convert` 46.9%，`pdf-fill` 28.0%，`pdf-verify` 22.2%，`pdf-check-fillable` 1.3%，`pdf-extract-fields` 1.0%，`pdf-mapping-driver` 0.3%

### tlc

- **r1**（ROI 37327 样本，699.6G cycles 近似）：
  - `xlsx-enhance` / libpython / `_PyEval_EvalFrameDefault` — 3.2%
  - `xlsx-recalc` / libpython / `_PyEval_EvalFrameDefault` — 1.7%
  - `xlsx-inspect-structure` / libpython / `_PyEval_EvalFrameDefault` — 1.4%
  - `xlsx-inspect-structure` / libpython / `dictiter_iternextkey` — 1.2%
  - `xlsx-inspect-features` / libpython / `_PyEval_EvalFrameDefault` — 1.0%
  - `xlsx-verify` / libpython / `_PyEval_EvalFrameDefault` — 1.0%
  - `xlsx-enhance` / libpython / `Py_INCREF` — 0.9%
  - `xlsx-inspect-cached` / libpython / `_PyEval_EvalFrameDefault` — 0.8%
- **r2**（ROI 36295 样本，692.6G cycles 近似）：
  - `xlsx-enhance` / libpython / `_PyEval_EvalFrameDefault` — 2.9%
  - `xlsx-recalc` / libpython / `_PyEval_EvalFrameDefault` — 1.8%
  - `xlsx-inspect-structure` / libpython / `_PyEval_EvalFrameDefault` — 1.6%
  - `xlsx-enhance` / libpython / `Py_INCREF` — 1.1%
  - `xlsx-verify` / libpython / `_PyEval_EvalFrameDefault` — 1.0%
  - `xlsx-inspect-features` / libpython / `_PyEval_EvalFrameDefault` — 0.9%
  - `xlsx-inspect-formulas` / libpython / `_PyEval_EvalFrameDefault` — 0.8%
  - `xlsx-inspect-cached` / libpython / `_PyEval_EvalFrameDefault` — 0.7%
- py-spy Python 层主要脚本：`xlsx-enhance` 24.0%，`xlsx-inspect-structure` 13.5%，`xlsx-recalc` 13.2%，`xlsx-inspect-features` 11.3%，`xlsx-verify` 10.9%，`xlsx-inspect-formulas` 8.9%

### retail

- **r1**（ROI 327607 样本，149.6G cycles 近似）：
  - `xlsx-verify` / libpython / `_PyEval_EvalFrameDefault` — 5.9%
  - `soffice.bin` / libreoffice / `std::_Rb_tree<int, int, std::_Identity<int>, std::less<int>, std::allocator<int> >::_M_get_insert_unique_pos(int const&)` — 2.5%
  - `xlsx-enhance` / libpython / `_PyEval_EvalFrameDefault` — 2.1%
  - `xlsx-inspect-tool` / libpython / `_PyEval_EvalFrameDefault` — 2.1%
  - `xlsx-verify` / libpython / `_PyEval_EvalFrameDefault` — 2.0%
  - `xlsx-verify` / libpython / `Py_INCREF` — 1.1%
  - `soffice.bin` / libc / `_int_free` — 1.0%
  - `soffice.bin` / libreoffice / `XclExpRowBuffer::GetOrCreateRow(unsigned int, bool)` — 0.9%
- **r2**（ROI 341303 样本，142.6G cycles 近似）：
  - `xlsx-verify` / libpython / `_PyEval_EvalFrameDefault` — 4.1%
  - `xlsx-inspect-tool` / libpython / `_PyEval_EvalFrameDefault` — 3.0%
  - `soffice.bin` / libreoffice / `std::_Rb_tree<int, int, std::_Identity<int>, std::less<int>, std::allocator<int> >::_M_get_insert_unique_pos(int const&)` — 2.5%
  - `xlsx-enhance` / libpython / `_PyEval_EvalFrameDefault` — 1.3%
  - `xlsx-verify` / libpython / `_PyEval_EvalFrameDefault` — 1.3%
  - `xlsx-inspect-tool` / libpython / `_PyEval_EvalFrameDefault` — 1.2%
  - `soffice.bin` / libc / `_int_free` — 1.0%
  - `xlsx-verify` / libpython / `Py_INCREF` — 1.0%
- py-spy Python 层主要脚本：`xlsx-verify` 46.1%，`xlsx-inspect-tool` 21.2%，`xlsx-enhance` 14.1%，`xlsx-recalc` 8.7%，`xlsx-summary-export` 8.0%，`runner` 1.8%

### manufacturing

- **r1**（ROI 182542 样本，80.8G cycles 近似）：
  - `xlsx-verify` / libpython / `_PyEval_EvalFrameDefault` — 3.7%
  - `xlsx-verify` / libpython / `_PyEval_EvalFrameDefault` — 3.0%
  - `xlsx-summary-export` / libpython / `_PyEval_EvalFrameDefault` — 2.2%
  - `xlsx-inspect-tool` / libpython / `_PyGCHead_NEXT` — 1.5%
  - `soffice.bin` / other / `[unknown]` — 1.3%
  - `soffice.bin` / ld / `do_lookup_x` — 1.2%
  - `xlsx-recalc` / libpython / `_PyEval_EvalFrameDefault` — 1.1%
  - `xlsx-verify` / unknown / `translate_newlines` — 1.0%
- **r2**（ROI 167715 样本，79.3G cycles 近似）：
  - `xlsx-verify` / libpython / `_PyEval_EvalFrameDefault` — 3.6%
  - `xlsx-verify` / libpython / `_PyEval_EvalFrameDefault` — 2.0%
  - `xlsx-enhance` / libpython / `_PyEval_EvalFrameDefault` — 1.2%
  - `soffice.bin` / libreoffice / `XclTools::GetXclColumnWidth(unsigned short, long)` — 1.2%
  - `xlsx-verify` / libpython / `_PyObject_GC_TRACK` — 1.2%
  - `xlsx-verify` / libpython / `Py_DECREF` — 1.1%
  - `xlsx-enhance` / libpython / `_Py_dict_lookup` — 1.0%
  - `xlsx-verify` / libpython / `tok_get` — 1.0%
- py-spy Python 层主要脚本：`xlsx-verify` 46.6%，`xlsx-inspect-tool` 22.3%，`xlsx-summary-export` 12.0%，`xlsx-enhance` 11.4%，`xlsx-recalc` 6.7%，`runner` 1.0%

### hr

- **r1**（ROI 89613 样本，148.3G cycles 近似）：
  - `xlsx-verify` / libpython / `_PyEval_EvalFrameDefault` — 4.4%
  - `xlsx-enhance` / libpython / `_PyEval_EvalFrameDefault` — 2.1%
  - `xlsx-verify` / libpython / `_PyEval_EvalFrameDefault` — 1.6%
  - `xlsx-inspect-tool` / libpython / `_PyEval_EvalFrameDefault` — 1.6%
  - `xlsx-verify` / libpython / `Py_INCREF` — 0.9%
  - `xlsx-recalc` / libpython / `_PyEval_EvalFrameDefault` — 0.8%
  - `xlsx-inspect-tool` / libpython / `PyObject_GetItem` — 0.7%
  - `xlsx-verify` / libpython / `_PyEval_EvalFrameDefault` — 0.7%
- **r2**（ROI 97838 样本，150.1G cycles 近似）：
  - `xlsx-verify` / libpython / `_PyEval_EvalFrameDefault` — 5.0%
  - `xlsx-recalc` / libpython / `_PyEval_EvalFrameDefault` — 2.0%
  - `xlsx-inspect-tool` / libpython / `_PyEval_EvalFrameDefault` — 1.7%
  - `xlsx-enhance` / libpython / `_PyEval_EvalFrameDefault` — 1.6%
  - `xlsx-summary-export` / libpython / `_PyEval_EvalFrameDefault` — 0.8%
  - `xlsx-verify` / libpython / `Py_INCREF` — 0.8%
  - `soffice.bin` / other / `[unknown]` — 0.7%
  - `soffice.bin` / ld / `do_lookup_x` — 0.7%
- py-spy Python 层主要脚本：`xlsx-verify` 44.6%，`xlsx-inspect-tool` 24.8%，`xlsx-enhance` 12.9%，`xlsx-recalc` 8.8%，`xlsx-summary-export` 8.8%

## 6. 热点分类（单项 ≥0.5% ROI；逐次匹配后按 period 合并）

已覆盖机制热点、旧脚本执行路径内的机制未知热点、未覆盖路径、候选机制和未知项分开列示；“热点”不自动表示新增机制。各次重复权重在 JSON 中保留。

### opm-n1

| 进程/脚本 | DSO | 叶函数/实体 / 代表栈 | 合并权重 | r1 / r2 | 直接路径部分 | 采样点机制 | 调用上下文（可重叠） | 栈前缀匹配权重 | 分类 |
|---|---|---|---:|---:|---:|---|---|---:|---|
| `pdf-convert` | /usr/lib64/libz.so.1.2.13 | `longest_match` / `longest_match`; `longest_match [/usr/lib64/libz.so.1.2.13]; deflate_slow [/usr/lib64/libz.so.1.2.13]; deflate [/usr/lib64/libz.so.1.2.13]; ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]` | 7.5% | 7.1% / 8.0% | 7.5% | M-ZIP-COMPRESS | M-PY-INTERPRETER, M-ZIP-COMPRESS | 7.5% | old-selected-execution-path-hotspot |
| `pdf-convert` | /opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so | `ImagingResampleHorizontal_8bpc` / `ImagingResampleHorizontal_8bpc`; `ImagingResampleHorizontal_8bpc [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; ImagingResampleInner [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _resize [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 6.8% | 6.6% / 7.0% | 6.8% | M-IMAGE-PROCESS | M-PY-INTERPRETER | 6.8% | old-selected-execution-path-hotspot |
| `pdf-convert` | /usr/lib64/libz.so.1.2.13 | `deflate_slow` / `deflate_slow`; `deflate_slow [/usr/lib64/libz.so.1.2.13]; deflate [/usr/lib64/libz.so.1.2.13]; ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _encode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]` | 4.2% | 4.4% / 4.1% | 4.2% | M-ZIP-COMPRESS | M-PY-INTERPRETER, M-ZIP-COMPRESS | 4.2% | old-selected-execution-path-hotspot |
| `pdf-convert` | /opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so | `ImagingZipEncode` / `ImagingZipEncode`; `ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _encode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_VectorcallTstate [inlined]` | 3.9% | 3.8% / 4.0% | 3.9% | M-IMAGE-PROCESS | M-PY-INTERPRETER | 3.9% | old-selected-execution-path-hotspot |
| `pdf-convert` | /opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so | `ImagingResampleVertical_8bpc` / `ImagingResampleVertical_8bpc`; `ImagingResampleVertical_8bpc [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; ImagingResampleInner [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _resize [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 2.8% | 2.6% / 2.9% | 2.8% | M-IMAGE-PROCESS | M-PY-INTERPRETER | 2.8% | old-selected-execution-path-hotspot |
| `pdf-verify` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyEval_EvalFrame [inlined]; gen_send_ex2 [inlined]; gen_iternext [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 2.2% | 2.4% / 2.0% | 2.2% | M-PY-INTERPRETER | M-PY-INTERPRETER | 2.2% | old-selected-execution-path-hotspot |
| `pdftoppm` | /usr/lib64/libpoppler.so.133.0.0 | `Splash::compositeBackground(unsigned char const*)` / `Splash::compositeBackground(unsigned char const*)`; `Splash::compositeBackground(unsigned char const*) [/usr/lib64/libpoppler.so.133.0.0]; Gfx::~Gfx() [/usr/lib64/libpoppler.so.133.0.0]; Page::displaySlice(OutputDev*, double, double, int, bool, bool, int, int, int, int, bool, bool (*)(void*), void*, bool (*)(Annot*, void*), void*, bool) [/usr/lib64/libpoppler.so.133.0.0]; main [/usr/bin/pdftoppm]` | 1.7% | 1.6% / 1.7% | 1.6% | M-PDF-RASTER | — | 0.0% | old-selected-execution-path-hotspot |
| `pdf-fill` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_FastCallDictTstate [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_Call_Prepend [inlined]; slot_tp_init [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.5% | 1.6% / 1.4% | 1.5% | M-PY-INTERPRETER | M-PY-INTERPRETER, M-PY-TYPECHECK | 1.0% | old-selected-execution-path-hotspot |
| `pdf-fill` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.4% | 1.5% / 1.3% | 1.4% | M-PY-INTERPRETER | M-PY-INTERPRETER | 1.4% | old-selected-execution-path-hotspot |
| `pdf-convert` | /usr/lib64/libz.so.1.2.13 | `slide_hash` / `slide_hash`; `slide_hash [/usr/lib64/libz.so.1.2.13]; fill_window [/usr/lib64/libz.so.1.2.13]; deflate_slow [/usr/lib64/libz.so.1.2.13]; deflate [/usr/lib64/libz.so.1.2.13]` | 1.4% | 0.7% / 2.0% | 1.4% | M-ZIP-OPERATION-UNSPECIFIED | M-PY-INTERPRETER, M-ZIP-COMPRESS | 1.4% | old-selected-execution-path-hotspot |
| `pdftoppm` | /usr/lib64/libpoppler.so.133.0.0 | `Splash::pipeRunAARGB8(SplashPipe*)` / `Splash::pipeRunAARGB8(SplashPipe*)`; `Splash::pipeRunAARGB8(SplashPipe*) [/usr/lib64/libpoppler.so.133.0.0]; Splash::fillGlyph2(int, int, SplashGlyphBitmap*, bool) [/usr/lib64/libpoppler.so.133.0.0]; Splash::fillChar(double, double, int, SplashFont*) [/usr/lib64/libpoppler.so.133.0.0]; SplashOutputDev::drawChar(GfxState*, double, double, double, double, double, double, unsigned int, int, unsigned int const*, int) [/usr/lib64/libpoppler.so.133.0.0]` | 1.3% | 1.9% / 0.8% | 1.1% | M-PDF-RASTER | — | 1.3% | old-selected-execution-path-hotspot |
| `pdf-convert` | /usr/lib64/libc.so.6 | `__memcpy_generic` / `__memcpy_generic`; `__memcpy_generic [/usr/lib64/libc.so.6]; PyBytes_FromStringAndSize [inlined]; read_bytes [inlined]; _io_BytesIO_read_impl [inlined]` | 1.2% | 0.5% / 1.9% | 1.2% | M-LIBC-PRIMITIVE | M-PY-INTERPRETER | 1.0% | old-selected-execution-path-hotspot |

### irs_w4-n1

| 进程/脚本 | DSO | 叶函数/实体 / 代表栈 | 合并权重 | r1 / r2 | 直接路径部分 | 采样点机制 | 调用上下文（可重叠） | 栈前缀匹配权重 | 分类 |
|---|---|---|---:|---:|---:|---|---|---:|---|
| `pdf-convert` | /usr/lib64/libz.so.1.2.13 | `longest_match` / `longest_match`; `longest_match [/usr/lib64/libz.so.1.2.13]; deflate_slow [/usr/lib64/libz.so.1.2.13]; deflate [/usr/lib64/libz.so.1.2.13]; ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]` | 8.5% | 7.6% / 9.4% | 8.5% | M-ZIP-COMPRESS | M-PY-INTERPRETER, M-ZIP-COMPRESS | 8.5% | old-selected-execution-path-hotspot |
| `pdf-convert` | /opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so | `ImagingResampleHorizontal_8bpc` / `ImagingResampleHorizontal_8bpc`; `ImagingResampleHorizontal_8bpc [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; ImagingResampleInner [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _resize [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 6.9% | 6.6% / 7.3% | 6.9% | M-IMAGE-PROCESS | M-PY-INTERPRETER | 6.9% | old-selected-execution-path-hotspot |
| `pdf-convert` | /usr/lib64/libz.so.1.2.13 | `deflate_slow` / `deflate_slow`; `deflate_slow [/usr/lib64/libz.so.1.2.13]; deflate [/usr/lib64/libz.so.1.2.13]; ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _encode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]` | 6.2% | 6.6% / 5.9% | 6.2% | M-ZIP-COMPRESS | M-PY-INTERPRETER, M-ZIP-COMPRESS | 6.2% | old-selected-execution-path-hotspot |
| `pdf-convert` | /opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so | `ImagingZipEncode` / `ImagingZipEncode`; `ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _encode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_VectorcallTstate [inlined]` | 4.8% | 4.6% / 4.9% | 4.8% | M-IMAGE-PROCESS | M-PY-INTERPRETER | 4.8% | old-selected-execution-path-hotspot |
| `pdf-convert` | /opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so | `ImagingResampleVertical_8bpc` / `ImagingResampleVertical_8bpc`; `ImagingResampleVertical_8bpc [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; ImagingResampleInner [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _resize [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 3.9% | 4.2% / 3.5% | 3.9% | M-IMAGE-PROCESS | M-PY-INTERPRETER | 3.9% | old-selected-execution-path-hotspot |
| `pdf-fill` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_FastCallDictTstate [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_Call_Prepend [inlined]; slot_tp_init [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 2.2% | 2.4% / 2.0% | 2.2% | M-PY-INTERPRETER | M-PY-INTERPRETER, M-PY-TYPECHECK | 1.8% | old-selected-execution-path-hotspot |
| `pdftoppm` | /usr/lib64/libpoppler.so.133.0.0 | `Splash::compositeBackground(unsigned char const*)` / `Splash::compositeBackground(unsigned char const*)`; `Splash::compositeBackground(unsigned char const*) [/usr/lib64/libpoppler.so.133.0.0]; Gfx::~Gfx() [/usr/lib64/libpoppler.so.133.0.0]; Page::displaySlice(OutputDev*, double, double, int, bool, bool, int, int, int, int, bool, bool (*)(void*), void*, bool (*)(Annot*, void*), void*, bool) [/usr/lib64/libpoppler.so.133.0.0]; main [/usr/bin/pdftoppm]` | 2.2% | 2.5% / 1.9% | 2.2% | M-PDF-RASTER | — | 0.0% | old-selected-execution-path-hotspot |
| `pdf-convert` | /usr/lib64/libz.so.1.2.13 | `slide_hash` / `slide_hash`; `slide_hash [/usr/lib64/libz.so.1.2.13]; fill_window [/usr/lib64/libz.so.1.2.13]; deflate_slow [/usr/lib64/libz.so.1.2.13]; deflate [/usr/lib64/libz.so.1.2.13]` | 1.7% | 1.7% / 1.7% | 1.7% | M-ZIP-OPERATION-UNSPECIFIED | M-PY-INTERPRETER, M-ZIP-COMPRESS | 1.7% | old-selected-execution-path-hotspot |
| `pdf-verify` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyEval_EvalFrame [inlined]; gen_send_ex2 [inlined]; gen_iternext [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.4% | 1.6% / 1.1% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER | 1.4% | shared-native-mechanism-and-stack-prefix |
| `pdftoppm` | /usr/lib64/libpoppler.so.133.0.0 | `Splash::pipeRunAARGB8(SplashPipe*)` / `Splash::pipeRunAARGB8(SplashPipe*)`; `Splash::pipeRunAARGB8(SplashPipe*) [/usr/lib64/libpoppler.so.133.0.0]; Splash::fillGlyph2(int, int, SplashGlyphBitmap*, bool) [/usr/lib64/libpoppler.so.133.0.0]; Splash::fillChar(double, double, int, SplashFont*) [/usr/lib64/libpoppler.so.133.0.0]; SplashOutputDev::drawChar(GfxState*, double, double, double, double, double, double, unsigned int, int, unsigned int const*, int) [/usr/lib64/libpoppler.so.133.0.0]` | 1.3% | 1.6% / 1.0% | 1.3% | M-PDF-RASTER | — | 1.3% | old-selected-execution-path-hotspot |
| `pdf-fill` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.0% | 1.1% / 1.0% | 1.0% | M-PY-INTERPRETER | M-PY-INTERPRETER | 1.0% | old-selected-execution-path-hotspot |
| `pdf-verify` | /usr/lib64/libz.so.1.2.13 | `inflate_fast` / `inflate_fast`; `inflate_fast [/usr/lib64/libz.so.1.2.13]; inflate [/usr/lib64/libz.so.1.2.13]; ImagingZipDecode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _decode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]` | 0.8% | 0.8% / 0.8% | 0.0% | M-ZIP-DECOMPRESS | M-PY-INTERPRETER, M-ZIP-DECOMPRESS | 0.4% | shared-native-mechanism-and-stack-prefix |

### sba1919-n1

| 进程/脚本 | DSO | 叶函数/实体 / 代表栈 | 合并权重 | r1 / r2 | 直接路径部分 | 采样点机制 | 调用上下文（可重叠） | 栈前缀匹配权重 | 分类 |
|---|---|---|---:|---:|---:|---|---|---:|---|
| `pdf-convert` | /usr/lib64/libz.so.1.2.13 | `longest_match` / `longest_match`; `longest_match [/usr/lib64/libz.so.1.2.13]; deflate_slow [/usr/lib64/libz.so.1.2.13]; deflate [/usr/lib64/libz.so.1.2.13]; ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]` | 8.0% | 8.0% / 7.9% | 8.0% | M-ZIP-COMPRESS | M-PY-INTERPRETER, M-ZIP-COMPRESS | 8.0% | old-selected-execution-path-hotspot |
| `pdf-convert` | /opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so | `ImagingResampleHorizontal_8bpc` / `ImagingResampleHorizontal_8bpc`; `ImagingResampleHorizontal_8bpc [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; ImagingResampleInner [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _resize [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 7.8% | 8.0% / 7.7% | 7.8% | M-IMAGE-PROCESS | M-PY-INTERPRETER | 7.8% | old-selected-execution-path-hotspot |
| `pdf-convert` | /usr/lib64/libz.so.1.2.13 | `deflate_slow` / `deflate_slow`; `deflate_slow [/usr/lib64/libz.so.1.2.13]; deflate [/usr/lib64/libz.so.1.2.13]; ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _encode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]` | 5.8% | 5.7% / 5.8% | 5.8% | M-ZIP-COMPRESS | M-PY-INTERPRETER, M-ZIP-COMPRESS | 5.8% | old-selected-execution-path-hotspot |
| `pdf-convert` | /opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so | `ImagingZipEncode` / `ImagingZipEncode`; `ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _encode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_VectorcallTstate [inlined]` | 4.4% | 4.9% / 3.9% | 4.4% | M-IMAGE-PROCESS | M-PY-INTERPRETER | 4.4% | old-selected-execution-path-hotspot |
| `pdf-convert` | /opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so | `ImagingResampleVertical_8bpc` / `ImagingResampleVertical_8bpc`; `ImagingResampleVertical_8bpc [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; ImagingResampleInner [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _resize [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 3.3% | 3.4% / 3.2% | 3.3% | M-IMAGE-PROCESS | M-PY-INTERPRETER | 3.3% | old-selected-execution-path-hotspot |
| `pdf-verify` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyEval_EvalFrame [inlined]; gen_send_ex2 [inlined]; gen_iternext [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 3.3% | 3.4% / 3.2% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER | 1.5% | shared-native-mechanism-and-stack-prefix |
| `pdftoppm` | /usr/lib64/libpoppler.so.133.0.0 | `Splash::pipeRunAARGB8(SplashPipe*)` / `Splash::pipeRunAARGB8(SplashPipe*)`; `Splash::pipeRunAARGB8(SplashPipe*) [/usr/lib64/libpoppler.so.133.0.0]; Splash::fillGlyph2(int, int, SplashGlyphBitmap*, bool) [/usr/lib64/libpoppler.so.133.0.0]; Splash::fillChar(double, double, int, SplashFont*) [/usr/lib64/libpoppler.so.133.0.0]; SplashOutputDev::drawChar(GfxState*, double, double, double, double, double, double, unsigned int, int, unsigned int const*, int) [/usr/lib64/libpoppler.so.133.0.0]` | 2.9% | 3.0% / 2.9% | 2.9% | M-PDF-RASTER | — | 2.9% | old-selected-execution-path-hotspot |
| `pdftoppm` | /usr/lib64/libpoppler.so.133.0.0 | `Splash::compositeBackground(unsigned char const*)` / `Splash::compositeBackground(unsigned char const*)`; `Splash::compositeBackground(unsigned char const*) [/usr/lib64/libpoppler.so.133.0.0]; Gfx::~Gfx() [/usr/lib64/libpoppler.so.133.0.0]; Page::displaySlice(OutputDev*, double, double, int, bool, bool, int, int, int, int, bool, bool (*)(void*), void*, bool (*)(Annot*, void*), void*, bool) [/usr/lib64/libpoppler.so.133.0.0]; main [/usr/bin/pdftoppm]` | 2.1% | 2.3% / 1.8% | 2.1% | M-PDF-RASTER | — | 0.0% | old-selected-execution-path-hotspot |
| `pdf-convert` | /usr/lib64/libz.so.1.2.13 | `slide_hash` / `slide_hash`; `slide_hash [/usr/lib64/libz.so.1.2.13]; fill_window [/usr/lib64/libz.so.1.2.13]; deflate_slow [/usr/lib64/libz.so.1.2.13]; deflate [/usr/lib64/libz.so.1.2.13]` | 1.6% | 1.9% / 1.4% | 1.6% | M-ZIP-OPERATION-UNSPECIFIED | M-PY-INTERPRETER, M-ZIP-COMPRESS | 1.6% | old-selected-execution-path-hotspot |
| `pdftoppm` | /usr/lib64/libfreetype.so.6.20.1 | `gray_render_line` / `gray_render_line`; `gray_render_line [/usr/lib64/libfreetype.so.6.20.1]; gray_render_conic [inlined]; gray_conic_to [/usr/lib64/libfreetype.so.6.20.1]; FT_Outline_Decompose [/usr/lib64/libfreetype.so.6.20.1]` | 1.6% | 1.8% / 1.3% | 1.6% | M-PDF-RASTER | — | 1.4% | old-selected-execution-path-hotspot |
| `pdf-fill` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.4% | 1.3% / 1.5% | 1.4% | M-PY-INTERPRETER | M-PY-INTERPRETER | 1.3% | old-selected-execution-path-hotspot |
| `pdf-fill` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_FastCallDictTstate [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_Call_Prepend [inlined]; slot_tp_init [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.3% | 1.3% / 1.3% | 1.3% | M-PY-INTERPRETER | M-PY-INTERPRETER, M-PY-TYPECHECK | 1.0% | old-selected-execution-path-hotspot |

### opm-n10

| 进程/脚本 | DSO | 叶函数/实体 / 代表栈 | 合并权重 | r1 / r2 | 直接路径部分 | 采样点机制 | 调用上下文（可重叠） | 栈前缀匹配权重 | 分类 |
|---|---|---|---:|---:|---:|---|---|---:|---|
| `pdf-convert` | /usr/lib64/libz.so.1.2.13 | `longest_match` / `longest_match`; `longest_match [/usr/lib64/libz.so.1.2.13]; deflate_slow [/usr/lib64/libz.so.1.2.13]; deflate [/usr/lib64/libz.so.1.2.13]; ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]` | 7.6% | 8.0% / 7.3% | 7.6% | M-ZIP-COMPRESS | M-PY-INTERPRETER, M-ZIP-COMPRESS | 7.6% | old-selected-execution-path-hotspot |
| `pdf-convert` | /opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so | `ImagingResampleHorizontal_8bpc` / `ImagingResampleHorizontal_8bpc`; `ImagingResampleHorizontal_8bpc [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; ImagingResampleInner [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _resize [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 7.1% | 6.8% / 7.4% | 7.1% | M-IMAGE-PROCESS | M-PY-INTERPRETER | 7.1% | old-selected-execution-path-hotspot |
| `pdf-convert` | /usr/lib64/libz.so.1.2.13 | `deflate_slow` / `deflate_slow`; `deflate_slow [/usr/lib64/libz.so.1.2.13]; deflate [/usr/lib64/libz.so.1.2.13]; ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _encode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]` | 4.9% | 4.7% / 5.0% | 4.9% | M-ZIP-COMPRESS | M-PY-INTERPRETER, M-ZIP-COMPRESS | 4.9% | old-selected-execution-path-hotspot |
| `pdf-convert` | /opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so | `ImagingZipEncode` / `ImagingZipEncode`; `ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _encode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_VectorcallTstate [inlined]` | 4.2% | 4.1% / 4.2% | 4.2% | M-IMAGE-PROCESS | M-PY-INTERPRETER | 4.2% | old-selected-execution-path-hotspot |
| `pdf-convert` | /opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so | `ImagingResampleVertical_8bpc` / `ImagingResampleVertical_8bpc`; `ImagingResampleVertical_8bpc [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; ImagingResampleInner [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _resize [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 3.3% | 3.1% / 3.4% | 3.3% | M-IMAGE-PROCESS | M-PY-INTERPRETER | 3.3% | old-selected-execution-path-hotspot |
| `pdf-verify` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyEval_EvalFrame [inlined]; gen_send_ex2 [inlined]; gen_iternext [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 3.1% | 3.2% / 3.0% | 3.1% | M-PY-INTERPRETER | M-PY-INTERPRETER | 3.1% | old-selected-execution-path-hotspot |
| `pdf-fill` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 2.7% | 2.9% / 2.4% | 2.7% | M-PY-INTERPRETER | M-PY-INTERPRETER | 2.6% | old-selected-execution-path-hotspot |
| `pdf-fill` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_FastCallDictTstate [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_Call_Prepend [inlined]; slot_tp_init [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 2.5% | 2.9% / 2.2% | 2.5% | M-PY-INTERPRETER | M-PY-INTERPRETER, M-PY-TYPECHECK | 1.8% | old-selected-execution-path-hotspot |
| `pdftoppm` | /usr/lib64/libpoppler.so.133.0.0 | `Splash::pipeRunAARGB8(SplashPipe*)` / `Splash::pipeRunAARGB8(SplashPipe*)`; `Splash::pipeRunAARGB8(SplashPipe*) [/usr/lib64/libpoppler.so.133.0.0]; Splash::fillGlyph2(int, int, SplashGlyphBitmap*, bool) [/usr/lib64/libpoppler.so.133.0.0]; Splash::fillChar(double, double, int, SplashFont*) [/usr/lib64/libpoppler.so.133.0.0]; SplashOutputDev::drawChar(GfxState*, double, double, double, double, double, double, unsigned int, int, unsigned int const*, int) [/usr/lib64/libpoppler.so.133.0.0]` | 1.8% | 2.1% / 1.6% | 1.8% | M-PDF-RASTER | — | 1.8% | old-selected-execution-path-hotspot |
| `pdftoppm` | /usr/lib64/libpoppler.so.133.0.0 | `Splash::compositeBackground(unsigned char const*)` / `Splash::compositeBackground(unsigned char const*)`; `Splash::compositeBackground(unsigned char const*) [/usr/lib64/libpoppler.so.133.0.0]; Gfx::~Gfx() [/usr/lib64/libpoppler.so.133.0.0]; Page::displaySlice(OutputDev*, double, double, int, bool, bool, int, int, int, int, bool, bool (*)(void*), void*, bool (*)(Annot*, void*), void*, bool) [/usr/lib64/libpoppler.so.133.0.0]; main [/usr/bin/pdftoppm]` | 1.6% | 1.5% / 1.7% | 1.6% | M-PDF-RASTER | — | 0.0% | old-selected-execution-path-hotspot |
| `pdf-convert` | /usr/lib64/libz.so.1.2.13 | `slide_hash` / `slide_hash`; `slide_hash [/usr/lib64/libz.so.1.2.13]; fill_window [/usr/lib64/libz.so.1.2.13]; deflate_slow [/usr/lib64/libz.so.1.2.13]; deflate [/usr/lib64/libz.so.1.2.13]` | 1.4% | 1.4% / 1.3% | 1.4% | M-ZIP-OPERATION-UNSPECIFIED | M-PY-INTERPRETER, M-ZIP-COMPRESS | 1.4% | old-selected-execution-path-hotspot |
| `pdf-verify` | /usr/lib64/libz.so.1.2.13 | `inflate_fast` / `inflate_fast`; `inflate_fast [/usr/lib64/libz.so.1.2.13]; inflate [/usr/lib64/libz.so.1.2.13]; ImagingZipDecode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _decode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]` | 1.0% | 1.1% / 1.0% | 1.0% | M-ZIP-DECOMPRESS | M-PY-INTERPRETER, M-ZIP-DECOMPRESS | 1.0% | old-selected-execution-path-hotspot |

### irs_w4-n10

| 进程/脚本 | DSO | 叶函数/实体 / 代表栈 | 合并权重 | r1 / r2 | 直接路径部分 | 采样点机制 | 调用上下文（可重叠） | 栈前缀匹配权重 | 分类 |
|---|---|---|---:|---:|---:|---|---|---:|---|
| `pdf-convert` | /usr/lib64/libz.so.1.2.13 | `longest_match` / `longest_match`; `longest_match [/usr/lib64/libz.so.1.2.13]; deflate_slow [/usr/lib64/libz.so.1.2.13]; deflate [/usr/lib64/libz.so.1.2.13]; ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]` | 8.5% | 7.5% / 9.6% | 8.5% | M-ZIP-COMPRESS | M-PY-INTERPRETER, M-ZIP-COMPRESS | 8.5% | old-selected-execution-path-hotspot |
| `pdf-convert` | /opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so | `ImagingResampleHorizontal_8bpc` / `ImagingResampleHorizontal_8bpc`; `ImagingResampleHorizontal_8bpc [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; ImagingResampleInner [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _resize [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 7.7% | 7.2% / 8.2% | 7.7% | M-IMAGE-PROCESS | M-PY-INTERPRETER | 7.7% | old-selected-execution-path-hotspot |
| `pdf-convert` | /usr/lib64/libz.so.1.2.13 | `deflate_slow` / `deflate_slow`; `deflate_slow [/usr/lib64/libz.so.1.2.13]; deflate [/usr/lib64/libz.so.1.2.13]; ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _encode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]` | 5.5% | 5.6% / 5.3% | 5.5% | M-ZIP-COMPRESS | M-PY-INTERPRETER, M-ZIP-COMPRESS | 5.5% | old-selected-execution-path-hotspot |
| `pdf-convert` | /opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so | `ImagingZipEncode` / `ImagingZipEncode`; `ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _encode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_VectorcallTstate [inlined]` | 5.1% | 5.3% / 5.0% | 5.1% | M-IMAGE-PROCESS | M-PY-INTERPRETER | 5.1% | old-selected-execution-path-hotspot |
| `pdf-fill` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_FastCallDictTstate [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_Call_Prepend [inlined]; slot_tp_init [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 4.2% | 5.0% / 3.4% | 4.2% | M-PY-INTERPRETER | M-PY-INTERPRETER, M-PY-TYPECHECK | 3.9% | old-selected-execution-path-hotspot |
| `pdf-convert` | /opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so | `ImagingResampleVertical_8bpc` / `ImagingResampleVertical_8bpc`; `ImagingResampleVertical_8bpc [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; ImagingResampleInner [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _resize [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 3.4% | 3.1% / 3.8% | 3.4% | M-IMAGE-PROCESS | M-PY-INTERPRETER | 3.4% | old-selected-execution-path-hotspot |
| `pdftoppm` | /usr/lib64/libpoppler.so.133.0.0 | `Splash::compositeBackground(unsigned char const*)` / `Splash::compositeBackground(unsigned char const*)`; `Splash::compositeBackground(unsigned char const*) [/usr/lib64/libpoppler.so.133.0.0]; Gfx::~Gfx() [/usr/lib64/libpoppler.so.133.0.0]; Page::displaySlice(OutputDev*, double, double, int, bool, bool, int, int, int, int, bool, bool (*)(void*), void*, bool (*)(Annot*, void*), void*, bool) [/usr/lib64/libpoppler.so.133.0.0]; main [/usr/bin/pdftoppm]` | 2.3% | 2.6% / 1.9% | 2.2% | M-PDF-RASTER | — | 0.0% | old-selected-execution-path-hotspot |
| `pdf-verify` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyEval_EvalFrame [inlined]; gen_send_ex2 [inlined]; gen_iternext [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 2.1% | 2.2% / 1.9% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER | 2.1% | shared-native-mechanism-and-stack-prefix |
| `pdftoppm` | /usr/lib64/libpoppler.so.133.0.0 | `Splash::pipeRunAARGB8(SplashPipe*)` / `Splash::pipeRunAARGB8(SplashPipe*)`; `Splash::pipeRunAARGB8(SplashPipe*) [/usr/lib64/libpoppler.so.133.0.0]; Splash::fillGlyph2(int, int, SplashGlyphBitmap*, bool) [/usr/lib64/libpoppler.so.133.0.0]; Splash::fillChar(double, double, int, SplashFont*) [/usr/lib64/libpoppler.so.133.0.0]; SplashOutputDev::drawChar(GfxState*, double, double, double, double, double, double, unsigned int, int, unsigned int const*, int) [/usr/lib64/libpoppler.so.133.0.0]` | 1.8% | 1.9% / 1.7% | 1.7% | M-PDF-RASTER | — | 1.8% | old-selected-execution-path-hotspot |
| `pdf-convert` | /usr/lib64/libz.so.1.2.13 | `slide_hash` / `slide_hash`; `slide_hash [/usr/lib64/libz.so.1.2.13]; fill_window [/usr/lib64/libz.so.1.2.13]; deflate_slow [/usr/lib64/libz.so.1.2.13]; deflate [/usr/lib64/libz.so.1.2.13]` | 1.7% | 1.3% / 2.1% | 1.7% | M-ZIP-OPERATION-UNSPECIFIED | M-PY-INTERPRETER, M-ZIP-COMPRESS | 1.7% | old-selected-execution-path-hotspot |
| `pdf-fill` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.4% | 1.5% / 1.3% | 1.4% | M-PY-INTERPRETER | M-PY-INTERPRETER | 1.3% | old-selected-execution-path-hotspot |
| `pdf-convert` | /usr/lib64/libc.so.6 | `__memcpy_generic` / `__memcpy_generic`; `__memcpy_generic [/usr/lib64/libc.so.6]; PyBytes_FromStringAndSize [inlined]; read_bytes [inlined]; _io_BytesIO_read_impl [inlined]` | 1.1% | 1.6% / 0.6% | 1.1% | M-LIBC-PRIMITIVE | M-PY-INTERPRETER | 0.7% | old-selected-execution-path-hotspot |

### sba1919-n10

| 进程/脚本 | DSO | 叶函数/实体 / 代表栈 | 合并权重 | r1 / r2 | 直接路径部分 | 采样点机制 | 调用上下文（可重叠） | 栈前缀匹配权重 | 分类 |
|---|---|---|---:|---:|---:|---|---|---:|---|
| `pdf-convert` | /usr/lib64/libz.so.1.2.13 | `longest_match` / `longest_match`; `longest_match [/usr/lib64/libz.so.1.2.13]; deflate_slow [/usr/lib64/libz.so.1.2.13]; deflate [/usr/lib64/libz.so.1.2.13]; ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]` | 8.0% | 8.1% / 7.9% | 8.0% | M-ZIP-COMPRESS | M-PY-INTERPRETER, M-ZIP-COMPRESS | 8.0% | old-selected-execution-path-hotspot |
| `pdf-convert` | /opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so | `ImagingResampleHorizontal_8bpc` / `ImagingResampleHorizontal_8bpc`; `ImagingResampleHorizontal_8bpc [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; ImagingResampleInner [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _resize [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 7.4% | 7.1% / 7.6% | 7.4% | M-IMAGE-PROCESS | M-PY-INTERPRETER | 7.4% | old-selected-execution-path-hotspot |
| `pdf-convert` | /usr/lib64/libz.so.1.2.13 | `deflate_slow` / `deflate_slow`; `deflate_slow [/usr/lib64/libz.so.1.2.13]; deflate [/usr/lib64/libz.so.1.2.13]; ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _encode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]` | 5.8% | 6.3% / 5.3% | 5.8% | M-ZIP-COMPRESS | M-PY-INTERPRETER, M-ZIP-COMPRESS | 5.8% | old-selected-execution-path-hotspot |
| `pdf-convert` | /opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so | `ImagingZipEncode` / `ImagingZipEncode`; `ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _encode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_VectorcallTstate [inlined]` | 4.8% | 4.8% / 4.8% | 4.8% | M-IMAGE-PROCESS | M-PY-INTERPRETER | 4.8% | old-selected-execution-path-hotspot |
| `pdf-verify` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyEval_EvalFrame [inlined]; gen_send_ex2 [inlined]; gen_iternext [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 4.6% | 4.7% / 4.6% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER | 4.6% | shared-native-mechanism-and-stack-prefix |
| `pdf-convert` | /opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so | `ImagingResampleVertical_8bpc` / `ImagingResampleVertical_8bpc`; `ImagingResampleVertical_8bpc [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; ImagingResampleInner [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _resize [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 3.8% | 3.7% / 3.8% | 3.8% | M-IMAGE-PROCESS | M-PY-INTERPRETER | 3.8% | old-selected-execution-path-hotspot |
| `pdftoppm` | /usr/lib64/libpoppler.so.133.0.0 | `Splash::pipeRunAARGB8(SplashPipe*)` / `Splash::pipeRunAARGB8(SplashPipe*)`; `Splash::pipeRunAARGB8(SplashPipe*) [/usr/lib64/libpoppler.so.133.0.0]; Splash::fillGlyph2(int, int, SplashGlyphBitmap*, bool) [/usr/lib64/libpoppler.so.133.0.0]; Splash::fillChar(double, double, int, SplashFont*) [/usr/lib64/libpoppler.so.133.0.0]; SplashOutputDev::drawChar(GfxState*, double, double, double, double, double, double, unsigned int, int, unsigned int const*, int) [/usr/lib64/libpoppler.so.133.0.0]` | 2.9% | 2.9% / 3.0% | 2.9% | M-PDF-RASTER | — | 2.9% | old-selected-execution-path-hotspot |
| `pdf-fill` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 2.5% | 2.5% / 2.5% | 2.5% | M-PY-INTERPRETER | M-PY-INTERPRETER | 2.3% | old-selected-execution-path-hotspot |
| `pdf-fill` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_FastCallDictTstate [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_Call_Prepend [inlined]; slot_tp_init [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 2.2% | 1.9% / 2.6% | 2.2% | M-PY-INTERPRETER | M-PY-INTERPRETER, M-PY-TYPECHECK | 1.8% | old-selected-execution-path-hotspot |
| `pdf-convert` | /usr/lib64/libz.so.1.2.13 | `slide_hash` / `slide_hash`; `slide_hash [/usr/lib64/libz.so.1.2.13]; fill_window [/usr/lib64/libz.so.1.2.13]; deflate_slow [/usr/lib64/libz.so.1.2.13]; deflate [/usr/lib64/libz.so.1.2.13]` | 2.0% | 1.9% / 2.0% | 2.0% | M-ZIP-OPERATION-UNSPECIFIED | M-PY-INTERPRETER, M-ZIP-COMPRESS | 2.0% | old-selected-execution-path-hotspot |
| `pdftoppm` | /usr/lib64/libpoppler.so.133.0.0 | `Splash::compositeBackground(unsigned char const*)` / `Splash::compositeBackground(unsigned char const*)`; `Splash::compositeBackground(unsigned char const*) [/usr/lib64/libpoppler.so.133.0.0]; Gfx::~Gfx() [/usr/lib64/libpoppler.so.133.0.0]; Page::displaySlice(OutputDev*, double, double, int, bool, bool, int, int, int, int, bool, bool (*)(void*), void*, bool (*)(Annot*, void*), void*, bool) [/usr/lib64/libpoppler.so.133.0.0]; main [/usr/bin/pdftoppm]` | 1.8% | 1.7% / 1.8% | 1.8% | M-PDF-RASTER | — | 0.0% | old-selected-execution-path-hotspot |
| `pdf-verify` | /usr/lib64/libz.so.1.2.13 | `inflate_fast` / `inflate_fast`; `inflate_fast [/usr/lib64/libz.so.1.2.13]; inflate [/usr/lib64/libz.so.1.2.13]; ImagingZipDecode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]; _decode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]` | 1.8% | 1.9% / 1.7% | 0.0% | M-ZIP-DECOMPRESS | M-PY-INTERPRETER, M-ZIP-DECOMPRESS | 1.7% | shared-native-mechanism-and-stack-prefix |

### tlc

| 进程/脚本 | DSO | 叶函数/实体 / 代表栈 | 合并权重 | r1 / r2 | 直接路径部分 | 采样点机制 | 调用上下文（可重叠） | 栈前缀匹配权重 | 分类 |
|---|---|---|---:|---:|---:|---|---|---:|---|
| `xlsx-enhance` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 3.1% | 3.2% / 2.9% | 3.1% | M-PY-INTERPRETER | M-PY-INTERPRETER | 3.1% | old-selected-execution-path-hotspot |
| `xlsx-recalc` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.8% | 1.7% / 1.8% | 1.8% | M-PY-INTERPRETER | M-PY-INTERPRETER | 1.8% | old-selected-execution-path-hotspot |
| `xlsx-inspect-structure` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.5% | 1.4% / 1.6% | 1.5% | M-PY-INTERPRETER | M-PY-INTERPRETER | 1.5% | old-selected-execution-path-hotspot |
| `xlsx-verify` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.0% | 1.0% / 1.0% | 1.0% | M-PY-INTERPRETER | M-PY-INTERPRETER | 1.0% | old-selected-execution-path-hotspot |
| `xlsx-enhance` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `Py_INCREF` / `_PyEval_EvalFrameDefault`; `Py_INCREF [inlined]; _PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.0% | 0.9% / 1.1% | 1.0% | M-PY-REFCOUNT | M-PY-INTERPRETER | 1.0% | old-selected-execution-path-hotspot |
| `xlsx-inspect-features` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.0% | 1.0% / 0.9% | 1.0% | M-PY-INTERPRETER | M-PY-INTERPRETER | 1.0% | old-selected-execution-path-hotspot |
| `xlsx-inspect-structure` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `dictiter_iternextkey` / `dictiter_iternextkey`; `dictiter_iternextkey [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyEval_EvalFrame [inlined]; gen_send_ex2 [inlined]` | 1.0% | 1.2% / 0.7% | 1.0% | M-PY-RUNTIME-OTHER | M-PY-INTERPRETER | 1.0% | old-selected-execution-path-hotspot |
| `xlsx-inspect-cached` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 0.7% | 0.8% / 0.7% | 0.7% | M-PY-INTERPRETER | M-PY-INTERPRETER | 0.7% | old-selected-execution-path-hotspot |
| `xlsx-inspect-formulas` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 0.7% | 0.7% / 0.8% | 0.7% | M-PY-INTERPRETER | M-PY-INTERPRETER | 0.7% | old-selected-execution-path-hotspot |
| `xlsx-summary-export` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 0.7% | 0.8% / 0.7% | 0.7% | M-PY-INTERPRETER | M-PY-INTERPRETER | 0.7% | old-selected-execution-path-hotspot |

### retail

| 进程/脚本 | DSO | 叶函数/实体 / 代表栈 | 合并权重 | r1 / r2 | 直接路径部分 | 采样点机制 | 调用上下文（可重叠） | 栈前缀匹配权重 | 分类 |
|---|---|---|---:|---:|---:|---|---|---:|---|
| `xlsx-verify` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 5.0% | 5.9% / 4.1% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER | 3.8% | shared-native-mechanism-and-stack-prefix |
| `soffice.bin` | /opt/libreoffice25.8-symbols/program/libsclo.so | `std::_Rb_tree<int, int, std::_Identity<int>, std::less<int>, std::allocator<int> >::_M_get_insert_unique_pos(int const&)` / `std::_Rb_tree<int, int, std::_Identity<int>, std::less<int>, std::allocator<int> >::_M_get_insert_unique_pos(int const&)`; `std::_Rb_tree<int, int, std::_Identity<int>, std::less<int>, std::allocator<int> >::_M_get_insert_unique_pos(int const&) [/opt/libreoffice25.8-symbols/program/libsclo.so]; std::pair<std::_Rb_tree_iterator<int>, bool> std::_Rb_tree<int, int, std::_Identity<int>, std::less<int>, std::allocator<int> >::_M_insert_unique<int const&>(int const&) [/opt/libreoffice25.8-symbols/program/libsclo.so]; ScTable::UpdatePageBreaks(ScRange const*) [/opt/libreoffice25.8-symbols/program/libsclo.so]; ScPrintFunc::UpdatePages() [/opt/libreoffice25.8-symbols/program/libsclo.so]` | 2.5% | 2.5% / 2.5% | 2.5% | M-LIBREOFFICE-NATIVE | — | 0.0% | old-selected-execution-path-hotspot |
| `xlsx-inspect-tool` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.9% | 0.8% / 3.0% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER | 1.9% | shared-native-mechanism-and-stack-prefix |
| `xlsx-enhance` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.7% | 2.1% / 1.3% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER | 1.6% | shared-native-mechanism-and-stack-prefix |
| `xlsx-inspect-tool` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_FastCallDictTstate [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_Call_Prepend [inlined]; slot_tp_init [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.7% | 2.1% / 1.2% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER, M-PY-TYPECHECK | 1.6% | shared-native-mechanism-and-stack-prefix |
| `xlsx-verify` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyEval_EvalFrame [inlined]; _PyEval_Vector [inlined]; _PyFunction_Vectorcall [inlined]` | 1.6% | 2.0% / 1.3% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER, M-PY-TYPECHECK | 1.6% | shared-native-mechanism-and-stack-prefix |
| `xlsx-verify` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `Py_INCREF` / `_PyEval_EvalFrameDefault`; `Py_INCREF [inlined]; _PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.0% | 1.1% / 1.0% | 0.0% | M-PY-REFCOUNT | M-PY-INTERPRETER | 1.0% | shared-native-mechanism-and-stack-prefix |
| `soffice.bin` | /usr/lib64/libc.so.6 | `_int_free` / `_int_free`; `_int_free [/usr/lib64/libc.so.6]; __GI___libc_free [inlined]; std::__new_allocator<std::_Rb_tree_node<int> >::deallocate(std::_Rb_tree_node<int>*, unsigned long) [inlined]; std::allocator<std::_Rb_tree_node<int> >::deallocate(std::_Rb_tree_node<int>*, unsigned long) [inlined]` | 1.0% | 1.0% / 1.0% | 1.0% | M-LIBC-PRIMITIVE | — | 0.0% | old-selected-execution-path-hotspot |
| `xlsx-recalc` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyEval_EvalFrame [inlined]; gen_send_ex2 [inlined]; gen_iternext [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 0.9% | 0.9% / 1.0% | 0.9% | M-PY-INTERPRETER | M-PY-INTERPRETER | 0.9% | old-selected-execution-path-hotspot |
| `soffice.bin` | /opt/libreoffice25.8-symbols/program/libscfiltlo.so | `XclExpRowBuffer::GetOrCreateRow(unsigned int, bool)` / `XclExpRowBuffer::GetOrCreateRow(unsigned int, bool)`; `XclExpRowBuffer::GetOrCreateRow(unsigned int, bool) [/opt/libreoffice25.8-symbols/program/libscfiltlo.so]; XclExpRowBuffer::CreateRows(int) [inlined]; XclExpRowBuffer::CreateRows(int) [inlined]; XclExpCellTable::XclExpCellTable(XclExpRoot const&) [/opt/libreoffice25.8-symbols/program/libscfiltlo.so]` | 0.7% | 0.9% / 0.5% | 0.7% | M-LIBREOFFICE-NATIVE | — | 0.7% | old-selected-execution-path-hotspot |
| `xlsx-verify` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyGCHead_NEXT` / `gc_collect_main`; `_PyGCHead_NEXT [inlined]; untrack_tuples [inlined]; gc_collect_main [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; gc_collect_with_callback [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 0.7% | 0.7% / 0.7% | 0.0% | M-PY-GC | M-PY-GC, M-PY-INTERPRETER | 0.7% | shared-native-mechanism-and-stack-prefix |
| `soffice.bin` | /opt/libreoffice25.8-symbols/program/libsclo.so | `ScHorizontalAttrIterator::InitForNextRow(bool)` / `ScHorizontalAttrIterator::InitForNextRow(bool)`; `ScHorizontalAttrIterator::InitForNextRow(bool) [/opt/libreoffice25.8-symbols/program/libsclo.so]; ScHorizontalAttrIterator::GetNext(short&, short&, int&) [/opt/libreoffice25.8-symbols/program/libsclo.so]; ScUsedAreaIterator::GetNext() [/opt/libreoffice25.8-symbols/program/libsclo.so]; XclExpCellTable::XclExpCellTable(XclExpRoot const&) [/opt/libreoffice25.8-symbols/program/libscfiltlo.so]` | 0.7% | 0.4% / 1.0% | 0.7% | M-LIBREOFFICE-NATIVE | — | 0.0% | old-selected-execution-path-hotspot |

### manufacturing

| 进程/脚本 | DSO | 叶函数/实体 / 代表栈 | 合并权重 | r1 / r2 | 直接路径部分 | 采样点机制 | 调用上下文（可重叠） | 栈前缀匹配权重 | 分类 |
|---|---|---|---:|---:|---:|---|---|---:|---|
| `xlsx-verify` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 3.3% | 3.0% / 3.6% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER | 2.8% | shared-native-mechanism-and-stack-prefix |
| `xlsx-verify` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyEval_EvalFrame [inlined]; _PyEval_Vector [inlined]; _PyFunction_Vectorcall [inlined]` | 2.9% | 3.7% / 2.0% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER, M-PY-TYPECHECK | 2.7% | shared-native-mechanism-and-stack-prefix |
| `xlsx-summary-export` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyEval_EvalFrame [inlined]; _PyEval_Vector [inlined]; _PyFunction_Vectorcall [inlined]` | 1.3% | 2.2% / 0.5% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER, M-PY-TYPECHECK | 1.3% | shared-native-mechanism-and-stack-prefix |
| `lo-thread` | /opt/libreoffice25.8-symbols/program/libscfiltlo.so | `XclExpRow::Finalize(std::vector<unsigned short, std::allocator<unsigned short> > const&, std::vector<unsigned short, std::allocator<unsigned short> >&, unsigned long, bool)` / `XclExpRow::Finalize(std::vector<unsigned short, std::allocator<unsigned short> > const&, std::vector<unsigned short, std::allocator<unsigned short> >&, unsigned long, bool)`; `XclExpRow::Finalize(std::vector<unsigned short, std::allocator<unsigned short> > const&, std::vector<unsigned short, std::allocator<unsigned short> >&, unsigned long, bool) [/opt/libreoffice25.8-symbols/program/libscfiltlo.so]; (anonymous namespace)::RowFinalizeTask::doWork() [/opt/libreoffice25.8-symbols/program/libscfiltlo.so]; comphelper::ThreadTask::exec() [/opt/libreoffice25.8-symbols/program/libcomphelper.so]; comphelper::ThreadPool::ThreadWorker::execute() [/opt/libreoffice25.8-symbols/program/libcomphelper.so]` | 1.2% | 1.0% / 1.4% | 0.7% | M-LIBREOFFICE-NATIVE | — | 0.9% | old-selected-execution-path-hotspot |
| `soffice.bin` | /usr/lib/ld-linux-aarch64.so.1 | `do_lookup_x` / `do_lookup_x`; `do_lookup_x [/usr/lib/ld-linux-aarch64.so.1]; _dl_lookup_symbol_x [/usr/lib/ld-linux-aarch64.so.1]; resolve_map [inlined]; elf_machine_rela [inlined]` | 1.0% | 1.2% / 0.8% | 1.0% | M-NATIVE-OTHER-UNSPECIFIED | — | 0.1% | old-selected-execution-path-hotspot |
| `soffice.bin` | /usr/lib64/libpixman-1.so.0.42.2 | `[unknown]` / `[unknown]`; `[unknown] [/usr/lib64/libpixman-1.so.0.42.2]; [unknown] [/usr/lib64/libpixman-1.so.0.42.2]; [unknown] [/usr/lib64/libpixman-1.so.0.42.2]; pixman_blt [/usr/lib64/libpixman-1.so.0.42.2]` | 1.0% | 1.3% / 0.7% | 1.0% | M-UNCLASSIFIED | — | 0.0% | unknown-native-hotspot |
| `xlsx-recalc` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyEval_EvalFrame [inlined]; gen_send_ex2 [inlined]; gen_iternext [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 0.8% | 1.1% / 0.6% | 0.8% | M-PY-INTERPRETER | M-PY-INTERPRETER | 0.8% | old-selected-execution-path-hotspot |
| `xlsx-inspect-tool` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_FastCallDictTstate [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyObject_Call_Prepend [inlined]; slot_tp_init [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 0.8% | 0.9% / 0.7% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER, M-PY-TYPECHECK | 0.8% | shared-native-mechanism-and-stack-prefix |
| `xlsx-enhance` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 0.8% | 0.4% / 1.2% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER | 0.7% | shared-native-mechanism-and-stack-prefix |
| `xlsx-inspect-tool` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyGCHead_NEXT` / `deduce_unreachable`; `_PyGCHead_NEXT [inlined]; update_refs [inlined]; deduce_unreachable [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; handle_resurrected_objects [inlined]` | 0.8% | 1.5% / 0.1% | 0.0% | M-PY-GC | M-PY-GC | 0.0% | new-execution-path-shared-native-mechanism |
| `xlsx-inspect-tool` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyGCHead_NEXT` / `gc_collect_main`; `_PyGCHead_NEXT [inlined]; untrack_tuples [inlined]; gc_collect_main [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; gc_collect_with_callback [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 0.8% | 1.0% / 0.6% | 0.0% | M-PY-GC | M-PY-GC | 0.5% | shared-native-mechanism-and-stack-prefix |
| `xlsx-verify` | /usr/lib64/libz.so.1.2.13 | `inflate_fast` / `inflate_fast`; `inflate_fast [/usr/lib64/libz.so.1.2.13]; inflate [/usr/lib64/libz.so.1.2.13]; zlib_Decompress_decompress_impl [inlined]; zlib_Decompress_decompress [/opt/python-3.12.3/lib/python3.12/lib-dynload/zlib.cpython-312-aarch64-linux-gnu.so]` | 0.6% | 0.8% / 0.5% | 0.0% | M-ZIP-DECOMPRESS | M-PY-INTERPRETER, M-ZIP-DECOMPRESS | 0.3% | shared-native-mechanism-and-stack-prefix |

### hr

| 进程/脚本 | DSO | 叶函数/实体 / 代表栈 | 合并权重 | r1 / r2 | 直接路径部分 | 采样点机制 | 调用上下文（可重叠） | 栈前缀匹配权重 | 分类 |
|---|---|---|---:|---:|---:|---|---|---:|---|
| `xlsx-verify` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 4.7% | 4.4% / 5.0% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER | 3.8% | shared-native-mechanism-and-stack-prefix |
| `xlsx-enhance` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.8% | 2.1% / 1.6% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER | 1.8% | shared-native-mechanism-and-stack-prefix |
| `xlsx-inspect-tool` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_mod [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.7% | 1.6% / 1.7% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER | 1.7% | shared-native-mechanism-and-stack-prefix |
| `xlsx-recalc` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyEval_EvalFrame [inlined]; gen_send_ex2 [inlined]; gen_iternext [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 1.4% | 0.8% / 2.0% | 1.4% | M-PY-INTERPRETER | M-PY-INTERPRETER | 1.3% | old-selected-execution-path-hotspot |
| `xlsx-verify` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyEval_EvalFrame [inlined]; _PyEval_Vector [inlined]; _PyFunction_Vectorcall [inlined]` | 1.1% | 1.6% / 0.5% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER, M-PY-TYPECHECK | 1.1% | shared-native-mechanism-and-stack-prefix |
| `xlsx-verify` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `Py_INCREF` / `_PyEval_EvalFrameDefault`; `Py_INCREF [inlined]; _PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 0.9% | 0.9% / 0.8% | 0.0% | M-PY-REFCOUNT | M-PY-INTERPRETER | 0.8% | shared-native-mechanism-and-stack-prefix |
| `xlsx-summary-export` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyEval_EvalFrameDefault` / `_PyEval_EvalFrameDefault`; `_PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; _PyEval_EvalFrame [inlined]; gen_send_ex2 [inlined]; gen_iternext [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 0.7% | 0.7% / 0.8% | 0.0% | M-PY-INTERPRETER | M-PY-INTERPRETER | 0.7% | shared-native-mechanism-and-stack-prefix |
| `soffice.bin` | /usr/lib64/libpixman-1.so.0.42.2 | `[unknown]` / `[unknown]`; `[unknown] [/usr/lib64/libpixman-1.so.0.42.2]; [unknown] [/usr/lib64/libpixman-1.so.0.42.2]; [unknown] [/usr/lib64/libpixman-1.so.0.42.2]; pixman_blt [/usr/lib64/libpixman-1.so.0.42.2]` | 0.7% | 0.6% / 0.7% | 0.7% | M-UNCLASSIFIED | — | 0.0% | unknown-native-hotspot |
| `xlsx-inspect-tool` | /opt/python-3.12.3/lib/python3.12/lib-dynload/_elementtree.cpython-312-aarch64-linux-gnu.so | `checkpath` / `checkpath`; `checkpath [/opt/python-3.12.3/lib/python3.12/lib-dynload/_elementtree.cpython-312-aarch64-linux-gnu.so]; _elementtree_Element_find_impl [inlined]; _elementtree_Element_find [/opt/python-3.12.3/lib/python3.12/lib-dynload/_elementtree.cpython-312-aarch64-linux-gnu.so]; method_vectorcall_FASTCALL_KEYWORDS_METHOD [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 0.6% | 0.5% / 0.7% | 0.0% | M-XML-PARSE | M-PY-INTERPRETER | 0.6% | shared-native-mechanism-and-stack-prefix |
| `xlsx-verify` | /opt/python-3.12.3/lib/libpython3.12.so.1.0 | `_PyGCHead_NEXT` / `deduce_unreachable`; `_PyGCHead_NEXT [inlined]; update_refs [inlined]; deduce_unreachable [/opt/python-3.12.3/lib/libpython3.12.so.1.0]; gc_collect_main [/opt/python-3.12.3/lib/libpython3.12.so.1.0]` | 0.5% | 0.5% / 0.5% | 0.0% | M-PY-GC | M-PY-GC, M-PY-INTERPRETER | 0.5% | shared-native-mechanism-and-stack-prefix |

### 阈值余量

| 配置 | 列出权重 | 阈值以下/未列出 | 未知总权重 | 旧定义机制候选（无切片样本） | 分类总和 |
|---|---:|---:|---:|---:|---:|
| opm-n1 | 41.1% | 58.9% | 3.3% | 0.0% | 100.0% |
| opm-n10 | 46.6% | 53.4% | 2.9% | 0.0% | 100.0% |
| irs_w4-n1 | 43.9% | 56.1% | 3.0% | 0.0% | 100.0% |
| irs_w4-n10 | 48.9% | 51.1% | 3.1% | 0.0% | 100.0% |
| sba1919-n1 | 51.3% | 48.7% | 2.5% | 0.0% | 100.0% |
| sba1919-n10 | 53.9% | 46.1% | 2.8% | 0.0% | 100.0% |
| tlc | 12.4% | 87.6% | 2.1% | 0.0% | 100.0% |
| retail | 22.3% | 77.7% | 3.1% | 0.0% | 100.0% |
| manufacturing | 20.9% | 79.1% | 6.9% | 0.0% | 100.0% |
| hr | 14.0% | 86.0% | 5.0% | 0.0% | 100.0% |

## 7. 旧切片逐项执行路径核对

执行路径依据采样时刻的实际 argv/父进程 argv，依次核实 Docker 安装路径、runner seed→workspace 复制和精确 recipe 写入；角色名或 basename 本身不构成匹配。source context 不自动作为执行脚本。路径匹配和机制归属是独立证据。

来源审计：Dockerfile `COPY legacy/document-oe/ /opt/document-bench/`；runner SHA256 `3623f72779249b9cc95517adc09064f96286d02105e1793cf09733e20f771e80`。计划镜像 `sha256:d258914a7b0094de2ba1a06281e6c6150060a13fc73603e1bc7c9292285ec702` 验收状态 `passed (image-internal, no host source mount)`，文件 `43/43 match the frozen lock`；本次采集记录的实际 image ID 仍未知。旧 OPM/TLC `source=None`，seed 分别来自 `/opt/document-bench/pdf`、`/opt/document-bench/xlsx`，runner reset 通过 copytree 放入 workspace。

| 核心来源争议 | 按实际入口重建的来源 | 旧冻结 hash | 仓库来源 hash | 结论 |
|---|---|---|---|---|
| PDF-S6 | `/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/input/verify_pdf_batch.py` → `legacy/document-oe/pdf/input/verify_pdf_batch.py` | `691b63fac6bef80848bfc5b5c78bd6bf6dd5995e230f20a747beeaa1db6d058a` | `691b63fac6bef80848bfc5b5c78bd6bf6dd5995e230f20a747beeaa1db6d058a` | hash verified; source snapshot 不是该入口的执行来源 |
| X-S4 | `/root/.openclaw/skills/xlsx/scripts/recalc.py` → `legacy/document-oe/skills/xlsx/scripts/recalc.py` | `b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3` | `b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3` | hash verified; source snapshot 不是该入口的执行来源 |
| X-S7 | `/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01/input/verify_xlsx_enhanced.py` → `legacy/document-oe/xlsx/input/verify_xlsx_enhanced.py` | `cbf9fc9de5a88666750d41f610a9c3d92d32ed65d2acd73f565179487ea71467` | `cbf9fc9de5a88666750d41f610a9c3d92d32ed65d2acd73f565179487ea71467` | hash verified; source snapshot 不是该入口的执行来源 |

| Slice | 配置/重复 | 状态 | period 份额 | 实际脚本/命令 | 来源等级及 hash/推导 | 未匹配原因 |
|---|---|---:|---:|---|---|---|
| PDF-S1 | opm-n1/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 8.0% | `/root/.openclaw/skills/pdf/scripts/check_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/skills/pdf; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/skills/pdf; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=True |  |
| PDF-S2 | opm-n1/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 8.4% | `/root/.openclaw/skills/pdf/scripts/extract_form_field_info.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/skills/pdf; frozen=bb235b36f497bbb1c7c6821cecf527bbba7213520de11219da99f7b13a38c109; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/extract_form_field_info.py; cwd_chain=True |  |
| PDF-S3 | opm-n1/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 20.3% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/skills/pdf; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=True; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S4 | opm-n1/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 19.3% | `/root/.openclaw/skills/pdf/scripts/fill_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=d140872c2e92e41b1e05370ae8d270c5b7f5ebdf55d9905f03bc974a9c708ff5; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/fill_fillable_fields.py; cwd_chain=False |  |
| PDF-S5 | opm-n1/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 24.0% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S6 | opm-n1/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 15.7% | `/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/input/verify_pdf_batch.py` | reconstructed_from_dataset_seed_and_workspace_reset; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01; frozen=691b63fac6bef80848bfc5b5c78bd6bf6dd5995e230f20a747beeaa1db6d058a; repo_hash_ok=True; origin=runner-seed-copy; source=legacy/document-oe/pdf/input/verify_pdf_batch.py; cwd_chain=True |  |
| PDF-S1 | opm-n1/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 7.3% | `/root/.openclaw/skills/pdf/scripts/check_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/skills/pdf; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/skills/pdf; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=True |  |
| PDF-S2 | opm-n1/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 9.4% | `/root/.openclaw/skills/pdf/scripts/extract_form_field_info.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/skills/pdf; frozen=bb235b36f497bbb1c7c6821cecf527bbba7213520de11219da99f7b13a38c109; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/extract_form_field_info.py; cwd_chain=True |  |
| PDF-S3 | opm-n1/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 25.0% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/skills/pdf; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=True; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S4 | opm-n1/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 18.5% | `/root/.openclaw/skills/pdf/scripts/fill_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=d140872c2e92e41b1e05370ae8d270c5b7f5ebdf55d9905f03bc974a9c708ff5; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/fill_fillable_fields.py; cwd_chain=False |  |
| PDF-S5 | opm-n1/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 23.9% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S6 | opm-n1/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 12.8% | `/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/input/verify_pdf_batch.py` | reconstructed_from_dataset_seed_and_workspace_reset; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01; frozen=691b63fac6bef80848bfc5b5c78bd6bf6dd5995e230f20a747beeaa1db6d058a; repo_hash_ok=True; origin=runner-seed-copy; source=legacy/document-oe/pdf/input/verify_pdf_batch.py; cwd_chain=True |  |
| PDF-S1 | opm-n10/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 1.5% | `/root/.openclaw/skills/pdf/scripts/check_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/skills/pdf; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/skills/pdf; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=True |  |
| PDF-S2 | opm-n10/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 1.5% | `/root/.openclaw/skills/pdf/scripts/extract_form_field_info.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/skills/pdf; frozen=bb235b36f497bbb1c7c6821cecf527bbba7213520de11219da99f7b13a38c109; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/extract_form_field_info.py; cwd_chain=True |  |
| PDF-S3 | opm-n10/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 4.3% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/skills/pdf; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=True; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S4 | opm-n10/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 35.2% | `/root/.openclaw/skills/pdf/scripts/fill_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=d140872c2e92e41b1e05370ae8d270c5b7f5ebdf55d9905f03bc974a9c708ff5; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/fill_fillable_fields.py; cwd_chain=False |  |
| PDF-S5 | opm-n10/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 45.6% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S6 | opm-n10/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 11.5% | `/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/input/verify_pdf_batch.py` | reconstructed_from_dataset_seed_and_workspace_reset; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01; frozen=691b63fac6bef80848bfc5b5c78bd6bf6dd5995e230f20a747beeaa1db6d058a; repo_hash_ok=True; origin=runner-seed-copy; source=legacy/document-oe/pdf/input/verify_pdf_batch.py; cwd_chain=True |  |
| PDF-S1 | opm-n10/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 1.8% | `/root/.openclaw/skills/pdf/scripts/check_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/skills/pdf; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/skills/pdf; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=True |  |
| PDF-S2 | opm-n10/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 1.9% | `/root/.openclaw/skills/pdf/scripts/extract_form_field_info.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/skills/pdf; frozen=bb235b36f497bbb1c7c6821cecf527bbba7213520de11219da99f7b13a38c109; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/extract_form_field_info.py; cwd_chain=True |  |
| PDF-S3 | opm-n10/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 4.5% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/skills/pdf; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=True; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S4 | opm-n10/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 34.9% | `/root/.openclaw/skills/pdf/scripts/fill_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=d140872c2e92e41b1e05370ae8d270c5b7f5ebdf55d9905f03bc974a9c708ff5; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/fill_fillable_fields.py; cwd_chain=False |  |
| PDF-S5 | opm-n10/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 46.1% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S6 | opm-n10/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 10.7% | `/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/input/verify_pdf_batch.py` | reconstructed_from_dataset_seed_and_workspace_reset; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01; frozen=691b63fac6bef80848bfc5b5c78bd6bf6dd5995e230f20a747beeaa1db6d058a; repo_hash_ok=True; origin=runner-seed-copy; source=legacy/document-oe/pdf/input/verify_pdf_batch.py; cwd_chain=True |  |
| PDF-S1 | irs_w4-n1/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 3.2% | `/root/.openclaw/skills/pdf/scripts/check_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-IRSW4-01; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-IRSW4-01; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=True |  |
| PDF-S2 | irs_w4-n1/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 4.5% | `/root/.openclaw/skills/pdf/scripts/extract_form_field_info.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=bb235b36f497bbb1c7c6821cecf527bbba7213520de11219da99f7b13a38c109; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/extract_form_field_info.py; cwd_chain=False |  |
| PDF-S3 | irs_w4-n1/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 24.5% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S4 | irs_w4-n1/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 18.5% | `/root/.openclaw/skills/pdf/scripts/fill_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=d140872c2e92e41b1e05370ae8d270c5b7f5ebdf55d9905f03bc974a9c708ff5; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/fill_fillable_fields.py; cwd_chain=False |  |
| PDF-S5 | irs_w4-n1/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 24.0% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S6 | irs_w4-n1/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| PDF-S1 | irs_w4-n1/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 3.8% | `/root/.openclaw/skills/pdf/scripts/check_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-IRSW4-01; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-IRSW4-01; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=True |  |
| PDF-S2 | irs_w4-n1/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 5.4% | `/root/.openclaw/skills/pdf/scripts/extract_form_field_info.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=bb235b36f497bbb1c7c6821cecf527bbba7213520de11219da99f7b13a38c109; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/extract_form_field_info.py; cwd_chain=False |  |
| PDF-S3 | irs_w4-n1/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 24.7% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S4 | irs_w4-n1/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 17.5% | `/root/.openclaw/skills/pdf/scripts/fill_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=d140872c2e92e41b1e05370ae8d270c5b7f5ebdf55d9905f03bc974a9c708ff5; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/fill_fillable_fields.py; cwd_chain=False |  |
| PDF-S5 | irs_w4-n1/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 25.1% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S6 | irs_w4-n1/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| PDF-S1 | irs_w4-n10/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 0.6% | `/root/.openclaw/skills/pdf/scripts/check_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-IRSW4-01; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-IRSW4-01; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=True |  |
| PDF-S2 | irs_w4-n10/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 0.8% | `/root/.openclaw/skills/pdf/scripts/extract_form_field_info.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=bb235b36f497bbb1c7c6821cecf527bbba7213520de11219da99f7b13a38c109; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/extract_form_field_info.py; cwd_chain=False |  |
| PDF-S3 | irs_w4-n10/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 3.2% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S4 | irs_w4-n10/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 33.7% | `/root/.openclaw/skills/pdf/scripts/fill_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=d140872c2e92e41b1e05370ae8d270c5b7f5ebdf55d9905f03bc974a9c708ff5; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/fill_fillable_fields.py; cwd_chain=False |  |
| PDF-S5 | irs_w4-n10/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 47.7% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S6 | irs_w4-n10/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| PDF-S1 | irs_w4-n10/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 0.9% | `/root/.openclaw/skills/pdf/scripts/check_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-IRSW4-01; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-IRSW4-01; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=True |  |
| PDF-S2 | irs_w4-n10/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 1.0% | `/root/.openclaw/skills/pdf/scripts/extract_form_field_info.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=bb235b36f497bbb1c7c6821cecf527bbba7213520de11219da99f7b13a38c109; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/extract_form_field_info.py; cwd_chain=False |  |
| PDF-S3 | irs_w4-n10/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 4.1% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S4 | irs_w4-n10/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 32.7% | `/root/.openclaw/skills/pdf/scripts/fill_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=d140872c2e92e41b1e05370ae8d270c5b7f5ebdf55d9905f03bc974a9c708ff5; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/fill_fillable_fields.py; cwd_chain=False |  |
| PDF-S5 | irs_w4-n10/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 48.4% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S6 | irs_w4-n10/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| PDF-S1 | sba1919-n1/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 3.3% | `/root/.openclaw/skills/pdf/scripts/check_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-SBA1919-01; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-SBA1919-01; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=True |  |
| PDF-S2 | sba1919-n1/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 4.7% | `/root/.openclaw/skills/pdf/scripts/extract_form_field_info.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=bb235b36f497bbb1c7c6821cecf527bbba7213520de11219da99f7b13a38c109; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/extract_form_field_info.py; cwd_chain=False |  |
| PDF-S3 | sba1919-n1/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 26.5% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S4 | sba1919-n1/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 14.1% | `/root/.openclaw/skills/pdf/scripts/fill_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=d140872c2e92e41b1e05370ae8d270c5b7f5ebdf55d9905f03bc974a9c708ff5; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/fill_fillable_fields.py; cwd_chain=False |  |
| PDF-S5 | sba1919-n1/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 26.2% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S6 | sba1919-n1/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| PDF-S1 | sba1919-n1/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 5.4% | `/root/.openclaw/skills/pdf/scripts/check_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-SBA1919-01; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-SBA1919-01; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=True |  |
| PDF-S2 | sba1919-n1/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 5.1% | `/root/.openclaw/skills/pdf/scripts/extract_form_field_info.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=bb235b36f497bbb1c7c6821cecf527bbba7213520de11219da99f7b13a38c109; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/extract_form_field_info.py; cwd_chain=False |  |
| PDF-S3 | sba1919-n1/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 24.9% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S4 | sba1919-n1/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 13.4% | `/root/.openclaw/skills/pdf/scripts/fill_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=d140872c2e92e41b1e05370ae8d270c5b7f5ebdf55d9905f03bc974a9c708ff5; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/fill_fillable_fields.py; cwd_chain=False |  |
| PDF-S5 | sba1919-n1/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 26.5% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S6 | sba1919-n1/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| PDF-S1 | sba1919-n10/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 1.1% | `/root/.openclaw/skills/pdf/scripts/check_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-SBA1919-01; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-SBA1919-01; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=True |  |
| PDF-S2 | sba1919-n10/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 1.0% | `/root/.openclaw/skills/pdf/scripts/extract_form_field_info.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=bb235b36f497bbb1c7c6821cecf527bbba7213520de11219da99f7b13a38c109; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/extract_form_field_info.py; cwd_chain=False |  |
| PDF-S3 | sba1919-n10/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 4.7% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S4 | sba1919-n10/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 24.2% | `/root/.openclaw/skills/pdf/scripts/fill_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=d140872c2e92e41b1e05370ae8d270c5b7f5ebdf55d9905f03bc974a9c708ff5; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/fill_fillable_fields.py; cwd_chain=False |  |
| PDF-S5 | sba1919-n10/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 49.5% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S6 | sba1919-n10/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| PDF-S1 | sba1919-n10/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 1.1% | `/root/.openclaw/skills/pdf/scripts/check_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-SBA1919-01; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-SBA1919-01; frozen=1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/check_fillable_fields.py; cwd_chain=True |  |
| PDF-S2 | sba1919-n10/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 1.1% | `/root/.openclaw/skills/pdf/scripts/extract_form_field_info.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=bb235b36f497bbb1c7c6821cecf527bbba7213520de11219da99f7b13a38c109; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/extract_form_field_info.py; cwd_chain=False |  |
| PDF-S3 | sba1919-n10/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 4.5% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S4 | sba1919-n10/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 24.9% | `/root/.openclaw/skills/pdf/scripts/fill_fillable_fields.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=d140872c2e92e41b1e05370ae8d270c5b7f5ebdf55d9905f03bc974a9c708ff5; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/fill_fillable_fields.py; cwd_chain=False |  |
| PDF-S5 | sba1919-n10/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 49.2% | `/root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/pdf/scripts/convert_pdf_to_images.py; cwd_chain=False; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| PDF-S6 | sba1919-n10/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S1 | tlc/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 12.6% | `/opt/document-bench/bin/inspect_xlsx_structure.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=32c72802e3710b260dcbb782933a5241f0dedc9be246df2dd226cf573a6681ab; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/bin/inspect_xlsx_structure.py; cwd_chain=False |  |
| X-S2 | tlc/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 10.4% | `/opt/document-bench/bin/inspect_xlsx_features.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=3d14f70a982370cf8992540b983fe91e7d8ad2c036dc67767960377e3e58de05; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/bin/inspect_xlsx_features.py; cwd_chain=False |  |
| X-S3 | tlc/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 21.8% | `/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01/enhance_workbook.py` | reconstructed_from_dataset_seed_and_workspace_reset; cwd=None; frozen=774a41787ea3b89fbaa7ef6095505a393dc35ed52121c052442aa11978cbbbbe; repo_hash_ok=True; origin=runner-seed-copy; source=legacy/document-oe/xlsx/enhance_workbook.py; cwd_chain=False; timestamped ppid relation plus source-matched child; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| X-S4 | tlc/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 19.3% | `/root/.openclaw/skills/xlsx/scripts/recalc.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=True; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=True |  |
| X-S5 | tlc/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 8.2% | `/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01/inspect_xlsx_formulas.py` | reconstructed_from_dataset_seed_and_workspace_reset; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01; frozen=d73007133f7389edad1229fc4c6e904d127cd2839dd0e672b3d740207f42419a; repo_hash_ok=True; origin=runner-seed-copy; source=legacy/document-oe/xlsx/inspect_xlsx_formulas.py; cwd_chain=False; reconstructed_from_dataset_seed_and_workspace_reset; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01; frozen=d73007133f7389edad1229fc4c6e904d127cd2839dd0e672b3d740207f42419a; repo_hash_ok=True; origin=runner-seed-copy; source=legacy/document-oe/xlsx/inspect_xlsx_formulas.py; cwd_chain=True |  |
| X-S6 | tlc/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 8.1% | `/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01/inspect_xlsx_cached_values.py` | reconstructed_from_dataset_seed_and_workspace_reset; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01; frozen=67aa196bfcc321869f3b786b4a15e37ab3f1c55bb59428948e6881402bf8d556; repo_hash_ok=True; origin=runner-seed-copy; source=legacy/document-oe/xlsx/inspect_xlsx_cached_values.py; cwd_chain=False; reconstructed_from_dataset_seed_and_workspace_reset; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01; frozen=67aa196bfcc321869f3b786b4a15e37ab3f1c55bb59428948e6881402bf8d556; repo_hash_ok=True; origin=runner-seed-copy; source=legacy/document-oe/xlsx/inspect_xlsx_cached_values.py; cwd_chain=True |  |
| X-S7 | tlc/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 10.2% | `/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01/input/verify_xlsx_enhanced.py` | reconstructed_from_dataset_seed_and_workspace_reset; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01; frozen=cbf9fc9de5a88666750d41f610a9c3d92d32ed65d2acd73f565179487ea71467; repo_hash_ok=True; origin=runner-seed-copy; source=legacy/document-oe/xlsx/input/verify_xlsx_enhanced.py; cwd_chain=False; reconstructed_from_dataset_seed_and_workspace_reset; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01; frozen=cbf9fc9de5a88666750d41f610a9c3d92d32ed65d2acd73f565179487ea71467; repo_hash_ok=True; origin=runner-seed-copy; source=legacy/document-oe/xlsx/input/verify_xlsx_enhanced.py; cwd_chain=True |  |
| X-S8 | tlc/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 8.6% | `/opt/document-bench/bin/write_xlsx_summary.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=f5e7102cb64dd6bb05d89b29998f98c88b48ade3d3f0701d5e4c295a313c903a; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/bin/write_xlsx_summary.py; cwd_chain=False |  |
| X-S1 | tlc/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 12.3% | `/opt/document-bench/bin/inspect_xlsx_structure.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=32c72802e3710b260dcbb782933a5241f0dedc9be246df2dd226cf573a6681ab; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/bin/inspect_xlsx_structure.py; cwd_chain=False |  |
| X-S2 | tlc/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 10.4% | `/opt/document-bench/bin/inspect_xlsx_features.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=3d14f70a982370cf8992540b983fe91e7d8ad2c036dc67767960377e3e58de05; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/bin/inspect_xlsx_features.py; cwd_chain=False |  |
| X-S3 | tlc/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 21.9% | `/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01/enhance_workbook.py` | reconstructed_from_dataset_seed_and_workspace_reset; cwd=None; frozen=774a41787ea3b89fbaa7ef6095505a393dc35ed52121c052442aa11978cbbbbe; repo_hash_ok=True; origin=runner-seed-copy; source=legacy/document-oe/xlsx/enhance_workbook.py; cwd_chain=False; timestamped ppid relation plus source-matched child; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False |  |
| X-S4 | tlc/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 19.4% | `/root/.openclaw/skills/xlsx/scripts/recalc.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=True; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=True |  |
| X-S5 | tlc/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 8.3% | `/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01/inspect_xlsx_formulas.py` | reconstructed_from_dataset_seed_and_workspace_reset; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01; frozen=d73007133f7389edad1229fc4c6e904d127cd2839dd0e672b3d740207f42419a; repo_hash_ok=True; origin=runner-seed-copy; source=legacy/document-oe/xlsx/inspect_xlsx_formulas.py; cwd_chain=False; reconstructed_from_dataset_seed_and_workspace_reset; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01; frozen=d73007133f7389edad1229fc4c6e904d127cd2839dd0e672b3d740207f42419a; repo_hash_ok=True; origin=runner-seed-copy; source=legacy/document-oe/xlsx/inspect_xlsx_formulas.py; cwd_chain=True |  |
| X-S6 | tlc/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 8.1% | `/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01/inspect_xlsx_cached_values.py` | reconstructed_from_dataset_seed_and_workspace_reset; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01; frozen=67aa196bfcc321869f3b786b4a15e37ab3f1c55bb59428948e6881402bf8d556; repo_hash_ok=True; origin=runner-seed-copy; source=legacy/document-oe/xlsx/inspect_xlsx_cached_values.py; cwd_chain=False; reconstructed_from_dataset_seed_and_workspace_reset; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01; frozen=67aa196bfcc321869f3b786b4a15e37ab3f1c55bb59428948e6881402bf8d556; repo_hash_ok=True; origin=runner-seed-copy; source=legacy/document-oe/xlsx/inspect_xlsx_cached_values.py; cwd_chain=True |  |
| X-S7 | tlc/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 10.3% | `/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01/input/verify_xlsx_enhanced.py` | reconstructed_from_dataset_seed_and_workspace_reset; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01; frozen=cbf9fc9de5a88666750d41f610a9c3d92d32ed65d2acd73f565179487ea71467; repo_hash_ok=True; origin=runner-seed-copy; source=legacy/document-oe/xlsx/input/verify_xlsx_enhanced.py; cwd_chain=False; reconstructed_from_dataset_seed_and_workspace_reset; cwd=/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01; frozen=cbf9fc9de5a88666750d41f610a9c3d92d32ed65d2acd73f565179487ea71467; repo_hash_ok=True; origin=runner-seed-copy; source=legacy/document-oe/xlsx/input/verify_xlsx_enhanced.py; cwd_chain=True |  |
| X-S8 | tlc/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 8.4% | `/opt/document-bench/bin/write_xlsx_summary.py` | reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=f5e7102cb64dd6bb05d89b29998f98c88b48ade3d3f0701d5e4c295a313c903a; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/bin/write_xlsx_summary.py; cwd_chain=False |  |
| X-S1 | retail/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S2 | retail/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S3 | retail/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S4 | retail/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 25.5% | `/root/.openclaw/skills/xlsx/scripts/recalc.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-RETAIL; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-RETAIL; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=True; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=True |  |
| X-S5 | retail/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S6 | retail/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S7 | retail/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S8 | retail/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S1 | retail/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S2 | retail/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S3 | retail/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S4 | retail/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 24.6% | `/root/.openclaw/skills/xlsx/scripts/recalc.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-RETAIL; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-RETAIL; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=True; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=True |  |
| X-S5 | retail/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S6 | retail/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S7 | retail/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S8 | retail/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S1 | manufacturing/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S2 | manufacturing/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S3 | manufacturing/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S4 | manufacturing/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 28.3% | `/root/.openclaw/skills/xlsx/scripts/recalc.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-MANUFACTURING; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-MANUFACTURING; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=True; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=True |  |
| X-S5 | manufacturing/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S6 | manufacturing/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S7 | manufacturing/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S8 | manufacturing/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S1 | manufacturing/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S2 | manufacturing/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S3 | manufacturing/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S4 | manufacturing/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 26.5% | `/root/.openclaw/skills/xlsx/scripts/recalc.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-MANUFACTURING; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-MANUFACTURING; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=True; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=True |  |
| X-S5 | manufacturing/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S6 | manufacturing/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S7 | manufacturing/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S8 | manufacturing/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S1 | hr/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S2 | hr/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S3 | hr/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S4 | hr/r1 | identity_path_mapped_and_sampled_runtime_hash_unknown | 18.2% | `/root/.openclaw/skills/xlsx/scripts/recalc.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-HR; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-HR; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=True; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=True |  |
| X-S5 | hr/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S6 | hr/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S7 | hr/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S8 | hr/r1 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S1 | hr/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S2 | hr/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S3 | hr/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S4 | hr/r2 | identity_path_mapped_and_sampled_runtime_hash_unknown | 17.9% | `/root/.openclaw/skills/xlsx/scripts/recalc.py` | reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-HR; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-HR; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=True; direct process identity/ppid; slice definition includes subtree; cwd=None; frozen=None; repo_hash_ok=False; origin=None; source=None; cwd_chain=False; reconstructed_from_docker_copy_and_runner_link; cwd=None; frozen=b4d04cd56ba59c67b15e6745bf8a825c7741861692d863e2eca81f7d704186c3; repo_hash_ok=True; origin=docker-installed-legacy; source=legacy/document-oe/skills/xlsx/scripts/recalc.py; cwd_chain=True |  |
| X-S5 | hr/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S6 | hr/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S7 | hr/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |
| X-S8 | hr/r2 | no_matching_identity_evidence | 0.0% | `—` | 无直接/候选来源证据 | no Python script operand resolved to this frozen source in timestamped identities |

完整 14 项汇总及来源链见 `processed/legacy-slice-source-map.json`。安装/seed/recipe hash 为按冻结运行规则重建，不是历史进程直接采集的文件 hash。运行时来源文件与旧切片内容一致时计路径匹配；只有 source snapshot 同名 hash 不同不构成冲突。父子范围仅按切片定义传递；PID 观察窗口和无退出时间戳的限制见来源 JSON。

## 8. strace 汇总（调用次数与累计 syscall 时间分开）

`-c` seconds 为 syscall 累计耗时，可能包含阻塞等待，不是内核 CPU 时间；aggregate 结果不能证明 futex 来自 LibreOffice 进程。

| Dataset | futex calls / share | futex seconds / share | calls 总和核对 | calls 排名前三 | 进程归属 |
|---|---:|---:|---|---|---|
| opm-n10 | 948 / 0.1% | 0.026257s / 0.2% | 1061478 = total 1061478 (一致) | write=275253, pread64=196735, read=146525 | insufficient: aggregate strace -c output has no per-process attribution |
| retail | 692512 / 38.8% | 876.696429s / 88.5% | 1784034 = total 1784034 (一致) | futex=692512, mprotect=187843, rt_sigprocmask=165177 | insufficient: aggregate strace -c output has no per-process attribution |
| manufacturing | 348979 / 25.0% | 420.266271s / 85.5% | 1393148 = total 1393148 (一致) | futex=348979, newfstatat=200177, rt_sigprocmask=86507 | insufficient: aggregate strace -c output has no per-process attribution |
| hr | 190073 / 19.7% | 246.220237s / 84.2% | 965596 = total 965596 (一致) | futex=190073, newfstatat=160946, read=69087 | insufficient: aggregate strace -c output has no per-process attribution |

## 9. 内联帧修正前后影响

解析器仅在首帧与连续内联帧同地址时，使用后续实体帧的 DSO；保留首个内联函数作为热点。未知叶节点不继承其他地址的调用者 DSO。下表与旧派生库分布比较，原始采样 period 未改变。

| Dataset | Repeat | 旧 unknown DSO | 新 unknown DSO | 变化 | libpython 变化 | XML DSO 变化 |
|---|---|---:|---:|---:|---:|---:|
| opm-n1 | r1 | 35.8% | 3.3% | -32.5 pp | +31.2 pp | +0.0 pp |
| opm-n1 | r2 | 34.9% | 2.9% | -31.9 pp | +30.9 pp | +0.0 pp |
| irs_w4-n1 | r1 | 34.8% | 2.9% | -31.9 pp | +30.7 pp | +0.0 pp |
| irs_w4-n1 | r2 | 36.9% | 2.9% | -34.1 pp | +32.0 pp | +0.0 pp |
| sba1919-n1 | r1 | 28.6% | 2.2% | -26.4 pp | +25.2 pp | +0.0 pp |
| sba1919-n1 | r2 | 31.8% | 2.5% | -29.3 pp | +27.6 pp | +0.0 pp |
| opm-n10 | r1 | 33.2% | 2.6% | -30.5 pp | +29.2 pp | +0.0 pp |
| opm-n10 | r2 | 33.8% | 2.6% | -31.3 pp | +28.7 pp | +0.0 pp |
| irs_w4-n10 | r1 | 30.3% | 3.2% | -27.1 pp | +25.2 pp | +0.0 pp |
| irs_w4-n10 | r2 | 31.9% | 2.2% | -29.7 pp | +27.4 pp | +0.0 pp |
| sba1919-n10 | r1 | 27.6% | 2.7% | -24.9 pp | +22.4 pp | +0.0 pp |
| sba1919-n10 | r2 | 27.9% | 2.5% | -25.3 pp | +23.1 pp | +0.0 pp |
| tlc | r1 | 59.2% | 2.1% | -57.1 pp | +49.0 pp | +5.8 pp |
| tlc | r2 | 59.8% | 2.1% | -57.7 pp | +49.5 pp | +6.2 pp |
| retail | r1 | 52.2% | 2.3% | -50.0 pp | +41.5 pp | +5.5 pp |
| retail | r2 | 51.5% | 2.6% | -49.0 pp | +40.4 pp | +5.7 pp |
| manufacturing | r1 | 55.0% | 4.7% | -50.3 pp | +42.1 pp | +2.2 pp |
| manufacturing | r2 | 54.6% | 3.8% | -50.8 pp | +43.6 pp | +3.9 pp |
| hr | r1 | 58.9% | 4.1% | -54.8 pp | +46.5 pp | +5.5 pp |
| hr | r2 | 57.9% | 2.9% | -55.1 pp | +47.5 pp | +5.5 pp |

| Dataset | Repeat | ROI 样本 | 内联恢复 period | 真未知 DSO period | 内联实体未恢复 | 未解析符号 | 空栈 | Lost 样本 | malformed frame 行 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| opm-n1 | r1 | 2194 | 32.5% | 0.3% | 2.9% | 0.4% | 0.0% | 0 | 0 |
| opm-n1 | r2 | 2257 | 31.9% | 0.3% | 2.6% | 0.7% | 0.0% | 0 | 0 |
| irs_w4-n1 | r1 | 2980 | 31.9% | 0.4% | 2.5% | 0.5% | 0.0% | 0 | 0 |
| irs_w4-n1 | r2 | 2860 | 34.1% | 0.2% | 2.7% | 0.3% | 0.0% | 0 | 0 |
| sba1919-n1 | r1 | 3407 | 26.4% | 0.3% | 1.9% | 0.4% | 0.0% | 0 | 0 |
| sba1919-n1 | r2 | 3962 | 29.3% | 0.4% | 2.1% | 0.6% | 0.0% | 0 | 0 |
| opm-n10 | r1 | 3212 | 30.5% | 0.8% | 1.8% | 1.0% | 0.0% | 0 | 0 |
| opm-n10 | r2 | 3201 | 31.3% | 0.6% | 2.0% | 1.1% | 0.0% | 0 | 0 |
| irs_w4-n10 | r1 | 3991 | 27.1% | 0.4% | 2.8% | 0.8% | 0.0% | 0 | 0 |
| irs_w4-n10 | r2 | 3919 | 29.7% | 0.2% | 2.0% | 0.5% | 0.0% | 0 | 0 |
| sba1919-n10 | r1 | 5753 | 24.9% | 0.4% | 2.3% | 0.6% | 0.0% | 0 | 0 |
| sba1919-n10 | r2 | 6177 | 25.3% | 0.3% | 2.3% | 0.3% | 0.0% | 0 | 0 |
| tlc | r1 | 37327 | 57.1% | 0.1% | 2.0% | 0.2% | 0.0% | 57 | 0 |
| tlc | r2 | 36295 | 57.7% | 0.1% | 2.0% | 0.1% | 0.0% | 115 | 0 |
| retail | r1 | 327607 | 50.0% | 0.2% | 2.1% | 1.1% | 0.0% | 2520 | 0 |
| retail | r2 | 341303 | 49.0% | 0.1% | 2.5% | 0.6% | 0.0% | 1360 | 0 |
| manufacturing | r1 | 182542 | 50.3% | 0.1% | 4.6% | 3.0% | 0.0% | 469 | 0 |
| manufacturing | r2 | 167715 | 50.8% | 0.2% | 3.6% | 2.5% | 0.0% | 633 | 0 |
| hr | r1 | 89613 | 54.8% | 0.4% | 3.7% | 2.1% | 0.0% | 170 | 0 |
| hr | r2 | 97838 | 55.1% | 0.2% | 2.7% | 1.6% | 0.0% | 359 | 0 |

## 10. 旧结论逐条验证

| Claim | 旧结论（原文） | Dataset | 当前对照与定量证据 | 状态 | 判定依据 | 证据路径 | 适用边界 |
|---|---|---|---|---|---|---|---|
| CLM-01 | PDF 场景进程构成：全部 python3 进程约占 cycles:u 的 90.6%，pdftoppm 约 9.2%（其余 pdfinfo/bash 合计 <0.2%）。 | opm-n1 | Python-process share repeats=[0.8495, 0.8598]; pdftoppm=[0.1285, 0.1193]; OPM same-scale=[0.8495, 0.8598] | partially-supported | Dominance is checked per repeat. OPM historical single-run points must fall inside the current OPM repeat ranges; new PDFs must overlap current OPM ranges. No uniform percentage band is used. | processed/opm-n1.json (native r1/r2 period aggregates); raw/{config}/r{1,2}/out/samples.jsonl; legacy/evidence/ANALYSIS-python3123.md#section-4 | N=1 PDF only; values describe current 8-CPU workload; process role grouping follows argv identity. |
| CLM-01 | PDF 场景进程构成：全部 python3 进程约占 cycles:u 的 90.6%，pdftoppm 约 9.2%（其余 pdfinfo/bash 合计 <0.2%）。 | irs_w4-n1 | Python-process share repeats=[0.8651, 0.8839]; pdftoppm=[0.1087, 0.1144]; OPM same-scale=[0.8495, 0.8598] | partially-supported | Dominance is checked per repeat. OPM historical single-run points must fall inside the current OPM repeat ranges; new PDFs must overlap current OPM ranges. No uniform percentage band is used. | processed/irs_w4-n1.json (native r1/r2 period aggregates); raw/{config}/r{1,2}/out/samples.jsonl; legacy/evidence/ANALYSIS-python3123.md#section-4 | N=1 PDF only; values describe current 8-CPU workload; process role grouping follows argv identity. |
| CLM-01 | PDF 场景进程构成：全部 python3 进程约占 cycles:u 的 90.6%，pdftoppm 约 9.2%（其余 pdfinfo/bash 合计 <0.2%）。 | sba1919-n1 | Python-process share repeats=[0.8444, 0.8448]; pdftoppm=[0.1518, 0.1525]; OPM same-scale=[0.8495, 0.8598] | partially-supported | Dominance is checked per repeat. OPM historical single-run points must fall inside the current OPM repeat ranges; new PDFs must overlap current OPM ranges. No uniform percentage band is used. | processed/sba1919-n1.json (native r1/r2 period aggregates); raw/{config}/r{1,2}/out/samples.jsonl; legacy/evidence/ANALYSIS-python3123.md#section-4 | N=1 PDF only; values describe current 8-CPU workload; process role grouping follows argv identity. |
| CLM-02 | PDF 库层构成：libpython ≈53.6%，zlib ≈18.1%，Pillow _imaging ≈15.2%，Poppler ≈6.3%，FreeType ≈1.9%。 | opm-n1 | libpython repeats=[0.5068212395226264, 0.5002905946916232] same-env OPM=[0.5068212395226264, 0.5002905946916232]; zlib repeats=[0.1508858634947676, 0.16485617567038785] same-env OPM=[0.1508858634947676, 0.16485617567038785]; pillow repeats=[0.15636568399335884, 0.1530120940681738] same-env OPM=[0.15636568399335884, 0.1530120940681738]; poppler repeats=[0.06684849343847356, 0.07074537866952471] same-env OPM=[0.06684849343847356, 0.07074537866952471]; freetype repeats=[0.035140684867701756, 0.021937611821556176] same-env OPM=[0.035140684867701756, 0.021937611821556176] | partially-supported | All expected DSOs must overlap OPM's same-environment repeat ranges for new PDFs; the OPM baseline is checked against historical single-run points. No universal percentage tolerance is applied. | processed/opm-n1.json (native r1/r2 period aggregates); processed/all-profiles.json; legacy/evidence/ANALYSIS-python3123.md#section-4 | N=1 PDF; same leaf-DSO categorization after inline recovery; percentages are sample-period estimates. |
| CLM-02 | PDF 库层构成：libpython ≈53.6%，zlib ≈18.1%，Pillow _imaging ≈15.2%，Poppler ≈6.3%，FreeType ≈1.9%。 | irs_w4-n1 | libpython repeats=[0.49258071514781887, 0.47634142678900737] same-env OPM=[0.5068212395226264, 0.5002905946916232]; zlib repeats=[0.18101964580884455, 0.1912575618841112] same-env OPM=[0.1508858634947676, 0.16485617567038785]; pillow repeats=[0.16894994423354787, 0.16976039300239112] same-env OPM=[0.15636568399335884, 0.1530120940681738]; poppler repeats=[0.059738033685423346, 0.04985144236815434] same-env OPM=[0.06684849343847356, 0.07074537866952471]; freetype repeats=[0.03141399505368916, 0.04446364040219707] same-env OPM=[0.035140684867701756, 0.021937611821556176] | partially-supported | All expected DSOs must overlap OPM's same-environment repeat ranges for new PDFs; the OPM baseline is checked against historical single-run points. No universal percentage tolerance is applied. | processed/irs_w4-n1.json (native r1/r2 period aggregates); processed/all-profiles.json; legacy/evidence/ANALYSIS-python3123.md#section-4 | N=1 PDF; same leaf-DSO categorization after inline recovery; percentages are sample-period estimates. |
| CLM-02 | PDF 库层构成：libpython ≈53.6%，zlib ≈18.1%，Pillow _imaging ≈15.2%，Poppler ≈6.3%，FreeType ≈1.9%。 | sba1919-n1 | libpython repeats=[0.43775609525723347, 0.45392470302596677] same-env OPM=[0.5068212395226264, 0.5002905946916232]; zlib repeats=[0.18107746913599215, 0.17795934005329447] same-env OPM=[0.1508858634947676, 0.16485617567038785]; pillow repeats=[0.18631287936652707, 0.16864226387943498] same-env OPM=[0.15636568399335884, 0.1530120940681738]; poppler repeats=[0.0929710162170343, 0.0927490003812872] same-env OPM=[0.06684849343847356, 0.07074537866952471]; freetype repeats=[0.05080734738725318, 0.050750384020717076] same-env OPM=[0.035140684867701756, 0.021937611821556176] | partially-supported | All expected DSOs must overlap OPM's same-environment repeat ranges for new PDFs; the OPM baseline is checked against historical single-run points. No universal percentage tolerance is applied. | processed/sba1919-n1.json (native r1/r2 period aggregates); processed/all-profiles.json; legacy/evidence/ANALYSIS-python3123.md#section-4 | N=1 PDF; same leaf-DSO categorization after inline recovery; percentages are sample-period estimates. |
| CLM-03 | PDF Python 层：时间分布在 6 类脚本（检查/提取/模板转换/填写/填写后转换/验证），热点是 pypdf 填写、Pillow/zlib 图像处理、Poppler 渲染和最终验证，没有出现新的业务热点。 | opm-n1 | native common-mechanism share=0.6340; normalized stack-prefix fingerprint match share=0.8665; source-matched old path share=0.9623; legacy-documented mechanism without matched old-slice sample share=0.0000; single py-spy top roles=[('pdf-convert', 626), ('pdf-fill', 261), ('pdf-verify', 186), ('pdf-extract-fields', 119), ('pdf-check-fillable', 118), ('runner', 7), ('pdf-mapping-driver', 3)]; new roles=['pdf-mapping-driver'] | partially-supported | Leaf-function mechanism and eligible normalized stack-prefix fingerprints support shared native work at their respective evidence levels. Prefixes are limited to eight normalized frames, require at least four resolved frames, merge DSOs into classes, and do not establish full call paths or code identity. Neither mechanism nor prefix identity proves the same Python algorithm; single-run py-spy is contextual only and is not assigned to native cycles. The assertion that there are no new business hotspots is not established. | raw/opm-n1/pyspy/out/pyspy-roles.json; legacy/evidence/ANALYSIS-python3123.md#section-5 | N=1 PDF or one-loop/current XLSX; conclusions are Python-stack evidence only. |
| CLM-03 | PDF Python 层：时间分布在 6 类脚本（检查/提取/模板转换/填写/填写后转换/验证），热点是 pypdf 填写、Pillow/zlib 图像处理、Poppler 渲染和最终验证，没有出现新的业务热点。 | irs_w4-n1 | native common-mechanism share=0.6359; normalized stack-prefix fingerprint match share=0.5239; source-matched old path share=0.7553; legacy-documented mechanism without matched old-slice sample share=0.0000; single py-spy top roles=[('pdf-convert', 963), ('pdf-verify', 536), ('pdf-fill', 395), ('pdf-check-fillable', 58), ('pdf-extract-fields', 48), ('runner', 19), ('pdf-mapping-driver', 2)]; new roles=['pdf-mapping-driver'] | partially-supported | Leaf-function mechanism and eligible normalized stack-prefix fingerprints support shared native work at their respective evidence levels. Prefixes are limited to eight normalized frames, require at least four resolved frames, merge DSOs into classes, and do not establish full call paths or code identity. Neither mechanism nor prefix identity proves the same Python algorithm; single-run py-spy is contextual only and is not assigned to native cycles. The assertion that there are no new business hotspots is not established. | raw/irs_w4-n1/pyspy/out/pyspy-roles.json; legacy/evidence/ANALYSIS-python3123.md#section-5 | N=1 PDF or one-loop/current XLSX; conclusions are Python-stack evidence only. |
| CLM-03 | PDF Python 层：时间分布在 6 类脚本（检查/提取/模板转换/填写/填写后转换/验证），热点是 pypdf 填写、Pillow/zlib 图像处理、Poppler 渲染和最终验证，没有出现新的业务热点。 | sba1919-n1 | native common-mechanism share=0.6794; normalized stack-prefix fingerprint match share=0.5919; source-matched old path share=0.7501; legacy-documented mechanism without matched old-slice sample share=0.0000; single py-spy top roles=[('pdf-convert', 1299), ('pdf-verify', 816), ('pdf-fill', 433), ('pdf-extract-fields', 147), ('pdf-check-fillable', 114), ('runner', 10), ('pdf-mapping-driver', 4)]; new roles=['pdf-mapping-driver'] | partially-supported | Leaf-function mechanism and eligible normalized stack-prefix fingerprints support shared native work at their respective evidence levels. Prefixes are limited to eight normalized frames, require at least four resolved frames, merge DSOs into classes, and do not establish full call paths or code identity. Neither mechanism nor prefix identity proves the same Python algorithm; single-run py-spy is contextual only and is not assigned to native cycles. The assertion that there are no new business hotspots is not established. | raw/sba1919-n1/pyspy/out/pyspy-roles.json; legacy/evidence/ANALYSIS-python3123.md#section-5 | N=1 PDF or one-loop/current XLSX; conclusions are Python-stack evidence only. |
| CLM-04 | XLSX 场景进程构成：全部 python3 进程 ≈92.5%，LibreOffice 及其线程 ≈7.5% cycles:u。 | tlc | python shares=[0.9204712992198573, 0.9208758998434858]; LO shares=[0.07952143030489417, 0.07905598187462655]; same-env TLC Python shares=[0.9204712992198573, 0.9208758998434858] | partially-supported | Python dominance is checked separately. TLC historical points must lie inside current TLC repeat ranges; new XLSX datasets must overlap current TLC ranges. | processed/tlc.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-4 | XLSX datasets only; 8-CPU current runs vs historical TLC 4-CPU run. |
| CLM-04 | XLSX 场景进程构成：全部 python3 进程 ≈92.5%，LibreOffice 及其线程 ≈7.5% cycles:u。 | retail | python shares=[0.8191824150934113, 0.8218549267585824]; LO shares=[0.18059728820424598, 0.17733442828884655]; same-env TLC Python shares=[0.9204712992198573, 0.9208758998434858] | partially-supported | Python dominance is checked separately. TLC historical points must lie inside current TLC repeat ranges; new XLSX datasets must overlap current TLC ranges. | processed/retail.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-4 | XLSX datasets only; 8-CPU current runs vs historical TLC 4-CPU run. |
| CLM-04 | XLSX 场景进程构成：全部 python3 进程 ≈92.5%，LibreOffice 及其线程 ≈7.5% cycles:u。 | manufacturing | python shares=[0.7698748375835467, 0.7796812039024776]; LO shares=[0.22878137406369733, 0.21892733591339705]; same-env TLC Python shares=[0.9204712992198573, 0.9208758998434858] | partially-supported | Python dominance is checked separately. TLC historical points must lie inside current TLC repeat ranges; new XLSX datasets must overlap current TLC ranges. | processed/manufacturing.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-4 | XLSX datasets only; 8-CPU current runs vs historical TLC 4-CPU run. |
| CLM-04 | XLSX 场景进程构成：全部 python3 进程 ≈92.5%，LibreOffice 及其线程 ≈7.5% cycles:u。 | hr | python shares=[0.8394907684249829, 0.898143616520681]; LO shares=[0.10788179241803214, 0.10065987214651274]; same-env TLC Python shares=[0.9204712992198573, 0.9208758998434858] | partially-supported | Python dominance is checked separately. TLC historical points must lie inside current TLC repeat ranges; new XLSX datasets must overlap current TLC ranges. | processed/hr.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-4 | XLSX datasets only; 8-CPU current runs vs historical TLC 4-CPU run. |
| CLM-05 | XLSX 库层构成：libpython ≈79.7%，Expat ≈5.6%，_elementtree ≈3.5%，zlib ≈1.4%（LibreOffice DSO 合计约 7%）。 | tlc | libraries current repeat ranges={'libpython': [0.7856584418114911, 0.7832918434286945], 'expat-xml': [0.05742049993568176, 0.059784683709898215], 'elementtree-xml': [0.029887576366832765, 0.03237964274160141], 'zlib': [0.017544381911572614, 0.017022327600515606], 'libreoffice': [0.05619115100843597, 0.05130544556054563]}; same-env TLC={'libpython': [0.7856584418114911, 0.7832918434286945], 'expat-xml': [0.05742049993568176, 0.059784683709898215], 'elementtree-xml': [0.029887576366832765, 0.03237964274160141], 'zlib': [0.017544381911572614, 0.017022327600515606], 'libreoffice': [0.05619115100843597, 0.05130544556054563]} | partially-supported | For TLC, historical single-run DSO points are checked against current repeat ranges; new XLSX datasets must overlap the current TLC repeat ranges for all listed DSO classes. No fixed pp band is used. | processed/tlc.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-4 | XLSX only; current/new workflows may use different operation mixes. |
| CLM-05 | XLSX 库层构成：libpython ≈79.7%，Expat ≈5.6%，_elementtree ≈3.5%，zlib ≈1.4%（LibreOffice DSO 合计约 7%）。 | retail | libraries current repeat ranges={'libpython': [0.7054887480041214, 0.6981316947595085], 'expat-xml': [0.05530620992841661, 0.051481184455626036], 'elementtree-xml': [0.02228817685584726, 0.023739871596503852], 'zlib': [0.015754294086624474, 0.01257818130088126], 'libreoffice': [0.1228004557495671, 0.12286546326504402]}; same-env TLC={'libpython': [0.7856584418114911, 0.7832918434286945], 'expat-xml': [0.05742049993568176, 0.059784683709898215], 'elementtree-xml': [0.029887576366832765, 0.03237964274160141], 'zlib': [0.017544381911572614, 0.017022327600515606], 'libreoffice': [0.05619115100843597, 0.05130544556054563]} | partially-supported | For TLC, historical single-run DSO points are checked against current repeat ranges; new XLSX datasets must overlap the current TLC repeat ranges for all listed DSO classes. No fixed pp band is used. | processed/retail.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-4 | XLSX only; current/new workflows may use different operation mixes. |
| CLM-05 | XLSX 库层构成：libpython ≈79.7%，Expat ≈5.6%，_elementtree ≈3.5%，zlib ≈1.4%（LibreOffice DSO 合计约 7%）。 | manufacturing | libraries current repeat ranges={'libpython': [0.654131539231386, 0.690741988540868], 'expat-xml': [0.02912396069760003, 0.03261238448643836], 'elementtree-xml': [0.024786959287263714, 0.01694798481133155], 'zlib': [0.017446725958486523, 0.01013092450772739], 'libreoffice': [0.13438009304412243, 0.1279477520894059]}; same-env TLC={'libpython': [0.7856584418114911, 0.7832918434286945], 'expat-xml': [0.05742049993568176, 0.059784683709898215], 'elementtree-xml': [0.029887576366832765, 0.03237964274160141], 'zlib': [0.017544381911572614, 0.017022327600515606], 'libreoffice': [0.05619115100843597, 0.05130544556054563]} | partially-supported | For TLC, historical single-run DSO points are checked against current repeat ranges; new XLSX datasets must overlap the current TLC repeat ranges for all listed DSO classes. No fixed pp band is used. | processed/manufacturing.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-4 | XLSX only; current/new workflows may use different operation mixes. |
| CLM-05 | XLSX 库层构成：libpython ≈79.7%，Expat ≈5.6%，_elementtree ≈3.5%，zlib ≈1.4%（LibreOffice DSO 合计约 7%）。 | hr | libraries current repeat ranges={'libpython': [0.7388508981113615, 0.7382376533234082], 'expat-xml': [0.05724674271426449, 0.053553109133091775], 'elementtree-xml': [0.03333650557766266, 0.038073155832994934], 'zlib': [0.010966856363037687, 0.025929457330484643], 'libreoffice': [0.05707836954222855, 0.051387114027591774]}; same-env TLC={'libpython': [0.7856584418114911, 0.7832918434286945], 'expat-xml': [0.05742049993568176, 0.059784683709898215], 'elementtree-xml': [0.029887576366832765, 0.03237964274160141], 'zlib': [0.017544381911572614, 0.017022327600515606], 'libreoffice': [0.05619115100843597, 0.05130544556054563]} | partially-supported | For TLC, historical single-run DSO points are checked against current repeat ranges; new XLSX datasets must overlap the current TLC repeat ranges for all listed DSO classes. No fixed pp band is used. | processed/hr.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-4 | XLSX only; current/new workflows may use different operation mixes. |
| CLM-06 | XLSX Python 层：8 个切片脚本按序执行；函数路径集中在 load_workbook()、XML 解析、单元格对象构造、工作簿遍历及保存压缩。 | tlc | native common-mechanism share=0.5739; normalized stack-prefix fingerprint match share=0.9270; source-matched old path share=0.9916; legacy-documented mechanism without matched old-slice sample share=0.0000; single py-spy top roles=[('xlsx-enhance', 2504), ('xlsx-inspect-structure', 1412), ('xlsx-recalc', 1383), ('xlsx-inspect-features', 1179), ('xlsx-verify', 1141), ('xlsx-inspect-formulas', 932), ('xlsx-summary-export', 921), ('xlsx-inspect-cached', 888)]; new roles=['xlsx-verify'] | partially-supported | Leaf-function mechanism and eligible normalized stack-prefix fingerprints support shared native work at their respective evidence levels. Prefixes are limited to eight normalized frames, require at least four resolved frames, merge DSOs into classes, and do not establish full call paths or code identity. Neither mechanism nor prefix identity proves the same Python algorithm; single-run py-spy is contextual only and is not assigned to native cycles. The assertion that there are no new business hotspots is not established. | raw/tlc/pyspy/out/pyspy-roles.json; legacy/evidence/ANALYSIS-python3123.md#section-5 | N=1 PDF or one-loop/current XLSX; conclusions are Python-stack evidence only. |
| CLM-06 | XLSX Python 层：8 个切片脚本按序执行；函数路径集中在 load_workbook()、XML 解析、单元格对象构造、工作簿遍历及保存压缩。 | retail | native common-mechanism share=0.5867; normalized stack-prefix fingerprint match share=0.6153; source-matched old path share=0.2509; legacy-documented mechanism without matched old-slice sample share=0.0000; single py-spy top roles=[('xlsx-verify', 918), ('xlsx-inspect-tool', 422), ('xlsx-enhance', 281), ('xlsx-recalc', 174), ('xlsx-summary-export', 160), ('runner', 36)]; new roles=['xlsx-verify', 'xlsx-inspect-tool'] | partially-supported | Leaf-function mechanism and eligible normalized stack-prefix fingerprints support shared native work at their respective evidence levels. Prefixes are limited to eight normalized frames, require at least four resolved frames, merge DSOs into classes, and do not establish full call paths or code identity. Neither mechanism nor prefix identity proves the same Python algorithm; single-run py-spy is contextual only and is not assigned to native cycles. The assertion that there are no new business hotspots is not established. | raw/retail/pyspy/out/pyspy-roles.json; legacy/evidence/ANALYSIS-python3123.md#section-5 | N=1 PDF or one-loop/current XLSX; conclusions are Python-stack evidence only. |
| CLM-06 | XLSX Python 层：8 个切片脚本按序执行；函数路径集中在 load_workbook()、XML 解析、单元格对象构造、工作簿遍历及保存压缩。 | manufacturing | native common-mechanism share=0.5348; normalized stack-prefix fingerprint match share=0.4132; source-matched old path share=0.2742; legacy-documented mechanism without matched old-slice sample share=0.0000; single py-spy top roles=[('xlsx-verify', 566), ('xlsx-inspect-tool', 271), ('xlsx-summary-export', 146), ('xlsx-enhance', 138), ('xlsx-recalc', 82), ('runner', 12)]; new roles=['xlsx-verify', 'xlsx-inspect-tool'] | partially-supported | Leaf-function mechanism and eligible normalized stack-prefix fingerprints support shared native work at their respective evidence levels. Prefixes are limited to eight normalized frames, require at least four resolved frames, merge DSOs into classes, and do not establish full call paths or code identity. Neither mechanism nor prefix identity proves the same Python algorithm; single-run py-spy is contextual only and is not assigned to native cycles. The assertion that there are no new business hotspots is not established. | raw/manufacturing/pyspy/out/pyspy-roles.json; legacy/evidence/ANALYSIS-python3123.md#section-5 | N=1 PDF or one-loop/current XLSX; conclusions are Python-stack evidence only. |
| CLM-06 | XLSX Python 层：8 个切片脚本按序执行；函数路径集中在 load_workbook()、XML 解析、单元格对象构造、工作簿遍历及保存压缩。 | hr | native common-mechanism share=0.5353; normalized stack-prefix fingerprint match share=0.6701; source-matched old path share=0.1804; legacy-documented mechanism without matched old-slice sample share=0.0000; single py-spy top roles=[('xlsx-verify', 1008), ('xlsx-inspect-tool', 561), ('xlsx-enhance', 292), ('xlsx-recalc', 199), ('xlsx-summary-export', 198)]; new roles=['xlsx-verify', 'xlsx-inspect-tool'] | partially-supported | Leaf-function mechanism and eligible normalized stack-prefix fingerprints support shared native work at their respective evidence levels. Prefixes are limited to eight normalized frames, require at least four resolved frames, merge DSOs into classes, and do not establish full call paths or code identity. Neither mechanism nor prefix identity proves the same Python algorithm; single-run py-spy is contextual only and is not assigned to native cycles. The assertion that there are no new business hotspots is not established. | raw/hr/pyspy/out/pyspy-roles.json; legacy/evidence/ANALYSIS-python3123.md#section-5 | N=1 PDF or one-loop/current XLSX; conclusions are Python-stack evidence only. |
| CLM-07 | IPC/用户-内核构成：PDF 用户态 IPC 2.55、内核态占 13.93% cycles；XLSX 用户态 IPC 2.53、内核态占 2.17% cycles。 | opm-n1 | user IPC=2.5325440065588043; kernel cycles share=0.12045848187538458; stat events include runner preflight | insufficient-evidence | Current perf stat wraps the runner including preflight; historical measurement scope differs and stat is not ROI-scoped. | raw/opm-n1/stat/stat.csv; raw/opm-n1/stat/metadata.json; legacy/evidence/ANALYSIS-python3123.md#section-6 | Perf-stat runs only; not evidence about workload ROI cycles composition. |
| CLM-07 | IPC/用户-内核构成：PDF 用户态 IPC 2.55、内核态占 13.93% cycles；XLSX 用户态 IPC 2.53、内核态占 2.17% cycles。 | opm-n10 | user IPC=2.700885870959948; kernel cycles share=0.10368928393576217; stat events include runner preflight | insufficient-evidence | Current perf stat wraps the runner including preflight; historical measurement scope differs and stat is not ROI-scoped. | raw/opm-n10/stat/stat.csv; raw/opm-n10/stat/metadata.json; legacy/evidence/ANALYSIS-python3123.md#section-6 | Perf-stat runs only; not evidence about workload ROI cycles composition. |
| CLM-07 | IPC/用户-内核构成：PDF 用户态 IPC 2.55、内核态占 13.93% cycles；XLSX 用户态 IPC 2.53、内核态占 2.17% cycles。 | irs_w4-n1 | user IPC=2.577850154745068; kernel cycles share=0.10911479954866043; stat events include runner preflight | insufficient-evidence | Current perf stat wraps the runner including preflight; historical measurement scope differs and stat is not ROI-scoped. | raw/irs_w4-n1/stat/stat.csv; raw/irs_w4-n1/stat/metadata.json; legacy/evidence/ANALYSIS-python3123.md#section-6 | Perf-stat runs only; not evidence about workload ROI cycles composition. |
| CLM-07 | IPC/用户-内核构成：PDF 用户态 IPC 2.55、内核态占 13.93% cycles；XLSX 用户态 IPC 2.53、内核态占 2.17% cycles。 | irs_w4-n10 | user IPC=2.7861833137319008; kernel cycles share=0.0953980736650568; stat events include runner preflight | insufficient-evidence | Current perf stat wraps the runner including preflight; historical measurement scope differs and stat is not ROI-scoped. | raw/irs_w4-n10/stat/stat.csv; raw/irs_w4-n10/stat/metadata.json; legacy/evidence/ANALYSIS-python3123.md#section-6 | Perf-stat runs only; not evidence about workload ROI cycles composition. |
| CLM-07 | IPC/用户-内核构成：PDF 用户态 IPC 2.55、内核态占 13.93% cycles；XLSX 用户态 IPC 2.53、内核态占 2.17% cycles。 | sba1919-n1 | user IPC=2.715084896369163; kernel cycles share=0.09708395448489514; stat events include runner preflight | insufficient-evidence | Current perf stat wraps the runner including preflight; historical measurement scope differs and stat is not ROI-scoped. | raw/sba1919-n1/stat/stat.csv; raw/sba1919-n1/stat/metadata.json; legacy/evidence/ANALYSIS-python3123.md#section-6 | Perf-stat runs only; not evidence about workload ROI cycles composition. |
| CLM-07 | IPC/用户-内核构成：PDF 用户态 IPC 2.55、内核态占 13.93% cycles；XLSX 用户态 IPC 2.53、内核态占 2.17% cycles。 | sba1919-n10 | user IPC=2.905415729883758; kernel cycles share=0.08685254758608994; stat events include runner preflight | insufficient-evidence | Current perf stat wraps the runner including preflight; historical measurement scope differs and stat is not ROI-scoped. | raw/sba1919-n10/stat/stat.csv; raw/sba1919-n10/stat/metadata.json; legacy/evidence/ANALYSIS-python3123.md#section-6 | Perf-stat runs only; not evidence about workload ROI cycles composition. |
| CLM-07 | IPC/用户-内核构成：PDF 用户态 IPC 2.55、内核态占 13.93% cycles；XLSX 用户态 IPC 2.53、内核态占 2.17% cycles。 | tlc | user IPC=2.559000690770256; kernel cycles share=0.019505085805953552; stat events include runner preflight | insufficient-evidence | Current perf stat wraps the runner including preflight; historical measurement scope differs and stat is not ROI-scoped. | raw/tlc/stat/stat.csv; raw/tlc/stat/metadata.json; legacy/evidence/ANALYSIS-python3123.md#section-6 | Perf-stat runs only; not evidence about workload ROI cycles composition. |
| CLM-07 | IPC/用户-内核构成：PDF 用户态 IPC 2.55、内核态占 13.93% cycles；XLSX 用户态 IPC 2.53、内核态占 2.17% cycles。 | retail | user IPC=2.471801006146002; kernel cycles share=0.11306091710853795; stat events include runner preflight | insufficient-evidence | Current perf stat wraps the runner including preflight; historical measurement scope differs and stat is not ROI-scoped. | raw/retail/stat/stat.csv; raw/retail/stat/metadata.json; legacy/evidence/ANALYSIS-python3123.md#section-6 | Perf-stat runs only; not evidence about workload ROI cycles composition. |
| CLM-07 | IPC/用户-内核构成：PDF 用户态 IPC 2.55、内核态占 13.93% cycles；XLSX 用户态 IPC 2.53、内核态占 2.17% cycles。 | manufacturing | user IPC=2.2383315613826014; kernel cycles share=0.14134450189472958; stat events include runner preflight | insufficient-evidence | Current perf stat wraps the runner including preflight; historical measurement scope differs and stat is not ROI-scoped. | raw/manufacturing/stat/stat.csv; raw/manufacturing/stat/metadata.json; legacy/evidence/ANALYSIS-python3123.md#section-6 | Perf-stat runs only; not evidence about workload ROI cycles composition. |
| CLM-07 | IPC/用户-内核构成：PDF 用户态 IPC 2.55、内核态占 13.93% cycles；XLSX 用户态 IPC 2.53、内核态占 2.17% cycles。 | hr | user IPC=2.481737121699582; kernel cycles share=0.09013349852330264; stat events include runner preflight | insufficient-evidence | Current perf stat wraps the runner including preflight; historical measurement scope differs and stat is not ROI-scoped. | raw/hr/stat/stat.csv; raw/hr/stat/metadata.json; legacy/evidence/ANALYSIS-python3123.md#section-6 | Perf-stat runs only; not evidence about workload ROI cycles composition. |
| CLM-08 | PDF 是多个父子进程串行接力，不是同时并行执行（单任务占比 100%，峰值并行度 1）。 | opm-n1 | threads-with-counter-advance-per-poll-interval shares=[0.012527964205816556, 0.012069736253911488]; maximum active-thread counts within an interval=[2, 3] | insufficient-evidence | These are counts of threads whose counters advanced at least once during a 10-25ms interval; they do not establish overlap or simultaneity. No scheduler trace is available. | processed/opm-n1.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-7 | PDF only for CLM-08; XLSX only for CLM-09. |
| CLM-08 | PDF 是多个父子进程串行接力，不是同时并行执行（单任务占比 100%，峰值并行度 1）。 | opm-n10 | threads-with-counter-advance-per-poll-interval shares=[0.016403402187120292, 0.012110202845897668]; maximum active-thread counts within an interval=[2, 2] | insufficient-evidence | These are counts of threads whose counters advanced at least once during a 10-25ms interval; they do not establish overlap or simultaneity. No scheduler trace is available. | processed/opm-n10.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-7 | PDF only for CLM-08; XLSX only for CLM-09. |
| CLM-08 | PDF 是多个父子进程串行接力，不是同时并行执行（单任务占比 100%，峰值并行度 1）。 | irs_w4-n1 | threads-with-counter-advance-per-poll-interval shares=[0.015348682015348681, 0.017737617135207495]; maximum active-thread counts within an interval=[2, 2] | insufficient-evidence | These are counts of threads whose counters advanced at least once during a 10-25ms interval; they do not establish overlap or simultaneity. No scheduler trace is available. | processed/irs_w4-n1.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-7 | PDF only for CLM-08; XLSX only for CLM-09. |
| CLM-08 | PDF 是多个父子进程串行接力，不是同时并行执行（单任务占比 100%，峰值并行度 1）。 | irs_w4-n10 | threads-with-counter-advance-per-poll-interval shares=[0.018141097424412094, 0.01663295122499438]; maximum active-thread counts within an interval=[2, 2] | insufficient-evidence | These are counts of threads whose counters advanced at least once during a 10-25ms interval; they do not establish overlap or simultaneity. No scheduler trace is available. | processed/irs_w4-n10.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-7 | PDF only for CLM-08; XLSX only for CLM-09. |
| CLM-08 | PDF 是多个父子进程串行接力，不是同时并行执行（单任务占比 100%，峰值并行度 1）。 | sba1919-n1 | threads-with-counter-advance-per-poll-interval shares=[0.017024426350851222, 0.016296296296296295]; maximum active-thread counts within an interval=[2, 2] | insufficient-evidence | These are counts of threads whose counters advanced at least once during a 10-25ms interval; they do not establish overlap or simultaneity. No scheduler trace is available. | processed/sba1919-n1.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-7 | PDF only for CLM-08; XLSX only for CLM-09. |
| CLM-08 | PDF 是多个父子进程串行接力，不是同时并行执行（单任务占比 100%，峰值并行度 1）。 | sba1919-n10 | threads-with-counter-advance-per-poll-interval shares=[0.016390782213567025, 0.016853022200615783]; maximum active-thread counts within an interval=[2, 2] | insufficient-evidence | These are counts of threads whose counters advanced at least once during a 10-25ms interval; they do not establish overlap or simultaneity. No scheduler trace is available. | processed/sba1919-n10.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-7 | PDF only for CLM-08; XLSX only for CLM-09. |
| CLM-09 | XLSX 是长时间单任务 + LibreOffice 短暂多线程：单任务活跃时间 ≈98.31%，多任务 ≈1.69%，峰值并行度 4，平均并行度 ≈0.999。 | tlc | threads-with-counter-advance-per-poll-interval shares=[0.02420343137254902, 0.024976777789245536]; maximum active-thread counts within an interval=[30, 28] | insufficient-evidence | These are counts of threads whose counters advanced at least once during a 10-25ms interval; they do not establish overlap or simultaneity. No scheduler trace is available. | processed/tlc.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-7 | PDF only for CLM-08; XLSX only for CLM-09. |
| CLM-09 | XLSX 是长时间单任务 + LibreOffice 短暂多线程：单任务活跃时间 ≈98.31%，多任务 ≈1.69%，峰值并行度 4，平均并行度 ≈0.999。 | retail | threads-with-counter-advance-per-poll-interval shares=[0.1783206106870229, 0.17765567765567766]; maximum active-thread counts within an interval=[6, 8] | insufficient-evidence | These are counts of threads whose counters advanced at least once during a 10-25ms interval; they do not establish overlap or simultaneity. No scheduler trace is available. | processed/retail.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-7 | PDF only for CLM-08; XLSX only for CLM-09. |
| CLM-09 | XLSX 是长时间单任务 + LibreOffice 短暂多线程：单任务活跃时间 ≈98.31%，多任务 ≈1.69%，峰值并行度 4，平均并行度 ≈0.999。 | manufacturing | threads-with-counter-advance-per-poll-interval shares=[0.1413870246085011, 0.13917975567190227]; maximum active-thread counts within an interval=[6, 7] | insufficient-evidence | These are counts of threads whose counters advanced at least once during a 10-25ms interval; they do not establish overlap or simultaneity. No scheduler trace is available. | processed/manufacturing.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-7 | PDF only for CLM-08; XLSX only for CLM-09. |
| CLM-09 | XLSX 是长时间单任务 + LibreOffice 短暂多线程：单任务活跃时间 ≈98.31%，多任务 ≈1.69%，峰值并行度 4，平均并行度 ≈0.999。 | hr | threads-with-counter-advance-per-poll-interval shares=[0.05787203450754853, 0.0586376404494382]; maximum active-thread counts within an interval=[5, 5] | insufficient-evidence | These are counts of threads whose counters advanced at least once during a 10-25ms interval; they do not establish overlap or simultaneity. No scheduler trace is available. | processed/hr.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-7 | PDF only for CLM-08; XLSX only for CLM-09. |
| CLM-10 | XLSX 系统调用以 LibreOffice 的 futex 同步为主，两轮总数约 55.6 万，基本稳定。 | tlc | No current strace aggregate for this dataset. | insufficient-evidence | Same-environment TLC syscall capture is absent for new XLSX datasets; aggregate strace cannot attribute futex to LibreOffice or establish repeat stability. | legacy/evidence/ANALYSIS-python3123.md#section-8 | XLSX only. |
| CLM-10 | XLSX 系统调用以 LibreOffice 的 futex 同步为主，两轮总数约 55.6 万，基本稳定。 | retail | observed aggregate futex calls=692512; calls share=0.3881719743009382; seconds share=0.8848248137531052 | insufficient-evidence | Same-environment TLC syscall capture is absent for new XLSX datasets; aggregate strace cannot attribute futex to LibreOffice or establish repeat stability. | raw/retail/syscalls/syscalls.txt; legacy/evidence/ANALYSIS-python3123.md#section-8 | XLSX only. |
| CLM-10 | XLSX 系统调用以 LibreOffice 的 futex 同步为主，两轮总数约 55.6 万，基本稳定。 | manufacturing | observed aggregate futex calls=348979; calls share=0.2504967167881661; seconds share=0.8545688194776823 | insufficient-evidence | Same-environment TLC syscall capture is absent for new XLSX datasets; aggregate strace cannot attribute futex to LibreOffice or establish repeat stability. | raw/manufacturing/syscalls/syscalls.txt; legacy/evidence/ANALYSIS-python3123.md#section-8 | XLSX only. |
| CLM-10 | XLSX 系统调用以 LibreOffice 的 futex 同步为主，两轮总数约 55.6 万，基本稳定。 | hr | observed aggregate futex calls=190073; calls share=0.19684526447914033; seconds share=0.8415423750014619 | insufficient-evidence | Same-environment TLC syscall capture is absent for new XLSX datasets; aggregate strace cannot attribute futex to LibreOffice or establish repeat stability. | raw/hr/syscalls/syscalls.txt; legacy/evidence/ANALYSIS-python3123.md#section-8 | XLSX only. |
| CLM-10 | XLSX 系统调用以 LibreOffice 的 futex 同步为主，两轮总数约 55.6 万，基本稳定。 | opm-n1 | PDF workload; CLM-10 concerns XLSX LibreOffice futex behavior. | not-applicable | Claim scope is XLSX only. |  | PDF datasets are outside claim scope. |
| CLM-10 | XLSX 系统调用以 LibreOffice 的 futex 同步为主，两轮总数约 55.6 万，基本稳定。 | opm-n10 | PDF workload; CLM-10 concerns XLSX LibreOffice futex behavior. | not-applicable | Claim scope is XLSX only. |  | PDF datasets are outside claim scope. |
| CLM-10 | XLSX 系统调用以 LibreOffice 的 futex 同步为主，两轮总数约 55.6 万，基本稳定。 | irs_w4-n1 | PDF workload; CLM-10 concerns XLSX LibreOffice futex behavior. | not-applicable | Claim scope is XLSX only. |  | PDF datasets are outside claim scope. |
| CLM-10 | XLSX 系统调用以 LibreOffice 的 futex 同步为主，两轮总数约 55.6 万，基本稳定。 | irs_w4-n10 | PDF workload; CLM-10 concerns XLSX LibreOffice futex behavior. | not-applicable | Claim scope is XLSX only. |  | PDF datasets are outside claim scope. |
| CLM-10 | XLSX 系统调用以 LibreOffice 的 futex 同步为主，两轮总数约 55.6 万，基本稳定。 | sba1919-n1 | PDF workload; CLM-10 concerns XLSX LibreOffice futex behavior. | not-applicable | Claim scope is XLSX only. |  | PDF datasets are outside claim scope. |
| CLM-10 | XLSX 系统调用以 LibreOffice 的 futex 同步为主，两轮总数约 55.6 万，基本稳定。 | sba1919-n10 | PDF workload; CLM-10 concerns XLSX LibreOffice futex behavior. | not-applicable | Claim scope is XLSX only. |  | PDF datasets are outside claim scope. |
| CLM-11 | 切片划分与插桩位置可继续使用：PDF 需分别覆盖 Python 脚本进程和 pdftoppm 进程；XLSX 需分别覆盖各 Python 进程和 LibreOffice 进程（含其线程）。 | opm-n1 | identity-path mapped and sampled=12/12 repeat-slice observations; content/path candidates not counted=0; direct path period share by repeat=[0.9565578918671318, 0.9677848506661895]; unknown-role period shares=[2.7301235106756865e-07, 2.4553019846610035e-07] | partially-supported | Timestamped process identities map selected scripts and permitted descendants to old slices. This confirms execution-path self-coverage, while absent per-process executed-file hashes and the unresolved candidate scripts prevent treating the full slice inventory as content-verified. Native mechanism unknowns are separate. | processed/opm-n1.json (native r1/r2 period aggregates); processed/legacy-slice-mapping.json; legacy/legacy-slices.json; legacy/slice-source-hashes.json | Self-coverage applies only to re-sampled OPM N=1/N=10 and TLC; current identity argv did not record executed-file hashes. |
| CLM-11 | 切片划分与插桩位置可继续使用：PDF 需分别覆盖 Python 脚本进程和 pdftoppm 进程；XLSX 需分别覆盖各 Python 进程和 LibreOffice 进程（含其线程）。 | opm-n10 | identity-path mapped and sampled=12/12 repeat-slice observations; content/path candidates not counted=0; direct path period share by repeat=[0.9956326715710709, 0.9989582090225454]; unknown-role period shares=[2.0727964356067635e-07, 2.224408004584019e-07] | partially-supported | Timestamped process identities map selected scripts and permitted descendants to old slices. This confirms execution-path self-coverage, while absent per-process executed-file hashes and the unresolved candidate scripts prevent treating the full slice inventory as content-verified. Native mechanism unknowns are separate. | processed/opm-n10.json (native r1/r2 period aggregates); processed/legacy-slice-mapping.json; legacy/legacy-slices.json; legacy/slice-source-hashes.json | Self-coverage applies only to re-sampled OPM N=1/N=10 and TLC; current identity argv did not record executed-file hashes. |
| CLM-11 | 切片划分与插桩位置可继续使用：PDF 需分别覆盖 Python 脚本进程和 pdftoppm 进程；XLSX 需分别覆盖各 Python 进程和 LibreOffice 进程（含其线程）。 | tlc | identity-path mapped and sampled=16/16 repeat-slice observations; content/path candidates not counted=0; direct path period share by repeat=[0.9915856811321807, 0.9916723984976614]; unknown-role period shares=[0.007753963147681902, 0.007590054566915814] | partially-supported | Timestamped process identities map selected scripts and permitted descendants to old slices. This confirms execution-path self-coverage, while absent per-process executed-file hashes and the unresolved candidate scripts prevent treating the full slice inventory as content-verified. Native mechanism unknowns are separate. | processed/tlc.json (native r1/r2 period aggregates); processed/legacy-slice-mapping.json; legacy/legacy-slices.json; legacy/slice-source-hashes.json | Self-coverage applies only to re-sampled OPM N=1/N=10 and TLC; current identity argv did not record executed-file hashes. |
| CLM-12 | Expat 在 3.12 环境体现为 pyexpat.cpython-312-*.so，旧环境为 libexpat.so，属于打包/链接呈现变化，业务仍是 XML 解析热点。 | tlc | expat+elementtree DSO share=8.972% | partially-supported | Validates XML parser DSO presence, not its whole Python-level work share. | processed/tlc.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-4 | XLSX workloads only. |
| CLM-12 | Expat 在 3.12 环境体现为 pyexpat.cpython-312-*.so，旧环境为 libexpat.so，属于打包/链接呈现变化，业务仍是 XML 解析热点。 | retail | expat+elementtree DSO share=7.644% | partially-supported | Validates XML parser DSO presence, not its whole Python-level work share. | processed/retail.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-4 | XLSX workloads only. |
| CLM-12 | Expat 在 3.12 环境体现为 pyexpat.cpython-312-*.so，旧环境为 libexpat.so，属于打包/链接呈现变化，业务仍是 XML 解析热点。 | manufacturing | expat+elementtree DSO share=5.176% | partially-supported | Validates XML parser DSO presence, not its whole Python-level work share. | processed/manufacturing.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-4 | XLSX workloads only. |
| CLM-12 | Expat 在 3.12 环境体现为 pyexpat.cpython-312-*.so，旧环境为 libexpat.so，属于打包/链接呈现变化，业务仍是 XML 解析热点。 | hr | expat+elementtree DSO share=9.111% | partially-supported | Validates XML parser DSO presence, not its whole Python-level work share. | processed/hr.json (native r1/r2 period aggregates); legacy/evidence/ANALYSIS-python3123.md#section-4 | XLSX workloads only. |
| CLM-13 | PDF N=10 切片权重（cycles:u，分母为完整命令）：字段检查+提取 3.348%；convert_from_path()（11 次，含 Poppler 子进程）17.256%；转换其他部分（Python 侧）32.500%；字段填写（10 次）33.053%；最终验证 10.224%；所选切片合计 96.353%；未单独切片 3.647%。 | opm-n10 | exact-script slice shares={'PDF-S1': 0.016613820180995796, 'PDF-S2': 0.017091955370149906, 'PDF-S3': 0.043649700209351036, 'PDF-S4': 0.3504852378054357, 'PDF-S5': 0.45835681226058567, 'PDF-S6': 0.11113269114831097}; process roles={'pdf-convert': 0.3669, 'pdf-fill': 0.3505, 'pdftoppm': 0.1333, 'pdf-verify': 0.1111, 'pdf-extract-fields': 0.0171, 'pdf-check-fillable': 0.0166, 'pdfinfo': 0.0018, 'pdf-summary-writer': 0.001, 'pdf-mapping-driver': 0.0006}; r1/r2 retained in per-repeat mapping | partially-supported | Use OPM N=10 as same-environment comparator; historical single-core PMU function windows differ from current 8-core period sample/process-window mapping. | processed/opm-n10.json (native r1/r2 period aggregates); raw/opm-n10/r{1,2}/out/monitor/identity.jsonl; legacy/evidence/REPORT-pdf10-weight.md | PDF N=10 only; convert parent windows and children are not identical to historical function-window accounting. |
| CLM-14 | N=10 执行时序：批处理父进程按申请人顺序执行填写→转换，前一子进程退出后才启动下一个；最终验证在全部完成后启动（严格串行）。 | opm-n10 | Native run has no scheduler trace; monitor poll intervals do not prove child-process ordering. | insufficient-evidence | Parent/child timeline claim needs event trace or verified per-process start/exit timestamps. | processed/opm-n10.json (native r1/r2 period aggregates); legacy/evidence/REPORT-pdf10-weight.md | PDF N=10 only. |
| CLM-15 | 十次填写非常一致（单次填写指令权重 2.938%-2.943%，cycles 3.296%-3.310%），没有明显异常申请人。 | opm-n10 | Per-record monitor CPU time is not the historical per-record cycles:u PMU weight; raw per-record event windows are unavailable. | insufficient-evidence | Measurement metric mismatch (CPU time vs cycles) prevents validating the historical narrow 0.5%-range consistency. | processed/opm-n10.json (native r1/r2 period aggregates); legacy/evidence/REPORT-pdf10-weight.md | PDF N=10 only. |
| CLM-16 | 六个 PDF 切片与八个 XLSX 切片构成可独立重放的单元集合，每个切片可从固定阶段输入独立运行。 | all | Aggregate workload replay does not independently prove all fourteen frozen slices can be replayed from their fixed input states. | insufficient-evidence | Slice execution-path evidence is not a standalone slice-replay test. | legacy/legacy-slices.json | Structural legacy claim. |

## 11. 方法、限制与未完成项

- 权重方法：`cycles:u` 原始 perf sample period 求和，作为每个样本代表 cycles 的估计；这是频率模式 perf 对采样周期的内核估计，不是精确硬件计数。monitor CPU 时间独立列示，不得用于修正覆盖率。
- ROI 时间边界是估计：stdout `start:` 到达时刻与 PERFROI 约 300ms marker 样本中位数对齐。每次 marker 的采样跨度见 `metadata/native-parse-quality.json`；stdout 缓冲和采样频率适应造成的偏移未独立校准，误差无法量化。因此不能声称严格排除了全部预运行活动；runner start 行之前的预运行检查不在设计 ROI，但边界样本可能受对齐误差影响。
- cycles 与 monitor CPU 时间按进程角色的差异见 `processed/monitor-cycles-crosscheck.json`；两者时间窗、轮询丢失和线程身份处理不同，差异保留为交叉核对信号，不把差异直接解释为 perf 低估。
- 热点阈值为单函数/角色/DSO 聚合权重 ≥0.5% ROI；阈值以下及 profile 保留阈值以下的合计余量见 `processed/hotspot-threshold-summary.json`。无法分类热点单列，不能据此称作新机制。
- 可复现范围：汇总 JSON、metadata 和压缩的详细 profiles 随仓库发布；先执行 `scripts/profile_artifacts.py restore` 恢复详细画像。原始 perf/monitor 数据只在采集机本地保留（gitignored），体积与 SHA256 见 `raw/index.json`。clone 仓库可以复核派生表，但缺少 raw 时不能重做采样解析；命令在 README 中列明。
- 采集质量：每个 native 配置 2 次独立重复；丢失样本、未解析符号与未归类比例记录在各 processed/<config>.json 的 unresolved 字段。
- 10-25ms monitor 轮询中的线程 CPU 计数增量只表示该间隔内曾获得过 CPU，不表示同时运行；不据此推断瞬时并行度或串行性，旧调度类结论记为证据不足。
- strace `-c` 的 seconds 是系统调用耗时累计，包含阻塞等待，不能解释为内核 CPU 时间。py-spy 每配置仅有一次独立采集，脚本/函数比例没有重复波动估计；W-4 N=1 虽有完整写出样本但 collector 返回错误，状态未改写为成功。
- 未采集支持缓存/内存瓶颈判断所需的专门计数器；未验证优化收益或跨硬件外推。

分析代码 SHA256（本报告对应的源码）：
- `scripts/parse_native.py`: `d93dce56f99857ec192723fbc0ee21953f00b99fa4d3464a436011186906aed5`
- `scripts/rename_parallelism_schema.py`: `a8c1b024fa92a9414f65afc37e631e41ddcda20df62f5c0df3165a7a833dd8a6`
- `scripts/build_profiles.py`: `5baae41adfae265210f30bb4e580f29bf12877ce9b731ac4a496f624ff57576e`
- `scripts/analyze_comparison.py`: `ba90da41bd6c4fc680f6f1021a15ad4e8c9fcb8b3ec5612c1cae8dfbde4828d9`
- `scripts/generate_report.py`: `9c234edf5f7f10e58a335f2ce326ab4762356d2dca8a06f571b7686ecf78f368`
- `scripts/build_raw_index.py`: `dc464b1667dcae8455937b8cc05397d7ac8179a5073347eaa844a97f51dcdb74`
- `scripts/run_collection2.sh`: `8c2d075f9089fea68570ed1789375017b19415b7f92db495d00ca661f89b179e`
- `scripts/analyze_unconfirmed_residuals.py`: `7f95b2150402de07417b1c4de4f74afd7386de049d3f55249443239c30f46701`
- `scripts/generate_final_summary.py`: `d7953f7b8c1bf50ebeb63fa50142cbd50c810b3c50b1525ed40f36402e40ba9b`
- `scripts/profile_artifacts.py`: `93bee2cfc6e3817df1cfeb52715af824a2aa288dc415fd8daffa174fc0c346db`
- `config/mechanism-taxonomy.json`: `559ce93e135f7b4203d89f42cd196037667022de914ef8fbd5edb48ee19967ad`
