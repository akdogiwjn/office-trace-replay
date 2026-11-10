# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`pdfwf005`. It is NOT a historical benchmark task and has no official score of
its own.

## Provenance

- `parent_task`: pdfwf005 (frozen `pdfwf_005_closeout_binder_page_labels_and_bookmarks_seed`)
- `synthetic`: true
- generator: docops/scaling/cases/pdfwf005/synth.py (version 1.0)
- seed: 2026110616
- scale: 20 binder groups -> 140 input pages / 120 output pages
- pages per group: 7 (6 live pages per group)

## Scale definition (explicit)

This variant defines scale by the number of **binder groups** in `groups.json`.
Each group is a real 7-page input block (6 live pages carrying a "Draft: "
prefix plus one "Obsolete Divider" page). The builder REALLY reads the input
PDF: per group it removes the "Draft: " prefixes, deletes the obsolete divider
page, reorders the six live pages, adds bookmarks (pointing to correct absolute
page numbers) and page labels (the visible section titles), and preserves
metadata. Live pages are never duplicated.

## Inputs

- Source document: `/root/pdfwf_005_closeout_binder_page_labels_and_bookmarks_seed_u20.pdf` (real multi-page PDF, read by the builder)
- Prepared group declaration: `/root/tmp/docs/groups.json`
- Frozen expected oracle: `/root/tmp/docs/expected.json`
- Original benchmark seed description: `/root/original_task_description.txt`

## Goal

Rebuild the live closeout binder from the marked working draft: remove visible
`Draft:` prefixes, delete each group's obsolete divider page, restore the live
pages to `Cover`, `Meeting Log`, `Binder Index`, `Approved Exhibit`,
`Appendix A`, `Appendix B`, and add bookmarks and page labels for every live
page.

## Required Outputs (per group)

- 6 live pages in the requested order with no `Draft:` residual.
- No `Obsolete Divider` page anywhere in the output.
- A bookmark for every live page pointing to the correct absolute page.
- A page label equal to the visible section title for every live page.
- Input metadata preserved (with `/Title` = `Closeout Binder`).

## Output Requirements

- Save to `/root/submission/pdfwf_005_closeout_binder_page_labels_and_bookmarks_seed_u20.pdf`.
- Do not modify the source document in place.
- Keep the output format the same as the input document (`.pdf`).
- Complete the full ordered workflow, not just local text replacement.
