#!/usr/bin/env python3
"""Explain the existing path-or-mechanism coverage residuals without changing coverage.

The script re-reads the already parsed native samples and assigns only samples
outside the existing direct-path/mechanism union to mutually exclusive evidence
classes.  It never writes coverage.json.
"""
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent.parent
RAW = ROOT / "raw"
PROCESSED = ROOT / "processed"
METADATA = ROOT / "metadata"
REPORTS = ROOT / "reports"
sys.path.insert(0, str(ROOT / "scripts"))

import build_profiles as native  # noqa: E402
import analyze_comparison as comparison  # noqa: E402

DATASETS = ("retail", "manufacturing", "hr")
CATEGORIES = ("R1", "R2", "R3", "R4", "R5")
CATEGORY_LABELS = {
    "R1": "规范化栈前缀指纹匹配",
    "R2": "仅叶函数匹配",
    "R3": "具体原生机制已知，旧切片参考未观察到",
    "R4": "符号/DSO 已解析，机制不够具体",
    "R5": "证据不足（未知项或采样质量限制）",
}
DISPLAY_THRESHOLD = 0.005  # 0.5% of the complete ROI, after full repeat matching/merge.
TOP_N = 10
UNKNOWN_SYMBOLS = getattr(native, "UNKNOWN_SYMBOLS", {"[unknown]", "[unknown symbol]", "??", "unknown", ""})


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def leaf_signature(symbol, dso_class):
    return json.dumps({"leaf": symbol, "dso_class": dso_class},
                      sort_keys=True, ensure_ascii=False)


def classify_residual_sample(sample, *, direct_path_matched, reference_mechanisms,
                             reference_fingerprints, reference_leaf_functions):
    """Classify a single ROI sample; return None when it is already in A union B.

    Priority for residual samples is R1 > R2 > R3 > R4 > R5. Unknown leaf/DSO
    values are never compared as matching function evidence. Weak-stack quality
    remains an independent diagnostic; a stronger resolved leaf/mechanism is
    retained when the stack itself is short.
    """
    stack = sample.get("stack") or []
    dso_cls = native.dso_class(str(sample.get("leaf_dso") or "[unknown]"))
    symbol = str(sample.get("leaf_sym") or "")
    role = str(sample.get("role") or "unknown")
    classified = native.classify_native_mechanism(role, dso_cls, symbol, stack)
    mechanism = classified["mechanism"]
    prefix = native.stack_prefix_fingerprint(stack)
    leaf_known = dso_cls != "unknown" and symbol not in UNKNOWN_SYMBOLS
    matched_prefix = (leaf_known and prefix["status"] == "strong" and
                      prefix["fingerprint"] in reference_fingerprints)
    leaf_sig = leaf_signature(symbol, dso_cls) if leaf_known else None
    matched_leaf = bool(leaf_sig and leaf_sig in reference_leaf_functions)

    # The original union is exactly A (sample's actual process scope) union B
    # (leaf-derived mechanism among those observed in old selected slices).
    if direct_path_matched or mechanism in reference_mechanisms:
        return None

    if matched_prefix:
        category = "R1"
    elif matched_leaf:
        category = "R2"
    elif comparison._specific_native_mechanism(mechanism):
        category = "R3"
    elif leaf_known and classified["native_status"] not in (
            "unknown-symbol", "unknown-dso", "unclassified"):
        category = "R4"
    else:
        category = "R5"

    if dso_cls == "unknown" and symbol in UNKNOWN_SYMBOLS:
        quality_reason = "unknown-dso-and-symbol"
    elif dso_cls == "unknown":
        quality_reason = "unknown-dso"
    elif symbol in UNKNOWN_SYMBOLS:
        quality_reason = "unknown-symbol"
    elif not stack:
        quality_reason = "empty-stack"
    elif prefix["status"] == "weak-short-stack":
        quality_reason = "short-stack"
    elif prefix["status"] == "weak-unknown-frame":
        quality_reason = "unknown-frame-in-prefix"
    else:
        quality_reason = "no-quality-blocker"

    return {
        "category": category,
        "mechanism": mechanism,
        "native_status": classified["native_status"],
        "upper_operation": classified["upper_operation"],
        "leaf_symbol": symbol,
        "leaf_dso": sample.get("leaf_dso"),
        "leaf_dso_class": dso_cls,
        "entity_symbol": sample.get("entity_sym"),
        "entity_dso": sample.get("entity_dso"),
        "role": role,
        "context_mechanisms": sorted({x["context_mechanism"]
                                       for x in classified["context_mechanisms"]}),
        "stack_prefix_status": prefix["status"],
        "stack_prefix_fingerprint": prefix["fingerprint"] if prefix["status"] == "strong" else None,
        "stack_depth": prefix["depth_used"],
        "quality_reason": quality_reason,
        "leaf_signature": leaf_sig,
        "top_callstack": [f"{f.get('symbol', '[unknown]')} [{f.get('dso', '[unknown]')}]"
                          for f in stack[:12]],
        "direct_path_matched": bool(direct_path_matched),
    }


def _contributor_key(row):
    return json.dumps({k: row[k] for k in (
        "role", "leaf_dso_class", "leaf_dso", "leaf_symbol", "entity_symbol",
        "entity_dso", "mechanism")}, sort_keys=True, ensure_ascii=False)


def decompose_repeat(samples, *, total_period, reference_mechanisms,
                     reference_fingerprints, reference_leaf_functions,
                     direct_pids, candidate_pids=None,
                     documented_mechanisms=None):
    """Build exact repeat-level R categories from a stream of full native samples."""
    category_period = Counter()
    category_samples = Counter()
    contributor_period = defaultdict(Counter)
    contributor_rows = {}
    contributor_stacks = defaultdict(lambda: defaultdict(Counter))
    diagnostics = defaultdict(Counter)
    residual_period = 0
    roi_period = 0
    for sample in samples:
        period = int(sample["period"])
        roi_period += period
        pid = sample.get("pid")
        match = classify_residual_sample(
            sample,
            direct_path_matched=pid in direct_pids,
            reference_mechanisms=reference_mechanisms,
            reference_fingerprints=reference_fingerprints,
            reference_leaf_functions=reference_leaf_functions)
        if match is None:
            continue
        category = match["category"]
        residual_period += period
        category_period[category] += period
        category_samples[category] += 1
        diagnostics["upper_operation"][match["upper_operation"]] += period
        diagnostics["stack_prefix_quality"][match["stack_prefix_status"]] += period
        diagnostics["quality_reason"][match["quality_reason"]] += period
        if category == "R5":
            diagnostics["R5_reason"][match["quality_reason"]] += period
        diagnostic_mechanism = match["mechanism"]
        if diagnostic_mechanism in (documented_mechanisms or set()) and diagnostic_mechanism not in reference_mechanisms:
            diagnostics["documented_legacy_mechanism_not_sampled_in_reference"][diagnostic_mechanism] += period
        if pid in (candidate_pids or {}):
            grades = sorted({str(x.get("evidence_grade", "candidate_unverified"))
                             for x in candidate_pids[pid]})
            path_grade = ";".join(grades) or "candidate_unverified"
        else:
            path_grade = "no_old_slice_path_candidate"
        diagnostics["path_source_evidence_grade"][path_grade] += period
        contributor_id = _contributor_key(match)
        contributor_period[category][contributor_id] += period
        contributor_rows[contributor_id] = {k: match[k] for k in (
            "role", "leaf_dso_class", "leaf_dso", "leaf_symbol", "entity_symbol",
            "entity_dso", "mechanism", "native_status", "upper_operation",
            "stack_prefix_status", "quality_reason")}
        contributor_stacks[category][contributor_id][tuple(match["top_callstack"])] += period
    if roi_period != total_period:
        raise ValueError(f"raw/profile period mismatch: raw={roi_period} profile={total_period}")
    return {
        "roi_period": roi_period,
        "residual_period": residual_period,
        "category_period": dict(category_period),
        "category_sample_count": dict(category_samples),
        "contributor_period": {k: dict(v) for k, v in contributor_period.items()},
        "contributor_rows": contributor_rows,
        "contributor_stacks": {cat: {key: dict(stacks) for key, stacks in rows.items()}
                                for cat, rows in contributor_stacks.items()},
        "diagnostics": {k: dict(v) for k, v in diagnostics.items()},
    }


def merge_repeat_category_weights(repeats):
    """Period-weight repeat category counts against summed complete ROI."""
    roi_period = sum(row["roi_period"] for row in repeats.values())
    category_period = Counter()
    residual_period = 0
    for row in repeats.values():
        residual_period += row["residual_period"]
        category_period.update(row["category_period"])
    return {"roi_period": roi_period, "residual_period": residual_period,
            "category_period": dict(category_period),
            "roi_share": {cat: category_period.get(cat, 0) / roi_period
                          for cat in CATEGORIES},
            "residual_share": {cat: category_period.get(cat, 0) / max(1, residual_period)
                               for cat in CATEGORIES}}


def _iter_sample_jsonl(path, digest):
    with open(path, "rb") as fh:
        for line in fh:
            digest.update(line)
            yield json.loads(line)


def _raw_index_map():
    index_path = RAW / "index.json"
    index = json.loads(index_path.read_text())
    return sha256_file(index_path), {row["path"]: row for row in index.get("files", [])}


def legacy_sample_reference(profiles, dataset, raw_index):
    """Rebuild sampled reference sets only from path-matched legacy slice scopes.

    This recalculates stack-prefix quality from raw parsed sample stacks, so a
    previously serialized weak inline prefix cannot enter the R1 reference.
    """
    base = comparison.legacy_slice_reference(profiles, dataset)
    control = base["control"]
    fingerprint_set, leaf_set, mechanism_set, slices = set(), set(), set(), set()
    sources = {}
    for repeat in profiles[control]["repeats"]:
        sample_path = RAW / control / repeat / "out" / "samples.jsonl"
        identity_path = RAW / control / repeat / "out" / "monitor" / "identity.jsonl"
        scopes, _direct, _candidates = native.legacy_process_scope_index(identity_path, "xlsx", control)
        digest = hashlib.sha256()
        for sample in _iter_sample_jsonl(sample_path, digest):
            pid = sample.get("pid")
            matches = scopes.get(pid, [])
            if not matches:
                continue
            dso_cls = native.dso_class(str(sample.get("leaf_dso") or "[unknown]"))
            symbol = str(sample.get("leaf_sym") or "")
            classified = native.classify_native_mechanism(
                sample.get("role", "unknown"), dso_cls, symbol, sample.get("stack", []))
            if comparison._specific_native_mechanism(classified["mechanism"]):
                mechanism_set.add(classified["mechanism"])
                slices.update(x["slice_id"] for x in matches)
            if dso_cls != "unknown" and symbol not in UNKNOWN_SYMBOLS:
                leaf_set.add(leaf_signature(symbol, dso_cls))
            prefix = native.stack_prefix_fingerprint(sample.get("stack", []))
            if prefix["status"] == "strong" and dso_cls != "unknown" and symbol not in UNKNOWN_SYMBOLS:
                fingerprint_set.add(prefix["fingerprint"])
        rel_sample = sample_path.relative_to(ROOT).as_posix()
        index_sample = sample_path.relative_to(RAW).as_posix()
        actual = digest.hexdigest()
        expected = raw_index.get(index_sample, {}).get("sha256")
        if expected and actual != expected:
            raise ValueError(f"raw index SHA256 mismatch for legacy reference {rel_sample}")
        sources[repeat] = {"samples_jsonl": rel_sample, "samples_sha256": actual,
                           "raw_index_sha256": expected}
    if slices != base["slices"]:
        raise ValueError(f"legacy reference slice scope mismatch: raw={sorted(slices)} profile={sorted(base['slices'])}")
    return {**base, "mechanisms": mechanism_set, "leaf_functions": leaf_set,
            "stack_prefix_fingerprints": fingerprint_set, "slices": slices,
            "sample_sources": sources,
            "reference_method": "recomputed from raw samples within timestamped/source-matched old-slice process scopes; unknown leaves and weak prefixes excluded"}


def _pct(value):
    percent = 100 * value
    return "<0.01%" if 0 < percent < 0.01 else f"{percent:.2f}%"


def _merged_contributors(repeats, category, total_period):
    periods = Counter()
    rows = {}
    stacks = defaultdict(Counter)
    for repeat in repeats.values():
        for key, period in repeat["contributor_period"].get(category, {}).items():
            periods[key] += period
            rows[key] = repeat["contributor_rows"][key]
            for stack, stack_period in repeat["contributor_stacks"].get(category, {}).get(key, {}).items():
                stacks[key][stack] += stack_period
    eligible = [(key, period) for key, period in periods.items()
                if period / total_period >= DISPLAY_THRESHOLD]
    eligible.sort(key=lambda x: -x[1])
    top = []
    for key, period in eligible[:TOP_N]:
        row = dict(rows[key])
        row.update({"roi_share": period / total_period,
                    "residual_share": period / max(1, sum(periods.values())),
                    "period": period,
                    "representative_stack": list(stacks[key].most_common(1)[0][0]) if stacks[key] else []})
        top.append(row)
    shown = {key for key, _ in eligible[:TOP_N]}
    below = sum(p for p in periods.values() if p / total_period < DISPLAY_THRESHOLD)
    omitted = sum(p for key, p in eligible[TOP_N:])
    return {"top_contributors": top,
            "below_display_threshold_period": below,
            "below_display_threshold_roi_share": below / total_period,
            "below_display_threshold_residual_share": below / max(1, sum(periods.values())),
            "eligible_beyond_top_n_period": omitted,
            "eligible_beyond_top_n_roi_share": omitted / total_period,
            "contributor_count": len(periods),
            "display_threshold_roi_share": DISPLAY_THRESHOLD,
            "top_n": TOP_N}


def _diagnostic_shares(repeats, field, total_period):
    values = Counter()
    for d in repeats.values():
        for name, period in d["diagnostics"].get(field, {}).items():
            values[name] += period
    return {k: {"period": v, "roi_share": v / total_period,
                "residual_share": v / max(1, sum(values.values()))}
            for k, v in values.items()}


def build_residual_report(profiles, coverage, *, datasets=DATASETS,
                          raw_index_sha256=None, raw_index=None):
    """Construct the provenance-rich, mutually exclusive residual decomposition."""
    rows = {}
    reference_cache = {}
    for dataset in datasets:
        profile = profiles[dataset]
        control = comparison.same_environment_control(dataset)
        if control not in reference_cache:
            reference_cache[control] = legacy_sample_reference(profiles, dataset, raw_index or {})
        ref = reference_cache[control]
        repetitions = {}
        sample_sources = {}
        for repeat, data in profile["repeats"].items():
            sample_path = RAW / dataset / repeat / "out" / "samples.jsonl"
            identity_path = RAW / dataset / repeat / "out" / "monitor" / "identity.jsonl"
            scene = "xlsx"
            scopes, _direct, candidates = native.legacy_process_scope_index(identity_path, scene, dataset)
            digest = hashlib.sha256()
            result = decompose_repeat(
                _iter_sample_jsonl(sample_path, digest), total_period=data["total_period"],
                reference_mechanisms=ref["mechanisms"],
                reference_fingerprints=ref["stack_prefix_fingerprints"],
                reference_leaf_functions=ref["leaf_functions"],
                direct_pids=set(scopes), candidate_pids=candidates,
                documented_mechanisms=ref["documented_mechanisms"])
            rel_sample = sample_path.relative_to(ROOT).as_posix()
            rel_identity = identity_path.relative_to(ROOT).as_posix()
            index_sample_path = sample_path.relative_to(RAW).as_posix()
            index_identity_path = identity_path.relative_to(RAW).as_posix()
            indexed = raw_index.get(index_sample_path, {}) if raw_index else {}
            indexed_identity = raw_index.get(index_identity_path, {}) if raw_index else {}
            actual_hash = digest.hexdigest()
            if indexed.get("sha256") and actual_hash != indexed["sha256"]:
                raise ValueError(f"raw index SHA256 mismatch for {rel_sample}")
            result["categories"] = {}
            residual = result["residual_period"]
            for category in CATEGORIES:
                period = result["category_period"].get(category, 0)
                result["categories"][category] = {
                    "label": CATEGORY_LABELS[category],
                    "period": period,
                    "roi_share": period / result["roi_period"],
                    "residual_share": period / max(1, residual),
                    "sample_count": result["category_sample_count"].get(category, 0)}
            result["sample_source"] = {
                "samples_jsonl": rel_sample,
                "samples_sha256": actual_hash,
                "raw_index_sha256": indexed.get("sha256"),
                "identity_jsonl": rel_identity,
                "identity_sha256_from_raw_index": indexed_identity.get("sha256"),
            }
            _REPEAT_PRIVATE[(dataset, repeat)] = {
                "contributor_period": result["contributor_period"],
                "contributor_rows": result["contributor_rows"],
                "contributor_stacks": result["contributor_stacks"],
            }
            # Raw per-sample contributions need not be duplicated in output;
            # retain only bounded top summaries after complete aggregation.
            result.pop("contributor_period")
            result.pop("contributor_rows")
            result.pop("contributor_stacks")
            repetitions[repeat] = result
            sample_sources[repeat] = result["sample_source"]
            print(f"processed {dataset}/{repeat}: {result['roi_period']} sample period; "
                  f"R={result['residual_period'] / result['roi_period']:.3%}", flush=True)

        merged_weight = merge_repeat_category_weights(repetitions)
        combined_total = merged_weight["roi_period"]
        combined_residual = merged_weight["residual_period"]
        # Aggregate complete contributor weights first; threshold is applied only
        # after the repeat join, so a one-repeat-only hotspot is not discarded.
        combined_periods = defaultdict(Counter)
        combined_rows = {}
        combined_stacks = defaultdict(lambda: defaultdict(Counter))
        # Re-read the profile-compatible raw streams is avoided by retaining the
        # compact contributor maps in this private side table below.
        for repeat, data in profile["repeats"].items():
            sample_path = RAW / dataset / repeat / "out" / "samples.jsonl"
            # The actual per-repeat contributor maps are recomputed in the pass
            # above and stored transiently by helper attachment before trimming.
            private = _REPEAT_PRIVATE.pop((dataset, repeat))
            for category, vals in private["contributor_period"].items():
                for key, period in vals.items():
                    combined_periods[category][key] += period
                    combined_rows[key] = private["contributor_rows"][key]
            for category, groups in private["contributor_stacks"].items():
                for key, stack_counts in groups.items():
                    combined_stacks[category][key].update(stack_counts)

        merged_categories = {}
        for category in CATEGORIES:
            period = merged_weight["category_period"].get(category, 0)
            assert abs(period / combined_total - merged_weight["roi_share"][category]) < 1e-12
            assert abs(period / max(1, combined_residual) - merged_weight["residual_share"][category]) < 1e-12
            merged_categories[category] = {
                "label": CATEGORY_LABELS[category],
                "period": period,
                "roi_share": period / combined_total,
                "residual_share": period / max(1, combined_residual),
                "sample_count": sum(x["category_sample_count"].get(category, 0)
                                    for x in repetitions.values()),
                "per_repeat": {rep: repetitions[rep]["categories"][category]
                               for rep in repetitions},
                "contributors": _merged_contributors_from_maps(
                    combined_periods.get(category, Counter()), combined_rows,
                    combined_stacks.get(category, {}), combined_total,
                    max(1, combined_residual)),
            }
        assert abs(sum(x["period"] for x in merged_categories.values()) - combined_residual) <= 1
        coverage_residual = coverage[dataset]["merged"]["uncovered_share"]
        computed_residual_share = combined_residual / combined_total
        if abs(computed_residual_share - coverage_residual) > 2e-8:
            raise ValueError(f"residual mismatch {dataset}: raw={computed_residual_share} coverage={coverage_residual}")
        rows[dataset] = {
            "same_environment_control": ref["control"],
            "reference_slice_ids": sorted(ref["slices"]),
            "reference_mechanism_count": len(ref["mechanisms"]),
            "reference_leaf_function_count": len(ref["leaf_functions"]),
            "reference_stack_prefix_count": len(ref["stack_prefix_fingerprints"]),
            "reference_sample_sources": ref["sample_sources"],
            "reference_method": ref["reference_method"],
            "roi_period": combined_total,
            "residual_period": combined_residual,
            "coverage_residual_share": coverage_residual,
            "computed_residual_share": computed_residual_share,
            "per_repeat": {rep: {
                "roi_period": value["roi_period"],
                "residual_period": value["residual_period"],
                "residual_roi_share": value["residual_period"] / value["roi_period"],
                "coverage_residual_share": coverage[dataset]["per_repeat"][rep]["uncovered_share"],
                "categories": value["categories"],
                "diagnostics": value["diagnostics"],
                "sample_source": value["sample_source"]}
                for rep, value in repetitions.items()},
            "categories": merged_categories,
            "diagnostics": {
                field: _diagnostic_shares(repetitions, field, combined_total)
                for field in ("upper_operation", "stack_prefix_quality", "quality_reason",
                              "path_source_evidence_grade",
                              "documented_legacy_mechanism_not_sampled_in_reference",
                              "R5_reason")},
            "interpretation": "R is outside the unchanged union of actual path match A and old-selected-slice sampled native mechanism B; it is not proven uncovered/new computation.",
        }
    return rows


def _merged_contributors_from_maps(periods, rows, stacks, total_period, residual_period):
    all_period = sum(periods.values())
    ranked = sorted(periods.items(), key=lambda item: -item[1])
    eligible = [(key, period) for key, period in periods.items()
                if period / total_period >= DISPLAY_THRESHOLD]
    eligible.sort(key=lambda item: -item[1])
    contributors = []
    for key, period in eligible[:TOP_N]:
        row = dict(rows[key])
        row.update({"period": period, "roi_share": period / total_period,
                    "residual_share": period / max(1, residual_period),
                    "representative_stack": list(stacks.get(key, Counter()).most_common(1)[0][0])
                    if stacks.get(key) else []})
        contributors.append(row)
    largest_all = []
    for key, period in ranked[:5]:
        row = dict(rows[key])
        row.update({"period": period, "roi_share": period / total_period,
                    "residual_share": period / max(1, residual_period),
                    "representative_stack": list(stacks.get(key, Counter()).most_common(1)[0][0])
                    if stacks.get(key) else []})
        largest_all.append(row)
    below = sum(period for period in periods.values()
                if period / total_period < DISPLAY_THRESHOLD)
    omitted = sum(period for key, period in eligible[TOP_N:])
    return {"top_contributors": contributors,
            "largest_contributors_all": largest_all,
            "contributor_count": len(periods),
            "display_threshold_roi_share": DISPLAY_THRESHOLD,
            "below_threshold_period": below,
            "below_threshold_roi_share": below / total_period,
            "below_threshold_residual_share": below / max(1, residual_period),
            "eligible_beyond_top_n_period": omitted,
            "eligible_beyond_top_n_roi_share": omitted / total_period,
            "all_contributors_period": all_period,
            "all_contributors_roi_share": all_period / total_period}


_REPEAT_PRIVATE = {}


def render_report(result, baseline, method_sha256, dependency_hashes):
    lines = ["# Retail / Manufacturing / HR 未确认覆盖余量分解", "",
             "本报告解释既有路径∪机制覆盖率的余量，不改写 coverage.json。A 是样本所属进程实际匹配旧选中切片路径，B 是叶机制在旧选中切片参考采样中出现；R = ROI 样本集合减去 A∪B。各主类别按 R1→R5 互斥分配，类别和都以完整 workload ROI cycles:u period 为分母。", "",
             f"基线 coverage.json SHA256：`{baseline['files']['processed/coverage.json']}`。分解代码 SHA256：`{method_sha256}`；当前机制/栈指纹代码 SHA256：`{dependency_hashes['scripts/build_profiles.py']}`。", "",
             "阈值为完整 ROI 的 0.5%，先跨完整重复合并同一贡献项再筛选。表中阈值以下权重和前 10 项以外的合格权重单独列出，全部纳入类别总和。栈指纹沿用 stack-prefix-v1：最多 8 帧、至少 4 帧、无未知帧，符号去偏移，DSO 归并为类别。", ""]
    for dataset, ds in result.items():
        lines += [f"## {dataset}", "",
                  f"旧参考：{ds['same_environment_control']}；切片 {', '.join(ds['reference_slice_ids']) or '无'}。ROI period `{ds['roi_period']}`；R `{_pct(ds['computed_residual_share'])}`，原 coverage 余量 `{_pct(ds['coverage_residual_share'])}`。", "",
                  "| 余量类别 | 占完整 ROI | 占余量 | r1 / r2（占各自 ROI） | 主要进程/函数（合并权重） | 证据边界 |",
                  "|---|---:|---:|---|---|---|"]
        for category in CATEGORIES:
            row = ds["categories"][category]
            reps = row["per_repeat"]
            rep_text = " / ".join(f"{rep} {_pct(reps[rep]['roi_share'])}"
                                  for rep in sorted(reps))
            contributors = row["contributors"]
            top = contributors["top_contributors"]
            displayed = top[:3] if top else contributors["largest_contributors_all"][:3]
            top_text = "<br>".join(
                f"{x['role']} · {x['leaf_symbol']} ({_pct(x['roi_share'])})"
                for x in displayed) or "—"
            if not top and displayed:
                top_text += "<br>（均低于阈值，计入阈值余量）"
            top_text += (f"<br>阈值以下 {_pct(contributors['below_threshold_residual_share'])}; "
                         f"前十以外 {_pct(contributors['eligible_beyond_top_n_roi_share'])}")
            evidence = {
                "R1": "栈前缀相等仅证明归一化前缀相同；原覆盖定义不采用指纹，因此仍留在余量。",
                "R2": "只支持叶函数和 DSO 类别相同；不证明栈上下文、业务操作或算法相同。",
                "R3": "采样点机制具体，但未在旧选中切片参考样本中观察到；不是旧切片定义明确排除。",
                "R4": "符号/DSO 已解析，但机制规则或上下文不足以细分；不是符号解析失败。",
                "R5": "未知或质量受限样本；不作为新增机制证据。"}[category]
            lines.append(f"| {category} {CATEGORY_LABELS[category]}（{row['sample_count']} samples） | {_pct(row['roi_share'])} | {_pct(row['residual_share'])} | {rep_text} | {top_text} | {evidence} |")
        lines += ["", "### 重叠诊断（不可与主类别相加）", "",
                  "上层操作、指纹质量、路径来源候选和具体质量原因按 ROI period 统计；同一样本可同时出现在多个诊断项。", ""]
        for field, title in (("upper_operation", "上层业务操作"),
                             ("stack_prefix_quality", "指纹质量"),
                             ("quality_reason", "质量原因"),
                             ("R5_reason", "R5 互斥原因"),
                             ("path_source_evidence_grade", "路径来源证据")):
            vals = sorted(ds["diagnostics"][field].items(), key=lambda x: -x[1]["period"])
            lines.append(f"- **{title}**：" + ("；".join(f"{k} {_pct(v['roi_share'])}" for k, v in vals) or "无"))
        lines += ["", "证据文件：" + "; ".join(
            f"`{rep['sample_source']['samples_jsonl']}` (SHA256 `{rep['sample_source']['samples_sha256']}`)"
            for rep in ds["per_repeat"].values()) + "; 旧切片参考：" + "; ".join(
            f"`{src['samples_jsonl']}` (SHA256 `{src['samples_sha256']}`)"
            for src in ds["reference_sample_sources"].values()), ""]
    lines += ["## 解释边界", "",
              "共同函数、栈前缀或原生机制分别只支持相应层级的相似性，不能推出相同 Python 业务操作、相同算法或相同优化收益。R3 表示旧选中切片采样中未观察到该机制；它既不证明旧切片定义排除该机制，也不证明该机制是新算法。R5 才是当前采样无法给出足够分类证据的部分。未确认覆盖不等于已证明未覆盖，也不单独证明旧用例缺乏代表性。", ""]
    return "\n".join(lines)


def freeze_baseline():
    paths = {
        "processed/coverage.json": PROCESSED / "coverage.json",
        "processed/all-profiles.json": PROCESSED / "all-profiles.json",
        "config/mechanism-taxonomy.json": ROOT / "config" / "mechanism-taxonomy.json",
        "legacy/legacy-slices.json": ROOT / "legacy" / "legacy-slices.json",
        "config/run-plan.json": ROOT / "config" / "run-plan.json",
        "raw/index.json": RAW / "index.json",
    }
    code_paths = {
        "scripts/analyze_comparison.py": ROOT / "scripts" / "analyze_comparison.py",
        "scripts/build_profiles.py": ROOT / "scripts" / "build_profiles.py",
    }
    target = METADATA / "unconfirmed-residual-baseline.json"
    current = {key: sha256_file(path) for key, path in paths.items()}
    current_code = {key: sha256_file(path) for key, path in code_paths.items()}
    if target.exists():
        saved = json.loads(target.read_text())
        # The original baseline manifest froze the analysis sources alongside
        # the data. Move those immutable historical code hashes into their own
        # field so a documented quality fix can be recorded without changing
        # the coverage/profile baseline hashes.
        saved_code = saved.get("analysis_code_sha256", {})
        for key in code_paths:
            if key not in saved_code and key in saved.get("files", {}):
                saved_code[key] = saved["files"].pop(key)
        if saved.get("files") != current:
            raise ValueError("frozen residual baseline changed; create a new analysis version rather than silently updating it")
        saved["analysis_code_sha256"] = saved_code
        saved["current_analysis_code_sha256"] = current_code
        target.write_text(json.dumps(saved, indent=2, ensure_ascii=False) + "\n")
        return saved
    coverage = json.loads((PROCESSED / "coverage.json").read_text())
    baseline = {
        "schema_version": "unconfirmed-residual-baseline-v1",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "coverage_definition": "A = sample in an identity/source-matched old selected-slice execution scope; B = leaf native mechanism observed in source-matched old selected-slice samples; coverage = A union B; residual R = not(A union B), denominator = complete ROI cycles:u sample period",
        "datasets": {cid: {"coverage_union_share": coverage[cid]["merged"]["coverage_union_share"],
                           "uncovered_share": coverage[cid]["merged"]["uncovered_share"]}
                     for cid in DATASETS},
        "files": current,
        "analysis_code_sha256": current_code,
        "current_analysis_code_sha256": current_code,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(baseline, indent=2, ensure_ascii=False) + "\n")
    return baseline


def main():
    baseline = freeze_baseline()
    profiles = json.loads((PROCESSED / "all-profiles.json").read_text())
    coverage = json.loads((PROCESSED / "coverage.json").read_text())
    raw_index_sha, raw_index = _raw_index_map()
    if raw_index_sha != baseline["files"]["raw/index.json"]:
        raise ValueError("raw index differs from frozen baseline")
    result = build_residual_report(profiles, coverage, raw_index_sha256=raw_index_sha,
                                   raw_index=raw_index)
    source_path = Path(__file__).resolve()
    result_doc = {
        "schema_version": "unconfirmed-residual-decomposition-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_manifest_sha256": sha256_file(METADATA / "unconfirmed-residual-baseline.json"),
        "analysis_code_sha256": sha256_file(source_path),
        "current_analysis_dependencies_sha256": {
            "scripts/analyze_comparison.py": sha256_file(ROOT / "scripts" / "analyze_comparison.py"),
            "scripts/build_profiles.py": sha256_file(ROOT / "scripts" / "build_profiles.py"),
        },
        "raw_index_sha256": raw_index_sha,
        "coverage_definition": baseline["coverage_definition"],
        "category_priority": ["R1", "R2", "R3", "R4", "R5"],
        "category_rule": "Exactly one category per residual sample; path A or mechanism B samples are excluded first. Strong prefix, then resolved leaf, then specific mechanism, then resolved-but-broad, then insufficient evidence.",
        "display_threshold": {"roi_share": DISPLAY_THRESHOLD, "top_n": TOP_N,
                              "application": "combine full per-repeat contributor weights first; then display threshold"},
        "baseline": baseline["datasets"],
        "datasets": result,
    }
    out_path = PROCESSED / "unconfirmed-residual-decomposition.json"
    out_path.write_text(json.dumps(result_doc, indent=2, ensure_ascii=False) + "\n")
    report_path = REPORTS / "unconfirmed-residual-report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(result, baseline, result_doc["analysis_code_sha256"],
                                         result_doc["current_analysis_dependencies_sha256"]))
    for dataset, row in result.items():
        print(f"{dataset}: R={_pct(row['computed_residual_share'])} categories=" +
              ", ".join(f"{cat}={_pct(row['categories'][cat]['roi_share'])}"
                         for cat in CATEGORIES))
    print(f"wrote {out_path} and {report_path}")


if __name__ == "__main__":
    main()
