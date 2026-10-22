# XLSX 单脚本切片

该目录已经保存一次完整成功运行产生的阶段输入。后续采 trace 时只恢复目标脚本所需输入，并启动一个选定的 Python 脚本，不再重复执行四步骤场景。

## 使用

```bash
/opt/document-bench-slicing-xlsx/run_slice.sh XLSX-01
```

也支持：

```bash
/opt/document-bench-slicing-xlsx/run_slice.sh --slice XLSX-04
```

| ID | 启动脚本 | 输入状态 |
|---|---|---|
| XLSX-01 | `inspect_xlsx_structure.py` | 原始工作簿 |
| XLSX-02 | `inspect_xlsx_features.py` | 原始、未增强工作簿 |
| XLSX-03 | `enhance_workbook.py` | 原始、未增强工作簿 |
| XLSX-04 | `recalc.py` | 已增强、未重算工作簿 |
| XLSX-05 | `inspect_xlsx_formulas.py` | 重算后工作簿 |
| XLSX-06 | `inspect_xlsx_cached_values.py` | 重算后工作簿 |
| XLSX-07 | `verify_xlsx_enhanced.py` | 重算后工作簿、重算JSON、两个CSV |
| XLSX-08 | `write_xlsx_summary.py` | XLSX-07所需输入及业务验证JSON |

需要插桩时直接修改根目录对应脚本。每次启动前，`run_slice.sh` 都会重新复制保存的输入，避免上一次执行修改工作簿后影响下一次采集。

脚本输入准备发生在目标 Python 进程启动前。若插桩逻辑位于目标 Python 脚本内，文件复制不会进入采集区间。
