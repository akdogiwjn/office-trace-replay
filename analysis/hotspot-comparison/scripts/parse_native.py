#!/usr/bin/env python3
"""Parse native perf samples + monitor identities + timestamped stdout into the
ROI-restricted, period-weighted process / DSO / symbol tables.

Inputs (one native run directory):
  <run>/raw/<config>.samples.txt   perf script default output (comm tid time:
                                   period cycles:u: + tab-indented frames)
  <run>/out/monitor/identity.jsonl identity events (pid, comm, cmdline, t)
  <run>/out/monitor/identity-last-seen.json
  <run>/out/monitor/monitor.jsonl  per-poll process+thread CPU counters
  <run>/out/stdout.log             mono-timestamped runner stdout

Outputs (written into <run>/out/):
  samples.jsonl        one line per ROI sample: {t, tid, pid, comm, period,
                       leaf_sym, leaf_dso, role}
  roi.json             ROI boundary info (marker anchor, loop start, cut time,
                       pre-loop excluded samples/period)
  roles.json           role table with identity evidence
  parallelism.json     thread-CPU-based parallelism profile inside the ROI
"""
import argparse
import json
import re
import sys
from pathlib import Path
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from script_identity import role_for_command

# perf writes the event tuple at the right edge. Keep the complete comm field,
# which may itself contain spaces, and accept leading whitespace from exporters.
HEADER = re.compile(
    r"^\s*(?P<comm>.+?)\s+(?P<tid>\d+)\s+"
    r"(?P<time>[0-9]+\.[0-9]+):\s+(?P<period>\d+)\s+cycles:u:\s*$")
SAMPLE_HEADER_SHAPE = re.compile(
    r"^\s*(?P<comm>.+?)\s+(?P<tid>\d+)\s+"
    r"(?P<time>[0-9]+\.[0-9]+):\s+(?P<period>\d+)\s+(?P<event>\S+):\s*$")
MAX_UNRECOGNIZED_HEADER_EXAMPLES = 5
# Demangled C++ names contain spaces; capture the final parenthesized field as DSO.
FRAME = re.compile(r"^\s+([0-9a-fA-F]+)\s+(.+?)\s+\(([^()]*)\)\s*$")


def parse_samples(path):
    samples = []
    stats = {"headers": 0, "frames": 0, "malformed_frame_lines": 0,
             "samples_without_frames": 0, "samples_with_unresolved_stack": 0,
             "unrecognized_sample_header_count": 0,
             "unrecognized_sample_header_period_sum": 0,
             "unrecognized_sample_header_examples": []}
    comm = tid = time_s = period = None
    frames = []
    def finish_sample():
        nonlocal comm, tid, time_s, period, frames
        if comm is None:
            return
        samples.append((comm, int(tid), float(time_s), int(period), frames))
        if not frames:
            stats["samples_without_frames"] += 1
        comm = tid = time_s = period = None
        frames = []

    with open(path) as fh:
        for line_number, line in enumerate(fh, 1):
            m = HEADER.match(line)
            if m:
                finish_sample()
                comm = m.group("comm").strip()
                tid, time_s, period = m.group("tid"), m.group("time"), m.group("period")
                frames = []
                stats["headers"] += 1
                continue
            candidate = SAMPLE_HEADER_SHAPE.match(line)
            if candidate:
                finish_sample()
                stats["unrecognized_sample_header_count"] += 1
                stats["unrecognized_sample_header_period_sum"] += int(candidate.group("period"))
                if len(stats["unrecognized_sample_header_examples"]) < MAX_UNRECOGNIZED_HEADER_EXAMPLES:
                    stats["unrecognized_sample_header_examples"].append({
                        "line": line_number,
                        "text": line.rstrip("\n")[:240],
                        "event": candidate.group("event"),
                        "period": int(candidate.group("period")),
                    })
                continue
            m = FRAME.match(line)
            if m and comm is not None:
                address, raw_sym, dso = m.groups()
                sym = raw_sym.split("+0x")[0] if "+0x" in raw_sym else raw_sym
                inline = dso == "inlined"
                frames.append({"address": address.lower(), "symbol": sym,
                               "raw_symbol": raw_sym, "dso": dso,
                               "inline": inline})
                stats["frames"] += 1
                continue
            if comm is not None and line.strip() and re.match(r"^\s+[0-9a-fA-F]+\s+", line):
                stats["malformed_frame_lines"] += 1
            if line.strip() == "" and comm is not None:
                finish_sample()
    finish_sample()
    stats["parsed_sample_count"] = len(samples)
    stats["parsed_period_total"] = sum(sample[3] for sample in samples)
    stats["samples_with_unresolved_stack"] = sum(
        not f or leaf_of(f)["dso"] == "[unknown]" for _, _, _, _, f in samples)
    stats["samples_with_single_frame_stack"] = sum(len(f) == 1 for _, _, _, _, f in samples)
    return samples, stats


def leaf_of(frames):
    """Resolve an inline leaf only to its same-address concrete frame."""
    if not frames:
        return {"symbol": "[no-frame]", "dso": "[unknown]", "entity_symbol": None,
                "inline_recovered": False, "unknown_reason": "empty-stack"}
    leaf = frames[0]
    if not leaf.get("inline"):
        return {"symbol": leaf["symbol"], "dso": leaf["dso"],
                "entity_symbol": leaf["symbol"], "entity_dso": leaf["dso"],
                "inline_recovered": False,
                "unknown_reason": "leaf-dso-unknown" if leaf["dso"] == "[unknown]" else None}
    # Inline frames are perf's logical expansion of the sampled address. Only
    # a concrete frame at that exact address can recover the owning DSO.
    for frame in frames[1:]:
        if frame["address"] != leaf["address"]:
            break
        if not frame.get("inline"):
            if frame["dso"] == "[unknown]":
                break
            return {"symbol": leaf["symbol"], "dso": frame["dso"],
                    "entity_symbol": frame["symbol"], "entity_dso": frame["dso"],
                    "inline_recovered": True, "unknown_reason": None}
    return {"symbol": leaf["symbol"], "dso": "[unknown]", "entity_symbol": None,
            "inline_recovered": False, "unknown_reason": "inline-owner-not-found-at-same-address"}


def rename_poll_metrics(metrics):
    """Normalize historic poll-counter labels without claiming simultaneity."""
    if not metrics or "error" in metrics:
        return metrics
    renames = {
        "single_active_share": "single_active_poll_interval_share",
        "multi_active_share": "multi_active_poll_interval_share",
        "idle_polls_share": "no_active_thread_poll_interval_share",
        "peak_parallelism": "max_active_threads_in_poll_interval",
        "avg_parallelism": "mean_active_threads_per_poll_interval",
        "parallelism_histogram": "active_threads_per_poll_interval_histogram",
    }
    out = {renames.get(k, k): v for k, v in metrics.items()}
    if "method" in out:
        out["method"] = ("thread utime+stime deltas per monitor poll interval inside the ROI; "
                          "counts threads whose CPU counters advanced at least once during each interval; "
                          "this is not simultaneity")
    return out


def load_identities(mon_dir):
    """Return per-pid list of identity windows:
    [{comm, cmdline, ppid, start_t, end_t}] with times in seconds (mono)."""
    events = {}
    with open(mon_dir / "identity.jsonl") as fh:
        for line in fh:
            ev = json.loads(line)
            events.setdefault(ev["pid"], []).append(ev)
    last_seen = json.load(open(mon_dir / "identity-last-seen.json"))
    windows = {}
    for pid, evs in events.items():
        wins = []
        for i, ev in enumerate(evs):
            start = ev["t_ns"] / 1e9
            end = (evs[i + 1]["t_ns"] / 1e9) if i + 1 < len(evs) else last_seen.get(str(pid), ev["t_ns"]) / 1e9
            wins.append({"comm": ev["comm"], "cmdline": ev["cmdline"],
                         "ppid": ev["ppid"], "start": start, "end": end})
        windows[pid] = wins
    return windows


def script_role(cmd, scene):
    """Resolve from the executed script operand, not arbitrary command text."""
    role = role_for_command(cmd, scene)
    if role:
        return role
    try:
        import shlex
        argv = shlex.split(cmd)
    except ValueError:
        argv = []
    if argv and Path(argv[0]).name.startswith("python") and "-c" in argv:
        return "python-inline"
    return None


LO_THREAD_COMMS = {
    "thread-pool", "Parser", "configmgrWriter", "osl_executeProc", "Unzipping",
    "Writer", "Reader", "Desktop", "Splash", "javaldx", "oosplash",
    "sal3", "salhelper", "UpdateCheckConfigUpdater", "vpolygon",
}
COMM_ROLES = {
    "pdftoppm": "pdftoppm", "pdfinfo": "pdfinfo",
    "soffice.bin": "soffice.bin", "soffice": "soffice-wrapper",
    "bash": "bash", "sh": "bash", "PERFROI": "roi-marker",
    "python3": "python-unknown-script", "python": "python-unknown-script",
    "perf": "perf", "perf-exec": "perf-exec", "taskset": "taskset",
    "timeout": "lo-startup", "gpg": "lo-startup", "gpgconf": "lo-startup",
    "gpgsm": "lo-startup", "dirname": "lo-startup", "basename": "lo-startup",
    "cat": "shell-text", "cp": "shell-text", "grep": "shell-text",
    "ls": "shell-text", "wc": "shell-text", "sort": "shell-text",
    "find": "shell-text", "sed": "shell-text", "head": "shell-text",
    "tee": "shell-text", "echo": "shell-text", "mkdir": "shell-text",
    "env": "shell-text", "test": "shell-text",
}


def role_for(pid, comm, t, windows, scene):
    wins = windows.get(pid, [])
    for win in wins:
        if win["start"] - 0.05 <= t <= win["end"] + 0.05 and comm == win["comm"]:
            role = script_role(win["cmdline"], scene)
            if role:
                return role, win["cmdline"]
            return COMM_ROLES.get(comm, "unknown:" + comm), win["cmdline"]
    # same pid, different comm: LibreOffice worker threads (perf reports the
    # thread comm; the process window belongs to soffice.bin)
    for win in wins:
        if win["start"] - 0.05 <= t <= win["end"] + 0.05 and "soffice" in win["cmdline"]:
            return "lo-thread", win["cmdline"]
    if comm in LO_THREAD_COMMS:
        return "lo-thread", ""
    return COMM_ROLES.get(comm, "unknown:" + comm), ""


def identity_cmdline_context(pid, t, windows):
    """Process argv plus bounded parent argv chain at the sample timestamp."""
    context, seen = [], set()
    current = pid
    for _ in range(8):
        if current in seen: break
        seen.add(current)
        win = next((w for w in windows.get(current, [])
                    if w["start"] - 0.05 <= t <= w["end"] + 0.05), None)
        if not win: break
        if win["cmdline"]: context.append(win["cmdline"])
        current = win["ppid"]
        if not current: break
    return context


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("config_id")
    args = ap.parse_args()
    run = Path(args.run_dir)
    out = run / "out"
    raw = run / "raw"
    mon = out / "monitor"

    # 1. ROI anchors from the timestamped stdout
    marker_mono = None
    loop_start_mono = None
    with open(out / "stdout.log") as fh:
        for line in fh:
            parts = line.split(" ", 1)
            if len(parts) != 2:
                continue
            t_ns, text = int(parts[0]), parts[1].rstrip("\n")
            if text.startswith("MARKER_MONO_NS"):
                marker_mono = int(text.split()[1]) / 1e9
            if "] start: loops=" in text:
                loop_start_mono = t_ns / 1e9
    if marker_mono is None or loop_start_mono is None:
        sys.exit("cannot find MARKER/loop-start in stdout.log")

    with open(out / "metadata.json") as fh:
        meta = json.load(fh)

    # 2. perf-time anchor: median PERFROI sample time. The marker burns 300 ms
    # starting at marker_mono; its samples spread uniformly over the burn, so
    # the median sample time anchors the midpoint (robust against first-sample
    # lag from DWARF/frequency adaptation).
    samples, parse_stats = parse_samples(raw / f"{args.config_id}.samples.txt")
    roi_marker = [s for s in samples if s[0] == "PERFROI"]
    if not roi_marker:
        sys.exit("no PERFROI marker samples")
    marker_times = sorted(s[2] for s in roi_marker)
    median_marker = marker_times[len(marker_times) // 2]
    offset = (marker_mono + 0.150) - median_marker
    t_loop_start_perf = loop_start_mono - offset

    # 3. classify samples, cut ROI
    windows = load_identities(mon)
    tid_to_pid = {}
    with open(mon / "monitor.jsonl") as fh:
        for line in fh:
            rec = json.loads(line)
            for pid, tid, _tcomm, _u, _s in rec["threads"]:
                tid_to_pid.setdefault(tid, []).append((rec["t_ns"] / 1e9, pid))

    kept, excluded = [], {"count": 0, "period": 0}
    frame_quality = {"inline_recovered_samples": 0, "true_unknown_dso_samples": 0,
                     "empty_stack_samples": 0, "inline_owner_unresolved_samples": 0,
                     "unresolved_leaf_symbol_samples": 0,
                     "inline_recovered_period": 0, "true_unknown_dso_period": 0,
                     "empty_stack_period": 0, "inline_owner_unresolved_period": 0}
    frame_quality["unresolved_leaf_symbol_period"] = 0
    out_fh = open(out / "samples.jsonl", "w")
    for comm, tid, t, period, frames in samples:
        if t < t_loop_start_perf:
            excluded["count"] += 1
            excluded["period"] += period
            continue
        t_mono = t + offset  # identity windows live in the monotonic domain
        owners = tid_to_pid.get(tid, [])
        pid = next((p for seen, p in reversed(owners) if seen <= t_mono), tid)
        role, cmd = role_for(pid, comm, t_mono, windows, meta['scene'])
        cmd_context = identity_cmdline_context(pid, t_mono, windows)
        leaf = leaf_of(frames)
        leaf_sym, leaf_dso = leaf["symbol"], leaf["dso"]
        frame_quality["inline_recovered_samples"] += int(leaf["inline_recovered"])
        frame_quality["true_unknown_dso_samples"] += int(leaf["unknown_reason"] == "leaf-dso-unknown")
        frame_quality["empty_stack_samples"] += int(leaf["unknown_reason"] == "empty-stack")
        frame_quality["inline_owner_unresolved_samples"] += int(leaf["unknown_reason"] == "inline-owner-not-found-at-same-address")
        unknown_symbol = leaf_sym in ("[unknown]", "[unknown symbol]", "??", "unknown", "")
        frame_quality["unresolved_leaf_symbol_samples"] += int(unknown_symbol)
        frame_quality["inline_recovered_period"] += period if leaf["inline_recovered"] else 0
        frame_quality["true_unknown_dso_period"] += period if leaf["unknown_reason"] == "leaf-dso-unknown" else 0
        frame_quality["empty_stack_period"] += period if leaf["unknown_reason"] == "empty-stack" else 0
        frame_quality["inline_owner_unresolved_period"] += period if leaf["unknown_reason"] == "inline-owner-not-found-at-same-address" else 0
        frame_quality["unresolved_leaf_symbol_period"] += period if unknown_symbol else 0
        rec = {"t": t, "tid": tid, "pid": pid, "comm": comm,
               "period": period, "leaf_sym": leaf_sym, "leaf_dso": leaf_dso,
               "entity_sym": leaf.get("entity_symbol"), "entity_dso": leaf.get("entity_dso"),
               "inline_recovered": leaf["inline_recovered"],
               "unknown_reason": leaf["unknown_reason"],
               "role": role, "cmdline": cmd, "identity_cmdlines": cmd_context,
               "stack": frames[:24]}
        out_fh.write(json.dumps(rec) + "\n")
        kept.append(rec)
    out_fh.close()

    # 4. parallelism from thread CPU counters (ROI window in mono time)
    parallelism = compute_parallelism(mon, loop_start_mono, marker_mono, offset)
    json.dump(parallelism, open(out / "parallelism.json", "w"), indent=2)

    roi = {
        "marker_mono_s": marker_mono,
        "loop_start_mono_s": loop_start_mono,
        "marker_perf_median_s": median_marker,
        "marker_sample_count": len(marker_times),
        "marker_perf_span_s": marker_times[-1] - marker_times[0],
        "alignment_method": "PERFROI sample median mapped to nominal 300ms burn midpoint; stdout monotonic arrival timestamp",
        "alignment_uncertainty": "not independently calibrated; stdout buffering and marker sampling/frequency effects remain unquantified",
        "perf_to_mono_offset_s": offset,
        "loop_start_perf_s": t_loop_start_perf,
        "preloop_excluded_samples": excluded["count"],
        "preloop_excluded_period": excluded["period"],
        "roi_samples": len(kept),
        "roi_period_total": sum(r["period"] for r in kept),
        "perf_script_parse": {**parse_stats, **frame_quality,
            "recognized_samples_total": len(samples),
            "perf_metadata_sample_count": meta.get("total_samples"),
            "unmatched_perf_sample_estimate": (meta.get("total_samples", len(samples)) - len(samples))},
    }
    json.dump(roi, open(out / "roi.json", "w"), indent=2)
    print(json.dumps(roi, indent=2))


def compute_parallelism(mon, loop_start_mono, marker_mono, offset):
    """Thread-CPU-based parallelism inside the ROI (mono-time domain)."""
    prev = {}  # tid -> (utime+stime ticks, t)
    samples = []
    with open(mon / "monitor.jsonl") as fh:
        for line in fh:
            rec = json.loads(line)
            t = rec["t_ns"] / 1e9
            cur = {}
            for pid, tid, tcomm, utime, stime in rec["threads"]:
                cur[tid] = (utime + stime, pid, tcomm)
            if prev:
                active = []
                for tid, (total, pid, tcomm) in cur.items():
                    if tid in prev and total > prev[tid][0]:
                        active.append((tid, pid, tcomm))
                samples.append((t, len(active), active))
            prev = cur
    # keep only polls inside the ROI (mono domain)
    roi = [(t, n, a) for (t, n, a) in samples if t >= loop_start_mono]
    if not roi:
        return {"error": "no ROI polls"}
    total_polls = len(roi)
    hist = {}
    for _, n, _ in roi:
        hist[n] = hist.get(n, 0) + 1
    active_time = sum(n for _, n, _ in roi)
    return {
        "method": "thread utime+stime deltas per monitor poll interval inside the ROI; counts threads whose CPU counters advanced at least once during each interval; this is not simultaneity",
        "poll_intervals": total_polls,
        "single_active_poll_interval_share": hist.get(1, 0) / total_polls,
        "multi_active_poll_interval_share": sum(v for k, v in hist.items() if k > 1) / total_polls,
        "no_active_thread_poll_interval_share": hist.get(0, 0) / total_polls,
        "max_active_threads_in_poll_interval": max(hist) if hist else 0,
        "mean_active_threads_per_poll_interval": active_time / total_polls,
        "active_threads_per_poll_interval_histogram": {str(k): v for k, v in sorted(hist.items())},
    }


if __name__ == "__main__":
    main()
