# XLSX 五次独立热点采集汇总

各数据集复用已有第一轮，新增四轮；全部五轮合并原始 period 计算热点，逐轮结果全部保留。

| 数据集 | 次数 | ROI 样本总数 | 两两重复的 Top-10 共同数范围 |
|---|---:|---:|---:|
| tlc | 5 | 184,974 | 10–10/10 |
| hr_metro | 5 | 201,185 | 10–10/10 |
| egrid | 5 | 240,148 | 8–9/10 |
| industry_productivity | 5 | 268,834 | 9–10/10 |

## tlc 主要函数的重复波动

| 合并 Top-10 函数 | 合并周期占比 | 逐轮最小–最大 | 逐轮占比 CV | 进入 Top-10 次数 |
|---|---:|---:|---:|---:|
| `libpython / _PyEval_EvalFrameDefault` | 23.65% | 22.93%–24.11% | 1.90% | 5/5 |
| `libpython / gc_collect_main` | 5.13% | 5.07%–5.25% | 1.45% | 5/5 |
| `libpython / subtype_traverse` | 3.90% | 3.77%–4.04% | 2.49% | 5/5 |
| `libpython / _Py_dict_lookup` | 3.57% | 3.25%–3.81% | 6.63% | 5/5 |
| `libpython / deduce_unreachable` | 3.23% | 3.05%–3.43% | 4.40% | 5/5 |
| `libpython / visit_reachable` | 2.97% | 2.85%–3.14% | 3.91% | 5/5 |
| `libpython / _PyObject_GenericGetAttrWithDict` | 2.04% | 1.93%–2.19% | 4.68% | 5/5 |
| `libpython / dictiter_iternextkey` | 1.92% | 1.71%–2.14% | 8.19% | 5/5 |
| `libpython / tupledealloc` | 1.61% | 1.56%–1.64% | 2.25% | 5/5 |
| `libpython / PyObject_GC_Del` | 1.49% | 1.37%–1.65% | 8.67% | 5/5 |

## hr_metro 主要函数的重复波动

| 合并 Top-10 函数 | 合并周期占比 | 逐轮最小–最大 | 逐轮占比 CV | 进入 Top-10 次数 |
|---|---:|---:|---:|---:|
| `libpython / _PyEval_EvalFrameDefault` | 21.97% | 21.91%–22.02% | 0.20% | 5/5 |
| `libpython / gc_collect_main` | 7.31% | 7.22%–7.37% | 0.73% | 5/5 |
| `libpython / subtype_traverse` | 4.84% | 4.70%–4.96% | 2.48% | 5/5 |
| `libpython / _Py_dict_lookup` | 4.77% | 4.58%–4.92% | 2.81% | 5/5 |
| `libpython / deduce_unreachable` | 4.30% | 4.23%–4.35% | 1.12% | 5/5 |
| `libpython / visit_reachable` | 3.33% | 3.26%–3.42% | 2.04% | 5/5 |
| `libpython / tupledealloc` | 1.81% | 1.70%–1.92% | 4.71% | 5/5 |
| `libpython / _PyObject_GenericGetAttrWithDict` | 1.27% | 1.16%–1.40% | 9.59% | 5/5 |
| `expat / storeAtts` | 1.22% | 1.13%–1.33% | 6.87% | 5/5 |
| `ElementTree / checkpath` | 1.19% | 1.12%–1.25% | 4.93% | 5/5 |

## egrid 主要函数的重复波动

| 合并 Top-10 函数 | 合并周期占比 | 逐轮最小–最大 | 逐轮占比 CV | 进入 Top-10 次数 |
|---|---:|---:|---:|---:|
| `libpython / _PyEval_EvalFrameDefault` | 22.80% | 22.45%–23.08% | 1.08% | 5/5 |
| `libpython / gc_collect_main` | 7.24% | 7.15%–7.38% | 1.37% | 5/5 |
| `libpython / subtype_traverse` | 5.09% | 4.87%–5.40% | 4.18% | 5/5 |
| `libpython / _Py_dict_lookup` | 4.97% | 4.84%–5.13% | 2.66% | 5/5 |
| `libpython / deduce_unreachable` | 4.43% | 4.26%–4.57% | 2.59% | 5/5 |
| `libpython / visit_reachable` | 3.38% | 3.21%–3.64% | 4.94% | 5/5 |
| `libpython / tupledealloc` | 1.76% | 1.51%–1.87% | 8.60% | 5/5 |
| `libpython / _PyObject_GenericGetAttrWithDict` | 1.35% | 1.28%–1.43% | 4.63% | 5/5 |
| `expat / storeAtts` | 1.22% | 1.10%–1.30% | 6.15% | 4/5 |
| `libpython / PyObject_GC_Del` | 1.15% | 0.97%–1.34% | 11.35% | 2/5 |

## industry_productivity 主要函数的重复波动

| 合并 Top-10 函数 | 合并周期占比 | 逐轮最小–最大 | 逐轮占比 CV | 进入 Top-10 次数 |
|---|---:|---:|---:|---:|
| `libpython / _PyEval_EvalFrameDefault` | 21.57% | 21.30%–21.75% | 0.78% | 5/5 |
| `libpython / gc_collect_main` | 7.04% | 7.00%–7.07% | 0.39% | 5/5 |
| `libpython / _Py_dict_lookup` | 4.80% | 4.64%–4.91% | 2.59% | 5/5 |
| `libpython / subtype_traverse` | 4.27% | 4.13%–4.41% | 2.41% | 5/5 |
| `libpython / deduce_unreachable` | 4.10% | 3.90%–4.20% | 2.86% | 5/5 |
| `libpython / visit_reachable` | 3.16% | 3.08%–3.30% | 2.80% | 5/5 |
| `libpython / tupledealloc` | 1.69% | 1.58%–1.81% | 5.68% | 5/5 |
| `libpython / _PyObject_GenericGetAttrWithDict` | 1.50% | 1.41%–1.59% | 4.87% | 5/5 |
| `expat / storeAtts` | 1.18% | 1.11%–1.22% | 3.70% | 5/5 |
| `expat / PyExpat_XML_Parse` | 1.12% | 0.96%–1.28% | 11.22% | 2/5 |
