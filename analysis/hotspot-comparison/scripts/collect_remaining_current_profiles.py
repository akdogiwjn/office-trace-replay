#!/usr/bin/env python3
"""Continue the initial campaign after preserving the failed Retail attempt.

Only HR and Industry Productivity are listed here. This wrapper intentionally
does not retry Retail or any completed configuration.
"""
import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("collect_current_loop_profiles.py")
spec = importlib.util.spec_from_file_location("current_profile_collector", SCRIPT)
collector = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = collector
spec.loader.exec_module(collector)


def main():
    plan = collector.read(collector.PLAN_PATH)
    manifest_path = collector.CAMPAIGN / "campaign-manifest.json"
    manifest = collector.read(manifest_path)
    failures = list(manifest.get("failures", []))
    configs = {item["config_id"]: item for item in plan["configs"]}
    for config_id in ("hr", "industry_productivity"):
        cfg = configs[config_id]
        print(f"START {config_id} loops={cfg['loops']}", flush=True)
        if not collector.collect_one(plan, cfg, "native"):
            failures.append(config_id + ":native")
            continue
        if not collector.collect_one(plan, cfg, "pyspy"):
            failures.append(config_id + ":pyspy")
    manifest["status"] = "complete_with_failures" if failures else "complete"
    manifest["failures"] = list(dict.fromkeys(failures))
    manifest["continued_configs"] = ["hr", "industry_productivity"]
    collector.write(manifest_path, manifest)
    print(json.dumps({"status": manifest["status"], "failures": manifest["failures"]}, indent=2),
          flush=True)
    return 1 if manifest["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
