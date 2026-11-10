# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`009`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 009 (frozen `docops_v2_l3_009_docx_incident_manual_publication`)
- `synthetic`: true
- generator: docops/scaling/cases/009/synth.py (version 1.0)
- seed: 2026110604
- scale: 500 incident cases

## Inputs

- Source document: `/root/docops_v2_l3_009_docx_incident_manual_publication_input_u500.docx`
- Frozen incident-case declaration: `/root/tmp/docs/cases.json`
- Frozen expected oracle: `/root/tmp/docs/expected.json`
- Original benchmark seed description: `/root/original_task_description.txt`

## Goal

Convert a draft incident response manual into a release-safe public Word manual
through the same long ordered workflow as parent task 009. Every declared
incident case in `cases.json` must appear as a real row in the response
timeline, customer communication, control exception, action register, evidence
index and approval tables of the final packet.

## Required Sequential Workflow

1. Verify the source still carries the `Draft:` marker and remove all draft /
   internal material.
2. Build the public cover and a real Word TOC field.
3. Reorder sections into: Publication Summary, Response Timeline, Customer
   Communication, Control Exceptions, Action Register, Appendix A - Evidence
   Index, Appendix B - Approval Record.
4. Normalize the six data tables from `cases.json`: one row per incident case
   in the timeline, communication, exception, action, evidence and approval
   tables (the last case is really written).
5. Add page breaks before Control Exceptions, Action Register, Appendix A and
   Appendix B; update header/footer; highlight the open MFA evidence exception.
6. Ensure no `Draft:`, `[INTERNAL]`, `Do not publish`, phone bridge or
   privileged vendor-root-cause text remains.
7. Preserve the document as `.docx` and save to `/root/submission/docops_v2_l3_009_docx_incident_manual_publication_output_u500.docx`.

## Public Release Specification

- Title: `Incident Response Manual | Public Release`
- Header: `Incident Response Manual | Public Release | 2026-06-05`
- Footer: page numbering with the label `Page`
- Table headers: `Time | Milestone | Public Summary`, `Audience | Message
  Owner | Required Update | Status`, `Exception ID | Control | Owner | Release
  Status`, `Action ID | Owner | Due Date | Publish Status`, `Evidence ID |
  Public Label | Disposition`, `Approver | Role | Decision`.

## Output Requirements

- Do not modify the source document in place.
- Keep the output format the same as the input document (`.docx`).
- Complete the entire long-flow publication workflow; partial section cleanup
  is not sufficient.
