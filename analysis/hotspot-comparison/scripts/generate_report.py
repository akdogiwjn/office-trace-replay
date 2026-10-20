#!/usr/bin/env python3
"""Generate reports/comparison-report.md from the processed tables."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "processed"
R = ROOT / "reports"

MECH_NAME = {
    "M-XLSX-LOAD": "openpyxl 载入（ZIP+XML 解析+对象构建）",
    "M-XLSX-SAVE": "openpyxl 保存（et_xmlfile+ZIP 压缩）",
    "M-XLSX-TRAVERSE": "openpyxl 遍历/校验逻辑",
    "M-LO-RECALC": "LibreOffice 重算与保存",
    "M-PDF-QPDF-PARSE": "pypdf 对象解析/读取",
    "M-PDF-FORMFILL": "pypdf 表单填写与写出",
    "M-POPPLER-RASTER": "Poppler 栅格化（pdftoppm/pdfinfo）",
    "M-PILLOW-IMG": "Pillow 图像处理/PNG 编码（含 zlib）",
    "M-JSON-MAPPING": "字段映射 JSON 生成/驱动/摘要",
    "M-ORCH": "调度与外壳（runner/bash/reset）",
    "M-UNCLASSIFIED": "未归类",
}
SELECTION_PATH = ROOT / "config" / "next-comparison-suite.json"


def selected_config_order():
    selection = json.loads(SELECTION_PATH.read_text())
    result = []
    for dataset in selection["baseline_datasets"] + selection["comparison_datasets"]:
        if dataset in ("opm", "irs_w4", "sba1919"):
            result.extend((dataset + "-n1", dataset + "-n10"))
        else:
            result.append(dataset)
    return list(dict.fromkeys(result))


CONFIG_ORDER = selected_config_order()
CONFIG_KIND = {
    "opm-n1": "旧对照 N=1", "opm-n10": "旧对照 N=10",
    "irs_w4-n1": "新 N=1", "irs_w4-n10": "新 N=10",
    "sba1919-n1": "新 N=1", "sba1919-n10": "新 N=10",
    "tlc": "旧对照", "retail": "历史 XLSX 对照", "manufacturing": "历史 XLSX 对照",
    "hr": "历史 XLSX 对照", "retail_online": "新（手工适配，功能/深审/性能证据已存在）",
    "hr_metro": "新（手工适配，功能/深审/性能证据已存在）",
    "industry_productivity": "新 XLSX 对照",
}


def load(name):
    path = P / name
    return json.load(open(path)) if path.is_file() else None


def fmt_pct(x, digits=1):
    return f"{x * 100:.{digits}f}%"


def main():
    R.mkdir(exist_ok=True)
    profiles = load("all-profiles.json") or {}
    coverage = load("coverage.json") or {}
    hotspots = load("new-hotspots.json") or []
    claims = load("claims-verification.json") or []
    lines = []
    w = lines.append

    w("# 新旧数据集计算热点对比报告")
    w("")
    selection = json.loads(SELECTION_PATH.read_text())
    w("未来主分析选择（读取 `config/next-comparison-suite.json`）：" +
      ", ".join(selection["baseline_datasets"] + selection["comparison_datasets"]) +
      "。Manufacturing 历史原始数据、recipe、trace 与结果保留，但从后续 XLSX 主对比中排除。")
    w("")
    w("最终研究结论见 [final-conclusions.md](final-conclusions.md)；"
      "未确认覆盖余量的逐样本分解见 [unconfirmed-residual-report.md](unconfirmed-residual-report.md)。")
    w("")
    w("口径：采集计划使用 v9 镜像（本批实际运行 image ID 未单独记录）、Python 3.12.3、workload 绑定 CPU 0-7（8 核预算，新旧同一设置）、"
      "`perf cycles:u` 99 Hz（PDF）/49 Hz（XLSX）DWARF 调用栈，period 加权；"
      "py-spy 独立运行只作 Python 层机制构成证据。ROI 从 runner `start:` 行"
      "（预运行 hash 校验与环境探测之后）到进程结束，业务 verifier 在内。"
      "每个 native 配置 2 次独立重复。详见 `config/run-plan.json`、"
      "`config/mechanism-taxonomy.json` 与 `README.md`。")
    w("")

    # ---- coverage table
    w("## 1. 旧切片覆盖率（规则版本及修正依据见 taxonomy 和 metadata）")
    w("")
    w("覆盖分母为完整 workload ROI 的用户态 cycles:u 样本 period 总和。执行路径与旧切片机制分别按样本求并集，并单列交集；函数/调用路径是更细的旁证，不能推断业务算法相同。"
      "‘未覆盖余量’、真未知 native、原生机制已知但业务操作未知是诊断维度，彼此可能重叠，不能相加。每个 native 样本只归入一个互斥机制。monitor CPU 时间仅作独立交叉核对。")
    w("")
    w("| 配置 | 类型 | 路径∪机制 | 执行路径 | 机制证据 | 交集 | 叶函数相同 | 规范化栈前缀指纹 | 旧定义机制候选 | 未覆盖余量 | 真未知 native | 原生已知/业务操作未知 |")
    w("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for cid in CONFIG_ORDER:
        if cid not in coverage:
            continue
        c = coverage[cid]
        m = c["merged"]
        w(f"| {cid} | {CONFIG_KIND[cid]} | {fmt_pct(m['coverage_total'])} | "
          f"{fmt_pct(m['direct_path_share'])} | {fmt_pct(m['mechanism_evidence_share'])} | "
          f"{fmt_pct(m['path_mechanism_intersection_share'])} | "
          f"{fmt_pct(m.get('same_leaf_function_share', 0))} | "
          f"{fmt_pct(m.get('normalized_stack_prefix_fingerprint_match_share', 0))} | "
          f"{fmt_pct(m.get('documented_legacy_mechanism_without_matched_slice_samples_share', 0))} | "
          f"{fmt_pct(m['uncovered_share'])} | "
          f"{fmt_pct(m['true_unknown_native_share'])} | "
          f"{fmt_pct(m['native_mechanism_known_upper_operation_unknown_share'])} |")
    w("")

    # ---- process layer
    w("## 2. 进程层热点（cycles:u period，两次重复按 period 合并）")
    w("")
    for cid in CONFIG_ORDER:
        if cid not in profiles:
            continue
        p = profiles[cid]
        total = sum(d["total_period"] for d in p["repeats"].values())
        agg = {}
        for d in p["repeats"].values():
            for r, s in d["process_layer"].items():
                agg[r] = agg.get(r, 0) + s * d["total_period"] / total
        merged = sorted(agg.items(), key=lambda x: -x[1])
        w(f"### {cid}（{CONFIG_KIND[cid]}）")
        w("")
        w("| 进程/命令角色 | ROI cycles:u period 份额 |")
        w("|---|---|")
        for r, s in merged[:10]:
            w(f"| `{r}` | {fmt_pct(s)} |")
        w("")

    w("### Monitor CPU 时间交叉核对（独立口径）")
    w("")

    w("### 调用上下文（可重叠，不属于机制分母分区）")
    w("")
    w("采样点机制由叶函数与叶 DSO 分类；调用栈中较远的函数只记为上下文证据。上下文可与采样点机制冲突并可多重出现，因此各项权重可能重叠，不能和互斥的机制层相加。它们解释采样所在路径，不证明上层 Python 算法相同。")
    w("")
    for cid in CONFIG_ORDER:
        if cid not in profiles:
            continue
        p = profiles[cid]
        total = sum(d["total_period"] for d in p["repeats"].values())
        context = {}
        conflict = 0
        for d in p["repeats"].values():
            for name, share in d.get("context_mechanism_layer", {}).items():
                context[name] = context.get(name, 0) + share * d["total_period"] / total
            conflict += d.get("leaf_context_conflict_share", 0) * d["total_period"] / total
        w(f"- **{cid}**: 叶函数/调用者类别冲突 period {fmt_pct(conflict)}；" +
          ", ".join(f"{name} {fmt_pct(share)}" for name, share in sorted(context.items(), key=lambda x: -x[1])[:8]))
    w("")
    w("monitor 线程 CPU 时间不参与上方 cycles 覆盖率或三层热点分母。与 cycles 进程份额的逐角色差异见 `processed/monitor-cycles-crosscheck.json`。")
    w("")

    # ---- library layer
    w("## 3. 库层热点（native period 加权，两次重复合并）")
    w("")
    for cid in CONFIG_ORDER:
        if cid not in profiles:
            continue
        p = profiles[cid]
        total = sum(d["total_period"] for d in p["repeats"].values())
        weighted = {}
        for rep, d in p["repeats"].items():
            for k, v in d["library_layer"].items():
                weighted[k] = weighted.get(k, 0) + v * d["total_period"] / total
        merged = sorted(weighted.items(), key=lambda x: -x[1])
        w(f"### {cid}")
        w("")
        w("| 库类 | period 份额 |")
        w("|---|---|")
        for k, v in merged[:10]:
            w(f"| {k} | {fmt_pct(v)} |")
        w("")

    # ---- mechanism layer
    w("## 4. 采样点机制层（cycles:u period 权重；monitor CPU 时间不参与重加权）")
    w("")
    mechanism_ids = sorted(set().union(*(set(d.get("mechanism_layer", {}))
                                         for p in profiles.values()
                                         for d in p.get("repeats", {}).values())))
    w("互斥采样点机制只由叶函数和叶 DSO 决定；例如 libpython 中解释器、引用计数、GC、分配、容器和类型检查分别列出。调用栈较远的函数单独记为上下文，可能与叶机制冲突且相互重叠。已知运行时工作但无法恢复 Python 业务操作的样本仍计入原生机制，业务操作另列未知。py-spy 不分配到 cycles。")
    w("")

    w("### 旧 joined-stack 分类器的影响诊断")
    w("")
    w("本节把旧版‘叶函数+整条栈’规则重新套用到同一采样，仅量化分类改变，不参与当前覆盖率。以下比例是旧规则类别→叶函数规则类别的 ROI period。")
    w("")
    impact = load("mechanism-classifier-impact.json") or {}
    w("| Dataset | 旧类别 → 叶函数类别 | period 权重 |")
    w("|---|---|---:|")
    for cid in CONFIG_ORDER:
        for transition, share in sorted(impact.get(cid, {}).get("legacy_context_classifier_transition_share", {}).items(), key=lambda x: -x[1]):
            old, new = transition.split("|", 1)
            if old != new and share > 0:
                w(f"| {cid} | {old} → {new} | {fmt_pct(share)} |")
    w("")
    w("### 栈前缀匹配质量")
    w("")
    w("指纹最多取前 8 帧，至少 4 帧且没有未知符号/DSO 才参与匹配；符号去掉偏移，DSO 归并为类别，同地址内联帧使用实体帧类别。短栈、未知帧不匹配。截断会忽略更深调用者，DSO 类别会合并不同具体库；相等只表示规范化前缀相等，不表示完整路径或代码身份。")
    w("")
    w("| Dataset | 可用于栈前缀匹配的 period 份额 |")
    w("|---|---:|")
    for cid in CONFIG_ORDER:
        if cid not in profiles:
            continue
        p = profiles[cid]
        total = sum(d["total_period"] for d in p["repeats"].values())
        eligible = sum(d.get("stack_prefix_fingerprint_quality", {}).get("eligible_match_period_share", 0) * d["total_period"] for d in p["repeats"].values())
        w(f"| {cid} | {fmt_pct(eligible / total if total else 0)} |")
    w("")
    w("| 配置 | " + " | ".join(mechanism_ids) + " |")
    w("|---" * (len(mechanism_ids) + 1) + "|")
    for cid in CONFIG_ORDER:
        if cid not in profiles:
            continue
        p = profiles[cid]
        if not any(d.get("mechanism_layer") for d in p["repeats"].values()):
            continue
        cells = []
        for m in mechanism_ids:
            v = sum(d.get("mechanism_layer", {}).get(m, 0) * d["total_period"]
                    for d in p["repeats"].values()) / sum(
                        d["total_period"] for d in p["repeats"].values())
            cells.append(fmt_pct(v))
        w(f"| {cid} | " + " | ".join(cells) + " |")
    w("")

    # ---- function layer summary
    w("## 5. 函数/调用栈层（要点，完整表在 processed/）")
    w("")
    for cid in CONFIG_ORDER:
        if cid not in profiles:
            continue
        p = profiles[cid]
        w(f"### {cid}")
        w("")
        for rep, d in sorted(p["repeats"].items()):
            top = d["function_layer"][:8]
            w(f"- **{rep}**（ROI {d['roi_samples']} 样本，"
              f"{d['total_period']/1e9:.1f}G cycles 近似）：")
            for e in top:
                w(f"  - `{e['role']}` / {e['dso_class']} / `{e['symbol']}` — "
                  f"{fmt_pct(e['share_of_roi'])}")
        pyspy = p.get("pyspy", {}).get("roles", {})
        if pyspy:
            total = sum(v["samples"] for v in pyspy.values())
            top_scripts = sorted(((r, v["samples"] / total) for r, v in pyspy.items()),
                                 key=lambda x: -x[1])[:6]
            w("- py-spy Python 层主要脚本：" +
              "，".join(f"`{r}` {fmt_pct(s)}" for r, s in top_scripts))
        w("")

    # ---- new hotspots
    w("## 6. 热点分类（单项 ≥0.5% ROI；逐次匹配后按 period 合并）")
    w("")
    w("已覆盖机制热点、旧脚本执行路径内的机制未知热点、未覆盖路径、候选机制和未知项分开列示；“热点”不自动表示新增机制。各次重复权重在 JSON 中保留。")
    w("")
    by_config = {}
    for h in hotspots:
        by_config.setdefault(h["config"], []).append(h)
    for cid in CONFIG_ORDER:
        if cid not in by_config:
            continue
        w(f"### {cid}")
        w("")
        w("| 进程/脚本 | DSO | 叶函数/实体 / 代表栈 | 合并权重 | r1 / r2 | 直接路径部分 | 采样点机制 | 调用上下文（可重叠） | 栈前缀匹配权重 | 分类 |")
        w("|---|---|---|---:|---:|---:|---|---|---:|---|")
        for h in by_config[cid][:12]:
            stack = "; ".join(h.get("callstack_by_repeat", {}).get("r1", [])[:4])
            if not stack:
                stack = "; ".join(h.get("callstack_by_repeat", {}).get("r2", [])[:4])
            reps_text = " / ".join(fmt_pct(h.get("repeat_shares", {}).get(rep, 0)) for rep in ("r1", "r2"))
            w(f"| `{h['role']}` | {h.get('dso') or h['dso_class']} | `{h['symbol']}` / `{h.get('entity_symbol') or 'unknown'}`; `{stack}` | "
              f"{fmt_pct(h['cpu_weight'])} | {reps_text} | {fmt_pct(h.get('direct_path_weight_share', 0))} | "
              f"{h['mechanism']} | {', '.join(h.get('context_mechanisms', [])) or '—'} | "
              f"{fmt_pct(h.get('normalized_stack_prefix_fingerprint_match_weight_share', 0))} | {h['classification']} |")
        w("")

    w("### 阈值余量")
    w("")
    residuals = load("hotspot-threshold-summary.json") or {}
    w("| 配置 | 列出权重 | 阈值以下/未列出 | 未知总权重 | 旧定义机制候选（无切片样本） | 分类总和 |")
    w("|---|---:|---:|---:|---:|---:|")
    for cid, x in residuals.items():
        w(f"| {cid} | {fmt_pct(x.get('listed_hotspot_share', 0))} | "
          f"{fmt_pct(x.get('below_threshold_or_function_retention_residual_share', 0))} | "
          f"{fmt_pct(x.get('unknown_mechanism_share', 0))} | "
          f"{fmt_pct(x.get('documented_legacy_mechanism_without_matched_slice_samples_share', 0))} | "
          f"{fmt_pct(x.get('period_partition_sum', 0))} |")
    w("")

    w("## 7. 旧切片逐项执行路径核对")
    w("")
    w("执行路径依据采样时刻的实际 argv/父进程 argv，依次核实 Docker 安装路径、runner seed→workspace 复制和精确 recipe 写入；角色名或 basename 本身不构成匹配。source context 不自动作为执行脚本。路径匹配和机制归属是独立证据。")
    w("")
    source_audit = load("../metadata/source-resolution-audit.json") or {}
    acceptance = source_audit.get("image_acceptance", {})
    w(f"来源审计：Dockerfile `{source_audit.get('docker', {}).get('install_rule')}`；runner SHA256 `{source_audit.get('docker', {}).get('runner_sha256')}`。计划镜像 `{acceptance.get('image_id')}` 验收状态 `{acceptance.get('status')}`，文件 `{acceptance.get('workload_files')}`；本次采集记录的实际 image ID 仍未知。旧 OPM/TLC `source=None`，seed 分别来自 `/opt/document-bench/pdf`、`/opt/document-bench/xlsx`，runner reset 通过 copytree 放入 workspace。")
    w("")
    w("| 核心来源争议 | 按实际入口重建的来源 | 旧冻结 hash | 仓库来源 hash | 结论 |")
    w("|---|---|---|---|---|")
    for sid in ("PDF-S6", "X-S4", "X-S7"):
        x = source_audit.get("known_snapshot_comparison_traps", {}).get(sid, {})
        frozen = source_audit.get("frozen_slice_source_checks", {}).get(sid, {})
        w(f"| {sid} | `{x.get('runtime_path')}` → `{x.get('runtime_chain_source')}` | `{frozen.get('expected_sha256')}` | `{x.get('runtime_chain_sha256')}` | {('hash verified' if frozen.get('repository_hash_matches') else 'hash unresolved')}; source snapshot 不是该入口的执行来源 |")
    w("")
    slice_map = load("legacy-slice-mapping.json") or {}
    w("| Slice | 配置/重复 | 状态 | period 份额 | 实际脚本/命令 | 来源等级及 hash/推导 | 未匹配原因 |")
    w("|---|---|---:|---:|---|---|---|")
    for cid, repeats in slice_map.items():
        for rep, slices in repeats.items():
            for sid, x in slices.items():
                source_rows = x.get("source_evidence", [])
                candidate_rows = x.get("candidate_source_evidence", [])
                actual_paths = sorted({e.get("resolved_script", "") for e in source_rows if e.get("resolved_script")})
                candidate_paths = sorted({e.get("resolved_script", "") for e in candidate_rows if e.get("resolved_script")})
                commands = "; ".join(actual_paths) or "—"
                if not actual_paths and candidate_paths:
                    commands = "候选（执行/内容未确认）: " + "; ".join(candidate_paths)
                reason = x.get("unmatched_reason") or ""
                sources = source_rows + candidate_rows
                summaries = []
                for e in sources:
                    src = e.get("source", {})
                    summary = (e.get("evidence_level", e.get("evidence_grade", "unknown")) +
                        f"; cwd={e.get('cwd')}; frozen={src.get('frozen_source_sha256') or src.get('source_sha256')}; "
                        f"repo_hash_ok={src.get('repository_source_hash_verified', src.get('source_hash_verified', 'unknown'))}; "
                        f"origin={src.get('origin')}; source={src.get('repository_path')}; "
                        f"cwd_chain={bool(e.get('cwd_resolution') or src.get('cwd_resolution'))}")
                    if summary not in summaries:
                        summaries.append(summary)
                source_text = "; ".join(summaries) or "无直接/候选来源证据"
                w(f"| {sid} | {cid}/{rep} | {x.get('status')} | "
                  f"{fmt_pct(x.get('sampled_period_share', 0))} | `{commands}` | {source_text} | {reason} |")
    w("")
    w("完整 14 项汇总及来源链见 `processed/legacy-slice-source-map.json`。安装/seed/recipe hash 为按冻结运行规则重建，不是历史进程直接采集的文件 hash。运行时来源文件与旧切片内容一致时计路径匹配；只有 source snapshot 同名 hash 不同不构成冲突。父子范围仅按切片定义传递；PID 观察窗口和无退出时间戳的限制见来源 JSON。")
    w("")

    w("## 8. strace 汇总（调用次数与累计 syscall 时间分开）")
    w("")
    w("`-c` seconds 为 syscall 累计耗时，可能包含阻塞等待，不是内核 CPU 时间；aggregate 结果不能证明 futex 来自 LibreOffice 进程。")
    w("")
    w("| Dataset | futex calls / share | futex seconds / share | calls 总和核对 | calls 排名前三 | 进程归属 |")
    w("|---|---:|---:|---|---|---|")
    for cid in CONFIG_ORDER:
        if cid not in profiles:
            continue
        d = profiles[cid].get("syscalls")
        if not d:
            continue
        f = d.get("futex", {})
        calls_top = ", ".join(f"{x['syscall']}={x['calls']}" for x in d.get("calls_ranked", [])[:3])
        w(f"| {cid} | {f.get('calls', 0)} / {fmt_pct(d.get('futex_call_share', 0))} | "
          f"{f.get('seconds', 0):.6f}s / {fmt_pct(d.get('futex_time_share', 0))} | "
          f"{d.get('calls_sum')} = total {d.get('total_calls')} ({'一致' if d.get('calls_total_matches') else '不一致'}) | "
          f"{calls_top} | {d.get('process_attribution', 'unknown')} |")
    w("")

    w("## 9. 内联帧修正前后影响")
    w("")
    w("解析器仅在首帧与连续内联帧同地址时，使用后续实体帧的 DSO；保留首个内联函数作为热点。未知叶节点不继承其他地址的调用者 DSO。下表与旧派生库分布比较，原始采样 period 未改变。")
    w("")
    correction = load("parser-correction-impact.json") or {}
    w("| Dataset | Repeat | 旧 unknown DSO | 新 unknown DSO | 变化 | libpython 变化 | XML DSO 变化 |")
    w("|---|---|---:|---:|---:|---:|---:|")
    for cid in CONFIG_ORDER:
        for rep, x in correction.get(cid, {}).items():
            ch = x.get("library_share_changes_pp", {})
            xml = ch.get("expat-xml", 0) + ch.get("elementtree-xml", 0)
            w(f"| {cid} | {rep} | {fmt_pct(x.get('before_unknown_dso_share', 0))} | "
              f"{fmt_pct(x.get('after_unknown_dso_share', 0))} | "
              f"{x.get('unknown_dso_change_pp', 0):+.1f} pp | {ch.get('libpython', 0):+.1f} pp | {xml:+.1f} pp |")
    w("")
    quality = load("../metadata/native-parse-quality.json") or {}
    w("| Dataset | Repeat | ROI 样本 | 内联恢复 period | 真未知 DSO period | 内联实体未恢复 | 未解析符号 | 空栈 | Lost 样本 | malformed frame 行 |")
    w("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for cid in CONFIG_ORDER:
        for rep, x in quality.get(cid, {}).items():
            q = x.get("perf_script_parse", {})
            denom = x.get("roi_period_total") or 1
            w(f"| {cid} | {rep} | {x.get('roi_samples', 0)} | "
              f"{fmt_pct(q.get('inline_recovered_period', 0)/denom)} | "
              f"{fmt_pct(q.get('true_unknown_dso_period', 0)/denom)} | "
              f"{fmt_pct(q.get('inline_owner_unresolved_period', 0)/denom)} | "
              f"{fmt_pct(x.get('unresolved_leaf_symbol_period_share', 0))} | "
              f"{fmt_pct(q.get('empty_stack_period', 0)/denom)} | "
              f"{x.get('perf_report_lost_samples') if x.get('perf_report_lost_samples') is not None else '未知'} | "
              f"{q.get('malformed_frame_lines', 0)} |")
    w("")

    # ---- claims
    w("## 10. 旧结论逐条验证")
    w("")
    legacy_claims = json.load(open(ROOT / "legacy" / "legacy-claims.json"))
    claim_text = {c["claim_id"]: c for c in legacy_claims["claims"]}
    w("| Claim | 旧结论（原文） | Dataset | 当前对照与定量证据 | 状态 | 判定依据 | 证据路径 | 适用边界 |")
    w("|---|---|---|---|---|---|---|---|")
    status_order = {"supported": 0, "partially-supported": 1, "not-supported": 2,
                    "insufficient-evidence": 3, "not-applicable": 4}
    for row in sorted(claims, key=lambda r: (r["claim_id"],
                                             status_order.get(r["status"], 9))):
        c = claim_text.get(row["claim_id"], {})
        brief = row.get("legacy_claim", c.get("original", ""))
        brief = brief.replace("|", "\\|")
        ev = row["evidence"].replace("|", "\\|")
        boundary = row.get("applicability_boundary", "").replace("|", "\\|")
        basis = row.get("decision_basis", "").replace("|", "\\|")
        path = "; ".join(row.get("evidence_paths", [])) or row.get("evidence_path", "")
        path = path.replace("|", "\\|")
        w(f"| {row['claim_id']} | {brief} | {row.get('dataset') or 'multiple'} | {ev} | "
          f"{row['status']} | {basis} | {path} | {boundary} |")
    w("")

    # ---- method & limitations
    w("## 11. 方法、限制与未完成项")
    w("")
    w("- 权重方法：`cycles:u` 原始 perf sample period 求和，作为每个样本代表 cycles 的估计；"
      "这是频率模式 perf 对采样周期的内核估计，不是精确硬件计数。monitor CPU 时间独立列示，"
      "不得用于修正覆盖率。")
    w("- ROI 时间边界是估计：stdout `start:` 到达时刻与 PERFROI 约 300ms marker 样本中位数对齐。"
      "每次 marker 的采样跨度见 `metadata/native-parse-quality.json`；stdout 缓冲和采样频率适应造成的偏移未独立校准，误差无法量化。"
      "因此不能声称严格排除了全部预运行活动；runner start 行之前的预运行检查不在设计 ROI，但边界样本可能受对齐误差影响。")
    w("- cycles 与 monitor CPU 时间按进程角色的差异见 `processed/monitor-cycles-crosscheck.json`；"
      "两者时间窗、轮询丢失和线程身份处理不同，差异保留为交叉核对信号，不把差异直接解释为 perf 低估。")
    w("- 热点阈值为单函数/角色/DSO 聚合权重 ≥0.5% ROI；阈值以下及 profile 保留阈值以下的合计余量见"
      " `processed/hotspot-threshold-summary.json`。无法分类热点单列，不能据此称作新机制。")
    w("- 可复现范围：汇总 JSON、metadata 和压缩的详细 profiles 随仓库发布；"
      "先执行 `scripts/profile_artifacts.py restore` 恢复详细画像。"
      "原始 perf/monitor 数据只在采集机本地保留（gitignored），体积与 SHA256 见 `raw/index.json`。"
      "clone 仓库可以复核派生表，但缺少 raw 时不能重做采样解析；命令在 README 中列明。")
    w("- 采集质量：每个 native 配置 2 次独立重复；丢失样本、未解析符号与未归类比例"
      "记录在各 processed/<config>.json 的 unresolved 字段。")
    w("- 10-25ms monitor 轮询中的线程 CPU 计数增量只表示该间隔内曾获得过 CPU，"
      "不表示同时运行；不据此推断瞬时并行度或串行性，旧调度类结论记为证据不足。")
    w("- strace `-c` 的 seconds 是系统调用耗时累计，包含阻塞等待，不能解释为内核 CPU 时间。"
      "py-spy 每配置仅有一次独立采集，脚本/函数比例没有重复波动估计；W-4 N=1 虽有完整写出样本但 collector 返回错误，状态未改写为成功。")
    w("- 未采集支持缓存/内存瓶颈判断所需的专门计数器；未验证优化收益或跨硬件外推。")
    build_meta = json.load(open(ROOT / "metadata" / "analysis-build.json"))
    w("")
    w("分析代码 SHA256（本报告对应的源码）：")
    for path, digest in build_meta.get("analysis_code_sha256", {}).items():
        w(f"- `{path}`: `{digest}`")

    (R / "comparison-report.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {R / 'comparison-report.md'} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
