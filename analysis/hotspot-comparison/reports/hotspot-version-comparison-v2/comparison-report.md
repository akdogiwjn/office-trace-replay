# 新旧执行版本热点对比 v2

## 直接回答

1. **当前旧 OPM/TLC 与历史：** OPM N=1 的 Python 进程角色约 87.4% 对历史 90.6%（-3.2 pp），pdftoppm 12.4% 对 9.2%（+3.1 pp）；TLC Python/LibreOffice 分别 92.1%/7.9%，历史 92.5%/7.5%。因此 TLC 大类接近，OPM 的 Poppler 子进程高约 3 pp；主要库也大体相近。历史只有报告汇总，函数级变化无法判断；两边 runner/环境不同，均属描述性比较。
2. **新数据集与旧用例：** XLSX 共有 libpython 热点（TLC 78.4%；Retail/HR/Industry 64.8%/70.5%/76.7%），并有 Expat/ElementTree 与 LibreOffice 路径；采样点 `_PyEval_EvalFrameDefault` 分别占 TLC/Retail/HR/Industry ROI 13.6%/8.3%/12.2%/12.5%。新三者最大脚本分别是 inspect 27.3%/28.2%/36.9%。PDF W-4/SBA 与 OPM 同见 zlib、Pillow 和 Poppler，N=1/N=10 分开。共享库/解释器函数只证明运行时路径相似，不能证明业务算法相同；新 XLSX 当前验证合约与旧 TLC 不同。
3. **XLSX load/save：** A/B/C/D/E（load_workbook 内部/只读延迟扫描/去重加载/Workbook.save/加载+保存）在全部 Python 活动样本中分别为：TLC: A/B/C/D/E 68.0%/10.4%/78.4%/12.4%/90.9%; Retail: A/B/C/D/E 56.6%/7.3%/64.0%/12.6%/76.6%; HR: A/B/C/D/E 48.2%/11.3%/59.5%/8.1%/67.6%; Industry Productivity: A/B/C/D/E 64.2%/13.0%/77.2%/13.4%/90.6%。样本按类别互斥、分母包括无 Python 栈；脚本贡献见后表。

## 证据资格与版本

| 对象 | 资格与使用口径 |
|---|---|
| 当前旧 OPM N=1/N=10、TLC | 复用 processed 中每项两次 native ROI；runner SHA 3623…，image ID 未记录；频率 OPM 99Hz/TLC 49Hz；TLC/OPM py-spy 复用已有记录。 |
| IRS W-4、SBA 1919 N=1/N=10 | 复用 current-loop-verifier-v1 的成功 native/py-spy 记录；版本 hash、采样和执行信息按配置保存在 JSON；N 分开。 |
| Retail native | recovery record 最终资格为 eligible；解析文本离线重算，原失败采集记录未改写。 |
| Retail/HR/Industry py-spy 与 HR/Industry native | v2 evidence-inventory 和 collection records 最终资格 true，SHA256 index complete。 |
| 历史 document-oe | 使用历史报告汇总。`/home/lcq/document_perf` 原始文件存在，但本轮未纳入/未解析。无历史逐函数对照。 |

## 当前旧输入与历史报告级对比

| 对照 | 指标 | 历史 | 当前 | 差值 |
|---|---|---:|---:|---:|
| OPM N=1 | identified Python process roles | 90.6% | 87.4% | -3.2 pp |
| OPM N=1 | pdftoppm | 9.2% | 12.4% | +3.1 pp |
| TLC | Python process | 92.5% | 92.1% | -0.5 pp |
| TLC | LibreOffice+threads | 7.5% | 7.9% | +0.5 pp |

历史库和脚本按报告同名口径另列。历史没有函数级样本记录，因此不为函数差异填造数字。当前 OPM/TLC 的两个 native repeat 详见 JSON `repeats`/`repeat_count`，其余新配置均为单次。

## 当前 native：进程/脚本、DSO、叶函数

全部百分比以完整 ROI 的 cycles:u sample period 为分母。前两次重复按 period 加权汇总，JSON 保留逐次 ROI period 和样本数。

| 配置 | 重复/ROI period | 主要进程/脚本 | 主要 DSO | 主要叶函数 |
|---|---:|---|---|---|
| opm-n1 | 2 / 94,824,294,340 | pdf-convert 34.5%; pdf-fill 18.8%; pdf-verify 14.2%; pdftoppm 12.4%; pdf-extract-fields 8.9% | libpython 50.3%; zlib 15.8%; pillow 15.5%; poppler 6.9%; libc 4.0% | pdf-convert:longest_match (zlib) 7.5%; pdf-convert:ImagingResampleHorizontal_8bpc (pillow) 6.8%; pdf-convert:deflate_slow (zlib) 4.2%; pdf-convert:ImagingZipEncode (pillow) 3.9% |
| opm-n10 | 2 / 155,618,972,809 | pdf-convert 36.7%; pdf-fill 35.0%; pdftoppm 13.3%; pdf-verify 11.1%; pdf-extract-fields 1.7% | libpython 48.5%; pillow 17.0%; zlib 16.5%; poppler 8.6%; libc 3.0% | pdf-convert:longest_match (zlib) 7.6%; pdf-convert:ImagingResampleHorizontal_8bpc (pillow) 7.1%; pdf-fill:_PyEval_EvalFrameDefault (libpython) 5.2%; pdf-convert:deflate_slow (zlib) 4.9% |
| tlc | 2 / 1,392,173,918,517 | xlsx-enhance 21.9%; xlsx-inspect-structure 12.5%; xlsx-recalc 11.5%; xlsx-inspect-features 10.4%; xlsx-verify 10.2% | libpython 78.4%; expat-xml 5.9%; libreoffice 5.4%; elementtree-xml 3.1%; unknown 2.1% | xlsx-enhance:_PyEval_EvalFrameDefault (libpython) 3.6%; xlsx-recalc:_PyEval_EvalFrameDefault (libpython) 2.1%; xlsx-inspect-structure:_PyEval_EvalFrameDefault (libpython) 2.0%; xlsx-verify:_PyEval_EvalFrameDefault (libpython) 1.4% |
| irs_w4-n1 | 1 / 72,917,313,738 | pdf-convert 34.1%; pdf-verify 19.8%; pdf-fill 17.5%; pdftoppm 13.5%; runner 4.6% | libpython 48.6%; zlib 17.3%; pillow 14.9%; poppler 6.4%; freetype 4.7% | pdf-convert:longest_match (zlib) 8.2%; pdf-convert:ImagingResampleHorizontal_8bpc (pillow) 5.9%; pdf-convert:deflate_slow (zlib) 5.4%; pdf-convert:ImagingZipEncode (pillow) 3.9% |
| irs_w4-n10 | 1 / 113,408,697,008 | pdf-convert 39.4%; pdf-fill 31.9%; pdftoppm 14.1%; pdf-verify 7.7%; runner 4.0% | libpython 45.1%; pillow 18.3%; zlib 18.3%; poppler 6.5%; freetype 5.2% | pdf-convert:longest_match (zlib) 8.2%; pdf-convert:ImagingResampleHorizontal_8bpc (pillow) 7.4%; pdf-fill:_PyEval_EvalFrameDefault (libpython) 5.9%; pdf-convert:deflate_slow (zlib) 5.9% |
| sba1919-n1 | 1 / 94,227,657,608 | pdf-convert 35.2%; pdf-verify 18.3%; pdftoppm 14.8%; pdf-fill 13.7%; pdf-extract-fields 5.9% | libpython 45.9%; pillow 17.3%; zlib 17.1%; poppler 8.8%; freetype 5.0% | pdf-convert:longest_match (zlib) 7.9%; pdf-convert:ImagingResampleHorizontal_8bpc (pillow) 6.7%; pdf-convert:ImagingZipEncode (pillow) 4.5%; pdf-convert:deflate_slow (zlib) 4.2% |
| sba1919-n10 | 1 / 143,097,298,603 | pdf-convert 41.6%; pdf-fill 27.3%; pdftoppm 17.9%; pdf-verify 10.3%; pdf-extract-fields 1.1% | libpython 38.9%; zlib 19.7%; pillow 19.1%; poppler 11.3%; freetype 4.9% | pdf-convert:longest_match (zlib) 9.5%; pdf-convert:ImagingResampleHorizontal_8bpc (pillow) 8.3%; pdf-convert:deflate_slow (zlib) 5.9%; pdf-convert:ImagingZipEncode (pillow) 4.9% |
| retail | 1 / 21,988,136,333 | xlsx-inspect-tool 27.3%; soffice.bin 22.9%; xlsx-enhance 15.1%; xlsx-verify 12.0%; xlsx-summary-export 10.1% | libpython 64.8%; libreoffice 15.6%; expat-xml 4.1%; other 3.9%; libc 3.7% | xlsx-inspect-tool:_PyEval_EvalFrameDefault (libpython) 4.2%; xlsx-inspect-tool:_Py_IsImmortal (libpython) 3.5%; xlsx-summary-export:_PyGCHead_NEXT (libpython) 3.5%; xlsx-inspect-tool:_PyInterpreterState_GET (libpython) 3.5% |
| hr | 1 / 14,696,693,492 | xlsx-inspect-tool 28.2%; xlsx-enhance 16.8%; xlsx-verify 15.2%; soffice.bin 14.4%; xlsx-recalc 11.1% | libpython 70.5%; libreoffice 8.3%; libc 4.8%; other 3.7%; elementtree-xml 3.6% | xlsx-enhance:_PyEval_EvalFrameDefault (libpython) 3.6%; xlsx-inspect-tool:_PyEval_EvalFrameDefault (libpython) 3.2%; xlsx-inspect-tool:arena_map_is_used (libpython) 2.8%; xlsx-summary-export:_PyEval_EvalFrameDefault (libpython) 2.5% |
| industry_productivity | 1 / 1,424,298,137,746 | xlsx-inspect-tool 36.9%; xlsx-enhance 20.0%; xlsx-recalc 13.1%; xlsx-summary-export 10.1%; xlsx-verify 10.1% | libpython 76.7%; libreoffice 6.8%; expat-xml 5.8%; elementtree-xml 3.4%; unknown 2.0% | xlsx-inspect-tool:_PyEval_EvalFrameDefault (libpython) 4.6%; xlsx-enhance:_PyEval_EvalFrameDefault (libpython) 3.4%; xlsx-inspect-tool:_PyGCHead_NEXT (libpython) 2.3%; xlsx-recalc:_PyEval_EvalFrameDefault (libpython) 2.2% |

叶函数列是互斥采样点权重；JSON `overlapping_call_contexts` 是可重叠栈前缀，不与叶函数百分比相加。库类别中 unknown 保留，不重新归一化。脚本身份按采样进程实际命令/身份记录；`python-unknown-script` 不猜测归属。

## 当前 OPM/TLC 与历史主要库、脚本

| 配置/项 | 历史报告 | 当前 profile | 差值 |
|---|---:|---:|---:|
| opm-n1/libpython | 53.6% | 50.3% | -3.2 pp |
| opm-n1/zlib | 18.1% | 15.8% | -2.3 pp |
| opm-n1/pillow | 15.2% | 15.5% | +0.3 pp |
| opm-n1/poppler | 6.3% | 6.9% | +0.6 pp |
| opm-n1/freetype | 1.9% | 2.8% | +1.0 pp |
| opm-n1/py-spy pdf-check-fillable | 7.4% | 9.7% | +2.3 pp |
| opm-n1/py-spy pdf-extract-fields | 9.8% | 9.5% | -0.2 pp |
| opm-n1/py-spy pdf-convert | 43.9% | 45.4% | +1.5 pp |
| opm-n1/py-spy pdf-fill | 21.2% | 20.1% | -1.1 pp |
| opm-n1/py-spy pdf-verify | 14.3% | 14.0% | -0.3 pp |
| tlc/libpython | 79.7% | 78.4% | -1.2 pp |
| tlc/expat-xml | 5.6% | 5.9% | +0.2 pp |
| tlc/elementtree-xml | 3.5% | 3.1% | -0.4 pp |
| tlc/zlib | 1.4% | 1.7% | +0.3 pp |
| tlc/py-spy xlsx-inspect-structure | 13.6% | 12.8% | -0.8 pp |
| tlc/py-spy xlsx-inspect-features | 11.1% | 11.5% | +0.4 pp |
| tlc/py-spy xlsx-enhance | 23.4% | 23.7% | +0.3 pp |
| tlc/py-spy xlsx-recalc | 12.6% | 12.5% | -0.1 pp |
| tlc/py-spy xlsx-verify | 11.0% | 10.9% | -0.1 pp |
| tlc/py-spy xlsx-summary-export | 8.8% | 9.1% | +0.3 pp |

脚本角色表示各自 Python 活动采样份额；当前脚本分解来自 py-spy，不与 native process cycles 混合。历史脚本份额来自历史报告聚合，环境/版本差异使其适合作描述性对照。

## 新 PDF 与 OPM（按 N 分开）

| 对照 | 配置 | native 主要进程 | 主要库 | py-spy 主要脚本 |
|---|---|---|---|---|
| OPM n1 → IRS W-4 n1 | irs_w4-n1 | pdf-convert 34.1%; pdf-verify 19.8%; pdf-fill 17.5%; pdftoppm 13.5% | libpython 48.6%; zlib 17.3%; pillow 14.9%; poppler 6.4% | pdf-convert 46.3%; pdf-verify 28.0%; pdf-fill 18.0%; pdf-check-fillable 4.1% |
| OPM n1 → SBA 1919 n1 | sba1919-n1 | pdf-convert 35.2%; pdf-verify 18.3%; pdftoppm 14.8%; pdf-fill 13.7% | libpython 45.9%; pillow 17.3%; zlib 17.1%; poppler 8.8% | pdf-convert 46.3%; pdf-verify 23.7%; pdf-fill 15.8%; pdf-extract-fields 6.9% |
| OPM n10 → IRS W-4 n10 | irs_w4-n10 | pdf-convert 39.4%; pdf-fill 31.9%; pdftoppm 14.1%; pdf-verify 7.7% | libpython 45.1%; pillow 18.3%; zlib 18.3%; poppler 6.5% | pdf-convert 47.7%; pdf-fill 36.1%; pdf-verify 14.9%; pdf-check-fillable 0.5% |
| OPM n10 → SBA 1919 n10 | sba1919-n10 | pdf-convert 41.6%; pdf-fill 27.3%; pdftoppm 17.9%; pdf-verify 10.3% | libpython 38.9%; zlib 19.7%; pillow 19.1%; poppler 11.3% | pdf-convert 52.2%; pdf-fill 32.3%; pdf-verify 12.9%; pdf-extract-fields 1.3% |

PDF N=10 profile 的 workload record_count 为 10；采集脚本的 requested/completed loop 字段按其运行配置记录，二者不混作单份任务。每个配置仅一条 profile，差异不代表稳定变化。

## XLSX load_workbook、只读延迟扫描与保存

py-spy 主分母是 ROI 内全部 Python 活动样本，含无 Python 函数栈进程样本；识别出的执行前 runner 校验样本单列并排除。A/B/C/D/E 为互斥分类样本的百分比，C=A+B，E=C+D。不是 wall time 或 native cycles。

| 配置 | Python 样本 | A load 内部 | B 延迟扫描 | C 加载并集 | D Workbook.save | E 加载+保存并集 | 其他 | 无 Python 栈 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TLC historical SVG | 22,405 | 67.0% | 10.3% | 77.3% | 12.2% | 89.5% | 4.2% | 6.4% |
| TLC current py-spy | 11,050 | 68.0% | 10.4% | 78.4% | 12.4% | 90.9% | 3.7% | 5.4% |
| retail | 286 | 56.6% | 7.3% | 64.0% | 12.6% | 76.6% | 13.3% | 10.1% |
| hr | 222 | 48.2% | 11.3% | 59.5% | 8.1% | 67.6% | 23.4% | 9.0% |
| industry_productivity | 22,065 | 64.2% | 13.0% | 77.2% | 13.4% | 90.6% | 2.8% | 6.6% |

脚本贡献：第一百分比是该脚本占全部 Python 活动样本；括号中依次为脚本内部 load / lazy / save / other+无栈比例。JSON 按所有实际角色完整保留。

| 配置 | 脚本热点及各自 load/lazy/save/other+无栈 |
|---|---|
| historical_tlc | xlsx-enhance 23.5% (L 42.9%/lazy 0.0%/save 51.9%/other+no-stack 5.3%); xlsx-inspect-structure 13.6% (L 75.0%/lazy 0.0%/save 0.0%/other+no-stack 25.0%); xlsx-recalc 12.6% (L 12.4%/lazy 81.9%/save 0.0%/other+no-stack 5.7%); xlsx-inspect-features 11.1% (L 90.5%/lazy 0.0%/save 0.0%/other+no-stack 9.5%); xlsx-verify 11.0% (L 88.6%/lazy 0.0%/save 0.0%/other+no-stack 11.4%); xlsx-inspect-formulas 9.3% (L 90.0%/lazy 0.0%/save 0.0%/other+no-stack 10.0%); xlsx-inspect-cached 9.3% (L 89.5%/lazy 0.0%/save 0.0%/other+no-stack 10.5%); xlsx-summary-export 8.8% (L 89.9%/lazy 0.0%/save 0.0%/other+no-stack 10.1%); xlsx-csv-export 0.8% (L 95.4%/lazy 0.0%/save 0.0%/other+no-stack 4.6%) |
| current_tlc | xlsx-enhance 23.7% (L 42.9%/lazy 0.0%/save 52.4%/other+no-stack 4.7%); xlsx-inspect-structure 12.8% (L 85.2%/lazy 0.0%/save 0.0%/other+no-stack 14.8%); xlsx-recalc 12.5% (L 12.0%/lazy 83.2%/save 0.0%/other+no-stack 4.8%); xlsx-inspect-features 11.5% (L 90.5%/lazy 0.0%/save 0.0%/other+no-stack 9.5%); xlsx-verify 10.9% (L 88.6%/lazy 0.0%/save 0.0%/other+no-stack 11.4%); xlsx-inspect-formulas 9.2% (L 91.8%/lazy 0.0%/save 0.0%/other+no-stack 8.2%); xlsx-summary-export 9.1% (L 89.4%/lazy 0.0%/save 0.0%/other+no-stack 10.6%); xlsx-inspect-cached 8.7% (L 91.9%/lazy 0.0%/save 0.0%/other+no-stack 8.1%); xlsx-csv-export 0.8% (L 97.7%/lazy 1.1%/save 0.0%/other+no-stack 1.1%) |
| retail | xlsx-inspect-tool 37.8% (L 75.9%/lazy 0.0%/save 0.0%/other+no-stack 24.1%); xlsx-enhance 24.1% (L 30.4%/lazy 0.0%/save 52.2%/other+no-stack 17.4%); xlsx-verify 15.0% (L 58.1%/lazy 0.0%/save 0.0%/other+no-stack 41.9%); xlsx-summary-export 12.2% (L 85.7%/lazy 0.0%/save 0.0%/other+no-stack 14.3%); xlsx-recalc 10.8% (L 12.9%/lazy 67.7%/save 0.0%/other+no-stack 19.4%) |
| hr | xlsx-inspect-tool 36.9% (L 64.6%/lazy 0.0%/save 0.0%/other+no-stack 35.4%); xlsx-enhance 16.7% (L 32.4%/lazy 0.0%/save 48.6%/other+no-stack 18.9%); xlsx-verify 16.2% (L 38.9%/lazy 8.3%/save 0.0%/other+no-stack 52.8%); xlsx-summary-export 16.2% (L 63.9%/lazy 0.0%/save 0.0%/other+no-stack 36.1%); xlsx-recalc 14.0% (L 16.1%/lazy 71.0%/save 0.0%/other+no-stack 12.9%) |
| industry_productivity | xlsx-inspect-tool 40.2% (L 88.2%/lazy 0.0%/save 0.0%/other+no-stack 11.8%); xlsx-enhance 22.4% (L 36.4%/lazy 0.0%/save 59.7%/other+no-stack 3.9%); xlsx-recalc 14.2% (L 0.1%/lazy 91.2%/save 0.0%/other+no-stack 8.7%); xlsx-verify 11.7% (L 87.0%/lazy 0.1%/save 0.0%/other+no-stack 13.0%); xlsx-summary-export 11.4% (L 90.7%/lazy 0.0%/save 0.0%/other+no-stack 9.3%) |

**边界：** read_only 后续 XML/worksheet generator/accessor 栈计入 lazy scan；若该栈仍嵌套在 load_workbook 中，样本按 load_call 归类一次。yield 单元格后的业务比较/样式验证归 other。Workbook.save 只识别 openpyxl workbook writer 栈，不包含 JSON save 或模块导入。

## 采集质量、限制和解释

| Native 配置 | lost samples | lost chunks | addr2line 警告 | unknown DSO period / ROI | unresolved leaf-symbol period / ROI | inline-owner unresolved period / ROI | 空栈 period / ROI |
|---|---:|---:|---:|---:|---:|---:|---:|
| retail | 471 | 45 | 321 | 4,073,588 / 0.0% | 413,886,828 / 1.9% | 778,161,949 / 3.5% | 277 / 0.0% |
| hr | 31 | 5 | 167 | 9,257,071 / 0.1% | 452,988,096 / 3.1% | 316,522,294 / 2.2% | 22 / 0.0% |
| industry_productivity | 63 | 11 | 334 | 1,489,118,943 / 0.1% | 2,027,897,035 / 0.1% | 26,504,781,879 / 1.9% | 58 / 0.0% |
| irs_w4-n1 | not recorded | not recorded | not recorded | 226,789,602 / 0.3% | 332,608,344 / 0.5% | 2,257,834,154 / 3.1% | 0 / 0.0% |
| irs_w4-n10 | not recorded | not recorded | not recorded | 335,965,797 / 0.3% | 521,303,560 / 0.5% | 2,221,714,284 / 2.0% | 0 / 0.0% |
| sba1919-n1 | not recorded | not recorded | not recorded | 247,258,697 / 0.3% | 495,962,384 / 0.5% | 2,132,521,468 / 2.3% | 0 / 0.0% |
| sba1919-n10 | not recorded | not recorded | not recorded | 395,568,052 / 0.3% | 790,354,865 / 0.6% | 2,476,912,237 / 1.7% | 0 / 0.0% |

lost samples 与 lost chunks 是不同来源的采集区间计数，ROI 归属未知；addr2line 警告只表示解析警告条数，不等同丢失样本。解析质量字段的样本数/period 权重可能相互重叠（如 unresolved symbol 与 inline owner），不可相加。
- 历史 /home/lcq/document_perf 中的 native 原始文件存在；本轮没有纳入或重新导出。历史对比只能使用 document-oe 报告汇总值，逐函数历史对照留空。
- 当前旧 OPM/TLC 与历史执行版本、runner/环境并非逐字节同一；变化是描述性比较，不是逐函数复现。
- native OPM/TLC 有两次重复；新 XLSX 和 PDF 各配置只有一次，无法估计新配置内波动或稳定性。
- Retail native 使用离线恢复后的 parser 输出，原采集失败记录仍保留失败；恢复只修复解析/归档资格，不代表重新采集。
- lost samples 与 lost chunks 分开记录，均来自采集报告/记录，ROI 归属未知；不转换为 cycles 权重。文本导出解析完整不等同采集无丢样。
- addr2line 警告、未知 DSO、未知符号与未恢复 inline owner 分别保留在各 native profile 的质量字段；符号警告数量不能代表其 period 影响。
- ROI marker 通过 PERFROI 中点与 stdout 时间估计对齐，尚未校准，缓冲/偏移误差未知。
- TLC/新 XLSX 的验证合约、输入结构和模块读取路径不同；工作量差异不归因于行业。Manufacturing 仅列为历史资料，不纳入主对比。
- py-spy 的 load/lazy/save 值是 Python 活动采样估计；不包括纯 native LibreOffice 活动，不可换算为函数墙钟或 native cycles。
- 脚本按实际进程身份和命令职责对齐。相同 role 名称不代表源码相同；旧 OPM/TLC 未保存逐 PID 执行文件 hash，跨版本脚本同一性无法确认。新 run 的 runner/recipe/verifier/helper hash 按 record 保留，不能外推为所有进程脚本的 hash。
- 样本 period 权重比样本数量更能表示 cycles:u 份额；JSON 保留两者及未展示余量。函数榜仅列前 30，未展示权重与 unknown 仍在完整分母中。
- 共同解释器/Expat/zlib/LibreOffice 库和函数仅能说明共同原生执行路径；不能推出同一 Python 业务算法、算法效率或优化收益。

## 可追溯交付

数值和每个 profile 的 period、样本数、质量字段、证据路径、执行身份见 `comparison.json`；本次分析代码与证据关联见 `analysis-build.json`。
