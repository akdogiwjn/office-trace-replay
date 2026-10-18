#!/usr/bin/env python3
"""Coverage, new-hotspot and legacy-claim verification analysis.

Reads processed/all-profiles.json (from build_profiles.py) plus the frozen
legacy inventories and emits:
  processed/coverage.json       per-config coverage breakdown
  processed/new-hotspots.json   uncovered / new-scale hotspot list
  processed/claims-verification.json  per-claim verification table
"""
import json
import hashlib
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "processed"

COVERED_MECHS = {
    "M-XLSX-LOAD", "M-XLSX-SAVE", "M-XLSX-TRAVERSE", "M-LO-RECALC",
    "M-PDF-QPDF-PARSE", "M-PDF-FORMFILL", "M-POPPLER-RASTER", "M-PILLOW-IMG",
}
UNCOVERED_MECHS = {"M-JSON-MAPPING", "M-ORCH"}

# old control references (ANALYSIS-python3123, N=1 PDF / 2-loop XLSX)
PDF_N1_CONFIGS = ["opm-n1", "irs_w4-n1", "sba1919-n1"]
PDF_N10_CONFIGS = ["opm-n10", "irs_w4-n10", "sba1919-n10"]
XLSX_CONFIGS = ["tlc", "retail", "manufacturing", "hr"]
LEGACY_MECHANISM_ALIASES = {"M-LO-RECALC": "M-LIBREOFFICE-NATIVE"}


def agg_repeats(profile, key):
    """Period-weighted merge of a per-repeat share dict."""
    merged = defaultdict(float)
    total_w = 0.0
    for rep, data in profile["repeats"].items():
        w = data["total_period"]
        total_w += w
        for k, v in data[key].items():
            merged[k] += v * w
    if not total_w:
        return {}
    return {k: v / total_w for k, v in merged.items()}


def merge_function_weights(repeats, periods):
    """Period-weighted full-repeat merge; absent functions contribute zero."""
    total = sum(periods.values())
    keys = set().union(*(set(rows) for rows in repeats.values())) if repeats else set()
    return {k: sum(repeats.get(rep, {}).get(k, 0.0) * periods[rep]
                   for rep in periods) / total for k in keys} if total else {}


def same_environment_control(dataset):
    if dataset.startswith("opm"):
        return dataset
    if dataset.startswith(("irs_w4", "sba1919")):
        return "opm-n10" if dataset.endswith("n10") else "opm-n1"
    if dataset == "tlc":
        return "tlc"
    if dataset in ("retail", "manufacturing", "hr"):
        return "tlc"
    return None


def python_roles_share(process_layer):
    python_keys = [r for r in process_layer
                   if r.startswith("pdf-") or r.startswith("xlsx-")
                   or r in ("runner", "python-inline", "python-unknown-script")]
    return sum(process_layer[r] for r in python_keys)


def lo_roles_share(process_layer):
    return sum(process_layer.get(r, 0) for r in
               ("soffice.bin", "lo-thread", "soffice-wrapper", "lo-startup"))


def _specific_native_mechanism(name):
    return (name != "M-UNCLASSIFIED" and "OTHER" not in name and
            "UNSPECIFIED" not in name)


def legacy_slice_reference(profiles, dataset):
    """Mechanisms, leaf functions, and eligible stack-prefix fingerprints sampled in old slices."""
    control = same_environment_control(dataset)
    profile = profiles.get(control, {})
    mechanisms, fingerprints, leaves, contributing_slices = set(), set(), set(), set()
    for repeat in profile.get("repeats", {}).values():
        layer = repeat.get("execution_path_layer", {})
        for sid, bins in layer.get("slice_mechanism_period", {}).items():
            present = {m for m, n in bins.items() if n and _specific_native_mechanism(m)}
            if present:
                contributing_slices.add(sid)
                mechanisms.update(present)
        for by_slice in layer.get("slice_stack_prefix_fingerprints", {}).values():
            fingerprints.update(sig for sig, period in by_slice.items() if period)
        for by_slice in layer.get("slice_leaf_function_period", {}).values():
            leaves.update(sig for sig, period in by_slice.items() if period)
    with open(ROOT / "legacy" / "legacy-slices.json") as fh:
        inventory = json.load(fh)
    scene = "pdf" if (control or "").startswith(("opm", "irs", "sba")) else "xlsx"
    slice_rows = inventory["pdf_slices"] if scene == "pdf" else inventory["xlsx_slices"]
    documented_mechanisms = {LEGACY_MECHANISM_ALIASES.get(m, m)
                             for sl in slice_rows for m in sl.get("covered_mechanisms", [])}
    return {"control": control, "mechanisms": mechanisms,
            "stack_prefix_fingerprints": fingerprints, "leaf_functions": leaves,
            "slices": contributing_slices,
            "documented_mechanisms": documented_mechanisms}


def coverage_for(dataset, profile, reference):
    per_rep = {}
    for rep, data in profile["repeats"].items():
        total = data["total_period"]
        direct = data["direct_path_share"]
        mech = data["mechanism_layer"]
        ref_mechanisms = reference["mechanisms"]
        mech_covered = sum(v for m, v in mech.items() if m in ref_mechanisms)
        direct_mech = data.get("execution_path_layer", {}).get("direct_mechanism_period", {})
        intersection = sum(v / total for m, v in direct_mech.items() if m in ref_mechanisms)
        union = direct + mech_covered - intersection
        additional = sum(v for m, v in mech.items()
                         if _specific_native_mechanism(m) and m not in ref_mechanisms)
        documented_candidate = sum(v for m, v in mech.items()
                                   if m in reference.get("documented_mechanisms", set())
                                   and m not in ref_mechanisms)
        status = data.get("native_mechanism_status_layer", {})
        true_unknown = sum(status.get(k, 0.0) for k in
                           ("unknown-dso", "unknown-symbol", "insufficient-stack", "unclassified"))
        known_upper_unknown = sum(data.get("native_status_upper_operation_layer", {}).get(f"{k}|unknown", 0.0)
                                  for k in ("known-native-mechanism", "known-extension-native-work",
                                            "known-runtime-operation-unspecified"))
        stack_prefix_match = sum(data.get("execution_path_layer", {}).get(
                                     "stack_prefix_fingerprint_period", {}).get(sig, 0)
                                 for sig in reference["stack_prefix_fingerprints"]) / total if total else 0.0
        leaf_match = sum(data.get("execution_path_layer", {}).get("leaf_function_period", {}).get(sig, 0)
                         for sig in reference["leaf_functions"]) / total if total else 0.0
        per_rep[rep] = {
            "direct_path_share": direct,
            "mechanism_evidence_share": mech_covered,
            "path_mechanism_intersection_share": intersection,
            "path_only_share": direct - intersection,
            "mechanism_only_share": mech_covered - intersection,
            "coverage_union_share": union,
            "coverage_total": union,
            "uncovered_share": max(0.0, 1.0 - union),
            "identified_mechanism_outside_old_selected_slice_share": additional,
            "documented_legacy_mechanism_without_matched_slice_samples_share": documented_candidate,
            "true_unknown_native_share": true_unknown,
            "native_mechanism_known_upper_operation_unknown_share": known_upper_unknown,
            "normalized_stack_prefix_fingerprint_match_share": stack_prefix_match,
            "same_leaf_function_share": leaf_match,
            "reference_mechanism_ids": sorted(ref_mechanisms),
            "documented_legacy_mechanism_candidate_ids": sorted(
                reference.get("documented_mechanisms", set()) - ref_mechanisms),
            "reference_slice_ids": sorted(reference["slices"]),
            "total": total,
        }
    # merged
    w = {r: d["total_period"] for r, d in profile["repeats"].items()}
    tw = sum(w.values())
    merged = {}
    for rep, c in per_rep.items():
        for k, v in c.items():
            if k != "total" and isinstance(v, (int, float)):
                merged[k] = merged.get(k, 0) + v * w[rep] / tw
    # Merge repeat shares using total sampled period, preserving each repeat above.
    return {"dataset": dataset, "same_environment_control": reference["control"],
            "reference_mechanism_ids": sorted(reference["mechanisms"]),
            "documented_legacy_mechanism_ids": sorted(reference.get("documented_mechanisms", set())),
            "reference_slice_ids": sorted(reference["slices"]),
            "reference_stack_prefix_fingerprint_count": len(reference["stack_prefix_fingerprints"]),
            "reference_leaf_function_count": len(reference["leaf_functions"]),
            "per_repeat": per_rep, "merged": merged}


def new_hotspots(profiles, *, write_outputs=True):
    threshold = 0.005
    out, threshold_summary = [], {}
    for cid, profile in profiles.items():
        reps = profile["repeats"]
        total_period = sum(d["total_period"] for d in reps.values())
        reference = legacy_slice_reference(profiles, cid)
        reference_mechs = reference["mechanisms"]
        reference_fingerprints = reference["stack_prefix_fingerprints"]
        by_rep = {}
        stacks_by_rep = {}
        for rep, data in reps.items():
            rows = {}
            stack_rows = {}
            for e in data["function_layer"]:
                k = (e["role"], e["dso_class"], e.get("dso"), e["symbol"],
                     e.get("entity_symbol"), e.get("entity_dso"), e.get("mechanism"),
                     e.get("upper_operation"), e.get("native_status"),
                     tuple(e.get("context_mechanisms", [])))
                value = rows.setdefault(k, {"share": 0.0, "direct_share": 0.0,
                                            "stack_prefix_match_share": 0.0,
                                            "same_leaf_function_share": 0.0,
                                            "context_mechanisms": e.get("context_mechanisms", [])})
                value["share"] += e["share_of_roi"]
                stack_rows[k] = e.get("top_callstack", [])
                matched_prefix_period = sum(period for sig, period in
                    e.get("stack_prefix_fingerprint_period", {}).items() if sig in reference_fingerprints)
                value["stack_prefix_match_share"] += matched_prefix_period / data["total_period"]
                leaf_signature = json.dumps({"leaf": e["symbol"], "dso_class": e["dso_class"]},
                                            sort_keys=True, ensure_ascii=False)
                if leaf_signature in reference["leaf_functions"]:
                    value["same_leaf_function_share"] += e["share_of_roi"]
                if e.get("direct_path_matched"):
                    value["direct_share"] += e["share_of_roi"]
            by_rep[rep] = rows
            stacks_by_rep[rep] = stack_rows
        periods = {rep: d["total_period"] for rep, d in reps.items()}
        merged_weights = merge_function_weights(
            {rep: {k: v["share"] for k,v in rows.items()} for rep,rows in by_rep.items()}, periods)
        merged_direct_weights = merge_function_weights(
            {rep: {k: v["direct_share"] for k,v in rows.items()} for rep,rows in by_rep.items()}, periods)
        merged_rows = list(merged_weights.items())
        listed = [(k, v) for k, v in merged_rows if v >= threshold]
        mechanism_layer = {m: sum(d["mechanism_layer"].get(m, 0.0) * d["total_period"]
                                  for d in reps.values()) / total_period
                           for m in set().union(*(d["mechanism_layer"] for d in reps.values()))}
        unknown_total = 0.0
        for d in reps.values():
            statuses = d.get("native_mechanism_status_layer", {})
            unknown_total += (sum(statuses.get(s, 0.0) * d["total_period"]
                                  for s in ("unknown-dso", "unknown-symbol", "insufficient-stack", "unclassified")))
        unknown_total /= total_period
        unknown_listed = sum(v for k, v in listed
                             if k[8] in ("unknown-dso", "unknown-symbol", "insufficient-stack", "unclassified"))
        threshold_summary[cid] = {
            "threshold_share": threshold,
            "merge_method": "period-weighted across all repeats; absent function in a repeat contributes zero",
            "listed_hotspot_share": sum(v for _, v in listed),
            "below_threshold_or_function_retention_residual_share": max(0.0, 1 - sum(v for _, v in listed)),
            "unknown_mechanism_share": unknown_total,
            "unknown_below_threshold_or_unlisted_share": max(0.0, unknown_total - unknown_listed),
            "documented_legacy_mechanism_without_matched_slice_samples_share": sum(
                mechanism_layer.get(m, 0.0) for m in
                reference.get("documented_mechanisms", set()) - reference_mechs),
            "documented_legacy_mechanism_candidate_ids": sorted(
                reference.get("documented_mechanisms", set()) - reference_mechs),
            "period_partition_sum": sum(mechanism_layer.values()),
            "repeat_count": len(reps),
            "legacy_control": reference["control"],
            "reference_slice_ids": sorted(reference["slices"]),
            "reference_mechanism_ids": sorted(reference_mechs),
        }
        for key, share in listed:
            role, dso_cls, dso, sym, entity_sym, entity_dso, mechanism, upper_operation, native_status, contexts = key
            direct_share = merged_direct_weights.get(key, 0.0)
            stack_prefix_share = sum(v.get("stack_prefix_match_share", 0.0) * periods[rep]
                                 for rep, rows in by_rep.items()
                                 for k, v in rows.items() if k == key) / total_period
            same_leaf_share = sum(v.get("same_leaf_function_share", 0.0) * periods[rep]
                                  for rep, rows in by_rep.items()
                                  for k, v in rows.items() if k == key) / total_period
            if native_status in ("unknown-dso", "unknown-symbol", "insufficient-stack", "unclassified"):
                category, why, confidence = "unknown-native-hotspot", "native sample lacks DSO/symbol/stack evidence; not a new mechanism", "low"
            elif direct_share > 0:
                category, why, confidence = "old-selected-execution-path-hotspot", "sampled in a source-matched old selected script; mechanism remains independently classified", "direct path evidence"
            elif mechanism in reference_mechs and stack_prefix_share > 0:
                category, why, confidence = "shared-native-mechanism-and-stack-prefix", "native mechanism and eligible normalized stack-prefix fingerprint occur in old selected-slice samples; not full-path or code identity", "eligible stack-prefix fingerprint"
            elif mechanism in reference_mechs:
                category, why, confidence = "new-execution-path-shared-native-mechanism", "native mechanism appears in old selected slices, but no eligible stack-prefix fingerprint matched", "leaf mechanism; stack-prefix not matched"
            elif mechanism in reference.get("documented_mechanisms", set()):
                category, why, confidence = ("candidate-documented-legacy-mechanism-without-matched-slice-samples",
                "legacy slice definition documents this mechanism, but source-matched old slice samples do not provide a native function/stack-prefix reference; excluded from definite mechanism coverage",
                    "legacy definition + current native DSO/function")
            elif _specific_native_mechanism(mechanism):
                category, why, confidence = "identified-mechanism-outside-old-selected-reference", "resolved native mechanism absent from observed old selected-slice mechanism reference; this alone does not prove a new algorithm", "native symbol/callstack"
            else:
                category, why, confidence = "candidate-or-unspecified-native-hotspot", "resolved DSO but no specific native mechanism rule; not a new mechanism", "low"
            repeat_shares = {rep: by_rep[rep].get(key, {}).get("share", 0.0) for rep in reps}
            callstacks = {rep: stacks_by_rep[rep].get(key, []) for rep in reps}
            out.append({"config": cid, "role": role, "dso_class": dso_cls, "dso": dso,
                        "symbol": sym, "callstack_by_repeat": callstacks,
                        "entity_symbol": entity_sym, "entity_dso": entity_dso,
                        "cpu_weight": share, "repeat_shares": repeat_shares,
                        "merge_method": threshold_summary[cid]["merge_method"],
                        "mechanism": mechanism, "upper_operation": upper_operation,
                        "context_mechanisms": list(contexts),
                        "native_status": native_status,
                        "normalized_stack_prefix_fingerprint_match_weight_share": stack_prefix_share,
                        "same_leaf_function_weight_share": same_leaf_share,
                        "context_mechanisms": by_rep[next(iter(reps))].get(key, {}).get("context_mechanisms", []),
                        "classification": category,
                        "why_not_automatically_new": why, "confidence": confidence,
                        "direct_path_matched": direct_share >= share * (1 - 1e-9) if share else False,
                        "direct_path_weight_share": direct_share,
                        "direct_path_fraction_of_function": direct_share / share if share else 0.0,
                        "evidence": [f"raw/{cid}/{rep}/out/samples.jsonl" for rep in reps]})
    out.sort(key=lambda x: (x["config"], -x["cpu_weight"]))
    if write_outputs:
        (PROCESSED / "hotspot-threshold-summary.json").write_text(json.dumps(threshold_summary, indent=2) + "\n")
    return out


def verify_claims(profiles, coverage):
    """Claim-specific checks anchored to same-environment OPM/TLC controls."""
    legacy = json.load(open(ROOT / "legacy" / "legacy-claims.json"))
    claims = {c["claim_id"]: c for c in legacy["claims"]}
    table = []

    def interval(profile, key, metric):
        vals = [d.get(key, {}).get(metric) for d in profile.get("repeats", {}).values()]
        vals = [v for v in vals if isinstance(v, (int, float))]
        return (min(vals), max(vals)) if vals else None

    def overlap(a, b):
        return bool(a and b and max(a[0], b[0]) <= min(a[1], b[1]))

    def emit(cid, dataset, status, current, basis, boundary, control=None,
             history=None, paths=None, dimensions=None):
        claim = claims[cid]
        table.append({"claim_id": cid, "legacy_claim": claim["original"],
            "applicability": claim.get("applicability"), "dataset": dataset,
            "same_environment_control": control, "current_comparison": current,
            "historical_reference": history or claim.get("original_evidence"),
            "quantitative_evidence": current,
            "evidence": current, "decision_basis": basis, "status": status,
            "applicability_boundary": boundary, "evidence_paths": paths or [],
            "dimensions": dimensions or {}})

    pdf_n1 = ["opm-n1", "irs_w4-n1", "sba1919-n1"]
    pdf_n10 = ["opm-n10", "irs_w4-n10", "sba1919-n10"]
    xlsx = ["tlc", "retail", "manufacturing", "hr"]
    profile_path = lambda cid: f"processed/{cid}.json (native r1/r2 period aggregates)"

    def point_in_repeat_range(values, point):
        return bool(values) and min(values) <= point <= max(values)

    # Process dominance and its quantitative proximity are separate assertions.
    for cid in pdf_n1:
        if cid not in profiles: continue
        control_id = "opm-n1"
        p, ctl = profiles[cid], profiles[control_id]
        py = interval(p, "process_layer", "pdf-python")
        # Actual process roles vary; use the aggregate role share already stored.
        py_vals = [sum(v for role, v in d["process_layer"].items()
                       if role.startswith("pdf-") or role in ("python-unknown-script", "python-inline"))
                   for d in p["repeats"].values()]
        pp_vals = [d["process_layer"].get("pdftoppm", 0) for d in p["repeats"].values()]
        ctl_py = [sum(v for role, v in d["process_layer"].items()
                      if role.startswith("pdf-") or role in ("python-unknown-script", "python-inline"))
                  for d in ctl["repeats"].values()]
        ctl_pp = [d["process_layer"].get("pdftoppm", 0) for d in ctl["repeats"].values()]
        dominant = all(a > b for a, b in zip(py_vals, pp_vals))
        close = max(min(py_vals), min(ctl_py)) <= min(max(py_vals), max(ctl_py))
        historical_points = {"python": 0.9064, "pdftoppm": 0.0923}
        hist_overlap = {"python": point_in_repeat_range(py_vals if cid == control_id else ctl_py,
                                                          historical_points["python"]),
                        "pdftoppm": point_in_repeat_range(pp_vals if cid == control_id else ctl_pp,
                                                          historical_points["pdftoppm"])}
        similar_to_baseline = all(hist_overlap.values()) if cid == control_id else close
        status = "supported" if dominant and similar_to_baseline else "partially-supported" if dominant else "not-supported"
        emit("CLM-01", cid, status,
             f"Python-process share repeats={list(map(lambda x:round(x,4),py_vals))}; pdftoppm={list(map(lambda x:round(x,4),pp_vals))}; OPM same-scale={list(map(lambda x:round(x,4),ctl_py))}",
             "Dominance is checked per repeat. OPM historical single-run points must fall inside the current OPM repeat ranges; new PDFs must overlap current OPM ranges. No uniform percentage band is used.",
             "N=1 PDF only; values describe current 8-CPU workload; process role grouping follows argv identity.", control_id,
             "Historical OPM N=1: python 90.64%, pdftoppm 9.23% (single historical run).",
             [profile_path(cid), "raw/{config}/r{1,2}/out/samples.jsonl", "legacy/evidence/ANALYSIS-python3123.md#section-4"],
             {"mechanism_presence": "not assessed", "dominance": dominant,
              "same_environment_repeat_range_overlap": close,
              "historical_point_inside_current_range": hist_overlap})
        lib_values = {key: [d["library_layer"].get(key, 0.0) for d in p["repeats"].values()]
                      for key in ("libpython", "zlib", "pillow", "poppler", "freetype")}
        ctl_values = {key: [d["library_layer"].get(key, 0.0) for d in ctl["repeats"].values()]
                      for key in lib_values}
        present = [k for k, vals in lib_values.items() if max(vals, default=0)>0]
        close_libs = [k for k in present if max(min(lib_values[k]), min(ctl_values[k])) <= min(max(lib_values[k]), max(ctl_values[k]))]
        historical_lib_points = {"libpython": .5358, "zlib": .1814, "pillow": .1521,
                                 "poppler": .0627, "freetype": .0188}
        comparison_ranges = lib_values if cid == control_id else ctl_values
        historical_lib_overlap = [k for k, point in historical_lib_points.items()
                                  if point_in_repeat_range(comparison_ranges[k], point)]
        lib_status = ("supported" if (set(lib_values).issubset(set(close_libs)) if cid != control_id
                                      else len(historical_lib_overlap) == len(historical_lib_points))
                      else "partially-supported" if present else "not-supported")
        emit("CLM-02", cid, lib_status,
             "; ".join(f"{k} repeats={lib_values[k]} same-env OPM={ctl_values[k]}" for k in lib_values),
             "All expected DSOs must overlap OPM's same-environment repeat ranges for new PDFs; the OPM baseline is checked against historical single-run points. No universal percentage tolerance is applied.",
             "N=1 PDF; same leaf-DSO categorization after inline recovery; percentages are sample-period estimates.", control_id,
             "Historical OPM N=1: libpython 53.58%, zlib 18.14%, Pillow 15.21%, Poppler 6.27%, FreeType 1.88%.",
             [profile_path(cid), "processed/all-profiles.json", "legacy/evidence/ANALYSIS-python3123.md#section-4"],
             {"mechanisms_present": present, "repeat_ranges_overlapping_control": close_libs,
              "historical_points_inside_comparison_ranges": historical_lib_overlap,
              "quantitative_similarity": "repeat-range overlap only; historical values are single-run references"})

    for cid in xlsx:
        if cid not in profiles: continue
        p, ctl = profiles[cid], profiles["tlc"]
        py_vals = [sum(v for role,v in d["process_layer"].items() if role.startswith("xlsx-") or role in ("python-unknown-script","python-inline")) for d in p["repeats"].values()]
        lo_vals = [sum(d["process_layer"].get(r,0) for r in ("soffice.bin","lo-thread","soffice-wrapper","lo-startup")) for d in p["repeats"].values()]
        ctl_py = [sum(v for role,v in d["process_layer"].items() if role.startswith("xlsx-") or role in ("python-unknown-script","python-inline")) for d in ctl["repeats"].values()]
        dominant = all(a>b for a,b in zip(py_vals,lo_vals))
        close = max(min(py_vals),min(ctl_py)) <= min(max(py_vals),max(ctl_py))
        historical_python, historical_lo = .9252, .0747
        historical_overlap = {"python": point_in_repeat_range(py_vals if cid == "tlc" else ctl_py,
                                                                historical_python),
                              "libreoffice": point_in_repeat_range(lo_vals if cid == "tlc" else
                                  [sum(d["library_layer"].get(k, 0) for k in ("libreoffice",)) for d in ctl["repeats"].values()],
                                  historical_lo)}
        status="supported" if dominant and (all(historical_overlap.values()) if cid=="tlc" else close) else "partially-supported" if dominant else "not-supported"
        emit("CLM-04",cid,status,f"python shares={py_vals}; LO shares={lo_vals}; same-env TLC Python shares={ctl_py}",
             "Python dominance is checked separately. TLC historical points must lie inside current TLC repeat ranges; new XLSX datasets must overlap current TLC ranges.",
             "XLSX datasets only; 8-CPU current runs vs historical TLC 4-CPU run.","tlc",
             "Historical TLC: Python 92.52%, LibreOffice 7.47%.",[profile_path(cid),"legacy/evidence/ANALYSIS-python3123.md#section-4"],
             {"dominant_mechanism":dominant,"quantitative_repeat_range_overlap":close,
              "historical_points_inside_comparison_ranges":historical_overlap})
        keys=("libpython","expat-xml","elementtree-xml","zlib","libreoffice")
        vals={k:[d["library_layer"].get(k,0) for d in p["repeats"].values()] for k in keys}
        ctlvals={k:[d["library_layer"].get(k,0) for d in ctl["repeats"].values()] for k in keys}
        present=[k for k,v in vals.items() if max(v,default=0)>0]
        overlaps=[k for k in keys if max(min(vals[k]),min(ctlvals[k]))<=min(max(vals[k]),max(ctlvals[k]))]
        historical_dso_points={"libpython":.7965,"expat-xml":.0561,"elementtree-xml":.0349,
                               "zlib":.0142,"libreoffice":.07}
        dso_comparison=vals if cid=="tlc" else ctlvals
        hist_dso_overlap=[k for k,pnt in historical_dso_points.items()
                          if point_in_repeat_range(dso_comparison[k],pnt)]
        emit("CLM-05",cid,"supported" if (set(keys).issubset(set(overlaps)) if cid!="tlc" else len(hist_dso_overlap)==len(keys)) else "partially-supported" if present else "not-supported",
             f"libraries current repeat ranges={vals}; same-env TLC={ctlvals}",
             "For TLC, historical single-run DSO points are checked against current repeat ranges; new XLSX datasets must overlap the current TLC repeat ranges for all listed DSO classes. No fixed pp band is used.",
             "XLSX only; current/new workflows may use different operation mixes.","tlc",
             "Historical TLC: libpython 79.65%, Expat 5.61%, elementtree 3.49%, zlib 1.42%, LO DSOs ~7%.",
             [profile_path(cid),"legacy/evidence/ANALYSIS-python3123.md#section-4"],
             {"mechanisms_present":present,"repeat_ranges_overlapping_control":overlaps,
              "historical_points_inside_comparison_ranges":hist_dso_overlap})

    for cid in pdf_n1 + xlsx:
        if cid not in profiles or "pyspy" not in profiles[cid]: continue
        claim="CLM-03" if cid.startswith(("opm","irs","sba")) else "CLM-06"
        py=profiles[cid]["pyspy"]["roles"]
        top=sorted(((r,v.get("samples",0)) for r,v in py.items()),key=lambda x:-x[1])[:8]
        scripts=[r for r,_ in top]
        new_roles=[r for r in scripts if r in ("pdf-mapping-driver","pdf-summary-writer","xlsx-inspect-tool","xlsx-atomic-helper","xlsx-verify")]
        c = coverage.get(cid, {}).get("merged", {})
        path_match = c.get("direct_path_share", 0.0)
        mechanism_match = c.get("mechanism_evidence_share", 0.0)
        stack_prefix_match = c.get("normalized_stack_prefix_fingerprint_match_share", 0.0)
        documented_candidate = c.get("documented_legacy_mechanism_without_matched_slice_samples_share", 0.0)
        status = "partially-supported" if mechanism_match > 0 else "insufficient-evidence"
        emit(claim,cid,status,
             f"native common-mechanism share={mechanism_match:.4f}; normalized stack-prefix fingerprint match share={stack_prefix_match:.4f}; source-matched old path share={path_match:.4f}; legacy-documented mechanism without matched old-slice sample share={documented_candidate:.4f}; single py-spy top roles={top}; new roles={new_roles}",
             "Leaf-function mechanism and eligible normalized stack-prefix fingerprints support shared native work at their respective evidence levels. Prefixes are limited to eight normalized frames, require at least four resolved frames, merge DSOs into classes, and do not establish full call paths or code identity. Neither mechanism nor prefix identity proves the same Python algorithm; single-run py-spy is contextual only and is not assigned to native cycles. The assertion that there are no new business hotspots is not established.",
             "N=1 PDF or one-loop/current XLSX; conclusions are Python-stack evidence only.",same_environment_control(cid),
             "Historical sources: ANALYSIS-python3123.md section 5; old script percentages are not mixed with native cycles.",
             [f"raw/{cid}/pyspy/out/pyspy-roles.json","legacy/evidence/ANALYSIS-python3123.md#section-5"],
             {"common_native_mechanism_share": mechanism_match,
              "normalized_stack_prefix_fingerprint_share": stack_prefix_match,
              "documented_legacy_mechanism_without_matched_slice_samples_share": documented_candidate,
              "direct_old_execution_path_share": path_match,
              "new_script_paths":new_roles,
              "business_operation_attribution":"unknown unless supported by stack evidence",
              "no_new_business_hotspot_claim":"not established",
              "repeatability":"py-spy single run; native r1/r2 retained"})

    for cid in list(profiles):
        if "stat" not in profiles[cid]: continue
        scene="pdf" if cid.startswith(("opm","irs","sba")) else "xlsx"
        old= "PDF IPC 2.55/kernel 13.93%" if scene=="pdf" else "XLSX IPC 2.53/kernel 2.17%"
        st=profiles[cid]["stat"]
        emit("CLM-07",cid,"insufficient-evidence",f"user IPC={st.get('user_ipc')}; kernel cycles share={st.get('kernel_cycles_share')}; stat events include runner preflight",
             "Current perf stat wraps the runner including preflight; historical measurement scope differs and stat is not ROI-scoped.",
             "Perf-stat runs only; not evidence about workload ROI cycles composition.",same_environment_control(cid),old,
             [f"raw/{cid}/stat/stat.csv",f"raw/{cid}/stat/metadata.json","legacy/evidence/ANALYSIS-python3123.md#section-6"],
             {"measurement_scope_match":False})

    for cid in list(profiles):
        scene="pdf" if cid.startswith(("opm","irs","sba")) else "xlsx"
        if scene=="xlsx" and cid!="tlc": pass
        claim="CLM-08" if scene=="pdf" else "CLM-09"
        par=[d.get("parallelism",{}) for d in profiles[cid]["repeats"].values()]
        multi=[v.get("multi_active_poll_interval_share") for v in par if v.get("multi_active_poll_interval_share") is not None]
        if multi:
            emit(claim,cid,"insufficient-evidence",f"threads-with-counter-advance-per-poll-interval shares={multi}; maximum active-thread counts within an interval={ [v.get('max_active_threads_in_poll_interval') for v in par] }",
                 "These are counts of threads whose counters advanced at least once during a 10-25ms interval; they do not establish overlap or simultaneity. No scheduler trace is available.",
                 "PDF only for CLM-08; XLSX only for CLM-09.",same_environment_control(cid),
                 "Historical scheduling assertions are from bound CPU traces; see legacy ANLYSIS section 7.",
                 [profile_path(cid),"legacy/evidence/ANALYSIS-python3123.md#section-7"],{"simultaneous_scheduling":"not measured"})

    for cid in list(profiles):
        if cid not in ("tlc","retail","manufacturing","hr"):
            if cid.startswith(("opm","irs","sba")):
                emit("CLM-10", cid, "not-applicable", "PDF workload; CLM-10 concerns XLSX LibreOffice futex behavior.",
                     "Claim scope is XLSX only.","PDF datasets are outside claim scope.",None,
                     "Historical XLSX futex evidence in ANALYSIS-python3123.md section 8.",[],{})
            continue
        if "syscalls" not in profiles[cid] or cid != "tlc":
            sc=profiles[cid].get("syscalls", {})
            syscall_summary = (f"observed aggregate futex calls={sc.get('futex',{}).get('calls')}; calls share={sc.get('futex_call_share')}; seconds share={sc.get('futex_time_share')}"
                               if sc else "No current strace aggregate for this dataset.")
            emit("CLM-10",cid,"insufficient-evidence",syscall_summary,
                 "Same-environment TLC syscall capture is absent for new XLSX datasets; aggregate strace cannot attribute futex to LibreOffice or establish repeat stability.","XLSX only.","tlc",
                 "TLC historical total 555,991/556,023; futex calls 110,379/111,894; futex cumulative time 78.57%/79.87%.",
                 ([f"raw/{cid}/syscalls/syscalls.txt"] if sc else []) + ["legacy/evidence/ANALYSIS-python3123.md#section-8"],
                 {"same_environment_control_available":False,"process_attribution":"insufficient"})
            continue
        sc=profiles[cid]["syscalls"]; fr=sc.get("futex_call_share"); ft=sc.get("futex_time_share")
        status="insufficient-evidence"
        emit("CLM-10",cid,status,
             f"calls total={sc['total_calls']}, futex calls share={fr:.2%}, futex cumulative syscall-time share={ft:.2%}; calls sum matches total={sc['calls_total_matches']}; calls-ranked top={[ (r['syscall'],r['calls']) for r in sc['calls_ranked'][:5] ]}",
             "‘Dominant’ is checked by cumulative syscall-time share to match the historical report; calls share is separately shown. Aggregate strace cannot attribute futex to LibreOffice.",
             "XLSX strace runs only; cumulative syscall seconds include blocking time and are not kernel CPU.","tlc",
             "Historical TLC: futex ~79% of strace cumulative time; 110,379/111,894 calls.",
             [f"raw/{cid}/syscalls/syscalls.txt","legacy/evidence/ANALYSIS-python3123.md#section-8"],
             {"futex_calls_share":fr,"futex_cumulative_time_share":ft,"process_attribution":"insufficient"})

    for cid in ("opm-n1", "opm-n10", "tlc"):
        if cid not in profiles: continue
        repeats = profiles[cid]["repeats"]
        evidence_rows = [e for d in repeats.values()
                         for e in d.get("execution_path_layer", {}).get("slice_evidence", {}).values()]
        # Path mapping is direct identity evidence even when the historical
        # runtime file hash was not captured. Keep that limitation explicit;
        # candidate paths with content conflicts do not count as self-coverage.
        matched = sum(e.get("status") == "identity_path_mapped_and_sampled_runtime_hash_unknown"
                      for e in evidence_rows)
        unverified = sum(e.get("status") == "candidate_path_or_content_unconfirmed"
                         for e in evidence_rows)
        unknown_role = [d["unresolved"].get("unknown_role", 0) for d in repeats.values()]
        emit("CLM-11",cid,"partially-supported" if matched else "insufficient-evidence",
             f"identity-path mapped and sampled={matched}/{len(evidence_rows)} repeat-slice observations; content/path candidates not counted={unverified}; direct path period share by repeat={[d['execution_path_layer'].get('direct_slice_share', 0) for d in repeats.values()]}; unknown-role period shares={unknown_role}",
             "Timestamped process identities map selected scripts and permitted descendants to old slices. This confirms execution-path self-coverage, while absent per-process executed-file hashes and the unresolved candidate scripts prevent treating the full slice inventory as content-verified. Native mechanism unknowns are separate.",
             "Self-coverage applies only to re-sampled OPM N=1/N=10 and TLC; current identity argv did not record executed-file hashes.",cid,
             "Historical structural attribution claim; see old slice inventory and slicing readmes.",
             [profile_path(cid),"processed/legacy-slice-mapping.json","legacy/legacy-slices.json","legacy/slice-source-hashes.json"],
             {"identity_path_mapped_sampled_observations":matched,"candidate_observations_not_counted":unverified,
              "direct_path_period_share_by_repeat":[d["execution_path_layer"].get("direct_slice_share",0) for d in repeats.values()],
              "unknown_role_shares":unknown_role})
    for cid in xlsx:
        if cid not in profiles:continue
        lib=agg_repeats(profiles[cid],"library_layer"); exp=lib.get("expat-xml",0)+lib.get("elementtree-xml",0)
        emit("CLM-12",cid,"partially-supported" if exp>0 else "not-supported",f"expat+elementtree DSO share={exp:.3%}",
             "Validates XML parser DSO presence, not its whole Python-level work share.","XLSX workloads only.","tlc",
             "Historical DSO note: pyexpat CPython 3.12 extension replaces old libexpat presentation.",
             [profile_path(cid),"legacy/evidence/ANALYSIS-python3123.md#section-4"],{"DSO_presence":exp>0})

    for cid in ("opm-n10",):
        if cid not in profiles:continue
        p=profiles[cid]; control_id="opm-n10"
        proc=agg_repeats(p,"process_layer")
        slices={sid:sum(d["execution_path_layer"]["matched_slice_period_shares"].get(sid,0)*d["total_period"] for d in p["repeats"].values())/sum(d["total_period"] for d in p["repeats"].values()) for sid in ("PDF-S1","PDF-S2","PDF-S3","PDF-S4","PDF-S5","PDF-S6")}
        evidence=f"exact-script slice shares={slices}; process roles={ {k:round(v,4) for k,v in proc.items() if k.startswith('pdf-') or k in ('pdftoppm','pdfinfo')} }; r1/r2 retained in per-repeat mapping"
        emit("CLM-13",cid,"partially-supported",evidence,
             "Use OPM N=10 as same-environment comparator; historical single-core PMU function windows differ from current 8-core period sample/process-window mapping.",
             "PDF N=10 only; convert parent windows and children are not identical to historical function-window accounting.",control_id,
             "Historical OPM N=10 slice weights: check+extract 3.348%, convert_from_path 17.256%, conversion-other 32.500%, fill 33.053%, verify 10.224%, unsliced 3.647%.",
             [profile_path(cid),f"raw/{cid}/r{{1,2}}/out/monitor/identity.jsonl","legacy/evidence/REPORT-pdf10-weight.md"],
             {"per_slice_path_shares":slices})
    for cid in ("opm-n10",):
        if cid in profiles:
            emit("CLM-14",cid,"insufficient-evidence","Native run has no scheduler trace; monitor poll intervals do not prove child-process ordering.",
                 "Parent/child timeline claim needs event trace or verified per-process start/exit timestamps.","PDF N=10 only.","opm-n10",
                 "Historical claim was under single-CPU binding; see REPORT-pdf10-weight.md.",[profile_path(cid),"legacy/evidence/REPORT-pdf10-weight.md"],{})
            emit("CLM-15",cid,"insufficient-evidence","Per-record monitor CPU time is not the historical per-record cycles:u PMU weight; raw per-record event windows are unavailable.",
                 "Measurement metric mismatch (CPU time vs cycles) prevents validating the historical narrow 0.5%-range consistency.","PDF N=10 only.","opm-n10",
                 "Historical fill cycles 3.296%-3.310%, instructions 2.938%-2.943%.",[profile_path(cid),"legacy/evidence/REPORT-pdf10-weight.md"],{})
    emit("CLM-16","all","insufficient-evidence","Aggregate workload replay does not independently prove all fourteen frozen slices can be replayed from their fixed input states.",
         "Slice execution-path evidence is not a standalone slice-replay test.","Structural legacy claim.",None,
         "legacy/evidence/README-slicing-pdf.md; legacy/evidence/README-slicing-xlsx.md",
         ["legacy/legacy-slices.json"],{})
    return table


def refresh_source_evidence_from_identity(profiles):
    """Rebuild source/candidate provenance from current timestamped identity logs.

    This is deliberately separate from weighted native-profile aggregation: it
    refreshes only provenance rows so a source-rule correction never requires
    reparsing large samples.jsonl files when period weights did not change.
    """
    from build_profiles import legacy_process_scope_index
    plan = {c["config_id"]: c for c in
            json.load(open(ROOT / "config" / "run-plan.json"))["configs"]}
    inventory = json.load(open(ROOT / "legacy" / "legacy-slices.json"))
    source_hashes = json.load(open(ROOT / "legacy" / "slice-source-hashes.json"))
    for cid, profile in profiles.items():
        scene = plan.get(cid, {}).get("scene")
        if not scene:
            continue
        slices = inventory["pdf_slices"] if scene == "pdf" else inventory["xlsx_slices"]
        for rep, data in profile.get("repeats", {}).items():
            identity_path = ROOT / "raw" / cid / rep / "out" / "monitor" / "identity.jsonl"
            scoped, _direct, candidates = legacy_process_scope_index(identity_path, scene, cid)
            layer = data.setdefault("execution_path_layer", {})
            slice_rows = layer.setdefault("slice_evidence", {})
            for sl in slices:
                sid = sl["slice_id"]
                evidence, candidate_rows, commands = [], [], set()
                for pid, entries in scoped.items():
                    for entry in entries:
                        if entry.get("slice_id") == sid:
                            evidence.append(entry)
                            if entry.get("command"):
                                commands.add(entry["command"])
                for pid, entries in candidates.items():
                    for entry in entries:
                        if entry.get("slice_id") == sid:
                            candidate_rows.append(entry)
                candidate_commands = sorted({json.dumps(x, sort_keys=True, ensure_ascii=False)
                                             for x in candidate_rows})
                old = slice_rows.setdefault(sid, {})
                old.update({
                    "legacy_script": sl["script"],
                    "matched_actual_commands": sorted(commands),
                    "candidate_argv_mentions": candidate_commands,
                    "source_evidence": evidence,
                    "candidate_source_evidence": candidate_rows,
                    "frozen_source_sha256": source_hashes.get(sid, {}).get("frozen_source_sha256"),
                    "executed_file_sha256": None,
                    "match_basis": "timestamped argv/ppid identity plus explicit or frozen-operation cwd and frozen-source hash mapping",
                    "remaining_gap": "historical per-process executed-file SHA256 was not recorded",
                })
                old["status"] = ("identity_path_mapped_and_sampled_runtime_hash_unknown"
                                  if evidence and old.get("sampled_period_share", 0) > 0 else
                                  "identity_path_observed_no_native_sample_runtime_hash_unknown"
                                  if evidence else "candidate_path_or_content_unconfirmed"
                                  if candidate_rows else "no_matching_identity_evidence")
                old["unmatched_reason"] = (None if evidence else
                    "script operand path was observed but frozen-source content relation is unresolved"
                    if candidate_rows else
                    "no Python script operand resolved to this frozen source in timestamped identities")


def main():
    profiles = json.load(open(PROCESSED / "all-profiles.json"))
    refresh_source_evidence_from_identity(profiles)
    json.dump(profiles, open(PROCESSED / "all-profiles.json", "w"), indent=2)
    for cid, profile in profiles.items():
        json.dump(profile, open(PROCESSED / f"{cid}.json", "w"), indent=2)
    old_profile_path = ROOT / "metadata" / "pre-inline-fix-library-profile.json"
    old_profiles = json.load(open(old_profile_path)) if old_profile_path.is_file() else {}
    old_profile_path = ROOT / "metadata" / "pre-inline-fix-library-profile.json"
    old_profiles = json.load(open(old_profile_path)) if old_profile_path.is_file() else {}
    coverage = {}
    crosscheck = {}
    slice_mapping = {}
    for cid, p in profiles.items():
        reference = legacy_slice_reference(profiles, cid)
        coverage[cid] = coverage_for(cid, p, reference)
        crosscheck[cid] = {}
        slice_mapping[cid] = {}
        for rep, d in p["repeats"].items():
            slice_mapping[cid][rep] = d.get("execution_path_layer", {}).get("slice_evidence", {})
            monitor = d.get("monitor_cpu_shares", {})
            native = d.get("process_layer", {})
            roles = set(monitor) | set(native)
            diffs = [{"role": role, "cycles_u_share": native.get(role, 0.0),
                      "monitor_cpu_time_share": monitor.get(role, 0.0),
                      "difference_pp": 100 * (native.get(role, 0.0) - monitor.get(role, 0.0))}
                     for role in roles]
            crosscheck[cid][rep] = sorted(diffs, key=lambda x: -abs(x["difference_pp"]))
    json.dump(coverage, open(PROCESSED / "coverage.json", "w"), indent=2)
    json.dump(crosscheck, open(PROCESSED / "monitor-cycles-crosscheck.json", "w"), indent=2)
    inventory = json.load(open(ROOT / "legacy" / "legacy-slices.json"))
    all_slice_rows = inventory["pdf_slices"] + inventory["xlsx_slices"]
    source_map = {}
    frozen_hashes = json.load(open(ROOT / "legacy" / "slice-source-hashes.json"))
    def unique_evidence(rows):
        found = {}
        for row in rows or []:
            key = json.dumps(row, sort_keys=True, ensure_ascii=False)
            found[key] = row
        return list(found.values())
    def with_source_chain(row):
        row = dict(row)
        src = row.get("source", {})
        cwd_resolution = row.get("cwd_resolution") or src.get("cwd_resolution") or {}
        chain = [{"evidence": "timestamped process identity argv",
                  "command": row.get("command"), "relation": row.get("relation"),
                  "process_pid": row.get("process_pid"), "process_ppid": row.get("process_ppid"),
                  "scope_parent_pid": row.get("scope_parent_pid"),
                  "scope_child_pid": row.get("scope_child_pid"),
                  "identity_first_t_ns": row.get("identity_first_t_ns"),
                  "identity_last_t_ns": row.get("identity_last_t_ns")}]
        if row.get("cwd"):
            chain.append({"evidence": cwd_resolution.get("evidence_grade",
                         "cwd from directly logged shell command or process identity chain"),
                          "cwd": row.get("cwd"),
                          "source_command": cwd_resolution.get("recipe_command")})
        if src.get("source_path"):
            chain.append({"evidence": "resolved installed/workspace path alias to frozen repository source",
                          "source_path": src.get("source_path"),
                          "frozen_source_sha256": src.get("frozen_source_sha256") or src.get("source_sha256"),
                          "repository_source_sha256": src.get("repository_source_sha256"),
                          "repository_source_hash_verified": src.get("repository_source_hash_verified",
                              src.get("source_hash_verified"))})
        if src.get("active_recipe_source_sha256"):
            chain.append({"evidence": "current active source hash comparison",
                          "active_recipe_source_sha256": src["active_recipe_source_sha256"],
                          "match": src.get("active_recipe_source_sha256") ==
                                   (src.get("frozen_source_sha256") or src.get("source_sha256"))})
        chain.append({"evidence": "historical per-process executed-file hash", "status": "not recorded"})
        row["source_chain"] = chain
        row["evidence_level"] = ("candidate_path_content_conflict" if src.get("active_recipe_source_sha256") and
                                  src.get("active_recipe_source_sha256") !=
                                  (src.get("frozen_source_sha256") or src.get("source_sha256")) else
                                  "identity_path_mapped_to_archived_source_runtime_hash_unknown")
        return row
    for repeats in slice_mapping.values():
        for slices in repeats.values():
            for item in slices.values():
                item["source_evidence"] = unique_evidence(item.get("source_evidence"))
                item["candidate_source_evidence"] = unique_evidence(item.get("candidate_source_evidence"))
                if item["source_evidence"] and item.get("sampled_period_share", 0) > 0:
                    item["status"] = "identity_path_mapped_and_sampled_runtime_hash_unknown"
                elif item["source_evidence"]:
                    item["status"] = "identity_path_observed_no_native_sample_runtime_hash_unknown"
                elif item["candidate_source_evidence"] or item.get("candidate_argv_mentions"):
                    item["status"] = "candidate_path_or_content_unconfirmed"
                else:
                    item["status"] = "no_matching_identity_evidence"
    json.dump(slice_mapping, open(PROCESSED / "legacy-slice-mapping.json", "w"), indent=2)
    for sl in all_slice_rows:
        sid = sl["slice_id"]
        seen, candidates = [], []
        for cid, repeats in slice_mapping.items():
            scene = "pdf" if cid.startswith(("opm", "irs", "sba")) else "xlsx"
            if (sid.startswith("PDF-") != (scene == "pdf")):
                continue
            for rep, rows in repeats.items():
                item = rows.get(sid, {})
                evidence_rows = [with_source_chain(e) for e in
                                 unique_evidence(item.get("source_evidence"))]
                candidate_rows = [with_source_chain(e) for e in
                                  unique_evidence(item.get("candidate_source_evidence"))]
                if evidence_rows:
                    seen.append({"dataset": cid, "repeat": rep,
                                 "sampled_period_share": item.get("sampled_period_share", 0),
                                 "status": item.get("status"),
                                 "source_evidence": evidence_rows})
                if candidate_rows:
                    candidates.append({"dataset": cid, "repeat": rep,
                                       "status": item.get("status"),
                                       "candidate_source_evidence": candidate_rows})
        source_map[sid] = {"legacy_script": sl["script"],
                           "frozen_source": frozen_hashes.get(sid),
                           "confirmed_observations": seen,
                           "candidate_observations": candidates,
                           "match_status": "identity_path_mapped_to_archived_source_runtime_hash_unknown" if seen else
                                           "candidate_only" if candidates else "not_observed",
                           "remaining_gap": "historical process capture did not record executed file hash; content conflicts remain candidates" if candidates else
                                           "no matching identity evidence" if not seen else
                                           "runtime executed-file hash was not captured"}
    json.dump(source_map, open(PROCESSED / "legacy-slice-source-map.json", "w"), indent=2)
    parse_quality = {}
    for cid, p in profiles.items():
        parse_quality[cid] = {}
        for rep in p["repeats"]:
            roi_file = ROOT / "raw" / cid / rep / "out" / "roi.json"
            if roi_file.is_file():
                roi = json.load(open(roi_file))
                loss_report = ROOT / "raw" / cid / rep / "out" / "native-by-dso.txt"
                loss_match = re.search(r"Total Lost Samples:\s*(\d+)",
                                       loss_report.read_text(errors="replace")) if loss_report.is_file() else None
                unresolved = p["repeats"][rep].get("unresolved", {})
                parse_quality[cid][rep] = {
                    "roi_samples": roi.get("roi_samples"),
                    "roi_period_total": roi.get("roi_period_total"),
                    "perf_script_parse": roi.get("perf_script_parse", {}),
                    "unresolved_leaf_symbol_period_share": unresolved.get("unresolved_leaf_symbol", 0),
                    "unresolved_leaf_symbol_samples": unresolved.get("unresolved_leaf_symbol_samples", 0),
                    "perf_report_lost_samples": int(loss_match.group(1)) if loss_match else None,
                    "stack_unwind_failure_count": None,
                    "stack_unwind_failure_note": "perf script text has no explicit per-sample unwind-failure counter; unknown/empty/malformed categories are reported separately, so no failure count is inferred",
                    "roi_alignment": {k: roi.get(k) for k in (
                        "alignment_method", "alignment_uncertainty", "perf_to_mono_offset_s",
                        "marker_sample_count", "marker_perf_span_s", "loop_start_mono_s",
                        "marker_mono_s", "preloop_excluded_samples", "preloop_excluded_period")},
                    "source": f"raw/{cid}/{rep}/out/roi.json",
                }
    meta_dir = ROOT / "metadata"
    meta_dir.mkdir(exist_ok=True)
    json.dump(parse_quality, open(meta_dir / "native-parse-quality.json", "w"), indent=2)
    impact = {}
    for cid, p in profiles.items():
        impact[cid] = {}
        for rep, d in p["repeats"].items():
            old = old_profiles.get(cid, {}).get(rep, {}).get("library_layer", {})
            new = d.get("library_layer", {})
            keys = set(old) | set(new)
            impact[cid][rep] = {"before_unknown_dso_share": old.get("unknown", 0.0),
                "after_unknown_dso_share": new.get("unknown", 0.0),
                "unknown_dso_change_pp": 100 * (new.get("unknown", 0.0)-old.get("unknown", 0.0)),
                "library_share_changes_pp": {k: 100 * (new.get(k,0.0)-old.get(k,0.0)) for k in keys},
                "comparison_source": "metadata/pre-inline-fix-library-profile.json captured before this parser reprocessing"}
    json.dump(impact, open(PROCESSED / "parser-correction-impact.json", "w"), indent=2)
    impact = {}
    for cid, p in profiles.items():
        impact[cid] = {}
        for rep, d in p["repeats"].items():
            old = old_profiles.get(cid, {}).get(rep, {}).get("library_layer", {})
            new = d.get("library_layer", {})
            keys = set(old) | set(new)
            impact[cid][rep] = {"before_unknown_dso_share": old.get("unknown", 0.0),
                "after_unknown_dso_share": new.get("unknown", 0.0),
                "unknown_dso_change_pp": 100 * (new.get("unknown", 0.0)-old.get("unknown", 0.0)),
                "library_share_changes_pp": {k: 100 * (new.get(k,0.0)-old.get(k,0.0)) for k in keys},
                "comparison_source": "metadata/pre-inline-fix-library-profile.json captured before this parser reprocessing"}
    json.dump(impact, open(PROCESSED / "parser-correction-impact.json", "w"), indent=2)
    hotspots = new_hotspots(profiles)
    json.dump(hotspots, open(PROCESSED / "new-hotspots.json", "w"), indent=2)
    table = verify_claims(profiles, coverage)
    json.dump(table, open(PROCESSED / "claims-verification.json", "w"), indent=2)
    classifier_impact = {}
    for cid, profile in profiles.items():
        total = sum(d["total_period"] for d in profile["repeats"].values())
        merged = defaultdict(float)
        per_repeat = {}
        for rep, data in profile["repeats"].items():
            transitions = data.get("legacy_context_classifier_transition_share", {})
            per_repeat[rep] = transitions
            for key, share in transitions.items():
                merged[key] += share * data["total_period"] / total if total else 0
        classifier_impact[cid] = {
            "legacy_context_classifier_transition_share": dict(merged),
            "per_repeat": per_repeat,
            "interpretation": "reapplies the former joined-stack classifier as a diagnostic; corrected primary mechanism is leaf-only and this comparison is not used for coverage",
            "rule_version": "native-mechanisms-v3-leaf-context-separated"}
    json.dump(classifier_impact, open(PROCESSED / "mechanism-classifier-impact.json", "w"), indent=2)

    repo = ROOT.parent.parent
    def file_sha(path):
        path = repo / path
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    run_prov = json.load(open(ROOT / "metadata" / "run-provenance.json"))
    run_rows = run_prov.get("runs", [])
    recorded_by_config = {}
    for row in run_rows:
        recorded_by_config.setdefault(row["config"], row)
    image_acceptance = json.load(open(repo / "reports/evidence/v9/image-verification.json"))
    source_catalog = json.load(open(ROOT / "legacy/slice-source-hashes.json"))
    source_checks = {}
    for sid, spec in source_catalog.items():
        actual = file_sha(spec["frozen_source_path"])
        source_checks[sid] = {"frozen_path": spec["frozen_source_path"],
                              "expected_sha256": spec["frozen_source_sha256"],
                              "repository_sha256": actual,
                              "repository_hash_matches": actual == spec["frozen_source_sha256"],
                              "historical_runtime_hash_recorded": False}
    recipe_checks = {}
    for cid, row in recorded_by_config.items():
        rel = ("legacy/document-oe/operations/pdf_key_operations.json" if cid in ("opm-n1", "opm-n10")
               else "legacy/document-oe/operations/xlsx_key_operations.json" if cid == "tlc"
               else f"compatibility/recipes/{cid}.json")
        recipe_checks[cid] = {"path": rel, "recorded_sha256": row.get("recipe_sha256"),
                              "repository_sha256": file_sha(rel),
                              "matches_recorded_recipe": file_sha(rel) == row.get("recipe_sha256"),
                              "runner_recorded_sha256": row.get("runner_sha256"),
                              "actual_runtime_image_id": row.get("actual_runtime_image_id"),
                              "planned_image_id": row.get("planned_image_id")}
    source_audit = {
        "schema_version": "runtime-script-source-audit-v1",
        "source_resolution_rule": "actual argv path -> Docker-installed legacy or runner DATASETS seed -> apply any exact recipe write override; source context is not treated as executed source",
        "docker": {"dockerfile": "runtime/Dockerfile", "dockerfile_sha256": file_sha("runtime/Dockerfile"),
                   "install_rule": "COPY legacy/document-oe/ /opt/document-bench/",
                   "runner_path": "legacy/document-oe/bin/run_document_scene_loop.py",
                   "runner_sha256": file_sha("legacy/document-oe/bin/run_document_scene_loop.py"),
                   "skills_rule": "prepare_environment->_ensure_skills symlinks /root/.openclaw/skills/{pdf,xlsx} to /opt/document-bench/skills/{pdf,xlsx}",
                   "old_dataset_sources": {"opm-n1": {"source": None, "seed": "/opt/document-bench/pdf"},
                                           "opm-n10": {"source": None, "seed": "/opt/document-bench/pdf"},
                                           "tlc": {"source": None, "seed": "/opt/document-bench/xlsx"},
                                           "reset": "reset_workspace removes prior workspace then shutil.copytree(seed, workspace)"}},
        "image_acceptance": {"path": "reports/evidence/v9/image-verification.json",
                             "image": image_acceptance.get("image"), "image_id": image_acceptance.get("image_id"),
                             "status": image_acceptance.get("validate"),
                             "workload_files": image_acceptance.get("workload_files"),
                             "note": "acceptance verifies the planned v9 image and workload files; collector did not record actual image ID"},
        "recipe_hash_checks": recipe_checks,
        "frozen_slice_source_checks": source_checks,
        "known_snapshot_comparison_traps": {
            "X-S4": {"runtime_path": "/root/.openclaw/skills/xlsx/scripts/recalc.py",
                     "runtime_chain_source": "legacy/document-oe/skills/xlsx/scripts/recalc.py",
                     "runtime_chain_sha256": file_sha("legacy/document-oe/skills/xlsx/scripts/recalc.py"),
                     "compatibility_source_snapshot_sha256": file_sha("compatibility/cases/manufacturing/source/vendor/skills/xlsx/scripts/recalc.py"),
                     "interpretation": "the source snapshot hash is not the script runtime path; the runner Skill symlink resolves to the Docker-installed legacy file"},
            "PDF-S6": {"runtime_path": "/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/input/verify_pdf_batch.py",
                        "runtime_chain_source": "legacy/document-oe/pdf/input/verify_pdf_batch.py",
                        "runtime_chain_sha256": file_sha("legacy/document-oe/pdf/input/verify_pdf_batch.py"),
                        "interpretation": "old OPM source=None; workspace reset copies /opt/document-bench/pdf seed; unrelated assets/source copy is not selected"},
            "X-S7": {"runtime_path": "/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01/input/verify_xlsx_enhanced.py",
                     "runtime_chain_source": "legacy/document-oe/xlsx/input/verify_xlsx_enhanced.py",
                     "runtime_chain_sha256": file_sha("legacy/document-oe/xlsx/input/verify_xlsx_enhanced.py"),
                     "interpretation": "old TLC source=None; workspace reset copies /opt/document-bench/xlsx seed; no recipe write targets this verifier"}},
        "status_boundary": "all source hashes here are reconstructed from frozen repository, runner and Docker rules, not historical per-process executed-file hash observations",
    }
    json.dump(source_audit, open(ROOT / "metadata" / "source-resolution-audit.json", "w"), indent=2)
    code_paths = [ROOT / "scripts" / name for name in (
        "parse_native.py", "rename_parallelism_schema.py", "build_profiles.py",
        "analyze_comparison.py", "generate_report.py", "build_raw_index.py",
        "run_collection2.sh", "analyze_unconfirmed_residuals.py",
        "generate_final_summary.py", "profile_artifacts.py")]
    code_paths += [ROOT / "config" / "mechanism-taxonomy.json"]
    code_hashes = {}
    for path in code_paths:
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        code_hashes[str(path.relative_to(ROOT))] = h
    json.dump({"generated_utc": __import__("datetime").datetime.now(
                   __import__("datetime").timezone.utc).isoformat(),
               "analysis_code_sha256": code_hashes,
               "result_inputs": ["processed/all-profiles.json", "raw/*/out/samples.jsonl",
                                 "raw/*/out/roi.json"],
               "recompute_commands_from_repository_root": [
                   "python3 analysis/hotspot-comparison/scripts/rename_parallelism_schema.py",
                   "python3 analysis/hotspot-comparison/scripts/build_profiles.py",
                   "python3 analysis/hotspot-comparison/scripts/analyze_comparison.py",
                   "python3 analysis/hotspot-comparison/scripts/generate_report.py"]},
              open(ROOT / "metadata" / "analysis-build.json", "w"), indent=2)
    print("coverage:")
    for cid, c in coverage.items():
        m = c["merged"]
        print(f"  {cid:16s} path={m['direct_path_share']:.1%} "
              f"mechanism={m['mechanism_evidence_share']:.1%} "
              f"intersection={m['path_mechanism_intersection_share']:.1%} "
              f"union={m['coverage_total']:.1%} unknown={m['true_unknown_native_share']:.1%}")
    print(f"\nnew hotspots: {len(hotspots)} entries")
    print(f"claim rows: {len(table)}")


if __name__ == "__main__":
    main()
