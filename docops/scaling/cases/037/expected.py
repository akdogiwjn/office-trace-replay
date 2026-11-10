"""Independent expectation generator for scaled PDF 037 variants.

Reads the frozen ``notices.json`` prepared material and derives the expected
page layout: total pages, per-group page ranges, the five public page titles,
required business facts, per-group forbidden draft values, bookmark titles and
orientation rules. The resulting expected.json is frozen at preparation time;
the replay loop never regenerates it.
"""
from __future__ import annotations

from pathlib import Path

from .. import common
from . import synth

PAGES_PER_GROUP = synth.PAGES_PER_GROUP
PAGE_TITLES = synth.PAGE_TITLES
METADATA = {
    "/Title": "Public Bus Detour Notice Packet",
    "/Author": "Transit Communications",
}
GLOBAL_FORBIDDEN = ["DRAFT", "PRIVATE", "do not post", "operator personal phone"]


def compute(notices_path: Path) -> dict:
    data = common.load_json(notices_path)
    groups = data["groups"]
    total = len(groups) * PAGES_PER_GROUP

    group_specs = []
    bookmark_titles = []
    bookmark_pages = []
    for index, group in enumerate(groups):
        page_start = index * PAGES_PER_GROUP + 1
        page_end = page_start + PAGES_PER_GROUP - 1
        titles = list(PAGE_TITLES)
        required = [
            group["id"],
            group["route"],
            group["corridor"],
            group["closure_begins"],
            group["reopening_target"],
            str(group["closed_stop_count"]),
            group["shuttle_headway"],
            group["contact"],
        ]
        group_bookmark_titles = [f"{group['id']} | {title}" for title in titles]
        group_specs.append({
            "id": group["id"],
            "route": group["route"],
            "corridor": group["corridor"],
            "closure_begins": group["closure_begins"],
            "reopening_target": group["reopening_target"],
            "closed_stop_count": group["closed_stop_count"],
            "shuttle_headway": group["shuttle_headway"],
            "contact": group["contact"],
            "page_start": page_start,
            "page_end": page_end,
            "page_titles": titles,
            "bookmark_titles": group_bookmark_titles,
            "required_texts": required,
            "stop_ids": [stop["id"] for stop in group["stops"]],
            "forbidden": list(group["draft_wrong"].values()),
            "orientation": ["portrait", "portrait", "landscape", "portrait", "portrait"],
        })
        for offset, title in enumerate(group_bookmark_titles):
            bookmark_titles.append(title)
            bookmark_pages.append(page_start - 1 + offset)

    return {
        "schema": "docops-scaling-expectation-v1",
        "variant_task_id": data["variant_task_id"],
        "kind": "pdf",
        "group_count": len(groups),
        "pages_per_group": PAGES_PER_GROUP,
        "total_pages": total,
        "page_titles": list(PAGE_TITLES),
        "groups": group_specs,
        "bookmark_titles": bookmark_titles,
        "bookmark_page_indexes": bookmark_pages,
        "metadata": METADATA,
        "global_forbidden": GLOBAL_FORBIDDEN,
        "global_required": ["311 Transit Desk"],
    }


def write_expected(variant_task_id: str, notices_path: Path, expected_path: Path) -> dict:
    result = compute(notices_path)
    common.write_json(expected_path, result)
    return result
