# DocOps L3：十二任务首批热点与 Topdown 对比

本轮覆盖 Word、Excel、PPT、PDF 各三项。每任务每路一次独立采集，批内执行十轮最终有效回放；两路共 24 个 profile。031 复用已验证的两路，其余新增 22 路，新增采集均成功，没有 workload 重试。
本报告用于初步观察同格式任务内部及不同格式间的差异；十轮批次不是十次独立采集，不计算重复稳定性或 CV。

**首批观察：同格式任务也存在负载差异，共用格式和工具并不保证函数热点相同。** Word 三项主要集中于渲染和 PNG 压缩；Excel 016 的重算／检查路径比另两项更突出；PPT 029 与另两项的 Python／LibreOffice 和 Poppler 权重不同；PDF 的结算材料包更多落在 ImageMagick 拼图路径。下文分别给出进程、库、函数和 PMU 证据，符号有限的比较单列。

## 1. 数据与质量

| 格式 | 任务 | 内容 | perf 十轮 ROI 秒 | ROI 样本 | 未解析叶符号权重 | 已解析 Top-10 占 ROI |
|---|---|---|---:|---:|---:|---:|
| word | 001 | 受控文档发布修复 | 21.20 | 3,266 | 15.86% | 64.48% |
| word | 003 | 公开记录元数据清理 | 18.67 | 2,747 | 13.46% | 66.73% |
| word | 009 | 事件手册发布 | 15.99 | 3,358 | 5.68% | 80.33% |
| excel | 013 | 采购投标评审发布 | 50.02 | 154,128 | 17.26% | 64.65% |
| excel | 014 | 灾害补助公开发布 | 38.02 | 112,435 | 14.37% | 62.93% |
| excel | 016 | 预测模型情景级联 | 51.98 | 241,887 | 29.31% | 49.34% |
| ppt | 021 | 庇护所无障碍整改 | 48.29 | 217,057 | 20.53% | 49.28% |
| ppt | 026 | 气候披露图表重建 | 35.66 | 117,523 | 21.09% | 46.77% |
| ppt | 029 | 季度业务回顾发布 | 22.15 | 101,373 | 35.34% | 26.09% |
| pdf | 031 | 听证材料包扁平化发布 | 15.53 | 694 | 4.86% | 92.53% |
| pdf | 037 | 公交绕行材料修复 | 18.66 | 1,048 | 11.91% | 84.89% |
| pdf | pdfwf005 | 结算材料包重建 | 16.69 | 1,297 | 13.55% | 76.54% |

符号质量超过试点 20% 未解析门槛的任务：016、021、026、029。门槛没有放宽，采集成功与函数对比资格分别记录。所有未知权重保留在完整 ROI 分母；下文的“Top-10”均指已解析函数的前十项，不是把未知部分补成已知函数。

## 2. 测量与计算方法

实际镜像 `sha256:bda6808f5b05feff831fb1700a24ee90f42c5b332f5411c80a752cf960baf617`；Python 3.12.14、openpyxl 3.1.5、LibreOffice 7.4.7.2、perf 6.1.190、DevKit 26.0.RC1。镜像与原七例的环境不同，本轮不将其百分比拼接成原七例的同环境对照。

perf 对测量入口及后代采集 `cycles:u`，49 Hz、DWARF 16384、CLOCK_MONOTONIC；同镜像 `perf script --no-inline --ns -F +pid` 导出。统计只保留 workflow 步骤区间并集，排除调度器。分母为 ROI 原始 sample period；它不是整轮 CPU 秒。
业务步骤 CPU affinity 为 0–7；调度、监测、准备和归档在 CPU 9。DevKit 在另一次批次按 CPU 0–7 采集，控制器在 CPU 9，命令为 `devkit tuner top-down -c 0-7 -L 0 -i 1 -l 0`。其最终 ALL 指标来自整个 PMU 包络，保留启动、间隙、结束及宿主活动；不冒充精确进程 ROI。
独立官方评分未重跑；原始历史内容判定保持不变。回放成功指选定的最终依赖链和原有检查完成，不将其升级为官方任务内容通过。
采集后的补符号只读挂载匹配 build-id 的调试文件；逐样本确认采样键、地址和物理 DSO 未变。旧解析器若把 C++ 函数括号误拆成 DSO，单列纠正记录；原始文本与旧 JSON 均保留。不改业务库、脚本和工作簿，也没有重录 perf 或重跑 workload。

| 比较量 | 输入与解释 |
|---|---|
| Bound 余弦 | 四维 `[Bad Speculation, Frontend Bound, Backend Bound, Retiring]`；点积除以模长积 |
| 已解析热点 Jaccard | 各任务已解析 Top-10，键为“DSO 文件名＋物理叶函数”；交集数除以并集数。符号有限时仅描述当前可解析名单 |
| 十维欧氏距离 | IPC、四顶层 Bound、Core、Memory、Fetch Latency、Fetch Bandwidth、idle；只作辅助，混合单位且包含父子层级 |

十维向量每项取该批最终汇总；idle 从同批 PMU 包络的 `/proc/stat` 另算。与旧七例采用循环门控 idle 的窗口不同，不与旧十维向量直接计算距离。不使用逐秒曲线的简单均值替代 DevKit ALL，不用两种 profiler 的比例相互折算。

## 3. Topdown 特征

除 IPC 外均为百分数。每行是一批十轮工作的最终结果，不是五次独立均值。

| 格式 | 任务 | IPC | Bad Spec. | Frontend | Backend | Retiring | Core | Memory | Fetch latency | Fetch bandwidth | idle |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| word | 001 | 0.86 | 2.86 | 15.78 | 67.01 | 14.35 | 48.69 | 18.32 | 13.80 | 1.98 | 87.11 |
| word | 003 | 0.96 | 2.78 | 13.72 | 67.51 | 15.98 | 51.11 | 16.40 | 11.63 | 2.09 | 83.68 |
| word | 009 | 1.25 | 3.10 | 14.22 | 61.80 | 20.88 | 48.24 | 13.56 | 11.73 | 2.49 | 76.61 |
| excel | 013 | 0.90 | 2.56 | 14.07 | 68.42 | 14.95 | 51.80 | 16.62 | 11.79 | 2.28 | 80.49 |
| excel | 014 | 0.82 | 2.80 | 17.57 | 65.97 | 13.66 | 49.73 | 16.24 | 15.01 | 2.56 | 80.10 |
| excel | 016 | 0.72 | 3.35 | 19.18 | 65.54 | 11.93 | 48.37 | 17.17 | 16.51 | 2.67 | 78.03 |
| ppt | 021 | 1.13 | 2.41 | 17.45 | 61.27 | 18.87 | 47.77 | 13.50 | 14.58 | 2.87 | 90.14 |
| ppt | 026 | 1.05 | 3.15 | 18.71 | 60.69 | 17.45 | 46.71 | 13.99 | 16.44 | 2.27 | 86.45 |
| ppt | 029 | 0.85 | 3.39 | 25.17 | 57.35 | 14.09 | 40.75 | 16.60 | 21.89 | 3.28 | 86.58 |
| pdf | 031 | 1.05 | 2.26 | 7.44 | 72.85 | 17.45 | 57.34 | 15.52 | 6.50 | 0.93 | 87.55 |
| pdf | 037 | 1.05 | 3.30 | 11.32 | 67.85 | 17.52 | 53.63 | 14.23 | 9.85 | 1.47 | 85.12 |
| pdf | pdfwf005 | 1.43 | 1.87 | 9.02 | 65.21 | 23.90 | 51.72 | 13.49 | 6.66 | 2.35 | 85.70 |

## 4. 同格式任务的两两对比

| 格式 | 配对 | Bound 余弦 | 已解析 Top-10 共同数 | Jaccard | 函数质量 |
|---|---|---:|---:|---:|---|
| word | 001 ↔ 003 | 0.999297 | 6/10 | 0.429 | 门槛内，仍有未知项 |
| word | 001 ↔ 009 | 0.993653 | 5/10 | 0.333 | 门槛内，仍有未知项 |
| word | 003 ↔ 009 | 0.995618 | 6/10 | 0.429 | 门槛内，仍有未知项 |
| excel | 013 ↔ 014 | 0.998320 | 6/10 | 0.429 | 门槛内，仍有未知项 |
| excel | 013 ↔ 016 | 0.995984 | 5/10 | 0.333 | 符号有限 |
| excel | 014 ↔ 016 | 0.999380 | 5/10 | 0.333 | 符号有限 |
| ppt | 021 ↔ 026 | 0.999522 | 7/10 | 0.538 | 符号有限 |
| ppt | 021 ↔ 029 | 0.989012 | 3/10 | 0.176 | 符号有限 |
| ppt | 026 ↔ 029 | 0.992745 | 2/10 | 0.111 | 符号有限 |
| pdf | 031 ↔ 037 | 0.997846 | 8/10 | 0.667 | 门槛内，仍有未知项 |
| pdf | 031 ↔ pdfwf005 | 0.992891 | 4/10 | 0.250 | 门槛内，仍有未知项 |
| pdf | 037 ↔ pdfwf005 | 0.994576 | 4/10 | 0.250 | 门槛内，仍有未知项 |

四项顶层分类接近不等于具体函数、脚本或绝对 CPU 工作量相同。本轮不套用未经本任务集校准的高／中／低相似阈值；先结合下列函数与库、脚本组成解释。

| 格式 | 同格式 Bound 余弦范围 | 已解析 Top-10 共同数范围 |
|---|---:|---:|
| word | 0.993653–0.999297 | 5–6/10 |
| excel | 0.995984–0.999380 | 5–6/10 |
| ppt | 0.989012–0.999522 | 2–7/10 |
| pdf | 0.992891–0.997846 | 4–8/10 |

### 跨格式配对范围

以下每行包含两类格式的 3×3＝9 个配对。范围不等于类别总体分布，也不要求跨格式一定比同格式更远。

| 格式配对 | Bound 余弦范围 | 已解析 Top-10 共同数范围 |
|---|---:|---:|
| word ↔ excel | 0.987910–0.999846 | 4–7/10 |
| word ↔ ppt | 0.978442–0.998300 | 2–3/10 |
| word ↔ pdf | 0.985701–0.999161 | 3–6/10 |
| excel ↔ ppt | 0.978735–0.996772 | 2–5/10 |
| excel ↔ pdf | 0.974460–0.998537 | 2–6/10 |
| ppt ↔ pdf | 0.953987–0.993379 | 1–4/10 |

### Excel 的数值库线程路径

`blas_thread_server` 的 ROI 占比分别为013：18.28%；014：19.91%；016：27.31%。它分布于构建、重算及检查脚本，具体上下文在 JSON 中单列。镜像中的 openpyxl 兼容模块会导入 NumPy；该热点按数值库线程服务路径列出，不能直接解释成工作簿执行了矩阵算法或相同比例的公式计算。

## 5. 各格式的脚本、库与热点函数

### WORD

| 项目 | 001 | 003 | 009 |
|---|---|---|---|
| 主要进程／脚本 | pdftoppm 54.5%<br>soffice.bin 22.2%<br>create_packet.py 13.2%<br>python-inline-or-module 9.8%<br>bash 0.0% | pdftoppm 58.2%<br>soffice.bin 21.6%<br>build_public_packet.py 13.2%<br>audit_public_packet.py 6.2%<br>render_docx.py 0.6% | pdftoppm 74.0%<br>soffice.bin 19.4%<br>build_incident_manual_publication.py 5.4%<br>validate_incident_manual_publication.py 0.7%<br>render_docx.py 0.4% |
| 主要库 | zlib 46.2%<br>Python 15.8%<br>LibreOffice 10.4%<br>libc 8.0%<br>PNG 7.8% | zlib 48.8%<br>Python 14.3%<br>PNG 10.8%<br>LibreOffice 10.4%<br>libc 6.5% | zlib 47.1%<br>PNG 28.0%<br>LibreOffice 10.3%<br>Python 3.7%<br>libc 3.7% |

| 已解析函数排名 | 001 | 003 | 009 |
|---:|---|---|---|
| 1 | `longest_match`<br>libz.so.1.2.13 · 39.66% | `longest_match`<br>libz.so.1.2.13 · 35.40% | `longest_match`<br>libz.so.1.2.13 · 31.98% |
| 2 | `png_write_find_filter`<br>libpng16.so.16.39.0 · 7.75% | `png_write_find_filter`<br>libpng16.so.16.39.0 · 10.76% | `png_write_find_filter`<br>libpng16.so.16.39.0 · 28.04% |
| 3 | `deflate_slow`<br>libz.so.1.2.13 · 5.44% | `deflate_slow`<br>libz.so.1.2.13 · 5.22% | `deflate_slow`<br>libz.so.1.2.13 · 11.51% |
| 4 | `malloc_consolidate`<br>libc.so.6 · 2.34% | `adler32_z`<br>libz.so.1.2.13 · 4.74% | `fill_window`<br>libz.so.1.2.13 · 2.83% |
| 5 | `_PyEval_EvalFrameDefault`<br>libpython3.12.so.1.0 · 2.30% | `fill_window`<br>libz.so.1.2.13 · 2.89% | `pixman_composite_src_8888_8888_asm_neon`<br>libpixman-1.so.0.42.2 · 1.47% |
| 6 | `engine_pkey_asn1_meths_free`<br>libcrypto.so.3 · 1.66% | `__memmove_sve`<br>libc.so.6 · 1.91% | `pixman_composite_src_n_8888_asm_neon`<br>libpixman-1.so.0.42.2 · 1.08% |
| 7 | `pixman_composite_src_n_8888_asm_neon`<br>libpixman-1.so.0.42.2 · 1.52% | `pixman_composite_src_n_8888_asm_neon`<br>libpixman-1.so.0.42.2 · 1.70% | `do_lookup_x`<br>ld-linux-aarch64.so.1 · 1.04% |
| 8 | `malloc`<br>libc.so.6 · 1.43% | `_PyEval_EvalFrameDefault`<br>libpython3.12.so.1.0 · 1.62% | `rtl_uString_release`<br>libuno_sal.so.3 · 0.94% |
| 9 | `ImplGetSVData`<br>libmergedlo.so · 1.31% | `pixman_composite_src_8888_8888_asm_neon`<br>libpixman-1.so.0.42.2 · 1.34% | `malloc`<br>libc.so.6 · 0.72% |
| 10 | `_PyType_Lookup`<br>libpython3.12.so.1.0 · 1.06% | `malloc_consolidate`<br>libc.so.6 · 1.16% | `rtl_uString_acquire`<br>libuno_sal.so.3 · 0.71% |

超长 C++ 符号在表中截短，完整名称见机器结果。
### EXCEL

| 项目 | 013 | 014 | 016 |
|---|---|---|---|
| 主要进程／脚本 | pdftoppm 27.7%<br>montage 17.9%<br>soffice.bin 17.4%<br>build_public_bid_workbook.py 14.3%<br>verify_public_bid_workbook.py 11.1% | pdftoppm 34.1%<br>soffice.bin 25.4%<br>build_disaster_release_v1.py 14.6%<br>validate_disaster_release_v1.py 13.6%<br>recalc.py 11.5% | soffice.bin 34.8%<br>python-inline-or-module 23.9%<br>recalc.py 21.9%<br>build_forecast_dashboard_v1.py 14.0%<br>pdftoppm 4.3% |
| 主要库 | zlib 28.1%<br>libscipy_openblas64_-bb25d554.so 18.3%<br>Python 16.6%<br>LibreOffice 9.6%<br>PNG 8.4% | zlib 26.6%<br>libscipy_openblas64_-bb25d554.so 19.9%<br>Python 18.1%<br>LibreOffice 12.4%<br>PNG 6.3% | Python 30.2%<br>libscipy_openblas64_-bb25d554.so 27.3%<br>LibreOffice 16.0%<br>libc 9.3%<br>pixman 5.3% |

| 已解析函数排名 | 013 | 014 | 016 |
|---:|---|---|---|
| 1 | `longest_match`<br>libz.so.1.2.13 · 18.46% | `longest_match`<br>libz.so.1.2.13 · 20.32% | `blas_thread_server`<br>libscipy_openblas64_-bb25d554.so · 27.31% |
| 2 | `blas_thread_server`<br>libscipy_openblas64_-bb25d554.so · 18.28% | `blas_thread_server`<br>libscipy_openblas64_-bb25d554.so · 19.91% | `_PyEval_EvalFrameDefault`<br>libpython3.12.so.1.0 · 4.66% |
| 3 | `png_write_find_filter`<br>libpng16.so.16.39.0 · 8.42% | `png_write_find_filter`<br>libpng16.so.16.39.0 · 6.27% | `longest_match`<br>libz.so.1.2.13 · 3.04% |
| 4 | `deflate_slow`<br>libz.so.1.2.13 · 6.11% | `_PyEval_EvalFrameDefault`<br>libpython3.12.so.1.0 · 4.63% | `pixman_composite_src_n_8888_asm_neon`<br>libpixman-1.so.0.42.2 · 2.94% |
| 5 | `HorizontalFilter._omp_fn.0`<br>libMagickCore-6.Q16.so.6.0.0 · 4.72% | `deflate_slow`<br>libz.so.1.2.13 · 3.92% | `malloc`<br>libc.so.6 · 2.76% |
| 6 | `_PyEval_EvalFrameDefault`<br>libpython3.12.so.1.0 · 2.17% | `pixman_composite_src_8888_8888_asm_neon`<br>libpixman-1.so.0.42.2 · 2.60% | `pixman_composite_src_8888_8888_asm_neon`<br>libpixman-1.so.0.42.2 · 2.23% |
| 7 | `malloc`<br>libc.so.6 · 2.00% | `pixman_composite_src_n_8888_asm_neon`<br>libpixman-1.so.0.42.2 · 1.74% | `_int_free`<br>libc.so.6 · 2.01% |
| 8 | `VerticalFilter._omp_fn.0`<br>libMagickCore-6.Q16.so.6.0.0 · 1.60% | `fill_window`<br>libz.so.1.2.13 · 1.49% | `_int_malloc`<br>libc.so.6 · 1.79% |
| 9 | `pixman_composite_src_n_8888_asm_neon`<br>libpixman-1.so.0.42.2 · 1.46% | `ScDocument::GetDefPattern`<br>libsclo.so · 1.12% | `_PyObject_GenericGetAttrWithDict`<br>libpython3.12.so.1.0 · 1.35% |
| 10 | `__memcpy_sve`<br>libc.so.6 · 1.44% | `PyObject_GetAttr`<br>libpython3.12.so.1.0 · 0.93% | `rtl_uString_release`<br>libuno_sal.so.3 · 1.24% |

超长 C++ 符号在表中截短，完整名称见机器结果。
### PPT

| 项目 | 021 | 026 | 029 |
|---|---|---|---|
| 主要进程／脚本 | pdftoppm 44.5%<br>soffice.bin 20.9%<br>build_public_shelter_briefing.py 14.0%<br>montage 11.5%<br>validate_public_shelter_briefing.py 7.8% | pdftoppm 46.8%<br>soffice.bin 29.6%<br>build_climate_disclosure.py 17.8%<br>qa_climate_disclosure.py 5.4%<br>unknown:thread-pool 0.1% | soffice.bin 45.3%<br>build_release_deck.py 30.0%<br>validate_release_deck.py 18.5%<br>pdftoppm 5.3%<br>unknown:thread-pool 0.6% |
| 主要库 | Poppler 39.9%<br>Python 16.7%<br>LibreOffice 14.0%<br>ImageMagick 9.8%<br>libc 8.5% | Poppler 40.9%<br>LibreOffice 18.3%<br>Python 16.8%<br>libc 8.5%<br>JPEG 3.9% | Python 39.1%<br>LibreOffice 29.0%<br>libc 8.6%<br>lxml 6.5%<br>fontconfig 4.8% |

| 已解析函数排名 | 021 | 026 | 029 |
|---:|---|---|---|
| 1 | `Splash::pipeRun`<br>libpoppler.so.126.0.0 · 16.18% | `Splash::pipeRun`<br>libpoppler.so.126.0.0 · 15.02% | `_PyEval_EvalFrameDefault`<br>libpython3.12.so.1.0 · 5.82% |
| 2 | `Splash::pipeRunAARGB8`<br>libpoppler.so.126.0.0 · 11.18% | `Splash::pipeRunAARGB8`<br>libpoppler.so.126.0.0 · 14.19% | `FcStrSetMember`<br>libfontconfig.so.1.12.0 · 3.20% |
| 3 | `VerticalFilter._omp_fn.0`<br>libMagickCore-6.Q16.so.6.0.0 · 7.72% | `_PyEval_EvalFrameDefault`<br>libpython3.12.so.1.0 · 3.80% | `malloc`<br>libc.so.6 · 3.20% |
| 4 | `_PyEval_EvalFrameDefault`<br>libpython3.12.so.1.0 · 2.79% | `Splash::scaleImageYupXupBilinear`<br>libpoppler.so.126.0.0 · 2.73% | `BigInt::Scale`<br>libmergedlo.so · 2.42% |
| 5 | `Splash::scaleImageYupXupBilinear`<br>libpoppler.so.126.0.0 · 2.51% | `Splash::drawAALine`<br>libpoppler.so.126.0.0 · 2.62% | `vcl::text::ImplLayoutArgs::AddRun`<br>libmergedlo.so · 2.39% |
| 6 | `__memcpy_sve`<br>libc.so.6 · 2.46% | `rtl_uString_release`<br>libuno_sal.so.3 · 2.14% | `pixman_composite_src_8888_8888_asm_neon`<br>libpixman-1.so.0.42.2 · 2.35% |
| 7 | `Splash::drawAALine`<br>libpoppler.so.126.0.0 · 1.91% | `__memcpy_sve`<br>libc.so.6 · 1.94% | `xmlOutputBufferWrite`<br>etree.cpython-312-aarch64-linux-gnu.so · 2.04% |
| 8 | `malloc`<br>libc.so.6 · 1.65% | `malloc`<br>libc.so.6 · 1.59% | `cppu::_copyConstructAnyFromData`<br>libuno_cppu.so.3 · 1.78% |
| 9 | `HorizontalFilter._omp_fn.0`<br>libMagickCore-6.Q16.so.6.0.0 · 1.58% | `pixman_composite_src_n_8888_asm_neon`<br>libpixman-1.so.0.42.2 · 1.38% | `_Py_Dealloc`<br>libpython3.12.so.1.0 · 1.45% |
| 10 | `pixman_composite_src_8888_8888_asm_neon`<br>libpixman-1.so.0.42.2 · 1.29% | `jsimd_rgb_ycc_convert_neon.localalias`<br>libjpeg.so.62.3.0 · 1.37% | `std::_Hashtable<char16_t const*, std::pair<char16_t const* const, _typelib_TypeDescriptionReference*>, std::allocator<std::pair<char16_t const* con…`<br>libuno_cppu.so.3 · 1.43% |

超长 C++ 符号在表中截短，完整名称见机器结果。
### PDF

| 项目 | 031 | 037 | pdfwf005 |
|---|---|---|---|
| 主要进程／脚本 | pdftoppm 91.7%<br>validate_public_packet.py 7.3%<br>build_public_packet.py 0.9%<br>unknown:bash 0.0%<br>bash 0.0% | pdftoppm 82.1%<br>build_bus_detour_packet.py 11.5%<br>validate_bus_detour_packet.py 6.3%<br>bash 0.0%<br>unknown:id 0.0% | montage 57.1%<br>pdftoppm 26.0%<br>python-inline-or-module 9.2%<br>rebuild_closeout_binder.py 7.6%<br>bash 0.0% |
| 主要库 | zlib 73.4%<br>PNG 13.6%<br>Python 8.2%<br>Poppler 3.3%<br>libc 0.7% | zlib 67.4%<br>Python 16.9%<br>PNG 10.4%<br>Poppler 3.6%<br>libc 1.1% | ImageMagick 49.6%<br>zlib 19.5%<br>Python 16.0%<br>PNG 10.2%<br>libc 2.0% |

| 已解析函数排名 | 031 | 037 | pdfwf005 |
|---:|---|---|---|
| 1 | `longest_match`<br>libz.so.1.2.13 · 64.03% | `longest_match`<br>libz.so.1.2.13 · 59.22% | `GetVirtualPixelCacheNexus`<br>libMagickCore-6.Q16.so.6.0.0 · 16.25% |
| 2 | `png_write_find_filter`<br>libpng16.so.16.39.0 · 13.59% | `png_write_find_filter`<br>libpng16.so.16.39.0 · 10.36% | `VerticalFilter._omp_fn.0`<br>libMagickCore-6.Q16.so.6.0.0 · 13.97% |
| 3 | `deflate_slow`<br>libz.so.1.2.13 · 7.58% | `deflate_slow`<br>libz.so.1.2.13 · 6.70% | `png_write_find_filter`<br>libpng16.so.16.39.0 · 10.20% |
| 4 | `Splash::pipeRunAARGB8`<br>libpoppler.so.126.0.0 · 1.94% | `_PyEval_EvalFrameDefault`<br>libpython3.12.so.1.0 · 3.27% | `SetPixelCacheNexusPixels.constprop.0`<br>libMagickCore-6.Q16.so.6.0.0 · 9.58% |
| 5 | `_PyEval_EvalFrameDefault`<br>libpython3.12.so.1.0 · 1.48% | `Splash::pipeRunAARGB8`<br>libpoppler.so.126.0.0 · 1.75% | `longest_match`<br>libz.so.1.2.13 · 9.46% |
| 6 | `PyObject_GC_Track`<br>libpython3.12.so.1.0 · 1.28% | `Splash::drawAALine`<br>libpoppler.so.126.0.0 · 1.08% | `deflate_slow`<br>libz.so.1.2.13 · 5.79% |
| 7 | `fill_window`<br>libz.so.1.2.13 · 0.88% | `fill_window`<br>libz.so.1.2.13 · 0.81% | `GetCacheViewVirtualPixels`<br>libMagickCore-6.Q16.so.6.0.0 · 4.08% |
| 8 | `Splash::compositeBackground`<br>libpoppler.so.126.0.0 · 0.70% | `_PyType_Lookup`<br>libpython3.12.so.1.0 · 0.62% | `inflate_fast`<br>libz.so.1.2.13 · 2.71% |
| 9 | `Splash::drawAALine`<br>libpoppler.so.126.0.0 · 0.53% | `Splash::compositeBackground`<br>libpoppler.so.126.0.0 · 0.54% | `HorizontalFilter._omp_fn.0`<br>libMagickCore-6.Q16.so.6.0.0 · 2.58% |
| 10 | `__memcpy_sve`<br>libc.so.6 · 0.53% | `adler32_z`<br>libz.so.1.2.13 · 0.54% | `_PyEval_EvalFrameDefault`<br>libpython3.12.so.1.0 · 1.93% |

超长 C++ 符号在表中截短，完整名称见机器结果。
## 6. 窗口、质量与后续

| 任务 | Topdown workflow 秒 | PMU 包络秒 | 包络内非 workflow 秒 | PMU read 次数 |
|---|---:|---:|---:|---:|
| 001 | 20.60 | 23.12 | 2.52 | 24 |
| 003 | 18.20 | 20.63 | 2.43 | 21 |
| 009 | 15.52 | 17.98 | 2.46 | 18 |
| 013 | 41.45 | 44.14 | 2.69 | 44 |
| 014 | 33.25 | 36.16 | 2.91 | 37 |
| 016 | 42.48 | 45.45 | 2.97 | 46 |
| 021 | 40.16 | 62.43 | 22.27 | 63 |
| 026 | 29.83 | 32.41 | 2.58 | 33 |
| 029 | 18.29 | 20.76 | 2.47 | 21 |
| 031 | 15.47 | 17.68 | 2.21 | 18 |
| 037 | 18.63 | 20.80 | 2.17 | 21 |
| pdfwf005 | 16.53 | 18.78 | 2.25 | 19 |

021 每轮字体环境准备在 workflow 外；控制程序位于 CPU 9，但这些间隙仍属于 DevKit 完整包络。各任务的全部未计数事件、公式复算、未知项和 perf loss 原单位记录在 comparison.json，不把缺失样本换算成周期。
本轮部分 PMU 采集期间，宿主同时进行了调试符号下载／校验，其 CPU affinity 未记录，也未从按核计数中扣除。首批结果保留这一宿主活动边界；后续独立重复应在采集前备齐符号并将宿主控制固定到目标 CPU 集合外。下载工具已补上 CPU 9 绑定，不能追溯声称本轮旧下载进程也已绑定。
目前每任务每路仅一份独立 profile，因此不计算稳定性、标准差或 CV。需要研究重复波动时，再补齐独立采集，而不是把批内十轮拆成十份独立测量。

## 证据与复算

- [机器结果与完整函数清单](comparison.json)
- [全部 66 个配对](pairs.csv)
- [来源与分析代码哈希](analysis-build.json)
- 采集清单：`analysis/docops/raw/first-comparison-batch-20261103/campaign.json`
- 离线补符号清单：`analysis/docops/raw/first-comparison-batch-20261103/offline-symbol-enrichment-v3/enrichment.json`

只离线重算，不启动 workload 或 profiler：

```bash
python3 -B analysis/docops/compare.py --campaign analysis/docops/raw/first-comparison-batch-20261103/campaign.json --enrichment analysis/docops/raw/first-comparison-batch-20261103/offline-symbol-enrichment-v3/enrichment.json --output <新的输出目录>
```
