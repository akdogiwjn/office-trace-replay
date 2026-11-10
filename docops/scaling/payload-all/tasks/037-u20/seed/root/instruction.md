# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`037`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 037 (frozen `docops_v2_l3_037_pdf_bus_detour_notice_layout_repair`)
- `synthetic`: true
- generator: docops/scaling/cases/037/synth.py (version 1.0)
- seed: 2026110508
- scale: 20 notice groups -> 100 pages
- pages per group: 5

## Scale definition (explicit)

This variant defines scale by the number of **frozen structured notice groups**
in `notices.json`. Each group is actually built through the real ReportLab page
drawing functions (cover, corrected summary, stop/shuttle matrix, rider
timeline, release checklist), then finalized with pypdf bookmarks/metadata and
rendered at 150 DPI PNG. Pages are never duplicated from a small base packet.

The synthetic input PDF `/root/docops_v2_l3_037_pdf_bus_detour_notice_layout_repair_input_u20.pdf` is an artifact only: like the
frozen parent input, the builder does not read it for content. Do not treat its
page count as the scale definition.

## Inputs

- Source document: `/root/docops_v2_l3_037_pdf_bus_detour_notice_layout_repair_input_u20.pdf` (artifact; not read by the builder)
- Prepared notice declaration: `/root/tmp/docs/notices.json`
- Frozen expected oracle: `/root/tmp/docs/expected.json`
- Original benchmark seed description: `/root/original_task_description.txt`

## Goal

Produce a clean public bus detour notice packet: for every notice group in
`notices.json`, build the five public pages in order, with dynamic page numbers,
bookmarks and metadata, using the same workflow as parent task 037.

## Required Pages (per group)

1. `Public Bus Detour Notice Packet` (cover, portrait)
2. `Corrected Detour Summary` (portrait)
3. `Stop Closure and Shuttle Matrix` (landscape)
4. `Rider Communication Timeline` (portrait)
5. `Release Checklist` (portrait)

## Required Corrections

Per group, use only the corrected public facts declared in `notices.json`
(route, closure/reopening dates, closed-stop count, shuttle headway, public
contact). Remove `DRAFT`, `PRIVATE`, and the draft wrong values (`Route 21`,
wrong dates, `7 stops`, `30 minutes`, `operator personal phone`, `do not post`).

## Output Requirements

- Save to `/root/submission/docops_v2_l3_037_pdf_bus_detour_notice_layout_repair_output_u20.pdf`.
- Do not modify the source document in place.
- Keep the output format the same as the input document (`.pdf`).
- Complete the full ordered workflow, not just local text replacement.
