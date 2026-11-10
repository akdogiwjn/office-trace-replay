"""Independent expectation generator for scaled Excel 013 variants.

Reads the frozen ``vendors.json`` prepared material and derives the full public
workbook structure expected after the builder applies the correction log:
vendor register facts, weighted scoring, price-normalization scores, the COI
log, the top-3 award recommendation, the evaluation summary formulas with their
cached values, the named range and both data-validation ranges. It deliberately
shares NO value computation with the in-replay builder (which only writes Excel
formula strings and applies corrections read out of the source workbook).
"""
from __future__ import annotations

from pathlib import Path

from .. import common
from . import synth

WEIGHTS = synth.WEIGHTS
REQUIREMENT_IDS = [req_id for req_id, _, _ in synth.REQUIREMENTS]


def weighted_score(vendor: dict) -> float:
    scores = vendor["scores"]
    return sum(weight * scores[req_id] for req_id, weight in zip(REQUIREMENT_IDS, WEIGHTS))


def compute(vendors_path: Path) -> dict:
    data = common.load_json(vendors_path)
    vendors = data["vendors"]
    n = len(vendors)
    last = n + 1
    scoring_last = 3 * n + 1

    records = []
    for vendor in vendors:
        scores = [vendor["scores"][req_id] for req_id in REQUIREMENT_IDS]
        records.append({
            "id": vendor["id"],
            "name": vendor["name"],
            "contact": vendor["contact"],
            "evaluator": vendor["evaluator"],
            "status": vendor["status"],
            "corrected_price": vendor["corrected_price"],
            "scores": dict(zip(REQUIREMENT_IDS, scores)),
            "technical_score": weighted_score(vendor),
            "price_score": None,  # computed below once the lowest price is known
        })

    lowest_price = min(r["corrected_price"] for r in records)
    for record in records:
        record["price_score"] = lowest_price / record["corrected_price"] * 100.0

    # Parent semantics: Evaluation Summary B6 is the plain average of every raw
    # requirement score in the Requirements Scoring sheet (AVERAGE over all 3N
    # score cells). The weighted per-vendor technical score is used only for the
    # award ranking, not for the published average.
    raw_scores = [score for r in records for score in r["scores"].values()]
    average_score = sum(raw_scores) / len(raw_scores)
    responsive = sum(1 for r in records if r["status"] == "Responsive")

    ranked = sorted(records, key=lambda r: (-r["technical_score"], r["id"]))
    award = [
        {
            "rank": index + 1,
            "vendor_id": ranked[index]["id"],
            "vendor_name": ranked[index]["name"],
            "status": "Recommend award" if index == 0 else "Reserve",
        }
        for index in range(3)
    ]

    coi_rows = [
        {
            "log_id": f"COI-{index + 1:03d}",
            "vendor_id": record["id"],
            "reviewer": "Leah Moore",
            "disclosure": "No conflict disclosed",
            "status": "Cleared",
        }
        for index, record in enumerate(records)
    ]

    dv_rows = [
        ["Named range", f"VendorIDs = Vendor Register A2:A{last}"],
        ["Scoring validation", f"Requirements Scoring B2:B{scoring_last} uses =VendorIDs"],
        ["Conflict validation", f"Conflict-of-Interest Log B2:B{last} uses =VendorIDs"],
        ["Debrief links", f"Debrief Register D2:D{last} uses mailto hyperlinks"],
    ]

    forbidden = [
        "DRAFT", "PRIVATE", "legal hold", "personal phone",
        "vendor protest strategy", "private negotiation", "do not release",
        "evaluator disagreement",
        "Correction_Log_INTERNAL", "Raw Vendor Data_INTERNAL",
        "Requirements Scratch_INTERNAL", "Price_Scratch_INTERNAL",
    ]
    # Correction-key old values are NOT forbidden text: corrected values such as
    # "Responsive" and "Leah Moore" contain "Responsiv" / "Leah Moor" as
    # substrings. Those corrections are verified by the full field comparisons.
    for index, vendor in enumerate(vendors):
        wrong = f"VND-{index + 1:03d}x"
        forbidden.append(wrong)

    return {
        "schema": "docops-scaling-expectation-v1",
        "variant_task_id": data["variant_task_id"],
        "kind": "xlsx",
        "n": n,
        "vendor_ids": [r["id"] for r in records],
        "records": records,
        "scoring_rows": [
            {
                "req_id": req_id,
                "vendor_id": record["id"],
                "requirement": requirement,
                "weight": weight,
                "score": record["scores"][req_id],
            }
            for record in records
            for req_id, requirement, weight in synth.REQUIREMENTS
        ],
        "price_scores": [r["price_score"] for r in records],
        "coi_rows": coi_rows,
        "award": award,
        "summary": {
            "responsive_vendors": responsive,
            "recommended_vendor": ranked[0]["name"],
            "lowest_corrected_price": lowest_price,
            "average_technical_score": average_score,
        },
        "summary_formulas": {
            "B3": f"=COUNTIF('Vendor Register'!E2:E{last},\"Responsive\")",
            "B4": "='Award Recommendation'!B2",
            "B5": f"=MIN('Price Normalization'!C2:C{last})",
            "B6": f"=AVERAGE('Requirements Scoring'!E2:E{scoring_last})",
        },
        "price_formula_row1": f"=MIN($C$2:$C${last})/C2*100",
        "price_formula_last": f"=MIN($C$2:$C${last})/C{last}*100",
        "named_range": f"'Vendor Register'!$A$2:$A${last}",
        "data_validations": {
            "Requirements Scoring": f"B2:B{scoring_last}",
            "Conflict-of-Interest Log": f"B2:B{last}",
        },
        "table_ranges": {
            "Evaluation Summary": "A3:B6",
            "Vendor Register": f"A1:E{last}",
            "Requirements Scoring": f"A1:E{scoring_last}",
            "Price Normalization": f"A1:D{last}",
            "Conflict-of-Interest Log": f"A1:E{last}",
            "Award Recommendation": "A1:D4",
            "Debrief Register": f"A1:D{last}",
            "Data Validation Guide": "A1:B5",
            "Publication Style Guide": "A1:B7",
            "Appendix Index": "A1:D5",
        },
        "register_range_end": last,
        "scoring_range_end": scoring_last,
        "cached_cells": n + 4,
        "formula_count": n + 4,
        "forbidden_phrases": forbidden,
        "tabs": synth.TAB_COLORS,
    }


def write_expected(variant_task_id: str, vendors_path: Path, expected_path: Path) -> dict:
    result = compute(vendors_path)
    result["variant_task_id"] = variant_task_id
    common.write_json(expected_path, result)
    return result
