# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`001`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 001 (frozen `docops_v2_l3_001_docx_controlled_document_release_repair`)
- `synthetic`: true
- generator: docops/scaling/cases/001/synth.py (version 1.0)
- seed: 2026110601
- scale: 100 controlled document records

## Inputs

- Source document: `/root/docops_v2_l3_001_docx_controlled_document_release_repair_input_u100.docx`
- Frozen record declaration: `/root/tmp/docs/records.json`
- Frozen expected oracle: `/root/tmp/docs/expected.json`
- Original benchmark seed description: `/root/original_task_description.txt`

## Goal

Prepare a clean controlled document release repair packet from a DRAFT internal
Word source. Every declared record in `records.json` must go through the same
sequential workflow as parent task 001, and every record's corrected release
facts must appear in the final packet.

## Required Sequential Workflow

1. Verify the source still carries the DRAFT/internal-error marker.
2. Remove all DRAFT/PRIVATE/TODO working content.
3. Apply the correction register (document ID `QMS-PR-007`, version `4.2`,
   effective `2026-08-01`, owner `Quality Systems Office`, approver
   `Compliance Director`, training due `2026-08-15`, retention `6 years`,
   obsolete copy retirement `2026-08-05`) and fix the spelling errors.
4. Rebuild the controlled document metadata, revision history, distribution
   and training workflow, obsolete copy retirement checklist and final release
   appendix from `records.json`; one register row per record.
5. Set release metadata, footer, margins, styles and page breaks once.
6. Save the clean public document as a new `.docx` without modifying the source.

## Required Style and Layout

- `Aptos Display` bold title text, 18 pt, color `0F4C5C`; `Aptos` body 10.5 pt.
- Heading text in color `0F4C5C`.
- Table header fill `0F4C5C` with white bold text.
- All page margins `0.8` inches.
- Footer `QMS-PR-007 | Version 4.2` + `Controlled Document Release Repair
  Packet | 2026` + page field.

## Output Requirements

- Save to `/root/submission/docops_v2_l3_001_docx_controlled_document_release_repair_output_u100.docx`.
- Do not modify the source document in place.
- Keep the output format the same as the input document (`.docx`).
- Complete the full ordered workflow, not just local text replacement.
