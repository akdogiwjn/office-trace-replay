"""Synthetic Word 001 inputs: scaled controlled document release repair packets.

A business record is one controlled document that must go through the full
frozen 001 workflow (draft-material removal, correction-register application,
metadata/ revision/ workflow/ retirement rebuild, appendix release record).
This generator produces:

- ``records.json``: the frozen controlled-document register declaration (unique
  ids, corrected facts) that drives the parameterized builder and the
  independent expected oracle.
- a synthetic source DOCX that carries the DRAFT/internal-error banner and
  per-record working entries the frozen processing stages must handle.

Generation is byte-deterministic for a fixed seed/params. The official frozen
001 payload is never touched.
"""
from __future__ import annotations

import datetime
import random
from pathlib import Path

from docx import Document

from .. import common

# Frozen public facts of parent task 001 (never parameterized).
DOC_ID = "QMS-PR-007"
VERSION = "4.2"
EFFECTIVE_DATE = "2026-08-01"
OWNER = "Quality Systems Office"
APPROVER = "Compliance Director"
TRAINING_DUE = "2026-08-15"
RETENTION = "6 years"
RETIREMENT = "2026-08-05"
PUBLIC_TITLE = "Controlled Document Release Repair Packet"
PUBLIC_SUBJECT = (
    "Controlled document release repair packet for QMS-PR-007 version 4.2"
)
PUBLIC_FOOTER = "Controlled Document Release Repair Packet | 2026"

# Parent task chapter headings (preserved verbatim).
HEADINGS = [
    PUBLIC_TITLE,
    "Correction Register Applied",
    "Controlled Document Metadata",
    "Revision History",
    "Distribution and Training Workflow",
    "Obsolete Copy Retirement Checklist",
    "Final Release Appendix",
]
PAGE_BREAK_HEADINGS = ["Distribution and Training Workflow", "Final Release Appendix"]

# Parent correction register / metadata / revision / workflow / retirement rows.
CORRECTION_ROWS = [
    ["Issue", "Correct Public Value", "Applied To"],
    ["Document ID", DOC_ID, "Metadata and footer"],
    ["Version", VERSION, "Revision history"],
    ["Effective date", EFFECTIVE_DATE, "Metadata"],
    ["Owner", OWNER, "Metadata"],
    ["Approver", APPROVER, "Approval record"],
    ["Training due", TRAINING_DUE, "Workflow"],
    ["Retention period", RETENTION, "Checklist"],
]
METADATA_ROWS = [
    ["Field", "Correct Public Value", "Status"],
    ["Document ID", DOC_ID, "Corrected"],
    ["Version", VERSION, "Corrected"],
    ["Effective date", EFFECTIVE_DATE, "Corrected"],
    ["Owner", OWNER, "Corrected"],
    ["Approver", APPROVER, "Corrected"],
]
REVISION_ROWS = [
    ["Version", "Date", "Public Change Summary"],
    ["4.0", "2025-04-15", "Baseline controlled release"],
    ["4.1", "2026-02-10", "Minor distribution update"],
    ["4.2", "2026-08-01", "Corrected approval workflow and obsolete copy controls"],
]
WORKFLOW_ROWS = [
    ["Step", "Owner", "Due Date", "Output"],
    ["Publish controlled copy", "Quality Systems Office", "2026-08-01",
     "Released controlled document"],
    ["Notify document users", "Quality Systems Office", "2026-08-03",
     "Distribution notice"],
    ["Complete training", "Department Leads", "2026-08-15", "Training completion record"],
    ["Archive release evidence", "Records Coordinator", "2026-08-20",
     "Release evidence packet"],
]
RETIREMENT_ROWS = [
    ["Control", "Required Result", "Status"],
    ["Obsolete copy retirement", "Complete by 2026-08-05", "Ready"],
    ["Retention period", "6 years", "Ready"],
    ["Approval record", "Compliance Director approval retained", "Ready"],
    ["Distribution list", "Current users notified", "Ready"],
]
AUTH_VALUES = [
    ("Document ID", DOC_ID),
    ("Document owner", OWNER),
    ("Approver", APPROVER),
    ("Release version", VERSION),
    ("Effective date", EFFECTIVE_DATE),
    ("Training due", TRAINING_DUE),
    ("Retention period", RETENTION),
    ("Obsolete copy retirement", RETIREMENT),
]
VERIFICATION_ITEMS = [
    ("01", "All spelling repairs are complete."),
    ("02", "All incorrect version and date values have been removed."),
    ("03", "All release metadata, revision history, training, and obsolete copy "
          "steps have been reconciled."),
]

# Wrong values the frozen source carries and the release must never contain.
FORBIDDEN_PHRASES = [
    "DRAFT", "PRIVATE", "TODO", "uncertain", "QMS-PR-700", "version 4.1",
    "2026-07-01", "QA analyst", "Interim Approver", "2026-08-25", "5 years",
    "2026-09-05", "aproval", "effectve", "obsolte", "distribtuion", "trainng",
    "retetion",
]

# Per-record working pools (deterministic; unique ids/dates always).
NAME_PREFIXES = [
    "Change Control Policy", "Document Control Procedure", "Training Matrix",
    "Distribution Policy", "Records Retention Schedule", "Approval Workflow Procedure",
    "Obsolete Copy Control", "Release Checklist", "Audit Trail Policy",
    "Version Control Standard", "Access Review Procedure", "Incident Response Policy",
    "Backup Verification Schedule", "Vendor Notification Procedure",
    "Confidentiality Agreement", "Privileged Access Policy", "Data Retention Policy",
    "Quality Assurance Checklist", "Continuity Plan", "Document Numbering Standard",
]
VERSIONS = ["1.0", "2.1", "3.0", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7",
            "4.8", "4.9", "4.10", "5.0", "6.1"]
OWNERS = ["Quality Systems Office", "Records Coordinator", "Document Control Team",
          "Department Leads", "Compliance Director"]
STATUSES = ["Corrected", "Released", "Ready"]
PRIVATE_NOTES = [
    "unverified draft values", "PRIVATE reviewer note", "duplicate working row",
    "legal hold note", "raw intake draft", "correction queued",
]

HEADER_LINES = [
    "DRAFT controlled document aproval packet",
    "QMS-PR-700 version 4.1 has effectve date 2026-07-01 and owner QA analyst.",
    "Interim Approver is listed, trainng due 2026-08-25, retetion is 5 years, "
    "obsolte copy retirement 2026-09-05.",
    "PRIVATE TODO: distribtuion list uncertain and aproval evidence incomplete.",
    "DRAFT internal release record: the working entries below must be rebuilt "
    "from the controlled records register.",
]


def make_records(n: int, rng: random.Random) -> list[dict]:
    """Deterministic per-variant controlled document records.

    Ids (``DOC-001``...) and effective dates are unique; document names are
    unique via the prefix pool + ordinal suffix. Effective dates (and the
    effective+14 day training-due dates) are drawn from a deterministic
    sequential window that skips the frozen forbidden wrong-date values
    (2026-07-01, 2026-08-25, 2026-09-05), so per-record facts can never collide
    with the parent task's forbidden phrases.
    """
    if n < 1:
        raise ValueError("record count must be >= 1")
    forbidden = {"2026-07-01", "2026-08-25", "2026-09-05"}
    base = datetime.date(2026, 1, 1)
    records = []
    index = 0
    cursor = 0
    while len(records) < n:
        effective = base + datetime.timedelta(days=cursor)
        training = effective + datetime.timedelta(days=14)
        if effective.isoformat() not in forbidden and training.isoformat() not in forbidden:
            records.append({
                "id": f"DOC-{index + 1:03d}",
                "name": (f"{NAME_PREFIXES[index % len(NAME_PREFIXES)]} "
                         f"{index // len(NAME_PREFIXES) + 1}"),
                "version": rng.choice(VERSIONS),
                "effective_date": effective.isoformat(),
                "owner": rng.choice(OWNERS),
                "training_due": training.isoformat(),
                "retention": RETENTION,
                "status": rng.choice(STATUSES),
            })
            index += 1
        cursor += 1
    assert len({r["id"] for r in records}) == n
    assert len({r["effective_date"] for r in records}) == n
    assert len({r["name"] for r in records}) == n
    for r in records:
        assert r["effective_date"] not in forbidden
        assert r["training_due"] not in forbidden
    return records


def write_records_json(variant_id: str, records: list[dict], out_dir: Path) -> Path:
    data = {
        "schema": "docops-scaling-records-v1",
        "variant_task_id": variant_id,
        "seed": common.VARIANTS[variant_id]["seed"],
        "doc_id": DOC_ID,
        "version": VERSION,
        "effective_date": EFFECTIVE_DATE,
        "owner": OWNER,
        "approver": APPROVER,
        "training_due": TRAINING_DUE,
        "retention": RETENTION,
        "retirement": RETIREMENT,
        "records": records,
    }
    common.write_json(out_dir / "records.json", data)
    return out_dir / "records.json"


def write_source_docx(records: list[dict], out_dir: Path, input_name: str) -> Path:
    """Draft input: DRAFT/internal banner + per-record working entries + one
    working table. The builder verifies the DRAFT marker and rebuilds clean."""
    doc = Document()
    doc.core_properties.author = "DocOps synthetic scale generator"
    doc.core_properties.last_modified_by = "DocOps synthetic scale generator"
    doc.core_properties.title = "DRAFT controlled document release packet"
    doc.core_properties.created = datetime.datetime(2026, 11, 2, 0, 0, 0)
    doc.core_properties.modified = datetime.datetime(2026, 11, 2, 0, 0, 0)

    title = doc.add_paragraph(HEADER_LINES[0], style="Title")
    for line in HEADER_LINES[1:]:
        doc.add_paragraph(line)

    for record in records:
        doc.add_paragraph(
            f"Record {record['id']} — DRAFT Internal Working Entry",
            style="Heading 2",
        )
        doc.add_paragraph(
            f"Working name: {record['name']}. Draft version: {record['version']}. "
            f"PRIVATE reviewer note: {rng_note(record)}."
        )

    working = doc.add_table(rows=1, cols=4)
    working.style = "Table Grid"
    for col, value in enumerate(["Record ID", "Working Name", "Draft Version",
                                 "PRIVATE Note"]):
        working.rows[0].cells[col].text = value
    for record in records:
        cells = working.add_row().cells
        cells[0].text = record["id"]
        cells[1].text = record["name"]
        cells[2].text = record["version"]
        cells[3].text = rng_note(record)

    output = out_dir / input_name
    tmp = output.parent / f".tmp-{input_name}"
    doc.save(str(tmp))
    common.deterministic_zip(tmp, output)
    tmp.unlink(missing_ok=True)
    return output


def rng_note(record: dict) -> str:
    # Deterministic note derived from the id only (no RNG state consumed by the
    # docx writer).
    return PRIVATE_NOTES[int(record["id"].split("-")[1]) % len(PRIVATE_NOTES)]


def generate(variant_id: str, out_dir: Path, write_raw_records: bool = True) -> dict:
    v = common.VARIANTS[variant_id]
    n = v["scale"]["records"]
    rng = random.Random(v["seed"])
    records = make_records(n, rng)

    out_dir.mkdir(parents=True, exist_ok=True)
    records_path = write_records_json(variant_id, records, out_dir)
    input_name = (
        f"docops_v2_l3_001_docx_controlled_document_release_repair_input_"
        f"{v['output_suffix']}.docx"
    )
    input_path = write_source_docx(records, out_dir, input_name)

    src_doc = Document(str(input_path))
    src_paragraphs = len(src_doc.paragraphs)
    src_tables = len(src_doc.tables)
    src_table_rows = sum(len(t.rows) for t in src_doc.tables)

    if write_raw_records:
        common.write_json(
            out_dir / "raw_records.json",
            {"schema": "docops-scaling-raw-records-v1",
             "variant_task_id": variant_id,
             "records": records},
        )

    first = records[0]
    middle = records[n // 2]
    last = records[-1]
    scale_metadata = {
        "records": n,
        "record_ids": [r["id"] for r in records],
        "record_id_summary": {
            "unit": "controlled_document",
            "first": first["id"],
            "middle": middle["id"],
            "last": last["id"],
            "count": n,
            "unique": True,
        },
        "input_records": n,
        "expected_output_tables": 6,
        "expected_output_table_rows": 29 + n,
        "expected_headings": len(HEADINGS),
        "expected_paragraphs": 35,
        "expected_images": 0,
        "render_scope": "full document; all pages rendered at 150 DPI",
        "first_record": first,
        "middle_record": middle,
        "last_record": last,
        "preserved_parent_behaviour": [
            "all parent chapter headings and their order",
            "correction register, metadata, revision history, workflow and "
            "retirement tables with the frozen public values",
            "release margins (0.8 in), footer with page field, header band, "
            "title/heading/table-header styling and core properties",
            "page breaks before Distribution and Training Workflow and Final "
            "Release Appendix",
            "byte-deterministic output and DRAFT-source verification",
        ],
        "changed_parent_behaviour": [
            "the Controlled Document Register table now holds one real row per "
            "declared record instead of a fixed register, so table row count "
            "is driven by the actual record count",
            "the register narrative reports the actual record count",
        ],
        "source_paragraphs": src_paragraphs,
        "source_tables": src_tables,
        "source_table_rows": src_table_rows,
        "input_bytes": input_path.stat().st_size,
        "input_sha256": common.sha256_file(input_path),
        "records_json_sha256": common.sha256_file(records_path),
        "seed": v["seed"],
    }

    meta = common.default_task_metadata(variant_id)
    meta["scale_metadata"] = scale_metadata
    meta["input_path"] = f"/root/{input_name}"
    meta["output_path"] = (
        f"/root/submission/"
        f"docops_v2_l3_001_docx_controlled_document_release_repair_output_"
        f"{v['output_suffix']}.docx"
    )
    meta["modified_workflow"] = [
        "01 build: stage order and processing tools unchanged from the frozen "
        "001 create_packet.py; the correction register and every release "
        "chapter are derived from the frozen records.json, and the controlled "
        "document register table iterates all N records (one real row per "
        "record), so output size is driven by the actual record count",
        "02 validate: dynamic validator reads frozen expected.json and covers "
        "every record plus document-level controls (metadata/style/margin/"
        "footer/header checks run once, not repeated per record)",
        "03 render: unchanged LibreOffice -> PDF -> 150 DPI PNG render; page "
        "count is decided by real layout",
    ]
    meta["measurement_scope"] = (
        "Scales the number of controlled document records that must go through "
        "the full frozen 001 pipeline: draft-material removal, correction "
        "register, controlled metadata, revision history, distribution and "
        "training workflow, obsolete-copy retirement checklist and final "
        "release appendix. Both the source DOCX working content and the final "
        "release packet scale with the record count. Page count is decided by "
        "real LibreOffice layout; no page count is forged here."
    )
    common.write_json(out_dir / "task_metadata.json", meta)
    (out_dir / "instruction.md").write_text(instruction_md(meta), encoding="utf-8")
    (out_dir / "original_task_description.txt").write_text(
        original_description(meta), encoding="utf-8")

    return {
        "input": input_path,
        "records": records_path,
        "task_metadata": out_dir / "task_metadata.json",
        "scale_metadata": scale_metadata,
    }


def instruction_md(meta: dict) -> str:
    v = common.VARIANTS[meta["variant_task_id"]]
    sm = meta["scale_metadata"]
    return f"""# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`001`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 001 (frozen `docops_v2_l3_001_docx_controlled_document_release_repair`)
- `synthetic`: true
- generator: {meta['generator']} (version {meta['generator_version']})
- seed: {meta['seed']}
- scale: {sm['records']} controlled document records

## Inputs

- Source document: `{meta['input_path']}`
- Frozen record declaration: `/root/tmp/docs/records.json`
- Frozen expected oracle: `/root/tmp/docs/expected.json`
- Original benchmark seed description: `/root/original_task_description.txt`

## Goal

Prepare a clean controlled document release repair packet from a DRAFT internal
Word source. Every declared record in `records.json` must go through the same
sequential workflow as parent task 001, and every record's corrected release
facts must appear in the final packet.

## Required Sequential Workflow

1. Verify the source still carries the DRAFT/internal-error marker.
2. Remove all DRAFT/PRIVATE/TODO working content.
3. Apply the correction register (document ID `QMS-PR-007`, version `4.2`,
   effective `2026-08-01`, owner `Quality Systems Office`, approver
   `Compliance Director`, training due `2026-08-15`, retention `6 years`,
   obsolete copy retirement `2026-08-05`) and fix the spelling errors.
4. Rebuild the controlled document metadata, revision history, distribution
   and training workflow, obsolete copy retirement checklist and final release
   appendix from `records.json`; one register row per record.
5. Set release metadata, footer, margins, styles and page breaks once.
6. Save the clean public document as a new `.docx` without modifying the source.

## Required Style and Layout

- `Aptos Display` bold title text, 18 pt, color `0F4C5C`; `Aptos` body 10.5 pt.
- Heading text in color `0F4C5C`.
- Table header fill `0F4C5C` with white bold text.
- All page margins `0.8` inches.
- Footer `QMS-PR-007 | Version 4.2` + `Controlled Document Release Repair
  Packet | 2026` + page field.

## Output Requirements

- Save to `{meta['output_path']}`.
- Do not modify the source document in place.
- Keep the output format the same as the input document (`.docx`).
- Complete the full ordered workflow, not just local text replacement.
"""


def original_description(meta: dict) -> str:
    sm = meta["scale_metadata"]
    return (
        "Synthetic scale variant of frozen task 001: controlled document "
        "release repair packet with version, approval, training, distribution, "
        "obsolete-copy, and spelling errors. The source contains "
        f"{sm['records']} controlled document records, each with DRAFT "
        "internal working entries that must be replaced by corrected release "
        "facts. Scale is defined by the number of records that must pass "
        "through the whole frozen pipeline and appear in the final packet. "
        f"Variant {meta['variant_task_id']}, seed {meta['seed']}. "
        "This is a synthetic input, not a historical benchmark task."
    )
