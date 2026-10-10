#!/usr/bin/env python3
"""Run the archived PDF/XLSX recipes locally inside the document image."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path("/opt/document-bench")
SCENES = {
    "xlsx": {
        "seed": ROOT / "xlsx",
        "workspace": Path("/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01"),
        "recipe": ROOT / "operations/xlsx_key_operations.json",
    },
    "pdf": {
        "seed": ROOT / "pdf",
        "workspace": Path("/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01"),
        "recipe": ROOT / "operations/pdf_key_operations.json",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", choices=("xlsx", "pdf", "all"), default="all")
    parser.add_argument("--timeout", type=int, default=600, help="timeout for every exec call")
    parser.add_argument("--recalc-timeout", type=int, default=600, help="LibreOffice recalculation timeout")
    parser.add_argument(
        "--overall-timeout",
        type=int,
        default=2100,
        help="deadline for all selected scenes combined",
    )
    return parser.parse_args()


def load_recipe(path: Path, kind: str) -> dict[str, Any]:
    recipe = json.loads(path.read_text(encoding="utf-8"))
    if recipe.get("schema_version") != "scene-key-operations-v2" or recipe.get("case_kind") != kind:
        raise ValueError(f"invalid archived {kind} recipe: {path}")
    operations = recipe.get("key_operations") or []
    by_id = {item["operation_id"]: item for item in operations}
    success_path = recipe.get("workflow", {}).get("success_path") or []
    if not success_path or any(operation_id not in by_id for operation_id in success_path):
        raise ValueError(f"invalid success path in {path}")
    return recipe


def remaining_exec_timeout(timeout: int, deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("document scene smoke exceeded its overall timeout")
    return min(float(timeout), remaining)


def execute_call(call: dict[str, Any], timeout: int, recalc_timeout: int, deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise TimeoutError("document scene smoke exceeded its overall timeout")
    function = call["function_name"]
    arguments = call["arguments"]
    if function == "read":
        path = Path(arguments["path"])
        if not path.is_file():
            raise FileNotFoundError(path)
        with path.open("rb") as handle:
            handle.read(65536)
    elif function == "write":
        path = Path(arguments["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(arguments["content"], encoding="utf-8")
    elif function == "exec":
        command = arguments["command"].replace("__DOCUMENT_RECALC_TIMEOUT__", str(recalc_timeout))
        subprocess.run(
            command,
            shell=True,
            executable="/bin/bash",
            check=True,
            timeout=remaining_exec_timeout(timeout, deadline),
        )
    else:
        raise ValueError(f"unsupported archived tool call: {function}")


def run_scene(kind: str, timeout: int, recalc_timeout: int, deadline: float) -> None:
    layout = SCENES[kind]
    workspace: Path = layout["workspace"]
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(layout["seed"], workspace)
    (workspace / "output").mkdir(exist_ok=True)

    recipe = load_recipe(layout["recipe"], kind)
    operations = {item["operation_id"]: item for item in recipe["key_operations"]}
    started = time.perf_counter()
    for operation_id in recipe["workflow"]["success_path"]:
        operation_started = time.perf_counter()
        for source_call in operations[operation_id]["source_tool_calls"]:
            execute_call(source_call["tool_call"], timeout, recalc_timeout, deadline)
        print(f"[{kind}] {operation_id}: {time.perf_counter() - operation_started:.2f}s")

    verification = json.loads(
        (workspace / "output/business_verification.json").read_text(encoding="utf-8")
    )
    if verification.get("status") != "success" or verification.get("failures"):
        raise RuntimeError(f"{kind} business verification failed: {verification}")
    print(f"[{kind}] success in {time.perf_counter() - started:.2f}s")


def main() -> int:
    args = parse_args()
    if args.timeout <= 0:
        raise ValueError("--timeout must be positive")
    if args.recalc_timeout <= 0 or args.recalc_timeout >= args.timeout:
        raise ValueError("--recalc-timeout must be positive and lower than --timeout")
    if args.overall_timeout <= args.recalc_timeout:
        raise ValueError("--overall-timeout must be greater than --recalc-timeout")
    deadline = time.monotonic() + args.overall_timeout
    scenes = ("xlsx", "pdf") if args.scene == "all" else (args.scene,)
    for scene in scenes:
        run_scene(scene, args.timeout, args.recalc_timeout, deadline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
