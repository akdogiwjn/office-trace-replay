# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`016`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 016 (frozen `docops_v2_l3_016_xlsx_forecast_driver_cascade`)
- `synthetic`: true
- generator: docops/scaling/cases/016/synth.py (version 1.0)
- seed: 2026110608
- scale: 500 business units x 4 periods
  = 2000 forecast model rows

## Inputs

- Source workbook: `/root/docops_v2_l3_016_xlsx_forecast_driver_cascade_input_u500.xlsx`
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

- Save to `/root/submission/docops_v2_l3_016_xlsx_forecast_driver_cascade_output_u500.xlsx`.
- Keep the output format the same as the input workbook (`.xlsx`).
- Complete the full ordered workflow, not just local text replacement.
