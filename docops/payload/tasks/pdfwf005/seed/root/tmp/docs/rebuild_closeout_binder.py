#!/usr/bin/env python3
"""Rebuild the live closeout binder from the marked working draft."""

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject


SOURCE = Path("/root/pdfwf_005_closeout_binder_page_labels_and_bookmarks_seed.pdf")
OUTPUT = Path("/root/submission/pdfwf_005_closeout_binder_page_labels_and_bookmarks_seed.pdf")

# Source page numbers are 1-based and follow the requested live-page order.
LIVE_PAGES = [
    (2, "Cover"),
    (3, "Meeting Log"),
    (4, "Binder Index"),
    (5, "Approved Exhibit"),
    (6, "Appendix A"),
    (1, "Appendix B"),
]
OBSOLETE_PAGE = 7
DRAFT_PREFIX = b"Draft: "


def remove_draft_prefixes(page, expected_title: str) -> None:
    contents = page.get_contents()
    original = contents.get_data()
    if DRAFT_PREFIX not in original:
        raise ValueError(f"{expected_title}: expected draft-prefixed text")

    revised = original.replace(DRAFT_PREFIX, b"")
    if DRAFT_PREFIX in revised:
        raise ValueError(f"{expected_title}: draft prefix remained after replacement")
    if f"({expected_title})".encode("ascii") not in revised:
        raise ValueError(f"{expected_title}: visible page title was not found")

    replacement = DecodedStreamObject()
    replacement.set_data(revised)
    page[NameObject("/Contents")] = replacement


def main() -> None:
    reader = PdfReader(SOURCE)
    if len(reader.pages) != 7:
        raise ValueError(f"expected 7 source pages, found {len(reader.pages)}")

    obsolete_text = reader.pages[OBSOLETE_PAGE - 1].extract_text() or ""
    if "Obsolete Divider" not in obsolete_text:
        raise ValueError("source page 7 is not the expected obsolete divider")

    writer = PdfWriter()
    for source_number, title in LIVE_PAGES:
        page = reader.pages[source_number - 1]
        text = page.extract_text() or ""
        if title not in text:
            raise ValueError(f"source page {source_number} is not titled {title!r}")

        remove_draft_prefixes(page, title)
        live_page = writer.add_page(page)
        writer.add_outline_item(title, live_page)

    # Give each live page its visible section title as the viewer page label.
    for page_index, (_, title) in enumerate(LIVE_PAGES):
        writer.set_page_label(
            page_index,
            page_index,
            style=None,
            prefix=title,
            start=0,
        )

    if reader.metadata:
        metadata = {
            str(key): str(value)
            for key, value in reader.metadata.items()
            if value is not None
        }
        metadata["/Title"] = "Closeout Binder"
        writer.add_metadata(metadata)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("wb") as output_file:
        writer.write(output_file)


if __name__ == "__main__":
    main()
