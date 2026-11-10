"""Synthetic PDF 037 inputs: scaled bus-detour notice packet variants.

The frozen parent 037 builder does NOT repair the seed PDF page by page; it
generates a fresh ReportLab packet and then finalizes bookmarks/metadata with
pypdf. This variant therefore defines scale with a frozen structured notice
declaration (``notices.json``) that drives the actual build: every declared
notice group produces the same five public page types (cover, corrected
summary, stop/shuttle matrix, rider communication timeline, release checklist)
through the real drawing functions. 5 groups -> 25 pages, 20 groups -> 100
pages.

This scale definition is explicit: the synthetic input PDF is an artifact only
(like the frozen parent input, the builder never reads it for content). It is
kept small on purpose and the task metadata records that the build is driven by
``notices.json``.

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

ROUTE_NUMBERS_U5 = [12, 18, 24, 30, 36]
ROUTE_NUMBERS_U20 = [12, 18, 24, 30, 36, 42, 48, 54, 60, 66, 72, 78, 84, 90,
                     96, 102, 108, 114, 120, 210]

AREA_NAMES = [
    "Northbank", "Market", "Civic", "Riverfront", "Harbor", "Central",
    "University", "Parkway", "Southbank", "Mill", "Station", "Airport",
    "Riverside", "Eastgate", "Westfield", "Oldtown", "Highland", "Lakeshore",
    "Greenway", "Sunset",
]
PLACE_NAMES = [
    "Library", "Square", "Terminal", "Plaza", "Exchange", "Campus",
    "Medical Center", "Mall", "Bridge", "Promenade", "Garage", "Stadium",
    "Museum", "Courthouse", "Post Office",
]
STREET_NAMES = ["Northbank Ave", "Market St", "Civic Center", "Pier Loop",
                "Bay St", "North Plaza", "West Gate", "Medical Campus",
                "Terminal Way", "Mill Crossing"]

PAGE_TITLES = [
    "Public Bus Detour Notice Packet",
    "Corrected Detour Summary",
    "Stop Closure and Shuttle Matrix",
    "Rider Communication Timeline",
    "Release Checklist",
]


def make_notice_group(index: int, route_number: int, rng: random.Random) -> dict:
    # All legal October dates avoid the frozen draft error dates 2026-10-13 and
    # 2026-10-27, and stop counts exclude 7, so the corrected public content can
    # never collide with the forbidden draft values.
    allowed_days = [3, 5, 8, 11, 15, 18, 21, 25, 28]
    closure_day = rng.choice(allowed_days[:-3])
    later = [d for d in allowed_days if d > closure_day]
    reopen_day = rng.choice(later[-2:]) if len(later) >= 2 else later[-1]
    mid_candidates = [d for d in allowed_days if closure_day < d < reopen_day]
    mid_day = mid_candidates[len(mid_candidates) // 2] if mid_candidates else closure_day + 3
    closure = f"2026-10-{closure_day:02d}"
    reopening = f"2026-10-{reopen_day:02d}"
    advance_day = closure_day - 7 if closure_day > 7 else 26
    advance_month = "09" if closure_day > 7 else "09"
    stop_count = rng.randint(8, 18)
    headway = rng.choice(["15 minutes", "10 minutes"])
    area = AREA_NAMES[index % len(AREA_NAMES)]
    place = PLACE_NAMES[(index * 3) % len(PLACE_NAMES)]
    street = STREET_NAMES[index % len(STREET_NAMES)]
    route_label = f"Route {route_number}"

    stops = []
    for i in range(1, stop_count + 1):
        stops.append({
            "id": f"{route_number}-{i:02d}",
            "name": f"{AREA_NAMES[(index + i) % len(AREA_NAMES)]} / "
                    f"{PLACE_NAMES[(index * 5 + i) % len(PLACE_NAMES)]}",
            "location": f"{STREET_NAMES[(index + i) % len(STREET_NAMES)]}",
            "boarding": (f"{AREA_NAMES[(index + i) % len(AREA_NAMES)]} - "
                         f"signed shuttle bay {i}"),
            "access": "Step-free",
        })

    return {
        "id": f"N-{index + 1:02d}",
        "route": route_label,
        "corridor": f"{area} bridge corridor",
        "closure_begins": closure,
        "reopening_target": reopening,
        "closed_stop_count": stop_count,
        "shuttle_headway": headway,
        "contact": "311 Transit Desk",
        "summary_note": (f"Corrected public service details for the {area} "
                         f"bridge closure, published for riders and customer "
                         f"information teams."),
        "stops": stops,
        "timeline": [
            {"date": f"2026-{advance_month}-{advance_day:02d}",
             "label": "Advance notice",
             "body": "Post stop notices and publish digital travel guidance."},
            {"date": closure, "label": "Closure begins",
             "body": f"Detour signs active; replacement shuttles run every "
                     f"{headway}."},
            {"date": f"2026-10-{mid_day:02d}", "label": "Mid-window check",
             "body": "Confirm stop conditions and refresh rider-facing service details."},
            {"date": reopening, "label": "Reopening target",
             "body": "Restore regular routing when bridge work is cleared and confirmed."},
        ],
        "checklist": [
            ("SERVICE FACTS",
             f"{route_label}, the closure window, {stop_count} closed stops, and "
             f"{headway} shuttle headway match the corrected notice."),
            ("STOP MATRIX", f"All {stop_count} stops and their signed "
                            f"shuttle boarding points are shown on the "
                            f"landscape matrix."),
            ("RIDER GUIDANCE", "Detour instructions, travel-time guidance, and "
                               "the rider communication timeline are published."),
            ("ACCESSIBILITY", "Step-free boarding and 311 Transit Desk "
                              "assistance are clearly stated for riders."),
            ("SIGNAGE AND ALERTS", "Stop notices, boarding signs, onboard "
                                   "messages, and digital alerts are scheduled."),
            ("PUBLIC CONTACT", "Every public-facing route to assistance points "
                               "to 311 Transit Desk."),
        ],
        "draft_wrong": {
            "route": "Route 21",
            "closure_begins": "2026-10-13",
            "reopening_target": "2026-10-27",
            "closed_stop_count": "7 stops",
            "shuttle_headway": "30 minutes",
            "contact": "operator personal phone",
            "note": "do not post",
        },
    }


def make_notices(variant_id: str, out_dir: Path) -> dict:
    v = common.VARIANTS[variant_id]
    n = v["scale"]["notice_groups"]
    seed = v["seed"]
    rng = random.Random(seed)
    route_numbers = ROUTE_NUMBERS_U20 if n == 20 else ROUTE_NUMBERS_U5[:n]
    groups = [make_notice_group(i, route_numbers[i], rng)
              for i in range(n)]
    data = {
        "schema": "docops-scaling-notices-v1",
        "variant_task_id": variant_id,
        "seed": seed,
        "pages_per_group": PAGES_PER_GROUP,
        "page_titles": PAGE_TITLES,
        "groups": groups,
    }
    common.write_json(out_dir / "notices.json", data)
    return data


def write_input_pdf(out_dir: Path, input_name: str) -> Path:
    """Small deterministic draft seed PDF (artifact only; the builder does not
    read it for content). Mirrors the parent input being an unread draft."""
    output = out_dir / input_name
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter, pageCompression=1)
    width, height = letter
    c.setFillColorRGB(0.04, 0.18, 0.30)
    c.rect(0, height - 40, width, 40, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(42, height - 28, "DRAFT Internal Bus Detour Packet")
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont("Helvetica", 10)
    lines = [
        "PRIVATE draft: operator personal phone; do not post.",
        "Wrong draft facts: Route 21, 2026-10-13, 2026-10-27, 7 stops, 30 minutes.",
        "Page one of the synthetic draft seed (the scaled builder is driven by",
        "notices.json and never reads this file for content).",
    ]
    y = height - 80
    for line in lines:
        c.drawString(42, y, line)
        y -= 16
    for page in range(2, 6):
        c.showPage()
        c.setFillColorRGB(0.04, 0.18, 0.30)
        c.rect(0, height - 40, width, 40, stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(42, height - 28, f"DRAFT Internal Bus Detour Packet - page {page}")
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
    n = v["scale"]["notice_groups"]
    out_dir.mkdir(parents=True, exist_ok=True)
    data = make_notices(variant_id, out_dir)
    groups = data["groups"]

    input_name = (
        f"docops_v2_l3_037_pdf_bus_detour_notice_layout_repair_input_"
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

    scale_metadata = {
        "notice_groups": n,
        "pages": n * PAGES_PER_GROUP,
        "pages_per_group": PAGES_PER_GROUP,
        "page_titles": PAGE_TITLES,
        "group_ids": [g["id"] for g in groups],
        "routes": [g["route"] for g in groups],
        "closure_begins": [g["closure_begins"] for g in groups],
        "reopening_targets": [g["reopening_target"] for g in groups],
        "closed_stop_counts": [g["closed_stop_count"] for g in groups],
        "headways": [g["shuttle_headway"] for g in groups],
        "total_stops": sum(g["closed_stop_count"] for g in groups),
        "input_bytes": input_path.stat().st_size,
        "input_sha256": common.sha256_file(input_path),
        "notices_json_sha256": common.sha256_file(notices_path),
        "seed": v["seed"],
        "scale_driven_by": (
            "frozen notices.json prepared material; the builder iterates every "
            "declared notice group through the real five-page drawing functions "
            "(no page duplication). The synthetic input PDF is an artifact only "
            "and is not read by the builder."
        ),
    }

    meta = common.default_task_metadata(variant_id)
    meta["scale_metadata"] = scale_metadata
    meta["input_path"] = f"/root/{input_name}"
    meta["output_path"] = (
        f"/root/submission/"
        f"docops_v2_l3_037_pdf_bus_detour_notice_layout_repair_output_"
        f"{v['output_suffix']}.pdf"
    )
    meta["modified_workflow"] = [
        "01 build_render: page sizes, portrait/landscape rules, fonts, drawing "
        "helpers, pageCompression and 150 DPI PNG rendering are unchanged; the "
        "builder iterates notices.json groups (5 pages per group), global page "
        "numbers and bookmark targets are computed over all groups",
        "02 validate: dynamic validator reads frozen expected.json and checks "
        "every group's pages, facts, bookmarks and orientation",
    ]
    meta["measurement_scope"] = (
        "Scales the number of frozen structured notice groups that drive actual "
        "ReportLab page construction, pypdf bookmark/metadata finalization and "
        "150 DPI PNG rendering. 5 groups -> 25 pages, 20 groups -> 100 pages. "
        "All units enter the build functions; pages are never duplicated from a "
        "5-page base."
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
`037`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 037 (frozen `docops_v2_l3_037_pdf_bus_detour_notice_layout_repair`)
- `synthetic`: true
- generator: {meta['generator']} (version {meta['generator_version']})
- seed: {meta['seed']}
- scale: {sm['notice_groups']} notice groups -> {sm['pages']} pages
- pages per group: {sm['pages_per_group']}

## Scale definition (explicit)

This variant defines scale by the number of **frozen structured notice groups**
in `notices.json`. Each group is actually built through the real ReportLab page
drawing functions (cover, corrected summary, stop/shuttle matrix, rider
timeline, release checklist), then finalized with pypdf bookmarks/metadata and
rendered at 150 DPI PNG. Pages are never duplicated from a small base packet.

The synthetic input PDF `{meta['input_path']}` is an artifact only: like the
frozen parent input, the builder does not read it for content. Do not treat its
page count as the scale definition.

## Inputs

- Source document: `{meta['input_path']}` (artifact; not read by the builder)
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

- Save to `{meta['output_path']}`.
- Do not modify the source document in place.
- Keep the output format the same as the input document (`.pdf`).
- Complete the full ordered workflow, not just local text replacement.
"""


def original_description(meta: dict) -> str:
    sm = meta["scale_metadata"]
    return (
        "Synthetic scale variant of frozen task 037: public bus detour notice "
        "layout repair. Scale is defined by the number of frozen structured "
        f"notice groups in notices.json: {sm['notice_groups']} groups -> "
        f"{sm['pages']} pages. Each group is built through the real ReportLab "
        "page functions; the synthetic input PDF is an artifact only and is "
        f"not read by the builder. Variant {meta['variant_task_id']}, seed "
        f"{meta['seed']}. This is a synthetic input, not a historical "
        "benchmark task."
    )
