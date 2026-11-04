#!/usr/bin/env python3
"""DocOps L3 public replay entry (shared scheduler inside the replay image).

Runs the frozen final-effective recipes from a frozen payload. The public code
ONLY schedules, prepares/isolates workspaces, records state, times ROI steps
and archives outputs; it never merges or rewrites task business logic. Each
task keeps its own frozen scripts/seed/commands even when names collide across
tasks.

ROI definition (monotonic clock, per workflow step):
  IN  ROI: recipe steps with phase == "workflow" (final build, repair, recalc,
           final render, original checks).
  OUT ROI: payload/material checks, workspace reset, seed placement, font
           environment setup (021), LibreOffice profile reset, archive copy,
           output hashing and external official scoring.

Execution rules:
  - Frozen-material validation runs BEFORE any workflow command executes; a
    missing/tampered file or mismatched command body aborts the run.
  - A fixed lock for the shared /root namespace rejects
    concurrent execution over the same absolute work path.
  - Workspace reset is restricted to task-scoped paths; it never touches the
    results/archive and never removes other tasks' materials.
  - Round state is written incrementally and flushed immediately; a failed
    round is never overwritten by a later success, and summary is never left
    permanently "in_progress".
  - External official scoring is a separate out-of-ROI record (not_run by
    default in this round); an Agent self-written verifier rc=0 is NOT treated
    as official content acceptance.

This entry does not call agents/models, does not download anything and does not
fall back to alternate script versions when the frozen material is invalid.
"""
from __future__ import annotations

import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import platform

ROOT = Path(__file__).resolve().parent
DEFAULT_PAYLOAD = Path("/opt/docops/payload")
DEFAULT_WORKDIR = Path("/workspace/docops/work")
DEFAULT_RESULTS = Path("/workspace/docops/results")
DEFAULT_STEP_TIMEOUT = 1200  # seconds per workflow step (configurable)
RUNTIME_PROFILE_PATH = ROOT / 'runtime-profile.json'
LEGACY_PROFILE = 'docops-debian-original'
UNIFIED_PROFILE = 'seven-case-openeuler-unified'

SPEC = importlib.util.spec_from_file_location("docops_replay_compile", ROOT / "compile.py")
compile_mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compile_mod)
validate_payload = compile_mod.validate_payload
load = compile_mod.load
destination = compile_mod.destination


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def monotonic_now():
    return time.monotonic()


def root_prefix():
    """Container root used for /root destinations and cwds.

    Defaults to "/" inside the replay image. Host fixture tests set
    DOC_REPLAY_ROOT to a writable temporary directory so the same public entry
    logic is exercised without touching /root. This is never a required runtime
    dependency on a fixed host absolute path inside the image.
    """
    return os.environ.get("DOC_REPLAY_ROOT", "") or "/"


def abs_path(p: str) -> str:
    """Map an absolute container path to the effective root."""
    if ".." in PurePosixPath(p).parts:
        raise ValueError(f"unsafe runtime path: {p}")
    base = Path(root_prefix()).resolve()
    path = base / p.lstrip("/")
    current = path
    while current != base:
        if current.is_symlink():
            raise ValueError(f"symlink in runtime path: {current}")
        current = current.parent
    return str(path)


def fixture_mode():
    return Path(root_prefix()).resolve() != Path("/")


def ensure_execution_context():
    if not fixture_mode() and not (ROOT == Path('/opt/docops') and Path('/.dockerenv').exists()):
        raise ValueError('run is allowed only in the DocOps image; host use is limited to validate-only')


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_json(path, obj):
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# payload & environment introspection
# ---------------------------------------------------------------------------

def catalog_tasks(payload):
    catalog = load(payload / "catalog.json")
    return catalog["tasks"]


def list_tasks(payload):
    rows = []
    for t in catalog_tasks(payload):
        recipe = load(payload / t["recipe"])
        rows.append({
            "task": t["task"], "format": recipe["format"],
            "task_id": recipe["task_id"], "steps": t["steps"],
            "scripts": t["scripts"], "historical_reward": t["historical_reward"],
        })
    return rows


def check_environment(payload):
    """Collect installed facts; environment_errors enforces the contract."""
    import importlib
    profile = runtime_profile()
    checks = {"runtime_profile": profile,
              "python": {"present": True, "version": platform.python_version(),
                         "executable": sys.executable, "prefix": sys.prefix}}
    modules = ("docx", "pptx", "openpyxl", "pypdf", "lxml", "fontTools")
    if profile == UNIFIED_PROFILE:
        modules += ('PIL', 'reportlab')
    for mod_name in modules:
        try:
            m = importlib.import_module(mod_name)
            checks[mod_name] = {"present": True, "version": getattr(m, "__version__", "?")}
        except Exception as e:
            checks[mod_name] = {"present": False, "detail": type(e).__name__}
    tools = UNIFIED_REQUIRED_TOOLS if profile == UNIFIED_PROFILE else (
        'soffice', 'pdftoppm', 'montage', 'fc-list', 'fc-cache', 'perf')
    for tool in tools:
        import shutil as _sh
        command = _sh.which(tool)
        checks[tool] = {**checks.get(tool, {}), 'present': command is not None,
                        'command_path': command}
    skills = {}
    for kind in ("doc", "xlsx", "pptx", "pdf"):
        source = payload / 'skills' / kind
        installed = Path(abs_path(f'/root/.codex/skills/{kind}'))
        skills[kind] = (source / 'SKILL.md').is_file() and all(
            (installed / p.relative_to(source)).is_file()
            and sha256_file(p) == sha256_file(installed / p.relative_to(source))
            for p in source.rglob('*') if p.is_file())
    checks["skills"] = skills
    checks["payload_catalog"] = (payload / "catalog.json").is_file()
    checks["payload_tasks"] = sorted(p.name for p in (payload / "tasks").iterdir()) if (payload / "tasks").is_dir() else []
    if profile == UNIFIED_PROFILE:
        checks['optional_numpy_present'] = importlib.util.find_spec('numpy') is not None
        checks['frozen_font_sources'] = {}
        for name, expected in UNIFIED_FONT_SHA256.items():
            try:
                checks['frozen_font_sources'][name] = sha256_file(Path(name)) == expected
            except OSError:
                checks['frozen_font_sources'][name] = False
    return checks


EXPECTED_VERSIONS = {"python": "3.12.14", "docx": "1.2.0", "pptx": "1.0.2",
                     "openpyxl": "3.1.5", "pypdf": "6.16.2", "lxml": "6.1.2",
                     "fontTools": "4.68.0"}
UNIFIED_VERSIONS = dict(EXPECTED_VERSIONS, python='3.12.3', pypdf='6.10.0',
                        PIL='12.2.0', reportlab='5.0.1')
UNIFIED_REQUIRED_TOOLS = ('python', 'python3', 'bash', 'soffice', 'libreoffice',
                          'pdftoppm', 'pdftotext', 'pdfinfo', 'montage', 'fc-list',
                          'fc-cache', 'fc-match', 'perf', 'unzip', 'rg', 'timeout',
                          'cp', 'mkdir', 'find', 'sort', 'sed', 'ls', 'cat', 'tail', 'sha256sum')
UNIFIED_FONT_SHA256 = {
    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf':
        'f8ace1f892b2bd9dc1792ba7f097fa7588f84fed48321480e04de5390828221f',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf':
        '361c61b82d575c5c35fd9157fda8b0194bcfcd0d88ea8521a4fb5dd53d33dddc',
}


def runtime_profile():
    """The installed, build-bound declaration selects a fixed runtime contract.

    Original payload provenance continues to describe its Agent environment.
    No environment variable can override the installed replay contract.
    """
    if not RUNTIME_PROFILE_PATH.exists():
        return LEGACY_PROFILE
    declaration = load(RUNTIME_PROFILE_PATH)
    profile = declaration.get('id')
    if declaration.get('schema') != 'docops-runtime-profile-v1' or profile not in (LEGACY_PROFILE, UNIFIED_PROFILE):
        raise ValueError('unsupported installed runtime profile')
    return profile


def environment_errors(checks):
    errors = []
    profile = checks.get('runtime_profile', LEGACY_PROFILE)
    versions = UNIFIED_VERSIONS if profile == UNIFIED_PROFILE else EXPECTED_VERSIONS
    if profile not in (LEGACY_PROFILE, UNIFIED_PROFILE):
        errors.append('unsupported runtime profile')
    if profile == UNIFIED_PROFILE:
        if checks.get('python', {}).get('prefix') != '/opt/docops/venv':
            errors.append('unified runtime requires the private DocOps venv')
        if checks.get('optional_numpy_present') is not False:
            errors.append('unexpected optional numpy in unified runtime')
        if not all(checks.get('frozen_font_sources', {}).get(name) for name in UNIFIED_FONT_SHA256):
            errors.append('missing or mismatched frozen font sources')
    for name, expected in versions.items():
        item = checks.get(name, {})
        if not item.get('present') or item.get('version') != expected:
            errors.append(f'{name}: expected {expected}, got {item}')
    tools = UNIFIED_REQUIRED_TOOLS if profile == UNIFIED_PROFILE else (
        'soffice', 'pdftoppm', 'montage', 'fc-list', 'fc-cache', 'perf')
    for name in tools:
        if not checks.get(name, {}).get('present'):
            errors.append(f'missing tool: {name}')
    if not all(checks.get('skills', {}).get(k) for k in ('doc', 'xlsx', 'pptx', 'pdf')):
        errors.append('missing frozen Skill')
    if not checks.get('payload_catalog') or len(checks.get('payload_tasks', [])) != 12:
        errors.append('expected twelve installed tasks')
    return errors


def plan_tasks(payload, tasks):
    """Return the execution plan (all workflow + environment steps) per task."""
    index = {t["task"]: t for t in catalog_tasks(payload)}
    plan = {}
    for tid in tasks:
        if tid not in index:
            raise ValueError(f"unknown task: {tid}")
        recipe = load(payload / index[tid]["recipe"])
        plan[tid] = {
            "task": tid,
            "task_id": recipe["task_id"],
            "format": recipe["format"],
            "output_path": recipe["output_path"],
            "steps": [
                {"id": s["id"], "name": s["name"], "phase": s["phase"],
                 "cwd": s["cwd"], "argv": s["argv"], "shell_sha256": s["shell_sha256"]}
                for s in recipe["steps"]
            ],
            "files": [
                {"kind": f["kind"], "payload": f["payload"], "destination": f["destination"], "sha256": f["sha256"]}
                for f in recipe["files"]
            ],
        }
    return plan


# ---------------------------------------------------------------------------
# workspace isolation helpers (host-side and in-image)
# ---------------------------------------------------------------------------

def task_scoped_paths(recipe):
    """Exact seed files plus disposable directories; never their /root parent."""
    paths = {"/root/tmp/docs", "/root/submission"}
    for f in recipe["files"]:
        p = PurePosixPath(f['destination'])
        destination(str(p))
        if p.parent == PurePosixPath('/root'):
            if p.name.startswith('.'):
                raise ValueError(f'protected /root entry: {p}')
            paths.add(str(p))
        elif p.is_relative_to('/root/tmp'):
            paths.add(str(p.parent))
        else:
            raise ValueError(f'unsupported seed destination: {p}')
    for s in recipe["steps"]:
        cwd = s.get("cwd", "/root")
        if cwd != '/root':
            if not PurePosixPath(cwd).is_relative_to('/root/tmp') or '..' in PurePosixPath(cwd).parts:
                raise ValueError(f'unsupported cwd: {cwd}')
            paths.add(cwd)
    return sorted(paths)


def remove_path(path):
    if path.is_symlink():
        raise ValueError(f'refusing symlink cleanup: {path}')
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def check_layout(recipe, payload, workdir, results_dir):
    protected = [Path(p).resolve() for p in (payload, workdir, results_dir)]
    for raw in task_scoped_paths(recipe):
        target = Path(abs_path(raw))
        for path in protected:
            if target == path or target.is_relative_to(path) or path.is_relative_to(target):
                raise ValueError(f'workspace reset overlaps protected path: {target} / {path}')


def reset_workspace(recipe, extra_clean=None):
    """Reset task-scoped workspace paths. Never touches results/archive and
    never removes paths outside the effective root. extra_clean is a
    caller-provided list of container-scoped paths already validated."""
    if extra_clean:
        raise ValueError('arbitrary extra cleanup paths are not supported')
    removed = []
    for d in task_scoped_paths(recipe):
        p = Path(abs_path(d))
        if p.exists():
            remove_path(p)
            removed.append(d)
    return removed


def place_files(payload, recipe, verify=True):
    """Copy frozen files to their destinations; verify sha256. Out of ROI."""
    placed = []
    for f in recipe["files"]:
        data = (payload / f["payload"]).read_bytes()
        if verify and hashlib.sha256(data).hexdigest() != f["sha256"]:
            raise ValueError(f"frozen file hash mismatch before run: {f['payload']}")
        rel = destination(f["destination"])
        path = Path(abs_path(rel))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        placed.append({"payload": f["payload"], "destination": f["destination"]})
    return placed


def prepare_font_env(recipe, state, timeout=DEFAULT_STEP_TIMEOUT):
    """Run environment_setup steps (021 font prep) OUT of ROI; returns their
    wall time separately. Restores other tasks' font state afterwards."""
    timings = []
    for s in recipe["steps"]:
        if s.get("phase") != "environment_setup":
            continue
        t0 = monotonic_now()
        r = run_step(s, state, timeout=timeout)
        timings.append({"step": s["id"], "name": s["name"], "rc": r["rc"],
                        "wall_s": r["wall_s"], "status": r["status"]})
        state['prepare']['font_env'] = timings
        flush(state)
        if r['status'] != 'ok':
            state['failures'].append({'step': s['id'], 'phase': 'environment_setup', 'status': r['status']})
            raise RuntimeError(f'environment preparation failed: {s["id"]}')
    return timings


# ---------------------------------------------------------------------------
# step execution
# ---------------------------------------------------------------------------

def run_step(step, state, timeout=None):
    """Run one recipe step with its frozen cwd. Returns monotonic wall time."""
    entry = {"id": step["id"], "name": step["name"], "phase": step.get("phase"),
             "cwd": step["cwd"], "argv": step["argv"],
             "status": "in_progress"}
    state["current_step"] = entry
    state["steps"].append(entry)
    flush(state)
    proc = None
    t0 = monotonic_now()
    entry['start_monotonic'] = t0
    try:
        cwd = abs_path(step['cwd'])
        if not Path(cwd).is_dir():
            raise ValueError(f'declared cwd is missing: {step["cwd"]}')
        proc = subprocess.Popen(
            step["argv"], cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True)
        entry['pid'] = proc.pid
        flush(state)
        stdout, stderr = proc.communicate(timeout=timeout)
        wall = monotonic_now() - t0
        entry.update({"rc": proc.returncode, "wall_s": round(wall, 4),
                      "status": "ok" if proc.returncode == 0 else "failed",
                      "stdout_tail": stdout.decode("utf-8", "replace")[-400:],
                      "stderr_tail": stderr.decode("utf-8", "replace")[-400:],
                      "end_monotonic": monotonic_now()})
    except subprocess.TimeoutExpired as e:
        terminate_group(proc)
        stdout, stderr = proc.communicate(timeout=5)
        wall = monotonic_now() - t0
        entry.update({"rc": "timeout", "wall_s": round(wall, 4), "status": "timeout",
                      "timeout_sec": timeout,
                      "stdout_tail": stdout.decode("utf-8", "replace")[-400:],
                      "stderr_tail": stderr.decode("utf-8", "replace")[-400:],
                      "end_monotonic": monotonic_now()})
    except (Exception, KeyboardInterrupt) as e:
        terminate_group(proc)
        wall = monotonic_now() - t0
        entry.update({"rc": "exception", "wall_s": round(wall, 4),
                      "status": "failed", "detail": f"{type(e).__name__}: {e}",
                      "end_monotonic": monotonic_now()})
    finally:
        terminate_group(proc)
    state["current_step"] = None
    flush(state)
    return entry


def terminate_group(proc):
    """Only kill the session created for this step, never global soffice PIDs."""
    if proc is None:
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait(timeout=5)


# ---------------------------------------------------------------------------
# round state
# ---------------------------------------------------------------------------

def flush(state):
    atomic_write_json(state["run_path"], state)


def round_initial(task, recipe, results_dir, round_id, loop, requested):
    run_path = results_dir / task / round_id / "run.json"
    run_path.parent.mkdir(parents=True, exist_ok=False)
    state = {
        "schema": "docops-replay-round-state-v1",
        "task": task, "loop": loop, "round_id": round_id, "requested": requested,
        "started_utc": now_utc(), "status": "in_progress",
        "steps": [], "current_step": None,
        "prepare": {}, "archive": {}, "external_score": {"status": "not_run"},
        "completed": False, "successes": 0, "failures": [],
        "run_path": str(run_path),
    }
    return state


# ---------------------------------------------------------------------------
# archive
# ---------------------------------------------------------------------------

def archive_output(recipe, results_dir, task, round_id):
    """Copy the declared output into results and hash it. Out of ROI."""
    out_path = recipe["output_path"]
    out_file = Path(abs_path(out_path))
    if not out_file.is_file():
        return {"status": "missing_output", "output_path": out_path}
    dest = results_dir / task / round_id / "submission"
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / out_file.name
    shutil.copy2(out_file, target)
    return {"status": "ok", "output_path": out_path,
            "archive_path": str(target.relative_to(results_dir)),
            "bytes": target.stat().st_size, "sha256": sha256_file(target)}


def external_score(recipe, archive, score_dir):
    """External official scoring stub (out of ROI). Not executed this round.
    Returns not_run; the interface exists so a later official score step can be
    bound to this run without conflating with Agent self-verifier results."""
    return {"status": "not_run",
            "note": "external official scoring is out of ROI and not executed in this round",
            "agent_self_verifier_is_not_official_score": True}


# ---------------------------------------------------------------------------
# run one task
# ---------------------------------------------------------------------------

def run_one_task(task, payload, workdir, results_dir, round_id, loop, timeout, lock_path, extra_clean=None):
    """Run one round for one task with frozen material validation before any
    workflow command. Returns the final state dict (never throws for workload
    failures; infra errors are recorded and re-raised)."""
    index = {t["task"]: t for t in catalog_tasks(payload)}
    if task not in index:
        raise ValueError(f"unknown task: {task}")
    recipe = load(payload / index[task]["recipe"])
    check_layout(recipe, payload, workdir, results_dir)

    state = round_initial(task, recipe, results_dir, round_id, loop, requested=True)
    state["task_id"] = recipe["task_id"]
    state["format"] = recipe["format"]
    state['historical_score'] = recipe.get('historical_score')
    state['recipe_sha256'] = sha256_file(payload / index[task]['recipe'])
    state['payload_index_sha256'] = sha256_file(payload / 'payload-index.json')
    state['roi_steps'] = []
    state['roi_intervals'] = []
    state['roi_clock'] = 'CLOCK_MONOTONIC'
    state['roi_n_failed'] = 0
    results_dir.mkdir(parents=True, exist_ok=True)
    snapshot = None
    try:
        # 1) frozen validation before ANY workflow command (out of ROI)
        validate_payload(payload)
        state["validate"] = {"status": "ok"}
        if not fixture_mode():
            state['environment'] = check_environment(payload)
            errors = environment_errors(state['environment'])
            if errors:
                raise ValueError('; '.join(errors))
        flush(state)

        # 2) prepare (out of ROI)
        reset_workspace(recipe, extra_clean)
        snapshot = snapshot_environment(workdir, recipe)
        placed = place_files(payload, recipe, verify=True)
        state["prepare"]["placed_files"] = len(placed)
        state["prepare"]["reset_paths"] = task_scoped_paths(recipe)
        state["prepare"]["status"] = "in_progress"
        # 021 font environment setup is out of ROI and restored afterwards
        font_ev = prepare_font_env(recipe, state, timeout=timeout)
        state["prepare"]["font_env"] = font_ev
        state["prepare"]["status"] = "ok"
        flush(state)

        # 3) workflow steps (IN ROI) with monotonic clock
        roi = []
        for s in recipe["steps"]:
            if s.get("phase") != "workflow":
                continue
            entry = run_step(s, state, timeout=timeout)
            roi.append({"step": s["id"], "name": s["name"], "rc": entry.get("rc"),
                        "wall_s": entry.get("wall_s"), "status": entry.get("status")})
            state['roi_steps'] = roi
            state['roi_intervals'].append({'step': s['id'], 'pid': entry.get('pid'),
                                          'start': entry['start_monotonic'],
                                          'end': entry['end_monotonic']})
            if entry.get("status") != "ok":
                state["failures"].append({"step": s["id"], "status": entry.get("status")})
                break
        state["roi_wall_s"] = round(sum(e.get("wall_s", 0) or 0 for e in roi), 4)
        state["roi_steps"] = roi
        state["roi_n_ok"] = sum(1 for e in roi if e.get("status") == "ok")
        state["roi_n_failed"] = sum(1 for e in roi if e.get("status") != "ok")

        # Archive remains out of ROI, including available failure artifacts.
        try:
            arc = archive_output(recipe, results_dir, task, round_id)
        except Exception as exc:
            state['archive'] = {'status': 'failed', 'detail': str(exc)}
            raise
        state["archive"] = arc
        state["external_score"] = external_score(recipe, arc, None)

        # 6) finalize
        state["completed"] = True
        state["successes"] = 1 if (state["roi_n_failed"] == 0 and arc.get("status") == "ok") else 0
        state["status"] = "completed" if state['successes'] else 'failed'
        state["ended_utc"] = now_utc()
    except (Exception, KeyboardInterrupt) as e:
        state["status"] = "failed"
        state["infra_failure"] = {"kind": type(e).__name__, "detail": str(e)}
        state["ended_utc"] = now_utc()
        state['successes'] = 0
        if state['prepare'].get('status') == 'in_progress':
            state['prepare']['status'] = 'failed'
    finally:
        if snapshot is not None:
            try:
                restore_fonts(snapshot)
                state['environment_restore'] = {'status': 'ok'}
            except Exception as exc:
                state['status'] = 'failed'
                state['successes'] = 0
                state['environment_restore'] = {'status': 'failed', 'detail': str(exc)}
    flush(state)
    return state


def snapshot_environment(workdir, recipe):
    """Preserve baseline state, including overwritten existing font files."""
    Path(workdir).mkdir(parents=True, exist_ok=True)
    temp = tempfile.TemporaryDirectory(prefix='environment-', dir=workdir)
    paths = ['/root/.config/libreoffice']
    if any(s.get('phase') == 'environment_setup' for s in recipe['steps']):
        paths += ['/root/.local/share/fonts', '/root/.cache/fontconfig', '/var/cache/fontconfig']
    if recipe.get('task') == '001':
        paths += ['/tmp/lo_packet_profile_20261103_v2']
    snapshot = {'temp': temp, 'paths': []}
    try:
        for number, raw in enumerate(paths):
            path = Path(abs_path(raw))
            backup = Path(temp.name) / str(number)
            existed = path.exists()
            if existed:
                shutil.copytree(path, backup, symlinks=True)
            snapshot['paths'].append((raw, backup, existed))
            if 'profile' in raw or raw.endswith('/libreoffice'):
                remove_path(path)
        return snapshot
    except BaseException:
        restore_fonts(snapshot)
        raise


def restore_fonts(snapshot):
    """Restore exactly the captured font/profile state, including failures."""
    try:
        for raw, backup, existed in snapshot['paths']:
            path = Path(abs_path(raw))
            remove_path(path)
            if existed:
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(backup, path, symlinks=True)
        # The per-user font cache is restored with the fonts. No broad fc-cache
        # scan or filename heuristic can leak Aptos substitutions to later tasks.
    finally:
        snapshot['temp'].cleanup()


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------

def update_summary(results_dir, task, state):
    summary_path = results_dir / task / "summary.json"
    summary = {"requested": 0, "completed": 0, "successes": 0, "failures": 0,
               "rounds": []}
    if summary_path.is_file():
        try:
            summary = load(summary_path)
        except Exception as exc:
            raise ValueError('existing summary is unreadable; refusing to overwrite') from exc
    summary["requested"] += 1
    summary["rounds"].append({"loop": state["loop"],
                              "round_id": state['round_id'],
                              "completed": state['completed'],
                              "status": state["status"],
                              "success": state.get("successes", 0) == 1,
                              "failures": state.get("failures", [])})
    summary["completed"] = sum(1 for r in summary["rounds"] if r.get('completed', r['status'] == 'completed'))
    summary["successes"] = sum(1 for r in summary["rounds"] if r["success"])
    summary["failures"] = sum(1 for r in summary["rounds"] if not r["success"])
    atomic_write_json(summary_path, summary)
    return summary


# ---------------------------------------------------------------------------
# validate-only
# ---------------------------------------------------------------------------

def validate_only(payload, workdir, env_check=False):
    result = {"payload": None, "environment": None, "plan": None,
              "workload_executed": False}
    result["payload"] = validate_payload(payload)
    if env_check:
        result["environment"] = check_environment(payload)
        result['environment_errors'] = environment_errors(result['environment'])
    result["plan"] = plan_tasks(payload, [t["task"] for t in catalog_tasks(payload)])
    return result


# ---------------------------------------------------------------------------
# lock
# ---------------------------------------------------------------------------

class WorkLock:
    def __init__(self, workdir):
        # All tasks write the same absolute /root namespace, regardless of
        # --workdir. Lock that namespace rather than a caller-selected directory.
        self.path = Path(abs_path('/tmp/docops-replay.lock'))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = None

    def acquire(self):
        self.fd = open(self.path, "a+")
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.fd.close()
            self.fd = None
            return False
        return True

    def release(self):
        if self.fd is not None:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            finally:
                self.fd.close()
                self.fd = None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)

    p_list = sub.add_parser("list", help="list the twelve tasks and their formats")
    p_list.add_argument("--payload", type=Path, default=DEFAULT_PAYLOAD)
    p_validate = sub.add_parser("validate-only",
                                help="check materials, environment and plan; never runs workload")
    p_validate.add_argument("--payload", type=Path, default=DEFAULT_PAYLOAD)
    p_validate.add_argument("--workdir", type=Path, default=DEFAULT_WORKDIR)
    p_validate.add_argument("--env-check", action="store_true",
                            help="also run installed-state environment check")

    p_run = sub.add_parser("run", help="run one or more tasks (loops, sequential)")
    p_run.add_argument("--payload", type=Path, default=DEFAULT_PAYLOAD)
    p_run.add_argument("--workdir", type=Path, default=DEFAULT_WORKDIR)
    p_run.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    p_run.add_argument("--task", action="append", required=True,
                       help="task id (repeatable); e.g. --task 026")
    p_run.add_argument("--loops", type=int, default=1)
    p_run.add_argument("--step-timeout", type=float, default=DEFAULT_STEP_TIMEOUT)
    p_run.add_argument("--validate-only", action="store_true",
                       help="only validate; do not execute any workload command")
    p_run.add_argument("--no-lock", action="store_true",
                       help="skip the workspace lock (tests only)")
    args = parser.parse_args()

    if args.action == "list":
        payload = Path(args.payload) if hasattr(args, "payload") else DEFAULT_PAYLOAD
        rows = list_tasks(payload)
        print(json.dumps({"tasks": rows}, ensure_ascii=False, indent=2))
        return 0

    if args.action == "validate-only":
        result = validate_only(args.payload, args.workdir, env_check=args.env_check)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get('environment_errors') else 0

    # run
    tasks = args.task
    if args.loops < 1 or args.step_timeout <= 0:
        parser.error('loops and step-timeout must be positive')
    for t in tasks:
        known = {row["task"] for row in list_tasks(args.payload)}
        if t not in known:
            print(f"FATAL: unknown task {t}", file=sys.stderr)
            return 2
    # validate before any workload command (shared entry guarantee)
    try:
        validate_payload(args.payload)
    except Exception as e:
        print(f"FATAL: frozen material invalid, refusing to run: {e}", file=sys.stderr)
        return 2
    if args.validate_only:
        result = validate_only(args.payload, args.workdir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    try:
        ensure_execution_context()
        if args.no_lock and not fixture_mode():
            raise ValueError('--no-lock is restricted to isolated fixtures')
        index = {t['task']: t for t in catalog_tasks(args.payload)}
        for task in tasks:
            check_layout(load(args.payload / index[task]['recipe']), args.payload,
                         args.workdir, args.results_dir)
    except ValueError as exc:
        print(f'FATAL: {exc}', file=sys.stderr)
        return 2

    lock = None if args.no_lock else WorkLock(args.workdir)
    if lock is not None and not lock.acquire():
        print("FATAL: shared work path is locked by another replay process; "
              "concurrent execution refused", file=sys.stderr)
        return 3

    results = []
    try:
        for task in tasks:
            seq = 0
            summary_path = args.results_dir / task / "summary.json"
            if summary_path.is_file():
                try:
                    seq = load(summary_path).get("requested", 0)
                except Exception:
                    seq = 0
            for loop in range(1, args.loops + 1):
                seq += 1
                round_id = f"round-{seq:03d}"
                state = run_one_task(task, args.payload, args.workdir, args.results_dir,
                                     round_id, loop, args.step_timeout, args.workdir)
                summary = update_summary(args.results_dir, task, state)
                results.append({"task": task, "loop": loop, "round_id": round_id,
                                "status": state["status"],
                                "successes": state.get("successes"),
                                "roi_wall_s": state.get("roi_wall_s"),
                                "failures": state.get("failures"),
                                "summary": summary})
                if state.get('successes') != 1:
                    print(json.dumps({'rounds': results, 'stopped_after_failure': True},
                                     ensure_ascii=False, indent=2))
                    return 1
    finally:
        if lock is not None:
            lock.release()
    print(json.dumps({"rounds": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
