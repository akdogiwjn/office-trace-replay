# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`003`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 003 (frozen `docops_v2_l3_003_docx_public_records_release_metadata_cleanup`)
- `synthetic`: true
- generator: docops/scaling/cases/003/synth.py (version 1.0)
- seed: 2026110510
- scale: 500 business units (reimbursement claims)

## Inputs

- Source document: `/root/docops_v2_l3_003_docx_public_records_release_metadata_cleanup_input_u500.docx`
- Frozen business-unit declaration: `/root/tmp/docs/units.json`
- Frozen expected oracle: `/root/tmp/docs/expected.json`
- Original benchmark seed description: `/root/original_task_description.txt`

## Goal

Prepare a clean public records release packet from a messy internal Word
document about water main break reimbursement claims. Every declared business
unit in `units.json` must go through the same sequential workflow as parent task
003, and every unit's corrected public facts must appear in the final packet.

## Required Sequential Workflow

1. Accept or resolve tracked changes before rebuilding the public packet.
2. Delete all comments and comment references.
3. Remove private metadata from document properties.
4. Apply the correction memo (global facts plus every unit's corrected amount /
   status) before rebuilding the public facts, tables, workflow, and appendix.
5. Remove all PII, legal-strategy notes, draft-only content, and private staff
   names.
6. Rebuild the public release packet from `units.json`: one corrected
   determination table per unit, the aggregate determination/category tables,
   footer, page breaks, and styles.
7. Save the clean public document as a new `.docx` without modifying the source.

## Required Corrections

Global (from the frozen parent memo): incident date `2026-01-18`, claim count
`500`, cap `$650`, public contact `Public Records Desk`,
response deadline `2026-08-15`. Per-unit amount/status corrections are declared
in `units.json`.

## Required Style and Layout

- Use `Aptos Display` bold title text, 18 pt, color `1F4E79`.
- Use `Aptos` body text, 10.5 pt.
- Use heading text in color `1F4E79`.
- Use table header fill `1F4E79` with white bold text.
- Set all page margins to `0.75` inches.
- Add footer text `Public Records Release | Water Main Break Claims | 2026`.

## Output Requirements

- Save to `/root/submission/docops_v2_l3_003_docx_public_records_release_metadata_cleanup_output_u500.docx`.
- Do not modify the source document in place.
- Keep the output format the same as the input document (`.docx`).
- Complete the full ordered workflow, not just local text replacement.
