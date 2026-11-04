from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml.ns import qn


DOCX_PATH = Path(
    "/root/submission/docops_v2_l3_009_docx_incident_manual_publication_output.docx"
)

EXPECTED_ORDER = [
    "Publication Summary",
    "Response Timeline",
    "Customer Communication",
    "Control Exceptions",
    "Action Register",
    "Appendix A - Evidence Index",
    "Appendix B - Approval Record",
]

EXPECTED_TABLES = [
    ["Time", "Milestone", "Public Summary"],
    ["Audience", "Message Owner", "Required Update", "Status"],
    ["Exception ID", "Control", "Owner", "Release Status"],
    ["Action ID", "Owner", "Due Date", "Publish Status"],
    ["Evidence ID", "Public Label", "Disposition"],
    ["Approver", "Role", "Decision"],
]


def table_rows(table) -> list[list[str]]:
    return [[cell.text for cell in row.cells] for row in table.rows]


def main():
    assert DOCX_PATH.is_file(), "Output DOCX is missing"
    doc = Document(DOCX_PATH)
    paragraph_text = [p.text for p in doc.paragraphs]
    heading_text = [
        p.text for p in doc.paragraphs if p.style.name == "Heading 1"
    ]

    assert heading_text == EXPECTED_ORDER, heading_text
    assert (
        "Incident Response Manual | Public Release" in paragraph_text
    ), "Title paragraph is missing"

    for heading in (
        "Control Exceptions",
        "Action Register",
        "Appendix A - Evidence Index",
        "Appendix B - Approval Record",
    ):
        paragraph = next(p for p in doc.paragraphs if p.text == heading)
        assert paragraph.paragraph_format.page_break_before, (
            f"Missing page break before {heading}"
        )

    required_paragraphs = [
        "This public manual summarizes the June 2026 incident response without "
        "privileged root-cause analysis.",
        "Customer-facing language has been normalized and internal notes have "
        "been removed.",
        "Exception: MFA evidence owner remains unassigned.",
        "Resolved exception: log retention evidence was exported and approved.",
    ]
    for text in required_paragraphs:
        assert text in paragraph_text, f"Missing paragraph: {text}"

    open_exception = next(
        p
        for p in doc.paragraphs
        if p.text == "Exception: MFA evidence owner remains unassigned."
    )
    assert open_exception.runs
    assert all(
        run.font.highlight_color == WD_COLOR_INDEX.YELLOW
        for run in open_exception.runs
    ), "Open exception paragraph is not fully highlighted"

    tables = [table_rows(table) for table in doc.tables]
    for expected_header in EXPECTED_TABLES:
        assert any(rows[0] == expected_header for rows in tables), (
            f"Missing table header: {expected_header}"
        )

    expected_payloads = {
        "Time": [
            [
                "2026-06-01 08:12",
                "Alert opened",
                "Incident response process started.",
            ],
            [
                "2026-06-01 09:40",
                "Containment applied",
                "Containment controls were applied.",
            ],
            [
                "2026-06-01 15:10",
                "Service restored",
                "Customer service was restored.",
            ],
        ],
        "Audience": [
            [
                "Customers",
                "Maya Chen",
                "Send public restoration summary.",
                "Ready",
            ],
            [
                "Support desk",
                "Jon Bell",
                "Use approved FAQ language only.",
                "Ready",
            ],
        ],
        "Exception ID": [
            ["EX-01", "MFA evidence", "Unassigned", "Open - owner required"],
            [
                "EX-02",
                "Log retention",
                "Rina Patel",
                "Closed - evidence exported",
            ],
        ],
        "Action ID": [
            [
                "ACT-01",
                "Unassigned",
                "2026-06-07",
                "Blocked until owner assigned",
            ],
            ["ACT-02", "Maya Chen", "2026-06-06", "Ready"],
        ],
        "Evidence ID": [
            ["EV-01", "Alert chronology", "Publish"],
            ["EV-02", "Internal Slack excerpt", "Exclude"],
            ["EV-03", "Customer notification record", "Publish"],
        ],
        "Approver": [
            ["Maya Chen", "Incident Lead", "Approved"],
            ["Jon Bell", "Legal", "Approved after privileged text removal"],
        ],
    }
    for key, expected_rows in expected_payloads.items():
        found = next(rows for rows in tables if rows[0][0] == key)
        assert found[1:] == expected_rows, f"Unexpected rows for {key}: {found[1:]}"

    section = doc.sections[0]
    header_text = "\n".join(p.text for p in section.header.paragraphs)
    assert (
        header_text == "Incident Response Manual | Public Release | 2026-06-05"
    ), header_text
    footer_text = "\n".join(p.text for p in section.footer.paragraphs)
    assert "Page" in footer_text, footer_text

    with ZipFile(DOCX_PATH) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
        footer_xml = archive.read("word/footer1.xml").decode("utf-8")
        combined_xml = "\n".join(
            archive.read(name).decode("utf-8", errors="ignore")
            for name in archive.namelist()
            if name.endswith(".xml")
        )
        assert "TOC \\o &quot;1-1&quot;" in document_xml or (
            'TOC \\o "1-1"' in document_xml
        ), "Real TOC field is missing"
        assert " PAGE " in footer_xml, "PAGE footer field is missing"

    lower_xml = combined_xml.lower()
    prohibited = [
        "draft:",
        "[internal]",
        "do not publish",
        "phone bridge",
        "555-0199",
        "privileged vendor-root-cause",
    ]
    for term in prohibited:
        assert term not in lower_xml, f"Prohibited text remains: {term}"

    print("Validation passed")
    print(f"Path: {DOCX_PATH}")
    print(f"Paragraphs: {len(doc.paragraphs)}; tables: {len(doc.tables)}")
    print(f"Headings in order: {heading_text}")
    print(f"Header: {header_text}")
    print(f"Footer: {footer_text}")


if __name__ == "__main__":
    main()
