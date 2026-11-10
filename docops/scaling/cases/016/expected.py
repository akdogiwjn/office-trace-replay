"""Independent expectation generator for scaled Excel 016 variants.

Reads the frozen ``units.json`` prepared material and derives the full expected
structure of the rebuilt scenario-driven workbook: the unit-period model rows
(base/actual/growth/forecast/price/revenue/capacity/flag/unit for every row),
the per-scenario rows and aggregates, the four-period dashboard chart sums, the
COMPLETE exception review list (every capacity breach in the default scenario),
the dashboard KPI formulas and cached values, the demand-raw business values,
the watch area and the chart cell references. It deliberately shares NO value
computation with the in-replay builder (which only writes Excel formula strings
and reads the source workbook), and the oracle is frozen at prepare time - it
is never regenerated during acceptance.
"""
from __future__ import annotations

from pathlib import Path

from .. import common
from . import synth

MODEL_HEADERS = [
    "Month", "Base Units", "Actual Units", "Scenario Growth", "Forecast Units",
    "Price", "Revenue", "Capacity", "Capacity Flag",
]
EXCEPTION_HEADERS = ["Unit", "Month", "Capacity Issue",
                     "Forecast Units", "Capacity", "Overage"]

KPI_FORMULA_CELLS = ["A5", "C5", "E5", "G5", "A8", "C8", "E8", "G8"]
WATCH_CELLS = ["A13", "C13", "E13", "G13", "A14", "C14", "E14", "G14"]

PERIOD_SUMMARY_HEADER_ROW = 20
PERIOD_SUMMARY_FIRST_DATA_ROW = 21


def model_formula_templates(m: int) -> dict:
    """Per-column formula template; ``{row}`` is substituted by the validator."""
    return {
        "A": "='Demand Raw'!A{row}",
        "B": "='Demand Raw'!B{row}",
        "C": "='Demand Raw'!C{row}",
        "D": "=INDEX(Assumptions!$B$2:$C$2,1,MATCH(Assumptions!$B$5,Assumptions!$B$1:$C$1,0))",
        "E": "=$B{row}*(1+$D{row})",
        "F": "=INDEX(Assumptions!$B$3:$C$3,1,MATCH(Assumptions!$B$5,Assumptions!$B$1:$C$1,0))",
        "G": "=$E{row}*$F{row}",
        "H": "=INDEX(Assumptions!$B$4:$C$4,1,MATCH(Assumptions!$B$5,Assumptions!$B$1:$C$1,0))",
        "I": f'=IF($E{{row}}>$H{{row}},"Breach","OK")',
        "J": f'=IF($I{{row}}="Breach",COUNTIF($I$2:$I{{row}},"Breach"),"")',
        "K": "='Demand Raw'!D{row}",
    }


def exception_formula_templates(m: int) -> dict:
    """Per-column formula template for the complete exception review rows."""
    return {
        "A": "=IFERROR(INDEX('Forecast Model'!$K$2:$K$m,MATCH(ROWS($A$2:A{r}),'Forecast Model'!$J$2:$J$m,0)),\"\")".replace("$m", "$" + str(m)),
        "B": "=IFERROR(INDEX('Forecast Model'!$A$2:$A$m,MATCH(ROWS($A$2:A{r}),'Forecast Model'!$J$2:$J$m,0)),\"\")".replace("$m", "$" + str(m)),
        "C": "=IF($B{r}=\"\",\"\",\"Forecast exceeds capacity by \"&TEXT($F{r},\"#,##0.0\")&\" units\")",
        "D": "=IFERROR(INDEX('Forecast Model'!$E$2:$E$m,MATCH(ROWS($A$2:A{r}),'Forecast Model'!$J$2:$J$m,0)),\"\")".replace("$m", "$" + str(m)),
        "E": "=IFERROR(INDEX('Forecast Model'!$H$2:$H$m,MATCH(ROWS($A$2:A{r}),'Forecast Model'!$J$2:$J$m,0)),\"\")".replace("$m", "$" + str(m)),
        "F": "=IF($B{r}=\"\",\"\",MAX($D{r}-$E{r},0))",
    }


def _row_facts(unit: dict, month: str, base: int, actual: int, scenario: str) -> dict:
    facts = synth.SCENARIOS[scenario]
    forecast = base * (1 + facts["growth"])
    capacity = facts["capacity"]
    return {
        "unit": unit["id"],
        "month": month,
        "base": base,
        "actual": actual,
        "growth": facts["growth"],
        "forecast": forecast,
        "price": facts["price"],
        "revenue": forecast * facts["price"],
        "capacity": capacity,
        "flag": "Breach" if forecast > capacity else "OK",
    }


def row_records(units: list[dict], scenario: str) -> list[dict]:
    rows = []
    for unit in units:
        for month, base, actual in zip(synth.PERIODS, unit["base_units"],
                                       unit["actual_units"]):
            rows.append(_row_facts(unit, month, base, actual, scenario))
    return rows


def demand_raw_rows(units: list[dict]) -> list[dict]:
    rows = []
    for unit in units:
        for month, base, actual in zip(synth.PERIODS, unit["base_units"],
                                       unit["actual_units"]):
            rows.append({"month": month, "base": base, "actual": actual,
                         "unit": unit["id"]})
    return rows


def period_sums(units: list[dict], scenario: str) -> dict:
    facts = synth.SCENARIOS[scenario]
    n = len(units)
    forecast = []
    capacity = []
    for idx in range(len(synth.PERIODS)):
        forecast.append(
            sum(u["base_units"][idx] * (1 + facts["growth"]) for u in units))
        capacity.append(n * facts["capacity"])
    return {"forecast": forecast, "capacity": capacity}


def kpis_for(rows: list[dict], scenario: str) -> dict:
    facts = synth.SCENARIOS[scenario]
    breach_rows = [r for r in rows if r["flag"] == "Breach"]
    return {
        "selected_scenario": scenario,
        "forecast_units": sum(r["forecast"] for r in rows),
        "total_revenue": sum(r["revenue"] for r in rows),
        "capacity_breaches": len(breach_rows),
        "total_overage": sum(r["forecast"] - r["capacity"] for r in breach_rows),
        "peak_forecast_units": max(r["forecast"] for r in rows),
        "average_price": facts["price"],
        "model_records": len(rows),
    }


def kpi_formulas(m: int) -> dict:
    return {
        "A5": "=Assumptions!$B$5",
        "C5": f"=SUM('Forecast Model'!$E$2:$E${m})",
        "E5": f"=SUM('Forecast Model'!$G$2:$G${m})",
        "G5": f"=COUNTIF('Forecast Model'!$I$2:$I${m},\"Breach\")",
        "A8": (f"=SUMPRODUCT(('Forecast Model'!$I$2:$I${m}=\"Breach\")*"
               f"('Forecast Model'!$E$2:$E${m}-'Forecast Model'!$H$2:$H${m}))"),
        "C8": f"=MAX('Forecast Model'!$E$2:$E${m})",
        "E8": f"=AVERAGE('Forecast Model'!$F$2:$F${m})",
        "G8": f"=COUNTA('Forecast Model'!$A$2:$A${m})",
    }


def watch_formulas(m: int) -> dict:
    def row_cells(exception_row: int) -> dict:
        return {
            "A": f"='Exception Review'!B{exception_row}",
            "C": f"='Exception Review'!D{exception_row}",
            "E": f"='Exception Review'!E{exception_row}",
            "G": f"='Exception Review'!F{exception_row}",
        }
    return {
        "A13": row_cells(2)["A"], "C13": row_cells(2)["C"],
        "E13": row_cells(2)["E"], "G13": row_cells(2)["G"],
        "A14": row_cells(3)["A"], "C14": row_cells(3)["C"],
        "E14": row_cells(3)["E"], "G14": row_cells(3)["G"],
    }


def period_summary_formulas(m: int) -> dict:
    templates = {}
    for offset, period in enumerate(synth.PERIODS):
        row = PERIOD_SUMMARY_FIRST_DATA_ROW + offset
        templates[f"B{row}"] = (
            f"=SUMIF('Forecast Model'!$A$2:$A${m},$A{row},'Forecast Model'!$E$2:$E${m})")
        templates[f"C{row}"] = (
            f"=SUMIF('Forecast Model'!$A$2:$A${m},$A{row},'Forecast Model'!$H$2:$H${m})")
    return templates


def compute(units_path: Path) -> dict:
    data = common.load_json(units_path)
    units = data["units"]
    n = len(units)
    periods = len(data["periods"])
    m = n * periods + 1
    default = data["default_scenario"]

    base_rows = row_records(units, "Base")
    stress_rows = row_records(units, "Stress")
    default_rows = row_records(units, default)
    assert all(r["flag"] == "OK" for r in base_rows), "Base scenario must have zero breaches"

    breach_rows = [r for r in default_rows if r["flag"] == "Breach"]
    breach_count = len(breach_rows)
    exception_slots = [
        {
            "unit": r["unit"], "month": r["month"],
            "forecast": r["forecast"], "capacity": r["capacity"],
            "overage": r["forecast"] - r["capacity"],
        }
        for r in breach_rows
    ]

    kpi = kpis_for(default_rows, default)
    period_summary = period_summary_formulas(m)
    last_data_row = PERIOD_SUMMARY_FIRST_DATA_ROW + periods - 1
    chart_refs = {
        "title": "Four-Period Forecast vs Capacity",
        "categories": list(synth.PERIODS),
        "categories_ref": "Dashboard!$A$21:$A$24",
        "series": [
            {"name": "Total Forecast Units", "name_cell": "Dashboard!B20",
             "values_ref": "Dashboard!$B$21:$B$24"},
            {"name": "Total Capacity", "name_cell": "Dashboard!C20",
             "values_ref": "Dashboard!$C$21:$C$24"},
        ],
        "forecast_cells": f"Dashboard!$B${PERIOD_SUMMARY_FIRST_DATA_ROW}:$B${last_data_row}",
        "capacity_cells": f"Dashboard!$C${PERIOD_SUMMARY_FIRST_DATA_ROW}:$C${last_data_row}",
        "last_forecast_cell": f"Dashboard!$B${last_data_row}",
        "last_capacity_cell": f"Dashboard!$C${last_data_row}",
    }

    formula_count = (n * periods) * 11 + breach_count * 6 + 25
    non_breach = (n * periods) - breach_count
    cached_cells = formula_count - non_breach  # Breach Rank J is empty on non-breach rows

    return {
        "schema": "docops-scaling-expectation-v1",
        "variant_task_id": data["variant_task_id"],
        "kind": "xlsx",
        "business_units": n,
        "periods": periods,
        "model_rows": n * periods,
        "model_range_end": m,
        "unit_ids": [u["id"] for u in units],
        "unit_names": {u["id"]: u["name"] for u in units},
        "periods_labels": data["periods"],
        "scenarios": data["scenarios"],
        "default_scenario": default,
        "model_headers": MODEL_HEADERS,
        "model_formula_templates": model_formula_templates(m),
        "demand_raw_rows": demand_raw_rows(units),
        "rows": default_rows,
        "scenario_rows": {"Base": base_rows, "Stress": stress_rows},
        "scenario_flags": {
            "Base": [r["flag"] for r in base_rows],
            "Stress": [r["flag"] for r in stress_rows],
        },
        "breach_count": breach_count,
        "breach_rows": [
            {"unit": r["unit"], "month": r["month"], "forecast": r["forecast"],
             "capacity": r["capacity"]}
            for r in breach_rows
        ],
        "exception_headers": EXCEPTION_HEADERS,
        "exception_first_row": 2,
        "exception_last_row": 1 + breach_count,
        "exception_slots": exception_slots,
        "exception_formula_templates": exception_formula_templates(m),
        "dashboard": kpi,
        "scenario_kpis": {"Base": kpis_for(base_rows, "Base"),
                          "Stress": kpis_for(stress_rows, "Stress")},
        "kpi_formulas": kpi_formulas(m),
        "kpi_cells": KPI_FORMULA_CELLS,
        "watch_formulas": watch_formulas(m),
        "watch_cells": WATCH_CELLS,
        "watch_exception_rows": [2, 3],
        "period_summary": {
            "header_row": PERIOD_SUMMARY_HEADER_ROW,
            "first_data_row": PERIOD_SUMMARY_FIRST_DATA_ROW,
            "last_data_row": last_data_row,
            "periods": synth.PERIODS,
            "forecast_cells": f"B{PERIOD_SUMMARY_FIRST_DATA_ROW}:B{last_data_row}",
            "capacity_cells": f"C{PERIOD_SUMMARY_FIRST_DATA_ROW}:C{last_data_row}",
            "formulas": period_summary,
        },
        "scenario_period_sums": {
            "Base": period_sums(units, "Base"),
            "Stress": period_sums(units, "Stress"),
        },
        "chart": chart_refs,
        "formula_count": formula_count,
        "cached_cells": cached_cells,
        "forbidden_phrases": ["Draft Forecast Dashboard", "DRAFT", "draft"],
        "release_order": [
            "Dashboard", "Forecast Model", "Exception Review", "Assumptions",
            "Demand Raw", "Archive",
        ],
        "hidden_sheets": ["Demand Raw", "Archive"],
    }


def write_expected(variant_task_id: str, units_path: Path, expected_path: Path) -> dict:
    result = compute(units_path)
    result["variant_task_id"] = variant_task_id
    common.write_json(expected_path, result)
    return result
