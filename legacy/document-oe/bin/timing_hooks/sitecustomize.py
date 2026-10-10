"""Auto-loaded by every python interpreter started with PYTHONPATH pointing here.

Used by run_document_scene_loop_timed.py: patches process spawning inside the
called scripts so that nested child invocations (scripts started inside
run_batch_fill_render.py, soffice inside recalc.py, etc.) are timed and
appended as JSON lines to the file named by DOCUMENT_BENCH_TIMING_LOG.

Covers subprocess.run / check_call / check_output / Popen.wait /
Popen.communicate / os.system, so it works regardless of which spawning API
the wrapped script uses. Does nothing when DOCUMENT_BENCH_TIMING_LOG is unset.
"""

import json
import os
import subprocess
import sys
import time

_LOG = os.environ.get("DOCUMENT_BENCH_TIMING_LOG", "")
_ORIG_INIT = subprocess.Popen.__init__
_ORIG_WAIT = subprocess.Popen.wait
_ORIG_COMMUNICATE = subprocess.Popen.communicate
_ORIG_SYSTEM = os.system


def _label(cmd) -> str:
    try:
        parts = cmd.split() if isinstance(cmd, str) else [str(p) for p in cmd]
        for p in parts:
            if p.endswith(".py"):
                return os.path.basename(p)
        return " ".join(parts)[:80]
    except Exception:
        return str(cmd)[:80]


def _write(started: float, cmd) -> None:
    try:
        with open(_LOG, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "ts": time.time(),
                        "parent": os.path.basename(sys.argv[0]) if sys.argv else "python",
                        "child": _label(cmd),
                        "seconds": round(time.perf_counter() - started, 6),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    except Exception:
        pass


if _LOG:
    def _timed_init(self, *args, **kwargs):
        self._bench_cmd = args[0] if args else kwargs.get("args")
        self._bench_started = time.perf_counter()
        _ORIG_INIT(self, *args, **kwargs)

    def _bench_record(self) -> None:
        if getattr(self, "_bench_done", False):
            return
        self._bench_done = True
        started = getattr(self, "_bench_started", None)
        if started is None:
            return
        _write(started, getattr(self, "_bench_cmd", None))

    def _timed_wait(self, *args, **kwargs):
        try:
            return _ORIG_WAIT(self, *args, **kwargs)
        finally:
            _bench_record(self)

    def _timed_communicate(self, *args, **kwargs):
        try:
            return _ORIG_COMMUNICATE(self, *args, **kwargs)
        finally:
            _bench_record(self)

    def _timed_system(command):
        started = time.perf_counter()
        try:
            return _ORIG_SYSTEM(command)
        finally:
            _write(started, command)

    subprocess.Popen.__init__ = _timed_init
    subprocess.Popen.wait = _timed_wait
    subprocess.Popen.communicate = _timed_communicate
    os.system = _timed_system
