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
PERF_DATA="$RAW/$CONFIG_ID.data"
if [ -e "$PERF_DATA" ]; then
  printf 'refusing to overwrite existing perf.data: %s\n' "$PERF_DATA" >&2
  exit 73
fi
RESULTS="$OUT/runner-results"
mkdir -p "$RESULTS"

# stop-flag dir for the monitor
STOPDIR="$OUT/monitor-ctl"; rm -rf "$STOPDIR"; mkdir -p "$STOPDIR"; touch "$STOPDIR/alive"
export HOTSPOT_MONITOR_STOP="$STOPDIR"

mkdir -p "$OUT/monitor"
taskset -c "$MONCPU" python3 "$SCRIPTS/monitor_procs.py" "$OUT/monitor" "$INTERVAL_MS" &
MONPID=$!
TSPID=
cleanup() {
  rm -f "$STOPDIR/alive"
  if [ -n "$MONPID" ]; then kill "$MONPID" 2>/dev/null || true; fi
  if [ -n "$TSPID" ]; then kill "$TSPID" 2>/dev/null || true; fi
  rm -f "$FIFO"
}
FIFO="$OUT/stdout.fifo"
trap cleanup EXIT

FIFO="$OUT/stdout.fifo"; rm -f "$FIFO"; mkfifo "$FIFO"
taskset -c "$MONCPU" python3 "$SCRIPTS/tstamp_pipe.py" "$FIFO" "$OUT/stdout.log" &
TSPID=$!

ARGS=(--scene "$SCENE" --dataset "$DATASET" --loops "$LOOPS" --results-dir "$RESULTS")
if [ "$SCENE" = pdf ]; then
  COUNT=${HOTSPOT_PDF_COUNT:-1}
  ARGS+=(--pdf-applicant-count "$COUNT")
else
  ARGS+=(--operation-timeout "${HOTSPOT_OPERATION_TIMEOUT:-900}"
         --recalc-timeout "${HOTSPOT_RECALC_TIMEOUT:-600}")
fi

T_START=$(date +%s)
perf record -e cycles:u -F "$RATE" -g --call-graph dwarf,16384 \
  -o "$PERF_DATA" \
  -- bash "$SCRIPTS/run_workload.sh" "${ARGS[@]}" > "$FIFO" 2>&1
PERF_RC=$?
T_END=$(date +%s)

# perf creates perf.data with mode 0600 regardless of umask. This path belongs
# to the new, unique capture only; make exactly this file host-readable for
# hashing/archival, and carry any chmod error into metadata and exit status.
PERF_DATA_PERMISSION_STATUS=not_applicable
PERF_DATA_PERMISSION_RC=0
if [ -e "$PERF_DATA" ]; then
  chmod 0644 -- "$PERF_DATA"
  chmod_rc=$?
  if [ "$chmod_rc" -eq 0 ]; then
    PERF_DATA_PERMISSION_STATUS=success
  else
    PERF_DATA_PERMISSION_STATUS=failed
    PERF_DATA_PERMISSION_RC=$chmod_rc
  fi
fi

rm -f "$STOPDIR/alive"
# Let the monitor write its last-seen table and the pipe reader drain stdout.
wait "$MONPID"; MONITOR_RC=$?; MONPID=
wait "$TSPID"; TSTAMP_RC=$?; TSPID=
rm -f "$FIFO"

# locate the successful run summary (last one written)
mapfile -t SUMMARIES < <(find "$RESULTS" -name summary.json)
SUMMARY=
if [ "${#SUMMARIES[@]}" -eq 1 ]; then SUMMARY=${SUMMARIES[0]}; fi
WORKLOAD_STATUS=unknown
PERF_RECORD_STATUS=failed
PERF_EXPORT_STATUS=not_started
PERF_EXPORT_RC=
PERF_EXPORT_REASON=
TOTAL_SAMPLES=0
if [ -n "$SUMMARY" ]; then
  WORKLOAD_STATUS=$(python3 - "$SUMMARY" "$LOOPS" <<'PY'
import json, sys
try:
    data=json.load(open(sys.argv[1]))
    ok=(not data.get('interrupted', False)
        and data.get('requested_iterations') == int(sys.argv[2])
        and data.get('completed_iterations') == int(sys.argv[2])
        and data.get('successes') == int(sys.argv[2]) and data.get('failures') == 0)
    print('success' if ok else 'failed')
except Exception:
    print('unknown')
PY
  )
fi
if [ "$PERF_RC" -eq 0 ] && [ -s "$RAW/$CONFIG_ID.data" ]; then
  PERF_RECORD_STATUS=success
fi
if [ "$WORKLOAD_STATUS" = success ]; then
  if [ "$PERF_RECORD_STATUS" = success ]; then
    if [ "$PERF_DATA_PERMISSION_STATUS" != success ]; then
      PERF_EXPORT_REASON='skipped: host-readable permission setup failed'
    else
      EXPORT_TIMEOUT=${HOTSPOT_PERF_EXPORT_TIMEOUT_SECONDS:-900}
      python3 "$SCRIPTS/bounded_perf_export.py" "$PERF_DATA" \
        "$RAW/$CONFIG_ID.samples.txt" "$OUT/perf-export-status.json" \
        --timeout-seconds "$EXPORT_TIMEOUT" > "$OUT/perf-export.log" 2>&1
      PERF_EXPORT_RC=$?
      PERF_EXPORT_STATUS=$(python3 - "$OUT/perf-export-status.json" <<'PY'
import json,sys
try: print(json.load(open(sys.argv[1])).get('status','unknown'))
except Exception: print('unknown')
PY
      )
      PERF_EXPORT_REASON=$(python3 - "$OUT/perf-export-status.json" <<'PY'
import json,sys
try: print(json.load(open(sys.argv[1])).get('reason') or '')
except Exception: print('export status could not be read')
PY
      )
    fi
  else
    PERF_EXPORT_REASON='skipped: perf record did not complete successfully'
  fi
else
  PERF_EXPORT_REASON="skipped: workload status was $WORKLOAD_STATUS"
fi

REPORTS_RC=0
if [ "$WORKLOAD_STATUS" = success ] && [ "$PERF_RECORD_STATUS" = success ] \
   && [ "$PERF_EXPORT_STATUS" = complete ]; then
  for sort_and_name in comm:native-by-process comm,dso:native-by-process-dso \
      comm,dso,symbol:native-by-process-dso-symbol dso:native-by-dso; do
    sort_key=${sort_and_name%%:*}; report_name=${sort_and_name#*:}
    python3 "$SCRIPTS/bounded_perf_export.py" "$RAW/$CONFIG_ID.data" \
      "$OUT/$report_name.txt" "$OUT/$report_name.status.json" \
      --report-sort "$sort_key" --timeout-seconds "${HOTSPOT_PERF_REPORT_TIMEOUT_SECONDS:-120}" \
      > "$OUT/$report_name.export.log" 2>&1 || { REPORTS_RC=$?; break; }
  done
  TOTAL_SAMPLES=$(grep -c 'cycles:u:' "$RAW/$CONFIG_ID.samples.txt" || true)
fi

python3 - "$OUT/metadata.json" "$CONFIG_ID" "$SCENE" "$DATASET" "$LOOPS" "$RATE" \
  "$T_START" "$T_END" "$PERF_RC" "$TOTAL_SAMPLES" "$SUMMARY" \
  "$WORKLOAD_STATUS" "$PERF_RECORD_STATUS" "$PERF_EXPORT_STATUS" "$PERF_EXPORT_RC" "$PERF_EXPORT_REASON" \
  "$MONITOR_RC" "$TSTAMP_RC" "$REPORTS_RC" \
  "$PERF_DATA_PERMISSION_STATUS" "$PERF_DATA_PERMISSION_RC" <<'PY'
import hashlib, json, sys
(out_path, config_id, scene, dataset, loops, rate, t0, t1, rc, total, summary,
 workload_status, record_status, export_status, export_rc, export_reason,
 monitor_rc, tstamp_rc, reports_rc, data_permission_status, data_permission_rc) = sys.argv[1:]
meta = {
  "config_id": config_id, "scene": scene, "dataset": dataset, "loops": int(loops),
  "rate_hz": int(rate), "mode": "native",
  "perf_rc": int(rc), "total_samples": int(total),
  "workload_status": workload_status,
  "perf_record_status": record_status,
  "perf_export_status": export_status,
  "perf_export_exit_code": int(export_rc) if export_rc else None,
  "perf_export_reason": export_reason or None,
  "perf_data_host_read_permission_status": data_permission_status,
  "perf_data_host_read_permission_exit_code": int(data_permission_rc),
  "monitor_exit_code": int(monitor_rc), "stdout_capture_exit_code": int(tstamp_rc),
  "perf_reports_exit_code": int(reports_rc),
  "profile_eligible_before_parse": False,
  "wall_seconds": int(t1) - int(t0),
  "runner_sha256": hashlib.sha256(open("/opt/document-bench/bin/run_document_scene_loop.py","rb").read()).hexdigest(),
  "image_files_check": "see preflight.json for binding validation evidence",
}
if summary:
    try:
        meta["runner_summary"] = json.load(open(summary))
    except Exception as exc:
        meta["runner_summary_error"] = f'{type(exc).__name__}: {exc}'
with open(out_path, "w") as fh:
    json.dump(meta, fh, indent=2)
PY
echo "native collection done: $CONFIG_ID rc=$PERF_RC samples=$TOTAL_SAMPLES summary=$SUMMARY"
if [ "$PERF_RC" -ne 0 ]; then exit "$PERF_RC"; fi
if [ "$WORKLOAD_STATUS" != success ] || [ "$PERF_EXPORT_STATUS" != complete ] \
   || [ "$MONITOR_RC" -ne 0 ] || [ "$TSTAMP_RC" -ne 0 ] || [ "$REPORTS_RC" -ne 0 ] \
   || { [ -e "$PERF_DATA" ] && [ "$PERF_DATA_PERMISSION_STATUS" != success ]; }; then exit 1; fi
