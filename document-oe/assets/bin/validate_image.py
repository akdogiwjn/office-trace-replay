#!/usr/bin/env python3
"""Validate the self-contained PDF/XLSX benchmark assets inside the image.

This script only checks immutable runtime inputs and dependencies.  It does not
execute a scene and does not replace the host-side e2b_bench scheduler.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import shutil
import sys
from pathlib import Path


DEFAULT_ROOT = Path("/opt/document-bench")
REQUIRED_ASSETS = (
    "xlsx/input/monthly_operations_template.xlsx",
    "xlsx/input/verify_xlsx_enhanced.py",
    "pdf/input/of306_aug2023.pdf",
    "pdf/input/synthetic_applicants.json",
    "pdf/input/verify_pdf_batch.py",
    "operations/xlsx_key_operations.json",
    "operations/pdf_key_operations.json",
    "bin/run_xlsx_helper_atomic.py",
    "bin/export_xlsx_csv.py",
    "bin/write_xlsx_summary.py",
    "bin/smoke_document_scenes.py",
    "bin/smoke_xlsx_recalc.py",
    "bin/run_document_scene_loop.py",
    "bin/run_pdf_scene.sh",
    "bin/run_xlsx_scene.sh",
    "skills/xlsx/SKILL.md",
    "skills/xlsx/scripts/recalc.py",
    "skills/pdf/SKILL.md",
    "skills/pdf/scripts/check_fillable_fields.py",
    "skills/pdf/scripts/extract_form_field_info.py",
    "skills/pdf/scripts/fill_fillable_fields.py",
    "skills/pdf/scripts/convert_pdf_to_images.py",
    "wheels/et_xmlfile-2.0.0-py3-none-any.whl",
    "wheels/openpyxl-3.1.5-py2.py3-none-any.whl",
    "wheels/pdf2image-1.17.0-py3-none-any.whl",
    "wheels/pillow-12.2.0-cp312-cp312-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl",
    "wheels/pypdf-6.10.0-py3-none-any.whl",
    "requirements.txt",
)
REQUIRED_COMMANDS = ("python3", "soffice", "pdftoppm", "gcc", "sshd", "websocat")
FORBIDDEN_COMMANDS = ("node", "npm", "openclaw", "llama-server", "supervisord")
ASSET_DIRECTORIES = ("xlsx", "pdf", "operations", "skills", "wheels", "bin")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_requirements(path: Path) -> dict[str, str]:
    requirements: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise ValueError(f"only pinned offline requirements are supported: {line}")
        name, version = line.split("==", 1)
        requirements[name.strip()] = version.strip()
    return requirements


def validate_recipe(path: Path, expected_kind: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "scene-key-operations-v2":
        raise ValueError(f"unsupported recipe schema: {path}")
    if data.get("case_kind") != expected_kind:
        raise ValueError(f"recipe kind mismatch: {path}")
    operations = data.get("key_operations") or []
    if data.get("operation_count") != len(operations):
        raise ValueError(f"operation_count mismatch: {path}")
    operation_ids = {operation.get("operation_id") for operation in operations}
    workflow = data.get("workflow", {})
    missing = set(workflow.get("success_path") or []) - operation_ids
    if missing:
        raise ValueError(f"recipe references unknown operations {sorted(missing)}: {path}")
    conditional_steps = workflow.get("conditional_path", {}).get("steps", [])
    missing = set(conditional_steps) - operation_ids
    if missing:
        raise ValueError(f"recipe conditional path references unknown operations {sorted(missing)}: {path}")


def manifest_asset_paths(root: Path) -> list[str]:
    """Return every immutable dataset, helper, recipe, and offline package."""
    paths = set(REQUIRED_ASSETS)
    paths.add("requirements.txt")
    for directory in ASSET_DIRECTORIES:
        base = root / directory
        if base.is_dir():
            paths.update(
                str(path.relative_to(root))
                for path in base.rglob("*")
                if path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix not in {".pyc", ".pyo"}
            )
    return sorted(paths)


def collect_manifest(root: Path, check_dependencies: bool) -> dict[str, object]:
    missing = [relative for relative in REQUIRED_ASSETS if not (root / relative).is_file()]
    if missing:
        raise FileNotFoundError(f"missing document benchmark assets: {missing}")

    validate_recipe(root / "operations/xlsx_key_operations.json", "xlsx")
    validate_recipe(root / "operations/pdf_key_operations.json", "pdf")

    requirements = read_requirements(root / "requirements.txt")
    installed: dict[str, str] = {}
    commands: dict[str, str] = {}
    forbidden_commands_absent: dict[str, bool] = {}
    if check_dependencies:
        for name, expected in requirements.items():
            actual = importlib.metadata.version(name)
            if actual != expected:
                raise RuntimeError(f"{name} version mismatch: expected {expected}, found {actual}")
            installed[name] = actual
        for command in REQUIRED_COMMANDS:
            resolved = shutil.which(command)
            if not resolved:
                raise RuntimeError(f"required command is unavailable: {command}")
            commands[command] = resolved
        for command in FORBIDDEN_COMMANDS:
            resolved = shutil.which(command)
            if resolved:
                raise RuntimeError(f"forbidden command is present: {command} ({resolved})")
            forbidden_commands_absent[command] = True

    return {
        "schema_version": "document-bench-image-v1",
        "asset_root": str(root),
        "scenes": ["xlsx", "pdf"],
        "assets": {relative: sha256(root / relative) for relative in manifest_asset_paths(root)},
        "python_requirements": requirements,
        "installed_python_packages": installed,
        "commands": commands,
        "forbidden_commands_absent": forbidden_commands_absent,
    }


def verify_saved_manifest(root: Path, current: dict[str, object]) -> None:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return
    saved = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key in (
        "schema_version",
        "scenes",
        "assets",
        "python_requirements",
        "forbidden_commands_absent",
    ):
        if saved.get(key) != current.get(key):
            raise RuntimeError(f"saved image manifest does not match current {key}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--asset-only", action="store_true", help="skip installed package and command checks")
    parser.add_argument("--write-manifest", type=Path, help="write the validated manifest to this path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = collect_manifest(args.root, check_dependencies=not args.asset_only)
        if args.write_manifest:
            args.write_manifest.parent.mkdir(parents=True, exist_ok=True)
            args.write_manifest.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        else:
            verify_saved_manifest(args.root, manifest)
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"document image validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
