"""Shared helpers and variant registry for the DocOps synthetic scale package.

All synthetic scale work lives under docops/scaling/. Nothing here reads or
modifies the frozen official payload; the original twelve tasks and their
materials are never touched.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SCALING_ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_ROOT = SCALING_ROOT / "payload"
STAGING_ROOT = SCALING_ROOT / "staging"

# Default order used when `--variants` is omitted. Kept byte/behaviour
# identical to the first round: only the four 014/021 variants are selected by
# default, so an unqualified prepare never generates the Word/PDF variants.
VARIANT_ORDER = ["014-n1000", "014-n10000", "021-g5", "021-g10"]

VARIANTS = {
    "014-n1000": {
        "parent": "014",
        "kind": "xlsx",
        "format": "xlsx",
        "generator": "docops/scaling/cases/014/synth.py",
        "generator_version": "1.0",
        "seed": 2026110501,
        "scale": {"deduped_applications": 1000},
        "derived": {"raw_rows": None, "duplicates": None, "valid": 1000},
        "output_suffix": "n1000",
    },
    "014-n10000": {
        "parent": "014",
        "kind": "xlsx",
        "format": "xlsx",
        "generator": "docops/scaling/cases/014/synth.py",
        "generator_version": "1.0",
        "seed": 2026110502,
        "scale": {"deduped_applications": 10000},
        "derived": {"raw_rows": None, "duplicates": None, "valid": 10000},
        "output_suffix": "n10000",
    },
    "021-g5": {
        "parent": "021",
        "kind": "pptx",
        "format": "pptx",
        "generator": "docops/scaling/cases/021/synth.py",
        "generator_version": "1.0",
        "seed": 2026110503,
        "scale": {"regions": 5, "pages": 40},
        "derived": {"regions": 5, "pages": 40},
        "output_suffix": "g5",
    },
    "021-g10": {
        "parent": "021",
        "kind": "pptx",
        "format": "pptx",
        "generator": "docops/scaling/cases/021/synth.py",
        "generator_version": "1.0",
        "seed": 2026110504,
        "scale": {"regions": 10, "pages": 80},
        "derived": {"regions": 10, "pages": 80},
        "output_suffix": "g10",
    },
    # Word / PDF scaling variants (second round). Registered here so they can be
    # selected explicitly, but deliberately NOT part of VARIANT_ORDER so the
    # default prepare behaviour (014/021 only) is unchanged.
    "003-u100": {
        "parent": "003",
        "kind": "docx",
        "format": "docx",
        "generator": "docops/scaling/cases/003/synth.py",
        "generator_version": "1.0",
        "seed": 2026110509,
        "scale": {"business_units": 100},
        "derived": {"business_units": 100},
        "output_suffix": "u100",
    },
    "003-u500": {
        "parent": "003",
        "kind": "docx",
        "format": "docx",
        "generator": "docops/scaling/cases/003/synth.py",
        "generator_version": "1.0",
        "seed": 2026110510,
        "scale": {"business_units": 500},
        "derived": {"business_units": 500},
        "output_suffix": "u500",
    },
    "037-u5": {
        "parent": "037",
        "kind": "pdf",
        "format": "pdf",
        "generator": "docops/scaling/cases/037/synth.py",
        "generator_version": "1.0",
        "seed": 2026110507,
        "scale": {"notice_groups": 5, "pages": 25},
        "derived": {"notice_groups": 5, "pages": 25},
        "output_suffix": "u5",
    },
    "037-u20": {
        "parent": "037",
        "kind": "pdf",
        "format": "pdf",
        "generator": "docops/scaling/cases/037/synth.py",
        "generator_version": "1.0",
        "seed": 2026110508,
         "scale": {"notice_groups": 20, "pages": 100},
         "derived": {"notice_groups": 20, "pages": 100},
         "output_suffix": "u20",
     },
    # ---- new round-3 Word variants ----
    "001-u100": {
        "parent": "001",
        "kind": "docx",
        "format": "docx",
        "generator": "docops/scaling/cases/001/synth.py",
        "generator_version": "1.0",
        "seed": 2026110601,
        "scale": {"records": 100},
        "derived": {"records": 100},
        "output_suffix": "u100",
    },
    "001-u500": {
        "parent": "001",
        "kind": "docx",
        "format": "docx",
        "generator": "docops/scaling/cases/001/synth.py",
        "generator_version": "1.0",
        "seed": 2026110602,
        "scale": {"records": 500},
        "derived": {"records": 500},
        "output_suffix": "u500",
    },
    "009-u100": {
        "parent": "009",
        "kind": "docx",
        "format": "docx",
        "generator": "docops/scaling/cases/009/synth.py",
        "generator_version": "1.0",
        "seed": 2026110603,
        "scale": {"incident_cases": 100},
        "derived": {"incident_cases": 100},
        "output_suffix": "u100",
    },
    "009-u500": {
        "parent": "009",
        "kind": "docx",
        "format": "docx",
        "generator": "docops/scaling/cases/009/synth.py",
        "generator_version": "1.0",
        "seed": 2026110604,
        "scale": {"incident_cases": 500},
        "derived": {"incident_cases": 500},
        "output_suffix": "u500",
    },
    # ---- new round-3 Excel variants ----
    "013-v100": {
        "parent": "013",
        "kind": "xlsx",
        "format": "xlsx",
        "generator": "docops/scaling/cases/013/synth.py",
        "generator_version": "1.0",
        "seed": 2026110605,
        "scale": {"vendors": 100},
        "derived": {"vendors": 100},
        "output_suffix": "v100",
    },
    "013-v1000": {
        "parent": "013",
        "kind": "xlsx",
        "format": "xlsx",
        "generator": "docops/scaling/cases/013/synth.py",
        "generator_version": "1.0",
        "seed": 2026110606,
        "scale": {"vendors": 1000},
        "derived": {"vendors": 1000},
        "output_suffix": "v1000",
    },
    "016-u100": {
        "parent": "016",
        "kind": "xlsx",
        "format": "xlsx",
        "generator": "docops/scaling/cases/016/synth.py",
        "generator_version": "1.0",
        "seed": 2026110607,
        "scale": {"business_units": 100, "periods": 4, "model_rows": 400},
        "derived": {"business_units": 100, "periods": 4, "model_rows": 400},
        "output_suffix": "u100",
    },
    "016-u500": {
        "parent": "016",
        "kind": "xlsx",
        "format": "xlsx",
        "generator": "docops/scaling/cases/016/synth.py",
        "generator_version": "1.0",
        "seed": 2026110608,
        "scale": {"business_units": 500, "periods": 4, "model_rows": 2000},
        "derived": {"business_units": 500, "periods": 4, "model_rows": 2000},
        "output_suffix": "u500",
    },
    # ---- new round-3 PPT variants ----
    "026-u5": {
        "parent": "026",
        "kind": "pptx",
        "format": "pptx",
        "generator": "docops/scaling/cases/026/synth.py",
        "generator_version": "1.0",
        "seed": 2026110609,
        "scale": {"units": 5, "slides_per_unit": 9, "pages": 45},
        "derived": {"units": 5, "slides_per_unit": 9, "pages": 45},
        "output_suffix": "u5",
    },
    "026-u10": {
        "parent": "026",
        "kind": "pptx",
        "format": "pptx",
        "generator": "docops/scaling/cases/026/synth.py",
        "generator_version": "1.0",
        "seed": 2026110610,
        "scale": {"units": 10, "slides_per_unit": 9, "pages": 90},
        "derived": {"units": 10, "slides_per_unit": 9, "pages": 90},
        "output_suffix": "u10",
    },
    "029-u5": {
        "parent": "029",
        "kind": "pptx",
        "format": "pptx",
        "generator": "docops/scaling/cases/029/synth.py",
        "generator_version": "1.0",
        "seed": 2026110611,
        "scale": {"units": 5, "slides_per_unit": 8, "pages": 41},
        "derived": {"units": 5, "slides_per_unit": 8, "pages": 41},
        "output_suffix": "u5",
    },
    "029-u10": {
        "parent": "029",
        "kind": "pptx",
        "format": "pptx",
        "generator": "docops/scaling/cases/029/synth.py",
        "generator_version": "1.0",
        "seed": 2026110612,
        "scale": {"units": 10, "slides_per_unit": 8, "pages": 81},
        "derived": {"units": 10, "slides_per_unit": 8, "pages": 81},
        "output_suffix": "u10",
    },
    # ---- new round-3 PDF variants ----
    "031-u5": {
        "parent": "031",
        "kind": "pdf",
        "format": "pdf",
        "generator": "docops/scaling/cases/031/synth.py",
        "generator_version": "1.0",
        "seed": 2026110613,
        "scale": {"groups": 5, "pages": 25},
        "derived": {"groups": 5, "pages": 25},
        "output_suffix": "u5",
    },
    "031-u20": {
        "parent": "031",
        "kind": "pdf",
        "format": "pdf",
        "generator": "docops/scaling/cases/031/synth.py",
        "generator_version": "1.0",
        "seed": 2026110614,
        "scale": {"groups": 20, "pages": 100},
        "derived": {"groups": 20, "pages": 100},
        "output_suffix": "u20",
    },
    "pdfwf005-u5": {
        "parent": "pdfwf005",
        "kind": "pdf",
        "format": "pdf",
        "generator": "docops/scaling/cases/pdfwf005/synth.py",
        "generator_version": "1.0",
        "seed": 2026110615,
        "scale": {"groups": 5, "input_pages": 35, "output_pages": 30},
        "derived": {"groups": 5, "input_pages": 35, "output_pages": 30},
        "output_suffix": "u5",
    },
    "pdfwf005-u20": {
        "parent": "pdfwf005",
        "kind": "pdf",
        "format": "pdf",
        "generator": "docops/scaling/cases/pdfwf005/synth.py",
        "generator_version": "1.0",
        "seed": 2026110616,
        "scale": {"groups": 20, "input_pages": 140, "output_pages": 120},
        "derived": {"groups": 20, "input_pages": 140, "output_pages": 120},
        "output_suffix": "u20",
    },
}

# Full 24-variant active set (existing eight byte-preserved + new sixteen).
VARIANT_ORDER_ALL = [
    "014-n1000", "014-n10000", "021-g5", "021-g10",
    "003-u100", "003-u500", "037-u5", "037-u20",
    "001-u100", "001-u500",
    "009-u100", "009-u500",
    "013-v100", "013-v1000",
    "016-u100", "016-u500",
    "026-u5", "026-u10",
    "029-u5", "029-u10",
    "031-u5", "031-u20",
    "pdfwf005-u5", "pdfwf005-u20",
]

# Explicit selection helper for the Word/PDF round (never used as a default).
VARIANT_ORDER_WORD_PDF = ["003-u100", "003-u500", "037-u5", "037-u20"]

PARENT_SOURCE = {
    "014": {
        "input": Path(
            "payload/tasks/014/seed/root/"
            "docops_v2_l3_014_xlsx_disaster_housing_grant_public_release_input.xlsx"
        ),
        "scripts": [
            "payload/tasks/014/seed/root/tmp/docs/build_disaster_release_v1.py",
            "payload/tasks/014/seed/root/tmp/docs/finalize_disaster_release_ooxml_v3.py",
            "payload/tasks/014/seed/root/tmp/docs/validate_disaster_release_v1.py",
        ],
    },
    "021": {
        "input": Path(
            "payload/tasks/021/seed/root/"
            "docops_v2_l3_021_pptx_shelter_accessibility_public_remediation_input.pptx"
        ),
        "scripts": [
            "payload/tasks/021/seed/root/tmp/docs/build_public_shelter_briefing.py",
            "payload/tasks/021/seed/root/tmp/docs/make_qa_fonts.py",
            "payload/tasks/021/seed/root/tmp/docs/validate_public_shelter_briefing.py",
        ],
    },
    "003": {
        "input": Path(
            "payload/tasks/003/seed/root/"
            "docops_v2_l3_003_docx_public_records_release_metadata_cleanup_input.docx"
        ),
        "scripts": [
            "payload/tasks/003/seed/root/tmp/docs/build_public_packet.py",
            "payload/tasks/003/seed/root/tmp/docs/audit_public_packet.py",
        ],
    },
    "037": {
        "input": Path(
            "payload/tasks/037/seed/root/"
            "docops_v2_l3_037_pdf_bus_detour_notice_layout_repair_input.pdf"
        ),
        "scripts": [
            "payload/tasks/037/seed/root/tmp/docs/build_bus_detour_packet.py",
            "payload/tasks/037/seed/root/tmp/docs/validate_bus_detour_packet.py",
        ],
    },
    "001": {
        "input": Path(
            "payload/tasks/001/seed/root/"
            "docops_v2_l3_001_docx_controlled_document_release_repair_input.docx"
        ),
        "scripts": [
            "payload/tasks/001/seed/root/create_packet.py",
        ],
    },
    "009": {
        "input": Path(
            "payload/tasks/009/seed/root/"
            "docops_v2_l3_009_docx_incident_manual_publication_input.docx"
        ),
        "scripts": [
            "payload/tasks/009/seed/root/tmp/docs/build_incident_manual_publication.py",
            "payload/tasks/009/seed/root/tmp/docs/validate_incident_manual_publication.py",
        ],
    },
    "013": {
        "input": Path(
            "payload/tasks/013/seed/root/"
            "docops_v2_l3_013_xlsx_procurement_bid_evaluation_release_input.xlsx"
        ),
        "scripts": [
            "payload/tasks/013/seed/root/tmp/docs/build_public_bid_workbook.py",
            "payload/tasks/013/seed/root/tmp/docs/verify_public_bid_workbook.py",
        ],
    },
    "016": {
        "input": Path(
            "payload/tasks/016/seed/root/"
            "docops_v2_l3_016_xlsx_forecast_driver_cascade_input.xlsx"
        ),
        "scripts": [
            "payload/tasks/016/seed/root/tmp/docs/build_forecast_dashboard_v1.py",
        ],
    },
    "026": {
        "input": Path(
            "payload/tasks/026/seed/root/"
            "docops_v2_l3_026_pptx_climate_disclosure_chart_rebuild_input.pptx"
        ),
        "scripts": [
            "payload/tasks/026/seed/root/tmp/docs/build_climate_disclosure.py",
            "payload/tasks/026/seed/root/tmp/docs/qa_climate_disclosure.py",
        ],
    },
    "029": {
        "input": Path(
            "payload/tasks/029/seed/root/"
            "docops_v2_l3_029_pptx_qbr_release_deck_input.pptx"
        ),
        "scripts": [
            "payload/tasks/029/seed/root/tmp/docs/build_release_deck.py",
            "payload/tasks/029/seed/root/tmp/docs/validate_release_deck.py",
        ],
    },
    "031": {
        "input": Path(
            "payload/tasks/031/seed/root/"
            "docops_v2_l3_031_pdf_public_hearing_packet_flatten_release_input.pdf"
        ),
        "scripts": [
            "payload/tasks/031/seed/root/tmp/docs/build_public_packet.py",
            "payload/tasks/031/seed/root/tmp/docs/validate_public_packet.py",
        ],
    },
    "pdfwf005": {
        "input": Path(
            "payload/tasks/pdfwf005/seed/root/"
            "pdfwf_005_closeout_binder_page_labels_and_bookmarks_seed.pdf"
        ),
        "scripts": [
            "payload/tasks/pdfwf005/seed/root/tmp/docs/rebuild_closeout_binder.py",
        ],
    },
}


def repo_root() -> Path:
    return SCALING_ROOT.parents[1]


def docops_root() -> Path:
    return SCALING_ROOT.parent


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def deterministic_zip(src, dst, transform=None):
    """Repack an OOXML archive with fixed entry timestamps so identical content
    always produces identical bytes. ``transform`` optionally rewrites bytes for
    a given entry name (e.g. a fixed core.xml modified stamp)."""
    import zipfile

    with zipfile.ZipFile(src, "r") as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if transform is not None and item.filename in transform:
                data = transform[item.filename](data)
            item.date_time = (1980, 1, 1, 0, 0, 0)
            item.extra = b""
            item.comment = b""
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o600 << 16
            zout.writestr(item, data)


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parent_material_hash(task: str) -> dict:
    """Hash of the frozen parent input and scripts (read-only reference)."""
    docops = docops_root()
    mapping = PARENT_SOURCE[task]
    out = {}
    for rel in [mapping["input"]] + mapping["scripts"]:
        path = docops / rel
        out[str(rel)] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    return out


def default_task_metadata(variant_id: str) -> dict:
    v = VARIANTS[variant_id]
    return {
        "schema": "docops-scaling-task-metadata-v1",
        "variant_task_id": variant_id,
        "synthetic": True,
        "parent_task": v["parent"],
        "kind": v["kind"],
        "seed": v["seed"],
        "scale": v["scale"],
        "generator": v["generator"],
        "generator_version": v["generator_version"],
        "modified_workflow": None,
        "scale_metadata": {},
    }
