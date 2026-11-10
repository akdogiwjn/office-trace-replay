"""Synthetic PPTX 021 inputs: scaled shelter accessibility briefing variants.

Produces the per-region prepared material (regions.json) and a messy internal
source presentation that contains, for every region, the to-be-fixed content
(DRAFT/PRIVATE markers, wrong raw shelter/accessible counts, staff phone,
internal EOC link, confidential notes, off-slide shapes). The public builder
reads regions.json and drives output size from the region count.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

from .. import common

PAGES_PER_REGION = 8

REGION_NAMES_G5 = [
    "North District", "South District", "East District", "West District", "Central District",
]
REGION_NAMES_G10 = REGION_NAMES_G5 + [
    "River District", "Hill District", "Lake District", "Harbor District", "Valley District",
]

TRANSIT_SERVICES = ["Paratransit", "Bus Route 4", "Bus Route 9", "Accessible shuttle",
                    "Night shuttles", "Cross-town bus", "Commuter rail", "Airport link"]

BANNED = [
    "DRAFT", "PRIVATE", "INTERNAL", "staff-only", "personal phone", "555-0199",
    "emergency operations center", "do not publish", "internal.example", "eoc.internal",
    "16 shelters", "11 wheelchair",
]


def _slug(name: str) -> str:
    return name.lower().replace(" ", "-").replace("'", "")


def make_regions(rng, names: list[str]) -> list[dict]:
    regions = []
    for index, name in enumerate(names):
        slug = _slug(name)
        shelter = rng.randint(10, 18)
        accessible = max(int(round(shelter * rng.uniform(0.55, 0.85))), 1)
        accessible = min(accessible, shelter)
        hotline = f"1-800-555-{140 + index:04d}"
        regions.append({
            "id": slug,
            "name": name,
            "slug": slug,
            "shelter_count": shelter,
            "accessible_count": accessible,
            "raw_shelter_count": shelter - 2,
            "raw_accessible_count": accessible - 3,
            "hotline": hotline,
            "website": f"https://city.example/{slug}/public",
            "email": f"accessibility-{slug}@city.example",
            "update_date": "2026-07-20",
            "transit_updates": [
                [service, "Priority return trips added" if index % 2 == 0 else "Extended weekend service"]
                for service in rng.sample(TRANSIT_SERVICES, 4)
            ],
        })
    return regions


def write_regions(variant_id: str, regions: list[dict], out_dir: Path) -> Path:
    data = {
        "schema": "docops-scaling-regions-v1",
        "variant_task_id": variant_id,
        "seed": common.VARIANTS[variant_id]["seed"],
        "pages_per_region": PAGES_PER_REGION,
        "regions": regions,
    }
    common.write_json(out_dir / "regions.json", data)
    return out_dir / "regions.json"


def write_source_pptx(regions: list[dict], out_dir: Path, output_name: str) -> Path:
    """Messy internal review deck: one internal slide + off-slide + notes per region."""
    import datetime as _dt
    import tempfile

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    prs.core_properties.created = _dt.datetime(2026, 1, 1, 0, 0, 0)
    prs.core_properties.modified = _dt.datetime(2026, 1, 1, 0, 0, 0)
    blank = prs.slide_layouts[6]
    for region in regions:
        slide = prs.slides.add_slide(blank)
        title = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(8), Inches(0.6))
        title.text_frame.text = f"{region['name']} INTERNAL REVIEW DRAFT"
        facts = slide.shapes.add_textbox(Inches(0.5), Inches(1.2), Inches(9), Inches(2.2))
        facts.text_frame.text = (
            f"shelters: {region['raw_shelter_count']} (PRIVATE draft value)\n"
            f"wheelchair accessible: {region['raw_accessible_count']} (PRIVATE draft value)\n"
            f"staff phone: 555-0199 (personal phone)\n"
            f"internal site: http://internal.example/eoc (eoc.internal, do not publish)\n"
            f"emergency operations center note: unverified closure rumor\n"
        )
        hidden = slide.shapes.add_textbox(Inches(20), Inches(20), Inches(2), Inches(2))
        hidden.text_frame.text = (
            f"off-slide: {region['name']} staff-only counts "
            f"raw {region['raw_shelter_count']} / accessible {region['raw_accessible_count']}"
        )
        notes = slide.notes_slide
        notes.notes_text_frame.text = (
            f"staff-only: internal review for {region['name']}. "
            "emergency operations center draft, do not publish."
        )
    output = out_dir / output_name
    fd, temp_name = tempfile.mkstemp(suffix=".pptx", dir=out_dir)
    import os as _os
    _os.close(fd)
    prs.save(temp_name)
    try:
        common.deterministic_zip(temp_name, output)
    finally:
        Path(temp_name).unlink(missing_ok=True)
    return output


def generate(variant_id: str, out_dir: Path) -> dict:
    v = common.VARIANTS[variant_id]
    regions_count = v["scale"]["regions"]
    rng = random.Random(v["seed"])
    names = REGION_NAMES_G10 if regions_count == 10 else REGION_NAMES_G5[:regions_count]
    regions = make_regions(rng, names)
    for region in regions:
        assert region["accessible_count"] <= region["shelter_count"]
        assert 0 < region["accessible_count"] <= 18 and 0 < region["shelter_count"] <= 18

    out_dir.mkdir(parents=True, exist_ok=True)
    regions_path = write_regions(variant_id, regions, out_dir)
    input_name = f"docops_v2_l3_021_pptx_shelter_accessibility_public_remediation_input_{v['output_suffix']}.pptx"
    input_path = write_source_pptx(regions, out_dir, input_name)

    scale_metadata = {
        "regions": regions_count,
        "pages": regions_count * PAGES_PER_REGION,
        "pages_per_region": PAGES_PER_REGION,
        "shelter_counts": [r["shelter_count"] for r in regions],
        "accessible_counts": [r["accessible_count"] for r in regions],
        "accessible_le_shelter": all(r["accessible_count"] <= r["shelter_count"] for r in regions),
        "input_bytes": input_path.stat().st_size,
        "input_sha256": common.sha256_file(input_path),
        "regions_json_sha256": common.sha256_file(regions_path),
        "seed": v["seed"],
        "source_must_contain": BANNED,
    }

    meta = common.default_task_metadata(variant_id)
    meta["scale_metadata"] = scale_metadata
    meta["input_path"] = f"/root/{input_name}"
    meta["output_path"] = (
        f"/root/submission/docops_v2_l3_021_pptx_shelter_accessibility_public_remediation_output_{v['output_suffix']}.pptx"
    )
    meta["modified_workflow"] = [
        "01 prepare_render_fonts: unchanged font-prep step",
        "02 build_validate_render: builder reads regions.json and iterates regions "
        "(8 public slides per region); validate checks every slide against frozen "
        "expected.json; contact sheets grouped by region (8 pages each) with "
        "numeric zero-padded filename sorting instead of fixed slide-{1..8}.jpg",
    ]
    meta["measurement_scope"] = (
        "Measures per-region document generation, validation, conversion and "
        "rendering scale: regions -> 8 public slides each (5 -> 40, 10 -> 80). "
        "The synthetic source PPTX page count is NOT what this variant parses or "
        "repairs; this variant does NOT measure a larger source-PPT parse/cleanup "
        "cost. Distinguish input PPTX pages vs region count vs expected output pages."
    )
    common.write_json(out_dir / "task_metadata.json", meta)
    (out_dir / "instruction.md").write_text(instruction_md(meta), encoding="utf-8")
    (out_dir / "original_task_description.txt").write_text(original_description(meta), encoding="utf-8")

    return {
        "input": input_path,
        "regions": regions_path,
        "task_metadata": out_dir / "task_metadata.json",
        "scale_metadata": scale_metadata,
    }


def instruction_md(meta: dict) -> str:
    v = common.VARIANTS[meta["variant_task_id"]]
    return f"""# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`021`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 021 (frozen `docops_v2_l3_021_pptx_shelter_accessibility_public_remediation`)
- `synthetic`: true
- generator: {meta['generator']} (version {meta['generator_version']})
- seed: {meta['seed']}
- scale: {meta['scale']} regions -> {meta['scale']['regions'] * meta['scale'].get('pages', 1)} output pages
- pages per region: {meta['scale_metadata']['pages_per_region']}

## Measurement scope

This variant measures **per-region document generation, validation, conversion
and rendering scale** (regions -> 8 public slides each). The synthetic source
presentation's own page count is NOT what this variant parses or repairs; it
does NOT claim to measure a larger source-PPT parse or cleanup cost. Distinguish
input PPTX pages vs region count vs expected output pages.

## Inputs

- Source presentation: `{meta['input_path']}`
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

- Save to `{meta['output_path']}`.
- Do not modify the source presentation in place.
- Keep the output format the same as the input presentation (`.pptx`).
- Complete the full ordered workflow, not just local text replacement.
"""


def original_description(meta: dict) -> str:
    return (
        "Synthetic scale variant of frozen task 021: public emergency shelter "
        "accessibility briefing remediation. Source contains internal slides, "
        "hidden off-slide private content, wrong shelter accessibility counts, "
        "staff-only links, missing alt text, broken hyperlinks, and confidential "
        "speaker notes. Scale is defined by the number of regions; each region "
        "produces 8 public slides. "
        f"Variant {meta['variant_task_id']}, seed {meta['seed']}, "
        f"{meta['scale_metadata']['regions']} regions -> {meta['scale_metadata']['pages']} pages. "
        "This is a synthetic input, not a historical benchmark task."
    )
