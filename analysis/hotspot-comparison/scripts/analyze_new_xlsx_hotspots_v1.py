#!/usr/bin/env python3
"""Offline native and py-spy comparison for current XLSX datasets.

Native function identities use the concrete entity frame when the parser
recovered an inline leaf's owner; otherwise they use the observed leaf frame.
The read/write view reuses the established script_io classifier.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parent.parent
OUT = BASE / "reports/new-xlsx-hotspot-io-v1"
sys.path.insert(0, str(BASE / "scripts"))
import build_profiles as bp
from collection_quality import (parse_lost_chunks, parse_perf_report_lost_samples,
                                summarize_addr2line_warnings)

CAMPAIGN = BASE / "raw/new-xlsx-performance-v1/campaign-20261020T0210Z"
RECOVERY = BASE / "raw/new-xlsx-performance-v1/recovery/20261020T030642Z-retail-online-native-same-image-noinline"
NEW_PYSPY = BASE / "raw/new-xlsx-performance-v1/20261020T032424Z-retail-online-pyspy"
RECENT = BASE / "raw/current-loop-hotspots-v2/20261019T124014Z-845e640e-remaining-modes"
V2_REPORT = BASE / "reports/hotspot-version-comparison-v2/comparison.json"

NATIVE = {
    "tlc": [BASE / "raw/tlc/r1", BASE / "raw/tlc/r2"],
    "industry_productivity": [RECENT / "industry_productivity/r1"],
    "hr_metro": [CAMPAIGN / "hr_metro/r1"],
    "retail_online": [RECOVERY / "retail/r1"],
}
PYSPY = {
    "tlc": BASE / "raw/tlc/pyspy",
    "industry_productivity": RECENT / "industry_productivity/pyspy",
    "hr_metro": CAMPAIGN / "hr_metro/pyspy",
    "retail_online": NEW_PYSPY / "retail_online/pyspy",
}
_IO_ANALYZER = None


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rel(path: Path) -> str:
    return str(Path(path).resolve().relative_to(BASE.resolve()))


def read(path: Path):
    return json.loads(Path(path).read_text())


def write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def physical_leaf(sample: dict) -> tuple[str, str, str]:
    """Normalize inline and --no-inline samples to the concrete owner frame."""
    if sample.get("inline_recovered") and sample.get("entity_sym"):
        symbol = sample.get("entity_sym")
        dso = sample.get("entity_dso") or sample.get("leaf_dso") or "[unknown]"
    else:
        symbol = sample.get("leaf_sym") or "[unknown-symbol]"
        dso = sample.get("leaf_dso") or "[unknown]"
    return symbol or "[unknown-symbol]", dso, bp.dso_class(dso)


def physical_stack_prefix(sample: dict, depth: int = 6) -> tuple[str, ...]:
    """Drop inline expansion rows while retaining the observed physical frames."""
    frames = []
    for frame in sample.get("stack") or []:
        if frame.get("inline") or frame.get("dso") == "inlined":
            continue
        symbol = frame.get("symbol") or "[unknown-symbol]"
        dso = frame.get("dso") or "[unknown]"
        frames.append(f"{symbol} [{bp.dso_class(dso)}]")
        if len(frames) == depth:
            break
    return tuple(frames)


def indexed_hash(index_path: Path, relative: str) -> str | None:
    if not index_path.is_file():
        return None
    for row in read(index_path).get("files", []):
        if row.get("path") == relative and row.get("status") == "hashed":
            return row.get("sha256")
    return None


def run_identity(dataset: str, run_dir: Path, roi: dict) -> dict:
    if dataset == "retail_online":
        record_path = run_dir / "out/recovery-record.json"
        record = read(record_path)
        if record.get("final_profile_eligible") is not True:
            raise ValueError(f"{dataset}: recovery profile is not eligible")
        return {"record_path": rel(record_path), "record_sha256": sha(record_path),
                "image_id": record.get("source_run", {}).get("image_id"),
                "export_image_id": record.get("export_environment", {}).get("actual_image_id"),
                "capture_quality": record.get("quality_limits"),
                "runner_image_is_original": True, "record": record}

    record_path = run_dir / "out/collection-record.json"
    if record_path.is_file():
        record = read(record_path)
        if record.get("final_profile_eligible") is not True:
            raise ValueError(f"{dataset}: native collection record is not eligible")
        return {"record_path": rel(record_path), "record_sha256": sha(record_path),
                "image_id": record.get("image_id"),
                "capture_quality": record.get("capture_quality"), "record": record}

    # Current TLC has older per-run metadata without a final collection record;
    # its two-repeat qualification comes from the retained v2 aggregate.
    if dataset == "tlc":
        prior = read(V2_REPORT)["native_profiles"]["tlc"]
        if prior.get("status") != "eligible_existing_processed_profile":
            raise ValueError("TLC is not qualified by the retained profile comparison")
        metadata = read(run_dir / "out/metadata.json")
        summary = metadata.get("runner_summary", {})
        if not (metadata.get("perf_rc") == 0 and summary.get("successes") == 1
                and summary.get("failures") == 0):
            raise ValueError(f"TLC {run_dir.name}: metadata does not show successful workload")
        return {"record_path": rel(run_dir / "out/metadata.json"),
                "record_sha256": sha(run_dir / "out/metadata.json"),
                "image_id": "unknown (not recorded per container)", "record": metadata,
                "capture_quality": None,
                "qualification_source": rel(V2_REPORT)}
    raise ValueError(f"no qualification record for {dataset}: {run_dir}")


def aggregate_native_run(dataset: str, run_dir: Path) -> dict:
    roi_path = run_dir / "out/roi.json"
    samples_path = run_dir / "out/samples.jsonl"
    roi = read(roi_path)
    ident = run_identity(dataset, run_dir, roi)
    process, libs, funcs, contexts, scripts = Counter(), Counter(), Counter(), Counter(), Counter()
    total_period = sample_count = 0
    unknown_dso_period = unknown_symbol_period = empty_stack_period = 0
    inline_recovered_period = inline_unresolved_period = 0
    inline_recovered_samples = 0
    with samples_path.open() as f:
        for line in f:
            if not line.strip():
                continue
            sample = json.loads(line)
            period = int(sample["period"])
            sample_count += 1
            total_period += period
            role = load_io_analyzer().native_role(sample)
            process[role] += period
            symbol, dso, dso_cls = physical_leaf(sample)
            dso_name = Path(dso).name if dso != "[unknown]" else "[unknown]"
            libs[dso_cls] += period
            funcs[(role, dso_cls, dso_name, symbol)] += period
            command = sample.get("cmdline") or ""
            scripts[(role, command)] += period
            prefix = physical_stack_prefix(sample)
            if prefix:
                contexts[(role, prefix)] += period
            if dso_cls == "unknown":
                unknown_dso_period += period
            if symbol in ("", "[unknown]", "[unknown-symbol]", "[unknown symbol]", "??", "unknown"):
                unknown_symbol_period += period
            if not sample.get("stack"):
                empty_stack_period += period
            if sample.get("inline_recovered"):
                inline_recovered_samples += 1
                inline_recovered_period += period
            reason = sample.get("unknown_reason") or ""
            if "inline" in reason:
                inline_unresolved_period += period

    if sample_count != int(roi["roi_samples"]) or total_period != int(roi["roi_period_total"]):
        raise ValueError(f"{dataset}/{run_dir.name}: period/sample mismatch: "
                         f"{sample_count}/{total_period} vs {roi['roi_samples']}/{roi['roi_period_total']}")
    denominator = total_period
    capture_quality = ident.get("capture_quality")
    if dataset == "tlc":
        stdout_path = run_dir / "out/stdout.log"
        report_path = run_dir / "out/native-by-dso.txt"
        stderr_path = run_dir / "raw/tlc.samples.txt.stderr.log"
        capture_quality = {
            "capture_loss": {
                "lost_chunks": parse_lost_chunks(stdout_path.read_text(errors="replace")),
                "lost_samples": parse_perf_report_lost_samples(report_path.read_text(errors="replace")),
                "scope_note": "Capture-wide counts; ROI attribution unknown.",
            },
            "symbol_resolution": {
                "addr2line_warnings": (summarize_addr2line_warnings(stderr_path.read_text(errors="replace"))
                                       if stderr_path.is_file() else {
                                           "status": "not_recorded", "warning_count": None,
                                           "reason": "No retained perf script stderr file for this TLC run."}),
            },
        }
    capture_quality = capture_quality or {"status": "not_recorded"}
    file_hash = indexed_hash(run_dir / "sha256-index.json", "out/samples.jsonl")
    if file_hash is None:
        # TLC's older local raw has no per-run index; hash the parsed JSONL only.
        file_hash = sha(samples_path)
    return {
        "run": run_dir.name, "status": "eligible", "roi_samples": sample_count,
        "roi_period": denominator, "repeat_count": 1,
        "process_share": {k: v / denominator for k, v in process.most_common()},
        "library_share": {k: v / denominator for k, v in libs.most_common()},
        "functions": [
            {"role": k[0], "dso_class": k[1], "dso": k[2], "physical_function": k[3],
             "period": v, "share_roi": v / denominator}
            for k, v in funcs.most_common(50)],
        "all_function_period": sum(funcs.values()),
        "unlisted_function_period": denominator - sum(v for _, v in funcs.most_common(50)),
        "top_commands_by_role": {
            role: [{"command": command, "period": weight, "share_roi": weight / denominator}
                   for (r, command), weight in scripts.most_common() if r == role][:2]
            for role in process},
        "physical_stack_prefixes": [
            {"role": k[0], "frames": list(k[1]), "period": v, "share_roi": v / denominator}
            for k, v in contexts.most_common(20)],
        "_all_function_periods": [
            {"role": k[0], "dso_class": k[1], "dso": k[2], "physical_function": k[3], "period": v}
            for k, v in funcs.items()],
        "_all_context_periods": [
            {"role": k[0], "frames": list(k[1]), "period": v}
            for k, v in contexts.items()],
        "quality": {
            "unknown_leaf_dso_period": unknown_dso_period,
            "unknown_leaf_dso_share_roi": unknown_dso_period / denominator,
            "unknown_leaf_symbol_period": unknown_symbol_period,
            "unknown_leaf_symbol_share_roi": unknown_symbol_period / denominator,
            "empty_stack_period": empty_stack_period,
            "empty_stack_share_roi": empty_stack_period / denominator,
            "inline_recovered_samples": inline_recovered_samples,
            "inline_recovered_period": inline_recovered_period,
            "inline_recovered_share_roi": inline_recovered_period / denominator,
            "inline_owner_unresolved_period_full_capture_diagnostic": roi.get("perf_script_parse", {}).get("inline_owner_unresolved_period"),
            "inline_owner_unresolved_diagnostic_scope": "The parser's perf_script_parse counter covers the full export, including any preloop samples; it is kept as a separate diagnostic and not represented as an ROI-only share.",
            "physical_frame_rule": "entity_sym/entity_dso only when inline_recovered=true; otherwise observed leaf_sym/leaf_dso. No caller DSO inheritance.",
        },
        "capture_quality": capture_quality,
        "provenance": {
            **{k: v for k, v in ident.items() if k != "record"},
            "parsed_samples": rel(samples_path), "parsed_samples_sha256": file_hash,
            "parsed_samples_hash_source": "existing index" if indexed_hash(run_dir / "sha256-index.json", "out/samples.jsonl") else "computed while consuming parsed output",
            "roi_path": rel(roi_path), "roi_sha256": sha(roi_path),
            "index_path": rel(run_dir / "sha256-index.json") if (run_dir / "sha256-index.json").is_file() else None,
        },
    }


def aggregate_native_dataset(dataset: str, runs: list[Path]) -> dict:
    reps = [aggregate_native_run(dataset, p) for p in runs]
    total_samples = sum(x["roi_samples"] for x in reps)
    total_period = sum(x["roi_period"] for x in reps)
    process, libs, funcs, contexts = Counter(), Counter(), Counter(), Counter()
    for run in reps:
        den = run["roi_period"]
        process.update({k: v * den for k, v in run["process_share"].items()})
        libs.update({k: v * den for k, v in run["library_share"].items()})
        funcs.update({(row["role"], row["dso_class"], row["dso"], row["physical_function"]): row["period"]
                      for row in run["_all_function_periods"]})
        contexts.update({(row["role"], tuple(row["frames"])): row["period"]
                         for row in run["_all_context_periods"]})
    process_share = {k: v / total_period for k, v in process.items()}
    library_share = {k: v / total_period for k, v in libs.items()}
    ranked = funcs.most_common(50)
    return {
        "dataset": dataset, "status": "eligible", "repeat_count": len(reps),
        "denominator": "sum of complete workload ROI cycles:u sample period across all retained repeats; period weighted",
        "roi_samples": total_samples, "roi_period": total_period,
        "repeats": [{"run": x["run"], "roi_samples": x["roi_samples"], "roi_period": x["roi_period"],
                     "unknown_leaf_dso_share_roi": x["quality"]["unknown_leaf_dso_share_roi"],
                     "empty_stack_share_roi": x["quality"]["empty_stack_share_roi"]} for x in reps],
        "process_share": dict(sorted(process_share.items(), key=lambda kv: -kv[1])),
        "library_share": dict(sorted(library_share.items(), key=lambda kv: -kv[1])),
        "physical_leaf_function_hotspots": [
            {"role": k[0], "dso_class": k[1], "dso": k[2], "physical_function": k[3],
             "period": v, "share_roi": v / total_period} for k, v in ranked],
        "_function_keys_all": [{"dso_class": k[1], "dso": k[2], "function": k[3]}
                               for k in funcs],
        "function_weight_accounting": {
            "displayed_top50_period": sum(v for _, v in ranked),
            "unlisted_tail_period": total_period - sum(v for _, v in ranked),
            "unknown_leaf_dso_period": sum(int(x["quality"]["unknown_leaf_dso_period"]) for x in reps),
            "unknown_leaf_symbol_period": sum(int(x["quality"]["unknown_leaf_symbol_period"]) for x in reps),
            "sample_points_counted_once": True,
        },
        "overlapping_physical_stack_contexts": [
            {"role": k[0], "frames": list(k[1]), "period": v, "share_roi": v / total_period}
            for k, v in contexts.most_common(20)],
        "run_quality": [{"run": x["run"], "roi_diagnostics": x["quality"],
                         "capture_quality": x["capture_quality"]} for x in reps],
        "source_runs": [x["provenance"] for x in reps],
    }


def load_io_analyzer():
    global _IO_ANALYZER
    if _IO_ANALYZER is not None:
        return _IO_ANALYZER
    path = BASE / "scripts/analyze_hotspot_version_v2.py"
    spec = importlib.util.spec_from_file_location("hotspot_v2_existing", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _IO_ANALYZER = module
    return _IO_ANALYZER


def pyspy_profile(dataset: str, folder: Path, legacy_tlc=False) -> dict:
    raw_path = folder / "raw" / f"{dataset}.pyspy.raw"
    if legacy_tlc:
        raw_path = folder / "raw/tlc.pyspy.raw"
    metadata_path = folder / "out/metadata.json"
    meta = read(metadata_path)
    if meta.get("rc") != 0 or meta.get("runner_summary", {}).get("failures") != 0:
        raise ValueError(f"{dataset}: py-spy metadata not successful")
    analyzer = load_io_analyzer()
    result = analyzer.scriptio_by_role(raw_path, "xlsx")
    record_path = folder / "out/collection-record.json"
    if record_path.is_file():
        record = read(record_path)
        if record.get("final_profile_eligible") is not True:
            raise ValueError(f"{dataset}: py-spy profile not eligible")
        record_qualification = {"path": rel(record_path), "sha256": sha(record_path), "final_profile_eligible": True}
    else:
        # TLC's profile predates the current archive record schema.
        prior = read(V2_REPORT)["pyspy_profiles"]["tlc"]
        if prior.get("denominator_samples") != result["denominator_samples"]:
            raise ValueError("TLC existing py-spy denominator differs from retained comparison")
        record_qualification = {"path": rel(V2_REPORT), "sha256": sha(V2_REPORT),
                                "status": "eligible in retained v2 analysis; no per-run final archive record"}
    raw_index = folder / "sha256-index.json"
    raw_rel = f"raw/{dataset}.pyspy.raw"
    digest = indexed_hash(raw_index, raw_rel)
    if not digest:
        digest = sha(raw_path)
    result.update({
        "dataset": dataset, "status": "eligible",
        "denominator_definition": "all parsed py-spy sample counts after the parser's explicit known-preflight-stack exclusion; process-only/no-Python-frame samples retained",
        "raw_path": rel(raw_path), "raw_sha256": digest,
        "raw_sha256_source": "existing stage index" if indexed_hash(raw_index, raw_rel) else "computed for small py-spy text profile",
        "metadata_path": rel(metadata_path), "metadata_sha256": sha(metadata_path),
        "qualification": record_qualification,
        "sampling": {"rate_hz": meta.get("rate_hz"), "pyspy_mode": "record --subprocesses --format raw",
                     "wall_seconds": meta.get("wall_seconds"), "requested_iterations": meta.get("runner_summary", {}).get("requested_iterations"),
                     "completed_iterations": meta.get("runner_summary", {}).get("completed_iterations"),
                     "successes": meta.get("runner_summary", {}).get("successes"),
                     "failures": meta.get("runner_summary", {}).get("failures")},
    })
    result["raw_samples"] = int(result["denominator_samples"]) + int(result.get("preflight_samples_excluded", 0))
    return result


def pct(x):
    return f"{100*x:.2f}%"


def make_report(data: dict) -> str:
    lines = [
        "# 新 XLSX 热点与读写特征（v1）", "",
        "## 主要结论", "",
        "本报告复用合格的 TLC、Industry Productivity 与 HR Metro profile，并加入 Retail Online 的同镜像 native 离线恢复和本轮唯一 py-spy 单轮。Native 为完整 ROI `cycles:u` sample period；py-spy 为独立样本计数，二者不互相换算。每个新数据集仅一次采集，结论是描述性画像。", "",
        "### Native 进程/脚本热点", "",
        "| 数据集 | ROI samples | ROI period | 重复数 | 主要进程/脚本（占完整 ROI） |", "|---|---:|---:|---:|---|",
    ]
    for name, p in data["native_profiles"].items():
        top = "; ".join(f"{k} {pct(v)}" for k, v in list(p["process_share"].items())[:5])
        lines.append(f"| {name} | {p['roi_samples']:,} | {p['roi_period']:,} | {p['repeat_count']} | {top} |")
    lines += ["", "### 主要库与物理叶函数", "",
              "函数名按实体帧归一化：仅在 `inline_recovered=true` 时以 `entity_sym/entity_dso` 代替内联叶帧；Retail Online 的 `--no-inline` 叶帧直接使用。未知 DSO/符号仍在分母内，不继承其他地址的调用者库。", "",
              "| 数据集 | 主要库（占完整 ROI） | 代表性物理叶函数（占完整 ROI） |", "|---|---|---|"]
    for name, p in data["native_profiles"].items():
        libs = "; ".join(f"{k} {pct(v)}" for k, v in list(p["library_share"].items())[:5])
        funcs = "; ".join(f"{x['role']}::{x['physical_function']} ({x['dso_class']}) {pct(x['share_roi'])}"
                           for x in p["physical_leaf_function_hotspots"][:5])
        lines.append(f"| {name} | {libs} | {funcs} |")
    lines += ["", "### 与 TLC 的热点差异", "",
              "| 数据集 | 进程/脚本 share 变化较大项（百分点，vs TLC） | 库 share 变化较大项（百分点，vs TLC） | TLC 未观察且本数据集 ≥0.5% 的物理叶函数 |", "|---|---|---|---|"]
    for name in ("industry_productivity", "hr_metro", "retail_online"):
        comp = data["comparisons_vs_tlc"][name]
        proc = "; ".join(f"{k} {v:+.2f}pp" for k, v in comp["largest_process_delta_pp"][:4])
        libs = "; ".join(f"{k} {v:+.2f}pp" for k, v in comp["largest_library_delta_pp"][:4])
        novel = "; ".join(f"{x['function']} {pct(x['share_roi'])}" for x in comp["not_observed_in_tlc_ge_0_5pct"][:5]) or "无（按观察集合定义）"
        lines.append(f"| {name} | {proc} | {libs} | {novel} |")
    lines += ["", "### Native 采样与符号质量", "",
              "丢失样本与丢失 chunks 按采集日志分别记录；其 ROI 归属未知。`addr2line` 计数标明日志来源，不代表对应 ROI 权重。未知 DSO、未知符号和空栈分别按完整 ROI period 计算，未知 DSO 与未知符号可重叠。", "",
              "| 数据集 | lost samples | lost chunks | addr2line warnings | ROI unknown DSO | ROI unknown symbol | ROI empty stack |", "|---|---:|---:|---:|---:|---:|---:|"]
    for name, p in data["native_profiles"].items():
        quality = p["run_quality"]
        def counts(key):
            vals = []
            for run in quality:
                q = run.get("capture_quality") or {}
                if "lost_samples" in q:
                    x = q["lost_samples"].get("count")
                else:
                    x = (q.get("capture_loss", {}).get("lost_samples") or {}).get("count")
                vals.append("未记录" if x is None else str(x))
            return "/".join(vals)
        def chunks():
            vals = []
            for run in quality:
                q = run.get("capture_quality") or {}
                if "lost_chunks" in q:
                    x = q["lost_chunks"].get("count")
                else:
                    x = (q.get("capture_loss", {}).get("lost_chunks") or {}).get("count")
                vals.append("未记录" if x is None else str(x))
            return "/".join(vals)
        def warnings():
            vals = []
            for run in quality:
                q = run.get("capture_quality") or {}
                sym = q.get("symbol_resolution", {})
                warning = sym.get("addr2line_warnings")
                if warning is not None:
                    vals.append("未记录" if warning.get("warning_count") is None else str(warning["warning_count"]))
                elif "addr2line_warnings_in_original_partial" in q:
                    orig = q["addr2line_warnings_in_original_partial"].get("warning_count")
                    restored = q.get("addr2line_warnings_in_no_inline_export", {}).get("warning_count")
                    vals.append(f"{orig}/{restored}（partial/no-inline）")
                else:
                    vals.append("未记录")
            return "/".join(vals)
        unknown_dso = p["function_weight_accounting"]["unknown_leaf_dso_period"] / p["roi_period"]
        unknown_sym = p["function_weight_accounting"]["unknown_leaf_symbol_period"] / p["roi_period"]
        empty = sum(run["roi_diagnostics"]["empty_stack_period"] for run in quality) / p["roi_period"]
        lines.append(f"| {name} | {counts('lost_samples')} | {chunks()} | {warnings()} | {pct(unknown_dso)} | {pct(unknown_sym)} | {pct(empty)} |")
    lines += ["", "### XLSX load / lazy scan / save（py-spy）", "",
              "分母是全部解析到的 py-spy stack count，保留 process-only/no-Python-frame 样本；明确排除了 parser 标记为已知预检的少量样本。百分比是 Python 采样活动估计，不是函数墙钟时间、I/O 等待或 native cycles。每个样本主分类互斥：load、lazy、save、other、no-python-frames。", "",
              "| 数据集 | 分母 samples | load_workbook 内部 A | read_only 延迟扫描 B | 加载并集 A∪B | Workbook.save D | 加载+保存并集 | 其他 | 无 Python 函数栈 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, p in data["pyspy_profiles"].items():
        lines.append(f"| {name} | {p['denominator_samples']:,} | {pct(p['A_load_workbook_internal'])} | {pct(p['B_read_only_lazy_scan'])} | {pct(p['C_load_union'])} | {pct(p['D_workbook_save'])} | {pct(p['E_load_and_save_union'])} | {pct(p['F_other'])} | {pct(p['unknown_no_python_frames'])} |")
    lines += ["", "#### 脚本贡献", "",
              "`全部 Python 样本贡献` 是该脚本 samples / 全部保留 samples；`脚本内` 是该脚本内各类样本占比。", "",
              "| 数据集 | 主要脚本 | 占全体 Python 样本 | 脚本内 load / lazy / save / other / no-stack |", "|---|---|---:|---|"]
    for name, p in data["pyspy_profiles"].items():
        for role, r in list(p["by_script"].items())[:6]:
            ops = r["operation_share_within_script"]
            vals = "/".join(pct(ops.get(k, 0)) for k in ("load_call", "lazy_scan", "save", "other", "no_python_frames"))
            lines.append(f"| {name} | {role} | {pct(r['share_all_python'])} | {vals} |")
    lines += ["", "### 当前旧 TLC 与历史报告", "",
              data["legacy_reference_summary"], "",
              "## 解释与证据边界", "",
              "- 共同的 libpython、expat/ElementTree、zlib、GC/解释器路径只证明运行时成本共有，不证明相同 Python 业务算法。具名函数相同也不证明调用语义或算法收益相同。", 
              "- Retail Online native 恢复采用同镜像 `perf script --no-inline`。原容器 partial 保留；宿主恢复的 94.31% 空栈输出不进入本报告。跨采集函数比较用实体帧口径；未恢复 owner 的样本保留未知。", 
              "- TLC/Industry 来自 v9/current-loop 旧 runner 数据；HR Metro/Retail Online 是 v11/current runner。输入、执行版本及轻量验证 contract 不完全相同。", 
              "- ROI 对齐基于 PERFROI 中点与 stdout 到达时刻估计，尚未独立校准；lost samples/chunks 和 addr2line 警告保持原记录，ROI 归属未知。", 
              "- TLC 有两次 native repeats；Industry、HR Metro、Retail Online 各仅一次。新样本无法估算重复波动或证明稳定性。", 
              "- py-spy 统计不是整轮墙钟时间。load/lazy/save 是调用栈分类，不等同磁盘读写等待、带宽或 LibreOffice 的 store 操作。", 
              "", "## 证据文件", ""]
    for item in data["evidence_inventory"]:
        lines.append(f"- `{item['dataset']}` {item['mode']}: `{item['path']}` (qualified={item['qualified']})")
    lines += ["", f"分析代码 SHA256：`{data['analysis_build']['analysis_script_sha256']}`。机器结果：`comparison.json`。", ""]
    return "\n".join(lines)


def main():
    native = {name: aggregate_native_dataset(name, runs) for name, runs in NATIVE.items()}
    io = {}
    evidence = []
    for name, folder in PYSPY.items():
        result = pyspy_profile(name, folder, legacy_tlc=(name == "tlc"))
        io[name] = result
        evidence.append({"dataset": name, "mode": "pyspy", "path": result["raw_path"],
                         "sha256": result["raw_sha256"], "qualified": result["status"] == "eligible",
                         "qualification": result["qualification"]})
    for name, runs in NATIVE.items():
        for run in runs:
            evidence.append({"dataset": name, "mode": "native", "path": rel(run / "out/samples.jsonl"),
                             "sha256": indexed_hash(run / "sha256-index.json", "out/samples.jsonl") or sha(run / "out/samples.jsonl"),
                             "qualified": True, "qualification": native[name]["source_runs"][runs.index(run)]["record_path"]})

    tlc = native["tlc"]
    ref_funcs = {(x["dso_class"], x["dso"], x["function"])
                 for x in tlc["_function_keys_all"]}
    comparisons = {}
    for name, profile in native.items():
        if name == "tlc":
            continue
        proc_keys = set(profile["process_share"]) | set(tlc["process_share"])
        lib_keys = set(profile["library_share"]) | set(tlc["library_share"])
        proc_delta = sorted(((k, 100 * (profile["process_share"].get(k, 0) - tlc["process_share"].get(k, 0)))
                             for k in proc_keys), key=lambda x: -abs(x[1]))
        lib_delta = sorted(((k, 100 * (profile["library_share"].get(k, 0) - tlc["library_share"].get(k, 0)))
                            for k in lib_keys), key=lambda x: -abs(x[1]))
        curr = profile["physical_leaf_function_hotspots"]
        common = []
        new = []
        for fn in curr:
            key = (fn["dso_class"], fn["dso"], fn["physical_function"])
            if key in ref_funcs:
                common.append(fn)
            elif fn["share_roi"] >= 0.005:
                new.append({"dso_class": fn["dso_class"], "dso": fn["dso"],
                            "function": fn["physical_function"], "share_roi": fn["share_roi"],
                            "role": fn["role"]})
        comparisons[name] = {
            "largest_process_delta_pp": proc_delta[:10],
            "largest_library_delta_pp": lib_delta[:10],
            "common_physical_functions_with_tlc_top50": [
                {"role": x["role"], "dso_class": x["dso_class"], "dso": x["dso"],
                 "function": x["physical_function"], "share_roi": x["share_roi"]}
                for x in common[:20]],
            "not_observed_in_tlc_ge_0_5pct": sorted(new, key=lambda x: -x["share_roi"]),
            "matching_boundary": "Exact symbol + normalized DSO class and basename. Current candidates come from the displayed top-50; TLC presence is checked against all sampled TLC physical functions. Absence means unobserved in these TLC captures, not proof absent from the full TLC workload.",
        }

    # Keep the full function reference set out of the public comparison JSON.
    for profile in native.values():
        profile.pop("_function_keys_all", None)

    v2 = read(V2_REPORT)
    htlc = v2["historical_reported"]["tlc"]
    hopm = v2["historical_reported"]["opm_n1"]
    current_tlc = native["tlc"]
    current_python = sum(v for k, v in current_tlc["process_share"].items() if k.startswith("xlsx-"))
    current_lo = sum(v for k, v in current_tlc["process_share"].items() if k in ("soffice.bin", "lo-thread", "lo-startup", "soffice-wrapper"))
    current_opm = v2["native_profiles"]["opm-n1"]
    opm_python = sum(v for k, v in current_opm["process_share"].items()
                     if k not in ("pdftoppm", "pdfinfo"))
    opm_pdftoppm = current_opm["process_share"].get("pdftoppm", 0)
    opm_pdfinfo = current_opm["process_share"].get("pdfinfo", 0)
    historical_controls = {
        "source_report": rel(V2_REPORT),
        "opm_n1": {
            "comparison_type": "descriptive report-level comparison; current profile is two period-weighted native repeats, historical source is legacy report-level aggregate",
            "current_native": {
                "roi_samples": current_opm["roi_samples"], "roi_period": current_opm["roi_period"],
                "repeat_count": current_opm["repeat_count"],
                "python_process_share": opm_python, "pdftoppm_process_share": opm_pdftoppm,
                "pdfinfo_process_share": opm_pdfinfo,
                "library_share": current_opm["library_share"],
            },
            "historical_reported": hopm,
            "percentage_point_delta": {
                "python_process": 100 * (opm_python - hopm["process"]["python3"]),
                "pdftoppm_process": 100 * (opm_pdftoppm - hopm["process"]["pdftoppm"]),
                "libraries": {k: 100 * (current_opm["library_share"].get(k, 0) - v)
                              for k, v in hopm["libraries"].items()},
            },
            "boundary": "Historical OPM has no per-function profile or matching runtime hashes; process role aggregation differs. N=1 only; do not generalize to N=10.",
        },
        "tlc": {
            "comparison_type": "descriptive report-level comparison; current native profile uses two repeats",
            "current_native": {
                "roi_samples": current_tlc["roi_samples"], "roi_period": current_tlc["roi_period"],
                "repeat_count": current_tlc["repeat_count"],
                "python_xlsx_script_share": current_python, "libreoffice_process_share": current_lo,
                "library_share": current_tlc["library_share"],
            },
            "historical_reported": htlc,
            "percentage_point_delta": {
                "libpython": 100 * (current_tlc["library_share"].get("libpython", 0) - htlc["libraries"]["libpython"]),
                "elementtree_xml": 100 * (current_tlc["library_share"].get("elementtree-xml", 0) - htlc["libraries"]["elementtree-xml"]),
                "expat_xml": 100 * (current_tlc["library_share"].get("expat-xml", 0) - htlc["libraries"]["expat-xml"]),
                "zlib": 100 * (current_tlc["library_share"].get("zlib", 0) - htlc["libraries"]["zlib"]),
            },
            "boundary": "Historical evidence is report-level and lacks per-function profile/hash; current per-container image identity was not recorded for these older runs.",
        },
    }
    legacy_summary = (
        f"OPM N=1：当前两次 native 的 Python 进程占 {pct(opm_python)}、pdftoppm 占 {pct(opm_pdftoppm)}"
        f"（另有 pdfinfo {pct(opm_pdfinfo)}）；历史报告为 Python {pct(hopm['process']['python3'])}、"
        f"pdftoppm {pct(hopm['process']['pdftoppm'])}。"
        f"库层当前/历史 libpython {pct(current_opm['library_share'].get('libpython',0))}/{pct(hopm['libraries']['libpython'])}、"
        f"zlib {pct(current_opm['library_share'].get('zlib',0))}/{pct(hopm['libraries']['zlib'])}、"
        f"Pillow {pct(current_opm['library_share'].get('pillow',0))}/{pct(hopm['libraries']['pillow'])}；"
        "属于描述性 N=1 对照，历史仅报告级且缺少逐函数身份。"
        f"TLC：历史报告级 libpython={pct(htlc['libraries']['libpython'])}、"
        f"ElementTree={pct(htlc['libraries']['elementtree-xml'])}、expat={pct(htlc['libraries']['expat-xml'])}、"
        f"zlib={pct(htlc['libraries']['zlib'])}；当前 TLC 两次 native 样本按 period 合并后 libpython="
        f"{pct(current_tlc['library_share'].get('libpython',0))}、ElementTree={pct(current_tlc['library_share'].get('elementtree-xml',0))}、"
        f"expat={pct(current_tlc['library_share'].get('expat-xml',0))}、zlib={pct(current_tlc['library_share'].get('zlib',0))}。"
        f"当前聚合 Python XLSX scripts={pct(current_python)}，LibreOffice process/threads={pct(current_lo)}。"
        "TLC 的库层比例总体接近；历史没有逐函数 profile/hash，不能声称逐函数复现。上述旧用例历史数据均复用 v2 报告，本轮未重采。"
    )
    analysis_path = Path(__file__)
    build = {
        "schema": "new-xlsx-hotspot-io-analysis-build-v1",
        "analysis_script": rel(analysis_path), "analysis_script_sha256": sha(analysis_path),
        "classifier_sources": [
            {"path": rel(BASE / "scripts/build_profiles.py"), "sha256": sha(BASE / "scripts/build_profiles.py")},
            {"path": rel(BASE / "scripts/analyze_hotspot_version_v2.py"), "sha256": sha(BASE / "scripts/analyze_hotspot_version_v2.py")},
            {"path": rel(BASE / "scripts/analyze_script_io_comparison.py"), "sha256": sha(BASE / "scripts/analyze_script_io_comparison.py")},
            {"path": rel(BASE / "scripts/parse_pyspy.py"), "sha256": sha(BASE / "scripts/parse_pyspy.py")},
        ],
        "historical_comparison_reference": {"path": rel(V2_REPORT), "sha256": sha(V2_REPORT)},
        "retail_pyspy_campaign_manifest": {"path": rel(NEW_PYSPY / "campaign-manifest.json"),
                                           "sha256": sha(NEW_PYSPY / "campaign-manifest.json")},
        "raw_perf_data_policy": "No perf.data or large perf script export was read or rehashed. Native summaries consume existing parsed samples; source hashes come from existing stage indexes where present.",
    }
    result = {
        "schema": "new-xlsx-hotspot-io-comparison-v1",
        "created_utc": "2026-10-20",
        "native_denominator": "Complete workload ROI cycles:u sample-period weight; all parsed ROI samples must sum exactly to roi.json; repeated TLC is period weighted.",
        "pyspy_denominator": "py-spy raw stack sample counts after the existing parser's explicit known-preflight-stack exclusion; process-only/no-Python-frame samples remain in the denominator.",
        "native_physical_frame_normalization": "If inline_recovered is true, use entity_sym/entity_dso; otherwise preserve leaf_sym/leaf_dso. Inline frames are removed from physical context prefixes. Unknown leaves do not inherit a caller DSO.",
        "native_profiles": native,
        "comparisons_vs_tlc": comparisons,
        "historical_control_comparison": historical_controls,
        "pyspy_profiles": io,
        "legacy_reference_summary": legacy_summary,
        "legacy_reference_report": {"path": rel(V2_REPORT), "sha256": sha(V2_REPORT)},
        "evidence_inventory": evidence,
        "analysis_build": build,
        "limitations": [
            "TLC and Industry Productivity profiles use the earlier v9/current-loop environment; HR Metro and Retail Online use v11 and a newer runner/verifier. Inputs and tasks differ.",
            "Only TLC has two native repeats; every other native profile and every py-spy profile has one measurement.",
            "Retail Online native uses same-image --no-inline recovery. It supports physical symbols and stacks; the earlier host-export 94.31% empty-stack result is retained as failed evidence and excluded.",
            "ROI marker/stdout alignment is an estimate and not independently calibrated.",
            "Lost samples/chunks and addr2line warnings remain collection quality limits; ROI attribution of lost records is unknown. Missing symbols/DSOs remain in denominators.",
            "Py-spy proportions are sampled Python activity, not wall-clock duration, native cycles, or disk I/O time.",
            "Physical function equality is exact normalized symbol + DSO-class/basename matching; it does not establish same Python algorithm or business operation.",
        ],
    }
    result["analysis_build"]["analysis_script_sha256"] = sha(analysis_path)
    write(OUT / "comparison.json", result)
    report = make_report(result)
    (OUT / "comparison-report.md").write_text(report)
    # Keep build record separate, and bind it to the final machine result.
    build["comparison_json_sha256"] = sha(OUT / "comparison.json")
    build["comparison_report_sha256"] = sha(OUT / "comparison-report.md")
    write(OUT / "analysis-build.json", build)
    print(json.dumps({"status": "complete", "output": rel(OUT),
                      "native_roi": {k: {"samples": v["roi_samples"], "period": v["roi_period"]} for k, v in native.items()},
                      "pyspy_io": {k: {x: v[x] for x in ("denominator_samples", "A_load_workbook_internal", "B_read_only_lazy_scan", "C_load_union", "D_workbook_save", "E_load_and_save_union", "F_other", "unknown_no_python_frames")} for k, v in io.items()}}, indent=2))


if __name__ == "__main__":
    main()
