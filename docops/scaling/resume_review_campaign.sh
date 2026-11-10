#!/usr/bin/env bash
# Start a detached, lock-protected resume; never overwrite an earlier log.
set -euo pipefail

REPO=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
CAMP="$REPO/results/docops/scaling-reviewed-perf-20261107T054300Z-4359de4a"
LOG_DIR=/tmp/opencode
while (($#)); do
  case "$1" in
    --campaign-dir) CAMP="$2"; shift 2 ;;
    --log-dir) LOG_DIR="$2"; shift 2 ;;
    *) echo "usage: $0 [--campaign-dir PATH] [--log-dir PATH]" >&2; exit 2 ;;
  esac
done
cd "$REPO"
if [[ ! -f "$CAMP/campaign.json" ]]; then
  echo "campaign.json missing: $CAMP" >&2
  exit 2
fi

for tool in setsid nohup python3 mktemp; do command -v "$tool" >/dev/null; done
mkdir -p -- "$LOG_DIR"
LOG=$(mktemp "$LOG_DIR/perf_campaign.resume.$(date -u +%Y%m%dT%H%M%SZ).XXXXXX.log")
STATUS="$LOG.startup.json"

# The Python entry holds the lock through acquisition AND finalization.
# A startup handshake distinguishes a live owner from a failed background job.
setsid nohup python3 -B -u docops/scaling/collect_review_campaign.py \
  --campaign-dir "$CAMP" --resume --startup-status "$STATUS" \
  >"$LOG" 2>&1 </dev/null &
LAUNCH_PID=$!
for ((i=0; i<100; i++)); do
  if [[ -f "$STATUS" ]]; then
    if python3 -B -c '
import json, sys
s = json.load(open(sys.argv[1]))
print("resume " + s["status"] + " pid=" + str(s.get("pid")))
if s.get("error"): print(s["error"], file=sys.stderr)
sys.exit(0 if s["status"] == "started" else 1)
' "$STATUS"; then
      echo "log: $LOG"
      echo "campaign: $CAMP"
      echo "Started in a separate session; SSH may be disconnected. Check the log/campaign for completion."
      exit 0
    fi
    echo "Not started. Diagnostic log: $LOG" >&2
    exit 1
  fi
  if ! kill -0 "$LAUNCH_PID" 2>/dev/null; then
    echo "Background launcher exited before startup confirmation. Log: $LOG" >&2
    exit 1
  fi
  sleep 0.1
done
echo "Startup not confirmed yet; do not launch again. pid=$LAUNCH_PID log=$LOG" >&2
exit 1
