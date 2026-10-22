#!/usr/bin/env bash
# Host-side driver: collection and parser exit statuses are tracked separately.
# Usage: run_collection2.sh {native|pyspy|stat|syscalls}
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
IMAGE=$(python3 -c "import json;print(json.load(open('$ROOT/config/run-plan.json'))['image'])")
LOG="$ROOT/raw/collection.log"
mkdir -p "$ROOT/raw"

run_container() {  # CONTAINER-COMMAND OUTDIR
  local cmd=$1 outdir=$2
  docker run --rm --network none --cap-add=PERFMON --cap-add=SYS_PTRACE \
    -v "$ROOT:/host-analysis" -v "$outdir:/data" \
    -e HOTSPOT_PDF_COUNT="${PDFCOUNT:-1}" \
    --entrypoint /bin/bash "$IMAGE" -c "
      cp -r /host-analysis/scripts /tmp/hs-scripts
      chmod +x /tmp/hs-scripts/*.sh /tmp/hs-scripts/*.py
      $cmd
    " >> "$LOG" 2>&1
  local rc=$?
  docker run --rm -v "$outdir:/data" --entrypoint /bin/bash "$IMAGE" \
    -c "chmod -R a+rwX /data" >/dev/null 2>&1
  return $rc
}

MODE=${1:?mode: native|pyspy|stat|syscalls}

preserve_incomplete_attempt() {
  local dir=$1 config=$2 mode=$3
  if [ -d "$dir" ] && [ -n "$(find "$dir" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
    local stamp
    stamp=$(date -u +%Y%m%dT%H%M%SZ)
    mkdir -p "$ROOT/raw/$config/attempts"
    mv "$dir" "$ROOT/raw/$config/attempts/${mode}-${stamp}"
    mkdir -p "$dir"
    echo "[$(date +%H:%M:%S)] preserved prior $mode attempt at raw/$config/attempts/${mode}-${stamp}" >> "$LOG"
  fi
}

python3 - "$ROOT" "$MODE" > "$ROOT/raw/active-plan.tsv" <<'PY'
import json, sys
root, mode = sys.argv[1], sys.argv[2]
plan = json.load(open(f"{root}/config/run-plan.json"))
want = plan["syscalls_configs"] if mode == "syscalls" else None
for cfg in plan["configs"]:
    if want is not None and cfg["config_id"] not in want:
        continue
    print("\t".join([cfg["config_id"], cfg["scene"], cfg["dataset"],
                     str(cfg["loops"]), str(cfg["rate_hz"]),
                     str(cfg.get("record_count") or 1)]))
PY

while IFS=$'\t' read -r config scene dataset loops rate count; do
  PDFCOUNT=$count
  case "$MODE" in
    native)
      for rep in r1 r2; do
        outdir="$ROOT/raw/$config/$rep"
        if [ -s "$outdir/out/samples.jsonl" ] && [ -f "$outdir/out/roi.json" ] && \
           [ -f "$outdir/raw/$config.samples.txt" ] && [ -f "$outdir/out/metadata.json" ] && \
           python3 - "$outdir/out/metadata.json" "$outdir/raw/$config.data" "$outdir/out/roi.json" "$LOG" "$config" "$rep" <<'PY'
import json,sys
from pathlib import Path
m=json.load(open(sys.argv[1])); log=Path(sys.argv[4]).read_text().splitlines()
roi=json.load(open(sys.argv[3]))
summary=m.get('runner_summary',{})
parse=roi.get('perf_script_parse',{})
tag=f"native {sys.argv[5]}/{sys.argv[6]} "
collector=[x for x in log if tag+'collector_rc=' in x]
parser=[x for x in log if tag+'parser_rc=' in x]
ok=(m.get('perf_rc') == 0 and summary.get('successes') == summary.get('requested_iterations')
    and Path(sys.argv[2]).is_file() and Path(sys.argv[2]).stat().st_size > 0
    and roi.get('roi_samples',0)>0 and parse.get('recognized_samples_total') == m.get('total_samples')
    and collector and collector[-1].endswith('collector_rc=0')
    and parser and parser[-1].endswith('parser_rc=0'))
raise SystemExit(0 if ok else 1)
PY
        then
          echo "[$(date +%H:%M:%S)] native $config/$rep collection validated, skip" >> "$LOG"
          continue
        fi
        preserve_incomplete_attempt "$outdir" "$config" "native-$rep"
        echo "[$(date +%H:%M:%S)] native $config/$rep start" >> "$LOG"
        run_container "mkdir -p /data/out /data/raw; bash /tmp/hs-scripts/collect_native.sh '$config' '$scene' '$dataset' '$loops' '$rate' /data/out /data/raw" "$outdir"
        collect_rc=$?
        echo "[$(date +%H:%M:%S)] native $config/$rep collector_rc=$collect_rc" >> "$LOG"
        python3 "$ROOT/scripts/parse_native.py" "$outdir" "$config" >> "$LOG" 2>&1
        parse_rc=$?
        echo "[$(date +%H:%M:%S)] native $config/$rep parser_rc=$parse_rc" >> "$LOG"
      done
      ;;
    pyspy)
      outdir="$ROOT/raw/$config/pyspy"
      if [ -s "$outdir/out/pyspy-roles.json" ] && [ -s "$outdir/raw/$config.pyspy.raw" ] && \
         [ -f "$outdir/out/metadata.json" ] && [ -f "$outdir/out/pyspy-run.log" ] && \
         python3 - "$outdir/out/metadata.json" "$LOG" "$config" <<'PY'
import json,sys
from pathlib import Path
m=json.load(open(sys.argv[1])); s=m.get('runner_summary',{})
log=Path(sys.argv[2]).read_text().splitlines(); tag=f"pyspy {sys.argv[3]} "
collector=[x for x in log if tag+'collector_rc=' in x]; parser=[x for x in log if tag+'parser_rc=' in x]
ok=(m.get('rc') == 0 and s.get('successes') == s.get('requested_iterations')
    and collector and collector[-1].endswith('collector_rc=0')
    and parser and parser[-1].endswith('parser_rc=0'))
raise SystemExit(0 if ok else 1)
PY
      then
        continue
      fi
      preserve_incomplete_attempt "$outdir" "$config" "pyspy"
      echo "[$(date +%H:%M:%S)] pyspy $config start" >> "$LOG"
      run_container "mkdir -p /data/out /data/raw; bash /tmp/hs-scripts/collect_pyspy.sh '$config' '$scene' '$dataset' '$loops' '$rate' /data/out /data/raw" "$outdir"
      collect_rc=$?
      echo "[$(date +%H:%M:%S)] pyspy $config collector_rc=$collect_rc" >> "$LOG"
      python3 "$ROOT/scripts/parse_pyspy.py" "$outdir/raw/$config.pyspy.raw" "$outdir/out" >> "$LOG" 2>&1
      parse_rc=$?
      echo "[$(date +%H:%M:%S)] pyspy $config parser_rc=$parse_rc" >> "$LOG"
      ;;
    stat)
      outdir="$ROOT/raw/$config/stat"
      if [ -s "$outdir/stat.csv" ] && [ -f "$outdir/metadata.json" ] && \
         python3 - "$outdir/metadata.json" "$outdir/stat.csv" "$LOG" "$config" <<'PY'
import csv,json,sys
from pathlib import Path
m=json.load(open(sys.argv[1])); s=m.get('runner_summary',{})
rows=list(csv.reader(open(sys.argv[2])))
events={r[2].strip() for r in rows if len(r)>2}
log=Path(sys.argv[3]).read_text().splitlines(); tag=f"stat {sys.argv[4]} "
collector=[x for x in log if tag+'collector_rc=' in x]
ok=(m.get('rc') == 0 and s.get('successes') == s.get('requested_iterations')
    and {'cycles:u','instructions:u'}.issubset(events)
    and collector and collector[-1].endswith('collector_rc=0'))
raise SystemExit(0 if ok else 1)
PY
      then
        continue
      fi
      preserve_incomplete_attempt "$outdir" "$config" "stat"
      echo "[$(date +%H:%M:%S)] stat $config start" >> "$LOG"
      run_container "mkdir -p /data; bash /tmp/hs-scripts/collect_stat.sh '$config' '$scene' '$dataset' '$loops' /data" "$outdir"
      collect_rc=$?
      echo "[$(date +%H:%M:%S)] stat $config collector_rc=$collect_rc" >> "$LOG"
      ;;
    syscalls)
      outdir="$ROOT/raw/$config/syscalls"
      if [ -s "$outdir/syscalls.txt" ] && [ -s "$outdir/strace-run.log" ] && \
         python3 - "$ROOT" "$outdir/syscalls.txt" "$outdir/strace-run.log" "$LOG" "$config" <<'PY'
import sys
from pathlib import Path
root=Path(sys.argv[1]); sys.path.insert(0,str(root/'scripts'))
from build_profiles import parse_strace_summary
summary=parse_strace_summary(Path(sys.argv[2]).read_text())
log=Path(sys.argv[3]).read_text()
driver=Path(sys.argv[4]).read_text().splitlines(); tag=f"strace {sys.argv[5]} "
collector=[x for x in driver if tag+'collector_rc=' in x]
ok=(summary.get('total_row') is not None and summary.get('calls_total_matches') and 'rc=0' in log
    and collector and collector[-1].endswith('collector_rc=0'))
raise SystemExit(0 if ok else 1)
PY
      then
        continue
      fi
      preserve_incomplete_attempt "$outdir" "$config" "syscalls"
      echo "[$(date +%H:%M:%S)] strace $config start" >> "$LOG"
      if [ "$scene" = pdf ]; then
        run_container "mkdir -p /data/runner-results; taskset -c 0-7 strace -f -c -o /data/syscalls.txt -- python3 /opt/document-bench/bin/run_document_scene_loop.py --scene '$scene' --dataset '$dataset' --loops '$loops' --pdf-applicant-count '$count' --results-dir /data/runner-results > /data/strace-run.log 2>&1; echo rc=\$? >> /data/strace-run.log" "$outdir"
      else
        run_container "mkdir -p /data/runner-results; taskset -c 0-7 strace -f -c -o /data/syscalls.txt -- python3 /opt/document-bench/bin/run_document_scene_loop.py --scene '$scene' --dataset '$dataset' --loops '$loops' --results-dir /data/runner-results > /data/strace-run.log 2>&1; echo rc=\$? >> /data/strace-run.log" "$outdir"
      fi
      collect_rc=$?
      echo "[$(date +%H:%M:%S)] strace $config collector_rc=$collect_rc" >> "$LOG"
      ;;
  esac
done < "$ROOT/raw/active-plan.tsv"
echo "[$(date +%H:%M:%S)] mode=$MODE complete" >> "$LOG"
