# 新旧执行版本热点对比 v1

## 直接回答

1. **当前旧 OPM/TLC 与历史 document-oe：** TLC 的 Python/LibreOffice 与主要 XML 库比例接近；脚本 py-spy 份额差大多不足 1 pp。OPM N=1 脚本份额也接近（历史主要脚本差 0.3–2.3 pp），但原生进程比例从历史 Python 90.6%/pdftoppm 9.2% 变为当前约 87.4%/12.4%。因此脚本热点总体稳定，OPM native 的 Poppler 子进程权重有约 3 pp 上移。历史 native 文件未纳入/未解析，当前旧控件 runner SHA 也不同，不能声称逐函数复现或确定归因。
2. **新 PDF 与旧 OPM：** IRS W-4、SBA 1919 在 N=1 和 N=10 都由 Python 填写/验证与 Poppler 渲染组成；主要库仍是 libpython、zlib、Pillow、Poppler/FreeType。各新表单的 verify 与 fill 占比不同，属于输入和当前 loop verifier 路径差异；每种配置只有一个 native profile，暂不能判断稳定权重变化。Retail/HR 的旧采集是在旧 loop verifier 下失败；保留产物经当前修复版 loop verifier 离线复核通过，但其采集记录和不完整 profile 不升级为当前合格热点。Industry 的成功单轮未得到完整 native 栈解析，故本轮不能给出这些 XLSX 与 TLC 的合格热点比较。
3. **XLSX load/save：** 当前 TLC 的 py-spy 可估计 load_workbook 内部、只读延迟扫描和 save；Retail/HR/Industry 无当前合格 py-spy 数据。具体表格使用 Python 活动采样数，不等于 cycles:u 或整轮墙钟占比。

## 数据资格和版本

| 对象 | 可用资料 | 资格/限制 |
|---|---|---|
| 历史 document-oe OPM/TLC | 历史报告；PDF N=1、TLC | 聚合数据；本轮未纳入/未解析现存历史 native 文件；环境身份按原报告记录 |
| 当前 OPM N=1/N=10、TLC | 现有 native r1/r2，TLC/OPM py-spy | 完整 ROI 解析；旧 recipe/workload 不变；runner SHA 3623…，不是最新版挂载 runner 559a… |
| IRS W-4、SBA 1919 N=1/N=10 | 本轮 native+独立 py-spy 各一组 | loop verifier 成功；完整 native ROI；单次采集无重复波动 |
| Retail | 本轮 5 次 native 尝试 | 采集时旧 verifier 因声明 dimension 误判 base_sheet_scale；保留工作簿修复版 loop verifier 离线复核=success，证据 processed/loop-verifier-recheck-v1.json。旧采集仍不计热点比例（采集时验证失败，perf script 不完整） |
| HR | 本轮 8 次 native 尝试 | 旧 verifier 原失败项为 semantic:scenario_dependency:projected_mean_wage 与 semantic:chart_dependency:major_employment；保留工作簿修复版 loop verifier 离线复核=success，证据 processed/loop-verifier-recheck-v1.json。旧采集仍不计热点比例（采集时验证失败，perf script 不完整） |
| Industry Productivity | 本轮一次 native loop 成功；输出和业务验证归档 | 业务验证成功，但 perf script 导出停止、未解析；未启动 py-spy |

## 当前完整 ROI：原生进程/脚本热点

周期权重来自完整 ROI 的 `cycles:u` sample period。新 PDF 表示每配置单次 native 采集；OPM/TLC 保留两个独立重复，表中为 period 加权合并，JSON 保留各次分母。

| 配置 | 重复 | 主要进程/脚本（ROI cycles:u） |
|---|---:|---|
| opm-n1 | 2 | pdf-convert 34.5%; pdf-fill 18.8%; pdf-verify 14.2%; pdftoppm 12.4%; pdf-extract-fields 8.9%; pdf-check-fillable 7.6%; Python-script subtotal 87.4%; LibreOffice subtotal 0.0% |
| opm-n10 | 2 | pdf-convert 36.7%; pdf-fill 35.0%; pdftoppm 13.3%; pdf-verify 11.1%; pdf-extract-fields 1.7%; pdf-check-fillable 1.7%; Python-script subtotal 86.5%; LibreOffice subtotal 0.0% |
| irs_w4-n1 | 1 | pdf-convert 34.1%; pdf-verify 19.8%; pdf-fill 17.5%; pdftoppm 13.5%; runner 4.6%; pdf-check-fillable 4.3%; Python-script subtotal 86.1%; LibreOffice subtotal 0.0% |
| irs_w4-n10 | 1 | pdf-convert 39.4%; pdf-fill 31.9%; pdftoppm 14.1%; pdf-verify 7.7%; runner 4.0%; python-unknown-script 1.1%; Python-script subtotal 85.6%; LibreOffice subtotal 0.0% |
| sba1919-n1 | 1 | pdf-convert 35.2%; pdf-verify 18.3%; pdftoppm 14.8%; pdf-fill 13.7%; pdf-extract-fields 5.9%; pdf-check-fillable 5.7%; Python-script subtotal 84.7%; LibreOffice subtotal 0.0% |
| sba1919-n10 | 1 | pdf-convert 41.6%; pdf-fill 27.3%; pdftoppm 17.9%; pdf-verify 10.3%; pdf-extract-fields 1.1%; pdf-check-fillable 1.0%; Python-script subtotal 81.7%; LibreOffice subtotal 0.0% |
| tlc | 2 | xlsx-enhance 21.9%; xlsx-inspect-structure 12.5%; xlsx-recalc 11.5%; xlsx-inspect-features 10.4%; xlsx-verify 10.2%; xlsx-summary-export 8.5%; Python-script subtotal 92.1%; LibreOffice subtotal 7.9% |

## Python 脚本热点（独立 py-spy）

这里的分母是 Python 活动采样数，不与 native cycles:u 相混。脚本角色按运行命令和栈识别；unknown/runner 保留。历史 OPM 只有 N=1 的 py-spy 参考；N=10 不冒充历史基线。

| 配置 | 采样数 | Python脚本热点 |
|---|---:|---|
| opm-n1 | 1425 | pdf-convert 45.4%; pdf-fill 20.1%; runner 0.7%; pdf-verify 14.0%; pdf-check-fillable 9.7%; pdf-extract-fields 9.5% |
| opm-n10 | 2333 | pdf-fill 40.1%; pdf-check-fillable 1.6%; pdf-convert 44.0%; pdf-verify 12.4%; pdf-extract-fields 1.2%; runner 0.3% |
| irs_w4-n1 | 2148 | pdf-verify 28.0%; pdf-fill 18.0%; pdf-check-fillable 4.1%; pdf-extract-fields 2.8%; pdf-convert 46.3%; pdf-mapping-driver 0.3% |
| irs_w4-n10 | 3347 | pdf-verify 14.9%; pdf-fill 36.1%; pdf-convert 47.7%; runner 0.2%; pdf-mapping-driver 0.2%; pdf-extract-fields 0.3% |
| sba1919-n1 | 2828 | pdf-convert 46.3%; pdf-fill 15.8%; pdf-verify 23.7%; pdf-check-fillable 6.0%; runner 0.9%; pdf-extract-fields 6.9% |
| sba1919-n10 | 4254 | pdf-fill 32.3%; pdf-verify 12.9%; pdf-convert 52.2%; pdf-mapping-driver 0.3%; pdf-extract-fields 1.3%; pdf-check-fillable 0.8% |
| tlc | 11050 | xlsx-verify 10.9%; xlsx-enhance 23.7%; xlsx-summary-export 9.1%; xlsx-inspect-formulas 9.2%; xlsx-inspect-cached 8.7%; xlsx-inspect-structure 12.8% |

历史报告与当前旧脚本对照（两者都是 py-spy Python 活动样本；历史没有逐栈 raw）：

| 对象/角色 | 历史 document-oe | 当前 | 变化 |
|---|---:|---:|---:|
| OPM N=1 / pdf-convert | 43.9% | 45.4% | +1.5 pp |
| OPM N=1 / pdf-fill | 21.2% | 20.1% | -1.1 pp |
| OPM N=1 / pdf-verify | 14.3% | 14.0% | -0.3 pp |
| OPM N=1 / pdf-check-fillable | 7.4% | 9.7% | +2.3 pp |
| OPM N=1 / pdf-extract-fields | 9.8% | 9.5% | -0.2 pp |
| TLC / xlsx-inspect-structure | 13.6% | 12.8% | -0.8 pp |
| TLC / xlsx-inspect-features | 11.1% | 11.5% | +0.4 pp |
| TLC / xlsx-enhance | 23.4% | 23.7% | +0.3 pp |
| TLC / xlsx-recalc | 12.6% | 12.5% | -0.1 pp |
| TLC / xlsx-verify | 11.0% | 10.9% | -0.1 pp |
| TLC / xlsx-summary-export | 8.8% | 9.1% | +0.3 pp |

同环境旧输入与新 PDF 的脚本占比（分开按 N 比较；当前旧 OPM 是桥接基线）：

| 对照 | pdf-convert | pdf-fill | pdf-verify | check-fillable | extract-fields |
|---|---:|---:|---:|---:|---:|
| OPM n1 → IRS W-4 n1 | +0.9 pp | -2.2 pp | +14.1 pp | -5.6 pp | -6.7 pp |
| OPM n1 → SBA 1919 n1 | +0.9 pp | -4.3 pp | +9.7 pp | -3.6 pp | -2.6 pp |
| OPM n10 → IRS W-4 n10 | +3.7 pp | -4.0 pp | +2.6 pp | -1.1 pp | -0.9 pp |
| OPM n10 → SBA 1919 n10 | +8.2 pp | -7.8 pp | +0.5 pp | -0.8 pp | +0.0 pp |
脚本角色的百分点变化是 Python 活动样本之间的差异；文件页数/字段数、实际操作路径和验证内容会影响它，不代表整个 workload CPU 周期变化，也不能单独归因输入类别。

## 当前完整 ROI：主要库与函数

函数份额为完整 ROI 的 period 权重；`leaf` 为采样点函数，实体函数仅用于 inline 归属，不把通用 libpython 解释成业务算法。

| 配置 | 高权重库 | 主要叶函数 / 脚本 |
|---|---|---|
| opm-n1 | libpython 50.3%; zlib 15.8%; pillow 15.5%; poppler 6.9%; libc 4.0% | pdf-convert:longest_match [zlib] 7.54% (ctx: longest_match [/usr/lib64/libz.so.1.2.13] → deflate_slow [/usr/lib64/libz.so.1.2.13] → deflate [/usr/lib64/libz.so.1.2.13]); pdf-convert:ImagingResampleHorizontal_8bpc [pillow] 6.81% (ctx: ImagingResampleHorizontal_8bpc [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so] → ImagingResampleInner [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so] → _resize [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]); pdf-convert:deflate_slow [zlib] 4.25% (ctx: deflate_slow [/usr/lib64/libz.so.1.2.13] → deflate [/usr/lib64/libz.so.1.2.13] → ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]); pdf-convert:ImagingZipEncode [pillow] 3.91% (ctx: ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so] → _encode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so] → method_vectorcall_VARARGS [/opt/python-3.12.3/lib/libpython3.12.so.1.0]) |
| opm-n10 | libpython 48.5%; pillow 17.0%; zlib 16.5%; poppler 8.6%; libc 3.0% | pdf-convert:longest_match [zlib] 7.63% (ctx: longest_match [/usr/lib64/libz.so.1.2.13] → deflate_slow [/usr/lib64/libz.so.1.2.13] → deflate [/usr/lib64/libz.so.1.2.13]); pdf-convert:ImagingResampleHorizontal_8bpc [pillow] 7.10% (ctx: ImagingResampleHorizontal_8bpc [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so] → ImagingResampleInner [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so] → _resize [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]); pdf-fill:_PyEval_EvalFrameDefault [libpython] 5.17% (ctx: _PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0] → PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0] → run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]); pdf-convert:deflate_slow [zlib] 4.88% (ctx: deflate_slow [/usr/lib64/libz.so.1.2.13] → deflate [/usr/lib64/libz.so.1.2.13] → ImagingZipEncode [/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so]) |
| irs_w4-n1 | libpython 48.6%; zlib 17.3%; pillow 14.9%; poppler 6.4%; freetype 4.7% | pdf-convert:longest_match [zlib] 8.16% (ctx: longest_match [zlib] → deflate_slow [zlib] → deflate [zlib]); pdf-convert:ImagingResampleHorizontal_8bpc [pillow] 5.89% (ctx: ImagingResampleHorizontal_8bpc [pillow] → ImagingResampleInner [pillow] → _resize [pillow]); pdf-convert:deflate_slow [zlib] 5.39% (ctx: deflate_slow [zlib] → deflate [zlib] → ImagingZipEncode [pillow]); pdf-convert:ImagingZipEncode [pillow] 3.86% (ctx: ImagingZipEncode [pillow] → _encode [pillow] → method_vectorcall_VARARGS [libpython]) |
| irs_w4-n10 | libpython 45.1%; pillow 18.3%; zlib 18.3%; poppler 6.5%; freetype 5.2% | pdf-convert:longest_match [zlib] 8.23% (ctx: longest_match [zlib] → deflate_slow [zlib] → deflate [zlib]); pdf-convert:ImagingResampleHorizontal_8bpc [pillow] 7.39% (ctx: ImagingResampleHorizontal_8bpc [pillow] → ImagingResampleInner [pillow] → _resize [pillow]); pdf-fill:_PyEval_EvalFrameDefault [libpython] 5.94% (ctx: _PyEval_EvalFrameDefault [libpython] → _PyObject_FastCallDictTstate [libpython] → _PyObject_Call_Prepend [other]); pdf-convert:deflate_slow [zlib] 5.93% (ctx: deflate_slow [zlib] → deflate [zlib] → ImagingZipEncode [pillow]) |
| sba1919-n1 | libpython 45.9%; pillow 17.3%; zlib 17.1%; poppler 8.8%; freetype 5.0% | pdf-convert:longest_match [zlib] 7.89% (ctx: longest_match [zlib] → deflate_slow [zlib] → deflate [zlib]); pdf-convert:ImagingResampleHorizontal_8bpc [pillow] 6.73% (ctx: ImagingResampleHorizontal_8bpc [pillow] → ImagingResampleInner [pillow] → _resize [pillow]); pdf-convert:ImagingZipEncode [pillow] 4.49% (ctx: ImagingZipEncode [pillow] → _encode [pillow] → method_vectorcall_VARARGS [libpython]); pdf-convert:deflate_slow [zlib] 4.21% (ctx: deflate_slow [zlib] → deflate [zlib] → ImagingZipEncode [pillow]) |
| sba1919-n10 | libpython 38.9%; zlib 19.7%; pillow 19.1%; poppler 11.3%; freetype 4.9% | pdf-convert:longest_match [zlib] 9.48% (ctx: longest_match [zlib] → deflate_slow [zlib] → deflate [zlib]); pdf-convert:ImagingResampleHorizontal_8bpc [pillow] 8.27% (ctx: ImagingResampleHorizontal_8bpc [pillow] → ImagingResampleInner [pillow] → _resize [pillow]); pdf-convert:deflate_slow [zlib] 5.95% (ctx: deflate_slow [zlib] → deflate [zlib] → ImagingZipEncode [pillow]); pdf-convert:ImagingZipEncode [pillow] 4.90% (ctx: ImagingZipEncode [pillow] → _encode [pillow] → method_vectorcall_VARARGS [libpython]) |
| tlc | libpython 78.4%; expat-xml 5.9%; libreoffice 5.4%; elementtree-xml 3.1%; unknown 2.1% | xlsx-enhance:_PyEval_EvalFrameDefault [libpython] 3.57% (ctx: _PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0] → PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0] → run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]); xlsx-recalc:_PyEval_EvalFrameDefault [libpython] 2.09% (ctx: _PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0] → PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0] → run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]); xlsx-inspect-structure:_PyEval_EvalFrameDefault [libpython] 1.96% (ctx: _PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0] → PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0] → run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]); xlsx-verify:_PyEval_EvalFrameDefault [libpython] 1.40% (ctx: _PyEval_EvalFrameDefault [/opt/python-3.12.3/lib/libpython3.12.so.1.0] → PyEval_EvalCode [/opt/python-3.12.3/lib/libpython3.12.so.1.0] → run_eval_code_obj [/opt/python-3.12.3/lib/libpython3.12.so.1.0]) |

## 当前旧控件与历史 document-oe 比较

| 对象 | 历史报告热点 | 当前运行 profile | 判断 |
|---|---|---|---|
| opm-n1 | python3 90.6%; pdftoppm 9.2% | Python脚本 subtotal 87.4% (r1/r2 87.1%/87.8%; vs hist -3.2 pp); pdftoppm 12.4% (r1/r2 12.9%/11.9%; vs hist +3.1 pp) | 大类总量可比较；历史报告与当前 ROI、runner版本不完全一致，且历史 native 文件本轮未纳入/未解析；当前脚本分项存在重组，无法作逐脚本增减判定 |
| tlc | python3 92.5%; libreoffice+threads 7.5% | Python脚本 subtotal 92.1% (r1/r2 92.0%/92.1%; vs hist -0.4 pp); LibreOffice/threads 7.9% (r1/r2 8.0%/7.9%; vs hist +0.5 pp) | 大类总量可比较；历史报告与当前 ROI、runner版本不完全一致，且历史 native 文件本轮未纳入/未解析；当前脚本分项存在重组，无法作逐脚本增减判定 |

主要库占比对照（两边均报告 cycles:u）：

| 对象 / 库 | 历史 | 当前 | 变化 |
|---|---:|---:|---:|
| opm-n1 / libpython | 53.6% | 50.3% | -3.2 pp |
| opm-n1 / zlib | 18.1% | 15.8% | -2.3 pp |
| opm-n1 / pillow | 15.2% | 15.5% | +0.3 pp |
| opm-n1 / poppler | 6.3% | 6.9% | +0.6 pp |
| opm-n1 / freetype | 1.9% | 2.8% | +1.0 pp |
| tlc / libpython | 79.7% | 78.4% | -1.2 pp |
| tlc / expat-xml | 5.6% | 5.9% | +0.2 pp |
| tlc / elementtree-xml | 3.5% | 3.1% | -0.4 pp |
| tlc / zlib | 1.4% | 1.7% | +0.3 pp |

## XLSX load_workbook、只读延迟扫描与保存

下表分母为全部 py-spy Python 活动样本（含无 Python 函数栈进程样本）。A/B/D 为生产分析器按完整栈分类的互斥样本；C=A+B 并集。非加载/保存及 no_python_frames 单列。py-spy 不测 LibreOffice-only 工作或闲置等待。

| 基线 | 全 Python 活动样本 | A load_workbook内部 | B read_only延迟扫描 | C 加载合计 | D Workbook.save | E 加载+保存 | F 其他 | 无 Python 栈 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 历史 TLC | 22405 | 67.0% | 10.3% | 77.3% | 12.2% | 89.5% | 4.2% | 6.4% |
| 当前 TLC | 11050 | 68.0% | 10.4% | 78.4% | 12.4% | 90.9% | 3.7% | 5.4% |
| 当前 retail | — | — | — | — | — | — | — | — |
| 当前 hr | — | — | — | — | — | — | — | — |
| 当前 industry_productivity | — | — | — | — | — | — | — | — |

主要脚本内部占比由完整调用栈按进程归属重建，见下表；仅为 Python 活动采样比例，不是墙钟时间。


| 版本/脚本 | Python样本 | 占全部 Python 样本 | load调用 | 延迟扫描 | save | 其他 |
|---|---:|---:|---:|---:|---:|---:|
| 历史 TLC/xlsx-enhance | 5255 | 23.5% | 42.9% | 0.0% | 51.9% | 5.3% |
| 历史 TLC/xlsx-verify | 2474 | 11.0% | 88.6% | 0.0% | 0.0% | 11.4% |
| 历史 TLC/xlsx-inspect-structure | 3043 | 13.6% | 75.0% | 0.0% | 0.0% | 25.0% |
| 历史 TLC/xlsx-inspect-features | 2484 | 11.1% | 90.5% | 0.0% | 0.0% | 9.5% |
| 历史 TLC/xlsx-inspect-formulas | 2087 | 9.3% | 90.0% | 0.0% | 0.0% | 10.0% |
| 历史 TLC/xlsx-inspect-cached | 2080 | 9.3% | 89.5% | 0.0% | 0.0% | 10.5% |
| 历史 TLC/xlsx-recalc | 2826 | 12.6% | 12.4% | 81.9% | 0.0% | 5.7% |
| 历史 TLC/xlsx-summary-export | 1977 | 8.8% | 89.9% | 0.0% | 0.0% | 10.1% |
| 当前 TLC/xlsx-enhance | 2620 | 23.7% | 42.9% | 0.0% | 52.4% | 4.7% |
| 当前 TLC/xlsx-verify | 1205 | 10.9% | 88.6% | 0.0% | 0.0% | 11.4% |
| 当前 TLC/xlsx-inspect-features | 1268 | 11.5% | 90.5% | 0.0% | 0.0% | 9.5% |
| 当前 TLC/xlsx-inspect-formulas | 1015 | 9.2% | 91.8% | 0.0% | 0.0% | 8.2% |
| 当前 TLC/xlsx-inspect-cached | 963 | 8.7% | 91.9% | 0.0% | 0.0% | 8.1% |
| 当前 TLC/xlsx-recalc | 1386 | 12.5% | 12.0% | 83.2% | 0.0% | 4.8% |
| 当前 TLC/xlsx-summary-export | 1006 | 9.1% | 89.4% | 0.0% | 0.0% | 10.6% |
历史 SVG 的交叉分类依据火焰图样本坐标和完整栈节点重建。
## Verifier 的单列解释

完整 ROI 已包含循环内 verifier。旧 OPM/TLC 的 verifier 是原 legacy 验证脚本；本次 IRS/SBA 执行当前 loop contract。Retail/HR 的旧采集在此前 verifier 规则下失败，但保留输出经本次修复版 loop verifier 离线复核通过；原始采集和 profile 状态不改写，仍不作为合格热点比例。Industry 通过一轮但没有有效 profile。由于当前 TLC 代码路径仍是 legacy workload，当前 TLC 可作保留验证器 profile，但不外推至 Retail/HR/Industry。

## 解释边界

- 样本 period 累计按 parser 的 ROI 样本定义；PERFROI marker 中点与 stdout arrival 的时间对齐未独立校准，buffering/偏移仍是误差源。
- perf 数据有 lost chunks：IRS/SBA及旧控件应查各 `roi.json`；旧 Retail/HR 采集记录验证失败，所以不计比例，即使其保留输出现在通过修复版 verifier。Industry 原始 perf.data 保留但没有完整 sample/ROI 解析。
- 不把父进程等待算作自己的 CPU，也不将 parent-child inclusive 窗口相加。native 进程身份由采样身份记录和脚本路径归属，未知身份保留。
- N=1 与 N=10 是不同任务规模，分别比较；不将其合并。PDF N=10 历史三轮文件是指令/切片权重报告，不是同口径 native cycles profile，不用于本次热点百分比对照。
- Retail/HR 的旧严格 verifier profile 保留在此前 processed 结果，但由于当前 loop verifier 已变化，只作为旧版本历史，不作为当前版本主结果。

## 可追溯文件

机器结果、采集资格、source hash 和分析脚本 hash：`hotspot-version-comparison.json`。原 profile 和失败材料位于 `raw/`；历史报告位于 `legacy/evidence/`。
