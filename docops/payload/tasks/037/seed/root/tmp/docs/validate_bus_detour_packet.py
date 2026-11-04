#!/usr/bin/env python3
"""Validate the final Route 12 public detour packet."""

import re
import sys
from pathlib import Path

from pypdf import PdfReader


PDF = Path(
    "/root/submission/"
    "docops_v2_l3_037_pdf_bus_detour_notice_layout_repair_output.pdf"
)
TITLES = [
    "Public Bus Detour Notice Packet",
    "Corrected Detour Summary",
    "Stop Closure and Shuttle Matrix",
    "Rider Communication Timeline",
    "Release Checklist",
]
REQUIRED = [
    "Route 12",
    "2026-10-03",
    "2026-10-17",
    "9",
    "15 minutes",
    "311 Transit Desk",
]
FORBIDDEN = [
    "DRAFT",
    "PRIVATE",
    "Route 21",
    "2026-10-13",
    "2026-10-27",
    "7 stops",
    "30 minutes",
    "operator personal phone",
    "do not post",
]


def normalized(text):
    return re.sub(r"\s+", " ", text).strip()


def main():
    if not PDF.is_file():
        raise AssertionError(f"Missing output: {PDF}")

    reader = PdfReader(str(PDF))
    assert len(reader.pages) == 5, f"Expected 5 pages, got {len(reader.pages)}"

    page_text = [normalized(page.extract_text() or "")
                 for page in reader.pages]
    all_text = normalized(" ".join(page_text))
    metadata_text = normalized(
        " ".join(str(value) for value in (reader.metadata or {}).values())
    )
    combined = normalized(f"{all_text} {metadata_text}")

    for title, text in zip(TITLES, page_text):
        assert title in text, f"Page title missing: {title}"

    outlines = reader.outline
    assert len(outlines) == 5, f"Expected 5 bookmarks, got {len(outlines)}"
    for index, (item, title) in enumerate(zip(outlines, TITLES)):
        assert normalized(item.title) == title
        assert reader.get_destination_page_number(item) == index

    for phrase in REQUIRED:
        assert phrase in combined, f"Required phrase missing: {phrase}"

    for phrase in FORBIDDEN:
        assert phrase.lower() not in combined.lower(), (
            f"Forbidden phrase remains: {phrase}"
        )

    for index in range(1, 10):
        stop_id = f"12-{index:02d}"
        assert stop_id in page_text[2], f"Matrix row missing: {stop_id}"

    widths_heights = [
        (float(page.mediabox.width), float(page.mediabox.height))
        for page in reader.pages
    ]
    assert widths_heights[2][0] > widths_heights[2][1], (
        "Page 3 must be landscape"
    )
    for index in (0, 1, 3, 4):
        width, height = widths_heights[index]
        assert height > width, f"Page {index + 1} must be portrait"

    expected_metadata = {
        "/Title": "Public Bus Detour Notice Packet",
        "/Author": "Transit Communications",
    }
    for key, value in expected_metadata.items():
        assert reader.metadata.get(key) == value, f"Metadata mismatch: {key}"

    print("PASS")
    print(f"pages={len(reader.pages)} bookmarks={len(outlines)}")
    print("page_sizes=" + ", ".join(
        f"{width:.0f}x{height:.0f}" for width, height in widths_heights
    ))
    print("required_phrases=present")
    print("forbidden_phrases=absent")
    print(f"bytes={PDF.stat().st_size}")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise
