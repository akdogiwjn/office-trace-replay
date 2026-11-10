"""Synthetic PDF pdfwf005 inputs: scaled closeout-binder rebuild variants.

The frozen parent pdfwf005 builder REALLY reads the seed PDF: it strips the
visible "Draft: " prefix from every live page, deletes the obsolete divider
page, restores the six live pages to their requested order, adds bookmarks and
page labels, and preserves metadata. This variant defines scale with a real
multi-page input PDF (drawn from scratch with pypdf) and a frozen structured
declaration (``groups.json``) that records every group's live titles, obsolete
page index, draft-prefix fact and the bookmark/page-label expectations.

Each group is a 7-page block (6 live pages carrying a "Draft: " prefix plus one
"Obsolete Divider" page). 5 groups -> 35 input pages / 30 output pages,
20 groups -> 140 input pages / 120 output pages.

Generation is byte-deterministic for a fixed seed/params.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from .. import common

PAGES_PER_GROUP = 7
LIVE_PAGES_PER_GROUP = 6
DRAFT_PREFIX = "Draft: "
OBSOLETE_TITLE = "Obsolete Divider"

# Source page order inside one 7-page group (1-based), mirroring the frozen
# parent seed where Appendix B lived on page 1 and the obsolete divider on
# page 7.
SOURCE_LAYOUT = {
    "Cover": 2,
    "Meeting Log": 3,
    "Binder Index": 4,
    "Approved Exhibit": 5,
    "Appendix A": 6,
    "Appendix B": 1,
    "Obsolete Divider": 7,
}

LIVE_ORDER = ["Cover", "Meeting Log", "Binder Index", "Approved Exhibit",
              "Appendix A", "Appendix B"]

# Physical page order inside one 7-page source block, derived from the frozen
# source layout (position 1 = Appendix B, 7 = Obsolete Divider).
SOURCE_ORDER = [title for title, _ in sorted(
    SOURCE_LAYOUT.items(), key=lambda item: item[1])]

PAGE_BODIES = {
    "Cover": ["Closeout Binder", "Page labels refreshed", "Bookmarks rebuilt"],
    "Meeting Log": ["Meeting log for the closeout binder."],
    "Binder Index": ["Binder index is now in final order."],
    "Approved Exhibit": ["Approved exhibit remains unchanged."],
    "Appendix A": ["Appendix A contains the reference list."],
    "Appendix B": ["Appendix B contains the completion log."],
    "Obsolete Divider": ["Superseded draft page. Remove this page from the final packet."],
}


def _font_resource():
    font = DictionaryObject()
    font.update({NameObject("/Type"): NameObject("/Font"),
                 NameObject("/Subtype"): NameObject("/Type1"),
                 NameObject("/BaseFont"): NameObject("/Helvetica"),
                 NameObject("/Encoding"): NameObject("/WinAnsiEncoding")})
    res = DictionaryObject()
    res[NameObject("/Font")] = DictionaryObject({NameObject("/F1"): font})
    return res


def _text_stream(data: bytes):
    stream = DecodedStreamObject()
    stream.set_data(data)
    return stream


def make_group(index: int) -> dict:
    group_id = f"GRP-{index + 1:03d}"
    live_titles = list(LIVE_ORDER)
    source_index_for_title = dict(SOURCE_LAYOUT)
    del source_index_for_title[OBSOLETE_TITLE]
    return {
        "group_id": group_id,
        "binder_title": "Closeout Binder",
        "live_titles": live_titles,
        "source_index_for_title": source_index_for_title,
        "obsolete_page_index": SOURCE_LAYOUT[OBSOLETE_TITLE],
        "obsolete_title": OBSOLETE_TITLE,
        "draft_prefix": DRAFT_PREFIX,
        "draft_prefix_fact": f"all {LIVE_PAGES_PER_GROUP} live pages carry a "
                             f"{DRAFT_PREFIX!r} prefix in the source input",
        "bookmark_labels": [f"{group_id} | {title}" for title in live_titles],
        "page_label_prefixes": list(live_titles),
        "required_lines": {title: list(PAGE_BODIES[title])
                           for title in live_titles},
    }


def write_input_pdf(out_dir: Path, input_name: str, groups: list[dict]) -> Path:
    """Real multi-page input PDF drawn from scratch with pypdf.

    Every group is a 7-page block: 6 live pages titled with a "Draft: " prefix
    plus one "Obsolete Divider" page, in the frozen source order."""
    output = out_dir / input_name
    writer = PdfWriter()
    for group in groups:
        for title in SOURCE_ORDER:
            body_lines = PAGE_BODIES[title]
            text = "\n".join([f"{DRAFT_PREFIX}{title}"] + body_lines)
            page = writer.add_blank_page(595.2756, 841.8898)
            content = _text_stream((
                "BT\n/F1 18 Tf\n60 700 Td\n"
                + "\n0 -28 Td\n".join(f"({line}) Tj"
                                       for line in text.split("\n"))
                + "\nET\n").encode("utf-8"))
            writer._add_object(content)
            page[NameObject("/Contents")] = content
            page[NameObject("/Resources")] = _font_resource()
    writer.add_metadata({
        "/Title": "Closeout Binder (working draft)",
        "/Author": "anonymous",
        "/Creator": "anonymous",
        "/Subject": "working draft",
        "/Keywords": "draft",
        "/Producer": "ReportLab PDF Library - (opensource)",
        "/CreationDate": "D:20260509203052+08'00'",
        "/ModDate": "D:20260509203052+08'00'",
    })
    with output.open("wb") as handle:
        writer.write(handle)
    return output


def make_groups(variant_id: str, out_dir: Path) -> dict:
    v = common.VARIANTS[variant_id]
    n = v["scale"]["groups"]
    groups = [make_group(i) for i in range(n)]
    data = {
        "schema": "docops-scaling-groups-v1",
        "variant_task_id": variant_id,
        "seed": v["seed"],
        "pages_per_group": PAGES_PER_GROUP,
        "live_pages_per_group": LIVE_PAGES_PER_GROUP,
        "draft_prefix": DRAFT_PREFIX,
        "obsolete_title": OBSOLETE_TITLE,
        "source_layout": dict(SOURCE_LAYOUT),
        "live_order": list(LIVE_ORDER),
        "groups": groups,
    }
    common.write_json(out_dir / "groups.json", data)
    return data


def generate(variant_id: str, out_dir: Path, write_raw_records: bool = True) -> dict:
    v = common.VARIANTS[variant_id]
    n = v["scale"]["groups"]
    out_dir.mkdir(parents=True, exist_ok=True)
    data = make_groups(variant_id, out_dir)
    groups = data["groups"]

    input_name = (
        f"pdfwf_005_closeout_binder_page_labels_and_bookmarks_seed_"
        f"{v['output_suffix']}.pdf"
    )
    input_path = write_input_pdf(out_dir, input_name, groups)
    groups_path = out_dir / "groups.json"

    if write_raw_records:
        common.write_json(
            out_dir / "raw_records.json",
            {"schema": "docops-scaling-raw-records-v1",
             "variant_task_id": variant_id,
             "records": groups},
        )

    first, middle, last = groups[0], groups[n // 2], groups[-1]

    scale_metadata = {
        "groups": n,
        "pages_per_group": PAGES_PER_GROUP,
        "live_pages_per_group": LIVE_PAGES_PER_GROUP,
        "input_pages": n * PAGES_PER_GROUP,
        "output_pages": n * LIVE_PAGES_PER_GROUP,
        "render_pages": n * LIVE_PAGES_PER_GROUP,
        "render_images": n * LIVE_PAGES_PER_GROUP,
        "contact_sheet_images": 1,
        "render_dpi": 130,
        "montage_tile": "3x2",
        "montage_geometry": "+18+24",
        "montage_label": "%f",
        "group_ids": [g["group_id"] for g in groups],
        "unique_group_ids": len({g["group_id"] for g in groups}),
        "live_titles": list(LIVE_ORDER),
        "obsolete_title": OBSOLETE_TITLE,
        "first_group": {
            "group_id": first["group_id"],
            "live_titles": first["live_titles"],
            "obsolete_page_index": first["obsolete_page_index"],
        },
        "middle_group": {
            "group_id": middle["group_id"],
            "live_titles": middle["live_titles"],
            "obsolete_page_index": middle["obsolete_page_index"],
        },
        "last_group": {
            "group_id": last["group_id"],
            "live_titles": last["live_titles"],
            "obsolete_page_index": last["obsolete_page_index"],
        },
        "bookmarks": n * LIVE_PAGES_PER_GROUP,
        "page_labels": n * LIVE_PAGES_PER_GROUP,
        "input_bytes": input_path.stat().st_size,
        "input_sha256": common.sha256_file(input_path),
        "groups_json_sha256": common.sha256_file(groups_path),
        "seed": v["seed"],
        "parameterized": (
            "The fixed 7-page source block and 6-page live scope are "
            "parameterized over all groups: source page indexes, obsolete page "
            "indexes, absolute bookmark targets and page-label prefixes are "
            "computed over the whole scaled binder."
        ),
        "preserved_parent_behavior": (
            "130 DPI pdftoppm page rendering with montage 3x2, geometry +18+24 "
            "and -label %f contact sheet; page labels equal the visible section "
            "titles; input metadata preserved with /Title overridden to "
            "'Closeout Binder'; no AcroForm handling is introduced (the rebuild "
            "neither reads nor writes AcroForm structures)."
        ),
        "changed_parent_behavior": (
            "The builder iterates every groups.json group through the real "
            "read-strip-drop-reorder-labelling path instead of a single fixed "
            "7-page seed; live pages are never duplicated."
        ),
    }

    meta = common.default_task_metadata(variant_id)
    meta["scale_metadata"] = scale_metadata
    meta["input_path"] = f"/root/{input_name}"
    meta["output_path"] = (
        f"/root/submission/pdfwf_005_closeout_binder_page_labels_and_"
        f"bookmarks_seed_{v['output_suffix']}.pdf"
    )
    meta["modified_workflow"] = [
        "01 build_and_pdfinfo: unchanged; the builder iterates groups.json "
        "groups (7 source pages per group -> 6 live pages), removing the "
        "'Draft: ' prefix, dropping the obsolete divider, reordering live "
        "pages and adding bookmarks/page labels over the whole binder",
        "02 final_text: unchanged pdftotext -layout over the output PDF",
        "03 page_labels_and_bookmarks: unchanged pypdf page-label and outline "
        "dump, now spanning all scaled groups",
        "04 render_contact_sheet: unchanged pdftoppm -png -r 130 + one montage "
        "3x2 -label %f invocation over every retained live page; because the "
        "montage tile grid is 3x2 and the retained page count (30/120) exceeds "
        "6, ImageMagick writes one numbered contact-sheet tile "
        "(output-contact-0.png, ...) per 3x2 grid page instead of a single "
        "output-contact.png. The command lists all produced tiles; this is the "
        "same single tool invocation as the parent, scaled by page count",
        "05 forbidden_text_diagnostic: unchanged pdftotext | rg over the "
        "output PDF",
    ]
    meta["measurement_scope"] = (
        "Scales the number of frozen binder groups that actually flow through "
        "the real read/prefix-strip/obsolete-drop/reorder/bookmark/label "
        "rebuild. 5 groups -> 35 input / 30 output pages, 20 groups -> 140 "
        "input / 120 output pages. Every retained live page is rendered at "
        "130 DPI into the 3x2 contact sheet; pages are never duplicated."
    )
    common.write_json(out_dir / "task_metadata.json", meta)
    (out_dir / "instruction.md").write_text(instruction_md(meta), encoding="utf-8")
    (out_dir / "original_task_description.txt").write_text(
        original_description(meta), encoding="utf-8")

    return {
        "input": input_path,
        "groups": groups_path,
        "task_metadata": out_dir / "task_metadata.json",
        "scale_metadata": scale_metadata,
    }


def instruction_md(meta: dict) -> str:
    v = common.VARIANTS[meta["variant_task_id"]]
    sm = meta["scale_metadata"]
    return f"""# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`pdfwf005`. It is NOT a historical benchmark task and has no official score of
its own.

## Provenance

- `parent_task`: pdfwf005 (frozen `pdfwf_005_closeout_binder_page_labels_and_bookmarks_seed`)
- `synthetic`: true
- generator: {meta['generator']} (version {meta['generator_version']})
- seed: {meta['seed']}
- scale: {sm['groups']} binder groups -> {sm['input_pages']} input pages / {sm['output_pages']} output pages
- pages per group: {sm['pages_per_group']} (6 live pages per group)

## Scale definition (explicit)

This variant defines scale by the number of **binder groups** in `groups.json`.
Each group is a real 7-page input block (6 live pages carrying a "Draft: "
prefix plus one "Obsolete Divider" page). The builder REALLY reads the input
PDF: per group it removes the "Draft: " prefixes, deletes the obsolete divider
page, reorders the six live pages, adds bookmarks (pointing to correct absolute
page numbers) and page labels (the visible section titles), and preserves
metadata. Live pages are never duplicated.

## Inputs

- Source document: `{meta['input_path']}` (real multi-page PDF, read by the builder)
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

- Save to `{meta['output_path']}`.
- Do not modify the source document in place.
- Keep the output format the same as the input document (`.pdf`).
- Complete the full ordered workflow, not just local text replacement.
"""


def original_description(meta: dict) -> str:
    sm = meta["scale_metadata"]
    return (
        "Synthetic scale variant of frozen task pdfwf005: rebuild a closeout "
        "binder PDF. Scale is defined by the number of binder groups in "
        f"groups.json: {sm['groups']} groups -> {sm['input_pages']} input / "
        f"{sm['output_pages']} output pages. The builder really reads the input "
        "PDF, strips 'Draft: ' prefixes, drops obsolete dividers, reorders live "
        f"pages and rebuilds bookmarks/page labels. Variant "
        f"{meta['variant_task_id']}, seed {meta['seed']}. This is a synthetic "
        "input, not a historical benchmark task."
    )
