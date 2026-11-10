"""Independent expectation generator for scaled PDF pdfwf005 variants.

Reads the frozen ``groups.json`` prepared material and derives the expected
rebuild: total output pages, per-group live-page ranges and titles, obsolete
divider removal, bookmark titles and absolute target pages, per-page label
prefixes and the required visible body lines. The resulting expected.json is
frozen at preparation time; the replay loop never regenerates it.
"""
from __future__ import annotations

from pathlib import Path

from .. import common
from . import synth

LIVE_PAGES_PER_GROUP = synth.LIVE_PAGES_PER_GROUP
DRAFT_PREFIX = synth.DRAFT_PREFIX
OBSOLETE_TITLE = synth.OBSOLETE_TITLE


def compute(groups_path: Path) -> dict:
    data = common.load_json(groups_path)
    groups = data["groups"]
    total = len(groups) * LIVE_PAGES_PER_GROUP

    group_specs = []
    bookmark_titles = []
    bookmark_page_indexes = []
    page_labels = []
    for group_index, group in enumerate(groups):
        page_start = group_index * LIVE_PAGES_PER_GROUP + 1
        page_end = page_start + LIVE_PAGES_PER_GROUP - 1
        live_titles = group["live_titles"]
        group_bookmark_titles = group["bookmark_labels"]
        group_page_labels = group["page_label_prefixes"]

        group_specs.append({
            "group_id": group["group_id"],
            "page_start": page_start,
            "page_end": page_end,
            "live_titles": live_titles,
            "source_index_for_title": group["source_index_for_title"],
            "obsolete_page_index": group["obsolete_page_index"],
            "obsolete_title": group.get("obsolete_title", OBSOLETE_TITLE),
            "draft_prefix": group.get("draft_prefix", DRAFT_PREFIX),
            "bookmark_labels": group_bookmark_titles,
            "page_label_prefixes": group_page_labels,
            "required_lines": group.get("required_lines", {}),
        })
        for offset, (title, label) in enumerate(zip(group_bookmark_titles,
                                                    group_page_labels)):
            bookmark_titles.append(title)
            bookmark_page_indexes.append(page_start - 1 + offset)
            page_labels.append(label)

    return {
        "schema": "docops-scaling-expectation-v1",
        "variant_task_id": data["variant_task_id"],
        "kind": "pdf",
        "group_count": len(groups),
        "live_pages_per_group": LIVE_PAGES_PER_GROUP,
        "total_pages": total,
        "live_order": data.get("live_order", list(synth.LIVE_ORDER)),
        "obsolete_title": OBSOLETE_TITLE,
        "draft_prefix": DRAFT_PREFIX,
        "groups": group_specs,
        "bookmark_titles": bookmark_titles,
        "bookmark_page_indexes": bookmark_page_indexes,
        "page_labels": page_labels,
    }


def write_expected(variant_task_id: str, groups_path: Path, expected_path: Path) -> dict:
    result = compute(groups_path)
    common.write_json(expected_path, result)
    return result
