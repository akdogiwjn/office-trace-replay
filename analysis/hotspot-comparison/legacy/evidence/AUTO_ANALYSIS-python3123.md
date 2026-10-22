# 文档场景白盒自动汇总

本报告由 `analyze_whitebox.py` 自动生成。热点百分比以 `perf cycles:u` 为分母，步骤百分比以墙钟时间为分母，两者不能混用。

## PDF 场景

- Python：`unknown`
- 循环数：unknown
- 平均整轮耗时：2.241 秒
- perf lost samples：0
- py-spy：1372 samples，0 errors

### 四步骤耗时

| 步骤 | 平均耗时 | 墙钟占比 |
|---|---:|---:|
| P01 检查与准备 | 0.910 s | 40.62% |
| P02 构建输入 | 0.052 s | 2.34% |
| P03 填写与渲染 | 0.953 s | 42.54% |
| P04 验证交付 | 0.323 s | 14.40% |

### 进程 CPU 周期热点

| 进程名 | cycles:u 占比 |
|---|---:|
| `python3` | 90.64% |
| `pdftoppm` | 9.23% |
| `pdfinfo` | 0.09% |
| `bash` | 0.04% |

### 动态库热点

| 进程 | 动态库 | cycles:u 占比 |
|---|---|---:|
| `python3` | `libpython3.12.so.1.0` | 53.58% |
| `python3` | `libz.so.1.2.13` | 18.14% |
| `python3` | `_imaging.cpython-312-aarch64-linux-gnu.so` | 15.21% |
| `pdftoppm` | `libpoppler.so.133.0.0` | 6.27% |
| `python3` | `libc.so.6` | 3.14% |
| `pdftoppm` | `libfreetype.so.6.20.1` | 1.88% |
| `pdftoppm` | `libc.so.6` | 0.84% |
| `python3` | `[unknown]` | 0.34% |
| `pdftoppm` | `libfontconfig.so.1.12.1` | 0.14% |
| `pdfinfo` | `libpoppler.so.133.0.0` | 0.08% |
| `pdftoppm` | `[unknown]` | 0.08% |
| `python3` | `_json.cpython-312-aarch64-linux-gnu.so` | 0.08% |

### 用户态、内核态与 IPC

| 模式 | 周期占比 | 指令占比 | CPU时间占比 | IPC |
|---|---:|---:|---:|---:|
| 用户态 | 86.07% | 93.07% | 86.79% | 2.55 |
| 内核态 | 13.93% | 6.93% | 13.21% | 1.17 |

### 调度与系统调用

- 活跃时间单任务占比：100.0000%
- 活跃时间多任务占比：0.0000%
- 峰值并行度：1
- 系统调用总数：733,955
- `wait4`：358 次，strace 跟踪时间占比 84.48%
- `sysinfo`：241 次，strace 跟踪时间占比 3.86%
- `read`：106,772 次，strace 跟踪时间占比 3.37%
- `write`：166,564 次，strace 跟踪时间占比 2.55%
- `ppoll`：68,198 次，strace 跟踪时间占比 1.02%

### 自动结论

- 最大进程热点为 `python3`，约占用户态 CPU 周期 90.64%。
- Python 函数级路径请结合本目录中的 py-spy SVG 查看。
- 占比用于同口径运行间比较；更换输入、循环规模或 recipe 后必须重新采集。

## XLSX 场景

- Python：`unknown`
- 循环数：unknown
- 平均整轮耗时：243.693 秒
- perf lost samples：659
- py-spy：22405 samples，6 errors

### 四步骤耗时

| 步骤 | 平均耗时 | 墙钟占比 |
|---|---:|---:|
| P01 检查与准备 | 56.526 s | 23.20% |
| P02 构建增强 | 53.499 s | 21.95% |
| P03 重算与发布 | 87.965 s | 36.10% |
| P04 验证交付 | 45.698 s | 18.75% |

### 进程 CPU 周期热点

| 进程名 | cycles:u 占比 |
|---|---:|
| `python3` | 92.52% |
| `soffice.bin` | 4.47% |
| `thread-pool` | 1.78% |
| `Parser` | 1.22% |

### 动态库热点

| 进程 | 动态库 | cycles:u 占比 |
|---|---|---:|
| `python3` | `libpython3.12.so.1.0` | 79.65% |
| `python3` | `pyexpat.cpython-312-aarch64-linux-gnu.so` | 5.61% |
| `python3` | `_elementtree.cpython-312-aarch64-linux-gnu.so` | 3.49% |
| `python3` | `libc.so.6` | 1.49% |
| `python3` | `libz.so.1.2.13` | 1.42% |
| `soffice.bin` | `libmergedlo.so` | 1.34% |
| `soffice.bin` | `libc.so.6` | 0.82% |
| `soffice.bin` | `libuno_sal.so.3` | 0.80% |
| `thread-pool` | `libuno_cppuhelpergcc3.so.3` | 0.79% |
| `soffice.bin` | `libsclo.so` | 0.62% |
| `python3` | `ld-linux-aarch64.so.1` | 0.49% |
| `Parser` | `libuno_sal.so.3` | 0.48% |

### 用户态、内核态与 IPC

| 模式 | 周期占比 | 指令占比 | CPU时间占比 | IPC |
|---|---:|---:|---:|---:|
| 用户态 | 97.83% | 99.24% | 98.12% | 2.53 |
| 内核态 | 2.17% | 0.76% | 1.88% | 0.87 |

### 调度与系统调用

- 活跃时间单任务占比：98.3111%
- 活跃时间多任务占比：1.6889%
- 峰值并行度：4
- 系统调用总数：556,023
- `futex`：111,894 次，strace 跟踪时间占比 79.87%
- `wait4`：164 次，strace 跟踪时间占比 14.72%
- `madvise`：5,149 次，strace 跟踪时间占比 2.09%
- `accept`：7 次，strace 跟踪时间占比 1.39%
- `rt_sigprocmask`：21,226 次，strace 跟踪时间占比 1.09%

### 自动结论

- 最大进程热点为 `python3`，约占用户态 CPU 周期 92.52%。
- Python 函数级路径请结合本目录中的 py-spy SVG 查看。
- 占比用于同口径运行间比较；更换输入、循环规模或 recipe 后必须重新采集。
