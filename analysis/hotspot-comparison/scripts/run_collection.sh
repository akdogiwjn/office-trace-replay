#!/usr/bin/env bash
# Host-side driver: runs the full hotspot collection plan from config/run-plan.json.
# Each config+repeat is one disposable container (image from the run plan) with
# PERFMON+SYS_PTRACE capabilities, network disabled, scripts mounted from the
# repository and raw data written into analysis/hotspot-comparison/raw/.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
IMAGE=$(python3 -c "import json;print(json.load(open('$ROOT/config/run-plan.json'))['image'])")
LOG="$ROOT/raw/collection.log"
mkdir -p "$ROOT/raw"

run_one() {  # KIND CONFIG SCENE DATASET LOOPS RATE PDFCOUNT OUTDIR
  local kind=$1 config=$2 scene=$3 dataset=$4 loops=$5 rate=$6 count=$7 outdir=$8
  echo "[$(date +%H:%M:%S)] $kind $config -> $outdir" | tee -a "$LOG"
  docker run --rm --network none --cap-add=PERFMON --cap-add=SYS_PTRACE \
    -v "$ROOT:/host-analysis" -v "$outdir:/data" \
    -e HOTSPOT_PDF_COUNT="$count" \
    --entrypoint /bin/bash "$IMAGE" -c "
      cp -r /host-analysis/scripts /tmp/hs-scripts
      chmod +x /tmp/hs-scripts/*.sh /tmp/hs-scripts/*.py
      mkdir -p /data/out /data/raw
      bash /tmp/hs-scripts/collect_$kind.sh '$config' '$scene' '$dataset' '$loops' '$rate' /data/out /data/raw
    " >> "$LOG" 2>&1
  local rc=$?
  docker run --rm -v "$outdir:/data" --entrypoint /bin/bash "$IMAGE" -c "chmod -R a+rwX /data" >/dev/null 2>&1
  echo "[$(date +%H:%M:%S)] $kind $config rc=$rc" | tee -a "$LOG"
  return $rc
}

run_stat_one() {  # CONFIG SCENE DATASET LOOPS PDFCOUNT OUTDIR
  local config=$1 scene=$2 dataset=$3 loops=$4 count=$5 outdir=$6
  echo "[$(date +%H:%M:%S)] stat $config -> $outdir" | tee -a "$LOG"
  docker run --rm --network none --cap-add=PERFMON --cap-add=SYS_PTRACE \
    -v "$ROOT:/host-analysis" -v "$outdir:/data" \
    -e HOTSPOT_PDF_COUNT="$count" \
    --entrypoint /bin/bash "$IMAGE" -c "
      cp -r /host-analysis/scripts /tmp/hs-scripts
      chmod +x /tmp/hs-scripts/*.sh /tmp/hs-scripts/*.py
      mkdir -p /data
      bash /tmp/hs-scripts/collect_stat.sh '$config' '$scene' '$dataset' '$loops' /data
    " >> "$LOG" 2>&1
  local rc=$?
  docker run --rm -v "$outdir:/data" --entrypoint /bin/bash "$IMAGE" -c "chmod -R a+rwX /data" >/dev/null 2>&1
  echo "[$(date +%H:%M:%S)] stat $config rc=$rc" | tee -a "$LOG"
}

run_strace_one() {  # CONFIG SCENE DATASET LOOPS PDFCOUNT OUTDIR
  local config=$1 scene=$2 dataset=$3 loops=$4 count=$5 outdir=$6
  echo "[$(date +%H:%M:%S)] strace $config -> $outdir" | tee -a "$LOG"
  docker run --rm --network none --cap-add=SYS_PTRACE \
    -v "$ROOT:/host-analysis" -v "$outdir:/data" \
    -e HOTSPOT_PDF_COUNT="$count" \
    --entrypoint /bin/bash "$IMAGE" -c "
      mkdir -p /data/runner-results
      taskset -c 0-7 strace -f -c -o /data/syscalls.txt -- \
        python3 /opt/document-bench/bin/run_document_scene_loop.py \
        --scene '$scene' --dataset '$dataset' --loops '$loops' \
        --results-dir /data/runner-results $( [ '$scene' = pdf ] && echo --pdf-applicant-count '$count' ) \
        > /data/strace-run.log 2>&1
      echo rc=\$? >> /data/strace-run.log
    " >> "$LOG" 2>&1
  docker run --rm -v "$outdir:/data" --entrypoint /bin/bash "$IMAGE" -c "chmod -R a+rwX /data" >/dev/null 2>&1
  echo "[$(date +%H:%M:%S)] strace $config done" | tee -a "$LOG"
}

python3 - "$ROOT" <<'PY' > "$ROOT/raw/plan.tsv"
import json, sys
root = sys.argv[1]
plan = json.load(open(f"{root}/config/run-plan.json"))
for cfg in plan["configs"]:
    count = cfg.get("record_count") or 1
    print("\t".join([cfg["config_id"], cfg["scene"], cfg["dataset"],
                     str(cfg["loops"]), str(cfg["rate_hz"]), str(count)]))
PY

MODE=${1:-all}
while IFS=$'\t' read -r config scene dataset loops rate count; do
  case "$MODE" in
    native)
      for rep in r1 r2; do
        outdir="$ROOT/raw/$config/$rep"
        [ -f "$outdir/out/samples.jsonl" ] || run_one native "$config" "$scene" "$dataset" "$loops" "$rate" "$count" "$outdir" || true
      done
      ;;
    pyspy)
      outdir="$ROOT/raw/$config/pyspy"
      [ -f "$outdir/out/pyspy-roles.json" ] || run_one pyspy "$config" "$scene" "$dataset" "$loops" "$rate" "$count" "$outdir" || true
      ;;
    stat)
      outdir="$ROOT/raw/$config/stat"
      [ -f "$outdir/stat.csv" ] || run_stat_one "$config" "$scene" "$dataset" "$loops" "$count" "$outdir" || true
      ;;
  esac
done < "$ROOT/raw/plan.tsv"

if [ "$MODE" = syscalls ]; then
  python3 - "$ROOT" <<'PY' > "$ROOT/raw/syscalls-plan.tsv"
import json, sys
root = sys.argv[1]
plan = json.load(open(f"{root}/config/run-plan.json"))
for config_id in plan["syscalls_configs"]:
    for cfg in plan["configs"]:
        if cfg["config_id"] == config_id:
            print("\t".join([config_id, cfg["scene"], cfg["dataset"],
                             str(cfg["loops"]), str(cfg.get("record_count") or 1)]))
PY
  while IFS=$'\t' read -r config scene dataset loops count; do
    outdir="$ROOT/raw/$config/syscalls"
    [ -f "$outdir/syscalls.txt" ] || run_strace_one "$config" "$scene" "$dataset" "$loops" "$count" "$outdir" || true
  done < "$ROOT/raw/syscalls-plan.tsv"
fi
echo "[$(date +%H:%M:%S)] mode=$MODE complete" | tee -a "$LOG"
