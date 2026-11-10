"""Synthetic Excel 014 inputs: scaled disaster housing grant release workbooks.

Produces a raw intake workbook with ``n`` deduplicated-valid applications. The
first twelve application records (H-101..H-112) are byte-faithful copies of the
frozen original seed records so the original corrections (H-104 county,
H-109 damage category, H-112 income band) and the H-107 duplicate example
remain present. Additional records and controlled duplicate rows are generated
with a fixed random seed; the scale is defined by the number of valid
applications after deduplication.
"""
from __future__ import annotations

import datetime
import json
import os
import random
from pathlib import Path

from openpyxl import Workbook

from .. import common

PUBLIC_FIELDS = [
    "Application ID",
    "County",
    "Damage Category",
    "Repair Estimate",
    "Insurance Proceeds",
    "Income Band",
    "Vulnerable Household",
    "Appeal Flag",
    "Inspection Date",
]

RAW_HEADERS = [
    "Application ID",
    "Applicant Name",
    "County",
    "Damage Category",
    "Repair Estimate",
    "Insurance Proceeds",
    "Income Band",
    "Vulnerable Household",
    "Appeal Flag",
    "Inspection Date",
    "Private Notes",
    "personal phone",
]

COUNTIES = ["East Bay", "North Fork", "South Ridge", "West Lake"]
DAMAGE_WEIGHTS = [("Destroyed", 18), ("Major", 30), ("Moderate", 30), ("Minor", 22)]
INCOME_WEIGHTS = [("Low", 40), ("Moderate", 40), ("High", 20)]
REPAIR_BANDS = {
    "Destroyed": (45000, 80000),
    "Major": (18000, 45000),
    "Moderate": (9000, 20000),
    "Minor": (4000, 12000),
}

CORRECTIONS = {
    "H-104": {"County": "North Fork"},
    "H-109": {"Damage Category": "Major"},
    "H-112": {"Income Band": "Low"},
}
CAPS = {"Minor": 12000, "Moderate": 18000, "Major": 28000, "Destroyed": 42000}

# Original frozen raw seed rows (public + private fields), byte faithful.
ORIGINAL_RAW = [
    ("H-101", "Alicia Tran", "South Ridge", "Moderate", 21500, 3000, "Moderate", "No", "No", "2026-05-14", "unverified hardship narrative", "555-0101"),
    ("H-102", "Marta Ruiz", "East Bay", "Major", 40200, 5000, "Low", "Yes", "No", "2026-05-15", "PRIVATE intake note", "555-0102"),
    ("H-103", "Lena Okafor", "West Lake", "Minor", 8800, 0, "High", "No", "Yes", "2026-05-16", "appeal note legal hold", "555-0103"),
    ("H-104", "Dev Patel", "N. Fork", "Major", 30500, 4000, "Low", "No", "No", "2026-05-18", "county correction pending", "555-0104"),
    ("H-105", "Iris Chen", "South Ridge", "Destroyed", 68000, 12000, "Low", "Yes", "Yes", "2026-05-18", "DRAFT senior review note", "555-0105"),
    ("H-106", "Omar Brooks", "East Bay", "Moderate", 15600, 800, "Moderate", "No", "No", "2026-05-19", "raw intake check", "555-0106"),
    ("H-107", "Nadia Singh", "West Lake", "Major", 22000, 1000, "Moderate", "Yes", "No", "2026-05-10", "older duplicate scratch row", "555-0107"),
    ("H-107", "Nadia Singh", "West Lake", "Major", 23500, 2000, "Moderate", "Yes", "No", "2026-05-21", "latest duplicate row", "555-0107"),
    ("H-108", "Theo Martin", "South Ridge", "Minor", 9400, 1200, "Low", "No", "No", "2026-05-20", "PRIVATE note", "555-0108"),
    ("H-109", "Bianca Flores", "East Bay", "Minor", 26700, 2500, "Moderate", "No", "Yes", "2026-05-22", "Minor correction pending", "555-0109"),
    ("H-110", "Samir Haddad", "North Fork", "Destroyed", 72000, 15000, "Low", "Yes", "No", "2026-05-23", "legal hold cleared later", "555-0110"),
    ("H-111", "Renee James", "West Lake", "Moderate", 19800, 0, "High", "No", "No", "2026-05-23", "raw intake note", "555-0111"),
    ("H-112", "Cole Rivera", "South Ridge", "Major", 31500, 5000, "Moderate", "Yes", "No", "2026-05-24", "moderate income pending", "555-0112"),
]

# Guaranteed branch-coverage anchors, generated after the original seed rows.
# These ensure every eligibility / priority / review branch actually appears.
COVERAGE_ANCHORS = [
    # Destroyed + Low + vulnerable -> capped 42000, score 80, Senior Review.
    ("H-113", "Rayna Vance", "West Lake", "Destroyed", 52000, 5000, "Low", "Yes", "No", "2026-05-25", "unverified hardship narrative", "555-0113"),
    # Minor + High + appeal -> eligible 1000 (< cap), Appeal Review.
    ("H-114", "Jonah Pike", "East Bay", "Minor", 7000, 6000, "High", "No", "Yes", "2026-05-26", "appeal note", "555-0114"),
    # Moderate + Moderate, repair == insurance -> eligible 0 branch, Ready.
    ("H-115", "Tessa Quinn", "North Fork", "Moderate", 15000, 15000, "Moderate", "No", "No", "2026-05-27", "raw intake check", "555-0115"),
    # Major + Low + vulnerable, below cap -> eligible 17000, score 70, Ready.
    ("H-116", "Marcus Bell", "South Ridge", "Major", 20000, 3000, "Low", "Yes", "No", "2026-05-28", "PRIVATE intake note", "555-0116"),
    # Destroyed + High -> capped 42000, score 40, Senior Review.
    ("H-117", "Priya Nair", "East Bay", "Destroyed", 65000, 20000, "High", "No", "No", "2026-05-29", "legal hold cleared later", "555-0117"),
    # Minor + Low + vulnerable + appeal -> Appeal Review, score 50.
    ("H-118", "Dylan Cross", "West Lake", "Minor", 5000, 0, "Low", "Yes", "Yes", "2026-05-30", "DRAFT review note", "555-0118"),
]

FIRST_NAMES = ["Ava", "Leo", "Mia", "Noah", "Zoe", "Eli", "Nora", "Owen", "Ivy", "Kai",
               "Ruth", "Sam", "Wren", "Felix", "June", "Theo", "Vera", "Hugo", "Lena", "Omar"]
LAST_NAMES = ["Kim", "Cheng", "Patel", "Rossi", "Novak", "Ito", "Sato", "Larsen",
              "Mendes", "Fischer", "Owens", "Silva", "Thorne", "Wu", "Park", "Ali",
              "Bauer", "Reed", "Grant", "Perez"]
PRIVATE_NOTES = [
    "unverified hardship narrative",
    "PRIVATE intake note",
    "legal hold",
    "duplicate scratch row",
    "raw intake check",
    "DRAFT review note",
    "appeal note",
]


def _row_dict(row) -> dict:
    app_id, name, county, damage, repair, insurance, income, vuln, appeal, date_, notes, phone = row
    return {
        "Application ID": app_id,
        "Applicant Name": name,
        "County": county,
        "Damage Category": damage,
        "Repair Estimate": repair,
        "Insurance Proceeds": insurance,
        "Income Band": income,
        "Vulnerable Household": vuln,
        "Appeal Flag": appeal,
        "Inspection Date": date_,
        "Private Notes": notes,
        "personal phone": phone,
    }


def _random_public(rng) -> dict:
    damage = rng.choices([d for d, _ in DAMAGE_WEIGHTS], weights=[w for _, w in DAMAGE_WEIGHTS])[0]
    income = rng.choices([i for i, _ in INCOME_WEIGHTS], weights=[w for _, w in INCOME_WEIGHTS])[0]
    low, high = REPAIR_BANDS[damage]
    repair = rng.randint(low, high)
    insurance = 0 if rng.random() < 0.15 else rng.randint(0, int(repair * 0.6))
    county = rng.choice(COUNTIES)
    vuln = "Yes" if rng.random() < 0.35 else "No"
    appeal = "Yes" if rng.random() < 0.22 else "No"
    day = rng.randint(1, 51)
    month = 6 if day > 31 else 5
    day = day - 31 if day > 31 else day
    date_ = f"2026-{month:02d}-{day:02d}"
    name = rng.choice(FIRST_NAMES) + " " + rng.choice(LAST_NAMES)
    phone = f"555-{rng.randint(100, 999)}"
    notes = rng.choice(PRIVATE_NOTES)
    return _row_dict((None, name, county, damage, repair, insurance, income, vuln, appeal,
                      date_, notes, phone))


def _dup_row(primary: dict, rng, offset_days: int) -> dict:
    base_year, base_month, base_day = (int(x) for x in primary["Inspection Date"].split("-"))
    import datetime as _dt
    base = _dt.date(base_year, base_month, base_day)
    new_date = base + _dt.timedelta(days=offset_days)
    row = dict(primary)
    row["Inspection Date"] = new_date.isoformat()
    if offset_days > 0:
        row["Repair Estimate"] = max(0, int(primary["Repair Estimate"]) + rng.randint(-2500, 3500))
        row["Insurance Proceeds"] = max(0, int(primary["Insurance Proceeds"]) + rng.randint(-800, 1200))
    row["Private Notes"] = "duplicate scratch row"
    return row


def generate(variant_id: str, out_dir: Path, write_raw_records: bool = True) -> dict:
    v = common.VARIANTS[variant_id]
    n = v["scale"]["deduped_applications"]
    seed = v["seed"]
    rng = random.Random(seed)

    rows = []
    for row in ORIGINAL_RAW:
        rows.append(_row_dict(row))
    for row in COVERAGE_ANCHORS:
        rows.append(_row_dict(row))

    start_id = 119
    for index in range(start_id, start_id + (n - 12 - len(COVERAGE_ANCHORS))):
        rec = _random_public(rng)
        rec["Application ID"] = f"H-{index}"
        rows.append(rec)

    # Controlled duplicates: extra rows with a different inspection date. The
    # dedup must keep the latest inspection record, whichever physical position
    # the newer row occupies (rows are shuffled afterwards).
    dup_pool = [r["Application ID"] for r in rows
                if r["Application ID"] not in ("H-104", "H-109", "H-112", "H-107")]
    dup_count = max(6, round(0.04 * n))
    rng.shuffle(dup_pool)
    dup_ids = dup_pool[:dup_count]
    for app_id in dup_ids:
        primary = next(r for r in rows if r["Application ID"] == app_id)
        offset = rng.choice([-1, -2, -3, -5, -8, 1, 2, 3, 4, 7])
        rows.append(_dup_row(primary, rng, offset))

    rng.shuffle(rows)

    out_dir.mkdir(parents=True, exist_ok=True)
    input_name = f"docops_v2_l3_014_xlsx_disaster_housing_grant_public_release_input_{v['output_suffix']}.xlsx"
    input_path = out_dir / input_name
    _write_input(input_path, rows)
    raw_records = [dict(r) for r in rows]
    valid_records = _dedup_for_metadata(rows)
    appeal_count = sum(1 for r in valid_records if r["Appeal Flag"] == "Yes")

    scale_metadata = {
        "raw_rows": len(rows),
        "duplicates": len(rows) - n,
        "valid_applications": n,
        "raw_fields": len(RAW_HEADERS),
        "public_fields": len(PUBLIC_FIELDS),
        "register_fields": 12,
        "appeal_count": appeal_count,
        "formula_count": 3 * n + 5 + 4 * 3 + 2 * appeal_count,
        "input_bytes": input_path.stat().st_size,
        "input_sha256": common.sha256_file(input_path),
        "seed": seed,
        "branch_coverage": branch_coverage(rows),
    }
    if write_raw_records:
        common.write_json(out_dir / "raw_records.json",
                          {"schema": "docops-scaling-raw-records-v1",
                           "variant_task_id": variant_id, "records": raw_records})

    meta = common.default_task_metadata(variant_id)
    meta["scale_metadata"] = scale_metadata
    meta["input_path"] = f"/root/{input_name}"
    meta["output_path"] = (
        f"/root/submission/docops_v2_l3_014_xlsx_disaster_housing_grant_public_release_output_{v['output_suffix']}.xlsx"
    )
    meta["modified_workflow"] = [
        "01 build: dynamic ranges (register/county/dashboard/appeal/tables/conditional formats/auto-filter) sized by actual deduplicated record count",
        "02 recalc: unchanged command, variant output path",
        "03 finalize+validate: OOXML repair unchanged; validate compares every row/aggregate against frozen expected.json",
        "04 convert_pdf: unchanged command, variant output path",
        "05 render: unchanged command, variant output path",
    ]
    meta["measurement_scope"] = (
        "Scales the number of deduplicated valid applications, which drives "
        "register/county/dashboard/appeal generation, recalc, validation, PDF "
        "export and page rendering. The source intake workbook is synthetic; the "
        "scope is register size, not a larger source-workbook parse or cleanup cost."
    )
    common.write_json(out_dir / "task_metadata.json", meta)
    (out_dir / "instruction.md").write_text(instruction_md(meta), encoding="utf-8")
    (out_dir / "original_task_description.txt").write_text(original_description(meta), encoding="utf-8")

    return {
        "input": input_path,
        "raw_records": out_dir / "raw_records.json",
        "task_metadata": out_dir / "task_metadata.json",
        "scale_metadata": scale_metadata,
    }


def _dedup_for_metadata(rows) -> list[dict]:
    import datetime as _dt
    latest = {}
    for r in rows:
        app_id = r["Application ID"]
        date_value = _dt.date.fromisoformat(str(r["Inspection Date"]).strip())
        prior = latest.get(app_id)
        if prior is None or date_value > prior[0]:
            latest[app_id] = (date_value, r)
    result = [entry[1] for entry in latest.values()]
    result.sort(key=lambda r: int(r["Application ID"].split("-")[1]))
    return result


def branch_coverage(rows) -> dict:
    counts = {
        "damage": {d: 0 for d in CAPS},
        "income": {"Low": 0, "Moderate": 0, "High": 0},
        "vulnerable": {"Yes": 0, "No": 0},
        "appeal": {"Yes": 0, "No": 0},
    }
    for r in rows:
        counts["damage"][r["Damage Category"]] += 1
        counts["income"][r["Income Band"]] += 1
        counts["vulnerable"][r["Vulnerable Household"]] += 1
        counts["appeal"][r["Appeal Flag"]] += 1
    return counts


def _write_input(path: Path, rows) -> None:
    wb = Workbook()
    wb.properties.created = datetime.datetime(2026, 1, 1, 0, 0, 0)
    wb.properties.modified = datetime.datetime(2026, 1, 1, 0, 0, 0)
    wb.properties.creator = "DocOps synthetic scale generator"
    intake = wb.active
    intake.title = "Raw Intake PRIVATE"
    intake.append(RAW_HEADERS)
    for r in rows:
        intake.append([r[f] for f in RAW_HEADERS])

    bulletin = wb.create_sheet("Correction Bulletin DRAFT")
    bulletin.append(["Field", "Wrong Value", "Corrected Public Value", "Private Rationale"])
    bulletin.append(["H-104 county", "N. Fork", "North Fork", "PRIVATE geocoder note"])
    bulletin.append(["H-109 damage category", "Minor", "Major", "inspection upload corrected"])
    bulletin.append(["H-112 income band", "Moderate", "Low", "income verification corrected"])
    bulletin.append(["Caps", "old draft caps",
                     "Minor 12000; Moderate 18000; Major 28000; Destroyed 42000",
                     "DRAFT finance note"])

    scratch = wb.create_sheet("duplicate scratch")
    scratch.append(["Application ID", "duplicate scratch instruction"])
    scratch.append(["H-107", "Keep the 2026-05-21 inspection row and remove the older row."])
    scratch.append(["H-103", "Appeal queue candidate."])

    hold = wb.create_sheet("legal hold")
    hold.append(["PRIVATE legal hold", "Do not publish"])
    hold.append(["Applicant Name", "personal phone"])
    hold.append(["unverified hardship narrative", "attorney note"])

    dash = wb.create_sheet("DRAFT Dashboard")
    dash.append(["DRAFT metric", "Unverified value"])
    dash.append(["Total applications", len(rows)])
    dash.append(["PRIVATE note", "dashboard uses raw intake and duplicates"])

    _save_deterministic(wb, path)


def _save_deterministic(wb, path):
    """openpyxl overwrites `modified` with now(); rewrite core.xml and normalize
    zip metadata so the same seed and parameters always produce the same bytes."""
    import re
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


def instruction_md(meta: dict) -> str:
    v = common.VARIANTS[meta["variant_task_id"]]
    return f"""# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`014`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 014 (frozen `docops_v2_l3_014_xlsx_disaster_housing_grant_public_release`)
- `synthetic`: true
- generator: {meta['generator']} (version {meta['generator_version']})
- seed: {meta['seed']}
- scale: {meta['scale']}
- raw input rows: {meta['scale_metadata']['raw_rows']}
- controlled duplicates: {meta['scale_metadata']['duplicates']}
- valid applications after dedup: {meta['scale_metadata']['valid_applications']}

## Inputs

- Source workbook: `{meta['input_path']}`
- Original benchmark seed description: `/root/original_task_description.txt`

## Goal

Prepare a clean public disaster housing repair grant release workbook from a
messy internal intake workbook, using the same sequential workflow as parent
task 014, with all fixed ranges sized to the actual data.

## Required Sequential Workflow

1. Remove private intake, duplicate-scratch, and legal-hold material.
2. Deduplicate applications by `Application ID`, keeping the latest `Inspection Date`.
3. Apply the correction bulletin before calculating eligibility (H-104 county
   `North Fork`, H-109 damage category `Major`, H-112 income band `Low`; caps
   Minor 12000 / Moderate 18000 / Major 28000 / Destroyed 42000).
4. Rebuild the public eligibility register with formulas for eligible amount,
   priority score, and review status covering every deduplicated row.
5. Build county rollup formulas and the dashboard chart from the corrected register.
6. Build the appeal queue from applications with appeal flag `Yes`.
7. Apply required public styles, freeze panes, conditional formatting (over the
   full register range), sheet protection and workbook structure protection.

## Calculation Rules

- `Eligible Amount`: `MAX(0, MIN(Repair Estimate - Insurance Proceeds, assistance cap))`.
- `Priority Score`: vulnerable `Yes` +20; damage Destroyed 40 / Major 30 /
  Moderate 20 / Minor 10; income Low 20 / Moderate 10 / High 0.
- `Review Status`: `Senior Review` when eligible amount >= 20000; otherwise
  `Appeal Review` when appeal flag `Yes`; otherwise `Ready`.

## Output Requirements

- Save to `{meta['output_path']}`.
- Do not modify the source workbook in place.
- Keep the output format the same as the input workbook (`.xlsx`).
- Complete the full ordered workflow, not just local text replacement.
"""


def original_description(meta: dict) -> str:
    return (
        "Synthetic scale variant of frozen task 014: public disaster housing "
        "repair grant release workbook. Source contains raw intake rows, controlled "
        "duplicate application records, PII, legal-hold material, draft corrections, "
        "and an unformatted dashboard. Scale is defined by the number of valid "
        "applications after deduplication. "
        f"Variant {meta['variant_task_id']}, seed {meta['seed']}, "
        f"{meta['scale_metadata']['valid_applications']} valid applications. "
        "This is a synthetic input, not a historical benchmark task."
    )
