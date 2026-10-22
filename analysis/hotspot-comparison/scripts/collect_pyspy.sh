#!/usr/bin/env bash
# One py-spy Python-stack collection inside the container (separate run from perf).
# Usage: collect_pyspy.sh CONFIG_ID SCENE DATASET LOOPS RATE_HZ OUTDIR RAWDIR
set -uo pipefail
CONFIG_ID=$1; SCENE=$2; DATASET=$3; LOOPS=$4; RATE=$5; OUT=$6; RAW=$7
SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
WORKCPUS=0-7
PYTHON=${HOTSPOT_PYTHON:-/opt/document-bench/.venv/bin/python}
ENTRY=${HOTSPOT_ENTRY:-/opt/office-trace-replay/replay/entry.py}
mkdir -p "$OUT" "$RAW"
RESULTS="$OUT/runner-results"; mkdir -p "$RESULTS"

ARGS=(--scene "$SCENE" --dataset "$DATASET" --loops "$LOOPS" --results-dir "$RESULTS")
if [ "$SCENE" = pdf ]; then
  ARGS+=(--pdf-applicant-count "${HOTSPOT_PDF_COUNT:-1}")
else
  ARGS+=(--operation-timeout "${HOTSPOT_OPERATION_TIMEOUT:-900}"
         --recalc-timeout "${HOTSPOT_RECALC_TIMEOUT:-600}")
fi

T_START=$(date +%s)
# py-spy (and the workload inheriting its affinity) on the fixed CPU budget;
# the runner must be py-spy's direct python child for --subprocesses tracking.
taskset -c "$WORKCPUS" py-spy record --subprocesses --rate "$RATE" --format raw \
  -o "$RAW/$CONFIG_ID.pyspy.raw" \
  -- "$PYTHON" "$ENTRY" "${ARGS[@]}" \
  > "$OUT/pyspy-run.log" 2>&1
RC=$?
T_END=$(date +%s)
RAW_PERMISSION_STATUS=not_applicable
RAW_PERMISSION_RC=0
if [ -e "$RAW/$CONFIG_ID.pyspy.raw" ]; then
  chmod 0644 -- "$RAW/$CONFIG_ID.pyspy.raw"
  RAW_PERMISSION_RC=$?
  if [ "$RAW_PERMISSION_RC" -eq 0 ]; then RAW_PERMISSION_STATUS=success
  else RAW_PERMISSION_STATUS=failed; fi
fi
mapfile -t SUMMARIES < <(find "$RESULTS" -name summary.json)
SUMMARY=
if [ "${#SUMMARIES[@]}" -eq 1 ]; then SUMMARY=${SUMMARIES[0]}; fi
python3 - "$OUT/metadata.json" "$CONFIG_ID" "$RATE" "$T_START" "$T_END" "$RC" "$SUMMARY" "$RAW_PERMISSION_STATUS" "$RAW_PERMISSION_RC" <<'PY'
import json, sys
(out_path, config_id, rate, t0, t1, rc, summary, raw_permission_status, raw_permission_rc) = sys.argv[1:]
meta = {"config_id": config_id, "mode": "pyspy", "rate_hz": int(rate),
       "rc": int(rc), "wall_seconds": int(t1)-int(t0),
       "raw_host_read_permission_status": raw_permission_status,
       "raw_host_read_permission_exit_code": int(raw_permission_rc)}
if summary:
    meta["runner_summary"] = json.load(open(summary))
json.dump(meta, open(out_path, "w"), indent=2)
PY
echo "pyspy collection done: $CONFIG_ID rc=$RC"
if [ -e "$RAW/$CONFIG_ID.pyspy.raw" ] && [ "$RAW_PERMISSION_STATUS" != success ]; then exit 1; fi
exit "$RC"
