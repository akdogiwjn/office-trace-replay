#!/usr/bin/env python3
"""Collect one native and one independent py-spy profile per planned config.

This campaign mounts the current replay checkout and its locked runner into the
existing image. It never builds an image or modifies historical raw captures.
Each run gets a unique container and output directory; a failed mode is kept
with its logs and the same configuration is not retried.
"""
import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
if str(HERE / "scripts") not in sys.path:
    sys.path.insert(0, str(HERE / "scripts"))
from collection_quality import summarize_native_quality
PLAN_PATH = HERE / "config/current-loop-profile-plan-v1.json"
CAMPAIGN = HERE / "raw/current-loop-verifier-v1"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def workload_status(summary, requested_loops):
    """Classify the runner independently of perf export/parser outcomes."""
    if not summary:
        return 'unknown'
    if (not summary.get('interrupted', False)
            and summary.get('requested_iterations') == requested_loops
            and summary.get('completed_iterations') == requested_loops
            and summary.get('successes') == requested_loops
            and summary.get('failures') == 0):
        return 'success'
    if summary.get('failures', 0) or summary.get('successes', 0) < requested_loops:
        return 'failed'
    return 'incomplete'


def native_profile_eligibility(*, workload, record, export, parser, roi):
    """A native percentage is eligible only after every evidence stage passes."""
    states = {'workload': workload, 'perf_record': record, 'perf_export': export,
              'parser': parser, 'roi': roi}
    return all(value == 'success' for value in states.values()), states


def verifier_hashes(scene):
    if scene == "xlsx":
        names = ("verify.py", "spreadsheet.py", "contracts.py", "workbooks.py")
    else:
        names = ("pdf.py", "pdf_loop.py")
    return {name: sha(HERE / "scripts" / ".." / ".." / ".." / "compatibility" / "verification" / name)
            for name in names}


def recipe_info(cfg):
    compat = read(REPO / "compatibility/suite.json")
    entry = next(e for e in compat["entries"]
                 if e["dataset_id"] == cfg["dataset"]
                 and (e.get("record_count") is None
                      or e["record_count"] == cfg["record_count"]))
    recipe_path = REPO / entry["recipe_path"]
    recipe = read(recipe_path)
    return entry, recipe_path, recipe


def invoke(command, log_path):
    """Stream one container's output to both a saved log and the caller."""
    with Path(log_path).open("w") as log:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            log.write(line)
            log.flush()
            print(line, end="", flush=True)
        return proc.wait()


def container_script(plan, cfg, mode):
    """Keep collector errors authoritative even when output archival fails."""
    if mode not in ('native', 'pyspy'):
        raise ValueError(f'unsupported collection mode: {mode}')
    q = shlex.quote
    count = cfg.get('record_count') or 1
    collect = shlex.join(['bash', f'/tmp/hs-scripts/collect_{mode}.sh',
                         cfg['config_id'], cfg['scene'], cfg['dataset'],
                         str(cfg['loops']), str(cfg['rate_hz']), '/data/out', '/data/raw'])
    return (
        'set -euo pipefail; '
        'cp -r /host-analysis/scripts /tmp/hs-scripts; '
        'mkdir -p /data/out /data/raw; '
        f'export HOTSPOT_PYTHON={q(plan.get("python", "/opt/document-bench/.venv/bin/python"))}; '
        f'export HOTSPOT_ENTRY={q(plan.get("entry", "/opt/office-trace-replay/replay/entry.py"))}; '
        'export PYTHONDONTWRITEBYTECODE=1; '
        f'export HOTSPOT_OPERATION_TIMEOUT={int(plan.get("operation_timeout_seconds", 900))}; '
        f'export HOTSPOT_RECALC_TIMEOUT={int(plan.get("recalc_timeout_seconds", 600))}; '
        f'if "$HOTSPOT_PYTHON" /tmp/hs-scripts/preflight_replay.py --scene {q(cfg["scene"])} '
        f'--dataset {q(cfg["dataset"])} --pdf-applicant-count {count} '
        f'--expected-operation-timeout {int(plan.get("operation_timeout_seconds", 900))} '
        f'--expected-recalc-timeout {int(plan.get("recalc_timeout_seconds", 600))} '
        '--output /data/out/preflight.json >/data/out/preflight.log 2>&1; '
        "then printf '0\\n' >/data/out/preflight-exit-code.txt; "
        'else preflight_rc=$?; printf "%s\\n" "$preflight_rc" '
        '>/data/out/preflight-exit-code.txt; exit "$preflight_rc"; fi; '
        f'collector_rc=0; {collect} || collector_rc=$?; '
        'printf "%s\\n" "$collector_rc" >/data/out/collector-exit-code.txt; '
        'archive_rc=0; '
        'WORKSPACE=$("$HOTSPOT_PYTHON" -c '
        "'import json; print(json.load(open(\"/data/out/preflight.json\"))[\"workspace\"])') || archive_rc=$?; "
        'if [ "$archive_rc" -eq 0 ] && [ -d "$WORKSPACE/output" ]; then '
        'cp -a "$WORKSPACE/output" /data/out/workspace-output || archive_rc=$?; '
        'if [ -d "$WORKSPACE/helpers" ]; then '
        'mkdir -p /data/out/workspace-helpers; '
        'cp -a "$WORKSPACE/helpers/." /data/out/workspace-helpers/ || archive_rc=$?; fi; '
        'mkdir -p /data/out/workspace-helpers; '
        'find "$WORKSPACE" -maxdepth 1 -type f -name "*.py" -exec cp -a {} /data/out/workspace-helpers/ \; '
        '|| archive_rc=$?; '
        'if [ -f /data/out/workspace-output/business_verification.json ]; then '
        'cp /data/out/workspace-output/business_verification.json /data/out/business_verification.json '
        '|| archive_rc=$?; else archive_rc=1; fi; '
        'else printf "workspace output unavailable; preserving existing logs\\n" >&2; archive_rc=1; fi; '
        'printf "%s\\n" "$archive_rc" >/data/out/archive-exit-code.txt; '
        'if [ "$collector_rc" -ne 0 ]; then exit "$collector_rc"; fi; exit "$archive_rc"'
    )


def collect_one(plan, cfg, mode, campaign_root=None):
    inner = container_script(plan, cfg, mode)
    cid = cfg["config_id"]
    rate = cfg["rate_hz"]
    loops = cfg["loops"]
    count = cfg["record_count"] or 1
    campaign_root = Path(campaign_root) if campaign_root is not None else CAMPAIGN
    stage = campaign_root / cid / ("r1" if mode == "native" else "pyspy")
    out = stage / "out"
    raw = stage / "raw"
    out.mkdir(parents=True, exist_ok=False)
    raw.mkdir(parents=True, exist_ok=False)
    entry, recipe_path, recipe = recipe_info(cfg)
    name = f"office-hs-{campaign_root.name}-{cid}-{mode}"
    command = [
        "docker", "run", "--name", name, "--network", "none",
        "--cap-add=SYS_PTRACE",
    ]
    if mode == "native":
        command.append("--cap-add=PERFMON")
    command += [
        "--mount", f"type=bind,src={HERE},dst=/host-analysis,readonly",
        "--mount", f"type=bind,src={REPO},dst=/opt/office-trace-replay,readonly",
        "--mount", (f"type=bind,src={REPO / 'legacy/document-oe/bin/run_document_scene_loop.py'},"
                    "dst=/opt/document-bench/bin/run_document_scene_loop.py,readonly"),
        "--mount", (f"type=bind,src={REPO / 'legacy/document-oe/bin/run_document_scene_loop_timed.py'},"
                    "dst=/opt/document-bench/bin/run_document_scene_loop_timed.py,readonly"),
        "--mount", f"type=bind,src={stage},dst=/data",
        "-e", f"HOTSPOT_PDF_COUNT={count}",
        "--entrypoint", "/bin/bash", plan.get("image_id", plan["image"]), "-c",
    ]
    command.append(inner)
    rc = invoke(command, stage / "container.log")
    state = None
    image_id = None
    container_id = None
    inspect = subprocess.run(["docker", "inspect", name], text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if inspect.returncode == 0:
        obj = json.loads(inspect.stdout)[0]
        state = obj.get("State", {})
        image_id = obj.get("Image")
        container_id = obj.get("Id")
    preflight_path = out / "preflight.json"
    preflight = read(preflight_path) if preflight_path.is_file() else {}
    preflight_status = preflight.get("status", "not_run")
    if mode == "native":
        meta_path = out / "metadata.json"
        meta = read(meta_path) if meta_path.exists() else {}
        summary = meta.get("runner_summary", {})
        workload = (workload_status(summary, loops) if summary else
                    ('not_run' if preflight_status != 'success' else 'unknown'))
        parser_rc = None
        roi_path = out / "roi.json"
        roi_data = {}
        parse_integrity = {'status': 'not_run'}
        export_status = meta.get("perf_export_status", "not_started")
        record_status = meta.get("perf_record_status", "not_started")
        if workload == 'success' and record_status == 'success' and export_status == 'complete':
            parser = subprocess.run([sys.executable, str(HERE / "scripts/parse_native.py"),
                                    str(stage), cid], text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
            (out / "parser.log").write_text(parser.stdout)
            parser_rc = parser.returncode
            roi_data = read(roi_path) if roi_path.exists() else {}
            parse_stats = roi_data.get('perf_script_parse', {})
            recognized = parse_stats.get('recognized_samples_total')
            reported = meta.get('total_samples')
            parse_integrity = {
                'status': 'complete' if recognized == reported and parser_rc == 0 else 'incomplete',
                'parser_exit_code': parser_rc,
                'recognized_samples': recognized,
                'perf_reported_samples': reported,
                'unmatched_sample_estimate': (reported - recognized
                                              if isinstance(reported, int) and isinstance(recognized, int)
                                              else None),
                'sample_period_total_in_text': parse_stats.get('parsed_period_total'),
                'unrecognized_header_count': parse_stats.get('unrecognized_sample_header_count'),
                'unrecognized_header_examples': parse_stats.get('unrecognized_sample_header_examples', []),
            }
            parse_ok = (parser_rc == 0 and roi_data.get("roi_samples", 0) > 0
                        and roi_data.get('roi_period_total', 0) > 0 and (
                roi_data.get("perf_script_parse", {}).get("recognized_samples_total")
                == meta.get("total_samples")))
        else:
            parse_ok = False
        roi_ok = bool(parse_ok and roi_data.get("roi_samples", 0) > 0)
        export_phase = {'complete': 'success', 'incomplete': 'incomplete',
                        'not_started': 'not_run'}.get(export_status, 'unknown')
        record_phase = ('success' if record_status == 'success' else
                        'not_run' if record_status == 'not_started' else 'failed')
        eligible, statuses = native_profile_eligibility(
            workload=workload, record=record_phase,
            export=export_phase,
            parser='success' if parse_ok else ('not_run' if parser_rc is None else 'failed'),
            roi='success' if roi_ok else ('not_run' if parser_rc is None else 'failed'))
        statuses['binding_preflight'] = preflight_status
        permission_status = meta.get('perf_data_host_read_permission_status', 'not_applicable')
        statuses['perf_data_host_read_permission'] = (
            'success' if permission_status == 'success' else
            'not_applicable' if record_status != 'success' else 'failed')
        # not_run is intentionally not success; no incomplete/failed phase can
        # enter a formal percentage even when earlier phases did succeed.
        collector_rc = meta.get("perf_rc")
    else:
        meta_path = out / "metadata.json"
        meta = read(meta_path) if meta_path.exists() else {}
        summary = meta.get("runner_summary", {})
        raw_file = raw / f"{cid}.pyspy.raw"
        parser_rc = None
        summary = meta.get("runner_summary", {})
        workload = (workload_status(summary, loops) if summary else
                    ('not_run' if preflight_status != 'success' else 'unknown'))
        if workload == 'success' and meta.get("rc") == 0 and raw_file.is_file() and raw_file.stat().st_size:
            parser = subprocess.run([sys.executable, str(HERE / "scripts/parse_pyspy.py"),
                                     str(raw_file), str(out)], text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            (out / "parser.log").write_text(parser.stdout)
            parser_rc = parser.returncode
        roles_path = out / "pyspy-roles.json"
        parsed_result = read(roles_path) if roles_path.is_file() else {}
        parse_integrity = parsed_result.get('parse_integrity', {})
        parsed_role_weight = sum(item.get('samples', 0)
                                 for item in parsed_result.get('roles', {}).values())
        parsed = (parser_rc == 0 and roles_path.is_file() and parsed_role_weight > 0
                  and parse_integrity.get('status') == 'complete'
                  and parse_integrity.get('raw_nonempty_line_count') ==
                      parse_integrity.get('parsed_stack_line_count')
                  and parse_integrity.get('raw_positive_count_sum') ==
                      parse_integrity.get('parsed_count_sum'))
        collector_rc = meta.get("rc")
    business = read(out / "business_verification.json") if (out / "business_verification.json").exists() else {}
    def step_exit_code(filename):
        path = out / filename
        try:
            return int(path.read_text().strip())
        except (OSError, ValueError):
            return None
    shell_rc = step_exit_code('collector-exit-code.txt')
    archive_rc = step_exit_code('archive-exit-code.txt')
    expected_recipe_sha = sha(recipe_path)
    if mode == "native":
        eligible = eligible and rc == 0 and state and state.get("ExitCode") == 0 \
            and business.get("status") == "success" and not business.get("failures")
        parsed = statuses['parser'] == 'success' and statuses['roi'] == 'success'
    else:
        raw_permission = meta.get('raw_host_read_permission_status', 'not_applicable')
        eligible = (workload == 'success' and rc == 0 and state and state.get("ExitCode") == 0
                    and collector_rc == 0 and parsed and raw_file.is_file()
                    and raw_file.stat().st_size > 0 and raw_permission == 'success')
        pyspy_status = ('not_started' if meta.get('rc') is None else
                        'success' if meta.get('rc') == 0 else 'failed')
        statuses = {'binding_preflight': preflight_status, 'workload': workload,
                    'perf_record': 'not_applicable', 'perf_export': 'not_applicable',
                    'pyspy': pyspy_status,
                    'raw_host_read_permission': ('success' if raw_permission == 'success'
                                                 else 'failed' if raw_file.is_file() else 'not_applicable'),
                    'parser': 'success' if parsed else
                    ('not_run' if parser_rc is None else 'failed'),
                    'roi': 'not_applicable'}
    statuses['collection_shell'] = ('not_run' if shell_rc is None else
                                    'success' if shell_rc == 0 else 'failed')
    statuses['archive'] = ('not_run' if archive_rc is None else
                           'success' if archive_rc == 0 else 'failed')
    run_ok = (rc == 0 and state and state.get("ExitCode") == 0 and collector_rc == 0
              and shell_rc == 0 and archive_rc == 0
              and preflight_status == 'success'
              and summary.get("requested_iterations") == loops
              and summary.get("completed_iterations") == loops
              and summary.get("successes") == loops and summary.get("failures") == 0
              and (mode != 'native' or record_status != 'success'
                   or meta.get('perf_data_host_read_permission_status') == 'success')
              and not summary.get('interrupted', False)
              and summary.get('dataset') == cfg['dataset'] and summary.get('scene') == cfg['scene']
              and (cfg['scene'] != 'pdf' or summary.get('pdf_applicant_count') == count)
              and summary.get("recipe_sha256") == expected_recipe_sha
              and expected_recipe_sha == entry['recipe_sha256']
              and (not plan.get('image_id') or image_id == plan['image_id'])
              and business.get("status") == "success" and not business.get("failures")
              and parsed and eligible)
    # A successful parser alone must not qualify a mismatched recipe/image or
    # failed binding/business validation for formal percentages.
    eligible = bool(run_ok)
    run_ok = bool(run_ok)
    source_hashes = {
        "runner_sha256": sha(REPO / "legacy/document-oe/bin/run_document_scene_loop.py"),
        "vendor_runner_sha256": sha(REPO / "vendor/document-oe/run_document_scene_loop.py"),
        "timed_runner_sha256": sha(REPO / "legacy/document-oe/bin/run_document_scene_loop_timed.py"),
        "replay_entry_sha256": sha(REPO / "replay/entry.py"),
        "replay_run_sha256": sha(REPO / "replay/run.py"),
        "freeze_sha256": sha(REPO / "replay/freeze.py"),
        "suite_registry_sha256": sha(REPO / "compatibility/suite.json"),
        "recipe_sha256": expected_recipe_sha,
        "recipe_frozen_sha256": entry["recipe_sha256"],
        "project_lock_sha256": sha(REPO / "assets/project-lock.json"),
        "compatibility_contract_sha256": sha(REPO / "compatibility/contract.json"),
        "verifier_sha256": verifier_hashes(cfg["scene"]),
        "input_hashes": recipe.get("input_hashes", {}),
        "helper_hashes": recipe.get("helper_hashes", {}),
        "analysis_scripts_sha256": {
            name: sha(HERE / "scripts" / name) for name in (
                "collect_current_loop_profiles.py", "collect_native.sh",
                "collect_pyspy.sh", "run_workload.sh", "bounded_perf_export.py",
                "preflight_replay.py", "collection_quality.py",
                "parse_native.py", "parse_pyspy.py", "script_identity.py", "monitor_procs.py",
                "roi_marker.py", "tstamp_pipe.py")},
    }
    record = {
        "schema_version": "hotspot-current-profile-record-v2",
        "config_id": cid, "mode": mode, "status": "success" if run_ok else "failed",
        "reason": None if run_ok else "one or more independent workload/record/export/parser/ROI/binding/business stages failed or were incomplete; preserve evidence and do not retry automatically",
        "container_name": name, "container_retained": True,
        "container_id": container_id,
        "container_exit_code": state.get("ExitCode") if state else rc,
        "collector_exit_code": shell_rc, "sampler_exit_code": collector_rc,
        "archive_exit_code": archive_rc, "parser_exit_code": parser_rc,
        "stage_status": {**statuses, 'profile_eligible': bool(eligible)},
        "parser_integrity": (parse_integrity if mode == 'native' else {
            **parse_integrity, 'status': 'success' if parsed else 'incomplete',
            'parser_exit_code': parser_rc, 'parsed_role_weight': parsed_role_weight}),
        "preflight": preflight,
        "image": plan["image"], "image_id": image_id,
        "mounts": {"repository": str(REPO), "analysis_scripts": str(HERE),
                   "installed_runner_override": str(REPO / "legacy/document-oe/bin/run_document_scene_loop.py")},
        "container_command": command,
        "in_container_command": inner,
        "hashes": source_hashes,
        "runtime": summary.get("environment"),
        "timeouts_seconds": {
            "operation": summary.get("operation_timeout_seconds"),
            "recalc": summary.get("recalc_timeout_seconds"),
        },
        "cpu_affinity": {"workload": "0-7", "monitor": "9"},
        "sampling": {"native_event": "cycles:u", "frequency_hz": rate,
                     "pyspy_frequency_hz": rate, "mode": mode},
        "execution": {"scene": cfg["scene"], "dataset": cfg["dataset"],
                      "record_count": cfg["record_count"], "requested_loops": loops,
                      "completed_loops": summary.get("completed_iterations"),
                      "successes": summary.get("successes"), "failures": summary.get("failures"),
                      "run_id": summary.get("run_id"),
                      "business_verification_status": business.get("status"),
                      "business_verification_failures": business.get("failures", [])},
        "roi": (read(out / "roi.json") if mode == "native" and (out / "roi.json").exists() else {
            "method": "py-spy run direct to current runner; known preflight stacks removed by existing parser; process-only samples retained",
            "boundary_limitation": "py-spy wall boundary is process-based and does not provide native perf ROI marker timing"}),
        "files": {"output_dir": str(out), "raw_dir": str(raw),
                  "runner_summary": str((out / "runner-results")),
                  "business_verification": str(out / "business_verification.json"),
                  "preflight_report": str(preflight_path),
                  "preflight_log": str(out / "preflight.log")},
    }
    if mode == 'native':
        def read_log(path):
            try:
                return path.read_text(errors='replace')
            except OSError as exc:
                record.setdefault('quality_log_read_errors', []).append(
                    {'path': str(path), 'error': f'{type(exc).__name__}: {exc}'})
                return ''
        record['capture_quality'] = summarize_native_quality(
            perf_record_log=read_log(out / 'stdout.log'),
            report_text=read_log(out / 'native-by-dso.txt'),
            perf_script_stderr=read_log(raw / f'{cid}.samples.txt.stderr.log'),
            roi=record['roi'], export_status=meta.get('perf_export_status', 'unknown'),
            parser_exit_code=parser_rc,
            perf_report_exit_code=meta.get('perf_reports_exit_code'))
        record['capture_quality']['source_files'] = {
            'perf_record_diagnostics': str(out / 'stdout.log'),
            'perf_report_lost_samples': str(out / 'native-by-dso.txt'),
            'perf_script_symbol_warnings': str(raw / f'{cid}.samples.txt.stderr.log'),
            'roi_symbol_counts_and_periods': str(out / 'roi.json'),
        }
        record['perf_data_host_read_permission'] = {
            'status': meta.get('perf_data_host_read_permission_status', 'not_applicable'),
            'exit_code': meta.get('perf_data_host_read_permission_exit_code'),
            'target': f'raw/{cid}.data', 'mode_requested': '0644 for this newly recorded file only',
        }
    write(out / "collection-record.json", record)
    print(f"{cid} {mode}: {record['status']} rc={rc} collector={collector_rc} parser={parser_rc} "
          f"business={business.get('status')} image={image_id}", flush=True)
    return run_ok


def main():
    plan = read(PLAN_PATH)
    CAMPAIGN.mkdir(parents=True, exist_ok=False)
    image = subprocess.check_output(["docker", "image", "inspect", plan["image"],
                                     "--format", "{{.Id}}"], text=True).strip()
    if image != plan["image_id"]:
        raise SystemExit(f"image ID mismatch: {image} != {plan['image_id']}; no runs started")
    manifest = {
        "schema_version": "hotspot-current-loop-campaign-v1", "status": "in_progress",
        "image": plan["image"], "image_id": image,
        "plan_sha256": sha(PLAN_PATH),
        "analysis_scripts_sha256": {p.name: sha(p) for p in sorted((HERE / "scripts").glob("*.py"))
                                    if p.name in ("collect_current_loop_profiles.py", "collect_native.sh", "collect_pyspy.sh", "bounded_perf_export.py", "parse_native.py", "parse_pyspy.py", "script_identity.py", "monitor_procs.py", "roi_marker.py", "tstamp_pipe.py", "run_workload.sh")},
        "mounted_runner_sha256": sha(REPO / "vendor/document-oe/run_document_scene_loop.py"),
        "configs": [cfg["config_id"] for cfg in plan["configs"]],
        "samplers": ["native", "pyspy"], "no_repeats": True,
    }
    write(CAMPAIGN / "campaign-manifest.json", manifest)
    failed = []
    for cfg in plan["configs"]:
        print(f"START {cfg['config_id']} loops={cfg['loops']} count={cfg['record_count']}", flush=True)
        native_ok = collect_one(plan, cfg, "native")
        native_record = read(CAMPAIGN / cfg["config_id"] / "r1/out/collection-record.json")
        if not native_ok:
            failed.append(cfg["config_id"] + ":native")
        native_workload = native_record.get('stage_status', {}).get('workload', 'unknown')
        if native_workload != 'success':
            skipped = manifest.setdefault('not_started', [])
            skipped.append({'config_id': cfg['config_id'], 'mode': 'pyspy',
                            'reason': f'native workload status was {native_workload}; sampler not started, not an acquisition failure'})
            write(CAMPAIGN / "campaign-manifest.json", manifest)
            continue
        if not collect_one(plan, cfg, "pyspy"):
            failed.append(cfg["config_id"] + ":pyspy")
    manifest["status"] = "complete_with_failures" if failed else "complete"
    manifest["failures"] = failed
    write(CAMPAIGN / "campaign-manifest.json", manifest)
    print(json.dumps({"status": manifest["status"], "failures": failed,
                      "campaign": str(CAMPAIGN)}, indent=2), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
