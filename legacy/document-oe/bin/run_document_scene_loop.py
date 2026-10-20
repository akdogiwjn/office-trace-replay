#!/usr/bin/env python3
"""Run the current four-step PDF or XLSX scene repeatedly in one container.

Unified entry for every dataset: `--scene` + `--dataset` select the workload
through the registry; `--scene pdf`/`--scene xlsx` default to the byte-preserved
`opm`/`tlc` workloads. Before the first iteration the runner validates the
selected frozen workload and prepares the source context / Skill links / Python
runtime environment itself, so direct invocation and the entry/suite path share
the same resolution and preparation rules. The original loop, workspace reset,
timeout, error handling, exit status and timing semantics are preserved.
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


LOOP_COUNT = 20_000
# Change only this default to 10 for the original ten-applicant PDF mode.
PDF_APPLICANT_COUNT = 1
ROOT = Path("/opt/document-bench")
REPO = Path("/opt/office-trace-replay")
DEFAULT_RESULTS_ROOT = ROOT / "results"
PDF_STEPS = [
    "PDF-P01-inspect_prepare",
    "PDF-P02-build",
    "PDF-P03-process_publish",
    "PDF-P04-verify_deliver",
]
XLSX_STEPS = [
    "XLSX-P01-inspect_prepare",
    "XLSX-P02-build",
    "XLSX-P03-process_publish",
    "XLSX-P04-verify_deliver",
]
SCENES = {
    "pdf": {
        "seed": ROOT / "pdf",
        "workspace": Path("/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01"),
        "recipe": ROOT / "operations/pdf_key_operations.json",
        "operation_timeout": 300,
        "recalc_timeout": 180,
        "step_order": PDF_STEPS,
    },
    "xlsx": {
        "seed": ROOT / "xlsx",
        "workspace": Path("/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01"),
        "recipe": ROOT / "operations/xlsx_key_operations.json",
        "operation_timeout": 900,
        "recalc_timeout": 600,
        "step_order": XLSX_STEPS,
    },
}

# Unified dataset registry. Each entry mirrors the layout keys the executor
# consumes (seed, workspace, recipe, operation_timeout, recalc_timeout,
# step_order) plus the source context used for environment preparation and
# post-loop acceptance. `opm`/`tlc` are the byte-preserved old workloads and
# keep their original defaults. PDF datasets carry per-applicant-count
# variants; record_count selects the matching recipe/seed.
DATASETS = {
    "pdf": {
        "opm": {
            "seed": ROOT / "pdf",
            "workspace": Path("/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01"),
            "recipe": ROOT / "operations/pdf_key_operations.json",
            "source": None,
            "operation_timeout": 300,
            "recalc_timeout": 180,
            "step_order": PDF_STEPS,
            "record_count": None,
        },
        "irs_w4": {
            "variants": {
                1: {
                    "seed": REPO / "compatibility/cases/irs_w4-n1/seed",
                    "workspace": Path("/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-IRSW4-01"),
                    "recipe": REPO / "compatibility/recipes/irs_w4-n1.json",
                    "source": REPO / "compatibility/cases/irs_w4-n1/source",
                    "operation_timeout": 300,
                    "recalc_timeout": 180,
                    "step_order": PDF_STEPS,
                    "record_count": 1,
                },
                10: {
                    "seed": REPO / "compatibility/cases/irs_w4-n10/seed",
                    "workspace": Path("/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-IRSW4-01"),
                    "recipe": REPO / "compatibility/recipes/irs_w4-n10.json",
                    "source": REPO / "compatibility/cases/irs_w4-n10/source",
                    "operation_timeout": 300,
                    "recalc_timeout": 180,
                    "step_order": PDF_STEPS,
                    "record_count": 10,
                },
            },
        },
        "sba1919": {
            "variants": {
                1: {
                    "seed": REPO / "compatibility/cases/sba1919-n1/seed",
                    "workspace": Path("/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-SBA1919-01"),
                    "recipe": REPO / "compatibility/recipes/sba1919-n1.json",
                    "source": REPO / "compatibility/cases/sba1919-n1/source",
                    "operation_timeout": 300,
                    "recalc_timeout": 180,
                    "step_order": PDF_STEPS,
                    "record_count": 1,
                },
                10: {
                    "seed": REPO / "compatibility/cases/sba1919-n10/seed",
                    "workspace": Path("/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-SBA1919-01"),
                    "recipe": REPO / "compatibility/recipes/sba1919-n10.json",
                    "source": REPO / "compatibility/cases/sba1919-n10/source",
                    "operation_timeout": 300,
                    "recalc_timeout": 180,
                    "step_order": PDF_STEPS,
                    "record_count": 10,
                },
            },
        },
    },
    "xlsx": {
        "tlc": {
            "seed": ROOT / "xlsx",
            "workspace": Path("/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01"),
            "recipe": ROOT / "operations/xlsx_key_operations.json",
            "source": None,
            "operation_timeout": 900,
            "recalc_timeout": 600,
            "step_order": XLSX_STEPS,
            "record_count": None,
        },
        "retail": {
            "seed": REPO / "compatibility/cases/retail/seed",
            "workspace": Path("/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-RETAIL"),
            "recipe": REPO / "compatibility/recipes/retail.json",
            "source": REPO / "compatibility/cases/retail/source",
            "operation_timeout": 900,
            "recalc_timeout": 600,
            "step_order": XLSX_STEPS,
            "record_count": None,
        },
        "retail_online": {
            "seed": REPO / "compatibility/cases/retail_online/seed",
            "workspace": Path("/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-RETAIL-ONLINE"),
            "recipe": REPO / "compatibility/recipes/retail_online.json",
            "source": REPO / "compatibility/cases/retail_online/source",
            "operation_timeout": 900,
            "recalc_timeout": 600,
            "step_order": XLSX_STEPS,
            "record_count": None,
        },
        "manufacturing": {
            "seed": REPO / "compatibility/cases/manufacturing/seed",
            "workspace": Path("/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-MANUFACTURING"),
            "recipe": REPO / "compatibility/recipes/manufacturing.json",
            "source": REPO / "compatibility/cases/manufacturing/source",
            "operation_timeout": 900,
            "recalc_timeout": 600,
            "step_order": XLSX_STEPS,
            "record_count": None,
        },
        "hr": {
            "seed": REPO / "compatibility/cases/hr/seed",
            "workspace": Path("/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-HR"),
            "recipe": REPO / "compatibility/recipes/hr.json",
            "source": REPO / "compatibility/cases/hr/source",
            "operation_timeout": 900,
            "recalc_timeout": 600,
            "step_order": XLSX_STEPS,
            "record_count": None,
        },
        "hr_metro": {
            "seed": REPO / "compatibility/cases/hr_metro/seed",
            "workspace": Path("/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-HR-METRO"),
            "recipe": REPO / "compatibility/recipes/hr_metro.json",
            "source": REPO / "compatibility/cases/hr_metro/source",
            "operation_timeout": 900,
            "recalc_timeout": 600,
            "step_order": XLSX_STEPS,
            "record_count": None,
        },
        "industry_productivity": {
            "seed": REPO / "compatibility/cases/industry_productivity/seed",
            "workspace": Path("/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-INDUSTRY-PRODUCTIVITY"),
            "recipe": REPO / "compatibility/recipes/industry_productivity.json",
            "source": REPO / "compatibility/cases/industry_productivity/source",
            "operation_timeout": 900,
            "recalc_timeout": 180,
            "step_order": XLSX_STEPS,
            "record_count": None,
        },
    },
}

SCENE_DEFAULT_DATASET = {"pdf": "opm", "xlsx": "tlc"}
DATASET_SCENE = {
    name: scene for scene, datasets in DATASETS.items() for name in datasets
}
ALL_DATASETS = sorted(DATASET_SCENE)


def dataset_layout(scene: str, dataset: str, record_count: int = PDF_APPLICANT_COUNT) -> dict[str, Any]:
    """Resolve a scene+dataset combination to its executor layout."""
    if scene not in DATASETS:
        raise ValueError(f"unsupported scene: {scene}")
    if dataset not in DATASETS[scene]:
        raise ValueError(f"dataset '{dataset}' is not valid for scene '{scene}'")
    entry = DATASETS[scene][dataset]
    if "variants" in entry:
        if record_count not in entry["variants"]:
            raise ValueError(
                f"dataset '{dataset}' does not support applicant count {record_count}"
            )
        entry = entry["variants"][record_count]
    return entry


@dataclass
class StepFailure(RuntimeError):
    step_id: str
    call_index: int
    function_name: str
    message: str
    elapsed_seconds: float
    tool_call_id: str = ""

    def __str__(self) -> str:
        call = f"call {self.call_index}"
        if self.tool_call_id:
            call += f" ({self.tool_call_id})"
        return f"{self.step_id} {call} {self.function_name} failed: {self.message}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "call_index": self.call_index,
            "tool_call_id": self.tool_call_id,
            "function_name": self.function_name,
            "error": self.message,
            "elapsed_seconds": round(self.elapsed_seconds, 6),
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", required=True, choices=tuple(SCENES))
    parser.add_argument(
        "--dataset",
        choices=ALL_DATASETS,
        default=None,
        help="dataset within the scene; defaults to the scene's original workload "
        "(pdf -> opm, xlsx -> tlc)",
    )
    parser.add_argument(
        "--pdf-applicant-count",
        type=int,
        choices=(1, 10),
        default=PDF_APPLICANT_COUNT,
        help="PDF P03 applicant count; ignored by the XLSX scene",
    )
    parser.add_argument("--loops", type=int, default=LOOP_COUNT)
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path(os.environ.get("DOCUMENT_BENCH_RESULTS_DIR", DEFAULT_RESULTS_ROOT)),
    )
    parser.add_argument("--operation-timeout", type=int)
    parser.add_argument("--recalc-timeout", type=int)
    parser.add_argument("--legacy-python", choices=("system", "venv"), default="venv",
                        help="runtime mode: original venv 3.12.3 (default) or system 3.11.6")
    parser.add_argument("--timed", action="store_true",
                        help="apply the original per-call/nested timing hooks")
    parser.add_argument("--validate-recipe", action="store_true")
    return parser.parse_args()


def load_recipe(path: Path, kind: str, expected_steps: list[str]) -> dict[str, Any]:
    recipe = json.loads(path.read_text(encoding="utf-8"))
    if recipe.get("schema_version") != "scene-key-operations-v2":
        raise ValueError(f"unsupported recipe schema: {path}")
    if recipe.get("case_kind") != kind:
        raise ValueError(f"recipe case_kind mismatch: {path}")

    # The stored schema keeps this legacy field name, but every entry now
    # represents one complete benchmark step.
    steps = recipe.get("key_operations")
    if not isinstance(steps, list) or not steps:
        raise ValueError(f"recipe has no steps: {path}")
    if recipe.get("operation_count") != len(steps):
        raise ValueError(f"recipe step count metadata mismatch: {path}")
    step_ids = [step.get("operation_id") for step in steps]
    if step_ids != expected_steps:
        raise ValueError(f"expected step order {expected_steps}, got {step_ids}")

    for step in steps:
        calls = step.get("source_tool_calls")
        if not isinstance(calls, list) or not calls:
            raise ValueError(f"step {step.get('operation_id')} has no calls")
        for item in calls:
            call = item.get("tool_call", {})
            if call.get("function_name") not in {"read", "write", "exec"}:
                raise ValueError(f"step {step.get('operation_id')} has an invalid call")
            if not isinstance(call.get("arguments"), dict):
                raise ValueError(f"step {step.get('operation_id')} has invalid arguments")

    workflow = recipe.get("workflow", {})
    if workflow.get("success_path") != expected_steps:
        raise ValueError("recipe success_path is not the canonical four-step path")
    if "conditional_path" in workflow:
        raise ValueError("step recipe must not contain the old conditional repair path")
    return recipe


def reset_workspace(seed: Path, workspace: Path) -> float:
    started = time.perf_counter()
    if not (seed / "input").is_dir():
        raise FileNotFoundError(f"scene seed is incomplete: {seed}")
    if workspace.exists() or workspace.is_symlink():
        if workspace.is_symlink() or workspace.is_file():
            workspace.unlink()
        else:
            shutil.rmtree(workspace)
    workspace.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(seed, workspace)
    (workspace / "output").mkdir(exist_ok=True)
    return time.perf_counter() - started


def output_excerpt(stdout: str, stderr: str, limit: int = 1000) -> str:
    return (stderr.strip() or stdout.strip() or "no command output")[-limit:]


def terminate_process_group(process: subprocess.Popen[str]) -> tuple[str, str]:
    if process.poll() is not None:
        return process.communicate()
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return process.communicate()
    try:
        return process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return process.communicate()


def run_command(command: str, timeout: int) -> None:
    process = subprocess.Popen(
        command,
        shell=True,
        executable="/bin/bash",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        stdout, stderr = terminate_process_group(process)
        raise TimeoutError(f"timed out after {timeout}s: {output_excerpt(stdout, stderr)}")
    except BaseException:
        terminate_process_group(process)
        raise
    if process.returncode != 0:
        raise RuntimeError(f"exit_code={process.returncode}: {output_excerpt(stdout, stderr)}")


def execute_call(call: dict[str, Any], operation_timeout: int, recalc_timeout: int) -> None:
    function = call["function_name"]
    arguments = call["arguments"]
    if function == "read":
        path = Path(arguments["path"])
        if not path.is_file():
            raise FileNotFoundError(path)
        with path.open("rb") as handle:
            handle.read(65_536)
    elif function == "write":
        path = Path(arguments["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(arguments["content"], encoding="utf-8")
    elif function == "exec":
        command = arguments["command"].replace(
            "__DOCUMENT_RECALC_TIMEOUT__", str(recalc_timeout)
        )
        run_command(command, operation_timeout)
    else:
        raise ValueError(f"unsupported archived tool call: {function}")


def execute_step(
    step: dict[str, Any],
    operation_timeout: int,
    recalc_timeout: int,
    step_times: dict[str, float],
) -> None:
    step_id = step["operation_id"]
    started = time.perf_counter()
    try:
        for call_index, source_call in enumerate(step["source_tool_calls"], start=1):
            call = source_call["tool_call"]
            call_started = time.perf_counter()
            try:
                execute_call(call, operation_timeout, recalc_timeout)
            except Exception as exc:
                raise StepFailure(
                    step_id=step_id,
                    call_index=call_index,
                    tool_call_id=str(source_call.get("tool_call_id", "")),
                    function_name=str(call.get("function_name", "unknown")),
                    message=f"{type(exc).__name__}: {exc}",
                    elapsed_seconds=time.perf_counter() - call_started,
                ) from exc
    finally:
        step_times[step_id] = round(
            step_times.get(step_id, 0.0) + time.perf_counter() - started, 6
        )


def validate_business_result(workspace: Path) -> None:
    report = json.loads(
        (workspace / "output/business_verification.json").read_text(encoding="utf-8")
    )
    if report.get("status") != "success" or report.get("failures"):
        raise RuntimeError(f"business verification failed: {report}")


def run_iteration(
    layout: dict[str, Any],
    recipe: dict[str, Any],
    operation_timeout: int,
    recalc_timeout: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    step_times: dict[str, float] = {}
    failed_step = "workspace_reset"
    reset_seconds = 0.0
    steps = {item["operation_id"]: item for item in recipe["key_operations"]}
    try:
        reset_seconds = reset_workspace(layout["seed"], layout["workspace"])
        for step_id in recipe["workflow"]["success_path"]:
            failed_step = step_id
            execute_step(steps[step_id], operation_timeout, recalc_timeout, step_times)
        failed_step = "business_verification"
        validate_business_result(layout["workspace"])
        return {
            "status": "success",
            "failed_step": "",
            "reset_seconds": round(reset_seconds, 6),
            "step_seconds": step_times,
            "elapsed_seconds": round(time.perf_counter() - started, 6),
        }
    except StepFailure as exc:
        return {
            "status": "failed",
            "failed_step": exc.step_id,
            "failed_call": exc.as_dict(),
            "error_type": type(exc.__cause__).__name__ if exc.__cause__ else type(exc).__name__,
            "error": str(exc),
            "reset_seconds": round(reset_seconds, 6),
            "step_seconds": step_times,
            "elapsed_seconds": round(time.perf_counter() - started, 6),
        }
    except Exception as exc:
        return {
            "status": "failed",
            "failed_step": failed_step,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "reset_seconds": round(reset_seconds, 6),
            "step_seconds": step_times,
            "elapsed_seconds": round(time.perf_counter() - started, 6),
        }


def write_json(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def stop_requested(_signum: int, _frame: Any) -> None:
    raise KeyboardInterrupt


# ---------------------------------------------------------------------------
# Self-contained environment preparation, frozen-binding validation and timing.
# The runner owns these so direct invocation and the entry/suite path use the
# same rules; nothing here runs inside the measured loop.
# ---------------------------------------------------------------------------

def _ensure_skills() -> None:
    skills = Path("/root/.openclaw/skills")
    skills.mkdir(parents=True, exist_ok=True)
    for kind in ("pdf", "xlsx"):
        link = skills / kind
        target = ROOT / "skills" / kind
        if link.is_symlink() and link.resolve() == target.resolve():
            continue
        if link.exists() or link.is_symlink():
            raise ValueError("Skill context changed; use a fresh container")
        link.symlink_to(target)


def prepare_environment(layout: dict[str, Any], python_mode: str) -> None:
    """Configure os.environ so every recipe subprocess gets the right context.

    Sets PATH / VIRTUAL_ENV for the requested Python mode, clears any stale
    PYTHONPATH / OFFICE_TRACE_PROJECT, creates the Skill links, and for
    canonicalized datasets exposes the source context through OFFICE_TRACE_PROJECT
    and the /workspace alias.
    """
    env = os.environ
    env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    env.pop("VIRTUAL_ENV", None)
    if python_mode == "venv":
        env["PATH"] = "/opt/document-bench/.venv/bin:" + env["PATH"]
        env["VIRTUAL_ENV"] = "/opt/document-bench/.venv"
    env.pop("PYTHONPATH", None)
    env.pop("OFFICE_TRACE_PROJECT", None)
    _ensure_skills()
    if layout.get("source") is not None:
        source = Path(layout["source"])
        alias = Path("/workspace")
        if alias.is_symlink():
            alias.unlink()
        elif alias.exists():
            if alias.is_dir() and not any(alias.iterdir()):
                alias.rmdir()
            else:
                raise ValueError("/workspace must be empty or a replay-owned symlink")
        alias.symlink_to(source)
        env["OFFICE_TRACE_PROJECT"] = str(source)


def validate_selected(scene: str, dataset: str, layout: dict[str, Any],
                      record_count: Optional[int]) -> None:
    """Validate the selected frozen workload before any iteration starts.

    Covers the executor/workload split, the full project freeze, and the
    dataset's recipe / helper / input / source-verifier / parent-trace /
    contract bindings. Raised mismatches reject the run before execution.
    """
    sys.path.insert(0, str(REPO))
    from replay import freeze
    freeze.validate_dataset(scene, dataset, layout, record_count,
                            check_installed=Path("/.dockerenv").exists())


def ensure_interpreter(python_mode: str) -> None:
    """Re-exec the runner under the requested interpreter when the current one
    does not match, so the runner and the recipe tools use one consistent
    Python environment.

    This happens before validation, environment preparation and the loop; argv,
    exit codes and signal behavior are preserved through os.execv. An explicit
    `DOCUMENT_BENCH_REEXEC_READY` guard prevents infinite restarts, and a
    missing or wrong-version interpreter is rejected instead of silently
    falling back.
    """
    requested = "/usr/bin/python3" if python_mode == "system" else "/opt/document-bench/.venv/bin/python"
    if os.path.realpath(sys.executable) == os.path.realpath(requested):
        return
    if os.environ.get("DOCUMENT_BENCH_REEXEC_READY"):
        raise RuntimeError(
            f"interpreter mismatch after re-exec: {sys.executable} != {requested}")
    if not os.path.isfile(requested):
        raise FileNotFoundError(f"requested interpreter does not exist: {requested}")
    expected_prefix = "3.11" if python_mode == "system" else "3.12"
    try:
        out = subprocess.run([requested, "-c", "import sys; print(sys.version.split()[0])"],
                             capture_output=True, text=True, timeout=30)
        version = (out.stdout or "").strip()
    except Exception as exc:
        raise RuntimeError(f"cannot probe requested interpreter {requested}: {exc}")
    if not version.startswith(expected_prefix):
        raise RuntimeError(
            f"requested interpreter {requested} is Python {version}, expected {expected_prefix}.*")
    os.environ["DOCUMENT_BENCH_REEXEC_READY"] = "1"
    os.execv(requested, [requested] + list(sys.argv))


def probe_environment() -> dict[str, Any]:
    """Actual interpreter and key library versions, outside the measured loop."""
    info: dict[str, Any] = {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "python3_executable": shutil.which("python3"),
        "python3_version": None,
        "python3_openpyxl": None,
        "packages": {},
        "libreoffice": None,
    }
    try:
        out = subprocess.run(
            ["python3", "-c", "import sys,importlib.metadata;"
                              "print(sys.version.split()[0]);"
                              "print(importlib.metadata.version('openpyxl'))"],
            capture_output=True, text=True, timeout=30)
        lines = [line for line in (out.stdout or "").strip().splitlines() if line]
        if lines:
            info["python3_version"] = lines[0]
        if len(lines) > 1:
            info["python3_openpyxl"] = lines[1]
    except Exception:
        pass
    for name in ("openpyxl", "et_xmlfile", "pypdf", "pdf2image", "pillow"):
        try:
            info["packages"][name] = importlib.metadata.version(name)
        except Exception:
            pass
    try:
        out = subprocess.run(["soffice", "--version"], capture_output=True,
                             text=True, timeout=10)
        info["libreoffice"] = (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception:
        pass
    return info


# --- timing hooks (the original per-call/nested logging moved into the runner) ---

_TIMING_HOOKS_DIR = Path(__file__).resolve().parent / "timing_hooks"
_plain_execute_step = execute_step
_plain_run_iteration = run_iteration
_plain_write_json = write_json
_plain_run_command = run_command

_current_calls: list[dict[str, Any]] = []
_pending: Optional[dict[str, Any]] = None
_calls_handle: Any = None
_nested_log_path: Optional[Path] = None
_nested_offset: int = 0
_scene: str = "run"
_iterations_done: int = 0
_net_total: float = 0.0


def call_label(call: dict[str, Any]) -> str:
    function = str(call.get("function_name", "unknown"))
    if function != "exec":
        return function
    command = " ".join(str(call["arguments"]["command"]).split())
    match = re.search(r"([\w.-]+\.py)\b", command)
    if match:
        return "exec:" + match.group(1)
    return "exec:" + (command[:60] + ("..." if len(command) > 60 else ""))


def timed_execute_step(step, operation_timeout, recalc_timeout, step_times):
    step_id = step["operation_id"]
    started = time.perf_counter()
    try:
        for call_index, source_call in enumerate(step["source_tool_calls"], start=1):
            call = source_call["tool_call"]
            call_started = time.perf_counter()
            try:
                execute_call(call, operation_timeout, recalc_timeout)
            except Exception as exc:
                raise StepFailure(
                    step_id=step_id,
                    call_index=call_index,
                    tool_call_id=str(source_call.get("tool_call_id", "")),
                    function_name=str(call.get("function_name", "unknown")),
                    message=f"{type(exc).__name__}: {exc}",
                    elapsed_seconds=time.perf_counter() - call_started,
                ) from exc
            finally:
                _current_calls.append({
                    "step_id": step_id,
                    "call_index": call_index,
                    "label": call_label(call),
                    "seconds": round(time.perf_counter() - call_started, 6),
                })
    finally:
        step_times[step_id] = round(
            step_times.get(step_id, 0.0) + time.perf_counter() - started, 6
        )


def timed_run_command(command: str, timeout: int) -> None:
    saved_path = os.environ.get("PYTHONPATH")
    saved_log = os.environ.get("DOCUMENT_BENCH_TIMING_LOG")
    os.environ["PYTHONPATH"] = (
        str(_TIMING_HOOKS_DIR) + (os.pathsep + saved_path if saved_path else "")
    )
    if _nested_log_path is not None:
        os.environ["DOCUMENT_BENCH_TIMING_LOG"] = str(_nested_log_path)
    try:
        _plain_run_command(command, timeout)
    finally:
        if saved_path is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = saved_path
        if saved_log is None:
            os.environ.pop("DOCUMENT_BENCH_TIMING_LOG", None)
        else:
            os.environ["DOCUMENT_BENCH_TIMING_LOG"] = saved_log


def _read_new_nested() -> list[dict[str, Any]]:
    global _nested_offset
    if _nested_log_path is None or not _nested_log_path.is_file():
        return []
    records: list[dict[str, Any]] = []
    with _nested_log_path.open("r", encoding="utf-8") as handle:
        handle.seek(_nested_offset)
        for line in handle:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        _nested_offset = handle.tell()
    return records


def _print_iteration_timings(record: dict[str, Any], nested: list[dict[str, Any]]) -> None:
    net = record["elapsed_seconds"] - record["reset_seconds"]
    print(f"[{_scene}] iteration {_iterations_done + 1} per-script timings:", flush=True)
    for c in sorted(_current_calls, key=lambda c: -c["seconds"]):
        print(
            "  %-28s %4s %-58s %9.4fs"
            % (c["step_id"], "#" + str(c["call_index"]), c["label"], c["seconds"]),
            flush=True,
        )
    if nested:
        print("  nested (invoked inside the parent script):", flush=True)
        for n in sorted(nested, key=lambda n: -n["seconds"]):
            print(
                "    %-42s -> %-46s %9.4fs"
                % (n["parent"], n["child"], n["seconds"]),
                flush=True,
            )
    print(
        "  iteration total: %.4fs | excl. workspace reset: %.4fs | reset: %.4fs"
        % (record["elapsed_seconds"], net, record["reset_seconds"]),
        flush=True,
    )


def timed_run_iteration(layout, recipe, operation_timeout, recalc_timeout):
    global _nested_offset, _iterations_done, _net_total
    _current_calls.clear()
    if _nested_log_path is not None and _nested_log_path.is_file():
        _nested_offset = _nested_log_path.stat().st_size
    record = _plain_run_iteration(layout, recipe, operation_timeout, recalc_timeout)
    _print_iteration_timings(record, _read_new_nested())
    _iterations_done += 1
    _net_total += record["elapsed_seconds"] - record["reset_seconds"]
    return record


def _close_calls_handle() -> None:
    if _calls_handle is not None:
        _calls_handle.close()


def _print_run_summary() -> None:
    if _iterations_done:
        print(
            "[%s] run timing: iterations=%d | sum excl. workspace resets=%.4fs"
            % (_scene, _iterations_done, _net_total),
            flush=True,
        )


def hooked_write_json(path: Path, data: dict[str, Any]) -> None:
    global _pending, _calls_handle, _nested_log_path, _scene
    if data.get("schema_version") == "document-step-scene-loop-v2":
        _scene = str(data.get("scene", _scene))
        if _calls_handle is None and data.get("events_file"):
            calls_path = Path(data["events_file"]).with_name("calls.jsonl")
            _calls_handle = calls_path.open("a", encoding="utf-8")
            _nested_log_path = calls_path.with_name("nested_calls.jsonl")
            atexit.register(_close_calls_handle)
            atexit.register(_print_run_summary)
        if _pending is not None and _calls_handle is not None:
            _calls_handle.write(
                json.dumps(_pending, sort_keys=True, ensure_ascii=False) + "\n"
            )
            _calls_handle.flush()
        _pending = None
        iteration = data.get("completed_iterations", 0)
        if iteration > 0 and _current_calls:
            _pending = {
                "schema_version": "document-step-scene-call-timing-v1",
                "iteration": iteration,
                "calls": list(_current_calls),
            }
    _plain_write_json(path, data)


def apply_timing_hooks() -> None:
    global execute_step, run_iteration, write_json, run_command
    execute_step = timed_execute_step
    run_iteration = timed_run_iteration
    write_json = hooked_write_json
    run_command = timed_run_command


def main() -> int:
    args = parse_args()
    ensure_interpreter(args.legacy_python)
    if args.scene == "pdf":
        os.environ["DOCUMENT_BENCH_PDF_APPLICANT_COUNT"] = str(args.pdf_applicant_count)
    dataset = args.dataset or SCENE_DEFAULT_DATASET[args.scene]
    layout = dataset_layout(args.scene, dataset, args.pdf_applicant_count)
    # Pre-loop: validate the selected frozen workload, then prepare the source
    # context / Skill links / runtime environment. Nothing here is measured.
    validate_selected(args.scene, dataset, layout,
                      args.pdf_applicant_count if args.scene == "pdf" else None)
    prepare_environment(layout, args.legacy_python)
    recipe = load_recipe(layout["recipe"], args.scene, layout["step_order"])
    if args.validate_recipe:
        print(f"{args.scene} {dataset} four-step recipe is valid")
        return 0
    if args.loops <= 0:
        raise ValueError("--loops must be positive")
    operation_timeout = args.operation_timeout or int(layout["operation_timeout"])
    recalc_timeout = args.recalc_timeout or int(layout["recalc_timeout"])
    if operation_timeout <= 0 or recalc_timeout <= 0:
        raise ValueError("timeouts must be positive")
    if args.scene == "xlsx" and recalc_timeout >= operation_timeout:
        raise ValueError("XLSX recalc timeout must be lower than operation timeout")

    recipe_sha256 = hashlib.sha256(layout["recipe"].read_bytes()).hexdigest()
    if args.timed:
        apply_timing_hooks()
    environment = probe_environment()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-pid{os.getpid()}"
    run_dir = args.results_dir / args.scene / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "iterations.jsonl"
    summary_path = run_dir / "summary.json"
    summary: dict[str, Any] = {
        "schema_version": "document-step-scene-loop-v2",
        "abstraction": "steps",
        "run_id": run_id,
        "scene": args.scene,
        "dataset": dataset,
        "pdf_applicant_count": (
            args.pdf_applicant_count if args.scene == "pdf" else None
        ),
        "python_mode": args.legacy_python,
        "environment": environment,
        "step_order": layout["step_order"],
        "requested_iterations": args.loops,
        "completed_iterations": 0,
        "successes": 0,
        "failures": 0,
        "operation_timeout_seconds": operation_timeout,
        "recalc_timeout_seconds": recalc_timeout,
        "seed": str(layout["seed"]),
        "workspace": str(layout["workspace"]),
        "recipe": str(layout["recipe"]),
        "recipe_sha256": recipe_sha256,
        "started_at": utc_now(),
        "finished_at": None,
        "elapsed_seconds": 0.0,
        "interrupted": False,
        "events_file": str(events_path),
    }
    write_json(summary_path, summary)
    run_started = time.perf_counter()
    print(
        f"[{args.scene}/{dataset}] start: loops={args.loops}, steps=4, "
        f"workspace={layout['workspace']}, results={run_dir}",
        flush=True,
    )
    signal.signal(signal.SIGTERM, stop_requested)
    try:
        with events_path.open("a", encoding="utf-8") as events:
            for iteration in range(1, args.loops + 1):
                record = run_iteration(layout, recipe, operation_timeout, recalc_timeout)
                record.update(
                    {
                        "schema_version": "document-step-scene-iteration-v2",
                        "abstraction": "steps",
                        "scene": args.scene,
                        "iteration": iteration,
                        "finished_at": utc_now(),
                    }
                )
                events.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
                events.flush()
                summary["completed_iterations"] = iteration
                summary["successes" if record["status"] == "success" else "failures"] += 1
                summary["elapsed_seconds"] = round(time.perf_counter() - run_started, 6)
                write_json(summary_path, summary)
                detail = ""
                if record["status"] == "failed":
                    detail = f", step={record['failed_step']}, error={record.get('error', '')[:300]}"
                print(
                    f"[{args.scene}/{dataset}] {iteration}/{args.loops}: {record['status']} "
                    f"in {record['elapsed_seconds']:.2f}s{detail}",
                    flush=True,
                )
    except KeyboardInterrupt:
        summary["interrupted"] = True
        print(f"[{args.scene}/{dataset}] interrupted by user", file=sys.stderr, flush=True)
    finally:
        summary["finished_at"] = utc_now()
        summary["elapsed_seconds"] = round(time.perf_counter() - run_started, 6)
        write_json(summary_path, summary)
    print(
        f"[{args.scene}/{dataset}] finished: completed={summary['completed_iterations']}, "
        f"successes={summary['successes']}, failures={summary['failures']}, "
        f"summary={summary_path}",
        flush=True,
    )
    if summary["interrupted"]:
        return 130
    return 1 if summary["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
