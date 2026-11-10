# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`013`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 013 (frozen `docops_v2_l3_013_xlsx_procurement_bid_evaluation_release`)
- `synthetic`: true
- generator: docops/scaling/cases/013/synth.py (version 1.0)
- seed: 2026110605
- scale: 100 vendors

## Inputs

- Source workbook: `/root/docops_v2_l3_013_xlsx_procurement_bid_evaluation_release_input_v100.xlsx`
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

- Save to `/root/submission/docops_v2_l3_013_xlsx_procurement_bid_evaluation_release_output_v100.xlsx`.
- Do not modify the source workbook in place.
- Keep the output format the same as the input workbook (`.xlsx`).
- Complete the full ordered workflow, not just local text replacement.
