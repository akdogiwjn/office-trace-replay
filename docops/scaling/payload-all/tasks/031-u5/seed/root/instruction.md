# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`031`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 031 (frozen `docops_v2_l3_031_pdf_public_hearing_packet_flatten_release`)
- `synthetic`: true
- generator: docops/scaling/cases/031/synth.py (version 1.0)
- seed: 2026110613
- scale: 5 hearing groups -> 25 pages
- pages per group: 5

## Scale definition (explicit)

This variant defines scale by the number of **frozen structured hearing groups**
in `notices.json`. Each group is actually built through the real ReportLab page
drawing functions (cover, corrected hearing summary, comment category matrix,
response workflow, release controls and appendix index), then finalized with
pypdf bookmarks/metadata and rendered at 144 DPI PNG. Pages are never duplicated
from a small base packet.

The synthetic input PDF `/root/docops_v2_l3_031_pdf_public_hearing_packet_flatten_release_input_u5.pdf` is an artifact only: like the
frozen parent input, the builder does not read it for content. Do not treat its
page count as the scale definition.

## Inputs

- Source document: `/root/docops_v2_l3_031_pdf_public_hearing_packet_flatten_release_input_u5.pdf` (artifact; not read by the builder)
- Prepared hearing declaration: `/root/tmp/docs/notices.json`
- Frozen expected oracle: `/root/tmp/docs/expected.json`
- Original benchmark seed description: `/root/original_task_description.txt`

## Goal

Produce a clean public hearing release packet: for every hearing group in
`notices.json`, build the five public pages in order, with dynamic page numbers,
bookmarks and metadata, using the same workflow as parent task 031.

## Required Pages (per group)

1. `Public Hearing Packet: Zoning Amendment Comments` (cover)
2. `Corrected Hearing Summary`
3. `Comment Category Matrix`
4. `Response Workflow`
5. `Release Controls and Appendix Index`

## Required Corrections

Per group, use only the corrected public facts declared in `notices.json`
(docket id, hearing date, deduplicated comment total, response deadline, public
contact). Remove `DRAFT`, `PRIVATE`, `INTERNAL`, and the draft wrong values
(`2026-03-04`, `112 comments`, `2026-09-01`, `Vivian Holt`, `Marco Ruiz`,
`555-0198`, `personal phone`, `legal hold`, `do not publish`).

## Output Requirements

- Save to `/root/submission/docops_v2_l3_031_pdf_public_hearing_packet_flatten_release_output_u5.pdf`.
- Do not modify the source document in place.
- Keep the output format the same as the input document (`.pdf`).
- Complete the full ordered workflow, not just local text replacement.
