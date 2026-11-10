# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`029`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 029 (frozen `docops_v2_l3_029_pptx_qbr_release_deck`)
- `synthetic`: true
- generator: docops/scaling/cases/029/synth.py (version 1.0)
- seed: 2026110612
- scale: 10 business units x 8 public slides
  per unit + 1 locked legal page = 81 output pages

## Inputs

- Source presentation: `/root/docops_v2_l3_029_pptx_qbr_release_deck_input_u10.pptx`
- Frozen business-unit material: `/root/tmp/docs/units.json`
- Frozen expected oracle: `/root/tmp/docs/expected.json`
- Original benchmark seed description: `/root/original_task_description.txt`

## Goal

Convert a messy synthetic QBR release deck from draft staging state into a
release-ready presentation using the same ordered workflow as parent task 029,
with a full eight-page public release set per business unit in `units.json` and
the shared locked legal reference page preserved exactly from the source.

## Required Sequential Workflow

1. Delete scratch/deprecated internal slides and per-unit placeholders; remove
   draft labels and stale content.
2. For every business unit in `units.json` build the eight public release
   pages: Market Context, KPI Snapshot, Customer Risks, Mitigation Plan,
   Decision Request, Action Register, Data Notes, Unit Summary.
3. Generate real per-unit KPI / risk / measure / decision tables with each
   unit's own facts.
4. Add the release footer `QBR Release | 2026-06-05` and `Slide i of <total>`
   on every public page.
5. Preserve the trailing `Reference - Locked Legal` page from the source
   exactly (text, shapes and speaker note unchanged) and keep it in the final
   position.
6. Save the release deck without modifying the source in place.

## Output Requirements

- Save to `/root/submission/docops_v2_l3_029_pptx_qbr_release_deck_output_u10.pptx`.
- Keep the output format the same as the input presentation (`.pptx`).
- Complete the full ordered workflow, not just local text replacement.
