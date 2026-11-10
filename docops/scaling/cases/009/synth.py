"""Synthetic Word 009 inputs: scaled incident manual public-release packets.

A business record is one incident case that must go through the full frozen 009
workflow (draft removal, TOC creation, section reorder, table normalization,
header/footer, exception highlighting, appendix release). This generator
produces:

- ``cases.json``: the frozen incident-case declaration (unique ids and the six
  per-case row facts for timeline / communication / exception / action /
  evidence / approval tables) that drives the parameterized builder and the
  independent expected oracle.
- a synthetic source DOCX that carries the DRAFT/internal working banner and
  per-case working entries the frozen publication stages must handle.

Generation is byte-deterministic for a fixed seed/params. The official frozen
009 payload is never touched.
"""
from __future__ import annotations

import datetime
import random
from pathlib import Path

from docx import Document

from .. import common

# Frozen public facts of parent task 009.
RELEASE_DATE = "2026-06-05"
PUBLIC_TITLE = "Incident Response Manual | Public Release"
PUBLIC_SUBJECT = "Release-safe public incident response manual"
PUBLIC_HEADER = "Incident Response Manual | Public Release | 2026-06-05"
PUBLIC_AUTHOR = "Security Operations Publication Office"

HEADINGS = [
    "Publication Summary",
    "Response Timeline",
    "Customer Communication",
    "Control Exceptions",
    "Action Register",
    "Appendix A - Evidence Index",
    "Appendix B - Approval Record",
]
PAGE_BREAK_HEADINGS = [
    "Control Exceptions",
    "Action Register",
    "Appendix A - Evidence Index",
    "Appendix B - Approval Record",
]
TOC_ENTRIES = [
    ("Publication Summary", "3"),
    ("Response Timeline", "3"),
    ("Customer Communication", "3"),
    ("Control Exceptions", "4"),
    ("Action Register", "5"),
    ("Appendix A - Evidence Index", "6"),
    ("Appendix B - Approval Record", "7"),
]

# Fixed public paragraphs preserved from the frozen parent.
FIXED_PARAGRAPHS = [
    "This public manual summarizes the June 2026 incident response without "
    "privileged root-cause analysis.",
    "Customer-facing language has been normalized and internal notes have "
    "been removed.",
    "Exception: MFA evidence owner remains unassigned.",
    "Resolved exception: log retention evidence was exported and approved.",
]

# Table headers per section (order matches HEADINGS tail).
TIMELINE_HEADER = ["Time", "Milestone", "Public Summary"]
COMMUNICATION_HEADER = ["Audience", "Message Owner", "Required Update", "Status"]
EXCEPTION_HEADER = ["Exception ID", "Control", "Owner", "Release Status"]
ACTION_HEADER = ["Action ID", "Owner", "Due Date", "Publish Status"]
EVIDENCE_HEADER = ["Evidence ID", "Public Label", "Disposition"]
APPROVAL_HEADER = ["Approver", "Role", "Decision"]

FORBIDDEN_PHRASES = [
    "draft:", "[internal]", "do not publish", "phone bridge",
    "555-0199", "privileged vendor-root-cause",
]

AUDIENCES = ["Customers", "Support desk", "Partners", "Public website",
             "Account teams"]
MILESTONES = ["Alert opened", "Containment applied", "Service restored",
              "Customer notified", "Evidence preserved", "Draft notification prepared"]
SUMMARIES = ["Incident response process started.",
             "Containment controls were applied.",
             "Customer service was restored.",
             "Public update published to customers.",
             "Release evidence archived for review.",
             "Public status notice prepared."]
MESSAGE_UPDATES = ["Send public restoration summary.",
                   "Use approved FAQ language only.",
                   "Send updated service status.",
                   "Publish confirmed resolution notice."]
MESSAGE_STATUS = "Ready"
OWNERS = ["Maya Chen", "Jon Bell", "Rina Patel", "Sam Foster", "Ivy Zhang"]
CONTROLS = ["MFA evidence", "Log retention", "Access review", "Change control",
            "Vendor notification"]
EXCEPTION_OWNERS = ["Unassigned", "Rina Patel", "Sam Foster"]
RELEASE_STATUSES = ["Open - owner required", "Closed - evidence exported"]
ACTION_OWNERS = ["Unassigned", "Maya Chen", "Rina Patel"]
PUBLISH_STATUSES = ["Blocked until owner assigned", "Ready"]
LABELS = ["Alert chronology", "Internal Slack excerpt", "Customer notification record",
          "Containment log", "Approval chain"]
DISPOSITIONS = ["Publish", "Exclude"]
APPROVERS = ["Maya Chen", "Jon Bell"]
ROLES = ["Incident Lead", "Legal", "Security Coordinator"]
DECISIONS = ["Approved", "Approved after privileged text removal"]

INPUT_HEADER_LINES = [
    "Draft: Incident Response Manual - Working Copy",
    "Manual TOC placeholder - replace with real table of contents before publication.",
    "[INTERNAL] Legal review note: vendor root cause language remains privileged "
    "and must not go public.",
    "Owner phone bridge: 555-0199. Do not publish this bridge line.",
    "Draft: working records for the incident cases below must be rebuilt as "
    "public tables.",
]
INPUT_NOTES = [
    "privileged vendor-root-cause note", "[INTERNAL] triage detail",
    "phone bridge 555-0199", "do not publish yet", "unverified draft label",
]
# Draft tables that mirror the frozen parent input structure.
DRAFT_TIMELINE_ROWS = [
    ["Raw Time", "Event", "Internal Detail", "Public?"],
    ["2026-06-01 08:12", "Alert opened", "Vendor root cause suspected", "Yes"],
    ["2026-06-01 09:40", "Containment applied", "[INTERNAL] firewall rule owner was late", "Yes"],
    ["2026-06-01 15:10", "Service restored", "Customer-visible summary needed", "Yes"],
]
DRAFT_EXCEPTION_ROWS = [
    ["Exception", "Control", "Owner", "Internal Comment", "Status"],
    ["EX-01", "MFA evidence", "Unassigned", "Do not publish: screenshots missing", "Open"],
    ["EX-02", "Log retention", "Rina Patel", "Resolved after archive export", "Closed"],
]
DRAFT_APPROVAL_ROWS = [
    ["Approver", "Role", "Decision"],
    ["Maya Chen", "Incident Lead", "Approved"],
    ["Jon Bell", "Legal", "Approved with privileged text removed"],
]
DRAFT_EVIDENCE_ROWS = [
    ["Evidence ID", "Source", "Public Label", "Keep?"],
    ["EV-01", "PagerDuty export", "Alert chronology", "Yes"],
    ["EV-02", "Internal Slack", "Do not publish", "No"],
    ["EV-03", "Customer email", "Customer notification record", "Yes"],
]


def make_cases(n: int, rng: random.Random) -> list[dict]:
    """Deterministic per-variant incident cases.

    Ids, timeline times and due dates are unique; every case carries the six
    row facts assigned to the response timeline, customer communication,
    control exception, action register, evidence index and approval tables.
    """
    if n < 1:
        raise ValueError("incident case count must be >= 1")
    base_time = datetime.datetime(2026, 6, 1, 8, 12)
    base_date = datetime.date(2026, 6, 5)
    cases = []
    for index in range(n):
        cases.append({
            "id": f"IC-{index + 1:03d}",
            "audience": rng.choice(AUDIENCES),
            "message_owner": rng.choice(OWNERS),
            "message_update": rng.choice(MESSAGE_UPDATES),
            "timeline_time": (base_time + datetime.timedelta(hours=index))
            .strftime("%Y-%m-%d %H:%M"),
            "milestone": rng.choice(MILESTONES),
            "summary": rng.choice(SUMMARIES),
            "exception_id": f"EX-{index + 1:03d}",
            "control": rng.choice(CONTROLS),
            "exception_owner": rng.choice(EXCEPTION_OWNERS),
            "release_status": rng.choice(RELEASE_STATUSES),
            "action_id": f"ACT-{index + 1:03d}",
            "action_owner": rng.choice(ACTION_OWNERS),
            "due_date": (base_date + datetime.timedelta(days=index)).isoformat(),
            "publish_status": rng.choice(PUBLISH_STATUSES),
            "evidence_id": f"EV-{index + 1:03d}",
            "public_label": rng.choice(LABELS),
            "disposition": rng.choice(DISPOSITIONS),
            "approver": rng.choice(APPROVERS),
            "role": rng.choice(ROLES),
            "decision": rng.choice(DECISIONS),
        })
    assert len({c["id"] for c in cases}) == n
    assert len({c["timeline_time"] for c in cases}) == n
    assert len({c["due_date"] for c in cases}) == n
    return cases


def write_cases_json(variant_id: str, cases: list[dict], out_dir: Path) -> Path:
    data = {
        "schema": "docops-scaling-cases-v1",
        "variant_task_id": variant_id,
        "seed": common.VARIANTS[variant_id]["seed"],
        "release_date": RELEASE_DATE,
        "cases": cases,
    }
    common.write_json(out_dir / "cases.json", data)
    return out_dir / "cases.json"


def _draft_table(doc, rows):
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.style = "Table Grid"
    for row_idx, values in enumerate(rows):
        for col_idx, value in enumerate(values):
            table.rows[row_idx].cells[col_idx].text = value


def write_source_docx(cases: list[dict], out_dir: Path, input_name: str) -> Path:
    """Draft input: DRAFT/internal banner + per-case working entries + the
    frozen draft tables. The builder verifies the Draft: marker and rebuilds."""
    doc = Document()
    doc.core_properties.author = "DocOps synthetic scale generator"
    doc.core_properties.last_modified_by = "DocOps synthetic scale generator"
    doc.core_properties.title = "Draft: Incident Response Manual - Working Copy"
    doc.core_properties.created = datetime.datetime(2026, 11, 2, 0, 0, 0)
    doc.core_properties.modified = datetime.datetime(2026, 11, 2, 0, 0, 0)

    doc.add_paragraph(INPUT_HEADER_LINES[0], style="Title")
    for line in INPUT_HEADER_LINES[1:]:
        doc.add_paragraph(line)

    for case in cases:
        doc.add_paragraph(f"Draft: Case {case['id']} - internal working entry",
                          style="Heading 1")
        doc.add_paragraph(
            f"[INTERNAL] case {case['id']}: {input_note(case)}.")

    working = doc.add_table(rows=1, cols=3)
    working.style = "Table Grid"
    for col, value in enumerate(["Case ID", "Internal Detail", "Public?"]):
        working.rows[0].cells[col].text = value
    for case in cases:
        cells = working.add_row().cells
        cells[0].text = case["id"]
        cells[1].text = input_note(case)
        cells[2].text = "Yes"

    _draft_table(doc, DRAFT_TIMELINE_ROWS)
    _draft_table(doc, DRAFT_EXCEPTION_ROWS)
    _draft_table(doc, DRAFT_APPROVAL_ROWS)
    _draft_table(doc, DRAFT_EVIDENCE_ROWS)

    output = out_dir / input_name
    tmp = output.parent / f".tmp-{input_name}"
    doc.save(str(tmp))
    common.deterministic_zip(tmp, output)
    tmp.unlink(missing_ok=True)
    return output


def input_note(case: dict) -> str:
    return INPUT_NOTES[int(case["id"].split("-")[1]) % len(INPUT_NOTES)]


def generate(variant_id: str, out_dir: Path, write_raw_records: bool = True) -> dict:
    v = common.VARIANTS[variant_id]
    n = v["scale"]["incident_cases"]
    rng = random.Random(v["seed"])
    cases = make_cases(n, rng)

    out_dir.mkdir(parents=True, exist_ok=True)
    cases_path = write_cases_json(variant_id, cases, out_dir)
    input_name = (
        f"docops_v2_l3_009_docx_incident_manual_publication_input_"
        f"{v['output_suffix']}.docx"
    )
    input_path = write_source_docx(cases, out_dir, input_name)

    src_doc = Document(str(input_path))
    src_paragraphs = len(src_doc.paragraphs)
    src_tables = len(src_doc.tables)
    src_table_rows = sum(len(t.rows) for t in src_doc.tables)

    if write_raw_records:
        common.write_json(
            out_dir / "raw_records.json",
            {"schema": "docops-scaling-raw-records-v1",
             "variant_task_id": variant_id,
             "records": cases},
        )

    first = cases[0]
    middle = cases[n // 2]
    last = cases[-1]
    scale_metadata = {
        "incident_cases": n,
        "case_ids": [c["id"] for c in cases],
        "case_id_summary": {
            "unit": "incident_case",
            "first": first["id"],
            "middle": middle["id"],
            "last": last["id"],
            "count": n,
            "unique": True,
        },
        "input_cases": n,
        "expected_output_tables": 7,
        "expected_output_table_rows": 9 + 6 * n,
        "expected_headings": len(HEADINGS),
        "expected_paragraphs": 39,
        "expected_images": 0,
        "render_scope": "full document; all pages rendered at 150 DPI",
        "first_case": first,
        "middle_case": middle,
        "last_case": last,
        "preserved_parent_behaviour": [
            "public cover page and real TOC field",
            "all parent section headings and their order",
            "fixed Publication Summary and exception paragraphs (open MFA "
            "exception stays highlighted)",
            "header, page-number footer, margins and page-break placement",
            "byte-deterministic output and Draft:-source verification",
        ],
        "changed_parent_behaviour": [
            "the six data tables (timeline, communication, exception, action, "
            "evidence, approval) now hold one real row per declared incident "
            "case instead of fixed rows, so table row counts are driven by the "
            "actual case count",
            "Publication Summary reports the actual case count",
        ],
        "source_paragraphs": src_paragraphs,
        "source_tables": src_tables,
        "source_table_rows": src_table_rows,
        "input_bytes": input_path.stat().st_size,
        "input_sha256": common.sha256_file(input_path),
        "cases_json_sha256": common.sha256_file(cases_path),
        "seed": v["seed"],
    }

    meta = common.default_task_metadata(variant_id)
    meta["scale_metadata"] = scale_metadata
    meta["input_path"] = f"/root/{input_name}"
    meta["output_path"] = (
        f"/root/submission/"
        f"docops_v2_l3_009_docx_incident_manual_publication_output_"
        f"{v['output_suffix']}.docx"
    )
    meta["modified_workflow"] = [
        "01 build: build_incident_manual_variant.py preserves the frozen 009 "
        "stage order (draft removal, cover, real TOC, section reorder, table "
        "normalization, header/footer, highlight, appendix split); the six "
        "data tables iterate all N incident cases (one real row per case per "
        "table), so output size is driven by the actual case count",
        "02 render: unchanged render_docx.py (LibreOffice -> PDF -> PNG); page "
        "count is decided by real layout",
        "03 validate: dynamic validator reads frozen expected.json and covers "
        "every case plus document-level controls (cover/TOC/header/footer/"
        "highlight/style/margin checks run once, not repeated per case)",
    ]
    meta["measurement_scope"] = (
        "Scales the number of incident cases that must go through the full "
        "frozen 009 publication pipeline: draft removal, TOC creation, section "
        "reorder, timeline/communication/exception/action/evidence/approval "
        "table normalization, header/footer, exception highlighting and "
        "appendix release. Both the source DOCX working content and the final "
        "public manual scale with the case count. Page count is decided by "
        "real LibreOffice layout; no page count is forged here."
    )
    common.write_json(out_dir / "task_metadata.json", meta)
    (out_dir / "instruction.md").write_text(instruction_md(meta), encoding="utf-8")
    (out_dir / "original_task_description.txt").write_text(
        original_description(meta), encoding="utf-8")

    return {
        "input": input_path,
        "cases": cases_path,
        "task_metadata": out_dir / "task_metadata.json",
        "scale_metadata": scale_metadata,
    }


def instruction_md(meta: dict) -> str:
    v = common.VARIANTS[meta["variant_task_id"]]
    sm = meta["scale_metadata"]
    return f"""# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`009`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 009 (frozen `docops_v2_l3_009_docx_incident_manual_publication`)
- `synthetic`: true
- generator: {meta['generator']} (version {meta['generator_version']})
- seed: {meta['seed']}
- scale: {sm['incident_cases']} incident cases

## Inputs

- Source document: `{meta['input_path']}`
- Frozen incident-case declaration: `/root/tmp/docs/cases.json`
- Frozen expected oracle: `/root/tmp/docs/expected.json`
- Original benchmark seed description: `/root/original_task_description.txt`

## Goal

Convert a draft incident response manual into a release-safe public Word manual
through the same long ordered workflow as parent task 009. Every declared
incident case in `cases.json` must appear as a real row in the response
timeline, customer communication, control exception, action register, evidence
index and approval tables of the final packet.

## Required Sequential Workflow

1. Verify the source still carries the `Draft:` marker and remove all draft /
   internal material.
2. Build the public cover and a real Word TOC field.
3. Reorder sections into: Publication Summary, Response Timeline, Customer
   Communication, Control Exceptions, Action Register, Appendix A - Evidence
   Index, Appendix B - Approval Record.
4. Normalize the six data tables from `cases.json`: one row per incident case
   in the timeline, communication, exception, action, evidence and approval
   tables (the last case is really written).
5. Add page breaks before Control Exceptions, Action Register, Appendix A and
   Appendix B; update header/footer; highlight the open MFA evidence exception.
6. Ensure no `Draft:`, `[INTERNAL]`, `Do not publish`, phone bridge or
   privileged vendor-root-cause text remains.
7. Preserve the document as `.docx` and save to `{meta['output_path']}`.

## Public Release Specification

- Title: `Incident Response Manual | Public Release`
- Header: `Incident Response Manual | Public Release | 2026-06-05`
- Footer: page numbering with the label `Page`
- Table headers: `Time | Milestone | Public Summary`, `Audience | Message
  Owner | Required Update | Status`, `Exception ID | Control | Owner | Release
  Status`, `Action ID | Owner | Due Date | Publish Status`, `Evidence ID |
  Public Label | Disposition`, `Approver | Role | Decision`.

## Output Requirements

- Do not modify the source document in place.
- Keep the output format the same as the input document (`.docx`).
- Complete the entire long-flow publication workflow; partial section cleanup
  is not sufficient.
"""


def original_description(meta: dict) -> str:
    sm = meta["scale_metadata"]
    return (
        "Synthetic scale variant of frozen task 009: incident response manual "
        "public release. The source contains "
        f"{sm['incident_cases']} incident cases, each with DRAFT internal "
        "working entries and per-case timeline/communication/exception/action/"
        "evidence/approval facts that must be normalized into the public "
        "tables. Scale is defined by the number of incident cases that must "
        "pass through the whole frozen publication pipeline and appear in the "
        "final packet. "
        f"Variant {meta['variant_task_id']}, seed {meta['seed']}. "
        "This is a synthetic input, not a historical benchmark task."
    )
