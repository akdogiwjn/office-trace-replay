#!/usr/bin/env python3
"""Installed-state check inside the replay candidate image.

Runs validate-only (frozen payload + environment) via replay.py and augments it
with perf/soffice/DevKit installed-state facts. It NEVER starts a real workload
or any sampler, including perf record permission probes.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path("/opt/docops")
OUT = Path(os.environ.get("DOC_INSTALL_STATE_OUT", "/workspace/docops/install-state.json"))


def load_replay():
    spec = importlib.util.spec_from_file_location("docops_replay", ROOT / "replay.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    m = load_replay()
    try:
        payload = m.validate_payload(ROOT / "payload")
    except Exception as exc:
        payload = {'status': 'failed', 'error': str(exc)}
    result = {
        "schema": "docops-replay-install-state-check-v1",
        "image": {"actual_id": "unknown",
                  "reported_reference": os.environ.get('DOC_IMAGE_REFERENCE'),
                  "note": "bind actual ID using host docker inspect; environment is not identity proof"},
        "payload": payload,
        "environment": m.check_environment(ROOT / "payload"),
        "extra": {},
    }
    # tool versions
    for tool, args in (("perf", ["--version"]), ("soffice", ["--version"])):
        try:
            cp = subprocess.run([tool, *args], capture_output=True, text=True, timeout=30)
            text = (cp.stdout or cp.stderr).strip()
            result["extra"][tool] = {"present": cp.returncode == 0,
                                     "rc": cp.returncode, "version": text[:200]}
        except Exception as e:
            result["extra"][tool] = {"present": False, "detail": type(e).__name__}
    # DevKit installed-state (no PMU capture)
    devkit_root = Path("/opt/devkit")
    candidates = sorted(devkit_root.glob("*/devkit")) if devkit_root.exists() else []
    devkit_bin = candidates[0] if candidates else None
    result["extra"]["devkit"] = {"present": devkit_bin is not None,
                                 "root": str(devkit_root),
                                 "binary": str(devkit_bin) if devkit_bin else None}
    if devkit_bin is not None:
        devkit_base = devkit_bin.parent
        lib_tuner = devkit_base / "tuner/libtuner.so"
        ld_env = dict(os.environ, LD_LIBRARY_PATH=str(devkit_base / "tuner/lib"))
        try:
            cp = subprocess.run(["devkit", "version"], capture_output=True, text=True,
                                timeout=30, env=ld_env)
            result["extra"]["devkit"]["version"] = (cp.stdout or cp.stderr).strip()
            result["extra"]["devkit"]["version_rc"] = cp.returncode
        except Exception as e:
            result["extra"]["devkit"]["version_error"] = type(e).__name__
        try:
            ldd = subprocess.run(["ldd", str(lib_tuner)],
                                 capture_output=True, text=True, timeout=30,
                                 env=ld_env)
            result["extra"]["devkit"]["libtuner_unresolved"] = sum(
                1 for line in ldd.stdout.splitlines() if "not found" in line)
            result["extra"]["devkit"]["libtuner_ldd_rc"] = ldd.returncode
        except Exception as e:
            result["extra"]["devkit"]["ldd_error"] = type(e).__name__
    # Installation checks never start a sampler, even a short perf record.
    result['errors'] = acceptance_errors(result, m.environment_errors)
    result['status'] = 'passed' if not result['errors'] else 'failed'
    result['perf_capture_validated'] = False
    result['devkit_capture_validated'] = False
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": result['status'], "errors": result['errors'],
                      "payload": result["payload"], "environment": result["environment"],
                      "perf": result["extra"].get("perf"),
                      "devkit": result["extra"].get("devkit"),
                      },
                     indent=2, ensure_ascii=False))
    return 0 if result['status'] == 'passed' else 1


def acceptance_errors(result, environment_errors):
    errors = list(environment_errors(result['environment']))
    if result.get('payload', {}).get('status') != 'static_valid' or result.get('payload', {}).get('tasks') != 12:
        errors.append('installed payload validation failed')
    unified = result['environment'].get('runtime_profile') == 'seven-case-openeuler-unified'
    tool_versions = (('perf', '6.6.0-145.3.23.154'), ('soffice', '25.8.7.3')) if unified else (
        ('perf', '6.1.190'), ('soffice', '7.4.7.2'))
    for tool, version in tool_versions:
        item = result['extra'].get(tool, {})
        if not item.get('present') or item.get('rc') != 0 or version not in item.get('version', ''):
            errors.append(f'{tool}: missing, failed, or wrong version')
    item = result['extra'].get('devkit', {})
    if not item.get('present') or item.get('version_rc') != 0 or '26.0.RC1' not in item.get('version', ''):
        errors.append('DevKit version probe failed')
    if item.get('libtuner_ldd_rc') != 0 or item.get('libtuner_unresolved') != 0:
        errors.append('DevKit private library resolution failed')
    return errors


if __name__ == "__main__":
    sys.exit(main())
