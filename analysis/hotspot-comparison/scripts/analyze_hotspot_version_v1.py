#!/usr/bin/env python3
"""Build a scoped comparison from eligible current ROI profiles only.

Historical aggregates are imported only where their source report states a
matching scale. Current new XLSX profiles from the pre-loop verifier era are
deliberately not promoted to current-version evidence.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "reports/hotspot-version-comparison-v1"
EVIDENCE_BASE = OUT
PROCESSED = BASE / "processed"
CAMPAIGN = BASE / "raw/current-loop-verifier-v1"
sys.path.insert(0, str(BASE / "scripts"))
import build_profiles as bp


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def aggregate_processed(config):
    d = read(PROCESSED / f"{config}.json")
    total = sum(r["total_period"] for r in d["repeats"].values())
    proc, lib = Counter(), Counter()
    funcs = Counter(); func_contexts = {}
    periods = {}
    per_repeat = {}
    for name, r in d["repeats"].items():
        periods[name] = r["total_period"]
        repeat_total = r["total_period"]
        per_repeat[name] = {
            "roi_period": repeat_total,
            "process_share": {k: v / repeat_total for k, v in r["process_layer_counts"].items()},
            "library_share": r["library_layer"],
            "roi_samples": r.get("roi_samples"),
        }
        proc.update(r["process_layer_counts"])
        for k, share in r["library_layer"].items():
            lib[k] += share * r["total_period"]
        for f in r["function_layer"]:
            key = (f.get("role"), f.get("dso_class"), Path(f.get("dso") or "").name,
                   f.get("symbol"), f.get("entity_symbol"), Path(f.get("entity_dso") or "").name)
            weight = f.get("share_of_roi", 0) * r["total_period"]
            funcs[key] += weight
            context = tuple(f.get("top_callstack", [])[:6])
            if context:
                func_contexts.setdefault(key, Counter())[context] += weight
    return {
        "config_id": config, "repeat_count": len(periods), "repeat_period": periods,
        "per_repeat": per_repeat,
        "roi_period": total,
        "process_share": {k: v / total for k, v in proc.most_common()},
        "python_script_share": sum(v for k, v in proc.items() if k.startswith(("pdf-", "xlsx-", "python-")) or k in ("python-inline", "runner")) / total,
        "libreoffice_process_share": sum(v for k, v in proc.items() if k in ("soffice.bin", "lo-thread", "thread-pool", "Parser")) / total,
        "library_share": {k: v / total for k, v in lib.most_common()},
        "function_hotspots": [
            {"script_role": k[0], "dso_class": k[1], "dso": k[2], "leaf_function": k[3],
             "entity_function": k[4], "entity_dso": k[5],
             "call_context": list(func_contexts[k].most_common(1)[0][0]) if func_contexts.get(k) else [],
             "period": v, "share_roi": v / total}
            for k, v in funcs.most_common(30)
        ],
        "source": f"processed/{config}.json", "quality": "two parsed native repeats; each repeat retained",
    }


def aggregate_fresh_native(config):
    path = CAMPAIGN / config / "r1/out/samples.jsonl"
    roi = read(CAMPAIGN / config / "r1/out/roi.json")
    total = 0
    proc, libs, funcs = Counter(), Counter(), Counter(); func_contexts = {}
    sample_count = 0
    for line in path.open():
        if not line.strip():
            continue
        s = json.loads(line)
        p = int(s["period"])
        total += p
        sample_count += 1
        proc[s.get("role") or "unknown-role"] += p
        cls = bp.dso_class(s.get("leaf_dso", ""))
        libs[cls] += p
        key=(s.get("role"), cls, Path(s.get("leaf_dso") or "").name, s.get("leaf_sym"),
             s.get("entity_sym"), Path(s.get("entity_dso") or "").name)
        funcs[key] += p
        context=tuple(f"{f.get('symbol')} [{bp.dso_class(f.get('dso',''))}]" for f in s.get("stack",[])[:6])
        if context: func_contexts.setdefault(key,Counter())[context]+=p
    if total != roi["roi_period_total"] or sample_count != roi["roi_samples"]:
        raise ValueError(f"{config}: parsed sample period/count does not conserve ROI")
    meta = read(CAMPAIGN / config / "r1/out/collection-record.json")
    return {
        "config_id": config, "repeat_count": 1, "repeat_period": {"r1": total},
        "roi_period": total, "roi_samples": sample_count,
        "roi_quality": roi["perf_script_parse"],
        "process_share": {k: v / total for k, v in proc.most_common()},
        "python_script_share": sum(v for k, v in proc.items() if k.startswith(("pdf-", "xlsx-", "python-")) or k in ("python-inline", "runner")) / total,
        "libreoffice_process_share": sum(v for k, v in proc.items() if k in ("soffice.bin", "lo-thread", "thread-pool", "Parser")) / total,
        "library_share": {k: v / total for k, v in libs.most_common()},
        "function_hotspots": [
            {"script_role": k[0], "dso_class": k[1], "dso": k[2], "leaf_function": k[3],
             "entity_function": k[4], "entity_dso": k[5],
             "call_context": list(func_contexts[k].most_common(1)[0][0]) if func_contexts.get(k) else [],
             "period": v, "share_roi": v / total}
            for k, v in funcs.most_common(30)
        ],
        "source": f"raw/current-loop-verifier-v1/{config}/r1/out/samples.jsonl",
        "collection_status": meta["status"], "runner": meta["hashes"]["runner_sha256"],
        "recipe": meta["hashes"]["recipe_sha256"],
        "quality": "one complete native ROI profile, one workload capture; no repeat estimate",
    }


def pyspy_result(raw_path: Path, scene: str):
    spec = importlib.util.spec_from_file_location("scriptio", BASE / "scripts/analyze_script_io_comparison.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.analyze_raw(raw_path, scene)


def script_operation_raw(path: Path):
    spec = importlib.util.spec_from_file_location("scriptio_raw", BASE / "scripts/analyze_script_io_comparison.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    roles, ops = Counter(), {}
    for line in path.read_text().splitlines():
        if not line.strip(): continue
        stack, _, raw_count = line.rpartition(" "); count = int(raw_count)
        procs, frames = [], []
        for segment in stack.split(";"):
            m = mod.PROC.fullmatch(segment)
            (procs if m else frames).append(m.groups() if m else segment)
        if not procs: continue
        role = mod.role_for(procs[-1][1], "xlsx") or "other"
        roles[role] += count
        ops.setdefault(role, Counter())[mod.category(frames)] += count
    return {role: {"total_samples": n,
                   "operation_percent": {k: 100 * v / n for k, v in ops[role].items()}}
            for role, n in roles.items()}


def script_operation_svg(path: Path):
    spec = importlib.util.spec_from_file_location("scriptio_svg", BASE / "scripts/analyze_script_io_comparison.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    ns, fg = "{http://www.w3.org/2000/svg}", "{http://github.com/jonhoo/inferno}"
    root = mod.ET.parse(path).getroot()
    container = next(n for n in root.iter(ns + "svg") if n.get("id") == "frames")
    total = int(container.get("total_samples")); hits = [set() for _ in range(total)]
    role_depth = [(-1, "other") for _ in range(total)]; has = [False] * total
    import re
    for g in container:
        rect, title = g.find(ns + "rect"), g.find(ns + "title")
        if rect is None: continue
        name = re.sub(r" \([\d,]+ samples?, [\d.]+%\)$", "", title.text)
        start, count, depth = int(rect.get(fg+"x")), int(rect.get(fg+"w")), int(rect.get("y"))
        role = mod.role_for(name, "xlsx") if name.startswith("process ") else None
        op = mod.operation(name)
        for i in range(start, start+count):
            if role and depth > role_depth[i][0]: role_depth[i] = (depth, role)
            if op: hits[i].add(op)
            if name != "all" and not name.startswith(("process ", "thread ", "all (")): has[i] = True
    roles, ops = Counter(), {}
    for h, resolved, (_, role) in zip(hits, has, role_depth):
        op = next((k for k in ("load_call", "save", "lazy_scan") if k in h), "other" if resolved else "no_python_frames")
        roles[role] += 1; ops.setdefault(role, Counter())[op] += 1
    return {role: {"total_samples": n,
                   "operation_percent": {k: 100 * v / n for k, v in ops[role].items()}}
            for role, n in roles.items()}


def pct(x):
    return f"{x * 100:.1f}%"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    posthoc_path = BASE / "processed/loop-verifier-recheck-v1.json"
    posthoc = read(posthoc_path) if posthoc_path.is_file() else {}
    posthoc_datasets = posthoc.get("datasets", {})
    current = {}
    for cfg in ("opm-n1", "opm-n10", "tlc"):
        current[cfg] = aggregate_processed(cfg)
    for cfg in ("irs_w4-n1", "irs_w4-n10", "sba1919-n1", "sba1919-n10"):
        current[cfg] = aggregate_fresh_native(cfg)

    pyspy_profiles = {}
    for cfg in ("opm-n1", "opm-n10", "tlc"):
        pyspy_profiles[cfg] = pyspy_result(BASE / "raw" / cfg / "pyspy/raw" / f"{cfg}.pyspy.raw",
                                           "xlsx" if cfg == "tlc" else "pdf")
    for cfg in ("irs_w4-n1", "irs_w4-n10", "sba1919-n1", "sba1919-n10"):
        pyspy_profiles[cfg] = pyspy_result(CAMPAIGN / cfg / "pyspy/raw" / f"{cfg}.pyspy.raw", "pdf")

    # Explicit collection eligibility; failures remain visible but never enter ROI summaries.
    status = read(CAMPAIGN / "campaign-manifest.json")
    xlsx_new_status = {
        "retail": {"status": "not_eligible", "reason": "current loop verifier failed all five iterations at P04 base_sheet_scale; profile export incomplete"},
        "hr": {"status": "not_eligible", "reason": "current loop verifier failed all eight iterations at P04; profile export incomplete"},
        "industry_productivity": {"status": "not_eligible", "reason": "one functional iteration and verifier succeeded, but native perf-script export was stopped before complete parse; no py-spy run"},
    }

    # XLSX load/save estimates: same historical svg and the available current TLC
    # py-spy raw capture, with all process-only samples retained.
    hist_path = BASE / "legacy/evidence/python3123-pyspy/xlsx-python.svg"
    spec = importlib.util.spec_from_file_location("scriptio", BASE / "scripts/analyze_script_io_comparison.py")
    scriptio = importlib.util.module_from_spec(spec); spec.loader.exec_module(scriptio)
    xlsx_io = {
        "historical_tlc": scriptio.analyze_svg(hist_path, "xlsx"),
        "current_tlc": scriptio.analyze_raw(BASE / "raw/tlc/pyspy/raw/tlc.pyspy.raw", "xlsx"),
        "by_script_historical_tlc": script_operation_svg(hist_path),
        "by_script_current_tlc": script_operation_raw(BASE / "raw/tlc/pyspy/raw/tlc.pyspy.raw"),
        "new_datasets": {k: {"status": "unavailable", "reason": v["reason"]} for k, v in xlsx_new_status.items()},
        "definitions": {
            "A_load_workbook_call": "load_workbook internal stack, inclusive; subsequent samples are not double-counted",
            "B_read_only_lazy_scan": "executed read_only iterator/accessor parsing frames after load_workbook returns",
            "C_load_union": "A+B union, exclusive sample assignment in source analyzer",
            "D_save": "Workbook.save inclusive stack",
            "denominator": "all py-spy Python activity samples including process-only; these are Python active-time sampling estimates, not ROI wall-time shares or native cycles",
            "limitation": "No current eligible Retail/HR/Industry XLSX py-spy profile; historical strict-contract profiles are not presented as current lightweight-loop verifier evidence.",
        },
    }
    # Historical reported process/library comparisons (not raw reanalysis).
    historical = {
        "opm_n1": {
            "source": "legacy/evidence/ANALYSIS-python3123.md, section 4/5",
            "process": {"python3": .9064, "pdftoppm": .0923},
            "libraries": {"libpython": .5358, "zlib": .1814, "pillow": .1521, "poppler": .0627, "freetype": .0188},
            "scripts_pyspy": {"pdf-check-fillable": .0736, "pdf-extract-fields": .0977, "pdf-convert": .4388, "pdf-fill": .2121, "pdf-verify": .1429},
            "scope": "historical document-oe PDF single-applicant workload, 10 profile loops; environment identity limitations as reported",
        },
        "tlc": {
            "source": "legacy/evidence/ANALYSIS-python3123.md, section 4/5",
            "process": {"python3": .9252, "libreoffice+threads": .0747},
            "libraries": {"libpython": .7965, "expat-xml": .0561, "elementtree-xml": .0349, "zlib": .0142},
            "scripts_pyspy": {"xlsx-inspect-structure": .1358, "xlsx-inspect-features": .1109, "xlsx-enhance": .2345, "xlsx-recalc": .1261, "xlsx-verify": .1104, "xlsx-summary-export": .0882},
            "scope": "historical document-oe TLC-like complete workbook, 2 profile loops; this report uses historical aggregates and did not import/parse the extant local native file",
        },
    }
    # Report evidence provenance for every primary input.
    provenance_paths = [BASE / "processed/opm-n1.json", BASE / "processed/opm-n10.json", BASE / "processed/tlc.json",
                        posthoc_path,
                        BASE / "legacy/evidence/ANALYSIS-python3123.md", hist_path,
                        BASE / "legacy/evidence/python3123-pyspy/pdf-python.svg",
                        BASE / "raw/tlc/pyspy/raw/tlc.pyspy.raw", CAMPAIGN / "campaign-manifest.json",
                        CAMPAIGN / "retail/r1/failure-record.json", CAMPAIGN / "hr/r1/out/collection-record.json",
                        CAMPAIGN / "industry_productivity/r1/failure-record.json",
                        CAMPAIGN / "industry_productivity/r1/raw/industry_productivity.samples.txt"]
    for cfg in ("irs_w4-n1", "irs_w4-n10", "sba1919-n1", "sba1919-n10"):
        provenance_paths.extend([CAMPAIGN / cfg / "r1/out/samples.jsonl", CAMPAIGN / cfg / "pyspy/raw" / f"{cfg}.pyspy.raw",
                                 CAMPAIGN / cfg / "r1/out/collection-record.json", CAMPAIGN / cfg / "pyspy/out/collection-record.json"])
    for cfg in ("opm-n1", "opm-n10", "tlc"):
        provenance_paths.append(BASE / "raw" / cfg / "pyspy/raw" / f"{cfg}.pyspy.raw")
    data = {
        "schema": "hotspot-version-comparison-v1",
        "analysis_baseline": {"inventory": "reports/hotspot-version-comparison-v1/evidence-inventory.json", "inventory_sha256": sha(EVIDENCE_BASE / "evidence-inventory.json"),
                              "scope": "Complete workload ROI incl. loop business verifier; native primary shares from cycles:u sample-period weights. No elapsed phase timing used."},
        "current_profiles": current,
        "pyspy_script_profiles": pyspy_profiles,
        "historical_reported": historical,
        "current_loop_campaign": {"status": status.get("status"), "failures": status.get("failures", []), "xlsx_new": xlsx_new_status,
                                  "posthoc_loop_verification": {
                                      "evidence_path": str(posthoc_path.relative_to(BASE)) if posthoc_path.is_file() else None,
                                      "evidence_sha256": sha(posthoc_path) if posthoc_path.is_file() else None,
                                      "datasets": {name: {"status": item.get("status"), "failures": item.get("failures"),
                                                          "output_sha256": item.get("evidence", {}).get("output_workbook_sha256"),
                                                          "original_capture_record_sha256": item.get("evidence", {}).get("original_failure_record_sha256")}
                                                   for name, item in posthoc_datasets.items()}}},
        "xlsx_io": xlsx_io,
        "limits": ["本机历史 native 文件仍存在于 /home/lcq/document_perf/python-3.12.3/pdf/pdf-native.data 与 /home/lcq/document_perf/python-3.12.3/xlsx/xlsx-native.data；本轮未纳入/未解析。历史 process/library 数值仍是旧报告聚合，不是重解析样本。",
                   "Current OPM/TLC profiles have two native repeats but use runner SHA 3623f727…; the latest mounted runner is 559a5c9a… . The frozen OPM/TLC recipes and old workload files are unchanged, but runner identity differs.",
                   "Fresh new PDF profiles have one native capture each and one independent py-spy capture; no repeat variance is available.",
                   "Retail and HR collection records reflect failures under the prior loop verifier. Rechecking their preserved r1 workbooks with the corrected verifier now succeeds; the old captures remain ineligible because workload validation failed at capture time and their profile pipelines were incomplete. HR's original failures were semantic:scenario_dependency:projected_mean_wage and semantic:chart_dependency:major_employment, not an openpyxl warning. Industry Productivity succeeded functionally once, but native stack export was incomplete, so no hotspot profile; py-spy was not started.",
                   "py-spy shares describe sampled Python-active time only; native shares describe cycles:u sample-period weights. They cannot be multiplied or used as whole-run wall time.",
                   "No current eligible XLSX profile exists for Retail, HR, or Industry Productivity; historical pre-loop-verifier XLSX profiles are retained but not used as current contract evidence."],
        "inputs": [{"path": str(p.relative_to(BASE)), "bytes": p.stat().st_size, "sha256": sha(p)} for p in provenance_paths if p.is_file()],
        "analysis_sources": [{"path": str(p.relative_to(BASE)), "sha256": sha(p)} for p in [Path(__file__), BASE / "scripts/build_profiles.py", BASE / "scripts/analyze_script_io_comparison.py", BASE / "scripts/recheck_failed_loop_outputs.py"]],
    }
    (OUT / "hotspot-version-comparison.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    lines = ["# 新旧执行版本热点对比 v1", "", "## 直接回答", "",
             "1. **当前旧 OPM/TLC 与历史 document-oe：** TLC 的 Python/LibreOffice 与主要 XML 库比例接近；脚本 py-spy 份额差大多不足 1 pp。OPM N=1 脚本份额也接近（历史主要脚本差 0.3–2.3 pp），但原生进程比例从历史 Python 90.6%/pdftoppm 9.2% 变为当前约 87.4%/12.4%。因此脚本热点总体稳定，OPM native 的 Poppler 子进程权重有约 3 pp 上移。历史 native 文件未纳入/未解析，当前旧控件 runner SHA 也不同，不能声称逐函数复现或确定归因。",
             "2. **新 PDF 与旧 OPM：** IRS W-4、SBA 1919 在 N=1 和 N=10 都由 Python 填写/验证与 Poppler 渲染组成；主要库仍是 libpython、zlib、Pillow、Poppler/FreeType。各新表单的 verify 与 fill 占比不同，属于输入和当前 loop verifier 路径差异；每种配置只有一个 native profile，暂不能判断稳定权重变化。Retail/HR 的旧采集是在旧 loop verifier 下失败；保留产物经当前修复版 loop verifier 离线复核通过，但其采集记录和不完整 profile 不升级为当前合格热点。Industry 的成功单轮未得到完整 native 栈解析，故本轮不能给出这些 XLSX 与 TLC 的合格热点比较。",
             "3. **XLSX load/save：** 当前 TLC 的 py-spy 可估计 load_workbook 内部、只读延迟扫描和 save；Retail/HR/Industry 无当前合格 py-spy 数据。具体表格使用 Python 活动采样数，不等于 cycles:u 或整轮墙钟占比。", "",
             "## 数据资格和版本", "",
             "| 对象 | 可用资料 | 资格/限制 |", "|---|---|---|"]
    retail_recheck_status = posthoc_datasets.get("retail", {}).get("status", "not rechecked")
    hr_recheck_status = posthoc_datasets.get("hr", {}).get("status", "not rechecked")
    recheck_evidence = "processed/loop-verifier-recheck-v1.json"
    rows = [
        ("历史 document-oe OPM/TLC", "历史报告；PDF N=1、TLC", "聚合数据；本轮未纳入/未解析现存历史 native 文件；环境身份按原报告记录"),
        ("当前 OPM N=1/N=10、TLC", "现有 native r1/r2，TLC/OPM py-spy", "完整 ROI 解析；旧 recipe/workload 不变；runner SHA 3623…，不是最新版挂载 runner 559a…"),
        ("IRS W-4、SBA 1919 N=1/N=10", "本轮 native+独立 py-spy 各一组", "loop verifier 成功；完整 native ROI；单次采集无重复波动"),
        ("Retail", "本轮 5 次 native 尝试", f"采集时旧 verifier 因声明 dimension 误判 base_sheet_scale；保留工作簿修复版 loop verifier 离线复核={retail_recheck_status}，证据 {recheck_evidence}。旧采集仍不计热点比例（采集时验证失败，perf script 不完整）"),
        ("HR", "本轮 8 次 native 尝试", f"旧 verifier 原失败项为 semantic:scenario_dependency:projected_mean_wage 与 semantic:chart_dependency:major_employment；保留工作簿修复版 loop verifier 离线复核={hr_recheck_status}，证据 {recheck_evidence}。旧采集仍不计热点比例（采集时验证失败，perf script 不完整）"),
        ("Industry Productivity", "本轮一次 native loop 成功；输出和业务验证归档", "业务验证成功，但 perf script 导出停止、未解析；未启动 py-spy"),
    ]
    for a,b,c in rows: lines.append(f"| {a} | {b} | {c} |")
    lines += ["", "## 当前完整 ROI：原生进程/脚本热点", "", "周期权重来自完整 ROI 的 `cycles:u` sample period。新 PDF 表示每配置单次 native 采集；OPM/TLC 保留两个独立重复，表中为 period 加权合并，JSON 保留各次分母。", "",
              "| 配置 | 重复 | 主要进程/脚本（ROI cycles:u） |", "|---|---:|---|"]
    for cfg in ("opm-n1", "opm-n10", "irs_w4-n1", "irs_w4-n10", "sba1919-n1", "sba1919-n10", "tlc"):
        p = current[cfg]
        tops = "; ".join(f"{k} {pct(v)}" for k,v in list(p["process_share"].items())[:6])
        lines.append(f"| {cfg} | {p['repeat_count']} | {tops}; Python-script subtotal {pct(p['python_script_share'])}; LibreOffice subtotal {pct(p['libreoffice_process_share'])} |")
    lines += ["", "## Python 脚本热点（独立 py-spy）", "", "这里的分母是 Python 活动采样数，不与 native cycles:u 相混。脚本角色按运行命令和栈识别；unknown/runner 保留。历史 OPM 只有 N=1 的 py-spy 参考；N=10 不冒充历史基线。", "", "| 配置 | 采样数 | Python脚本热点 |", "|---|---:|---|"]
    for cfg in ("opm-n1", "opm-n10", "irs_w4-n1", "irs_w4-n10", "sba1919-n1", "sba1919-n10", "tlc"):
        d=pyspy_profiles[cfg]
        tops="; ".join(f"{k} {v:.1f}%" for k,v in list(d["role_percent"].items())[:6])
        lines.append(f"| {cfg} | {d['total_samples']} | {tops} |")
    lines += ["", "历史报告与当前旧脚本对照（两者都是 py-spy Python 活动样本；历史没有逐栈 raw）：", "", "| 对象/角色 | 历史 document-oe | 当前 | 变化 |", "|---|---:|---:|---:|"]
    for role, hist_value in (("pdf-convert",.4388),("pdf-fill",.2121),("pdf-verify",.1429),("pdf-check-fillable",.0736),("pdf-extract-fields",.0977)):
        cur=pyspy_profiles["opm-n1"]["role_percent"].get(role,0)/100
        lines.append(f"| OPM N=1 / {role} | {hist_value*100:.1f}% | {cur*100:.1f}% | {(cur-hist_value)*100:+.1f} pp |")
    for role, hist_value in historical["tlc"]["scripts_pyspy"].items():
        cur=pyspy_profiles["tlc"]["role_percent"].get(role,0)/100
        lines.append(f"| TLC / {role} | {hist_value*100:.1f}% | {cur*100:.1f}% | {(cur-hist_value)*100:+.1f} pp |")
    lines += ["", "同环境旧输入与新 PDF 的脚本占比（分开按 N 比较；当前旧 OPM 是桥接基线）：", "", "| 对照 | pdf-convert | pdf-fill | pdf-verify | check-fillable | extract-fields |", "|---|---:|---:|---:|---:|---:|"]
    for n in ("n1", "n10"):
        old=pyspy_profiles[f"opm-{n}"]
        for new in (("irs_w4", "IRS W-4"), ("sba1919", "SBA 1919")):
            cur=pyspy_profiles[f"{new[0]}-{n}"]
            def delta(role): return cur["role_percent"].get(role,0)-old["role_percent"].get(role,0)
            lines.append(f"| OPM {n} → {new[1]} {n} | {delta('pdf-convert'):+.1f} pp | {delta('pdf-fill'):+.1f} pp | {delta('pdf-verify'):+.1f} pp | {delta('pdf-check-fillable'):+.1f} pp | {delta('pdf-extract-fields'):+.1f} pp |")
    lines.append("脚本角色的百分点变化是 Python 活动样本之间的差异；文件页数/字段数、实际操作路径和验证内容会影响它，不代表整个 workload CPU 周期变化，也不能单独归因输入类别。")
    lines += ["", "## 当前完整 ROI：主要库与函数", "", "函数份额为完整 ROI 的 period 权重；`leaf` 为采样点函数，实体函数仅用于 inline 归属，不把通用 libpython 解释成业务算法。", "", "| 配置 | 高权重库 | 主要叶函数 / 脚本 |", "|---|---|---|"]
    for cfg in ("opm-n1", "opm-n10", "irs_w4-n1", "irs_w4-n10", "sba1919-n1", "sba1919-n10", "tlc"):
        p=current[cfg]
        libs="; ".join(f"{k} {pct(v)}" for k,v in list(p["library_share"].items())[:5])
        fns="; ".join(f"{x['script_role']}:{x['leaf_function']} [{x['dso_class']}] {x['share_roi']*100:.2f}% (ctx: {' → '.join(x['call_context'][:3])})" for x in p["function_hotspots"][:4])
        lines.append(f"| {cfg} | {libs} | {fns} |")
    lines += ["", "## 当前旧控件与历史 document-oe 比较", "", "| 对象 | 历史报告热点 | 当前运行 profile | 判断 |", "|---|---|---|---|"]
    for cfg,hkey in (("opm-n1","opm_n1"),("tlc","tlc")):
        h=historical[hkey]; p=current[cfg]
        hs="; ".join(f"{k} {pct(v)}" for k,v in h["process"].items())
        if cfg == "opm-n1":
            pdftoppm = p["process_share"].get("pdftoppm", 0)
            vals=[sum(v for k,v in r["process_share"].items() if k.startswith(("pdf-","python-")) or k in ("python-inline","runner")) for r in p["per_repeat"].values()]
            child_vals=[r["process_share"].get("pdftoppm",0) for r in p["per_repeat"].values()]
            cs=f"Python脚本 subtotal {pct(p['python_script_share'])} (r1/r2 {pct(vals[0])}/{pct(vals[1])}; vs hist {(p['python_script_share']-h['process']['python3'])*100:+.1f} pp); pdftoppm {pct(pdftoppm)} (r1/r2 {pct(child_vals[0])}/{pct(child_vals[1])}; vs hist {(pdftoppm-h['process']['pdftoppm'])*100:+.1f} pp)"
        else:
            vals=[sum(v for k,v in r["process_share"].items() if k.startswith(("xlsx-","python-")) or k == "runner") for r in p["per_repeat"].values()]
            lo_vals=[sum(v for k,v in r["process_share"].items() if k in ("soffice.bin","lo-thread","thread-pool","Parser")) for r in p["per_repeat"].values()]
            cs=f"Python脚本 subtotal {pct(p['python_script_share'])} (r1/r2 {pct(vals[0])}/{pct(vals[1])}; vs hist {(p['python_script_share']-h['process']['python3'])*100:+.1f} pp); LibreOffice/threads {pct(p['libreoffice_process_share'])} (r1/r2 {pct(lo_vals[0])}/{pct(lo_vals[1])}; vs hist {(p['libreoffice_process_share']-h['process']['libreoffice+threads'])*100:+.1f} pp)"
        lines.append(f"| {cfg} | {hs} | {cs} | 大类总量可比较；历史报告与当前 ROI、runner版本不完全一致，且历史 native 文件本轮未纳入/未解析；当前脚本分项存在重组，无法作逐脚本增减判定 |")
    lines += ["", "主要库占比对照（两边均报告 cycles:u）：", "", "| 对象 / 库 | 历史 | 当前 | 变化 |", "|---|---:|---:|---:|"]
    for cfg,hkey,classes in (("opm-n1","opm_n1",("libpython","zlib","pillow","poppler","freetype")),
                             ("tlc","tlc",("libpython","expat-xml","elementtree-xml","zlib"))):
        for cls in classes:
            old=historical[hkey]["libraries"].get(cls,0)
            now=current[cfg]["library_share"].get(cls,0)
            lines.append(f"| {cfg} / {cls} | {old*100:.1f}% | {now*100:.1f}% | {(now-old)*100:+.1f} pp |")
    lines += ["", "## XLSX load_workbook、只读延迟扫描与保存", "", "下表分母为全部 py-spy Python 活动样本（含无 Python 函数栈进程样本）。A/B/D 为生产分析器按完整栈分类的互斥样本；C=A+B 并集。非加载/保存及 no_python_frames 单列。py-spy 不测 LibreOffice-only 工作或闲置等待。", "", "| 基线 | 全 Python 活动样本 | A load_workbook内部 | B read_only延迟扫描 | C 加载合计 | D Workbook.save | E 加载+保存 | F 其他 | 无 Python 栈 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for key,label in (("historical_tlc","历史 TLC"),("current_tlc","当前 TLC")):
        d=xlsx_io[key]; op=d["operation_percent"]; total=d["total_samples"]
        load=op.get("load_call",0)+op.get("lazy_scan",0)
        save=op.get("save",0)
        lines.append(f"| {label} | {total} | {pct(op.get('load_call',0)/100)} | {pct(op.get('lazy_scan',0)/100)} | {pct(load/100)} | {pct(save/100)} | {pct((load+save)/100)} | {pct(op.get('other',0)/100)} | {pct(op.get('no_python_frames',0)/100)} |")
    for cfg in xlsx_new_status:
        lines.append(f"| 当前 {cfg} | — | — | — | — | — | — | — | — |")
    lines += ["", "主要脚本内部占比由完整调用栈按进程归属重建，见下表；仅为 Python 活动采样比例，不是墙钟时间。", "", "## Verifier 的单列解释", "", "完整 ROI 已包含循环内 verifier。旧 OPM/TLC 的 verifier 是原 legacy 验证脚本；本次 IRS/SBA 执行当前 loop contract。Retail/HR 的旧采集在此前 verifier 规则下失败，但保留输出经本次修复版 loop verifier 离线复核通过；原始采集和 profile 状态不改写，仍不作为合格热点比例。Industry 通过一轮但没有有效 profile。由于当前 TLC 代码路径仍是 legacy workload，当前 TLC 可作保留验证器 profile，但不外推至 Retail/HR/Industry。", "", "## 解释边界", "", "- 样本 period 累计按 parser 的 ROI 样本定义；PERFROI marker 中点与 stdout arrival 的时间对齐未独立校准，buffering/偏移仍是误差源。", "- perf 数据有 lost chunks：IRS/SBA及旧控件应查各 `roi.json`；旧 Retail/HR 采集记录验证失败，所以不计比例，即使其保留输出现在通过修复版 verifier。Industry 原始 perf.data 保留但没有完整 sample/ROI 解析。", "- 不把父进程等待算作自己的 CPU，也不将 parent-child inclusive 窗口相加。native 进程身份由采样身份记录和脚本路径归属，未知身份保留。", "- N=1 与 N=10 是不同任务规模，分别比较；不将其合并。PDF N=10 历史三轮文件是指令/切片权重报告，不是同口径 native cycles profile，不用于本次热点百分比对照。", "- Retail/HR 的旧严格 verifier profile 保留在此前 processed 结果，但由于当前 loop verifier 已变化，只作为旧版本历史，不作为当前版本主结果。", "", "## 可追溯文件", "", "机器结果、采集资格、source hash 和分析脚本 hash：`hotspot-version-comparison.json`。原 profile 和失败材料位于 `raw/`；历史报告位于 `legacy/evidence/`。", ""]
    marker = "## Verifier 的单列解释"
    at = lines.index(marker)
    lines[at:at] = ["", "| 版本/脚本 | Python样本 | 占全部 Python 样本 | load调用 | 延迟扫描 | save | 其他 |", "|---|---:|---:|---:|---:|---:|---:|"]
    at += 3
    for ver, key in (("历史 TLC", "by_script_historical_tlc"), ("当前 TLC", "by_script_current_tlc")):
        by_script = xlsx_io[key]
        for role in ("xlsx-enhance", "xlsx-verify", "xlsx-inspect-structure", "xlsx-inspect-features", "xlsx-inspect-formulas", "xlsx-inspect-cached", "xlsx-recalc", "xlsx-summary-export"):
            if role not in by_script: continue
            d = by_script[role]; op = d["operation_percent"]
            all_samples = xlsx_io["historical_tlc" if ver == "历史 TLC" else "current_tlc"]["total_samples"]
            lines.insert(at, f"| {ver}/{role} | {d['total_samples']} | {100*d['total_samples']/all_samples:.1f}% | {op.get('load_call',0):.1f}% | {op.get('lazy_scan',0):.1f}% | {op.get('save',0):.1f}% | {op.get('other',0)+op.get('no_python_frames',0):.1f}% |")
            at += 1
    lines.insert(at, "历史 SVG 的交叉分类依据火焰图样本坐标和完整栈节点重建。")
    (OUT / "comparison-report.md").write_text("\n".join(lines))
    build = {"schema":"hotspot-version-analysis-build-v1", "script":str(Path(__file__).relative_to(BASE)),
             "script_sha256":sha(Path(__file__)), "output_json_sha256":sha(OUT/"hotspot-version-comparison.json"),
             "output_report_sha256":sha(OUT/"comparison-report.md"), "generated_utc":"2026-10-19"}
    (OUT/"analysis-build.json").write_text(json.dumps(build,indent=2)+"\n")
    print(OUT / "comparison-report.md")


if __name__ == "__main__":
    main()
