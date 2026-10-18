#!/usr/bin/env bash
# One py-spy Python-stack collection inside the container (separate run from perf).
# Usage: collect_pyspy.sh CONFIG_ID SCENE DATASET LOOPS RATE_HZ OUTDIR RAWDIR
set -uo pipefail
CONFIG_ID=$1; SCENE=$2; DATASET=$3; LOOPS=$4; RATE=$5; OUT=$6; RAW=$7
SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
WORKCPUS=0-7
mkdir -p "$OUT" "$RAW"
RESULTS="$OUT/runner-results"; mkdir -p "$RESULTS"

ARGS=(--scene "$SCENE" --dataset "$DATASET" --loops "$LOOPS" --results-dir "$RESULTS")
if [ "$SCENE" = pdf ]; then
  ARGS+=(--pdf-applicant-count "${HOTSPOT_PDF_COUNT:-1}")
fi

T_START=$(date +%s)
# py-spy (and the workload inheriting its affinity) on the fixed CPU budget;
# the runner must be py-spy's direct python child for --subprocesses tracking.
taskset -c "$WORKCPUS" py-spy record --subprocesses --rate "$RATE" --format raw \
  -o "$RAW/$CONFIG_ID.pyspy.raw" \
  -- python3 /opt/document-bench/bin/run_document_scene_loop.py "${ARGS[@]}" \
  > "$OUT/pyspy-run.log" 2>&1
RC=$?
T_END=$(date +%s)
SUMMARY=$(find "$RESULTS" -name summary.json | sort | tail -1)
python3 - "$OUT/metadata.json" "$CONFIG_ID" "$RATE" "$T_START" "$T_END" "$RC" "$SUMMARY" <<'PY'
import json, sys
(out_path, config_id, rate, t0, t1, rc, summary) = sys.argv[1:]
meta = {"config_id": config_id, "mode": "pyspy", "rate_hz": int(rate),
       "rc": int(rc), "wall_seconds": int(t1)-int(t0)}
if summary:
    meta["runner_summary"] = json.load(open(summary))
json.dump(meta, open(out_path, "w"), indent=2)
PY
echo "pyspy collection done: $CONFIG_ID rc=$RC"
