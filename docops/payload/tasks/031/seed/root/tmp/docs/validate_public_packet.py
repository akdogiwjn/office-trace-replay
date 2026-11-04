#!/usr/bin/env python3
"""Validate the generated public hearing packet against the release contract."""

from pathlib import Path

from pypdf import PdfReader


PDF = Path(
    "/root/submission/"
    "docops_v2_l3_031_pdf_public_hearing_packet_flatten_release_output.pdf"
)
TITLES = [
    "Public Hearing Packet: Zoning Amendment Comments",
    "Corrected Hearing Summary",
    "Comment Category Matrix",
    "Response Workflow",
    "Release Controls and Appendix Index",
]
FOOTER = "Public Hearing Release | ZA-2026-041 | 2026"
FORBIDDEN = [
    "DRAFT",
    "PRIVATE",
    "INTERNAL",
    "staff-only",
    "Vivian Holt",
    "Marco Ruiz",
    "555-0198",
    "legal hold",
    "unreleased deliberation",
    "procedural objections",
    "2026-03-04",
    "112",
    "2026-09-01",
]


def walk_forbidden_keys(value, path="root", seen=None):
    """Recursively find prohibited interactive or attachment structures."""
    if seen is None:
        seen = set()
    forbidden_keys = {
        "/AcroForm",
        "/Annots",
        "/EmbeddedFiles",
        "/JavaScript",
        "/OpenAction",
        "/AA",
    }
    found = []
    if hasattr(value, "idnum"):
        key = (value.idnum, value.generation)
        if key in seen:
            return found
        seen.add(key)
        value = value.get_object()
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}/{key}"
            if str(key) in forbidden_keys:
                found.append(child_path)
            found.extend(walk_forbidden_keys(child, child_path, seen))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(walk_forbidden_keys(child, f"{path}[{index}]", seen))
    return found


def main():
    reader = PdfReader(str(PDF))
    errors = []
    notes = []

    if len(reader.pages) != 5:
        errors.append(f"Expected 5 pages, found {len(reader.pages)}")
    else:
        notes.append("Page count: 5")

    for index, page in enumerate(reader.pages, 1):
        size = (float(page.mediabox.width), float(page.mediabox.height))
        if size != (612.0, 792.0):
            errors.append(f"Page {index} is not Letter size: {size}")
    notes.append("Page size: Letter (612 x 792 pt) on every page")

    extracted_pages = [page.extract_text() or "" for page in reader.pages]
    for index, (title, text) in enumerate(zip(TITLES, extracted_pages), 1):
        if title not in text:
            errors.append(f"Page {index} is missing exact title: {title}")
        if FOOTER not in text:
            errors.append(f"Page {index} is missing required footer")
        if f"{index} / 5" not in text:
            errors.append(f"Page {index} is missing the correct page number")
    notes.append("Titles, required footer, and page numbers: verified")

    metadata = reader.metadata or {}
    expected_metadata = {
        "/Title": TITLES[0],
        "/Author": "Public Hearing Desk",
        "/Subject": "Clean flattened public release packet",
    }
    for key, expected in expected_metadata.items():
        if metadata.get(key) != expected:
            errors.append(f"Metadata {key} mismatch: {metadata.get(key)!r}")
    notes.append("Required public metadata: verified")

    outline_titles = [item.title for item in reader.outline]
    if outline_titles != TITLES:
        errors.append(f"Outline order mismatch: {outline_titles!r}")
    notes.append("Five outline bookmarks in required page order: verified")

    structural_findings = walk_forbidden_keys(reader.trailer["/Root"])
    if structural_findings:
        errors.append(
            "Prohibited PDF structures found: "
            + ", ".join(structural_findings)
        )
    if reader.attachments:
        errors.append(f"Embedded files remain: {list(reader.attachments)}")
    notes.append("Forms, annotations, attachments, and JavaScript: absent")

    combined_text = "\n".join(extracted_pages)
    metadata_text = "\n".join(str(value) for value in metadata.values())
    public_text = f"{combined_text}\n{metadata_text}"
    found_forbidden = [
        value for value in FORBIDDEN if value.lower() in public_text.lower()
    ]
    if found_forbidden:
        errors.append(f"Prohibited public text remains: {found_forbidden}")
    notes.append("Restricted names, contact data, old values, and labels: absent")

    required_values = [
        "2026-03-14",
        "128",
        "2026-09-15",
        "Public Hearing Desk",
        "ZA-2026-041",
    ]
    for value in required_values:
        if value not in combined_text:
            errors.append(f"Required corrected value is missing: {value}")
    notes.append("All five corrected public facts: present")

    category_counts = [35, 28, 21, 18, 15, 11]
    if sum(category_counts) != 128:
        errors.append("Category counts do not total 128")
    if sum([27.3, 21.9, 16.4, 14.1, 11.7, 8.6]) != 100.0:
        errors.append("Displayed category shares do not total 100.0%")
    notes.append("Category matrix totals: 128 comments and 100.0%")

    header_rgb = b".043137 .239216 .568627 rg"
    accent_rgb = b".960784 .619608 .043137 rg"
    for index, page in enumerate(reader.pages, 1):
        content = page.get_contents().get_data()
        if header_rgb not in content:
            errors.append(f"Page {index} is missing #0B3D91 header color")
        if accent_rgb not in content:
            errors.append(f"Page {index} is missing #F59E0B accent color")
    notes.append("Required header and accent colors: present on every page")

    print("PASS" if not errors else "FAIL")
    for note in notes:
        print(f"OK  {note}")
    for error in errors:
        print(f"ERR {error}")
    print(f"Output: {PDF}")
    raise SystemExit(0 if not errors else 1)


if __name__ == "__main__":
    main()
