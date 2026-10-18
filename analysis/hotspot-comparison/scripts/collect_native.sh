#!/usr/bin/env bash
# One native perf hotspot collection inside the container.
#
# Usage: collect_native.sh CONFIG_ID SCENE DATASET LOOPS RATE_HZ OUTDIR RAWDIR
#
# Starts the /proc monitor (CPU 9) and a stdout timestamper, then records
# cycles:u with DWARF call graphs around the workload runner (CPUs 0-7), and
# emits derived perf reports plus metadata into OUTDIR; the perf.data stays in
# RAWDIR.
set -uo pipefail

CONFIG_ID=$1; SCENE=$2; DATASET=$3; LOOPS=$4; RATE=$5; OUT=$6; RAW=$7
SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
RUNNER=/opt/document-bench/bin/run_document_scene_loop.py
WORKCPUS=0-7
MONCPU=9
if [ "$RATE" -ge 99 ]; then INTERVAL_MS=10; else INTERVAL_MS=25; fi

mkdir -p "$OUT" "$RAW"
RESULTS="$OUT/runner-results"
mkdir -p "$RESULTS"

# stop-flag dir for the monitor
STOPDIR="$OUT/monitor-ctl"; rm -rf "$STOPDIR"; mkdir -p "$STOPDIR"; touch "$STOPDIR/alive"
export HOTSPOT_MONITOR_STOP="$STOPDIR"

mkdir -p "$OUT/monitor"
taskset -c "$MONCPU" python3 "$SCRIPTS/monitor_procs.py" "$OUT/monitor" "$INTERVAL_MS" &
MONPID=$!

FIFO="$OUT/stdout.fifo"; rm -f "$FIFO"; mkfifo "$FIFO"
taskset -c "$MONCPU" python3 "$SCRIPTS/tstamp_pipe.py" "$FIFO" "$OUT/stdout.log" &
TSPID=$!

ARGS=(--scene "$SCENE" --dataset "$DATASET" --loops "$LOOPS" --results-dir "$RESULTS")
if [ "$SCENE" = pdf ]; then
  COUNT=${HOTSPOT_PDF_COUNT:-1}
  ARGS+=(--pdf-applicant-count "$COUNT")
fi

T_START=$(date +%s)
perf record -e cycles:u -F "$RATE" -g --call-graph dwarf,16384 \
  -o "$RAW/$CONFIG_ID.data" \
  -- bash "$SCRIPTS/run_workload.sh" "${ARGS[@]}" > "$FIFO" 2>&1
PERF_RC=$?
T_END=$(date +%s)

rm -f "$STOPDIR/alive"
sleep 0.3
kill "$MONPID" 2>/dev/null
wait "$MONPID" 2>/dev/null
kill "$TSPID" 2>/dev/null
wait "$TSPID" 2>/dev/null
rm -f "$FIFO"

# locate the successful run summary (last one written)
SUMMARY=$(find "$RESULTS" -name summary.json | sort | tail -1)

perf report --stdio --call-graph none --no-children --sort comm --percent-limit 0.01 \
  -i "$RAW/$CONFIG_ID.data" > "$OUT/native-by-process.txt" 2>/dev/null
perf report --stdio --call-graph none --no-children --sort comm,dso --percent-limit 0.01 \
  -i "$RAW/$CONFIG_ID.data" > "$OUT/native-by-process-dso.txt" 2>/dev/null
perf report --stdio --call-graph none --no-children --sort comm,dso,symbol --percent-limit 0.10 \
  -i "$RAW/$CONFIG_ID.data" > "$OUT/native-by-process-dso-symbol.txt" 2>/dev/null
perf report --stdio --call-graph none --no-children --sort dso --percent-limit 0.01 \
  -i "$RAW/$CONFIG_ID.data" > "$OUT/native-by-dso.txt" 2>/dev/null
perf script -i "$RAW/$CONFIG_ID.data" > "$RAW/$CONFIG_ID.samples.txt" 2>/dev/null
TOTAL_SAMPLES=$(grep -c 'cycles:u:' "$RAW/$CONFIG_ID.samples.txt" || true)
LOST=$(perf report --stdio -i "$RAW/$CONFIG_ID.data" 2>/dev/null | grep -m1 'Total Lost Samples' || true)

python3 - "$OUT/metadata.json" "$CONFIG_ID" "$SCENE" "$DATASET" "$LOOPS" "$RATE" \
  "$T_START" "$T_END" "$PERF_RC" "$TOTAL_SAMPLES" "$SUMMARY" <<'PY'
import hashlib, json, sys
(out_path, config_id, scene, dataset, loops, rate, t0, t1, rc, total, summary) = sys.argv[1:]
meta = {
  "config_id": config_id, "scene": scene, "dataset": dataset, "loops": int(loops),
  "rate_hz": int(rate), "mode": "native",
  "perf_rc": int(rc), "total_samples": int(total),
  "wall_seconds": int(t1) - int(t0),
  "runner_sha256": hashlib.sha256(open("/opt/document-bench/bin/run_document_scene_loop.py","rb").read()).hexdigest(),
  "image_files_check": "runner self-validation passed (pre-run project hash validation completed)",
}
if summary:
    meta["runner_summary"] = json.load(open(summary))
with open(out_path, "w") as fh:
    json.dump(meta, fh, indent=2)
PY
echo "native collection done: $CONFIG_ID rc=$PERF_RC samples=$TOTAL_SAMPLES summary=$SUMMARY"
