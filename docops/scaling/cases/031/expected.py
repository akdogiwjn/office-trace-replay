"""Independent expectation generator for scaled PDF 031 variants.

Reads the frozen ``notices.json`` prepared material and derives the expected
page layout: total pages, per-group page ranges, the five public page titles,
required business facts, per-group forbidden draft values, bookmark titles and
target pages. The resulting expected.json is frozen at preparation time; the
replay loop never regenerates it.
"""
from __future__ import annotations

from pathlib import Path

from .. import common
from . import synth

PAGES_PER_GROUP = synth.PAGES_PER_GROUP
PAGE_TITLES = synth.PAGE_TITLES

METADATA = {
    "/Title": PAGE_TITLES[0],
    "/Author": "Public Hearing Desk",
    "/Subject": "Clean flattened public release packet",
}

GLOBAL_FORBIDDEN = [
    "DRAFT", "PRIVATE", "INTERNAL", "staff-only", "Vivian Holt", "Marco Ruiz",
    "555-0198", "legal hold", "unreleased deliberation", "procedural objections",
    "2026-03-04", "112", "2026-09-01", "personal phone", "do not publish",
    "private reviewer",
]


def compute(notices_path: Path) -> dict:
    data = common.load_json(notices_path)
    groups = data["groups"]
    total = len(groups) * PAGES_PER_GROUP

    group_specs = []
    bookmark_titles = []
    bookmark_pages = []
    for group in groups:
        page_start = group["page_start"]
        page_end = page_start + PAGES_PER_GROUP - 1
        titles = list(PAGE_TITLES)
        required = [
            group["id"],
            group["hearing_date"],
            str(group["comment_total"]),
            group["response_deadline"],
            group["contact"],
        ]
        required += [category["name"] for category in group["categories"]]
        required += [str(category["count"]) for category in group["categories"]]
        required += [item["section"] for item in group["appendix"]]

        group_bookmark_titles = [f"{group['id']} | {title}" for title in titles]
        group_specs.append({
            "id": group["id"],
            "page_start": page_start,
            "page_end": page_end,
            "page_titles": titles,
            "bookmark_titles": group_bookmark_titles,
            "required_texts": required,
            "appendix_pages": [item["page"] for item in group["appendix"]],
            "packet_pages": [item["page"] for item in group["packet_contents"]],
            "forbidden": list(group["draft_wrong"].values()),
            "orientation": ["portrait"] * PAGES_PER_GROUP,
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
        "global_required": ["Public Hearing Desk"],
    }


def write_expected(variant_task_id: str, notices_path: Path, expected_path: Path) -> dict:
    result = compute(notices_path)
    common.write_json(expected_path, result)
    return result
