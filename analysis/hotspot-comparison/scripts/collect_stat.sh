#!/usr/bin/env bash
# One perf stat collection (hardware counters + task-clock) inside the container.
# Usage: collect_stat.sh CONFIG_ID SCENE DATASET LOOPS OUTDIR
set -uo pipefail
CONFIG_ID=$1; SCENE=$2; DATASET=$3; LOOPS=$4; OUT=$5
mkdir -p "$OUT"
python3 - "$OUT" "$CONFIG_ID" "$SCENE" "$DATASET" "$LOOPS" <<'PY'
import json, os, subprocess, sys, time

out, config_id, scene, dataset, loops = sys.argv[1:6]
os.makedirs(os.path.join(out, "runner-results"), exist_ok=True)
args = ["taskset", "-c", "0-7", "python3",
        "/opt/document-bench/bin/run_document_scene_loop.py",
        "--scene", scene, "--dataset", dataset, "--loops", loops,
        "--results-dir", os.path.join(out, "runner-results")]
if scene == "pdf":
    args += ["--pdf-applicant-count", os.environ.get("HOTSPOT_PDF_COUNT", "1")]
cmd = ["perf", "stat", "-x,", "-o", os.path.join(out, "stat.csv"),
       "-e", "cycles:u,cycles:k,instructions:u,instructions:k,task-clock,"
             "context-switches,cpu-migrations,page-faults", "--"] + args
t0 = time.monotonic()
r = subprocess.run(cmd, capture_output=True)
t1 = time.monotonic()
with open(os.path.join(out, "stat-wall.txt"), "w") as fh:
    fh.write("wall_seconds=%.3f\nrc=%d\n" % (t1 - t0, r.returncode))
meta = {"config_id": config_id, "mode": "stat", "rc": r.returncode,
        "wall_seconds": round(t1 - t0, 3)}
summaries = subprocess.run(
    ["find", os.path.join(out, "runner-results"), "-name", "summary.json"],
    capture_output=True, text=True).stdout.split()
if summaries:
    meta["runner_summary"] = json.load(open(sorted(summaries)[-1]))
json.dump(meta, open(os.path.join(out, "metadata.json"), "w"), indent=2)
print("stat done", config_id, "rc=", r.returncode)
PY
