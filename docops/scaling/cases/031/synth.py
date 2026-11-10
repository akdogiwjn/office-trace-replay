"""Synthetic PDF 031 inputs: scaled public-hearing release packet variants.

The frozen parent 031 builder does NOT repair the seed PDF page by page; it
generates a fresh ReportLab public-hearing release packet and then finalizes
bookmarks/metadata with pypdf. This variant therefore defines scale with a
frozen structured notice declaration (``notices.json``) that drives the actual
build: every declared hearing group produces the same five public page types
(cover, corrected summary, comment category matrix, response workflow, release
controls and appendix index) through the real drawing functions. 5 groups -> 25
pages, 20 groups -> 100 pages.

Like the frozen parent input, the synthetic input PDF is an artifact only (the
builder never reads it for content): it is kept small on purpose and the task
metadata records that the build is driven by ``notices.json``.

Generation is byte-deterministic for a fixed seed/params.
"""
from __future__ import annotations

import random
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .. import common

PAGES_PER_GROUP = 5

PAGE_TITLES = [
    "Public Hearing Packet: Zoning Amendment Comments",
    "Corrected Hearing Summary",
    "Comment Category Matrix",
    "Response Workflow",
    "Release Controls and Appendix Index",
]

CATEGORIES = [
    ("Land use and density", "Building form, height, and site transitions",
     "Planning review"),
    ("Transportation and access", "Access, parking, circulation, and transit",
     "Mobility review"),
    ("Housing supply", "Housing type, supply, and affordability",
     "Housing review"),
    ("Environment and stormwater", "Stormwater, tree canopy, and site impacts",
     "Environmental review"),
    ("Infrastructure and services", "Utilities, schools, and community services",
     "Infrastructure review"),
    ("Process and notification", "Notice, meeting access, and comment submission",
     "Public engagement"),
]

WORKFLOW_STEPS = [
    ("01", "Comment intake",
     "Log each submission under the public docket with a receipt reference."),
    ("02", "Category assignment",
     "Assign one primary category from the public matrix on the previous page."),
    ("03", "Issue review",
     "Route the issue to the relevant review lane for a factual response."),
    ("04", "Public update",
     "Publish a consolidated response through the public hearing channel."),
    ("05", "Record close",
     "Index the final response package and confirm the public deadline."),
]

CONTROLS = [
    "No active form fields",
    "No annotations or attachments",
    "No script actions",
    "Public-only metadata",
    "Five-page sequence verified",
    "Outline and page numbers verified",
    "Restricted identifiers excluded",
    "Public contact consolidated",
]

HEARING_DATES = ["2026-03-05", "2026-03-07", "2026-03-10", "2026-03-12",
                 "2026-03-14", "2026-03-17", "2026-03-19", "2026-03-21",
                 "2026-03-24", "2026-03-26", "2026-03-28", "2026-03-31"]
DEADLINES = ["2026-09-03", "2026-09-08", "2026-09-10", "2026-09-15",
             "2026-09-17", "2026-09-22", "2026-09-24", "2026-09-29"]

# Frozen draft wrong values (the exact values the parent draft packet carried).
FORBIDDEN_DRAFT = {
    "hearing_date": "2026-03-04",
    "comment_total": "112 comments",
    "response_deadline": "2026-09-01",
    "contact": "Vivian Holt",
    "private_reviewer": "private reviewer",
}


def split_comment_counts(total: int, rng: random.Random) -> list[int]:
    """Six primary categories whose counts sum to ``total`` (never 112)."""
    while True:
        counts = []
        remaining = total
        for _ in range(5):
            if remaining <= 0:
                counts.append(0)
                continue
            max_c = max(1, remaining - (5 - len(counts)))
            c = rng.randint(1, max_c)
            counts.append(c)
            remaining -= c
        counts.append(max(remaining, 0))
        if sum(counts) == total and 112 not in counts:
            return counts


def make_hearing_group(index: int, rng: random.Random) -> dict:
    docket = f"ZA-2026-{index + 1:03d}"
    hearing_date = rng.choice(HEARING_DATES)
    response_deadline = rng.choice(DEADLINES)
    comment_total = rng.choice([t for t in range(96, 171) if t != 112])
    counts = split_comment_counts(comment_total, rng)

    page_start = index * PAGES_PER_GROUP + 1
    categories = []
    for (name, focus, lane), count in zip(CATEGORIES, counts):
        share = round(count * 100.0 / comment_total, 1)
        categories.append({
            "name": name,
            "count": count,
            "share": f"{share:.1f}%",
            "focus": focus,
            "lane": lane,
        })

    workflow = [
        {"number": number, "step": step, "body": body}
        for number, step, body in WORKFLOW_STEPS
    ]

    appendix = [
        {"index": "A", "section": "Hearing particulars", "page": page_start + 1},
        {"index": "B", "section": "Comment category matrix", "page": page_start + 2},
        {"index": "C", "section": "Response workflow", "page": page_start + 3},
        {"index": "D", "section": "Release record", "page": page_start + 4},
    ]
    packet_contents = [
        {"number": "01", "title": "Corrected Hearing Summary", "page": page_start + 1},
        {"number": "02", "title": "Comment Category Matrix", "page": page_start + 2},
        {"number": "03", "title": "Response Workflow", "page": page_start + 3},
        {"number": "04", "title": "Release Controls and Appendix Index",
         "page": page_start + 4},
    ]

    top = max(counts, key=lambda c: c)
    top_name = categories[counts.index(top)]["name"]

    return {
        "id": docket,
        "page_start": page_start,
        "hearing_date": hearing_date,
        "comment_total": comment_total,
        "response_deadline": response_deadline,
        "contact": "Public Hearing Desk",
        "categories": categories,
        "workflow": workflow,
        "controls": list(CONTROLS),
        "appendix": appendix,
        "packet_contents": packet_contents,
        "summary_note": (f"Consolidated public hearing record for {docket}: the "
                         f"corrected date, deduplicated comment total, response "
                         f"deadline, and public contact are used consistently "
                         f"throughout this packet."),
        "feedback_note": (f"Each of the {comment_total} comments is assigned to "
                          f"one primary category. {top_name} is the largest "
                          f"group ({top}; {categories[counts.index(top)]['share']}), "
                          f"and every category is answered through its follow-up "
                          f"lane on the matrix page."),
        "draft_wrong": dict(FORBIDDEN_DRAFT),
    }


def make_notices(variant_id: str, out_dir: Path) -> dict:
    v = common.VARIANTS[variant_id]
    n = v["scale"]["groups"]
    seed = v["seed"]
    rng = random.Random(seed)
    groups = [make_hearing_group(i, rng) for i in range(n)]
    data = {
        "schema": "docops-scaling-notices-v1",
        "variant_task_id": variant_id,
        "seed": seed,
        "pages_per_group": PAGES_PER_GROUP,
        "page_titles": list(PAGE_TITLES),
        "groups": groups,
    }
    common.write_json(out_dir / "notices.json", data)
    return data


def write_input_pdf(out_dir: Path, input_name: str) -> Path:
    """Small deterministic draft seed PDF (artifact only; the builder does not
    read it for content). Mirrors the parent input being an unread draft that
    carried the frozen draft values."""
    output = out_dir / input_name
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter, pageCompression=1)
    width, height = letter
    c.setFillColorRGB(0.043137, 0.239216, 0.568627)
    c.rect(0, height - 40, width, 40, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(42, height - 28, "DRAFT Public Hearing Packet")
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont("Helvetica", 10)
    lines = [
        "PRIVATE staff draft: docket ZA-2026-041.",
        "Wrong draft facts: hearing 2026-03-04, 112 comments, deadline 2026-09-01,",
        "Vivian Holt, Marco Ruiz, 555-0198, personal phone, legal hold.",
        "INTERNAL deliberation, unreleased review notes, do not publish.",
        "Page one of the synthetic draft seed (the scaled builder is driven by",
        "notices.json and never reads this file for content).",
    ]
    y = height - 80
    for line in lines:
        c.drawString(42, y, line)
        y -= 16
    for page in range(2, 6):
        c.showPage()
        c.setFillColorRGB(0.043137, 0.239216, 0.568627)
        c.rect(0, height - 40, width, 40, stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(42, height - 28, f"DRAFT Public Hearing Packet - page {page}")
    c.showPage()
    c.save()
    data = buf.getvalue()
    # ReportLab embeds a random /ID trailer and current CreationDate/ModDate;
    # pin them so the artifact is byte-deterministic for the same seed/params.
    import re as _re
    data = _re.sub(rb"/ID\s*\[<[0-9a-fA-F]{32}><[0-9a-fA-F]{32}>\]",
                   b"/ID [<deadbeefdeadbeefdeadbeefdeadbeef>"
                   b"<deadbeefdeadbeefdeadbeefdeadbeef>]",
                   data)
    data = _re.sub(rb"/CreationDate \(D:[^)]*\)",
                   b"/CreationDate (D:20261102000000+00'00')", data)
    data = _re.sub(rb"/ModDate \(D:[^)]*\)",
                   b"/ModDate (D:20261102000000+00'00')", data)
    output.write_bytes(data)
    return output


def generate(variant_id: str, out_dir: Path, write_raw_records: bool = True) -> dict:
    v = common.VARIANTS[variant_id]
    n = v["scale"]["groups"]
    out_dir.mkdir(parents=True, exist_ok=True)
    data = make_notices(variant_id, out_dir)
    groups = data["groups"]

    input_name = (
        f"docops_v2_l3_031_pdf_public_hearing_packet_flatten_release_input_"
        f"{v['output_suffix']}.pdf"
    )
    input_path = write_input_pdf(out_dir, input_name)
    notices_path = out_dir / "notices.json"

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
        "pages": n * PAGES_PER_GROUP,
        "pages_per_group": PAGES_PER_GROUP,
        "page_titles": list(PAGE_TITLES),
        "group_ids": [g["id"] for g in groups],
        "unique_group_ids": len({g["id"] for g in groups}),
        "hearing_dates": [g["hearing_date"] for g in groups],
        "response_deadlines": [g["response_deadline"] for g in groups],
        "comment_totals": [g["comment_total"] for g in groups],
        "input_pages": 5,
        "output_pages": n * PAGES_PER_GROUP,
        "render_pages": n * PAGES_PER_GROUP,
        "render_images": n * PAGES_PER_GROUP,
        "render_dpi": 144,
        "bookmarks": n * PAGES_PER_GROUP,
        "page_labels": 0,
        "first_group": {
            "id": first["id"], "hearing_date": first["hearing_date"],
            "comment_total": first["comment_total"],
            "response_deadline": first["response_deadline"]},
        "middle_group": {
            "id": middle["id"], "hearing_date": middle["hearing_date"],
            "comment_total": middle["comment_total"],
            "response_deadline": middle["response_deadline"]},
        "last_group": {
            "id": last["id"], "hearing_date": last["hearing_date"],
            "comment_total": last["comment_total"],
            "response_deadline": last["response_deadline"]},
        "input_bytes": input_path.stat().st_size,
        "input_sha256": common.sha256_file(input_path),
        "notices_json_sha256": common.sha256_file(notices_path),
        "seed": v["seed"],
        "parameterized": (
            "Fixed scope of five public page types per hearing group is "
            "parameterized over all groups: global page numbers, footers "
            "'page / total', appendix and packet-content page targets and "
            "bookmark targets are absolute across the whole packet."
        ),
        "preserved_parent_behavior": (
            "144 DPI pdftoppm page rendering; Letter portrait pages; public "
            "metadata model; ReportLab page construction finalized with pypdf "
            "bookmarks/metadata; no AcroForm/annotation handling is introduced "
            "(the parameterized rebuild neither reads nor writes AcroForm "
            "structures)."
        ),
        "changed_parent_behavior": (
            "The builder iterates every notices.json hearing group through the "
            "real five-page drawing functions instead of building a single "
            "fixed docket; pages are never duplicated from a 5-page base."
        ),
    }

    meta = common.default_task_metadata(variant_id)
    meta["scale_metadata"] = scale_metadata
    meta["input_path"] = f"/root/{input_name}"
    meta["output_path"] = (
        f"/root/submission/"
        f"docops_v2_l3_031_pdf_public_hearing_packet_flatten_release_output_"
        f"{v['output_suffix']}.pdf"
    )
    meta["modified_workflow"] = [
        "01 build: page sizes, portrait rules, fonts, drawing helpers and "
        "pageCompression are unchanged; the builder iterates notices.json "
        "hearing groups (5 pages per group), global page numbers, footers and "
        "bookmark targets are computed over all groups",
        "02 render: unchanged pdftoppm -png -r 144 over the output PDF",
        "03 validate: dynamic validator reads frozen expected.json and checks "
        "every group's pages, facts, bookmarks and forbidden tokens",
    ]
    meta["measurement_scope"] = (
        "Scales the number of frozen structured hearing groups that drive "
        "actual ReportLab page construction and pypdf bookmark/metadata "
        "finalization. 5 groups -> 25 pages, 20 groups -> 100 pages. All units "
        "enter the build functions; pages are never duplicated from a 5-page "
        "base. The synthetic input PDF is an artifact only and is not read by "
        "the builder."
    )
    common.write_json(out_dir / "task_metadata.json", meta)
    (out_dir / "instruction.md").write_text(instruction_md(meta), encoding="utf-8")
    (out_dir / "original_task_description.txt").write_text(
        original_description(meta), encoding="utf-8")

    return {
        "input": input_path,
        "notices": notices_path,
        "task_metadata": out_dir / "task_metadata.json",
        "scale_metadata": scale_metadata,
    }


def instruction_md(meta: dict) -> str:
    v = common.VARIANTS[meta["variant_task_id"]]
    sm = meta["scale_metadata"]
    return f"""# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`031`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 031 (frozen `docops_v2_l3_031_pdf_public_hearing_packet_flatten_release`)
- `synthetic`: true
- generator: {meta['generator']} (version {meta['generator_version']})
- seed: {meta['seed']}
- scale: {sm['groups']} hearing groups -> {sm['pages']} pages
- pages per group: {sm['pages_per_group']}

## Scale definition (explicit)

This variant defines scale by the number of **frozen structured hearing groups**
in `notices.json`. Each group is actually built through the real ReportLab page
drawing functions (cover, corrected hearing summary, comment category matrix,
response workflow, release controls and appendix index), then finalized with
pypdf bookmarks/metadata and rendered at 144 DPI PNG. Pages are never duplicated
from a small base packet.

The synthetic input PDF `{meta['input_path']}` is an artifact only: like the
frozen parent input, the builder does not read it for content. Do not treat its
page count as the scale definition.

## Inputs

- Source document: `{meta['input_path']}` (artifact; not read by the builder)
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

- Save to `{meta['output_path']}`.
- Do not modify the source document in place.
- Keep the output format the same as the input document (`.pdf`).
- Complete the full ordered workflow, not just local text replacement.
"""


def original_description(meta: dict) -> str:
    sm = meta["scale_metadata"]
    return (
        "Synthetic scale variant of frozen task 031: public hearing comment "
        "packet flattening and release cleanup. Scale is defined by the number "
        "of frozen structured hearing groups in notices.json: "
        f"{sm['groups']} groups -> {sm['pages']} pages. Each group is "
        "built through the real ReportLab page functions; the synthetic input "
        "PDF is an artifact only and is not read by the builder. Variant "
        f"{meta['variant_task_id']}, seed {meta['seed']}. This is a synthetic "
        "input, not a historical benchmark task."
    )
