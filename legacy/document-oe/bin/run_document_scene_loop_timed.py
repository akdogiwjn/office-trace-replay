#!/usr/bin/env python3
"""Per-call timing wrapper around run_document_scene_loop.py.

Imports the original loop module untouched and monkey-patches it so that:

1. The elapsed time of every top-level tool call (read / write / exec, i.e.
   every script invoked by the recipe) is recorded to calls.jsonl next to
   iterations.jsonl in the run results directory.
2. Nested script invocations made *inside* those scripts (e.g.
   fill_fillable_fields.py and convert_pdf_to_images.py inside
   run_batch_fill_render.py, soffice inside recalc.py) are timed as well,
   via a sitecustomize hook injected through PYTHONPATH, and recorded to
   nested_calls.jsonl in the same directory.
3. After every iteration the per-script timings are printed to the terminal,
   together with the iteration total both including and excluding the
   workspace reset time.

Usage (identical arguments to the original script):
    python3 run_document_scene_loop_timed.py --scene pdf --loops 1
    python3 run_document_scene_loop_timed.py --scene xlsx --loops 1
"""

from __future__ import annotations

import atexit
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_document_scene_loop as core

_original_run_iteration = core.run_iteration
_original_write_json = core.write_json
_original_run_command = core.run_command

_TIMING_HOOKS_DIR = Path(__file__).resolve().parent / "timing_hooks"

_current_calls: list[dict[str, Any]] = []
_pending: Optional[dict[str, Any]] = None
_calls_handle: Any = None
_nested_log_path: Optional[Path] = None
_nested_offset: int = 0
_scene: str = "run"
_iterations_done: int = 0
_net_total: float = 0.0


def call_label(call: dict[str, Any]) -> str:
    """Human readable label: script basename for exec, else function name."""
    function = str(call.get("function_name", "unknown"))
    if function != "exec":
        return function
    command = " ".join(str(call["arguments"]["command"]).split())
    match = re.search(r"([\w.-]+\.py)\b", command)
    if match:
        return "exec:" + match.group(1)
    return "exec:" + (command[:60] + ("..." if len(command) > 60 else ""))


def timed_execute_step(
    step: dict[str, Any],
    operation_timeout: int,
    recalc_timeout: int,
    step_times: dict[str, float],
) -> None:
    """Replacement for core.execute_step: same behavior, but records each call."""
    step_id = step["operation_id"]
    started = time.perf_counter()
    try:
        for call_index, source_call in enumerate(step["source_tool_calls"], start=1):
            call = source_call["tool_call"]
            call_started = time.perf_counter()
            try:
                core.execute_call(call, operation_timeout, recalc_timeout)
            except Exception as exc:
                raise core.StepFailure(
                    step_id=step_id,
                    call_index=call_index,
                    tool_call_id=str(source_call.get("tool_call_id", "")),
                    function_name=str(call.get("function_name", "unknown")),
                    message=f"{type(exc).__name__}: {exc}",
                    elapsed_seconds=time.perf_counter() - call_started,
                ) from exc
            finally:
                _current_calls.append(
                    {
                        "step_id": step_id,
                        "call_index": call_index,
                        "label": call_label(call),
                        "seconds": round(time.perf_counter() - call_started, 6),
                    }
                )
    finally:
        step_times[step_id] = round(
            step_times.get(step_id, 0.0) + time.perf_counter() - started, 6
        )


def timed_run_command(command: str, timeout: int) -> None:
    """Replacement for core.run_command: injects the nested-timing hook dir.

    PYTHONPATH is inherited by every python3 the command starts, so each of
    them loads timing_hooks/sitecustomize.py, which patches its own
    subprocess.run and appends nested child timings to the run's
    nested_calls.jsonl. The variable is restored afterwards.
    """
    saved_path = os.environ.get("PYTHONPATH")
    saved_log = os.environ.get("DOCUMENT_BENCH_TIMING_LOG")
    os.environ["PYTHONPATH"] = (
        str(_TIMING_HOOKS_DIR) + (os.pathsep + saved_path if saved_path else "")
    )
    if _nested_log_path is not None:
        os.environ["DOCUMENT_BENCH_TIMING_LOG"] = str(_nested_log_path)
    try:
        _original_run_command(command, timeout)
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
    """Returns nested timing lines appended since this iteration started."""
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


def timed_run_iteration(
    layout: dict[str, Any],
    recipe: dict[str, Any],
    operation_timeout: int,
    recalc_timeout: int,
) -> dict[str, Any]:
    """Replacement for core.run_iteration: resets timers, prints the breakdown."""
    global _nested_offset, _iterations_done, _net_total
    _current_calls.clear()
    if _nested_log_path is not None and _nested_log_path.is_file():
        _nested_offset = _nested_log_path.stat().st_size
    record = _original_run_iteration(layout, recipe, operation_timeout, recalc_timeout)
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
    """Replacement for core.write_json: flushes finished iterations to calls.jsonl.

    The original main() calls write_json once before the loop (iteration 0)
    and once after every iteration, so this is the only reliable hook point
    that knows both the results directory and the iteration number.
    """
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
    _original_write_json(path, data)


core.execute_step = timed_execute_step
core.run_iteration = timed_run_iteration
core.write_json = hooked_write_json
core.run_command = timed_run_command

if __name__ == "__main__":
    raise SystemExit(core.main())
