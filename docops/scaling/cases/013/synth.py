"""Synthetic Excel 013 inputs: scaled procurement bid evaluation release workbooks.

Produces a synthetic internal source workbook and a frozen ``vendors.json``
material declaration. Every vendor row in the synthetic source workbook carries
a deliberately wrong internal value (raw vendor id with an ``x`` suffix, a
misspelled evaluator, a draft status spelling, and a wrong price) together with
a matching ``Correction_Log_INTERNAL`` entry, so the parameterized builder must
genuinely read the source workbook and apply the correction log before it can
rebuild the ten public sheets. The expected oracle reads only ``vendors.json``
and shares no value computation with the builder.
"""
from __future__ import annotations

import datetime
import os
import random
import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .. import common

# Exact parent-task constants (frozen public behaviour).
SHEET_ORDER = [
    "Evaluation Summary",
    "Vendor Register",
    "Requirements Scoring",
    "Price Normalization",
    "Conflict-of-Interest Log",
    "Award Recommendation",
    "Debrief Register",
    "Data Validation Guide",
    "Publication Style Guide",
    "Appendix Index",
]

TAB_COLORS = {
    "Evaluation Summary": "4F2D7F",
    "Vendor Register": "70AD47",
    "Requirements Scoring": "4472C4",
    "Price Normalization": "ED7D31",
    "Conflict-of-Interest Log": "C00000",
    "Award Recommendation": "0F6B6E",
    "Debrief Register": "7030A0",
    "Data Validation Guide": "5B9BD5",
    "Publication Style Guide": "4F2D7F",
    "Appendix Index": "4472C4",
}

REQUIREMENTS = [
    ("REQ-01", "Implementation plan", 0.2),
    ("REQ-02", "Security controls", 0.3),
    ("REQ-03", "Support model", 0.5),
]
WEIGHTS = [weight for _, _, weight in REQUIREMENTS]

FIRST_NAMES = ["Ava", "Leo", "Mia", "Noah", "Zoe", "Eli", "Nora", "Owen",
               "Ivy", "Kai", "Ruth", "Sam", "Wren", "Felix", "June", "Theo",
               "Vera", "Hugo", "Lena", "Omar", "Tess", "Axel", "Iris", "Mina",
               "Callum"]
LAST_NAMES = ["Kim", "Cheng", "Patel", "Rossi", "Novak", "Ito", "Sato",
              "Larsen", "Mendes", "Fischer", "Owens", "Silva", "Thorne",
              "Wu", "Park", "Ali", "Bauer", "Reed", "Grant", "Perez",
              "Okafor", "Nguyen", "Romano", "Banks", "Holt", "Vega",
              "Marsh", "Quinn", "Sloan", "Mercer", "Doyle", "Cruz", "Blake",
              "Stone", "Vaughn", "Pace", "Riley", "Dunn", "Hale", "Boyle"]

# Global correction pairs, modelled on the frozen parent Correction_Log.
GLOBAL_CORRECTIONS = [
    ("Leah Moor", "Leah Moore"),
    ("Responsiv", "Responsive"),
    ("Nonresponsiv", "Nonresponsive"),
]
CORRECTION_PRIVATE = [
    "legal hold",
    "vendor protest strategy",
    "personal phone",
    "private negotiation",
    "do not release",
    "evaluator disagreement",
]


def _fmt_price(value: int) -> str:
    return f"${value:,.0f}"


def _vendor_name(index: int) -> str:
    first = FIRST_NAMES[index % len(FIRST_NAMES)]
    last = LAST_NAMES[(index // len(FIRST_NAMES)) % len(LAST_NAMES)]
    if len(FIRST_NAMES) * len(LAST_NAMES) < index + 1:
        raise ValueError("name pool exhausted")
    return f"{first} {last} Systems" if index % 5 else f"{first} {last} Works"


def make_vendors(n: int, rng: random.Random) -> list[dict]:
    """Deterministic per-variant vendor declaration (frozen business facts).

    ``corrected_price`` values are globally unique so the correction-log price
    keys (``$X,XXX,XXX`` formatted strings) cannot cross-match any other vendor.
    """
    if n < 1:
        raise ValueError("vendor count must be >= 1")
    prices = rng.sample(range(1_100_000, 2_400_000), n)
    assert len(prices) == len(set(prices)) == n
    vendors = []
    for index in range(n):
        vid = f"VND-{index + 1:03d}"
        status = "Responsive" if rng.random() < 0.7 else "Nonresponsive"
        scores = {req_id: rng.randint(60, 99) for req_id, _, _ in REQUIREMENTS}
        contact_first = FIRST_NAMES[(index + 7) % len(FIRST_NAMES)]
        contact_last = LAST_NAMES[((index + 7) // len(FIRST_NAMES)) % len(LAST_NAMES)]
        vendors.append({
            "id": vid,
            "name": _vendor_name(index),
            "contact": f"{contact_first} {contact_last}",
            "evaluator": "Leah Moore",
            "status": status,
            "corrected_price": prices[index],
            "scores": scores,
        })
    assert len({v["name"] for v in vendors}) == n
    assert len({v["contact"] for v in vendors}) == n
    return vendors


def corrections_for(n: int) -> list[tuple[str, str, str]]:
    """Global correction-log rows: [Old, New, PRIVATE].

    The three global string corrections (evaluator and status spellings) plus
    one vendor-id correction per vendor. Each old value is globally unique
    because vendor ids are unique.
    """
    rows = [
        ("Leah Moor", "Leah Moore", "personal phone"),
        ("Responsiv", "Responsive", "do not release"),
        ("Nonresponsiv", "Nonresponsive", "do not release"),
    ]
    for index in range(n):
        vid = f"VND-{index + 1:03d}"
        rows.append((f"{vid}x", vid, "legal hold"))
    return rows


def price_corrections_for(vendors: list[dict]) -> list[tuple[str, str, str]]:
    rows = []
    for index, vendor in enumerate(vendors):
        wrong = vendor["corrected_price"] + 5_000
        rows.append((_fmt_price(wrong), _fmt_price(vendor["corrected_price"]),
                     "private negotiation"))
    return rows


def _raw_vendor_rows(vendors: list[dict]) -> list[list]:
    """Source-workbook raw rows carrying the values the correction log fixes."""
    rows = []
    for index, vendor in enumerate(vendors):
        wrong_status = ("Responsiv" if vendor["status"] == "Responsive"
                        else "Nonresponsiv")
        rows.append([
            f"{vendor['id']}x",
            vendor["name"],
            vendor["contact"],
            "Leah Moor",
            wrong_status,
            vendor["corrected_price"] + 5_000,
        ])
    return rows


def _raw_requirement_rows(vendors: list[dict]) -> list[list]:
    rows = []
    for vendor in vendors:
        for req_id, req_name, weight in REQUIREMENTS:
            rows.append([f"{vendor['id']}x", req_id, req_name, weight,
                         vendor["scores"][req_id]])
    return rows


def apply_corrections(value, corrections):
    """Same correction application semantics as the frozen parent script."""
    if isinstance(value, (int, float)):
        formatted = _fmt_price(int(value))
        for old, new, *_ in corrections:
            if formatted == str(old):
                return float(str(new).replace("$", "").replace(",", ""))
        return value
    corrected = str(value)
    for old, new, *_ in corrections:
        corrected = re.sub(
            rf"(?<!\w){re.escape(str(old))}(?!\w)",
            lambda _: str(new),
            corrected,
        )
    return corrected


def write_vendors_json(variant_id: str, vendors: list[dict],
                       input_name: str, out_dir: Path) -> Path:
    data = {
        "schema": "docops-scaling-vendors-v1",
        "variant_task_id": variant_id,
        "seed": common.VARIANTS[variant_id]["seed"],
        "input_path": f"/root/{input_name}",
        "vendors": vendors,
    }
    common.write_json(out_dir / "vendors.json", data)
    return out_dir / "vendors.json"


def write_input_workbook(vendors: list[dict], path: Path) -> None:
    corrections = corrections_for(len(vendors)) + price_corrections_for(vendors)

    wb = Workbook()
    wb.properties.created = datetime.datetime(2026, 1, 1, 0, 0, 0)
    wb.properties.modified = datetime.datetime(2026, 1, 1, 0, 0, 0)
    wb.properties.creator = "DocOps synthetic scale generator"

    draft = wb.active
    draft.title = "Evaluation_DRAFT_PRIVATE"
    draft.append(["Vendor ID", "Vendor", "Evaluator", "Status", "PRIVATE"])
    for vendor in vendors[:2]:
        draft.append([vendor["id"], vendor["name"], "Leah Moor",
                      "Responsiv", "evaluator disagreement"])

    scratch = wb.create_sheet("Price_Scratch_INTERNAL")
    scratch.append(["Vendor", "Price", "PRIVATE"])
    for vendor in vendors[:2]:
        scratch.append([vendor["name"], vendor["corrected_price"] + 5_000,
                        "private negotiation"])

    corr = wb.create_sheet("Correction_Log_INTERNAL")
    corr.append(["Old", "New", "PRIVATE"])
    for row in corrections:
        corr.append(row)

    hold = wb.create_sheet("legal hold")
    hold.append(["PRIVATE", "legal hold", "scoring rumor"])
    hold.append(["do not release", "evaluator disagreement", "personal phone"])

    raw = wb.create_sheet("Raw Vendor Data_INTERNAL")
    raw.append(["Raw Vendor ID", "Vendor Name", "Contact", "Evaluator",
                "Status", "Raw Corrected Price"])
    for row in _raw_vendor_rows(vendors):
        raw.append(row)
    raw.freeze_panes = "A2"

    req = wb.create_sheet("Requirements Scratch_INTERNAL")
    req.append(["Raw Vendor ID", "Requirement ID", "Requirement", "Weight", "Score"])
    for row in _raw_requirement_rows(vendors):
        req.append(row)
    req.freeze_panes = "A2"

    _save_deterministic(wb, path)


def _save_deterministic(wb, path):
    import tempfile
    import zipfile

    fixed = datetime.datetime(2026, 1, 1, 0, 0, 0).isoformat() + "Z"
    temp_fd, temp_name = tempfile.mkstemp(suffix=".xlsx", dir=path.parent)
    os.close(temp_fd)
    wb.save(temp_name)
    try:

        def core_fix(data):
            return re.sub(
                rb"(<dcterms:modified\b[^>]*>)[^<]*(</dcterms:modified>)",
                rf"\g<1>{fixed}</dcterms:modified>".encode(),
                data,
            )

        common.deterministic_zip(temp_name, path, transform={"docProps/core.xml": core_fix})
    finally:
        Path(temp_name).unlink(missing_ok=True)


def generate(variant_id: str, out_dir: Path, write_raw_records: bool = True) -> dict:
    v = common.VARIANTS[variant_id]
    n = v["scale"]["vendors"]
    seed = v["seed"]
    rng = random.Random(seed)
    vendors = make_vendors(n, rng)

    out_dir.mkdir(parents=True, exist_ok=True)
    input_name = (
        f"docops_v2_l3_013_xlsx_procurement_bid_evaluation_release_input_"
        f"{v['output_suffix']}.xlsx"
    )
    input_path = out_dir / input_name
    write_input_workbook(vendors, input_path)
    vendors_path = write_vendors_json(variant_id, vendors, input_name, out_dir)

    if write_raw_records:
        common.write_json(
            out_dir / "raw_records.json",
            {"schema": "docops-scaling-raw-records-v1",
             "variant_task_id": variant_id,
             "records": vendors},
        )

    responsive = sum(1 for ven in vendors if ven["status"] == "Responsive")
    prices = [ven["corrected_price"] for ven in vendors]
    lowest = min(prices)
    avg_score = (sum(ven["scores"][rid] for ven in vendors for rid, _, _ in REQUIREMENTS)
                 / (3 * n))
    top = sorted(
        vendors,
        key=lambda ven: (-weighted_score(ven), ven["id"]),
    )[:3]

    scale_metadata = {
        "vendors": n,
        "vendor_ids": [ven["id"] for ven in vendors],
        "source_vendor_rows": n,
        "source_requirements_rows": 3 * n,
        "source_correction_rows": len(corrections_for(n)) + len(price_corrections_for(vendors)),
        "register_rows": n,
        "scoring_rows": 3 * n,
        "price_rows": n,
        "coi_rows": n,
        "award_rows": 3,
        "debrief_rows": n,
        "price_formula_cells": n,
        "summary_formula_cells": 4,
        "formula_count": n + 4,
        "cached_check_cells": n + 4,
        "named_range": f"'Vendor Register'!$A$2:$A${n + 1}",
        "scoring_dv_range": f"B2:B{3 * n + 1}",
        "coi_dv_range": f"B2:B{n + 1}",
        "parameterized_ranges": [
            f"'Vendor Register'!$A$2:$A${n + 1} (VendorIDs)",
            f"'Requirements Scoring'!$B$2:$B${3 * n + 1} (data validation)",
            f"'Conflict-of-Interest Log'!$B$2:$B${n + 1} (data validation)",
            f"'Price Normalization'!$C$2:$C${n + 1}",
            f"'Price Normalization'!$D$2:$D${n + 1}",
            f"'Evaluation Summary'!$B$3:$B$6",
        ],
        "render_scope": (
            "all rendered pages at 110 dpi (one PNG per page) tiled into 2x5 "
            "contact sheets; page count is decided by real LibreOffice layout "
            "(landscape, fit-to-width=1, height unconstrained)"
        ),
        "expected_render_images": "one PNG per rendered page plus contact sheets",
        "preserved_parent_behavior": [
            "ten-sheet order, tab colors, header/body styles, freeze panes, "
            "auto filters, landscape fit-to-width printing",
            "Correction_Log application semantics and internal-sheet removal",
            "price normalization, top-3 award, summary formulas and debrief "
            "mailto hyperlinks",
        ],
        "changed_parent_behavior": [
            "every fixed range, formula range, named range, data-validation "
            "range and dropdown is sized from the actual vendor count instead "
            "of the original five vendors",
        ],
        "responsive_count": responsive,
        "lowest_price": lowest,
        "average_score": avg_score,
        "first_vendor": vendors[0],
        "middle_vendor": vendors[n // 2],
        "last_vendor": vendors[-1],
        "top3_award": [ven["id"] for ven in top],
        "input_bytes": input_path.stat().st_size,
        "input_sha256": common.sha256_file(input_path),
        "vendors_json_sha256": common.sha256_file(vendors_path),
        "seed": seed,
    }

    meta = common.default_task_metadata(variant_id)
    meta["scale_metadata"] = scale_metadata
    meta["input_path"] = f"/root/{input_name}"
    meta["output_path"] = (
        f"/root/submission/"
        f"docops_v2_l3_013_xlsx_procurement_bid_evaluation_release_output_"
        f"{v['output_suffix']}.xlsx"
    )
    meta["modified_workflow"] = [
        "01 build: frozen parent stage order preserved (read Correction_Log "
        "from the synthetic source workbook, apply corrections, remove internal "
        "sheets, rebuild the ten public sheets); every fixed range / named "
        "range / data-validation range / summary formula / dropdown is sized "
        "from the actual vendor count read out of the source workbook",
        "02 recalc: unchanged recalc.py (LibreOffice calculates all formulas "
        "and caches values)",
        "03 verify: dynamic validator covers all N vendors, all 3N scoring "
        "rows, all N price-normalization formulas, the top-3 award rows, the "
        "summary formulas with their cached values, the VendorIDs named range, "
        "both data-validation ranges, forbidden text and zip integrity",
    ]
    meta["measurement_scope"] = (
        "Scales the number of vendors that must be read from the synthetic "
        "source workbook, corrected via the correction log, and rebuilt across "
        "the ten public sheets (register, scoring, price normalization, COI "
        "log, award recommendation, debrief register and summary). The size "
        "drives formula count, named-range/data-validation extents, recalc "
        "cost and validation coverage; page rendering is decided by real "
        "LibreOffice layout (fit-to-width keeps one sheet page wide, height "
        "unconstrained)."
    )
    common.write_json(out_dir / "task_metadata.json", meta)
    (out_dir / "instruction.md").write_text(instruction_md(meta), encoding="utf-8")
    (out_dir / "original_task_description.txt").write_text(
        original_description(meta), encoding="utf-8")

    return {
        "input": input_path,
        "vendors": vendors_path,
        "task_metadata": out_dir / "task_metadata.json",
        "scale_metadata": scale_metadata,
    }


def weighted_score(vendor: dict) -> float:
    scores = vendor["scores"]
    return sum(weight * scores[req_id] for req_id, _, weight in REQUIREMENTS)


def instruction_md(meta: dict) -> str:
    v = common.VARIANTS[meta["variant_task_id"]]
    sm = meta["scale_metadata"]
    return f"""# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`013`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 013 (frozen `docops_v2_l3_013_xlsx_procurement_bid_evaluation_release`)
- `synthetic`: true
- generator: {meta['generator']} (version {meta['generator_version']})
- seed: {meta['seed']}
- scale: {sm['vendors']} vendors

## Inputs

- Source workbook: `{meta['input_path']}`
- Frozen vendor declaration: `/root/tmp/docs/vendors.json`
- Frozen expected oracle: `/root/tmp/docs/expected.json`
- Original benchmark seed description: `/root/original_task_description.txt`

## Goal

Prepare a clean public procurement bid evaluation release workbook from a messy
internal workbook, using the same sequential workflow as parent task 013, with
every fixed range sized to the actual vendor count.

## Required Sequential Workflow

1. Read the internal `Correction_Log_INTERNAL` sheet and apply every listed
   correction before rebuilding any public sheet.
2. Remove every internal sheet (draft evaluations, price scratch, legal-hold
   and raw working data).
3. Rebuild the ten public sheets in the frozen order: Evaluation Summary,
   Vendor Register, Requirements Scoring, Price Normalization,
   Conflict-of-Interest Log, Award Recommendation, Debrief Register, Data
   Validation Guide, Publication Style Guide, Appendix Index.
4. Create the public `VendorIDs` named range over the full vendor register.
5. Add named-range-backed dropdown data validation to the scoring and COI
   sheets over their full ranges.
6. Add public debrief mailto hyperlinks for every vendor.
7. Apply the required public styles, freeze panes, auto filters, column widths
   and landscape fit-to-width print setup.

## Output Requirements

- Save to `{meta['output_path']}`.
- Do not modify the source workbook in place.
- Keep the output format the same as the input workbook (`.xlsx`).
- Complete the full ordered workflow, not just local text replacement.
"""


def original_description(meta: dict) -> str:
    sm = meta["scale_metadata"]
    return (
        "Synthetic scale variant of frozen task 013: public procurement bid "
        "evaluation release workbook. The source contains raw vendor data with "
        "internal corrections, draft evaluations, price scratch, legal-hold "
        "material and working scores. Scale is defined by the number of vendors "
        f"that must be corrected and rebuilt across the ten public sheets. "
        f"Variant {meta['variant_task_id']}, seed {meta['seed']}, "
        f"{sm['vendors']} vendors. This is a synthetic input, not a historical "
        "benchmark task."
    )
