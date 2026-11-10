#!/usr/bin/env python3
"""Dynamic validator for synthetic scaled pdfwf005 variants.

Reads the frozen expected.json and the rebuilt PDF, then checks over ALL
groups (never only the first group):

- total output pages = 6 x N;
- every group's live pages exist, carry the visible section title and show no
  "Draft:" residual;
- the "Obsolete Divider" page is absent from the whole output;
- every bookmark title exists and points to the expected absolute page;
- every page label equals the expected visible section title;
- the last group is complete (its six live pages and required lines are present);
- required visible body lines per live page.
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


def check(output_path: Path, expected_path: Path) -> dict:
    expected = json.loads(Path(expected_path).read_text(encoding="utf-8"))
    if expected.get("kind") != "pdf":
        raise ValueError(f"not a PDF expectation file: {expected_path}")

    reader = PdfReader(str(output_path))
    errors = []
    report = {"groups": {}, "bookmarks_checked": 0, "labels_checked": 0,
              "errors": []}

    def error(message):
        errors.append(message)

    if len(reader.pages) != expected["total_pages"]:
        error(f"Expected {expected['total_pages']} pages, got {len(reader.pages)}")

    page_text = [normalized(page.extract_text() or "") for page in reader.pages]
    all_text = normalized(" ".join(page_text))
    draft_prefix = expected.get("draft_prefix", "Draft: ")
    obsolete_title = expected.get("obsolete_title", "Obsolete Divider")

    if obsolete_title in all_text:
        error(f"Obsolete divider page text {obsolete_title!r} remains in the output")

    for group in expected["groups"]:
        gid = group["group_id"]
        start = group["page_start"] - 1
        pages = page_text[start:start + expected["live_pages_per_group"]]
        missing_pages = []

        for offset, title in enumerate(group["live_titles"]):
            if offset >= len(pages):
                error(f"group {gid} page {offset + 1}: page missing")
                continue
            text = pages[offset]
            if title not in text:
                error(f"group {gid} page {offset + 1}: visible title "
                      f"{title!r} missing")
            if draft_prefix in text:
                error(f"group {gid} page {offset + 1}: 'Draft: ' residual remains")
            required_lines = group.get("required_lines", {}).get(title, [])
            missing_lines = [line for line in required_lines if line not in text]
            if missing_lines:
                error(f"group {gid} page {offset + 1} ({title!r}): required "
                      f"lines missing: {missing_lines}")
            if not text:
                missing_pages.append(offset + 1)

        report["groups"][gid] = {"missing_pages": missing_pages}

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

    # page labels
    labels = list(reader.page_labels or [])
    if len(labels) != len(expected["page_labels"]):
        error(f"Expected {len(expected['page_labels'])} page labels, "
              f"got {len(labels)}")
    for index, (actual, expected_label) in enumerate(zip(
            labels, expected["page_labels"])):
        if normalized(str(actual)) != expected_label:
            error(f"page label {index}: {actual!r}, expected {expected_label!r}")
    report["labels_checked"] = min(len(labels), len(expected["page_labels"]))

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
    print("All structural, content, bookmark and page-label checks passed.")


if __name__ == "__main__":
    main()
