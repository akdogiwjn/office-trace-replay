#!/usr/bin/env python3
"""Parameterized builder for synthetic scaled pdfwf005 variants.

Mirrors the frozen parent rebuild_closeout_binder.py: it REALLY reads the input
PDF, removes the visible "Draft: " prefixes, deletes each group's obsolete
divider page, restores the six live pages to their requested order, adds a
bookmark for every live page (pointing to the correct absolute page number) and
sets the visible section title as each page's label, then preserves the input
metadata with the /Title overridden to "Closeout Binder".

The only change is that the builder iterates every binder group declared in
``groups.json`` instead of a single fixed 7-page seed. Live pages are never
duplicated; every group flows through the real read/prefix-strip/obsolete-drop/
reorder/label path. Output pages = 6 x N.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

LIVE_PAGES_PER_GROUP = 6


def remove_draft_prefixes(page, expected_title: str, draft_prefix: bytes) -> None:
    contents = page.get_contents()
    original = contents.get_data()
    if draft_prefix not in original:
        raise ValueError(f"{expected_title}: expected draft-prefixed text")

    revised = original.replace(draft_prefix, b"")
    if draft_prefix in revised:
        raise ValueError(f"{expected_title}: draft prefix remained after replacement")
    if f"({expected_title})".encode("ascii") not in revised:
        raise ValueError(f"{expected_title}: visible page title was not found")

    replacement = DecodedStreamObject()
    replacement.set_data(revised)
    page[NameObject("/Contents")] = replacement


def build(input_path: Path, groups_path: Path, output_path: Path,
          remove_draft: bool = True, include_obsolete: bool = False) -> int:
    """Rebuild the scaled closeout binder.

    ``remove_draft`` and ``include_obsolete`` are internal test-fixture knobs
    (the CLI always uses the production defaults): they let directed negative
    fixtures keep a draft prefix or keep the obsolete divider page.
    """
    data = json.loads(Path(groups_path).read_text(encoding="utf-8"))
    groups = data["groups"]
    pages_per_group = data["pages_per_group"]
    default_obsolete_title = data.get("obsolete_title", "Obsolete Divider")
    draft_prefix = data.get("draft_prefix", "Draft: ").encode("ascii")

    reader = PdfReader(str(input_path))
    expected_input_pages = len(groups) * pages_per_group
    if len(reader.pages) != expected_input_pages:
        raise ValueError(
            f"expected {expected_input_pages} source pages for "
            f"{len(groups)} groups, found {len(reader.pages)}")

    writer = PdfWriter()
    for group_index, group in enumerate(groups):
        offset = group_index * pages_per_group
        group_id = group["group_id"]
        obsolete_title = group.get("obsolete_title", default_obsolete_title)
        obsolete_rel = group["obsolete_page_index"]

        obsolete_page = reader.pages[offset + obsolete_rel - 1]
        obsolete_text = obsolete_page.extract_text() or ""
        if obsolete_title not in obsolete_text:
            raise ValueError(
                f"{group_id}: source page {obsolete_rel} is not the expected "
                f"obsolete divider {obsolete_title!r}")

        for title in group["live_titles"]:
            rel = group["source_index_for_title"][title]
            page = reader.pages[offset + rel - 1]
            text = page.extract_text() or ""
            if title not in text:
                raise ValueError(
                    f"{group_id}: source page {rel} is not titled {title!r}")
            if remove_draft:
                remove_draft_prefixes(page, title, draft_prefix)
            live_page = writer.add_page(page)
            writer.add_outline_item(f"{group_id} | {title}", live_page)

        if include_obsolete:
            kept = writer.add_page(obsolete_page)
            writer.add_outline_item(f"{group_id} | {obsolete_title}", kept)

        # assign labels by absolute output page indexes for this group
        for local, title in enumerate(group["page_label_prefixes"]):
            absolute = group_index * LIVE_PAGES_PER_GROUP + local
            writer.set_page_label(
                absolute, absolute, style=None, prefix=title, start=0)

    if reader.metadata:
        metadata = {
            str(key): str(value)
            for key, value in reader.metadata.items()
            if value is not None
        }
        metadata["/Title"] = "Closeout Binder"
        writer.add_metadata(metadata)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        writer.write(handle)
    return len(groups) * LIVE_PAGES_PER_GROUP


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=os.environ.get("VARIANT_INPUT"),
                        help="input seed PDF path")
    parser.add_argument("--groups", default=os.environ.get("VARIANT_GROUPS", "/root/tmp/docs/groups.json"),
                        help="frozen groups.json prepared material")
    parser.add_argument("--output", default=os.environ.get("VARIANT_OUTPUT"),
                        help="output PDF path")
    args = parser.parse_args(argv)
    if not args.input:
        parser.error("--input is required (or set VARIANT_INPUT)")
    if not args.output:
        parser.error("--output is required (or set VARIANT_OUTPUT)")
    pages = build(Path(args.input), Path(args.groups), Path(args.output))
    print(args.output)
    print(f"Pages: {pages}")


if __name__ == "__main__":
    main()
