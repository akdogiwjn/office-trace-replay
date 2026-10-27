#!/usr/bin/env python3
"""Tiny sampler/export/parser/archive smoke; never invokes replay or a dataset."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = Path(__file__).resolve().parent
IMAGE = "office-trace-replay:openeuler-release"
EXPECTED_IMAGE = "sha256:e68ea4ca0e43340b09dd355b4217f756260fe4ae3d33c576fdb0b8ab4d5f437a"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


DRIVER = r'''import hashlib, json, os, subprocess, sys
from pathlib import Path

sys.path.insert(0, "/host-analysis/scripts")
mode, root_s = sys.argv[1:]
root = Path(root_s)
py = "/opt/document-bench/.venv/bin/python"
root.mkdir(parents=True, exist_ok=True)
work = root / "work.py"
child = root / "child.py"
nl = chr(10)
work.write_text(nl.join(["import subprocess, sys, time",
                         "subprocess.run([sys.executable, %r], check=True)" % str(child),
                         "end=time.monotonic()+2.2", "x=0",
                         "while time.monotonic()<end: x=(x+1)*3%10000019"]))
child.write_text(nl.join(["import time", "end=time.monotonic()+2.0", "x=0",
                          "while time.monotonic()<end: x=(x+1)*7%10000079"]))
raw = root / "raw"; out = root / "out"
raw.mkdir(exist_ok=True); out.mkdir(exist_ok=True)
def run(args, **kw): return subprocess.run(args, check=True, **kw)
if mode == "native":
    perf_data = raw / "smoke.data"
    run(["perf", "record", "-e", "cycles:u", "-F", "49", "-g",
         "--call-graph", "dwarf,16384", "-o", str(perf_data), "--", py, str(work)],
        stdout=(out / "perf-record.stdout.log").open("w"),
        stderr=(out / "perf-record.stderr.log").open("w"))
    os.chmod(perf_data, 0o644)
    from bounded_perf_export import bounded_export
    exported = raw / "smoke.samples.txt"
    status = raw / "smoke-export-status.json"
    res = bounded_export(perf_data, exported, status, 90)
    if res.get("status") != "complete": raise RuntimeError("bounded perf export incomplete: %r" % res)
    from parse_native import parse_samples
    samples, stats = parse_samples(exported)
    if not samples or stats["unrecognized_sample_header_count"] or stats["parsed_period_total"] <= 0:
        raise RuntimeError("native parser sample/period integrity failed: %r" % stats)
    if not os.access(perf_data, os.R_OK): raise RuntimeError("native raw is not readable")
    (out / "parse-summary.json").write_text(json.dumps(stats, indent=2)+nl)
    result = {"schema_version":"collector-smoke-v1", "kind":"collector_smoke",
              "mode":mode, "status":"success", "profile_eligible":False,
              "raw_nonempty":perf_data.stat().st_size > 0,
              "raw_mode":oct(perf_data.stat().st_mode & 0o777),
              "sample_count":len(samples), "sample_period_total":stats["parsed_period_total"],
              "export_status":res["status"], "unrecognized_sample_header_count":stats["unrecognized_sample_header_count"]}
else:
    raw_file = raw / "smoke.pyspy.raw"
    command = ["py-spy", "record", "--subprocesses", "--rate", "49", "--format", "raw",
               "-o", str(raw_file), "--", py, str(work)]
    run(command, stdout=(out / "pyspy-run.stdout.log").open("w"),
        stderr=(out / "pyspy-run.stderr.log").open("w"))
    os.chmod(raw_file, 0o644)
    (out / "metadata.json").write_text(json.dumps({"runner_summary":{"scene":"xlsx"}}))
    parser = run([py, "/host-analysis/scripts/parse_pyspy.py", str(raw_file), str(out)],
                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (out / "parser.log").write_text(parser.stdout)
    parsed = json.loads((out / "pyspy-roles.json").read_text())
    integrity = parsed["parse_integrity"]
    if integrity["status"] != "complete" or integrity["parsed_count_sum"] <= 0:
        raise RuntimeError("py-spy parser integrity failed: %r" % integrity)
    if "child.py" not in raw_file.read_text(errors="replace"):
        raise RuntimeError("py-spy --subprocesses did not capture child.py")
    result = {"schema_version":"collector-smoke-v1", "kind":"collector_smoke",
              "mode":mode, "status":"success", "profile_eligible":False,
              "raw_nonempty":raw_file.stat().st_size > 0,
              "raw_mode":oct(raw_file.stat().st_mode & 0o777),
              "parse_integrity":integrity, "child_process_tracked":True}
(out / "smoke-record.json").write_text(json.dumps(result, indent=2)+nl)
files=[]
owned = [root / "raw", root / "out", work, child]
for item in owned:
    candidates = sorted(item.rglob("*")) if item.is_dir() else [item]
    for p in candidates:
        if p.is_file() and p.name != "sha256-index.json":
            files.append({"path":str(p.relative_to(root)),"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
(root / "sha256-index.json").write_text(json.dumps({"schema_version":"collector-smoke-index-v1","files":files},indent=2)+nl)
print(json.dumps(result), flush=True)
'''


def write_driver(root: Path) -> None:
    (root / "driver.py").write_text(DRIVER)


def write_campaign_index(root: Path) -> None:
    rows = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "evidence-index.json":
            rows.append({"path":str(p.relative_to(root)),"bytes":p.stat().st_size,"sha256":sha(p)})
    (root / "evidence-index.json").write_text(json.dumps(
        {"schema_version":"collector-smoke-campaign-index-v1","files":rows},indent=2)+"\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--image", default=IMAGE)
    ap.add_argument("--expected-image-id", default=EXPECTED_IMAGE)
    args = ap.parse_args(argv)
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    image_id = subprocess.check_output(
        ["docker", "image", "inspect", args.image, "--format", "{{.Id}}"], text=True).strip()
    if image_id != args.expected_image_id:
        raise SystemExit(f"image ID mismatch: {image_id} != {args.expected_image_id}")
    write_driver(out)
    record = {"schema_version":"collector-smoke-campaign-v1", "kind":"collector_smoke",
              "status":"in_progress", "image":args.image, "image_id":image_id,
              "started_at_utc":datetime.now(timezone.utc).isoformat(), "modes":[]}
    (out / "campaign-record.json").write_text(json.dumps(record,indent=2)+"\n")
    for mode in ("native", "pyspy"):
        mode_root = out / mode
        mode_root.mkdir()
        name = f"collector-smoke-{out.name}-{mode}"
        command = ["docker", "run", "--name", name, "--network", "none",
                   "--cap-add=SYS_PTRACE", "--cap-add=PERFMON",
                   "--mount", f"type=bind,src={SCRIPTS},dst=/host-analysis/scripts,readonly",
                   "--mount", f"type=bind,src={out},dst=/smoke",
                   "--entrypoint", "/opt/document-bench/.venv/bin/python", image_id,
                   "/smoke/driver.py", mode, f"/smoke/{mode}"]
        (mode_root / "docker-argv.json").write_text(json.dumps(command,indent=2)+"\n")
        try:
            with (mode_root / "container.log").open("w") as log:
                proc = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                      text=True, timeout=120)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            exit_code = 124
            (mode_root / "timeout.txt").write_text("smoke container command exceeded 120 seconds\n")
        inspect = subprocess.run(["docker", "inspect", name], text=True,
                                 capture_output=True)
        info = None
        if inspect.returncode == 0:
            info = json.loads(inspect.stdout)[0]
            (mode_root / "container-inspect.json").write_text(json.dumps(info,indent=2)+"\n")
        mode_record = {"mode":mode, "container_name":name,
                       "container_id":info.get("Id") if info else None,
                       "actual_image_id":info.get("Image") if info else None,
                       "exit_code":exit_code, "status":"failed"}
        smoke_record = mode_root / "out/smoke-record.json"
        if exit_code == 0 and info and info.get("Image") == image_id and smoke_record.is_file():
            payload = json.loads(smoke_record.read_text())
            mode_record.update(payload)
            index_path = mode_root / "sha256-index.json"
            index = json.loads(index_path.read_text()) if index_path.is_file() else {}
            index_errors = []
            for row in index.get("files", []):
                path = mode_root / row["path"]
                if (not path.is_file() or path.stat().st_size != row["bytes"]
                        or sha(path) != row["sha256"]):
                    index_errors.append(row["path"])
            mode_record["archive_index_entries"] = len(index.get("files", []))
            mode_record["archive_index_errors"] = index_errors
            raw_candidate = next((p for p in (mode_root / "raw").glob("*")
                                  if p.suffix in {".data", ".raw"}), None)
            mode_record["host_raw_readable"] = bool(raw_candidate and raw_candidate.open("rb").read(1) is not None)
            mode_record["host_raw_mode"] = oct(raw_candidate.stat().st_mode & 0o777) if raw_candidate else None
            mode_record["status"] = ("success" if payload.get("status") == "success"
                                      and not index_errors and mode_record["host_raw_readable"]
                                      and mode_record["host_raw_mode"] == "0o644" else "failed")
        record["modes"].append(mode_record)
        record["status"] = "in_progress" if exit_code == 0 and mode_record["status"] == "success" else "stopped_on_failure"
        (out / "campaign-record.json").write_text(json.dumps(record,indent=2)+"\n")
        if record["status"] != "in_progress":
            record["not_started"] = [m for m in ("native", "pyspy") if m not in [x["mode"] for x in record["modes"]]]
            (out / "campaign-record.json").write_text(json.dumps(record,indent=2)+"\n")
            write_campaign_index(out)
            return 1
    record["status"] = "success"
    record["profile_eligible"] = False
    record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    (out / "campaign-record.json").write_text(json.dumps(record,indent=2)+"\n")
    write_campaign_index(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
