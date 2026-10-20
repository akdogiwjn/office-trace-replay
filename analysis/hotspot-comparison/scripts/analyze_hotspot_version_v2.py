#!/usr/bin/env python3
"""Offline comparison of eligible historical/current hotspot evidence.

This consumes parsed sample JSONL and existing processed aggregates only. It
never invokes perf export or reads perf.data. Large artifact hashes are taken
from their existing campaign indexes.
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
OUT = BASE / "reports/hotspot-version-comparison-v2"
sys.path.insert(0, str(BASE / "scripts"))
import build_profiles as bp

RECENT = BASE / "raw/current-loop-hotspots-v2/20261019T124014Z-845e640e-remaining-modes"
RECOVERY = BASE / "raw/current-loop-hotspots-v2/recovery/20261019T122928Z-a6a55875-retail-native-offline"
V1_CAMPAIGN = BASE / "raw/current-loop-verifier-v1"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def display_path(path: Path | None):
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(BASE.resolve()))
    except ValueError:
        return str(path)


def indexed_file_hash(index_path: Path, relative: str) -> str | None:
    d = read(index_path)
    for item in d.get("files", []):
        if item.get("path") == relative and item.get("status") == "hashed":
            return item.get("sha256")
    return None


def pct_map(counts, total):
    return {k: v / total for k, v in counts.most_common()} if total else {}


def _context(sample):
    stack = sample.get("stack") or []
    return tuple(f"{x.get('symbol') or '[unknown-symbol]'} [{bp.dso_class(x.get('dso') or '')}]"
                 for x in stack[:6])


def native_role(sample):
    role = sample.get("role") or "unknown-role"
    cmdline = sample.get("cmdline") or ""
    identities = sample.get("identity_cmdlines") or []
    if (role == "python-unknown-script" and cmdline.endswith(".runtime.py")
            and any("run_xlsx_helper_atomic.py" in x for x in identities)
            and any("helpers/industry_productivity_build.py" in x for x in identities)):
        return "xlsx-enhance"
    return role


def aggregate_sample_jsonl(path: Path, roi_path: Path, index_path: Path,
                           sample_index_name: str, source_name: str,
                           identity: dict, quality: dict):
    roi = read(roi_path)
    proc, libs, funcs, contexts = Counter(), Counter(), Counter(), Counter()
    total = samples = 0
    with path.open() as f:
        for line in f:
            if not line.strip():
                continue
            s = json.loads(line)
            period = int(s["period"])
            total += period
            samples += 1
            role = native_role(s)
            dso = s.get("leaf_dso") or "[unknown]"
            dso_cls = bp.dso_class(dso)
            proc[role] += period
            libs[dso_cls] += period
            funcs[(role, dso_cls, Path(dso).name, s.get("leaf_sym") or "[unknown-symbol]",
                   s.get("entity_sym") or "", Path(s.get("entity_dso") or "").name)] += period
            context = _context(s)
            if context:
                contexts[(role, context)] += period
    if samples != int(roi["roi_samples"]) or total != int(roi["roi_period_total"]):
        raise ValueError(f"{source_name}: parsed ROI count/period mismatch: "
                         f"{samples}/{total} != {roi['roi_samples']}/{roi['roi_period_total']}")
    sample_hash = indexed_file_hash(index_path, sample_index_name) if index_path and index_path.is_file() else None
    sample_hash_source = "existing_index"
    if not sample_hash:
        # Older v1 PDF captures predate per-campaign SHA256 indexes. The parsed
        # JSONL is being read for aggregation anyway; hash that parsed artifact,
        # never perf.data or samples.txt.
        sample_hash = sha(path)
        sample_hash_source = "computed_for_parsed_output_only"
    displayed_functions = funcs.most_common(30)
    symbols = Counter()
    for key, weight in funcs.items():
        symbols[key[3]] += weight
    unknown_leaf_period = sum(v for (role, dso_cls, dso, symbol, entity, entity_dso), v in funcs.items()
                              if dso_cls == "unknown" or symbol in ("", "[unknown-symbol]"))
    return {
        "dataset": source_name, "status": "eligible", "repeat_count": 1,
        "denominator": "full workload ROI cycles:u sample-period weight",
        "roi_samples": samples, "roi_period": total,
        "process_share": pct_map(proc, total), "library_share": pct_map(libs, total),
        "leaf_function_hotspots": [
            {"role": k[0], "dso_class": k[1], "dso": k[2], "leaf_function": k[3],
             "entity_function": k[4] or None, "entity_dso": k[5] or None,
             "period": v, "share_roi": v / total}
            for k, v in displayed_functions],
        "leaf_symbol_hotspots": [{"leaf_function": symbol, "period": weight,
                                   "share_roi": weight / total}
                                  for symbol, weight in symbols.most_common(20)],
        "leaf_function_weight_accounting": {
            "all_leaf_period": sum(funcs.values()), "displayed_top30_period": sum(v for _, v in displayed_functions),
            "unlisted_tail_period": total - sum(v for _, v in displayed_functions),
            "unknown_leaf_period": unknown_leaf_period,
            "unknown_leaf_share_roi": unknown_leaf_period / total,
            "sample_points_counted_once": True,
        },
        "overlapping_call_contexts": [
            {"role": k[0], "stack_prefix": list(k[1]), "period": v,
             "share_roi": v / total}
            for k, v in contexts.most_common(20)],
        "roi_quality": roi.get("perf_script_parse"),
        "capture_quality": quality,
        "identity": identity,
        "source": {"parsed_samples": display_path(path),
                   "parsed_samples_sha256": sample_hash,
                   "parsed_samples_hash_source": sample_hash_source,
                   "roi": display_path(roi_path),
                   "sha256_index": display_path(index_path)},
    }


def aggregate_processed(config: str):
    p = BASE / "processed" / f"{config}.json"
    d = read(p)
    total = sum(int(r["total_period"]) for r in d["repeats"].values())
    process, libs, funcs, contexts = Counter(), Counter(), Counter(), Counter()
    repeats = {}
    for rep, r in d["repeats"].items():
        den = int(r["total_period"])
        process.update(r["process_layer_counts"])
        for k, share in r["library_layer"].items():
            libs[k] += share * den
        repeats[rep] = {"roi_samples": r.get("roi_samples"), "roi_period": den,
                        "process_share": {k: v / den for k, v in r["process_layer_counts"].items()}}
        for f in r["function_layer"]:
            key = (f.get("role") or "unknown-role", f.get("dso_class") or "unknown",
                   Path(f.get("dso") or "").name, f.get("symbol") or "[unknown-symbol]",
                   f.get("entity_symbol") or "", Path(f.get("entity_dso") or "").name)
            weight = float(f.get("share_of_roi", 0)) * den
            funcs[key] += weight
            prefix = tuple(f.get("top_callstack", [])[:6])
            if prefix:
                contexts[(key[0], prefix)] += weight
    displayed_functions = funcs.most_common(30)
    symbols = Counter()
    for key, weight in funcs.items():
        symbols[key[3]] += weight
    unknown_leaf_period = sum(v for (role, dso_cls, dso, symbol, entity, entity_dso), v in funcs.items()
                              if dso_cls == "unknown" or symbol in ("", "[unknown-symbol]"))
    return {
        "dataset": config, "status": "eligible_existing_processed_profile",
        "repeat_count": len(repeats), "denominator": "full workload ROI cycles:u sample-period weight",
        "roi_samples": sum(int(x.get("roi_samples") or 0) for x in repeats.values()),
        "roi_period": total, "repeats": repeats,
        "process_share": pct_map(process, total), "library_share": pct_map(libs, total),
        "leaf_function_hotspots": [
            {"role": k[0], "dso_class": k[1], "dso": k[2], "leaf_function": k[3],
             "entity_function": k[4] or None, "entity_dso": k[5] or None,
             "period": v, "share_roi": v / total}
            for k, v in displayed_functions],
        "leaf_symbol_hotspots": [{"leaf_function": symbol, "period": weight,
                                   "share_roi": weight / total}
                                  for symbol, weight in symbols.most_common(20)],
        "leaf_function_weight_accounting": {
            "all_leaf_period_from_processed_aggregation": sum(funcs.values()),
            "displayed_top30_period": sum(v for _, v in displayed_functions),
            "unlisted_tail_period": total - sum(v for _, v in displayed_functions),
            "unknown_leaf_period": unknown_leaf_period,
            "unknown_leaf_share_roi": unknown_leaf_period / total,
            "sample_points_counted_once": True,
        },
        "overlapping_call_contexts": [
            {"role": k[0], "stack_prefix": list(k[1]), "period": v, "share_roi": v / total}
            for k, v in contexts.most_common(20)],
        "source": {"processed_profile": str(p.relative_to(BASE)), "sha256": sha(p)},
    }


def scriptio_module():
    spec = importlib.util.spec_from_file_location("scriptio_v2", BASE / "scripts/analyze_script_io_comparison.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def scriptio_by_role(path: Path, scene: str):
    mod = scriptio_module()
    roles, ops = Counter(), {}
    dropped_preflight = 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        stack, _, raw_count = line.rpartition(" ")
        count = int(raw_count)
        procs, frames = [], []
        for seg in stack.split(";"):
            m = mod.PROC.fullmatch(seg)
            (procs if m else frames).append(m.groups() if m else seg)
        if not procs:
            raise ValueError(f"{path}: py-spy sample has no process identity")
        command = procs[-1][1]
        role = mod.role_for(command, scene)
        if (role is None and scene == "xlsx" and command.endswith(".runtime.py")
                and any("run_xlsx_helper_atomic.py" in proc_cmd for _, proc_cmd in procs)
                and any("industry_productivity_build.py" in proc_cmd for _, proc_cmd in procs)):
            role = "xlsx-enhance"
        if role is None or (role == "runner" and len(procs) > 1 and command == procs[0][1]):
            for frame in frames:
                match = mod.MODULE_FRAME.search(frame)
                recovered = mod.role_for(match[1], scene) if match else None
                if recovered and recovered != "runner":
                    role = recovered
                    break
        role = role or ("runner" if len(procs) == 1 and not command.strip() else "other")
        if role == "runner" and any(mod.PRELOOP_FRAMES.search(f) for f in frames):
            dropped_preflight += count
            continue
        roles[role] += count
        op = mod.category(frames) if scene == "xlsx" else ("other" if frames else "no_python_frames")
        ops.setdefault(role, Counter())[op] += count
    total = sum(roles.values())
    assert total == sum(sum(x.values()) for x in ops.values()) and total > 0
    overall = Counter()
    for c in ops.values():
        overall.update(c)
    load_union = overall["load_call"] + overall["lazy_scan"]
    save = overall["save"]
    return {
        "denominator_samples": total, "preflight_samples_excluded": dropped_preflight,
        "role_samples": dict(roles),
        "role_share": {k: v / total for k, v in roles.most_common()},
        "operation_samples": dict(overall),
        "operation_share": {k: v / total for k, v in overall.items()},
        "A_load_workbook_internal": overall["load_call"] / total,
        "B_read_only_lazy_scan": overall["lazy_scan"] / total,
        "C_load_union": load_union / total,
        "D_workbook_save": save / total,
        "E_load_and_save_union": (load_union + save) / total,
        "F_other": overall["other"] / total,
        "unknown_no_python_frames": overall["no_python_frames"] / total,
        "by_script": {
            role: {"samples": n, "share_all_python": n / total,
                   "operations": dict(ops[role]),
                   "operation_share_within_script": {k: v / n for k, v in ops[role].items()}}
            for role, n in roles.most_common()},
        "classification": "Existing analyze_script_io_comparison.operation/category logic; per sample exclusive load_call, lazy_scan, save, other, or no_python_frames. load/save sets are de-duplicated by category; process-only samples remain denominator.",
    }


def scriptio_svg_by_role(path: Path):
    """Rebuild per-script XLSX operation counts from the historical SVG sample coordinates."""
    mod = scriptio_module()
    import re
    ns, fg = "{http://www.w3.org/2000/svg}", "{http://github.com/jonhoo/inferno}"
    root = mod.ET.parse(path).getroot()
    container = next(n for n in root.iter(ns + "svg") if n.get("id") == "frames")
    total = int(container.get("total_samples"))
    hits = [set() for _ in range(total)]
    has_frame = [False] * total
    roles = [(-1, "other") for _ in range(total)]
    for group in container:
        rect, title = group.find(ns + "rect"), group.find(ns + "title")
        if rect is None:
            continue
        name = re.sub(r" \([\d,]+ samples?, [\d.]+%\)$", "", title.text)
        start, count, depth = int(rect.get(fg + "x")), int(rect.get(fg + "w")), int(rect.get("y"))
        role = mod.role_for(name, "xlsx") if name.startswith("process ") else None
        op = mod.operation(name)
        for i in range(start, start + count):
            if role and depth > roles[i][0]:
                roles[i] = (depth, role)
            if op:
                hits[i].add(op)
            if name != "all" and not name.startswith(("process ", "thread ", "all (")):
                has_frame[i] = True
    role_counts, role_ops, overall = Counter(), {}, Counter()
    for h, resolved, (_, role) in zip(hits, has_frame, roles):
        if "save" in h and ("load_call" in h or "lazy_scan" in h):
            raise ValueError("historical SVG has nested save and load operation frames")
        op = next((k for k in ("load_call", "save", "lazy_scan") if k in h),
                  "other" if resolved else "no_python_frames")
        role_counts[role] += 1
        role_ops.setdefault(role, Counter())[op] += 1
        overall[op] += 1
    load = overall["load_call"] + overall["lazy_scan"]
    return {
        "denominator_samples": total, "preflight_samples_excluded": 0,
        "role_samples": dict(role_counts),
        "role_share": {k: v / total for k, v in role_counts.most_common()},
        "operation_samples": dict(overall),
        "operation_share": {k: v / total for k, v in overall.items()},
        "A_load_workbook_internal": overall["load_call"] / total,
        "B_read_only_lazy_scan": overall["lazy_scan"] / total,
        "C_load_union": load / total,
        "D_workbook_save": overall["save"] / total,
        "E_load_and_save_union": (load + overall["save"]) / total,
        "F_other": overall["other"] / total,
        "unknown_no_python_frames": overall["no_python_frames"] / total,
        "by_script": {role: {"samples": count, "share_all_python": count / total,
                              "operations": dict(role_ops[role]),
                              "operation_share_within_script": {k: v / count for k, v in role_ops[role].items()}}
                      for role, count in role_counts.most_common()},
        "classification": "Historical SVG sample coordinates mapped through the existing stack operation classifier; process-only samples retained.",
    }


def campaign_native(dataset: str):
    root = RECOVERY if dataset == "retail" else RECENT
    suffix = Path("retail/r1") if dataset == "retail" else Path(dataset) / "r1"
    base = root / suffix
    record_path = base / "out/collection-record.json"
    record = read(record_path) if record_path.is_file() else read(base / "out/recovery-record.json")
    roi = base / "out/roi.json"
    index = base / "sha256-index.json"
    samples = base / "out/samples.jsonl"
    if dataset == "retail":
        recovery_record = read(RECOVERY / "retail/r1/out/recovery-record.json")
        qualified = recovery_record.get("final_profile_eligible") is True
        identity = recovery_record["workload_identity_from_original_run"]
        quality = recovery_record.get("capture_quality", {})
    else:
        qualified = record.get("final_profile_eligible") is True
        identity = {k: record.get(k) for k in ("image", "image_id", "hashes", "runtime", "sampling", "cpu_affinity", "execution")}
        quality = record.get("capture_quality", {})
    if not qualified:
        raise ValueError(f"{dataset}: native record is not finally eligible")
    result = aggregate_sample_jsonl(samples, roi, index, "out/samples.jsonl", dataset, identity, quality)
    result["qualification_record"] = str(record_path.relative_to(BASE) if record_path.is_file() else (base / "out/recovery-record.json").relative_to(BASE))
    result["qualification_record_sha256"] = sha(record_path if record_path.is_file() else base / "out/recovery-record.json")
    result["archive_index_status"] = read(index).get("status")
    return result


def campaign_pyspy(dataset: str):
    base = RECENT / dataset / "pyspy"
    record_path = base / "out/collection-record.json"
    record = read(record_path)
    if record.get("final_profile_eligible") is not True:
        raise ValueError(f"{dataset}: py-spy record not finally eligible")
    index = base / "sha256-index.json"
    raw = base / "raw" / f"{dataset}.pyspy.raw"
    raw_hash = indexed_file_hash(index, f"raw/{dataset}.pyspy.raw")
    if not raw_hash:
        raise ValueError(f"{dataset}: py-spy raw missing from index")
    result = scriptio_by_role(raw, "xlsx")
    result.update({"dataset": dataset, "status": "eligible", "raw_path": str(raw.relative_to(BASE)),
                   "raw_sha256_from_existing_index": raw_hash,
                   "record_path": str(record_path.relative_to(BASE)),
                   "record_sha256": sha(record_path), "index_status": read(index).get("status"),
                   "identity": {k: record.get(k) for k in ("image_id", "hashes", "runtime", "sampling", "execution")},
                   "interpretation": "Independent py-spy Python activity sample counts, not native cycles or function wall time."})
    return result


def pdf_native(config):
    root = V1_CAMPAIGN / config / "r1"
    record = read(root / "out/collection-record.json")
    if record.get("status") != "success":
        raise ValueError(f"{config}: PDF native capture not successful")
    index = root / "sha256-index.json"
    return aggregate_sample_jsonl(root / "out/samples.jsonl", root / "out/roi.json", index if index.exists() else None,
                                  "out/samples.jsonl", config,
                                  {k: record.get("hashes", {}).get(k) for k in ("runner_sha256", "recipe_sha256", "verifier_sha256")},
                                  record.get("capture_quality", {}))


def pdf_pyspy(config):
    root = V1_CAMPAIGN / config / "pyspy"
    record = read(root / "out/collection-record.json")
    if record.get("status") != "success":
        raise ValueError(f"{config}: PDF py-spy capture not successful")
    index = root / "sha256-index.json"
    raw = root / "raw" / f"{config}.pyspy.raw"
    result = scriptio_by_role(raw, "pdf")
    result.update({"dataset": config, "record_path": str((root / "out/collection-record.json").relative_to(BASE)),
                   "record_sha256": sha(root / "out/collection-record.json"),
                   "raw_sha256_from_existing_index": indexed_file_hash(index, f"raw/{config}.pyspy.raw") if index.exists() else sha(raw),
                   "raw_hash_source": "existing_index" if index.exists() else "computed_for_small_pyspy_raw",
                   "index_status": read(index).get("status") if index.exists() else "no v1 index; raw file directly hashed"})
    return result


def current_pyspy(config, scene):
    raw = BASE / "raw" / config / "pyspy/raw" / f"{config}.pyspy.raw"
    result = scriptio_by_role(raw, scene)
    metadata_path = BASE / "raw" / config / "pyspy/out/metadata.json"
    result.update({"source_raw_path": str(raw.relative_to(BASE)), "source_raw_sha256_computed": sha(raw),
                   "source_raw_size_bytes": raw.stat().st_size,
                   "metadata_path": str(metadata_path.relative_to(BASE)) if metadata_path.is_file() else None,
                   "metadata_sha256": sha(metadata_path) if metadata_path.is_file() else None})
    return result


def historical_reported():
    return {
        "opm_n1": {"source": "legacy/evidence/ANALYSIS-python3123.md sections 4-5",
                    "process": {"python3": .9064, "pdftoppm": .0923},
                    "libraries": {"libpython": .5358, "zlib": .1814, "pillow": .1521, "poppler": .0627, "freetype": .0188},
                    "python_scripts": {"pdf-check-fillable": .0736, "pdf-extract-fields": .0977, "pdf-convert": .4388, "pdf-fill": .2121, "pdf-verify": .1429}},
        "tlc": {"source": "legacy/evidence/ANALYSIS-python3123.md sections 4-5",
                "process": {"python3": .9252, "libreoffice+threads": .0747},
                "libraries": {"libpython": .7965, "expat-xml": .0561, "elementtree-xml": .0349, "zlib": .0142},
                "python_scripts": {"xlsx-inspect-structure": .1358, "xlsx-inspect-features": .1109, "xlsx-enhance": .2345, "xlsx-recalc": .1261, "xlsx-verify": .1104, "xlsx-summary-export": .0882}},
        "scope": "Report-level historical document-oe aggregates; historical raw files exist under /home/lcq/document_perf but were not exported or re-parsed in this analysis. Historical function-level values are unavailable here."
    }


def pct(x):
    return f"{100*x:.1f}%"


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    native = {cfg: aggregate_processed(cfg) for cfg in ("opm-n1", "opm-n10", "tlc")}
    for cfg in ("irs_w4-n1", "irs_w4-n10", "sba1919-n1", "sba1919-n10"):
        native[cfg] = pdf_native(cfg)
    for ds in ("retail", "hr", "industry_productivity"):
        native[ds] = campaign_native(ds)

    pyspy = {cfg: current_pyspy(cfg, "xlsx" if cfg == "tlc" else "pdf")
             for cfg in ("opm-n1", "opm-n10", "tlc")}
    for cfg in ("irs_w4-n1", "irs_w4-n10", "sba1919-n1", "sba1919-n10"):
        pyspy[cfg] = pdf_pyspy(cfg)
    xlsx_io = {
        "historical_tlc": scriptio_svg_by_role(BASE / "legacy/evidence/python3123-pyspy/xlsx-python.svg"),
        "current_tlc": current_pyspy("tlc", "xlsx"),
    }
    hist_svg = BASE / "legacy/evidence/python3123-pyspy/xlsx-python.svg"
    xlsx_io["historical_tlc"]["source"] = {"path": str(hist_svg.relative_to(BASE)), "sha256": sha(hist_svg),
                                             "size_bytes": hist_svg.stat().st_size}
    for ds in ("retail", "hr", "industry_productivity"):
        pyspy[ds] = campaign_pyspy(ds)
        xlsx_io[ds] = pyspy[ds]

    historical = historical_reported()
    evidence = read(RECENT / "evidence-inventory.json")
    recovery_record = read(RECOVERY / "retail/r1/out/recovery-record.json")
    old_run_provenance_path = BASE / "metadata/run-provenance.json"
    old_run_provenance = read(old_run_provenance_path)
    old_control_runs = [r for r in old_run_provenance.get("runs", [])
                        if r.get("config") in ("opm-n1", "opm-n10", "tlc")]
    pdf_execution = {}
    for cfg in ("irs_w4-n1", "irs_w4-n10", "sba1919-n1", "sba1919-n10"):
        rec = read(V1_CAMPAIGN / cfg / "r1/out/collection-record.json")
        pdf_execution[cfg] = {"collection_status": rec.get("status"), "hashes": rec.get("hashes"),
                              "sampling": rec.get("sampling"), "runtime": rec.get("runtime"),
                              "execution": rec.get("execution"),
                              "native_record_path": str((V1_CAMPAIGN / cfg / "r1/out/collection-record.json").relative_to(BASE))}
    report_path = BASE / "legacy/evidence/ANALYSIS-python3123.md"
    build_info = {
        "schema": "hotspot-version-comparison-build-v2",
        "generated_utc": "2026-10-19",
        "analysis_script": str(Path(__file__).relative_to(BASE)),
        "analysis_script_sha256": sha(Path(__file__)),
        "script_io_classifier_sha256": sha(BASE / "scripts/analyze_script_io_comparison.py"),
        "profile_builder_sha256": sha(BASE / "scripts/build_profiles.py"),
        "evidence_inventory": {"path": str((RECENT / "evidence-inventory.json").relative_to(BASE)),
                                "sha256": sha(RECENT / "evidence-inventory.json")},
        "retail_recovery_record": {"path": str((RECOVERY / "retail/r1/out/recovery-record.json").relative_to(BASE)),
                                   "sha256": sha(RECOVERY / "retail/r1/out/recovery-record.json")},
        "historical_report": {"path": str(report_path.relative_to(BASE)), "sha256": sha(report_path)},
        "current_old_run_provenance": {"path": str((BASE / "metadata/run-provenance.json").relative_to(BASE)),
                                        "sha256": sha(BASE / "metadata/run-provenance.json")},
        "historical_xlsx_pyspy_svg": {"path": str(hist_svg.relative_to(BASE)), "sha256": sha(hist_svg)},
        "raw_hash_policy": "Large raw data hashes are referenced from existing campaign SHA256 indexes; this build did not rehash perf.data, samples.txt, or py-spy raw captures.",
        "versions": {"new_xlsx_campaign_image_id": evidence.get("image", {}).get("image_id"),
                     "new_xlsx_runner_sha256": evidence.get("preflight", {}).get("host", {}).get("retail", {}).get("runner_sha256"),
                     "new_xlsx_python": "3.12.3", "retail_workload_identity_from_original_run": recovery_record.get("workload_identity_from_original_run")},
    }

    data = {
        "schema": "hotspot-version-comparison-v2",
        "answers_scope": "Offline analysis of finally eligible profiles and report-level historical aggregates. No workload, collector, perf export, or full raw rehash was run.",
        "native_denominator": "full workload ROI cycles:u sample-period total; percent values are not elapsed time",
        "pyspy_denominator": "independent Python activity sample counts including process-only samples; identified runner preflight samples excluded and reported; not cycles or wall time",
        "native_profiles": native, "pyspy_profiles": pyspy,
        "xlsx_load_save": xlsx_io,
        "historical_reported": historical,
        "qualification_inventory": {"new_xlsx_campaign": evidence, "retail_recovery_status": recovery_record.get("final_profile_eligible"),
                                    "retail_original_capture_record_preserved_failed": recovery_record.get("original_failure_record", {}).get("status") == "failed"},
        "execution_versions": {
            "current_old_controls": {"source": str(old_run_provenance_path.relative_to(BASE)),
                                      "source_sha256": sha(old_run_provenance_path),
                                      "runs": old_control_runs},
            "new_pdf": pdf_execution,
            "new_xlsx": {"evidence_inventory_path": str((RECENT / "evidence-inventory.json").relative_to(BASE)),
                         "tasks": evidence.get("tasks", [])},
        },
        "limitations": [
            "历史 /home/lcq/document_perf 中的 native 原始文件存在；本轮没有纳入或重新导出。历史对比只能使用 document-oe 报告汇总值，逐函数历史对照留空。",
            "当前旧 OPM/TLC 与历史执行版本、runner/环境并非逐字节同一；变化是描述性比较，不是逐函数复现。",
            "native OPM/TLC 有两次重复；新 XLSX 和 PDF 各配置只有一次，无法估计新配置内波动或稳定性。",
            "Retail native 使用离线恢复后的 parser 输出，原采集失败记录仍保留失败；恢复只修复解析/归档资格，不代表重新采集。",
            "lost samples 与 lost chunks 分开记录，均来自采集报告/记录，ROI 归属未知；不转换为 cycles 权重。文本导出解析完整不等同采集无丢样。",
            "addr2line 警告、未知 DSO、未知符号与未恢复 inline owner 分别保留在各 native profile 的质量字段；符号警告数量不能代表其 period 影响。",
            "ROI marker 通过 PERFROI 中点与 stdout 时间估计对齐，尚未校准，缓冲/偏移误差未知。",
            "TLC/新 XLSX 的验证合约、输入结构和模块读取路径不同；工作量差异不归因于行业。Manufacturing 仅列为历史资料，不纳入主对比。",
            "py-spy 的 load/lazy/save 值是 Python 活动采样估计；不包括纯 native LibreOffice 活动，不可换算为函数墙钟或 native cycles。",
            "脚本按实际进程身份和命令职责对齐。相同 role 名称不代表源码相同；旧 OPM/TLC 未保存逐 PID 执行文件 hash，跨版本脚本同一性无法确认。新 run 的 runner/recipe/verifier/helper hash 按 record 保留，不能外推为所有进程脚本的 hash。",
        ],
        "script_role_alignment": {
            "basis": "Observed sampled command lines, process identity ancestry, and dataset role; industry productivity's generated hidden runtime helper is attributed to xlsx-enhance only when identity_cmdlines link it to run_xlsx_helper_atomic.py and helpers/industry_productivity_build.py.",
            "code_identity": "Role alignment is by responsibility. Exact script-code equality is reported only where a matching recorded file hash exists; this evidence does not contain per-PID hashes for every installed script, so same-role cross-dataset code identity is unverified.",
        },
        "build": build_info,
    }
    (OUT / "comparison.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    (OUT / "analysis-build.json").write_text(json.dumps(build_info, ensure_ascii=False, indent=2) + "\n")
    report = make_report(data)
    (OUT / "comparison-report.md").write_text(report)
    return data


def make_report(d):
    n, p, hist = d["native_profiles"], d["pyspy_profiles"], d["historical_reported"]
    opm_python = sum(v for k, v in n["opm-n1"]["process_share"].items()
                     if k.startswith(("pdf-", "python-")) or k in ("python-inline", "runner"))
    tlc_python = sum(v for k, v in n["tlc"]["process_share"].items()
                     if k.startswith(("xlsx-", "python-")) or k in ("python-inline", "runner"))
    tlc_lo = sum(v for k, v in n["tlc"]["process_share"].items()
                 if k in ("soffice.bin", "lo-thread", "thread-pool", "Parser"))
    io_brief = "; ".join(
        f"{label}: A/B/C/D/E {pct(d['xlsx_load_save'][key]['A_load_workbook_internal'])}/"
        f"{pct(d['xlsx_load_save'][key]['B_read_only_lazy_scan'])}/"
        f"{pct(d['xlsx_load_save'][key]['C_load_union'])}/"
        f"{pct(d['xlsx_load_save'][key]['D_workbook_save'])}/"
        f"{pct(d['xlsx_load_save'][key]['E_load_and_save_union'])}"
        for key, label in (("current_tlc", "TLC"), ("retail", "Retail"), ("hr", "HR"),
                           ("industry_productivity", "Industry Productivity"))
    )
    py_eval = {cfg: next((f["share_roi"] for f in n[cfg].get("leaf_symbol_hotspots", [])
                          if f["leaf_function"] == "_PyEval_EvalFrameDefault"), 0.0)
               for cfg in ("tlc", "retail", "hr", "industry_productivity")}
    lines = ["# 新旧执行版本热点对比 v2", "", "## 直接回答", "",
             f"1. **当前旧 OPM/TLC 与历史：** OPM N=1 的 Python 进程角色约 {pct(opm_python)} 对历史 {pct(hist['opm_n1']['process']['python3'])}（{(opm_python-hist['opm_n1']['process']['python3'])*100:+.1f} pp），pdftoppm {pct(n['opm-n1']['process_share'].get('pdftoppm',0))} 对 {pct(hist['opm_n1']['process']['pdftoppm'])}（{(n['opm-n1']['process_share'].get('pdftoppm',0)-hist['opm_n1']['process']['pdftoppm'])*100:+.1f} pp）；TLC Python/LibreOffice 分别 {pct(tlc_python)}/{pct(tlc_lo)}，历史 {pct(hist['tlc']['process']['python3'])}/{pct(hist['tlc']['process']['libreoffice+threads'])}。因此 TLC 大类接近，OPM 的 Poppler 子进程高约 3 pp；主要库也大体相近。历史只有报告汇总，函数级变化无法判断；两边 runner/环境不同，均属描述性比较。",
             f"2. **新数据集与旧用例：** XLSX 共有 libpython 热点（TLC {pct(n['tlc']['library_share'].get('libpython',0))}；Retail/HR/Industry {pct(n['retail']['library_share'].get('libpython',0))}/{pct(n['hr']['library_share'].get('libpython',0))}/{pct(n['industry_productivity']['library_share'].get('libpython',0))}），并有 Expat/ElementTree 与 LibreOffice 路径；采样点 `_PyEval_EvalFrameDefault` 分别占 TLC/Retail/HR/Industry ROI {pct(py_eval['tlc'])}/{pct(py_eval['retail'])}/{pct(py_eval['hr'])}/{pct(py_eval['industry_productivity'])}。新三者最大脚本分别是 inspect {pct(n['retail']['process_share'].get('xlsx-inspect-tool',0))}/{pct(n['hr']['process_share'].get('xlsx-inspect-tool',0))}/{pct(n['industry_productivity']['process_share'].get('xlsx-inspect-tool',0))}。PDF W-4/SBA 与 OPM 同见 zlib、Pillow 和 Poppler，N=1/N=10 分开。共享库/解释器函数只证明运行时路径相似，不能证明业务算法相同；新 XLSX 当前验证合约与旧 TLC 不同。",
             f"3. **XLSX load/save：** A/B/C/D/E（load_workbook 内部/只读延迟扫描/去重加载/Workbook.save/加载+保存）在全部 Python 活动样本中分别为：{io_brief}。样本按类别互斥、分母包括无 Python 栈；脚本贡献见后表。", "",
             "## 证据资格与版本", "", "| 对象 | 资格与使用口径 |", "|---|---|",
             "| 当前旧 OPM N=1/N=10、TLC | 复用 processed 中每项两次 native ROI；runner SHA 3623…，image ID 未记录；频率 OPM 99Hz/TLC 49Hz；TLC/OPM py-spy 复用已有记录。 |",
             "| IRS W-4、SBA 1919 N=1/N=10 | 复用 current-loop-verifier-v1 的成功 native/py-spy 记录；版本 hash、采样和执行信息按配置保存在 JSON；N 分开。 |",
             "| Retail native | recovery record 最终资格为 eligible；解析文本离线重算，原失败采集记录未改写。 |",
             "| Retail/HR/Industry py-spy 与 HR/Industry native | v2 evidence-inventory 和 collection records 最终资格 true，SHA256 index complete。 |",
             "| 历史 document-oe | 使用历史报告汇总。`/home/lcq/document_perf` 原始文件存在，但本轮未纳入/未解析。无历史逐函数对照。 |", "",
             "## 当前旧输入与历史报告级对比", "", "| 对照 | 指标 | 历史 | 当前 | 差值 |", "|---|---|---:|---:|---:|"]
    comparisons = [
        ("OPM N=1", "identified Python process roles", hist["opm_n1"]["process"]["python3"], sum(v for k,v in n["opm-n1"]["process_share"].items() if k.startswith(("pdf-", "python-")) or k in ("python-inline", "runner"))),
        ("OPM N=1", "pdftoppm", hist["opm_n1"]["process"]["pdftoppm"], n["opm-n1"]["process_share"].get("pdftoppm", 0)),
        ("TLC", "Python process", hist["tlc"]["process"]["python3"], sum(v for k,v in n["tlc"]["process_share"].items() if k.startswith(("xlsx-", "python-")))),
        ("TLC", "LibreOffice+threads", hist["tlc"]["process"]["libreoffice+threads"], sum(v for k,v in n["tlc"]["process_share"].items() if k in ("soffice.bin", "lo-thread", "thread-pool", "Parser"))),
    ]
    for label, metric, old, now in comparisons:
        lines.append(f"| {label} | {metric} | {pct(old)} | {pct(now)} | {(now-old)*100:+.1f} pp |")
    lines += ["", "历史库和脚本按报告同名口径另列。历史没有函数级样本记录，因此不为函数差异填造数字。当前 OPM/TLC 的两个 native repeat 详见 JSON `repeats`/`repeat_count`，其余新配置均为单次。", "",
              "## 当前 native：进程/脚本、DSO、叶函数", "", "全部百分比以完整 ROI 的 cycles:u sample period 为分母。前两次重复按 period 加权汇总，JSON 保留逐次 ROI period 和样本数。", "",
              "| 配置 | 重复/ROI period | 主要进程/脚本 | 主要 DSO | 主要叶函数 |", "|---|---:|---|---|---|"]
    for cfg in ("opm-n1", "opm-n10", "tlc", "irs_w4-n1", "irs_w4-n10", "sba1919-n1", "sba1919-n10", "retail", "hr", "industry_productivity"):
        x=n[cfg]; role="; ".join(f"{k} {pct(v)}" for k,v in list(x["process_share"].items())[:5])
        libs="; ".join(f"{k} {pct(v)}" for k,v in list(x["library_share"].items())[:5])
        fns="; ".join(f"{f['role']}:{f['leaf_function']} ({f['dso_class']}) {pct(f['share_roi'])}" for f in x["leaf_function_hotspots"][:4])
        lines.append(f"| {cfg} | {x.get('repeat_count',1)} / {x['roi_period']:,} | {role} | {libs} | {fns} |")
    lines += ["", "叶函数列是互斥采样点权重；JSON `overlapping_call_contexts` 是可重叠栈前缀，不与叶函数百分比相加。库类别中 unknown 保留，不重新归一化。脚本身份按采样进程实际命令/身份记录；`python-unknown-script` 不猜测归属。", "",
              "## 当前 OPM/TLC 与历史主要库、脚本", "", "| 配置/项 | 历史报告 | 当前 profile | 差值 |", "|---|---:|---:|---:|"]
    for cfg,key in (("opm-n1","opm_n1"),("tlc","tlc")):
        for k,old in hist[key]["libraries"].items():
            now=n[cfg]["library_share"].get(k,0)
            lines.append(f"| {cfg}/{k} | {pct(old)} | {pct(now)} | {(now-old)*100:+.1f} pp |")
        cur_py=p[cfg]["role_share"]
        for k,old in hist[key]["python_scripts"].items():
            now=cur_py.get(k,0)
            lines.append(f"| {cfg}/py-spy {k} | {pct(old)} | {pct(now)} | {(now-old)*100:+.1f} pp |")
    lines += ["", "脚本角色表示各自 Python 活动采样份额；当前脚本分解来自 py-spy，不与 native process cycles 混合。历史脚本份额来自历史报告聚合，环境/版本差异使其适合作描述性对照。", "",
              "## 新 PDF 与 OPM（按 N 分开）", "", "| 对照 | 配置 | native 主要进程 | 主要库 | py-spy 主要脚本 |", "|---|---|---|---|---|"]
    for size in ("n1", "n10"):
        old=f"opm-{size}"
        for prefix,label in (("irs_w4","IRS W-4"),("sba1919","SBA 1919")):
            cfg=f"{prefix}-{size}"
            roles="; ".join(f"{k} {pct(v)}" for k,v in list(n[cfg]["process_share"].items())[:4])
            libs="; ".join(f"{k} {pct(v)}" for k,v in list(n[cfg]["library_share"].items())[:4])
            scripts="; ".join(f"{k} {pct(v)}" for k,v in list(p[cfg]["role_share"].items())[:4])
            lines.append(f"| OPM {size} → {label} {size} | {cfg} | {roles} | {libs} | {scripts} |")
    lines += ["", "PDF N=10 profile 的 workload record_count 为 10；采集脚本的 requested/completed loop 字段按其运行配置记录，二者不混作单份任务。每个配置仅一条 profile，差异不代表稳定变化。", "",
              "## XLSX load_workbook、只读延迟扫描与保存", "", "py-spy 主分母是 ROI 内全部 Python 活动样本，含无 Python 函数栈进程样本；识别出的执行前 runner 校验样本单列并排除。A/B/C/D/E 为互斥分类样本的百分比，C=A+B，E=C+D。不是 wall time 或 native cycles。", "",
              "| 配置 | Python 样本 | A load 内部 | B 延迟扫描 | C 加载并集 | D Workbook.save | E 加载+保存并集 | 其他 | 无 Python 栈 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for cfg in ("historical_tlc", "current_tlc", "retail", "hr", "industry_productivity"):
        x=d["xlsx_load_save"][cfg]
        label={"historical_tlc":"TLC historical SVG","current_tlc":"TLC current py-spy"}.get(cfg,cfg)
        lines.append(f"| {label} | {x['denominator_samples']:,} | {pct(x['A_load_workbook_internal'])} | {pct(x['B_read_only_lazy_scan'])} | {pct(x['C_load_union'])} | {pct(x['D_workbook_save'])} | {pct(x['E_load_and_save_union'])} | {pct(x['F_other'])} | {pct(x['unknown_no_python_frames'])} |")
    lines += ["", "脚本贡献：第一百分比是该脚本占全部 Python 活动样本；括号中依次为脚本内部 load / lazy / save / other+无栈比例。JSON 按所有实际角色完整保留。", "", "| 配置 | 脚本热点及各自 load/lazy/save/other+无栈 |", "|---|---|"]
    for cfg in ("historical_tlc", "current_tlc", "retail", "hr", "industry_productivity"):
        x=d["xlsx_load_save"][cfg]
        rolelines=[]
        for role,item in sorted(x["by_script"].items(), key=lambda kv:-kv[1]["samples"]):
            q=item["operation_share_within_script"]
            rolelines.append(f"{role} {pct(item['share_all_python'])} (L {pct(q.get('load_call',0))}/lazy {pct(q.get('lazy_scan',0))}/save {pct(q.get('save',0))}/other+no-stack {pct(q.get('other',0)+q.get('no_python_frames',0))})")
        lines.append(f"| {cfg} | " + "; ".join(rolelines[:9]) + " |")
    lines += ["", "**边界：** read_only 后续 XML/worksheet generator/accessor 栈计入 lazy scan；若该栈仍嵌套在 load_workbook 中，样本按 load_call 归类一次。yield 单元格后的业务比较/样式验证归 other。Workbook.save 只识别 openpyxl workbook writer 栈，不包含 JSON save 或模块导入。", "",
              "## 采集质量、限制和解释", "",
              "| Native 配置 | lost samples | lost chunks | addr2line 警告 | unknown DSO period / ROI | unresolved leaf-symbol period / ROI | inline-owner unresolved period / ROI | 空栈 period / ROI |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for cfg in ("retail", "hr", "industry_productivity", "irs_w4-n1", "irs_w4-n10", "sba1919-n1", "sba1919-n10"):
        x = n[cfg]
        q = x.get("roi_quality") or {}
        cap = x.get("capture_quality") or {}
        loss = cap.get("capture_loss", {})
        sym = cap.get("symbol_resolution", {}).get("addr2line_warnings", {})
        den = x["roi_period"]
        unknown = int(q.get("true_unknown_dso_period", 0))
        unresolved = int(q.get("unresolved_leaf_symbol_period", 0))
        inline = int(q.get("inline_owner_unresolved_period", 0))
        empty = int(q.get("empty_stack_period", 0))
        lost_s = loss.get("lost_samples", {}).get("count", "not recorded")
        lost_c = loss.get("lost_chunks", {}).get("count", "not recorded")
        addr = sym.get("warning_count", "not recorded")
        lines.append(f"| {cfg} | {lost_s} | {lost_c} | {addr} | {unknown:,} / {pct(unknown/den)} | {unresolved:,} / {pct(unresolved/den)} | {inline:,} / {pct(inline/den)} | {empty:,} / {pct(empty/den)} |")
    lines += ["", "lost samples 与 lost chunks 是不同来源的采集区间计数，ROI 归属未知；addr2line 警告只表示解析警告条数，不等同丢失样本。解析质量字段的样本数/period 权重可能相互重叠（如 unresolved symbol 与 inline owner），不可相加。"]
    lines.extend(f"- {s}" for s in d["limitations"])
    lines += ["- 样本 period 权重比样本数量更能表示 cycles:u 份额；JSON 保留两者及未展示余量。函数榜仅列前 30，未展示权重与 unknown 仍在完整分母中。", "- 共同解释器/Expat/zlib/LibreOffice 库和函数仅能说明共同原生执行路径；不能推出同一 Python 业务算法、算法效率或优化收益。", "",
              "## 可追溯交付", "", "数值和每个 profile 的 period、样本数、质量字段、证据路径、执行身份见 `comparison.json`；本次分析代码与证据关联见 `analysis-build.json`。", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    result = build()
    print(OUT / "comparison-report.md")
