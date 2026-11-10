"""Scale-payload preparation scheduler for the DocOps synthetic variants.

This tool ONLY generates inputs, prepared materials, expected oracles, recipes,
commands and the payload index. It never executes a workload, never invokes
LibreOffice / pdftoppm / montage, never runs the replay, and never touches the
frozen official payload. The replay loop is out of ROI here.

Safety:
- The output target is validated before any synthesis: it may not be the
  official payload, the repository root, any parent of a protected path, the
  source tree, the staging tree, or a dangerous overlap; symlinks are resolved.
- Overwriting an existing target requires an explicit --force-replace, and only
  happens AFTER the freshly staged payload passes the static validation.
  Failure always keeps the existing active package untouched.

Sync mode:
- `prepare.py sync` refreshes only derived files (scripts, commands, recipe,
  catalog, index) for existing variants without regenerating inputs; frozen
  input bytes stay identical.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from cases import common

SCALING = Path(__file__).resolve().parent
PAYLOAD = SCALING / "payload"
STAGING = Path(os.environ.get("SCALING_STAGING", SCALING / "staging"))
OFFICIAL_PAYLOAD = SCALING.parent / "payload"
REPO_ROOT = SCALING.parents[1]

# make `docops` importable so relative package imports inside cases work
sys.path.insert(0, str(SCALING.parent))

GENERATOR_VERSION = "1.0"

# Per-parent registration: each frozen task gets its own builder scripts,
# commands, step phases, material and output path. Dispatch is by parent task
# id (never by file format) so 013 never reuses 014's scripts and 001 never
# reuses 003's.
PARENT_CONFIG = {
    "001": {
        "kind": "docx",
        "material": "records.json",
        "scripts": ["build_controlled_document_release_variant.py",
                    "validate_controlled_document_release_variant.py"],
        "commands": {"01": "build", "02": "validate", "03": "render"},
        "phases": {"01": "workflow", "02": "workflow", "03": "workflow"},
        "output": lambda suffix: (
            f"/root/submission/docops_v2_l3_001_docx_controlled_document_release_repair_output_{suffix}.docx"),
    },
    "009": {
        "kind": "docx",
        "material": "cases.json",
        "scripts": ["build_incident_manual_variant.py",
                    "update_toc_and_render.py",
                    "validate_incident_manual_variant.py"],
        "commands": {"01": "build", "02": "render_and_update_toc", "03": "validate"},
        "phases": {"01": "workflow", "02": "workflow", "03": "workflow"},
        "output": lambda suffix: (
            f"/root/submission/docops_v2_l3_009_docx_incident_manual_publication_output_{suffix}.docx"),
    },
    "013": {
        "kind": "xlsx",
        "material": "vendors.json",
        "scripts": ["build_bid_evaluation_variant.py",
                    "validate_bid_evaluation_variant.py"],
        "commands": {"01": "build_recalculate_verify", "02": "render_contact_sheet"},
        "phases": {"01": "workflow", "02": "workflow"},
        "output": lambda suffix: (
            f"/root/submission/docops_v2_l3_013_xlsx_procurement_bid_evaluation_release_output_{suffix}.xlsx"),
    },
    "016": {
        "kind": "xlsx",
        "material": "units.json",
        "scripts": ["build_forecast_dashboard_variant.py",
                    "validate_forecast_dashboard_variant.py"],
        "commands": {"01": "build_recalculate_convert", "02": "render_dashboard",
                     "03": "verify_scenario_cascade"},
        "phases": {"01": "workflow", "02": "workflow", "03": "workflow"},
        "output": lambda suffix: (
            f"/root/submission/docops_v2_l3_016_xlsx_forecast_driver_cascade_output_{suffix}.xlsx"),
    },
    "026": {
        "kind": "pptx",
        "material": "units.json",
        "scripts": ["build_climate_disclosure_variant.py",
                    "validate_climate_disclosure_variant.py"],
        "commands": {"01": "build", "02": "convert_pdf", "03": "render", "04": "validate"},
        "phases": {"01": "workflow", "02": "workflow", "03": "workflow", "04": "workflow"},
        "output": lambda suffix: (
            f"/root/submission/docops_v2_l3_026_pptx_climate_disclosure_chart_rebuild_output_{suffix}.pptx"),
    },
    "029": {
        "kind": "pptx",
        "material": "units.json",
        "scripts": ["build_qbr_release_variant.py",
                    "validate_qbr_release_variant.py"],
        "commands": {"01": "build_validate_render"},
        "phases": {"01": "workflow"},
        "output": lambda suffix: (
            f"/root/submission/docops_v2_l3_029_pptx_qbr_release_deck_output_{suffix}.pptx"),
    },
    "031": {
        "kind": "pdf",
        "material": "notices.json",
        "scripts": ["build_public_packet_variant.py",
                    "validate_public_packet_variant.py"],
        "commands": {"01": "build", "02": "render", "03": "validate"},
        "phases": {"01": "workflow", "02": "workflow", "03": "workflow"},
        "output": lambda suffix: (
            f"/root/submission/docops_v2_l3_031_pdf_public_hearing_packet_flatten_release_output_{suffix}.pdf"),
    },
    "pdfwf005": {
        "kind": "pdf",
        "material": "groups.json",
        "scripts": ["rebuild_closeout_binder_variant.py",
                    "validate_closeout_binder_variant.py"],
        "commands": {"01": "build_and_pdfinfo", "02": "final_text",
                     "03": "page_labels_and_bookmarks", "04": "render_contact_sheet",
                     "05": "forbidden_text_diagnostic"},
        "phases": {"01": "workflow", "02": "workflow", "03": "workflow",
                   "04": "workflow", "05": "workflow"},
        "output": lambda suffix: (
            f"/root/submission/pdfwf_005_closeout_binder_page_labels_and_bookmarks_seed_{suffix}.pdf"),
    },
    "014": {
        "kind": "xlsx",
        "material": None,
        "scripts": ["build_disaster_release_variant.py",
                    "finalize_disaster_release_variant_ooxml.py",
                    "validate_disaster_release_variant.py"],
        "commands": {"01": "build", "02": "recalculate", "03": "final_ooxml_repair_and_validate",
                     "04": "convert_pdf", "05": "render"},
        "phases": {"01": "workflow", "02": "workflow", "03": "workflow",
                   "04": "workflow", "05": "workflow"},
        "output": lambda suffix: (
            f"/root/submission/docops_v2_l3_014_xlsx_disaster_housing_grant_public_release_output_{suffix}.xlsx"),
    },
    "021": {
        "kind": "pptx",
        "material": "regions.json",
        "scripts": ["make_qa_fonts.py", "build_public_shelter_briefing_variant.py",
                    "validate_public_shelter_briefing_variant.py", "make_contact_sheets.py"],
        "commands": {"01": "prepare_render_fonts", "02": "build_validate_render"},
        "phases": {"01": "environment_setup", "02": "workflow"},
        "output": lambda suffix: (
            f"/root/submission/docops_v2_l3_021_pptx_shelter_accessibility_public_remediation_output_{suffix}.pptx"),
    },
    "003": {
        "kind": "docx",
        "material": "units.json",
        "scripts": ["build_public_packet_variant.py", "validate_public_packet_variant.py"],
        "commands": {"01": "build", "02": "validate", "03": "render"},
        "phases": {"01": "workflow", "02": "workflow", "03": "workflow"},
        "output": lambda suffix: (
            f"/root/submission/docops_v2_l3_003_docx_public_records_release_metadata_cleanup_output_{suffix}.docx"),
    },
    "037": {
        "kind": "pdf",
        "material": "notices.json",
        "scripts": ["build_bus_detour_packet_variant.py", "validate_bus_detour_packet_variant.py"],
        "commands": {"01": "build_render", "02": "validate"},
        "phases": {"01": "workflow", "02": "workflow"},
        "output": lambda suffix: (
            f"/root/submission/docops_v2_l3_037_pdf_bus_detour_notice_layout_repair_output_{suffix}.pdf"),
    },
}


# The existing eight scale variants are carried into the unified package
# byte-identically (never regenerated). Map variant -> original payload dir.
EXISTING_SOURCE = {
    "014-n1000": SCALING / "payload",
    "014-n10000": SCALING / "payload",
    "021-g5": SCALING / "payload",
    "021-g10": SCALING / "payload",
    "003-u100": SCALING / "payload-word-pdf",
    "003-u500": SCALING / "payload-word-pdf",
    "037-u5": SCALING / "payload-word-pdf",
    "037-u20": SCALING / "payload-word-pdf",
}


def import_case(parent):
    return importlib.import_module(f"cases.{parent}.synth"), importlib.import_module(f"cases.{parent}.expected")


def seed_root(payload_root: Path, variant: str) -> Path:
    return payload_root / "tasks" / variant / "seed" / "root"


def commands_dir(payload_root: Path, variant: str) -> Path:
    return payload_root / "tasks" / variant / "commands"


def protected_roots() -> list[Path]:
    return [OFFICIAL_PAYLOAD.resolve(), REPO_ROOT.resolve(), SCALING.resolve(),
            STAGING.resolve(), SCALING.parent.resolve()]


def assert_safe_payload_out(payload_root: Path) -> Path:
    """Reject unsafe/dangerous output targets before any synthesis.

    Only the three explicitly designated scaling payload roots are allowed inside
    the repository tree: the round-1 ``payload``, the Word/PDF round
    ``payload-word-pdf``, and the unified 24-variant ``payload-all``. Every other
    in-tree target is still rejected.
    """
    resolved = payload_root.resolve()
    safe_defaults = {
        (SCALING / "payload").resolve(),
        (SCALING / "payload-word-pdf").resolve(),
        (SCALING / "payload-all").resolve(),
    }
    if resolved in safe_defaults:
        return resolved
    protected = protected_roots()
    for root in protected:
        if resolved == root:
            raise ValueError(f"unsafe --payload-out: equals protected path {root}")
        if resolved.is_relative_to(root):
            raise ValueError(f"unsafe --payload-out: {resolved} is inside protected path {root}")
        if root.is_relative_to(resolved):
            raise ValueError(f"unsafe --payload-out: {resolved} contains protected path {root}")
    return resolved


def step_bodies(variant: str, input_name: str, output_name: str, output_path: str) -> dict:
    v = common.VARIANTS[variant]
    parent = v["parent"]
    kind = PARENT_CONFIG[parent]["kind"]
    if kind == "xlsx":
        if parent == "014":
            return {
                "01": (f"python /root/tmp/docs/build_disaster_release_variant.py "
                       f"--input /root/{input_name} --output {output_path}"),
                "02": (f"python /root/.codex/skills/xlsx/scripts/recalc.py {output_path} 120"),
                "03": (f"python /root/tmp/docs/finalize_disaster_release_variant_ooxml.py "
                       f"--output {output_path} && python /root/tmp/docs/validate_disaster_release_variant.py "
                       f"--output {output_path} --expected /root/tmp/docs/expected.json"),
                "04": (f"mkdir -p /root/tmp/docs/preview && libreoffice --headless --convert-to pdf "
                       f"--outdir /root/tmp/docs/preview {output_path}"),
                "05": (f"pdftoppm -png -r 110 /root/tmp/docs/preview/{output_name.replace('.xlsx', '.pdf')} "
                       f"/root/tmp/docs/preview/page"),
            }
        if parent == "013":
            return {
                "01": (f"python /root/tmp/docs/build_bid_evaluation_variant.py "
                       f"--vendors /root/tmp/docs/vendors.json --output {output_path} && "
                       f"python /root/.codex/skills/xlsx/scripts/recalc.py {output_path} 60 && "
                       f"python /root/tmp/docs/validate_bid_evaluation_variant.py "
                       f"--output {output_path} --expected /root/tmp/docs/expected.json "
                       f"--report /root/tmp/docs/output_validation.json"),
                "02": (f"mkdir -p /root/tmp/docs/rendered-final && "
                       f"libreoffice --headless --convert-to pdf --outdir /root/tmp/docs/rendered-final "
                       f"{output_path} >/dev/null && "
                       f"pdftoppm -png -r 110 /root/tmp/docs/rendered-final/{output_name.replace('.xlsx', '.pdf')} "
                       f"/root/tmp/docs/rendered-final/final-page >/dev/null 2>&1 && "
                       f"montage /root/tmp/docs/rendered-final/final-page-*.png -thumbnail 620x480 "
                       f"-tile 2x5 -geometry +10+10 /root/tmp/docs/rendered-final/final-contact-sheet.png"),
            }
        if parent == "016":
            return {
                "01": (f"python /root/tmp/docs/build_forecast_dashboard_variant.py "
                       f"--units /root/tmp/docs/units.json --output {output_path} && "
                       f"python /root/.codex/skills/xlsx/scripts/recalc.py {output_path} 120 && "
                       f"mkdir -p /root/tmp/docs/render_landscape && "
                       f"soffice --headless --convert-to pdf --outdir /root/tmp/docs/render_landscape {output_path}"),
                "02": (f"pdfinfo /root/tmp/docs/render_landscape/{output_name.replace('.xlsx', '.pdf')} | "
                       f"sed -n '1,25p'; pdftoppm -f 1 -singlefile -png -r 150 "
                       f"/root/tmp/docs/render_landscape/{output_name.replace('.xlsx', '.pdf')} "
                       f"/root/tmp/docs/render_landscape/dashboard"),
                "03": (f"python /root/tmp/docs/validate_forecast_dashboard_variant.py "
                       f"--output {output_path} --expected /root/tmp/docs/expected.json "
                       f"--report /root/tmp/docs/output_validation.json"),
            }
        raise ValueError(parent)
    if kind == "pptx":
        if parent == "021":
            return {
                "01": ("python /root/tmp/docs/make_qa_fonts.py && mkdir -p /root/.local/share/fonts && "
                       "cp /root/tmp/docs/qa_fonts/*.ttf /root/.local/share/fonts/ && "
                       "fc-cache -f /root/.local/share/fonts >/dev/null && "
                       "fc-match 'Aptos Display' && fc-match 'Aptos'"),
                "02": (f"python /root/tmp/docs/build_public_shelter_briefing_variant.py "
                       f"--regions /root/tmp/docs/regions.json --output {output_path} && "
                       f"python /root/tmp/docs/validate_public_shelter_briefing_variant.py "
                       f"--output {output_path} --expected /root/tmp/docs/expected.json "
                       f"--report /root/tmp/docs/output_validation.json && "
                       f"mkdir -p /root/tmp/docs/render3 && "
                       f"python /root/.codex/skills/pptx/scripts/office/soffice.py --headless "
                       f"--convert-to pdf --outdir /root/tmp/docs/render3 {output_path} && "
                       f"pdftoppm -jpeg -r 150 /root/tmp/docs/render3/{output_name.replace('.pptx', '.pdf')} "
                       f"/root/tmp/docs/render3/slide && "
                       f"python /root/tmp/docs/make_contact_sheets.py /root/tmp/docs/render3 "
                       f"--expected /root/tmp/docs/expected.json"),
            }
        if parent == "026":
            return {
                "01": (f"python /root/tmp/docs/build_climate_disclosure_variant.py "
                       f"--units /root/tmp/docs/units.json --output {output_path}"),
                "02": (f"python /root/.codex/skills/pptx/scripts/office/soffice.py --headless "
                       f"--convert-to pdf --outdir /root/tmp/docs {output_path}"),
                "03": (f"mkdir -p /root/tmp/docs/rendered && pdftoppm -jpeg -r 150 "
                       f"/root/tmp/docs/{output_name.replace('.pptx', '.pdf')} "
                       f"/root/tmp/docs/rendered/slide"),
                "04": (f"python /root/tmp/docs/validate_climate_disclosure_variant.py "
                       f"--output {output_path} --expected /root/tmp/docs/expected.json "
                       f"--report /root/tmp/docs/output_validation.json"),
            }
        if parent == "029":
            return {
                "01": (f"python /root/tmp/docs/build_qbr_release_variant.py "
                       f"--units /root/tmp/docs/units.json --output {output_path} && "
                       f"python /root/tmp/docs/validate_qbr_release_variant.py "
                       f"--output {output_path} --expected /root/tmp/docs/expected.json "
                       f"--report /root/tmp/docs/output_validation.json "
                       f"> /root/tmp/docs/validation_final.txt && "
                       f"python /root/.codex/skills/pptx/scripts/office/soffice.py --headless "
                       f"--convert-to pdf --outdir /root/tmp/docs {output_path} "
                       f">/root/tmp/docs/final_render.log 2>&1 && "
                       f"pdftoppm -jpeg -r 150 -f 1 -l 1 "
                       f"/root/tmp/docs/{output_name.replace('.pptx', '.pdf')} "
                       f"/root/tmp/docs/release_final_slide && cat /root/tmp/docs/validation_final.txt"),
            }
        raise ValueError(parent)
    if kind == "docx":
        if parent == "001":
            return {
                "01": (f"python /root/tmp/docs/build_controlled_document_release_variant.py "
                       f"--records /root/tmp/docs/records.json --output {output_path}"),
                "02": (f"python /root/tmp/docs/validate_controlled_document_release_variant.py "
                       f"--output {output_path} --expected /root/tmp/docs/expected.json "
                       f"--report /root/tmp/docs/output_validation.json"),
                "03": (f"render_dir=/root/tmp/docs/render_variant_v2; mkdir -p $render_dir; "
                       f"soffice -env:UserInstallation=file:///tmp/lo_packet_profile_variant_v2 "
                       f"--headless --convert-to pdf --outdir $render_dir {output_path}; "
                       f"pdfinfo $render_dir/{output_name.replace('.docx', '.pdf')} | sed -n '1,25p'; "
                       f"pdftoppm -png -r 150 $render_dir/{output_name.replace('.docx', '.pdf')} "
                       f"$render_dir/page"),
            }
        if parent == "009":
            return {
                "01": (f"python /root/tmp/docs/build_incident_manual_variant.py "
                       f"--cases /root/tmp/docs/cases.json --output {output_path}"),
                "02": (f"python /root/tmp/docs/update_toc_and_render.py "
                       f"--input {output_path} --outdir /root/tmp/docs/rendered_v2"),
                "03": (f"python /root/tmp/docs/validate_incident_manual_variant.py "
                       f"--output {output_path} --expected /root/tmp/docs/expected.json "
                       f"--report /root/tmp/docs/output_validation.json"),
            }
        if parent == "003":
            return {
                "01": (f"python /root/tmp/docs/build_public_packet_variant.py "
                       f"--input /root/{input_name} --units /root/tmp/docs/units.json "
                       f"--output {output_path}"),
                "02": (f"python /root/tmp/docs/validate_public_packet_variant.py "
                       f"--output {output_path} --expected /root/tmp/docs/expected.json "
                       f"--report /root/tmp/docs/output_validation.json"),
                "03": (f"python /root/.codex/skills/doc/scripts/render_docx.py {output_path} "
                       f"--output_dir /root/tmp/docs/rendered_v2"),
            }
        raise ValueError(parent)
    if kind == "pdf":
        if parent == "037":
            return {
                "01": (f"python /root/tmp/docs/build_bus_detour_packet_variant.py "
                       f"--notices /root/tmp/docs/notices.json --output {output_path} && "
                       f"mkdir -p /root/tmp/docs/render_v2 && "
                       f"pdftoppm -png -r 150 {output_path} /root/tmp/docs/render_v2/page"),
                "02": (f"python /root/tmp/docs/validate_bus_detour_packet_variant.py "
                       f"--output {output_path} --expected /root/tmp/docs/expected.json "
                       f"--report /root/tmp/docs/output_validation.json"),
            }
        if parent == "031":
            return {
                "01": (f"python /root/tmp/docs/build_public_packet_variant.py "
                       f"--notices /root/tmp/docs/notices.json --output {output_path}"),
                "02": (f"pdftoppm -png -r 144 {output_path} /root/tmp/docs/release_page"),
                "03": (f"python /root/tmp/docs/validate_public_packet_variant.py "
                       f"--output {output_path} --expected /root/tmp/docs/expected.json "
                       f"--report /root/tmp/docs/output_validation.json"),
            }
        if parent == "pdfwf005":
            return {
                "01": (f"python /root/tmp/docs/rebuild_closeout_binder_variant.py "
                       f"--input /root/{input_name} --groups /root/tmp/docs/groups.json "
                       f"--output {output_path} && pdfinfo {output_path}"),
                "02": (f"pdftotext -layout {output_path} -"),
                "03": (f"python3 - <<'PY'\n"
                       f"from pypdf import PdfReader\n"
                       f"p='{output_path}'\n"
                       f"r=PdfReader(p)\n"
                       f"print('pages', len(r.pages))\n"
                       f"print('page_labels', r.page_labels)\n"
                       f"print('outline entries:')\n"
                       f"for item in r.outline:\n"
                       f"    print(' ', repr(item.title), 'page_index', r.get_destination_page_number(item))\n"
                       f"print('named_destinations', list(r.named_destinations))\n"
                       f"PY"),
                "04": (f"mkdir -p /root/tmp/docs/render-output && "
                       f"pdftoppm -png -r 130 {output_path} /root/tmp/docs/render-output/page && "
                       f"montage /root/tmp/docs/render-output/page-*.png -thumbnail 30% -tile 3x2 "
                       f"-geometry +18+24 -background '#d9d9d9' -label '%f' "
                       f"/root/tmp/docs/output-contact.png && "
                       f"ls -lh /root/tmp/docs/output-contact*.png | head -30 && "
                       f"ls /root/tmp/docs/render-output/page-*.png | wc -l"),
                "05": (f"pdftotext {output_path} - | rg -n 'Draft:|Obsolete|Superseded' || true"),
            }
        raise ValueError(parent)
    raise ValueError(kind)


def recipe_files(variant: str, seed_root: Path, input_name: str, output_path: str) -> list[dict]:
    v = common.VARIANTS[variant]
    parent = v["parent"]
    config = PARENT_CONFIG[parent]
    files = []

    def add(kind_, rel, dest, source):
        data = (seed_root / rel).read_bytes()
        files.append({
            "kind": kind_, "payload": f"tasks/{variant}/seed/root/{rel}",
            "destination": dest, "source": source,
            "sha256": common.sha256_bytes(data), "bytes": len(data),
        })

    add("input", input_name, f"/root/{input_name}", "docops/scaling (synthetic)")
    if config["material"] is not None:
        add("input", f"tmp/docs/{config['material']}", f"/root/tmp/docs/{config['material']}",
            "docops/scaling (synthetic)")
    add("input", "original_task_description.txt", "/root/original_task_description.txt", "docops/scaling (synthetic)")
    add("input", "task_metadata.json", "/root/task_metadata.json", "docops/scaling (synthetic)")
    add("input", "instruction.md", "/root/instruction.md", "docops/scaling (synthetic)")
    add("input", "tmp/docs/expected.json", "/root/tmp/docs/expected.json", "docops/scaling (prepared oracle)")
    for name in config["scripts"]:
        add("script", f"tmp/docs/{name}", f"/root/tmp/docs/{name}", f"docops/scaling/cases/{parent}/scripts")
    return files


def recipe_json(variant: str, payload_root: Path, seed_root: Path, files: list[dict],
                input_name: str, output_path: str, expected_rel: str) -> dict:
    v = common.VARIANTS[variant]
    bodies = step_bodies(variant, input_name, output_path.replace("/root/submission/", ""), output_path)
    steps = []
    previous = None
    for step_id in sorted(bodies):
        body = bodies[step_id]
        argv = ["/bin/bash", "-c", body]
        entry = {
            "id": step_id,
            "name": PARENT_CONFIG[v["parent"]]["commands"][step_id],
            "phase": PARENT_CONFIG[v["parent"]]["phases"][step_id],
            "cwd": "/root",
            "argv": argv,
            "shell_body": f"tasks/{variant}/commands/{step_id}.sh",
            "shell_sha256": common.sha256_bytes(body.encode()),
            "source_command_sha256": None,
            "source_exit_code": None,
            "depends_on": [] if previous is None else [previous],
        }
        steps.append(entry)
        previous = entry["id"]

    parent_info = common.parent_material_hash(v["parent"])
    parent_recipe = common.load_json(common.docops_root() / f"payload/tasks/{v['parent']}/recipe.json")
    scale_meta = common.load_json(seed_root / "task_metadata.json")["scale_metadata"]
    expected_path = seed_root / "tmp" / "docs" / "expected.json"

    return {
        "schema": "docops-final-effective-recipe-v1",
        "task": variant,
        "task_id": f"docops_synthetic_{variant}_scale_variant",
        "format": v["format"],
        "source_run_id": None,
        "output_path": output_path,
        "files": files,
        "steps": steps,
        "review": (
            "Synthetic scale variant of frozen task "
            f"{v['parent']}; builder/validator are parameterized by actual data "
            "scale and every range/check covers all generated rows/pages."
        ),
        "excluded_items": [],
        "provenance": {
            "trace": None, "trace_sha256": None,
            "run_env": None, "run_env_sha256": None,
            "note": "synthetic scale variant; no historical Agent trace",
        },
        "synthetic_variant": {
            "synthetic": True,
            "parent_task": v["parent"],
            "parent_historical_score": parent_recipe.get("historical_score"),
            "parent_input": {
                "payload": str(common.PARENT_SOURCE[v["parent"]]["input"]),
                "sha256": parent_info[str(common.PARENT_SOURCE[v["parent"]]["input"])]["sha256"],
            },
            "parent_scripts": parent_info,
            "generator": v["generator"],
            "generator_version": v["generator_version"],
            "seed": v["seed"],
            "scale": v["scale"],
            "input_sha256": common.sha256_file(seed_root / input_name),
            "expected_sha256": common.sha256_file(expected_path),
            "config_sha256": common.sha256_file(seed_root / "task_metadata.json"),
            "scale_metadata": scale_meta,
            "modified_steps": common.load_json(seed_root / "task_metadata.json")["modified_workflow"],
        },
    }


def output_path_for(variant: str) -> str:
    v = common.VARIANTS[variant]
    return PARENT_CONFIG[v["parent"]]["output"](v["output_suffix"])


def assemble_variant(variant: str, payload_root: Path, temp: Path):
    v = common.VARIANTS[variant]
    synth_mod, expected_mod = import_case(v["parent"])
    seed = seed_root(payload_root, variant)
    seed.mkdir(parents=True, exist_ok=True)
    out = synth_mod.generate(variant, seed)
    # provenance snapshot (not a replay input) lives in the staging tree, not in the payload
    raw_snapshot = seed / "raw_records.json"
    if raw_snapshot.exists():
        STAGING.mkdir(parents=True, exist_ok=True)
        (STAGING / variant).mkdir(parents=True, exist_ok=True)
        shutil.move(str(raw_snapshot), str(STAGING / variant / "raw_records.json"))
    docs_dir = seed / "tmp" / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    config = PARENT_CONFIG[v["parent"]]
    material_name = config["material"]
    if material_name is not None:
        material = seed / material_name
        if material.exists() and not (docs_dir / material_name).exists():
            shutil.move(str(material), str(docs_dir / material_name))
    scripts_src = SCALING / "cases" / v["parent"] / "scripts"
    for name in config["scripts"]:
        shutil.copy2(scripts_src / name, docs_dir / name)
    if material_name is not None:
        expected_source = docs_dir / material_name
    else:
        expected_source = out["input"]
    expected_mod.write_expected(variant, expected_source, docs_dir / "expected.json")

    input_name = Path(out["input"]).name
    output_path = output_path_for(variant)
    output_name = Path(output_path).name

    files = recipe_files(variant, seed, input_name, output_path)
    recipe = recipe_json(variant, payload_root, seed, files, input_name, output_path, "tmp/docs/expected.json")
    (payload_root / "tasks" / variant).mkdir(parents=True, exist_ok=True)
    (payload_root / "tasks" / variant / "recipe.json").write_text(
        json.dumps(recipe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cmd_dir = commands_dir(payload_root, variant)
    cmd_dir.mkdir(parents=True, exist_ok=True)
    bodies = step_bodies(variant, input_name, output_name, output_path)
    for step_id in sorted(bodies):
        (cmd_dir / f"{step_id}.sh").write_text(bodies[step_id], encoding="utf-8")
    return recipe


def sync_variant(variant: str, payload_root: Path):
    """Refresh derived files (scripts, commands, recipe) for an existing variant.

    Inputs, regions, expected oracle and task metadata are kept byte-identical;
    only hashes/bindings derived from them are recomputed.
    """
    v = common.VARIANTS[variant]
    seed = seed_root(payload_root, variant)
    if not (payload_root / "tasks" / variant / "recipe.json").is_file():
        raise ValueError(f"{variant} has no existing recipe to sync; use build instead")
    existing = common.load_json(payload_root / "tasks" / variant / "recipe.json")
    input_rel = next(
        f["payload"] for f in existing["files"]
        if f["kind"] == "input" and Path(f["payload"]).name.endswith((".xlsx", ".pptx", ".docx", ".pdf"))
    )
    input_name = Path(input_rel).name
    input_path = seed / input_name
    if not input_path.is_file():
        raise ValueError(f"{variant} input missing: {input_path}")

    docs_dir = seed / "tmp" / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    config = PARENT_CONFIG[v["parent"]]
    scripts_src = SCALING / "cases" / v["parent"] / "scripts"
    for name in config["scripts"]:
        shutil.copy2(scripts_src / name, docs_dir / name)

    output_path = existing["output_path"]
    files = recipe_files(variant, seed, input_name, output_path)
    recipe = recipe_json(variant, payload_root, seed, files, input_name, output_path, "tmp/docs/expected.json")
    (payload_root / "tasks" / variant / "recipe.json").write_text(
        json.dumps(recipe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cmd_dir = commands_dir(payload_root, variant)
    cmd_dir.mkdir(parents=True, exist_ok=True)
    bodies = step_bodies(variant, input_name, Path(output_path).name, output_path)
    for step_id in sorted(bodies):
        (cmd_dir / f"{step_id}.sh").write_text(bodies[step_id], encoding="utf-8")
    return recipe


def copy_skills(payload_root: Path):
    for skill in ("doc", "xlsx", "pptx", "pdf"):
        src = OFFICIAL_PAYLOAD / "skills" / skill
        dst = payload_root / "skills" / skill
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)


def catalog_json(payload_root: Path, variants: list[str]) -> dict:
    official = common.load_json(OFFICIAL_PAYLOAD / "catalog.json")
    tasks = []
    for variant in variants:
        recipe = common.load_json(payload_root / "tasks" / variant / "recipe.json")
        tasks.append({
            "task": variant,
            "recipe": f"tasks/{variant}/recipe.json",
            "steps": len(recipe["steps"]),
            "scripts": sum(1 for f in recipe["files"] if f["kind"] == "script"),
            "historical_reward": None,
            "synthetic": True,
            "parent_task": recipe["synthetic_variant"]["parent_task"],
            "scale": recipe["synthetic_variant"]["scale"],
        })
    return {
        "schema": "docops-final-effective-payload-v1",
        "kind": "scaling",
        "status": "synthetic_scale_variants_static_valid",
        "scope": "synthetic_scale_input_size_variants",
        "synthetic": True,
        "declaration": (
            "Manually labelled synthetic scale variants for input-size hotspot "
            "studies. Parent scores are NOT inherited as acceptance results. "
            "Nothing here is a historical benchmark task."
        ),
        "tasks": tasks,
        "environment": dict(official.get("environment", {}),
                            base_image=official.get("environment", {}).get("base_image"),
                            note="same installed environment; synthetic payload does not change it"),
        "measurement_policy": {
            "parent_reference": official.get("measurement_policy", {}),
            "scaling": "same measurement policy as the frozen official package; "
                       "only input size / region count vary",
        },
    }


def build_index(payload_root: Path) -> dict:
    index = {}
    for p in sorted(payload_root.rglob("*")):
        if p.is_file() and p.name != "payload-index.json":
            index[str(p.relative_to(payload_root))] = {
                "bytes": p.stat().st_size, "sha256": common.sha256_file(p)}
    (payload_root / "payload-index.json").write_text(
        json.dumps({"schema": "docops-payload-index-v1", "files": index}, indent=2) + "\n", encoding="utf-8")
    return index


def validate_payload(payload_root: Path) -> dict:
    import importlib.util
    spec = importlib.util.spec_from_file_location("docops_compile", SCALING.parent / "compile.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.validate_payload(payload_root)


def manifest() -> dict:
    return {"schema": "docops-scaling-manifest-v1", "generator_version": GENERATOR_VERSION, "variants": {}}


def collect_manifest(payload_root: Path, variants: list[str], recipes: dict[str, dict]) -> dict:
    man = manifest()
    for variant in variants:
        meta = common.load_json(payload_root / "tasks" / variant / "seed" / "root" / "task_metadata.json")
        input_name = Path(meta["input_path"]).name
        input_file = payload_root / "tasks" / variant / "seed" / "root" / input_name
        man["variants"][variant] = {
            "input_bytes": input_file.stat().st_size,
            "input_sha256": common.sha256_file(input_file),
            "scale_metadata": meta["scale_metadata"],
            "output_path": meta["output_path"],
            "steps": [s["name"] for s in recipes[variant]["steps"]],
        }
    return man


def write_manifest(man: dict):
    STAGING.mkdir(parents=True, exist_ok=True)
    (STAGING / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")


def check_variants(variants: list[str]):
    for variant in variants:
        if variant not in common.VARIANTS:
            raise ValueError(f"unknown variant {variant}")
    if len(set(variants)) != len(variants):
        raise ValueError(f"duplicate variants: {variants}")


def cmd_build(args) -> int:
    payload_root = assert_safe_payload_out(args.payload_out)
    if payload_root.exists() and not args.force_replace:
        raise ValueError(
            f"refusing to overwrite existing target {payload_root}; use --force-replace to rebuild"
        )
    temp = Path(tempfile.mkdtemp(prefix="scaling-payload-", dir=SCALING))
    try:
        recipes = {}
        for variant in args.variants:
            if variant in EXISTING_SOURCE:
                source = EXISTING_SOURCE[variant]
                if not (source / "tasks" / variant).is_dir():
                    raise ValueError(f"existing variant missing: {variant} in {source}")
                shutil.copytree(source / "tasks" / variant, temp / "tasks" / variant)
                recipes[variant] = common.load_json(temp / "tasks" / variant / "recipe.json")
                print(f"copied existing {variant} byte-identical", flush=True)
            else:
                recipes[variant] = assemble_variant(variant, temp, temp)
        copy_skills(temp)
        (temp / "catalog.json").write_text(
            json.dumps(catalog_json(temp, args.variants), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        build_index(temp)
        if not args.skip_static_check:
            result = validate_payload(temp)
            print(json.dumps(result, ensure_ascii=False))
        # publish only after the staged payload is valid
        if payload_root.exists():
            shutil.rmtree(payload_root)
        payload_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(temp), str(payload_root))
        man = collect_manifest(payload_root, args.variants, recipes)
        write_manifest(man)
    finally:
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)
    print(f"Scaling payload written to {payload_root}")
    print(f"Manifest: {STAGING / 'manifest.json'}")
    return 0


def cmd_sync(args) -> int:
    payload_root = assert_safe_payload_out(args.payload_out)
    if not payload_root.is_dir() or not (payload_root / "catalog.json").is_file():
        raise ValueError(f"not an existing scaling payload to sync: {payload_root}")
    recipes = {}
    for variant in args.variants:
        recipes[variant] = sync_variant(variant, payload_root)
    (payload_root / "catalog.json").write_text(
        json.dumps(catalog_json(payload_root, args.variants), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    build_index(payload_root)
    if not args.skip_static_check:
        result = validate_payload(payload_root)
        print(json.dumps(result, ensure_ascii=False))
    man = collect_manifest(payload_root, args.variants, recipes)
    write_manifest(man)
    print(f"Synced derived files for {args.variants} at {payload_root}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    p_build = sub.add_parser("build", help="build (or rebuild) a scaling payload in a temp dir, validate, publish")
    p_build.add_argument("--payload-out", type=Path, default=PAYLOAD)
    p_build.add_argument("--variants", nargs="*", default=list(common.VARIANT_ORDER))
    p_build.add_argument("--force-replace", action="store_true",
                         help="explicitly replace an existing target after staged validation")
    p_build.add_argument("--skip-static-check", action="store_true")
    p_sync = sub.add_parser("sync", help="refresh derived scripts/commands/recipe/index only (inputs unchanged)")
    p_sync.add_argument("--payload-out", type=Path, default=PAYLOAD)
    p_sync.add_argument("--variants", nargs="*", default=list(common.VARIANT_ORDER))
    p_sync.add_argument("--skip-static-check", action="store_true")
    args = parser.parse_args(argv)
    check_variants(args.variants)
    if args.action == "build":
        return cmd_build(args)
    return cmd_sync(args)


if __name__ == "__main__":
    sys.exit(main())
