#!/usr/bin/env python3
"""Run the current four-step PDF or XLSX scene repeatedly in one container."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LOOP_COUNT = 20_000
# Change only this default to 10 for the original ten-applicant PDF mode.
PDF_APPLICANT_COUNT = 1
ROOT = Path("/opt/document-bench")
DEFAULT_RESULTS_ROOT = ROOT / "results"
SCENES = {
    "pdf": {
        "seed": ROOT / "pdf",
        "workspace": Path("/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01"),
        "recipe": ROOT / "operations/pdf_key_operations.json",
        "operation_timeout": 300,
        "recalc_timeout": 180,
        "step_order": [
            "PDF-P01-inspect_prepare",
            "PDF-P02-build",
            "PDF-P03-process_publish",
            "PDF-P04-verify_deliver",
        ],
    },
    "xlsx": {
        "seed": ROOT / "xlsx",
        "workspace": Path("/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01"),
        "recipe": ROOT / "operations/xlsx_key_operations.json",
        "operation_timeout": 900,
        "recalc_timeout": 600,
        "step_order": [
            "XLSX-P01-inspect_prepare",
            "XLSX-P02-build",
            "XLSX-P03-process_publish",
            "XLSX-P04-verify_deliver",
        ],
    },
}


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


def main() -> int:
    args = parse_args()
    if args.scene == "pdf":
        os.environ["DOCUMENT_BENCH_PDF_APPLICANT_COUNT"] = str(args.pdf_applicant_count)
    layout = SCENES[args.scene]
    recipe = load_recipe(layout["recipe"], args.scene, layout["step_order"])
    if args.validate_recipe:
        print(f"{args.scene} four-step recipe is valid")
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
        "pdf_applicant_count": (
            args.pdf_applicant_count if args.scene == "pdf" else None
        ),
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
        f"[{args.scene}] start: loops={args.loops}, steps=4, "
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
                    f"[{args.scene}] {iteration}/{args.loops}: {record['status']} "
                    f"in {record['elapsed_seconds']:.2f}s{detail}",
                    flush=True,
                )
    except KeyboardInterrupt:
        summary["interrupted"] = True
        print(f"[{args.scene}] interrupted by user", file=sys.stderr, flush=True)
    finally:
        summary["finished_at"] = utc_now()
        summary["elapsed_seconds"] = round(time.perf_counter() - run_started, 6)
        write_json(summary_path, summary)
    print(
        f"[{args.scene}] finished: completed={summary['completed_iterations']}, "
        f"successes={summary['successes']}, failures={summary['failures']}, "
        f"summary={summary_path}",
        flush=True,
    )
    if summary["interrupted"]:
        return 130
    return 1 if summary["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
