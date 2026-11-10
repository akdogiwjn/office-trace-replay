#!/usr/bin/env python3
"""Dynamic validator for synthetic scaled PDF 037 variants.

Reads the frozen expected.json and the rebuilt PDF, then checks:

- total page count and per-group page titles/facts over ALL groups (never only
  the first group);
- every group's matrix page contains all of its stop ids;
- page orientation follows the per-group portrait/landscape rule;
- every bookmark title exists and points to the expected page;
- required and forbidden content, with forbidden matching done on token
  boundaries so a legal id/date/count that merely CONTAINS an old forbidden
  word as a substring (e.g. ``17 stops`` vs ``7 stops``, ``Route 210`` vs
  ``Route 21``) is not wrongly reported;
- metadata controls.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from pypdf import PdfReader


def normalized(text):
    return re.sub(r"\s+", " ", text or "").strip()


def token_pattern(phrase: str):
    return re.compile(
        rf"(?<![A-Za-z0-9]){re.escape(phrase)}(?![A-Za-z0-9])",
        re.IGNORECASE,
    )


def contains_token(text: str, phrase: str) -> bool:
    """Boundary-aware forbidden match (no substring false positives)."""
    return bool(token_pattern(phrase).search(text))


def check(output_path: Path, expected_path: Path) -> dict:
    expected = json.loads(Path(expected_path).read_text(encoding="utf-8"))
    if expected.get("kind") != "pdf":
        raise ValueError(f"not a PDF expectation file: {expected_path}")

    reader = PdfReader(str(output_path))
    errors = []
    report = {"groups": {}, "bookmarks_checked": 0, "errors": []}

    def error(message):
        errors.append(message)

    if len(reader.pages) != expected["total_pages"]:
        error(f"Expected {expected['total_pages']} pages, got {len(reader.pages)}")

    page_text = [normalized(page.extract_text() or "") for page in reader.pages]
    all_text = normalized(" ".join(page_text))
    metadata_text = normalized(
        " ".join(str(value) for value in (reader.metadata or {}).values())
    )
    combined = normalized(f"{all_text} {metadata_text}")

    group_by_page = {}
    for group in expected["groups"]:
        for page in range(group["page_start"], group["page_end"] + 1):
            group_by_page[page] = group

    for group in expected["groups"]:
        gid = group["id"]
        start = group["page_start"] - 1
        pages = page_text[start:start + expected["pages_per_group"]]
        group_combined = normalized(" ".join(pages))

        missing = [term for term in group["required_texts"] if term not in group_combined]
        if missing:
            error(f"group {gid}: required business facts missing: {missing}")

        for offset, title in enumerate(group["page_titles"]):
            if offset >= len(pages):
                error(f"group {gid} page {offset + 1}: page missing")
                continue
            if title not in pages[offset]:
                error(f"group {gid} page {offset + 1}: title missing {title!r}")

        matrix = pages[2] if len(pages) > 2 else ""
        missing_stops = [sid for sid in group["stop_ids"] if sid not in matrix]
        if missing_stops:
            error(f"group {gid}: matrix missing stop ids: {missing_stops}")

        forbidden_hits = []
        for phrase in group["forbidden"]:
            if contains_token(group_combined, phrase):
                forbidden_hits.append(phrase)
        if forbidden_hits:
            error(f"group {gid}: forbidden draft content remains: {forbidden_hits}")

        # orientation rule: page 3 landscape, others portrait
        for offset, expected_orient in enumerate(group["orientation"]):
            index = start + offset
            if index >= len(reader.pages):
                error(f"group {gid} page {offset + 1}: page missing")
                continue
            page = reader.pages[index]
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            is_landscape = width > height
            ok = is_landscape if expected_orient == "landscape" else not is_landscape
            if not ok:
                error(f"group {gid} page {offset + 1}: orientation "
                      f"{'landscape' if is_landscape else 'portrait'}, "
                      f"expected {expected_orient}")

        report["groups"][gid] = {
            "required_present": not missing,
            "missing_stops": missing_stops,
            "forbidden_hits": forbidden_hits,
        }

    # global forbidden (boundary-aware)
    global_hits = [p for p in expected["global_forbidden"]
                   if contains_token(combined, p)]
    if global_hits:
        error(f"Global forbidden content remains: {global_hits}")
    for phrase in expected["global_required"]:
        if phrase not in combined:
            error(f"Global required phrase missing: {phrase}")

    # bookmarks
    outlines = reader.outline or []
    if len(outlines) != len(expected["bookmark_titles"]):
        error(f"Expected {len(expected['bookmark_titles'])} bookmarks, "
              f"got {len(outlines)}")
    for index, (item, expected_title, expected_page) in enumerate(zip(
            outlines, expected["bookmark_titles"], expected["bookmark_page_indexes"])):
        if normalized(item.title) != expected_title:
            error(f"bookmark {index}: title {normalized(item.title)!r}, "
                  f"expected {expected_title!r}")
        try:
            actual_page = reader.get_destination_page_number(item)
        except Exception as exc:  # noqa: BLE001
            error(f"bookmark {index}: cannot resolve page ({exc})")
            continue
        if actual_page != expected_page:
            error(f"bookmark {index} {expected_title!r}: points to page "
                  f"{actual_page}, expected page {expected_page}")
    report["bookmarks_checked"] = min(len(outlines), len(expected["bookmark_titles"]))

    # metadata
    for key, value in expected["metadata"].items():
        if reader.metadata.get(key) != value:
            error(f"Metadata mismatch: {key}: expected {value!r}, "
                  f"got {reader.metadata.get(key)!r}")

    report["errors"] = errors
    report["passed"] = not errors
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=os.environ.get("VARIANT_OUTPUT"),
                        help="output PDF path")
    parser.add_argument("--expected", default=os.environ.get("VARIANT_EXPECTED", "/root/tmp/docs/expected.json"))
    parser.add_argument("--report", default=os.environ.get("VARIANT_REPORT", "/root/tmp/docs/output_validation.json"))
    args = parser.parse_args(argv)
    if not args.output:
        parser.error("--output is required (or set VARIANT_OUTPUT)")
    report = check(Path(args.output), Path(args.expected))
    Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["errors"]:
        raise SystemExit(f"Validation failed with {len(report['errors'])} error(s)")
    print("All structural, content, bookmark and orientation checks passed.")


if __name__ == "__main__":
    main()
