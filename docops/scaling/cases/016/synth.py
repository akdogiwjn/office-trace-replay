"""Synthetic Excel 016 inputs: scaled scenario-driven forecast dashboard workbooks.

Produces a synthetic source workbook (Assumptions initial controls, Demand Raw
raw rows, Dashboard/Archive placeholders) and a frozen ``units.json`` material
declaration. Each business unit carries four forecast months. Base growth and
Stress growth are frozen scenario facts; generated base-unit values are kept in
[950, 1110] so the Base scenario produces zero capacity breaches while the
Stress scenario produces a data-dependent breach set. The parameterized builder
must genuinely read the source workbook; the expected oracle reads only
``units.json`` and shares no value computation with the builder.
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

SCENARIOS = {
    "Base": {"growth": 0.08, "price": 42, "capacity": 1200},
    "Stress": {"growth": -0.03, "price": 39, "capacity": 980},
}
DEFAULT_SCENARIO = "Stress"
PERIODS = ["Jun", "Jul", "Aug", "Sep"]

# base*(1+0.08) must stay < 1200 (Base capacity) -> base < 1111.11; and
# base*0.97 must exceed 980 (Stress capacity) for at least part of the data
# -> base > 1010.3. The deterministic generation window keeps Base at zero
# breaches while Stress depends on the actual generated values.
BASE_WINDOW = (950, 1110)
ACTUAL_WINDOW = (900, 1100)

PREFIXES = ["Central", "North", "South", "East", "West", "Harbor", "River",
            "Lakeside", "Summit", "Valley", "Market", "Crest", "Old Town",
            "Bayside", "Uptown", "Crossing", "Garden", "Ironworks", "Mill",
            "Fairview", "Anchor", "Beacon", "Catalyst", "Deerfield", "Elmwood"]
SUFFIXES = ["Plant", "Hub", "Works", "Station", "Depot", "Complex", "Center",
            "Facility", "Terminal", "Park", "Yard", "Annex", "Division",
            "Branch", "Store", "Point", "Road", "Field", "Dock", "Pavilion"]

LIGHT_BLUE = "D9EAF7"
VERY_LIGHT_BLUE = "EEF5FB"


def make_units(n: int, rng: random.Random) -> list[dict]:
    if n < 1:
        raise ValueError("business unit count must be >= 1")
    units = []
    for index in range(n):
        base_low, base_high = BASE_WINDOW
        units.append({
            "id": f"BU-{index + 1:03d}",
            "name": (f"{PREFIXES[index % len(PREFIXES)]} "
                     f"{SUFFIXES[(index // len(PREFIXES)) % len(SUFFIXES)]}"),
            "base_units": [rng.randint(base_low, base_high) for _ in PERIODS],
            "actual_units": [rng.randint(*ACTUAL_WINDOW) for _ in PERIODS],
        })
    assert len({u["name"] for u in units}) == n
    return units


def write_units_json(variant_id: str, units: list[dict],
                     input_name: str, out_dir: Path) -> Path:
    data = {
        "schema": "docops-scaling-units-v1",
        "variant_task_id": variant_id,
        "seed": common.VARIANTS[variant_id]["seed"],
        "input_path": f"/root/{input_name}",
        "scenarios": SCENARIOS,
        "default_scenario": DEFAULT_SCENARIO,
        "periods": PERIODS,
        "units": units,
    }
    common.write_json(out_dir / "units.json", data)
    return out_dir / "units.json"


def write_input_workbook(units: list[dict], path: Path) -> None:
    wb = Workbook()
    wb.properties.created = datetime.datetime(2026, 1, 1, 0, 0, 0)
    wb.properties.modified = datetime.datetime(2026, 1, 1, 0, 0, 0)
    wb.properties.creator = "DocOps synthetic scale generator"

    assumptions = wb.active
    assumptions.title = "Assumptions"
    assumptions.append(["Driver", "Base", "Stress"])
    assumptions.append(["Unit Growth", SCENARIOS["Base"]["growth"],
                        SCENARIOS["Stress"]["growth"]])
    assumptions.append(["Price", SCENARIOS["Base"]["price"],
                        SCENARIOS["Stress"]["price"]])
    assumptions.append(["Capacity", SCENARIOS["Base"]["capacity"],
                        SCENARIOS["Stress"]["capacity"]])
    assumptions.append(["Scenario", DEFAULT_SCENARIO, ""])
    assumptions["B5"].fill = PatternFill("solid", fgColor="FFFF00")
    assumptions["B5"].number_format = "@"
    assumptions.column_dimensions["A"].width = 20
    assumptions.column_dimensions["B"].width = 16
    assumptions.column_dimensions["C"].width = 16
    for row in range(2, 6):
        for col in range(2, 4):
            assumptions.cell(row, col).fill = PatternFill(
                "solid", fgColor="FFF2CC" if row == 5 else LIGHT_BLUE)
            assumptions.cell(row, col).alignment = Alignment(
                horizontal="center", vertical="center")

    demand = wb.create_sheet("Demand Raw")
    demand.append(["Month", "Base Units", "Actual Units", "Unit"])
    for unit in units:
        for month, base, actual in zip(PERIODS, unit["base_units"],
                                       unit["actual_units"]):
            demand.append([month, base, actual, unit["id"]])
    demand.freeze_panes = "A2"

    dashboard = wb.create_sheet("Dashboard")
    dashboard["A1"] = "Draft Forecast Dashboard"

    archive = wb.create_sheet("Archive")
    archive["A1"] = "Hide"

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


def stress_flags(units: list[dict]) -> list[str]:
    stress = SCENARIOS["Stress"]
    flags = []
    for unit in units:
        for base in unit["base_units"]:
            forecast = base * (1 + stress["growth"])
            flags.append("Breach" if forecast > stress["capacity"] else "OK")
    return flags


def generate(variant_id: str, out_dir: Path, write_raw_records: bool = True) -> dict:
    v = common.VARIANTS[variant_id]
    n = v["scale"]["business_units"]
    periods = v["scale"]["periods"]
    model_rows = v["scale"]["model_rows"]
    seed = v["seed"]
    rng = random.Random(seed)
    units = make_units(n, rng)

    out_dir.mkdir(parents=True, exist_ok=True)
    input_name = (
        f"docops_v2_l3_016_xlsx_forecast_driver_cascade_input_"
        f"{v['output_suffix']}.xlsx"
    )
    input_path = out_dir / input_name
    write_input_workbook(units, input_path)
    units_path = write_units_json(variant_id, units, input_name, out_dir)

    if write_raw_records:
        common.write_json(
            out_dir / "raw_records.json",
            {"schema": "docops-scaling-raw-records-v1",
             "variant_task_id": variant_id,
             "records": units},
        )

    base_flags = ["OK"] * model_rows
    stress = stress_flags(units)
    stress_breach_count = sum(1 for f in stress if f == "Breach")
    assert model_rows == n * periods == len(base_flags) == len(stress)

    scale_metadata = {
        "business_units": n,
        "periods": periods,
        "model_rows": model_rows,
        "model_range_end": model_rows + 1,
        "unit_ids": [u["id"] for u in units],
        "source_demand_rows": model_rows,
        "source_sheets": ["Assumptions", "Demand Raw", "Dashboard", "Archive"],
        "assumption_facts": SCENARIOS,
        "default_scenario": DEFAULT_SCENARIO,
        "capacity_flag_cells": model_rows,
        "kpi_formula_cells": 8,
        "watch_formula_cells": 8,
        "exception_slots": 10,
        "exception_formula_cells": 50,
        "unit_summary_formula_cells": 2 * n,
        "parameterized_ranges": [
            f"'Demand Raw'!A2:D{model_rows + 1}",
            f"'Forecast Model'!A2:I{model_rows + 1} (model)",
            f"'Forecast Model'!J2:J{model_rows + 1} (breach rank)",
            f"'Forecast Model'!K2:K{model_rows + 1} (unit key)",
            f"'Exception Review'!A2:E11 (slots)",
            f"'Dashboard'!A5:G8 (KPI cells)",
            f"'Dashboard'!A40:B{39 + n} (unit summary)",
        ],
        "render_scope": (
            "Dashboard first page only (pdftoppm -f 1 -singlefile at 150 dpi); "
            "the dashboard keeps fitToWidth=1/fitToHeight=1 while Forecast "
            "Model and Exception Review use fitToWidth=1/fitToHeight=0"
        ),
        "expected_render_images": 1,
        "preserved_parent_behavior": [
            "sheet order and visibility (Dashboard, Forecast Model, Exception "
            "Review, Assumptions visible; Demand Raw and Archive hidden)",
            "scenario-driven INDEX/MATCH formulas, capacity flag logic, "
            "exception breach-rank slots, dashboard KPIs, chart and yellow B5 "
            "scenario driver",
        ],
        "changed_parent_behavior": [
            "Forecast Model and Exception Review print setup changed from "
            "fitToWidth=1/fitToHeight=1 to fitToWidth=1/fitToHeight=0 so large "
            "ranges render across multiple readable pages",
            "every fixed range, KPI aggregate, exception slot, conditional-"
            "format range and chart data range is sized from the actual unit "
            "count; the native bar chart aggregates the four periods per unit "
            "instead of plotting every model row",
        ],
        "formula_count": model_rows * 11 + 50 + 8 + 8 + 2 * n + 2,
        "cached_check_cells": model_rows * 11 + 50 + 8 + 8,
        "base_breach_count": 0,
        "stress_breach_count": stress_breach_count,
        "first_unit": units[0],
        "middle_unit": units[n // 2],
        "last_unit": units[-1],
        "input_bytes": input_path.stat().st_size,
        "input_sha256": common.sha256_file(input_path),
        "units_json_sha256": common.sha256_file(units_path),
        "seed": seed,
    }

    meta = common.default_task_metadata(variant_id)
    meta["scale_metadata"] = scale_metadata
    meta["input_path"] = f"/root/{input_name}"
    meta["output_path"] = (
        f"/root/submission/"
        f"docops_v2_l3_016_xlsx_forecast_driver_cascade_output_"
        f"{v['output_suffix']}.xlsx"
    )
    meta["modified_workflow"] = [
        "01 build: frozen parent sheet order, formulas and styles preserved; "
        "Forecast Model and Exception Review print setup changed from "
        "fitToWidth=1/fitToHeight=1 to fitToWidth=1/fitToHeight=0 so large "
        "model/exception ranges render across multiple readable pages instead "
        "of one unreadable compressed page; every fixed range / KPI aggregate / "
        "exception slot / conditional-format range / dashboard chart data range "
        "is sized from the actual unit count read out of the synthetic source "
        "workbook",
        "02 recalc + pdf: unchanged recalc.py and soffice convert-to-pdf; page "
        "count is decided by real layout",
        "03 scenario cascade verify: dynamic validator checks every model row, "
        "the dashboard aggregates against the frozen expected.json, then flips "
        "B5 Base -> recalc -> all flags OK, and Stress -> recalc -> breach set "
        "and exception rows match the oracle",
    ]
    meta["measurement_scope"] = (
        "Scales the number of business units x forecast periods that must be "
        "cascaded through the scenario-driven model: Demand Raw rows, Forecast "
        "Model rows with per-row formulas, capacity flags, exception review "
        "slots, dashboard KPI aggregates and the dashboard chart. The size "
        "drives formula count, recalc cost, PDF page count and validation "
        "coverage; the dashboard keeps fit-to-one-page so only the first page "
        "is rendered."
    )
    common.write_json(out_dir / "task_metadata.json", meta)
    (out_dir / "instruction.md").write_text(instruction_md(meta), encoding="utf-8")
    (out_dir / "original_task_description.txt").write_text(
        original_description(meta), encoding="utf-8")

    return {
        "input": input_path,
        "units": units_path,
        "task_metadata": out_dir / "task_metadata.json",
        "scale_metadata": scale_metadata,
    }


def instruction_md(meta: dict) -> str:
    v = common.VARIANTS[meta["variant_task_id"]]
    sm = meta["scale_metadata"]
    return f"""# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`016`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 016 (frozen `docops_v2_l3_016_xlsx_forecast_driver_cascade`)
- `synthetic`: true
- generator: {meta['generator']} (version {meta['generator_version']})
- seed: {meta['seed']}
- scale: {sm['business_units']} business units x {sm['periods']} periods
  = {sm['model_rows']} forecast model rows

## Inputs

- Source workbook: `{meta['input_path']}`
- Frozen business-unit declaration: `/root/tmp/docs/units.json`
- Frozen expected oracle: `/root/tmp/docs/expected.json`
- Original benchmark seed description: `/root/original_task_description.txt`

## Goal

Build a clean scenario-driven forecast dashboard from a synthetic source
workbook using the same sequential workflow as parent task 016, with every
fixed range sized to the actual unit count.

## Required Sequential Workflow

1. Preserve the Assumptions sheet as the primary scenario control: B1:C1 hold
   the Base/Stress scenario names, B2:C2 unit growth, B3:C3 price, B4:C4
   capacity, and B5 is the yellow editable scenario driver (drop-down from
   B1:C1).
2. Preserve the hidden Demand Raw rows for all units and months.
3. Rebuild the Forecast Model with one row per unit-month, per-row formulas
   driven by the Assumptions scenario control, and the Capacity Flag
   (Breach when Forecast Units exceed Capacity).
4. Build the formula-driven Exception Review slots that select the current
   scenario's breach rows by breach rank.
5. Build the Dashboard with the scenario title, formula-backed KPIs over every
   model row, an exception watch referencing the exception review, and the
   native bar chart aggregating the four periods per unit.
6. Keep the Archive placeholder hidden; set the release order and visibility.
7. Save the clean workbook without modifying the source in place.

## Output Requirements

- Save to `{meta['output_path']}`.
- Keep the output format the same as the input workbook (`.xlsx`).
- Complete the full ordered workflow, not just local text replacement.
"""


def original_description(meta: dict) -> str:
    sm = meta["scale_metadata"]
    return (
        "Synthetic scale variant of frozen task 016: scenario-driven forecast "
        "dashboard cascade. The source contains the Assumptions scenario "
        "controls, raw demand rows for every unit and month, and Dashboard / "
        "Archive placeholders. Scale is defined by the number of business units "
        "x forecast periods that must cascade through the model, exception "
        f"review and dashboard. Variant {meta['variant_task_id']}, seed "
        f"{meta['seed']}, {sm['model_rows']} model rows. This is a synthetic "
        "input, not a historical benchmark task."
    )
