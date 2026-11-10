# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`014`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 014 (frozen `docops_v2_l3_014_xlsx_disaster_housing_grant_public_release`)
- `synthetic`: true
- generator: docops/scaling/cases/014/synth.py (version 1.0)
- seed: 2026110502
- scale: {'deduped_applications': 10000}
- raw input rows: 10401
- controlled duplicates: 401
- valid applications after dedup: 10000

## Inputs

- Source workbook: `/root/docops_v2_l3_014_xlsx_disaster_housing_grant_public_release_input_n10000.xlsx`
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

- Save to `/root/submission/docops_v2_l3_014_xlsx_disaster_housing_grant_public_release_output_n10000.xlsx`.
- Do not modify the source workbook in place.
- Keep the output format the same as the input workbook (`.xlsx`).
- Complete the full ordered workflow, not just local text replacement.
