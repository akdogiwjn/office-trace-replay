# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`021`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 021 (frozen `docops_v2_l3_021_pptx_shelter_accessibility_public_remediation`)
- `synthetic`: true
- generator: docops/scaling/cases/021/synth.py (version 1.0)
- seed: 2026110503
- scale: {'regions': 5, 'pages': 40} regions -> 200 output pages
- pages per region: 8

## Inputs

- Source presentation: `/root/docops_v2_l3_021_pptx_shelter_accessibility_public_remediation_input_g5.pptx`
- Prepared region material: `/root/tmp/docs/regions.json`
- Original benchmark seed description: `/root/original_task_description.txt`

## Goal

Prepare a clean accessible public emergency shelter briefing deck from a messy
internal accessibility review presentation, one 8-page public region group per
region in `regions.json`, using the same sequential workflow as parent task 021.

## Required Sequential Workflow

1. Remove internal-only slides, hidden off-slide content, confidential notes,
   and staff-only links.
2. Apply the correction memo before rebuilding public counts, tables, contact
   details, and the update log (per region).
3. Rebuild the public deck by iterating regions from `regions.json`; every
   region produces 8 public slides in the required slide order.
4. Add meaningful alt text to the key visual on every slide.
5. Replace broken or internal hyperlinks with public links (per region).
6. Apply the required visual style, footer, speaker-note cleanup, and table
   styling on every slide.

## Output Requirements

- Save to `/root/submission/docops_v2_l3_021_pptx_shelter_accessibility_public_remediation_output_g5.pptx`.
- Do not modify the source presentation in place.
- Keep the output format the same as the input presentation (`.pptx`).
- Complete the full ordered workflow, not just local text replacement.


## Measurement scope

This variant measures **per-region document generation, validation, conversion
and rendering scale** (regions -> 8 public slides each). The synthetic source
presentation's own page count is NOT what this variant parses or repairs; it
does NOT claim to measure a larger source-PPT parse or cleanup cost. Distinguish
input PPTX pages vs region count vs expected output pages.
