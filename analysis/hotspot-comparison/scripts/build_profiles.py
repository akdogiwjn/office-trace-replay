#!/usr/bin/env python3
"""Build the three-layer hotspot profiles, old-slice coverage, new-hotspot list
and legacy-claim verification from the collected runs.

Inputs:  analysis/hotspot-comparison/raw/<config>/{r1,r2,pyspy,stat,syscalls}
         analysis/hotspot-comparison/config/*.json, legacy/*.json
Outputs: analysis/hotspot-comparison/processed/<config>.json (per-config profiles)
         analysis/hotspot-comparison/processed/coverage.json
         analysis/hotspot-comparison/processed/new-hotspots.json
         analysis/hotspot-comparison/processed/claims-verification.json
"""
import json
import re
import csv
import argparse
import sys
import shlex
import hashlib
from functools import lru_cache
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent.parent
RAW = ROOT / "raw"
PROCESSED = ROOT / "processed"

# ---------------------------------------------------------------- DSO classes
DSO_CLASS_RULES = [
    (r"libpython(?:3\.\d+)?", "libpython"),
    (r"pyexpat|libexpat", "expat-xml"),
    (r"_elementtree", "elementtree-xml"),
    (r"libxml2", "libxml2"),
    (r"^libz\.so|^libz\.|zlib", "zlib"),
    (r"_imaging", "pillow"),
    (r"libpoppler", "poppler"),
    (r"libfreetype", "freetype"),
    (r"libfontconfig", "fontconfig"),
    (r"libmergedlo|libsclo|libscfiltlo|libuno_|libsal|sax\.|libcomphelper|"
     r"libvcl|libcanvas|libbasegfx|libdrawinglayer|libsvl|libsvt|libtl|"
     r"libootlo|libfwk|libtk|libediteng|liboffacc|libi18n|libgcc3|store|"
     r"libchart|libcuilo|libdbtools|libembobj|libfilterconfig|libodf|"
     r"liboox|libreflect|librpt|libsfx|libsmlo|libsot|libspell|libsvgio|"
     r"libsvx|libswlo|libtextconversion|libtvhlp|libucp|libunotest|"
     r"libvbaobj|libxmlsecurity|libxo|libbinaryurp|libconnectorfactory|"
     r"libintervention|liblocalebe|libnsapp|libpackage2|libpasswordcontainer|"
     r"libsrtrs1|libtextfd|libucpdav|libupdchk|libvclcanvas|libconfigmgr",
     "libreoffice"),
    (r"libc\.so|libc-2\.", "libc"),
    (r"ld-linux", "ld"),
    (r"cpython-312", "python-ext"),
    (r"^pdftoppm$", "pdftoppm-bin"),
    (r"^bash$|^dash$", "bash-bin"),
    (r"\[unknown\]", "unknown"),
]
GENERIC_DSO_CLASSES = {"libpython", "libc", "ld", "python-ext", "unknown"}

ROLE_SIDE = {
    # role -> "side" used by the zlib/expat DSO rules (taxonomy R5)
    "xlsx-enhance": "xlsx-save",
    "xlsx-inspect-structure": "xlsx-load", "xlsx-inspect-features": "xlsx-load",
    "xlsx-inspect-formulas": "xlsx-load", "xlsx-inspect-cached": "xlsx-load",
    "xlsx-verify": "xlsx-load", "xlsx-summary-export": "xlsx-load",
    "xlsx-inspect-tool": "xlsx-load", "xlsx-recalc": "xlsx-load",
    "xlsx-atomic-helper": "orch",
    "pdf-convert": "pdf-image", "pdf-fill": "pdf-fill",
    "pdf-check-fillable": "pdf-parse", "pdf-extract-fields": "pdf-parse",
    "pdf-verify": "pdf-parse",
}
ORCH_ROLES = {"runner", "bash", "shell-text", "lo-startup", "taskset",
              "soffice-wrapper", "roi-marker", "perf", "perf-exec"}
JSON_ROLES = {"pdf-mapping-driver", "pdf-summary-writer", "python-inline"}

LEGACY_SCRIPT_TOKENS = {
    "PDF-S1": ("check_fillable_fields.py",),
    "PDF-S2": ("extract_form_field_info.py",),
    "PDF-S3": ("convert_pdf_to_images.py",), "PDF-S4": ("fill_fillable_fields.py",),
    "PDF-S5": ("convert_pdf_to_images.py",), "PDF-S6": ("verify_pdf_batch.py",),
    "X-S1": ("inspect_xlsx_structure.py",), "X-S2": ("inspect_xlsx_features.py",),
    "X-S3": ("enhance_workbook.py",), "X-S4": ("recalc.py",),
    "X-S5": ("inspect_xlsx_formulas.py",), "X-S6": ("inspect_xlsx_cached_values.py",),
    "X-S7": ("verify_xlsx_enhanced.py",), "X-S8": ("write_xlsx_summary.py",),
}



# Path-aware execution and source attribution.
SHELL_WRAPPERS = {"sh", "bash", "dash"}
OLD_WORKSPACES = {
    "pdf": "/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01",
    "xlsx": "/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01",
}


def extract_python_invocations(command, cwd=None):
    """Return Python script operands, tracking explicit cd within shell text.

    A Python script argument is the only source candidate; workbook arguments,
    redirects, `cat` paths, and arbitrary text are not treated as scripts.
    """
    if not command:
        return []
    # /proc command identities are reconstructed from argv without quoting.
    # For `bash -c`, all text after the `-c` operand is that shell program even
    # when operators appear unquoted in the reconstructed representation.
    nested = re.match(r"^\s*(?:\S*/)?(?:bash|sh|dash)\s+-c\s+([\s\S]*)$", str(command))
    if nested:
        return extract_python_invocations(nested.group(1), cwd)
    lexer = shlex.shlex(str(command), posix=True, punctuation_chars=";&|\n")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        tokens = shlex.split(str(command), posix=True)
    segments, seg = [], []
    for token in tokens:
        if token in (";", "&&", "||", "|", "\n"):
            if seg:
                segments.append(seg)
                seg = []
        else:
            seg.append(token)
    if seg:
        segments.append(seg)
    result, current_cwd = [], cwd
    for seg in segments:
        if not seg:
            continue
        exe = Path(seg[0]).name
        if exe in SHELL_WRAPPERS and "-c" in seg:
            idx = seg.index("-c")
            result.extend(extract_python_invocations(seg[idx + 1] if idx + 1 < len(seg) else "", current_cwd))
            continue
        if exe == "cd":
            if len(seg) > 1:
                current_cwd = (str(Path(seg[1])) if seg[1].startswith("/") else
                               str(Path(current_cwd) / seg[1]) if current_cwd else None)
            continue
        i = 0
        while i < len(seg) and ("=" in seg[i] or Path(seg[i]).name in
                                {"env", "taskset", "timeout", "time", "nice", "stdbuf"}):
            wrapper = Path(seg[i]).name
            i += 1
            if wrapper in {"taskset", "timeout", "nice", "stdbuf"}:
                while i < len(seg) and seg[i].startswith("-"):
                    option = seg[i]
                    i += 1
                    if option in {"-c", "-k", "--kill-after", "-o", "-e"} and i < len(seg):
                        i += 1
                if wrapper == "timeout" and i < len(seg) and re.fullmatch(r"[0-9.]+[smhd]?", seg[i]):
                    i += 1
        if i >= len(seg) or not re.fullmatch(r"(?:.*/)?python(?:\d+(?:\.\d+)*)?", seg[i]):
            continue
        interpreter = seg[i]
        i += 1
        while i < len(seg) and seg[i].startswith("-"):
            option = seg[i]
            i += 1
            if option in ("-c", "-m"):
                i = len(seg)
                break
            if option in ("-W", "-X") and i < len(seg):
                i += 1
        if i >= len(seg) or seg[i] == "-" or seg[i].startswith("-"):
            continue
        script = seg[i]
        resolved = (str(Path(script)) if script.startswith("/") else
                    str(Path(current_cwd) / script) if current_cwd else None)
        result.append({"interpreter": interpreter, "script_argument": script,
                       "resolved_script": resolved, "cwd": current_cwd,
                       "arguments": seg[i + 1:], "segment": " ".join(seg)})
    return result


@lru_cache(maxsize=2)
def _legacy_recipe_commands(scene):
    path = REPO_ROOT / "legacy" / "document-oe" / "operations" / (
        "pdf_key_operations.json" if scene == "pdf" else "xlsx_key_operations.json")
    data = json.loads(path.read_text())
    commands = []
    def walk(node):
        if isinstance(node, dict):
            value = node.get("command")
            if isinstance(value, str):
                commands.append(value)
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)
    walk(data)
    return commands


@lru_cache(maxsize=512)
def _resolve_cwd_cached(base, args, scene):
    """Cached implementation for repeated samples of the same script argv."""
    if not base or not args:
        return None, None
    for command in _legacy_recipe_commands(scene):
        for ref in extract_python_invocations(command):
            if Path(ref["script_argument"]).name != base or not ref.get("cwd"):
                continue
            ref_args = {Path(x).name for x in ref.get("arguments", []) if not x.startswith("-")}
            shared = sorted(set(args) & ref_args)
            if shared:
                return ref["cwd"], {"evidence_grade": "reconstructed from frozen operation command",
                                     "recipe_command": command,
                                     "shared_data_argument_basenames": shared,
                                     "cwd_was_directly_recorded": False}
    return None, None


def resolve_cwd_from_frozen_recipe(invocation, scene):
    """Reconstruct cwd only when frozen operation script and data args match.

    This returns recipe-derived evidence, never a directly recorded cwd.
    Matching uses the Python script operand plus an input/output basename from
    the archived command; a shared process role or a mention is insufficient.
    """
    base = Path(invocation.get("script_argument", "")).name
    args = tuple(Path(x).name for x in invocation.get("arguments", []) if not x.startswith("-"))
    return _resolve_cwd_cached(base, args, scene)


def resolve_invocation_context(invocation, scene):
    if invocation.get("resolved_script"):
        return invocation
    cwd, evidence = resolve_cwd_from_frozen_recipe(invocation, scene)
    if cwd:
        invocation = dict(invocation)
        invocation["cwd"] = cwd
        invocation["resolved_script"] = str(Path(cwd) / invocation["script_argument"])
        invocation["cwd_resolution"] = evidence
    return invocation


def _frozen_recipe_for_config(config, scene):
    if config in ("opm-n1", "opm-n10", "tlc"):
        suffix = "pdf" if scene == "pdf" else "xlsx"
        return REPO_ROOT / "legacy/document-oe/operations" / f"{suffix}_key_operations.json"
    if config:
        return REPO_ROOT / "compatibility/recipes" / f"{config}.json"
    return None


def _recipe_written_script(script_path, config, scene):
    """Return exact recipe write content targeting this runtime path, if any."""
    recipe_path = _frozen_recipe_for_config(config, scene)
    if not recipe_path or not recipe_path.is_file():
        return None
    recipe = json.loads(recipe_path.read_text())
    wanted = str(Path(script_path))
    def walk(value):
        if isinstance(value, dict):
            tool = value.get("tool_call", {})
            args = tool.get("arguments", {}) if isinstance(tool, dict) else {}
            if (tool.get("function_name") == "write" and args.get("path") and
                    str(Path(args["path"])) == wanted and isinstance(args.get("content"), str)):
                return args
            for child in value.values():
                found = walk(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = walk(child)
                if found:
                    return found
        return None
    args = walk(recipe)
    if args:
        return args["content"], str(recipe_path.relative_to(REPO_ROOT)), args
    return None


def resolve_runtime_script_source(script_path, config, scene, cwd=None, recipe_writes=None):
    """Resolve a script through the actual Docker/runner install or seed path.

    Source snapshots are deliberately not consulted: prepare_environment only
    exposes them as data context and Skill links always target /opt/document-bench.
    Recipe writes take precedence over the seed because they happen after reset.
    """
    if not script_path:
        return None, {"evidence_grade": "unresolved", "reason": "script path unresolved"}
    if not config:
        config = "opm-n1" if scene == "pdf" else "tlc" if scene == "xlsx" else None
    path = Path(script_path)
    runtime = str(path)
    written = ((recipe_writes[runtime], "injected/frozen recipe write", {"path": runtime})
               if recipe_writes and runtime in recipe_writes else
               _recipe_written_script(runtime, config, scene))
    if written:
        content, recipe_rel, args = written
        return f"recipe-written:{Path(runtime).name}", {"origin": "recipe-written", "evidence_grade": "reconstructed_from_frozen_recipe_write",
                      "recipe": recipe_rel, "recipe_write_path": runtime,
                      "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                      "runtime_hash_recorded": False}

    installed_prefixes = [("/root/.openclaw/skills/pdf/", "legacy/document-oe/skills/pdf/"),
                          ("/root/.openclaw/skills/xlsx/", "legacy/document-oe/skills/xlsx/"),
                          ("/opt/document-bench/", "legacy/document-oe/")]
    for prefix, repo_prefix in installed_prefixes:
        if runtime.startswith(prefix):
            rel = repo_prefix + runtime.removeprefix(prefix)
            source = REPO_ROOT / rel
            return (rel if source.is_file() else None), {
                "origin": "docker-installed-legacy", "evidence_grade": "reconstructed_from_docker_copy_and_runner_link",
                "runtime_path": runtime, "repository_path": rel,
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None,
                "runtime_hash_recorded": False,
                "chain": ["runtime/Dockerfile COPY legacy/document-oe/ /opt/document-bench/",
                          "runner _ensure_skills links /root/.openclaw/skills to /opt/document-bench/skills"]}

    workspaces = {"pdf": "/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01",
                  "xlsx": "/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01"}
    workspace = workspaces.get(scene)
    if workspace:
        try:
            rel = path.relative_to(workspace).as_posix()
        except ValueError:
            rel = None
        if rel is None and cwd and str(Path(cwd)) == workspace and not path.is_absolute():
            rel = path.as_posix()
        if rel:
            if config in ("opm-n1", "opm-n10", "tlc"):
                suite = "pdf" if scene == "pdf" else "xlsx"
                seed_rel = f"legacy/document-oe/{suite}/{rel}"
                seed_description = f"DATASETS old workload seed=/opt/document-bench/{suite}; reset_workspace copies seed to {workspace}"
            else:
                case = config.removesuffix("-n1").removesuffix("-n10") if config else ""
                seed_rel = f"compatibility/cases/{case}/seed/{rel}"
                seed_description = f"DATASETS seed=compatibility/cases/{case}/seed; reset_workspace copies seed to {workspace}"
            source = REPO_ROOT / seed_rel
            return (seed_rel if source.is_file() else None), {
                "origin": "runner-seed-copy", "evidence_grade": "reconstructed_from_dataset_seed_and_workspace_reset",
                "runtime_path": runtime, "repository_path": seed_rel,
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None,
                "runtime_hash_recorded": False, "chain": [seed_description]}
    return None, {"origin": "unresolved", "evidence_grade": "candidate_or_unknown",
                  "runtime_path": runtime,
                  "reason": "runtime path is outside installed legacy roots and runner seed workspace"}


def _slice_by_script_path(script_path, scene, cwd=None, config=None, recipe_writes=None):
    """Map actual runtime script path via install, seed copy, or recipe write."""
    if not script_path:
        return None, {"reason": "script path unresolved because cwd is unknown"}
    path = str(Path(script_path) if Path(script_path).is_absolute() else Path(cwd or ".") / script_path)
    rel, source = resolve_runtime_script_source(path, config, scene, cwd, recipe_writes)
    if rel is None:
        return None, source
    catalog = json.loads((ROOT / "legacy" / "slice-source-hashes.json").read_text())
    for sid, item in catalog.items():
        if (item["frozen_source_path"] != rel and
                not (str(rel).startswith("recipe-written:") and
                     Path(item["frozen_source_path"]).name == str(rel).removeprefix("recipe-written:"))):
            continue
        expected = item["frozen_source_sha256"]
        actual = source.get("source_sha256", source.get("content_sha256"))
        if actual == expected:
            return sid, {**source, "source_path": rel,
                          "frozen_source_sha256": expected,
                          "repository_source_sha256": actual,
                          "repository_source_hash_verified": True,
                          "runtime_hash_recorded": False,
                          "reason": None}
        return None, {**source, "source_path": rel, "frozen_source_sha256": expected,
                      "repository_source_sha256": actual,
                      "repository_source_hash_verified": False,
                      "reason": "resolved runtime source content differs from frozen slice source"}
    return None, {**source, "source_path": rel,
                  "reason": "resolved runtime source is not an old selected-slice file"}


def match_legacy_slices(cmdline, scene, cwd=None, ancestor_cmdlines=None, config=None):
    """Match script operands by resolved path; only defined child scopes inherit."""
    if not cmdline:
        return []
    matched = set()
    for inv in extract_python_invocations(cmdline, cwd):
        inv = resolve_invocation_context(inv, scene)
        sid, _ = _slice_by_script_path(inv.get("resolved_script"), scene, inv.get("cwd"), config)
        if sid == "PDF-S3" and ("/filled/" in inv["segment"] or "applicant_" in inv["segment"]):
            sid = "PDF-S5"
        if sid:
            matched.add(sid)
    descendant_scopes = {"PDF-S3", "PDF-S5", "X-S3", "X-S4"}
    for parent in ancestor_cmdlines or []:
        for inv in extract_python_invocations(parent):
            inv = resolve_invocation_context(inv, scene)
            sid, _ = _slice_by_script_path(inv.get("resolved_script"), scene, inv.get("cwd"), config)
            if sid == "PDF-S3" and ("/filled/" in inv["segment"] or "applicant_" in inv["segment"]):
                sid = "PDF-S5"
            if sid in descendant_scopes:
                matched.add(sid)
    return sorted(matched)


def legacy_match_evidence(cmdline, scene, cwd=None, ancestor_cmdlines=None, config=None):
    """Explain script-source matches without presenting reconstructed hashes as runtime hashes."""
    evidence = []
    rows = [(cmdline, cwd, "direct-process")]
    descendant_scopes = {"PDF-S3", "PDF-S5", "X-S3", "X-S4"}
    for parent in ancestor_cmdlines or []:
        rows.append((parent, None, "ancestor-process"))
    for command, command_cwd, relation in rows:
        for inv in extract_python_invocations(command, command_cwd):
            inv = resolve_invocation_context(inv, scene)
            sid, source = _slice_by_script_path(inv.get("resolved_script"), scene, inv.get("cwd"), config)
            if not sid:
                continue
            if sid == "PDF-S3" and ("/filled/" in inv["segment"] or "applicant_" in inv["segment"]):
                sid = "PDF-S5"
            descendant = relation == "ancestor-process"
            if descendant and sid not in descendant_scopes:
                continue
            if sid in ("PDF-S3", "PDF-S5"):
                args = inv["segment"]
                template = "template" in args or "blank" in args
                filled = "filled" in args or "applicant_" in args
                if (sid == "PDF-S3" and not template) or (sid == "PDF-S5" and not filled):
                    continue
            evidence.append({"slice_id": sid, "script_argument": inv["script_argument"],
                             "resolved_script": inv["resolved_script"], "cwd": inv["cwd"],
                             "relation": relation, "scope_includes_descendant": descendant,
                             "evidence_grade": source.get("evidence_grade", "runtime source chain unresolved"),
                             "source": {**source, "cwd_resolution": inv.get("cwd_resolution")},
                             "command": command})
    return evidence


def cwd_from_identity_chain(identity_cmdlines):
    """Find cwd established by the nearest recorded parent shell invocation."""
    return cwd_from_identity_chain_evidence(identity_cmdlines)[0]


def cwd_from_identity_chain_evidence(identity_cmdlines):
    """Return a cwd plus the timestamped parent argv that established it."""
    for command in (identity_cmdlines or [])[1:]:
        invs = extract_python_invocations(command)
        for inv in invs:
            if inv.get("cwd"):
                return inv["cwd"], command
    return None, None


def legacy_process_scope_index(identity_path, scene, config):
    """Build per-PID source evidence from timestamped identity and ppid records.

    Descendants are included only for old slice definitions that explicitly
    contain children/threads. X-S3 also includes its atomic wrapper only when
    the wrapper is the recorded parent of a source-matched enhancer child.
    """
    if not identity_path.is_file():
        return {}, {}, {}
    events = [json.loads(line) for line in identity_path.read_text().splitlines() if line.strip()]
    by_pid = {}
    for ev in events:
        row = by_pid.setdefault(ev["pid"], {"ppid": ev.get("ppid"), "cmdline": ev.get("cmdline", ""),
                                             "first_t_ns": ev.get("t_ns"), "last_t_ns": ev.get("t_ns")})
        row["cmdline"] = ev.get("cmdline", row["cmdline"])
        row["ppid"] = ev.get("ppid", row["ppid"])
        row["first_t_ns"] = min(row["first_t_ns"], ev.get("t_ns", row["first_t_ns"]))
        row["last_t_ns"] = max(row["last_t_ns"], ev.get("t_ns", row["last_t_ns"]))
    children = defaultdict(set)
    for pid, row in by_pid.items():
        if row.get("ppid") in by_pid:
            children[row["ppid"]].add(pid)

    def ancestry(pid):
        out, seen = [], {pid}
        parent = by_pid.get(pid, {}).get("ppid")
        while parent in by_pid and parent not in seen:
            seen.add(parent)
            out.append(by_pid[parent]["cmdline"])
            parent = by_pid[parent].get("ppid")
        return out

    direct, candidates = {}, {}
    for pid, row in by_pid.items():
        cmd = row["cmdline"]
        parents = ancestry(pid)
        cwd, cwd_source_command = cwd_from_identity_chain_evidence([cmd] + parents)
        evs = legacy_match_evidence(cmd, scene, cwd, parents, config)
        for ev in evs:
            ev.update({"process_pid": pid, "process_ppid": row.get("ppid"),
                       "identity_first_t_ns": row.get("first_t_ns"),
                       "identity_last_t_ns": row.get("last_t_ns")})
            if cwd_source_command:
                ev["cwd_resolution"] = {"evidence_grade": "cwd recovered from timestamped parent shell argv",
                                         "cwd": cwd, "source_command": cwd_source_command,
                                         "cwd_was_directly_recorded": False}
        if evs:
            direct[pid] = evs
        cand = legacy_script_candidates(cmd, scene, cwd, parents, config)
        for ev in cand:
            ev.update({"process_pid": pid, "process_ppid": row.get("ppid"),
                       "identity_first_t_ns": row.get("first_t_ns"),
                       "identity_last_t_ns": row.get("last_t_ns")})
        if cand:
            candidates[pid] = cand

    scoped = {pid: list(evs) for pid, evs in direct.items()}
    descendant_ids = {"PDF-S3", "PDF-S5", "X-S3", "X-S4"}
    for source_pid, evs in direct.items():
        allowed = {e["slice_id"] for e in evs} & descendant_ids
        if not allowed:
            continue
        queue = list(children.get(source_pid, ()))
        seen = set()
        while queue:
            pid = queue.pop()
            if pid in seen:
                continue
            seen.add(pid)
            for sid in allowed:
                scoped.setdefault(pid, []).append({"slice_id": sid,
                    "relation": "descendant process via timestamped ppid chain",
                    "evidence_grade": "direct process identity/ppid; slice definition includes subtree",
                    "process_pid": pid, "process_ppid": by_pid[pid].get("ppid"),
                    "identity_first_t_ns": by_pid[pid].get("first_t_ns"),
                    "identity_last_t_ns": by_pid[pid].get("last_t_ns"),
                    "scope_parent_pid": source_pid,
                    "command": by_pid[pid]["cmdline"],
                    "source": {"source_sha256": None, "source_hash_verified": False,
                               "reason": "child inherits selected process scope; its own source is separate"}})
            queue.extend(children.get(pid, ()))

    # The frozen X-S3 process_scope is a helper window. Attribute its atomic
    # wrapper only after the child code source has been independently mapped.
    for child_pid, evs in direct.items():
        if not any(e["slice_id"] == "X-S3" for e in evs):
            continue
        parent_pid = by_pid.get(child_pid, {}).get("ppid")
        if parent_pid not in by_pid:
            continue
        parent_cmd = by_pid[parent_pid]["cmdline"]
        if "run_xlsx_helper_atomic.py" in parent_cmd and parent_cmd in {x["cmdline"] for x in events}:
            scoped.setdefault(parent_pid, []).append({"slice_id": "X-S3",
                "relation": "atomic helper parent of source-matched enhancer child",
                "evidence_grade": "timestamped ppid relation plus source-matched child",
                "process_pid": parent_pid, "process_ppid": by_pid[parent_pid].get("ppid"),
                "identity_first_t_ns": by_pid[parent_pid].get("first_t_ns"),
                "identity_last_t_ns": by_pid[parent_pid].get("last_t_ns"),
                "scope_child_pid": child_pid,
                "command": parent_cmd,
                "source": {"source_sha256": None, "source_hash_verified": False,
                           "reason": "wrapper belongs to frozen full helper window; not the enhancer source itself"}})
    return scoped, direct, candidates


def legacy_script_candidates(cmdline, scene, cwd=None, ancestor_cmdlines=None, config=None):
    """Collect script-operand candidates (including explicit rejection reasons)."""
    rows = [(cmdline, cwd)] + [(x, None) for x in (ancestor_cmdlines or [])]
    candidates = []
    allowed = {sid: names for sid, names in LEGACY_SCRIPT_TOKENS.items()
               if sid.startswith("PDF-") == (scene == "pdf")}
    for command, row_cwd in rows:
        for inv in extract_python_invocations(command, row_cwd):
            inv = resolve_invocation_context(inv, scene)
            base = Path(inv["script_argument"]).name
            for sid, names in allowed.items():
                if base not in {Path(n.split(" ")[0]).name for n in names}:
                    continue
                effective_sid = sid
                if sid in ("PDF-S3", "PDF-S5"):
                    args_text = inv["segment"].lower()
                    effective_sid = "PDF-S5" if ("filled" in args_text or "applicant_" in args_text) else "PDF-S3"
                mapped, source = _slice_by_script_path(inv.get("resolved_script"), scene,
                                                       inv.get("cwd"), config)
                if mapped in ("PDF-S3", "PDF-S5"):
                    args_text = inv["segment"].lower()
                    mapped = "PDF-S5" if ("filled" in args_text or "applicant_" in args_text) else "PDF-S3"
                if mapped == effective_sid:
                    continue
                candidates.append({"slice_id": effective_sid, "script_argument": inv["script_argument"],
                                   "resolved_script": inv.get("resolved_script"),
                                   "cwd": inv.get("cwd"), "command": command,
                                   "cwd_resolution": inv.get("cwd_resolution"),
                                   "source": source,
                                   "evidence_grade": ("resolved runtime source content differs from frozen slice"
                                     if source.get("reason", "").startswith("resolved runtime source content") else
                                     "script operand candidate; runtime source chain not established"),
                                   "reason": source.get("reason", "script operand does not resolve to frozen source")})
    return candidates

COVERED_MECHS = {
    "M-XLSX-LOAD", "M-XLSX-SAVE", "M-XLSX-TRAVERSE", "M-LO-RECALC",
    "M-PDF-QPDF-PARSE", "M-PDF-FORMFILL", "M-POPPLER-RASTER", "M-PILLOW-IMG",
}


def coverage_partition(records=None, *, mechanism_period=None, direct_period=0,
                       intersection_period=0, total_period=None):
    """Disjoint native-period bins and path/mechanism set intersection/union."""
    if mechanism_period is not None:
        mech_period = Counter(mechanism_period)
        total = total_period if total_period is not None else sum(mech_period.values())
        direct = direct_period
        intersection = intersection_period
        mechanism = sum(p for m, p in mech_period.items() if m in COVERED_MECHS)
    else:
        total = 0
        mech_period = Counter()
        direct = mechanism = intersection = 0
        for r in records or ():
            p, m = r["period"], r["mechanism"]
            total += p
            mech_period[m] += p
            mechanism += p if m in COVERED_MECHS else 0
            direct += p if r["direct_path"] else 0
            intersection += p if r["direct_path"] and m in COVERED_MECHS else 0
    union = direct + mechanism - intersection
    if total and sum(mech_period.values()) != total:
        raise ValueError("mechanism bins do not conserve sample period")
    return {"total_period": total, "mechanism_period": mech_period,
            "direct_period": direct, "mechanism_covered_period": mechanism,
            "intersection_period": intersection, "union_period": union,
            "path_only_period": direct - intersection,
            "mechanism_only_period": mechanism - intersection}


@lru_cache(maxsize=4096)
def dso_class(dso):
    base = dso.split("/")[-1]
    for pattern, cls in DSO_CLASS_RULES:
        if re.search(pattern, base):
            return cls
    if dso == "[unknown]":
        return "unknown"
    return "other"


STACK_PREFIX_RULES = {"version": "stack-prefix-v1", "depth": 8, "minimum_depth": 4,
                      "normalization": "symbol name without +offset/address; DSO reduced to dso_class; inline DSO resolved by same-address entity frame",
                      "quality_filter": "eligible only with >=4 frames and no unknown symbol/DSO frame",
                      "limitations": ["prefix is truncated at eight frames", "DSO classes merge distinct libraries",
                                      "unknown or short prefixes are retained as weak diagnostics but excluded from matching"]}


def stack_prefix_fingerprint(stack, *, depth=8, minimum_depth=4):
    """Canonical bounded stack prefix plus evidence quality; never code identity."""
    frames = list(stack or [])[:depth]
    tokens = []
    has_unknown = False
    for i, frame in enumerate(frames):
        symbol = str(frame.get("symbol", "")).split("+", 1)[0].strip()
        dso = str(frame.get("dso", ""))
        cls = dso_class(dso)
        if frame.get("inline") or dso == "inlined":
            address = frame.get("address")
            owner = next((x for x in (stack or [])
                          if x.get("address") == address and
                          x.get("dso") not in (None, "", "inlined", "[unknown]") and not x.get("inline")), None)
            if owner:
                cls = dso_class(owner.get("dso", ""))
            else:
                # An unresolved inline frame is not a resolved "other" DSO.
                # Keep it weak unless a same-address entity frame supplies ownership.
                cls = "unknown"
        elif dso in ("", "[unknown]"):
            cls = "unknown"
        if symbol in UNKNOWN_SYMBOLS or not symbol or cls == "unknown":
            has_unknown = True
        tokens.append({"symbol": symbol or "[unknown]", "dso_class": cls})
    quality = "strong"
    reasons = []
    if len(tokens) < minimum_depth:
        quality = "weak-short-stack"
        reasons.append(f"only {len(tokens)} frames; minimum is {minimum_depth}")
    if has_unknown:
        quality = "weak-unknown-frame"
        reasons.append("unknown symbol or DSO in prefix")
    value = json.dumps(tokens, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return {"fingerprint": value, "status": quality, "depth_used": len(tokens),
            "configured_depth": depth, "minimum_depth": minimum_depth,
            "normalization": STACK_PREFIX_RULES["normalization"],
            "dso_class_mapping": "DSO_CLASS_RULES; inline owner from same instruction address" if frames else None,
            "quality_reasons": reasons}


def parse_strace_summary(text):
    """Parse `strace -c` by semantic columns; exclude total/header rows."""
    rows = []
    total_row = None
    for line in text.splitlines():
        cols = line.split()
        if len(cols) < 5:
            continue
        try:
            pct = float(cols[0])
            seconds = float(cols[1])
            usecs = float(cols[2])
        except ValueError:
            continue
        if cols[3].replace(",", "").isdigit():
            calls_idx = 3
            calls = int(cols[calls_idx].replace(",", ""))
            has_errors = len(cols) >= 6 and cols[4].replace(",", "").isdigit()
            errors = int(cols[4].replace(",", "")) if has_errors else None
            syscall = cols[5] if has_errors else cols[4]
        else:
            continue
        row = {"percent_time": pct, "seconds": seconds, "usecs_per_call": usecs,
               "calls": calls, "errors": errors, "syscall": syscall}
        if syscall == "total":
            total_row = row
        else:
            rows.append(row)
    call_sum = sum(x["calls"] for x in rows)
    seconds_sum = sum(x["seconds"] for x in rows)
    futex = next((r for r in rows if r["syscall"] == "futex"), None)
    calls_ranked = sorted(rows, key=lambda x: (-x["calls"], x["syscall"]))
    time_ranked = sorted(rows, key=lambda x: (-x["seconds"], x["syscall"]))
    denom_time = total_row["seconds"] if total_row else seconds_sum
    return {"rows": rows, "total_row": total_row, "calls_sum": call_sum,
            "seconds_sum": seconds_sum,
            "calls_total_matches": total_row is None or call_sum == total_row["calls"],
            "seconds_total_delta": None if total_row is None else seconds_sum - total_row["seconds"],
            "calls_ranked": calls_ranked, "time_ranked": time_ranked,
            "total_calls": total_row["calls"] if total_row else call_sum,
            "futex": futex,
            "futex_call_share": next((r["calls"] / call_sum for r in rows if r["syscall"] == "futex"), None),
            "futex_time_share": next((r["seconds"] / denom_time for r in rows if r["syscall"] == "futex"), None),
            "process_attribution": "insufficient: aggregate strace -c output has no per-process attribution"}


def parse_perf_stat_csv(text):
    """Read perf stat CSV where hardware-event unit fields are intentionally empty."""
    events = {}
    for row in csv.reader(text.splitlines()):
        if len(row) < 3:
            continue
        value, unit, event = (x.strip() for x in row[:3])
        if not event:
            continue
        if value in ("<not supported>", "<not counted>"):
            events[event] = {"status": value.strip("<>").replace(" ", "_"), "value": None,
                             "unit": unit, "runtime": row[3].strip() if len(row)>3 else "",
                             "percentage": row[4].strip() if len(row)>4 else ""}
            continue
        try:
            events[event] = {"status": "valid", "value": float(value), "unit": unit,
                             "runtime": row[3].strip() if len(row)>3 else "",
                             "percentage": row[4].strip() if len(row)>4 else ""}
        except ValueError:
            continue
    return events


MECHANISM_RULES_VERSION = "native-mechanisms-v3-leaf-context-separated"
UNKNOWN_SYMBOLS = {"[unknown]", "[unknown symbol]", "??", "unknown", ""}


@lru_cache(maxsize=8192)
def _libpython_leaf_mechanism(symbol):
    """Classify only the named function; never search caller frames here."""
    name = str(symbol or "").split("+", 1)[0].strip()
    rules = [
        (r"^(?:_Py)?GC_(?:Collect|CollectNoFail|Merge|Clear|Untrack|Track|Head|Visit|Traverse|Update|UntrackObject|TrackObject).*|^_PyGCHead_.*|^deduce_unreachable$|^update_refs$|^collect_generations$",
         "M-PY-GC", "GC function name"),
        (r"^(?:_Py)?(?:INCREF|DECREF)(?:_.*)?$|^Py_(?:X?INCREF|X?DECREF)$|^_Py_Dealloc$|^newreference$|^forgetreference$",
         "M-PY-REFCOUNT", "reference-counting function name"),
        (r"^(?:pymalloc|obmalloc|_PyObject_(?:Malloc|Calloc|Realloc|ArenaAlloc)|PyObject_(?:Malloc|Calloc)|PyMem_(?:Malloc|Calloc|Realloc)|gc_alloc)(?:_.*)?$|^(?:arena_alloc|_PyObject_GC_New)$",
         "M-PY-ALLOC", "allocation function name"),
        (r"^(?:list_|tuple_|dict_|set_|frozenset_|PyDict_|PyList_|PyTuple_|PySet_|_PyDict_|_PyList_|_PyTuple_|_PySet_).+|^list_sort_impl$|^list_sort$",
         "M-PY-CONTAINER", "container function name"),
        (r"^(?:_?PyType_|PyType_|type_.*|.*TypeCheck|.*IsSubtype|.*IsInstance).*$",
         "M-PY-TYPECHECK", "type-check function name"),
        (r"^(?:_?PyEval_.*|_PyFunction_Vectorcall|_PyObject_Vectorcall.*|PyObject_Call.*|pyobject_call|run_eval_code|PyRun_.*|run_mod)$",
         "M-PY-INTERPRETER", "interpreter/call-dispatch function name"),
    ]
    for pattern, mechanism, label in rules:
        if re.match(pattern, name, re.I):
            return mechanism, label
    return None, None


def _context_mechanisms(stack, dso_cls):
    contexts = []
    for index, frame in enumerate((stack or [])[1:], start=1):
        symbol = str(frame.get("symbol", ""))
        frame_dso = str(frame.get("dso", ""))
        cls = dso_class(frame_dso)
        if frame.get("inline") or frame_dso == "inlined":
            address = frame.get("address")
            owner = next((dso_class(x.get("dso", "")) for x in (stack or [])
                          if x.get("address") == address and
                          x.get("dso") not in (None, "", "inlined", "[unknown]") and not x.get("inline")), None)
            if owner:
                cls = owner
        mechanism, why = _libpython_leaf_mechanism(symbol) if cls == "libpython" else (None, None)
        if cls == "zlib":
            if re.match(r"^(?:deflate|compress|longest_match|fill_window|deflate_slow)", symbol, re.I):
                mechanism, why = "M-ZIP-COMPRESS", "zlib caller function name"
            elif re.match(r"^(?:inflate|uncompress)", symbol, re.I):
                mechanism, why = "M-ZIP-DECOMPRESS", "zlib caller function name"
        if mechanism:
            contexts.append({"frame_index": index, "stack_depth": len(stack or []),
                             "symbol": symbol, "dso_class": cls,
                             "context_mechanism": mechanism,
                             "evidence": why, "confidence": "contextual"})
    return contexts


def legacy_context_sensitive_mechanism(dso_cls, leaf_sym, stack=None):
    """Reproduce the former joined-stack heuristic solely for impact auditing."""
    names = [str(leaf_sym or "")] + [str(f.get("symbol", "")) for f in (stack or [])[1:]]
    joined = " ".join(names)
    if dso_cls == "libpython":
        rules = [
            (r"(?:_py)?gc_|\bgc_|_pygchead|deduce_unreachable|update_refs|collect_generations", "M-PY-GC"),
            (r"py_(?:inc|dec)ref|_py_(?:inc|dec)ref|\bpy_x?(?:inc|dec)ref|_py_dealloc|newreference|forgetreference", "M-PY-REFCOUNT"),
            (r"pymalloc|obmalloc|(?:malloc|calloc|realloc|free)|arena_|pyobject_(?:new|malloc|calloc)|pymem_", "M-PY-ALLOC"),
            (r"dict|list|tuple|set|sequence|mapping|frozenset", "M-PY-CONTAINER"),
            (r"pytype|typecheck|issubtype|isinstance|check_subtype", "M-PY-TYPECHECK"),
            (r"pyeval|evalframe|vectorcall|pyobject_call|pyfunction_call|run_eval_code|pyrun_|run_mod", "M-PY-INTERPRETER"),
        ]
        for pattern, mechanism in rules:
            if re.search(pattern, joined, re.I):
                return mechanism
        return "M-PY-RUNTIME-OTHER"
    if dso_cls == "zlib":
        if re.search(r"deflate|compress|longest_match|fill_window|deflate_slow", joined, re.I):
            return "M-ZIP-COMPRESS"
        if re.search(r"inflate|uncompress", joined, re.I):
            return "M-ZIP-DECOMPRESS"
        return "M-ZIP-OPERATION-UNSPECIFIED"
    return None


def classify_native_mechanism(role, dso_cls, leaf_sym, stack=None):
    """Return a leaf-only sampling-point mechanism plus separate stack contexts."""
    stack = stack or []
    leaf = str(leaf_sym or "")
    result = {"mechanism": "M-UNCLASSIFIED", "evidence": "unresolved",
              "native_status": "unclassified", "upper_operation": "unknown",
              "upper_operation_evidence": "no Python-level business frame in perf stack",
              "confidence": "low", "context_mechanisms": [],
              "context_conflict": False, "classification_basis": "leaf function + leaf DSO"}
    result["context_mechanisms"] = _context_mechanisms(stack, dso_cls)
    if dso_cls == "unknown":
        result.update(evidence="unknown-dso", native_status="unknown-dso")
        return result
    if leaf in UNKNOWN_SYMBOLS:
        result.update(evidence="unknown-symbol", native_status="unknown-symbol")
        return result
    if len(stack) < 2 and dso_cls in ("libpython", "libc", "python-ext"):
        result.update(evidence="insufficient-stack", native_status="insufficient-stack")
        return result

    if dso_cls == "libpython":
        mechanism, label = _libpython_leaf_mechanism(leaf)
        if mechanism:
            result.update(mechanism=mechanism, evidence=f"leaf {label}",
                          native_status="known-native-mechanism", confidence="high")
            result["context_conflict"] = bool(any(x["context_mechanism"] != mechanism
                                                   for x in result["context_mechanisms"]))
            return result
        result.update(mechanism="M-PY-RUNTIME-OTHER", evidence="resolved libpython symbol without narrower rule",
                      native_status="known-runtime-operation-unspecified", confidence="low")
        return result
    if dso_cls in ("expat-xml", "elementtree-xml", "libxml2"):
        result.update(mechanism="M-XML-PARSE", evidence=f"leaf DSO class {dso_cls} with resolved symbol",
                      native_status="known-native-mechanism", confidence="high")
        return result
    if dso_cls == "zlib":
        if re.match(r"^(?:deflate|compress|longest_match|fill_window|deflate_slow)", leaf, re.I):
            name = "M-ZIP-COMPRESS"
        elif re.match(r"^(?:inflate|uncompress)", leaf, re.I):
            name = "M-ZIP-DECOMPRESS"
        else:
            name = "M-ZIP-OPERATION-UNSPECIFIED"
        result.update(mechanism=name, evidence="resolved zlib leaf function; direction only split with leaf evidence",
                      native_status="known-native-mechanism", confidence="high" if name != "M-ZIP-OPERATION-UNSPECIFIED" else "medium")
        result["context_conflict"] = bool(any(x["context_mechanism"] != name
                                               for x in result["context_mechanisms"]))
        return result
    if dso_cls == "pillow":
        result.update(mechanism="M-IMAGE-PROCESS", evidence="resolved Pillow native extension symbol",
                      native_status="known-native-mechanism", confidence="medium")
        return result
    if dso_cls in ("poppler", "freetype", "fontconfig"):
        is_raster = role in ("pdftoppm", "pdfinfo") or bool(re.search(r"splash|raster", leaf, re.I))
        result.update(mechanism="M-PDF-RASTER" if is_raster else "M-PDF-NATIVE-OTHER",
                      evidence="Poppler/font native symbol plus process/stack context",
                      native_status="known-native-mechanism", confidence="medium")
        if is_raster:
            result.update(upper_operation="PDF rasterization",
                          upper_operation_evidence="Poppler DSO in pdftoppm/pdfinfo process")
        return result
    if dso_cls == "libreoffice":
        result.update(mechanism="M-LIBREOFFICE-NATIVE", evidence="resolved LibreOffice DSO symbol",
                      native_status="known-native-mechanism", confidence="medium")
        if re.search(r"formula|interpret|sc.*recalc|calculate", leaf, re.I):
            result.update(upper_operation="spreadsheet recalculation",
                          upper_operation_evidence="LibreOffice formula/recalc symbol in stack", confidence="high")
        return result
    if dso_cls == "libc" and re.search(r"memcpy|memmove|memcmp|strcmp|strlen|malloc|free", leaf, re.I):
        result.update(mechanism="M-LIBC-PRIMITIVE", evidence="resolved libc primitive symbol",
                      native_status="known-native-mechanism", confidence="medium")
        return result
    if dso_cls == "python-ext":
        result.update(mechanism="M-PYTHON-EXTENSION-OTHER", evidence="resolved compiled Python extension symbol",
                      native_status="known-extension-native-work", confidence="low")
        return result
    result.update(mechanism="M-NATIVE-OTHER-UNSPECIFIED",
                  evidence=f"resolved symbol in DSO class {dso_cls}; no narrower rule",
                  native_status="known-dso-mechanism-unspecified", confidence="low")
    return result


def role_mechanism(role, dso_cls, leaf_sym):
    """Backward-compatible tuple interface for tests and report callers."""
    x = classify_native_mechanism(role, dso_cls, leaf_sym)
    return x["mechanism"], x["evidence"]


def load_native(config, rep):
    path = RAW / config / rep / "out" / "samples.jsonl"
    if not path.is_file():
        return None
    samples = []
    with open(path) as fh:
        for line in fh:
            samples.append(json.loads(line))
    return samples


def iter_native(path):
    with open(path) as fh:
        for line in fh:
            yield json.loads(line)


def load_pyspy_data(config):
    path = RAW / config / "pyspy" / "out" / "pyspy-roles.json"
    if not path.is_file():
        return None
    return json.load(open(path))


def monitor_cpu_shares(config, rep):
    """Sampling-independent cross-check: per-role CPU milliseconds from the
    monitor's thread utime+stime deltas, restricted to the ROI window."""
    mon = RAW / config / rep / "out" / "monitor"
    roi_path = RAW / config / rep / "out" / "roi.json"
    ident_path = mon / "identity.jsonl"
    if not (mon / "monitor.jsonl").is_file() or not roi_path.is_file():
        return None
    roi = json.load(open(roi_path))
    t_roi_mono = roi["loop_start_mono_s"]
    # pid -> latest identity before/at each poll (simplified: last identity)
    pid_cmd = {}
    for line in open(ident_path):
        ev = json.loads(line)
        pid_cmd[ev["pid"]] = ev["cmdline"]
    # exclude measurement overhead processes (perf userspace, collector, pipes)
    def _is_overhead(cmd):
        return (cmd.startswith("perf") or "collect_native" in cmd
                or "tstamp_pipe" in cmd or "monitor_procs" in cmd
                or "run_collection" in cmd)
    prev = {}
    role_ms = Counter()
    total_ms = 0.0
    for line in open(mon / "monitor.jsonl"):
        rec = json.loads(line)
        t = rec["t_ns"] / 1e9
        cur = {th[1]: (th[0], th[3] + th[4]) for th in rec["threads"]}
        if t >= t_roi_mono:
            for tid, (pid, total) in cur.items():
                if tid in prev and total > prev[tid][1]:
                    delta_ms = (total - prev[tid][1]) * 10.0
                    cmd = pid_cmd.get(pid, "")
                    if not _is_overhead(cmd):
                        role = _role_from_cmdline(cmd, rec, pid) or f"pid{pid}"
                        role_ms[role] += delta_ms
                        total_ms += delta_ms
        prev.update(cur)
    if not total_ms:
        return None
    return {r: ms / total_ms for r, ms in role_ms.most_common() if ms / total_ms > 0.0005}


def _role_from_cmdline(cmd, rec, pid):
    scene = _CURRENT_SCENE.get("scene")
    if not cmd:
        # comm-based lookup for the poll record
        for p in rec["procs"]:
            if p["pid"] == pid:
                comm = p["comm"]
                if comm in ("pdftoppm", "pdfinfo", "soffice.bin"):
                    return comm
                if comm == "bash" or comm == "sh":
                    return "bash"
                return None
        return None
    return script_role(cmd, scene) if scene else None


_CURRENT_SCENE = {}


def script_role(cmd, scene):
    pdf = scene == "pdf"
    import re as _re
    if _re.search(r"run_document_scene_loop\.py", cmd):
        return "runner"
    if _re.search(r"check_fillable_fields\.py", cmd):
        return "pdf-check-fillable"
    if _re.search(r"extract_form_field_info\.py", cmd):
        return "pdf-extract-fields"
    if _re.search(r"convert_pdf_to_images\.py", cmd):
        return "pdf-convert"
    if _re.search(r"fill_fillable_fields\.py", cmd):
        return "pdf-fill"
    if _re.search(r"verify_pdf_batch\.py", cmd):
        return "pdf-verify"
    if _re.search(r"verify_office\.py", cmd):
        return "pdf-verify" if pdf else "xlsx-verify"
    if _re.search(r"generate_and_run_batch\.py|build_field_values\.py|"
                   r"run_batch_fill_render\.py|pdf_batch\.py", cmd):
        return "pdf-mapping-driver"
    if _re.search(r"write_pdf_batch_summary\.py", cmd):
        return "pdf-summary-writer"
    if _re.search(r"summary\.py", cmd):
        return "pdf-summary-writer" if pdf else "xlsx-summary-export"
    if _re.search(r"inspect_xlsx_structure\.py", cmd):
        return "xlsx-inspect-structure"
    if _re.search(r"inspect_xlsx_features\.py", cmd):
        return "xlsx-inspect-features"
    if _re.search(r"enhance_workbook\.py|build_enhance|build_enhanced", cmd):
        return "xlsx-enhance"
    if _re.search(r"[/ ]build\.py|\.build\.runtime\.py", cmd):
        return "xlsx-enhance"
    if _re.search(r"run_xlsx_helper_atomic\.py", cmd):
        return "xlsx-atomic-helper"
    if _re.search(r"recalc\.py", cmd):
        return "xlsx-recalc"
    if _re.search(r"inspect_xlsx_formulas\.py", cmd):
        return "xlsx-inspect-formulas"
    if _re.search(r"inspect_xlsx_cached_values\.py", cmd):
        return "xlsx-inspect-cached"
    if _re.search(r"verify_xlsx_enhanced\.py", cmd):
        return "xlsx-verify"
    if _re.search(r"write_xlsx_summary\.py|export_xlsx\.py", cmd):
        return "xlsx-summary-export"
    if _re.search(r"inspect_xlsx\.py", cmd):
        return "xlsx-inspect-tool"
    if _re.search(r"\bpython3?\s+-c\b", cmd):
        return "python-inline"
    if _re.search(r"pdftoppm", cmd):
        return "pdftoppm"
    if _re.search(r"pdfinfo", cmd):
        return "pdfinfo"
    if _re.search(r"soffice\.bin", cmd):
        return "soffice.bin"
    if _re.search(r"oosplash|javaldx|jvmfwk|gpgconf|gpgsm|\bgpg\b", cmd):
        return "lo-startup"
    return "other:" + cmd.split()[0][-24:] if cmd.split() else None


def profile_config(config):
    reps = {}
    pyspy_data = {}
    plan = {c["config_id"]: c for c in
            json.load(open(ROOT / "config" / "run-plan.json"))["configs"]}
    _CURRENT_SCENE["scene"] = plan.get(config, {}).get("scene")
    try:
        pyspy_data = load_pyspy_data(config)
    except ValueError:
        pass
    for rep in ("r1", "r2"):
        sample_path = RAW / config / rep / "out" / "samples.jsonl"
        if not sample_path.is_file() or sample_path.stat().st_size == 0:
            continue
        total_period = sum(s["period"] for s in iter_native(sample_path))
        role_p = Counter(); dso_p = Counter(); role_dso = defaultdict(Counter)
        func_p = Counter(); func_stack_p = defaultdict(Counter); func_prefix_p = defaultdict(Counter)
        func_context_evidence_p = defaultdict(Counter)
        mech_p = Counter(); direct_p = 0; intersection_p = 0
        context_p = Counter(); context_conflict_p = 0
        context_pair_p = Counter(); classifier_transition_p = Counter()
        prefix_quality_period = Counter(); prefix_quality_samples = Counter()
        native_status_p = Counter(); upper_operation_p = Counter()
        native_status_upper_p = Counter()
        slice_period = Counter()
        slice_mech_period = defaultdict(Counter)
        direct_mech_period = Counter()
        slice_function_period = defaultdict(Counter)
        slice_leaf_period = defaultdict(Counter)
        function_stack_prefix_period = Counter()
        function_leaf_period = Counter()
        slice_sample_commands = defaultdict(set)
        slice_source_evidence = defaultdict(list)
        slice_candidate_evidence = defaultdict(list)
        unknown_role_p = Counter()
        unresolved_symbol_period = 0
        unresolved_symbol_samples = 0
        identity_file = RAW / config / rep / "out" / "monitor" / "identity.jsonl"
        scope_by_pid, identity_direct_by_pid, identity_candidates_by_pid = legacy_process_scope_index(
            identity_file, plan.get(config, {}).get("scene"), config)
        # Repeated samples share immutable identity/recipe context. Cache both
        # matches and empty results within this repeat, retaining the full
        # context in the key so exec/identity changes are resolved separately.
        fallback_matches = {}
        fallback_candidates = {}
        for s in iter_native(sample_path):
            w = s["period"] / total_period
            role = s["role"]
            cls = dso_class(s["leaf_dso"])
            stack = s.get("stack", [])
            result = classify_native_mechanism(role, cls, s["leaf_sym"], stack)
            prefix = stack_prefix_fingerprint(stack)
            legacy_mech = legacy_context_sensitive_mechanism(cls, s["leaf_sym"], stack)
            if s["leaf_sym"] in ("[unknown]", "[unknown symbol]", "??", "unknown", ""):
                unresolved_symbol_period += s["period"]
                unresolved_symbol_samples += 1
            s["_mech"] = result["mechanism"]
            s["_native_status"] = result["native_status"]
            s["_upper_operation"] = result["upper_operation"]
            s["_context_mechanisms"] = sorted({x["context_mechanism"] for x in result["context_mechanisms"]})
            s["_context_evidence"] = result["context_mechanisms"]
            s["_context_conflict"] = result["context_conflict"]
            s["_stack_prefix"] = prefix
            identity = s.get("identity_cmdlines", [])
            cmd = s.get("cmdline", "")
            pid = s.get("pid")
            scene = plan.get(config, {}).get("scene")
            context_key = (pid, cmd, tuple(identity))
            # Identity and ancestor parsing is process-level work, not sample-
            # level work. The monitor identity index already resolves each PID
            # once and records allowed subtree inheritance. Fall back only when
            # a sampled PID has no identity record at all.
            match_evidence = list(scope_by_pid.get(pid, []))
            if not match_evidence and (cmd or identity):
                if context_key not in fallback_matches:
                    ancestors = identity[1:] if identity and identity[0] == cmd else identity
                    fallback_matches[context_key] = legacy_match_evidence(cmd, scene, None, ancestors, config)
                match_evidence = fallback_matches[context_key]
            matched_slices = sorted({x["slice_id"] for x in match_evidence})
            candidates = list(identity_candidates_by_pid.get(pid, []))
            if not candidates and (cmd or identity):
                if context_key not in fallback_candidates:
                    ancestors = identity[1:] if identity and identity[0] == cmd else identity
                    fallback_candidates[context_key] = legacy_script_candidates(cmd, scene, None, ancestors, config)
                candidates = fallback_candidates[context_key]
            role_p[role] += s["period"]
            dso_p[cls] += s["period"]
            role_dso[role][cls] += s["period"]
            func_key = (role, cls, s.get("leaf_dso"), s["leaf_sym"],
                        s.get("entity_sym"), s.get("entity_dso"), bool(matched_slices),
                        s["_mech"], s["_upper_operation"], s["_native_status"],
                        tuple(s["_context_mechanisms"]))
            func_p[func_key] += s["period"]
            signature = prefix["fingerprint"]
            leaf_signature = json.dumps({"leaf": s["leaf_sym"], "dso_class": cls},
                                        sort_keys=True, ensure_ascii=False)
            function_leaf_period[leaf_signature] += s["period"]
            prefix_quality_period[prefix["status"]] += s["period"]
            prefix_quality_samples[prefix["status"]] += 1
            if prefix["status"] == "strong":
                func_prefix_p[func_key][signature] += s["period"]
                function_stack_prefix_period[signature] += s["period"]
            for context in s["_context_mechanisms"]:
                context_p[context] += s["period"]
            for c in s["_context_evidence"]:
                token = (c["frame_index"], c["stack_depth"], c["symbol"], c["dso_class"],
                         c["context_mechanism"], c["evidence"])
                func_context_evidence_p[func_key][token] += s["period"]
            if s["_context_conflict"]:
                context_conflict_p += s["period"]
            for context in s["_context_mechanisms"]:
                if context != s["_mech"]:
                    context_pair_p[(s["_mech"], context)] += s["period"]
            if legacy_mech is not None:
                classifier_transition_p[(legacy_mech, s["_mech"])] += s["period"]
            stack_sig = tuple(f"{f.get('symbol')} [{f.get('dso')}]" for f in s.get("stack", [])[:12])
            if stack_sig:
                stack_counts = func_stack_p[func_key]
                if stack_sig in stack_counts:
                    stack_counts[stack_sig] += s["period"]
                elif len(stack_counts) < 4:
                    stack_counts[stack_sig] = s["period"]
                else:
                    least = min(stack_counts, key=stack_counts.get)
                    if s["period"] > stack_counts[least]:
                        del stack_counts[least]
                        stack_counts[stack_sig] = s["period"]
            if role.startswith("unknown:") or role == "python-unknown-script":
                unknown_role_p[role] += s["period"]
            mech_p[s["_mech"]] += s["period"]
            native_status_p[s["_native_status"]] += s["period"]
            upper_operation_p[s["_upper_operation"]] += s["period"]
            native_status_upper_p[(s["_native_status"], s["_upper_operation"])] += s["period"]
            if matched_slices:
                direct_p += s["period"]
                direct_mech_period[s["_mech"]] += s["period"]
                for sid in matched_slices:
                    slice_period[sid] += s["period"]
                    slice_mech_period[sid][s["_mech"]] += s["period"]
                    if prefix["status"] == "strong":
                        slice_function_period[sid][signature] += s["period"]
                    slice_leaf_period[sid][leaf_signature] += s["period"]
                    slice_sample_commands[sid].add(cmd)
                    for entry in match_evidence:
                        if entry["slice_id"] == sid and len(slice_source_evidence[sid]) < 20:
                            slice_source_evidence[sid].append(entry)
            for candidate in candidates:
                sid = candidate["slice_id"]
                if len(slice_candidate_evidence[sid]) < 20:
                    slice_candidate_evidence[sid].append(candidate)
            if matched_slices and result["native_status"] == "known-native-mechanism":
                intersection_p += s["period"]
        roi = json.load(open(RAW / config / rep / "out" / "roi.json"))
        partition = coverage_partition(mechanism_period=mech_p,
                                       direct_period=direct_p,
                                       intersection_period=intersection_p,
                                       total_period=total_period)
        total_period = partition["total_period"]
        mech_p = partition["mechanism_period"]
        direct_p = partition["direct_period"]
        intersection_p = partition["intersection_period"]
        observed_commands = defaultdict(set)
        candidate_commands = defaultdict(set)
        if identity_file.is_file():
            for line in open(identity_file):
                ev = json.loads(line)
                cmdline = ev.get("cmdline", "")
                scene = plan.get(config, {}).get("scene")
                invocations = extract_python_invocations(cmdline)
                for inv in invocations:
                    inv = resolve_invocation_context(inv, plan.get(config, {}).get("scene"))
                    sid, source = _slice_by_script_path(inv.get("resolved_script"), scene,
                                                        inv.get("cwd"), config)
                    if sid in ("PDF-S3", "PDF-S5"):
                        args_text = inv["segment"].lower()
                        sid = "PDF-S5" if ("filled" in args_text or "applicant_" in args_text) else "PDF-S3"
                    if sid:
                        observed_commands[sid].add(cmdline)
                    base = Path(inv["script_argument"]).name
                    for candidate_sid, names in LEGACY_SCRIPT_TOKENS.items():
                        if candidate_sid.startswith("PDF-") != (scene == "pdf"):
                            continue
                        effective_candidate = candidate_sid
                        if candidate_sid in ("PDF-S3", "PDF-S5"):
                            args_text = inv["segment"].lower()
                            effective_candidate = "PDF-S5" if ("filled" in args_text or "applicant_" in args_text) else "PDF-S3"
                        if base in {Path(x).name for x in names} and sid != effective_candidate:
                            candidate_commands[effective_candidate].add(json.dumps({
                                "command": cmdline, "script_argument": inv["script_argument"],
                                "resolved_script": inv.get("resolved_script"),
                                "cwd": inv.get("cwd"), "cwd_resolution": inv.get("cwd_resolution"),
                                "source": source,
                                "reason": source.get("reason", "not frozen source")
                            }, ensure_ascii=False, sort_keys=True))
        slice_inventory = json.load(open(ROOT / "legacy" / "legacy-slices.json"))
        source_hashes = json.load(open(ROOT / "legacy" / "slice-source-hashes.json"))
        all_slices = slice_inventory["pdf_slices"] if plan.get(config, {}).get("scene") == "pdf" else slice_inventory["xlsx_slices"]
        slice_evidence = {}
        for sl in all_slices:
            sid = sl["slice_id"]
            slice_evidence[sid] = {
                "legacy_script": sl["script"],
                "matched_actual_commands": sorted(observed_commands.get(sid, set())),
                "candidate_argv_mentions": sorted(candidate_commands.get(sid, set())),
                "source_evidence": slice_source_evidence.get(sid, []),
                "candidate_source_evidence": slice_candidate_evidence.get(sid, []),
                "sampled_period_share": slice_period.get(sid, 0) / total_period,
                "sampled_cycles_weight": slice_period.get(sid, 0),
                "frozen_source_sha256": source_hashes.get(sid, {}).get("frozen_source_sha256"),
                "executed_file_sha256": None,
                "match_basis": "Python script operand resolved through cwd/path to frozen source; no runtime file hash claimed",
                "status": ("executed_and_sampled" if slice_period.get(sid) else
                           "executed_no_native_sample" if observed_commands.get(sid) else
                           "script_operand_candidate_source_unverified" if candidate_commands.get(sid) else
                           "no_matching_identity_command"),
                "unmatched_reason": (None if observed_commands.get(sid) else
                    "script operand basename matched but resolved path/source did not match frozen source"
                    if candidate_commands.get(sid) else
                    "no Python script operand resolved to this frozen source in timestamped identities"),
                "evidence_grade": ("direct_identity_path_reconstructed_source" if slice_period.get(sid) else
                                  "candidate_path_or_content_only" if candidate_commands.get(sid) else "no_evidence"),
                "remaining_gap": "actual executed file SHA256 absent from historical process capture",
            }
        reps[rep] = {
            "total_period": total_period,
            "roi_samples": roi["roi_samples"],
            "process_layer": {r: p / total_period for r, p in role_p.most_common()},
            "process_layer_counts": dict(role_p.most_common()),
            "library_layer": {d: p / total_period for d, p in dso_p.most_common()},
            "role_dso_layer": {r: {d: p / role_p[r] for d, p in c.most_common()}
                               for r, c in role_dso.items()},
            "function_layer": [
                {"role": k[0], "dso_class": k[1], "dso": k[2], "symbol": k[3],
                 "entity_symbol": k[4], "entity_dso": k[5],
                 "top_callstack": list(func_stack_p[k].most_common(1)[0][0]) if func_stack_p[k] else [],
                 "direct_path_matched": k[6],
                 "mechanism": k[7], "upper_operation": k[8], "native_status": k[9],
                 "context_mechanisms": list(k[10]),
                 "context_evidence_top": [
                     {"frame_index": token[0], "stack_depth": token[1], "symbol": token[2],
                      "dso_class": token[3], "context_mechanism": token[4],
                      "evidence": token[5], "period": period}
                     for token, period in func_context_evidence_p[k].most_common(8)],
                 "dominant_stack_prefix_fingerprint": func_prefix_p[k].most_common(1)[0][0]
                     if func_prefix_p[k] else None,
                 "stack_prefix_match_quality": "strong" if func_prefix_p[k] else "weak_or_unavailable",
                 "stack_prefix_fingerprint_period": dict(func_prefix_p[k]),
                 "eligible_stack_prefix_period": sum(func_prefix_p[k].values()),
                 "share_of_roi": p / total_period}
                for k, p in func_p.most_common()],
            "mechanism_layer": {m: p / total_period for m, p in mech_p.most_common()},
            "context_mechanism_layer": {m: p / total_period for m, p in context_p.most_common()},
            "context_mechanism_layer_note": "overlapping caller-context evidence; does not partition samples and must not be added to mechanism_layer",
            "leaf_context_conflict_share": context_conflict_p / total_period,
            "leaf_context_pair_share": {f"{leaf}|{context}": period / total_period
                                        for (leaf, context), period in context_pair_p.items()},
            "legacy_context_classifier_transition_share": {
                f"{old}|{new}": period / total_period
                for (old, new), period in classifier_transition_p.items()},
            "legacy_context_classifier_transition_note": "diagnostic reapplication of native-mechanisms-v2 joined-stack rule; not used for coverage or primary classification",
            "stack_prefix_fingerprint_quality": {
                "rules": STACK_PREFIX_RULES,
                "period_share": {k: v / total_period for k, v in prefix_quality_period.items()},
                "sample_count": dict(prefix_quality_samples),
                "eligible_match_period_share": prefix_quality_period.get("strong", 0) / total_period},
            "leaf_function_period": {k: v / total_period for k, v in function_leaf_period.items()},
            "native_mechanism_status_layer": {m: p / total_period for m, p in native_status_p.most_common()},
            "upper_operation_layer": {m: p / total_period for m, p in upper_operation_p.most_common()},
            "native_status_upper_operation_layer": {
                f"{status}|{op}": period / total_period
                for (status, op), period in native_status_upper_p.items()},
            "mechanism_rules_version": MECHANISM_RULES_VERSION,
            "execution_path_layer": {"direct_slice_share": direct_p / total_period,
                "matched_slice_period_shares": {sid: v / total_period for sid, v in slice_period.items()},
                "direct_mechanism_period": dict(direct_mech_period),
                "slice_mechanism_period": {sid: dict(v) for sid, v in slice_mech_period.items()},
                "slice_stack_prefix_fingerprints_top": {sid: [
                    {"signature": sig, "period": period,
                     "slice_period_share": period / slice_period[sid]}
                    for sig, period in counter.most_common(100)]
                    for sid, counter in slice_function_period.items()},
                "slice_stack_prefix_fingerprints": {sid: dict(counter)
                                               for sid, counter in slice_function_period.items()},
                "slice_leaf_function_period": {sid: dict(counter)
                                                for sid, counter in slice_leaf_period.items()},
                "stack_prefix_fingerprint_period": dict(function_stack_prefix_period),
                "leaf_function_period": dict(function_leaf_period),
                "path_and_mechanism_intersection_share": intersection_p / total_period,
                "path_match_basis": "exact script token/path in timestamp-resolved process identity; historical executed-file hashes were not captured",
                "slice_evidence": slice_evidence},
            "direct_path_share": direct_p / total_period,
            "classified_native_mechanism_share": sum(
                v for status, v in ((k, p / total_period) for k, p in native_status_p.items())
                if status in ("known-native-mechanism", "known-extension-native-work",
                              "known-runtime-operation-unspecified", "known-dso-mechanism-unspecified")),
            "inline_recovered_period_share": roi.get("perf_script_parse", {}).get("inline_recovered_period", 0) / total_period,
            "unresolved": {
                "unknown_dso": dso_p.get("unknown", 0) / total_period,
                "unknown_role": sum(unknown_role_p.values()) / total_period,
                "unclassified_mech": mech_p.get("M-UNCLASSIFIED", 0) / total_period,
                "unresolved_leaf_symbol": unresolved_symbol_period / total_period,
                "unresolved_leaf_symbol_samples": unresolved_symbol_samples,
                "empty_stack_samples": roi.get("perf_script_parse", {}).get("empty_stack_samples"),
                "inline_owner_unresolved_samples": roi.get("perf_script_parse", {}).get("inline_owner_unresolved_samples"),
                "malformed_frame_lines": roi.get("perf_script_parse", {}).get("malformed_frame_lines"),
                "unmatched_perf_sample_estimate": roi.get("perf_script_parse", {}).get("unmatched_perf_sample_estimate"),
            },
            "parallelism": json.load(open(RAW / config / rep / "out" / "parallelism.json")),
        }
        mon_shares = monitor_cpu_shares(config, rep)
        if mon_shares:
            reps[rep]["monitor_cpu_shares"] = mon_shares
        # Monitor time is retained as an independent cross-check only.
        reps[rep]["monitor_cpu_time_is_independent_crosscheck"] = True
    result = {"config_id": config, "repeats": reps}
    # py-spy python-level view
    if pyspy_data:
        result["pyspy"] = pyspy_data
    stat_dir = RAW / config / "stat"
    if (stat_dir / "stat.csv").is_file():
        stat = parse_perf_stat_csv((stat_dir / "stat.csv").read_text())
        wall = {}
        for line in open(stat_dir / "stat-wall.txt"):
            k, _, v = line.strip().partition("=")
            wall[k] = v
        if stat:
            val = lambda key: stat.get(key, {}).get("value") if isinstance(stat.get(key), dict) else None
            cu, ck = val("cycles:u"), val("cycles:k")
            iu, ik = val("instructions:u"), val("instructions:k")
            tc = val("task-clock")
            stat_out = {"cycles:u": cu, "cycles:k": ck, "task_clock_ms": tc,
                        "kernel_cycles_share": ck / (cu + ck) if cu is not None and ck is not None and cu + ck else None,
                        "user_ipc": iu / cu if iu is not None and cu is not None and cu else None,
                        "kernel_ipc": ik / ck if ik is not None and ck is not None and ck else None,
                        "events": stat, "measurement_scope": "whole perf-stat command including runner preflight"}
            try:
                stat_out["wall_seconds"] = float(wall.get("wall_seconds", "nan"))
                stat_out["avg_parallelism_taskclock"] = (tc / 1000.0 /
                                                         stat_out["wall_seconds"])
            except (ValueError, ZeroDivisionError):
                pass
            result["stat"] = stat_out
    sys_dir = RAW / config / "syscalls"
    if (sys_dir / "syscalls.txt").is_file():
        parsed = parse_strace_summary((sys_dir / "syscalls.txt").read_text())
        result["syscalls"] = parsed
    return result


def main():
    PROCESSED.mkdir(exist_ok=True)
    ap = argparse.ArgumentParser(description="Build native period profiles from existing parsed raw samples")
    ap.add_argument("configs", nargs="*", help="optional config ids to refresh; merged into all-profiles.json")
    selected = set(ap.parse_args().configs)
    plan = json.load(open(ROOT / "config" / "run-plan.json"))
    all_profiles_path = PROCESSED / "all-profiles.json"
    profiles = json.load(open(all_profiles_path)) if all_profiles_path.is_file() and selected else {}
    for cfg in plan["configs"]:
        cid = cfg["config_id"]
        if selected and cid not in selected:
            continue
        p = profile_config(cid)
        if p["repeats"]:
            profiles[cid] = p
            with open(PROCESSED / f"{cid}.json", "w") as fh:
                json.dump(p, fh, indent=2)
            print(f"profiled {cid}: repeats={list(p['repeats'])}")
    json.dump(profiles, open(all_profiles_path, "w"), indent=2)
    print(f"wrote/merged {len(profiles)} profiles")


if __name__ == "__main__":
    main()
