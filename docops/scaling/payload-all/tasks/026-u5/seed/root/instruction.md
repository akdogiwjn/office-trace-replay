# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`026`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 026 (frozen `docops_v2_l3_026_pptx_climate_disclosure_chart_rebuild`)
- `synthetic`: true
- generator: docops/scaling/cases/026/synth.py (version 1.0)
- seed: 2026110609
- scale: 5 reporting units x 9 slides per unit
  = 45 output pages

## Inputs

- Source presentation: `/root/docops_v2_l3_026_pptx_climate_disclosure_chart_rebuild_input_u5.pptx`
- Frozen reporting-unit material: `/root/tmp/docs/units.json`
- Frozen expected oracle: `/root/tmp/docs/expected.json`
- Original benchmark seed description: `/root/original_task_description.txt`

## Goal

Rebuild a clean multi-unit public climate disclosure deck from a messy internal
review presentation using the same sequential workflow as parent task 026, with
one full nine-page disclosure set per reporting unit in `units.json`.

## Required Sequential Workflow

1. Remove internal-only slides, hidden off-slide content, confidential notes,
   and staff-only links.
2. Apply the correction memo before rebuilding any table or chart.
3. Iterate the reporting units from `units.json`; every unit produces the frozen
   nine public slides: Title, Disclosure Boundary, Corrected Emissions Inventory,
   Emissions Trend Chart, Assurance Status, Transition Action Plan, Supplier
   Engagement Register, Board Actions, Publication Style Guide.
4. Rebuild the emissions inventory table and the supplier engagement register
   table with each unit's own corrected facts.
5. Rebuild the native clustered-column trend chart from each unit's corrected
   annual totals (per-unit 3-year values).
6. Apply the required public visual style after content and chart data are final.
7. Preserve only concise public speaker notes (per unit, per page).
8. Save the clean deck without modifying the source in place.

## Output Requirements

- Save to `/root/submission/docops_v2_l3_026_pptx_climate_disclosure_chart_rebuild_output_u5.pptx`.
- Keep the output format the same as the input presentation (`.pptx`).
- Complete the full ordered workflow, not just local text replacement.
