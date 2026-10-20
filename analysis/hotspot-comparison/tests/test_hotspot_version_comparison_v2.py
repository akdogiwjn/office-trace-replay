import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/analyze_hotspot_version_v2.py"
spec = importlib.util.spec_from_file_location("hotspot_v2", SCRIPT)
v2 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = v2
spec.loader.exec_module(v2)


def test_native_period_sample_conservation_and_existing_index(tmp_path):
    samples = tmp_path / "samples.jsonl"
    samples.write_text("\n".join([
        json.dumps({"period": 7, "role": "xlsx-verify", "leaf_dso": "/lib/libpython3.12.so",
                    "leaf_sym": "_PyEval_EvalFrameDefault", "entity_sym": "_PyEval_EvalFrameDefault",
                    "entity_dso": "/lib/libpython3.12.so", "stack": []}),
        json.dumps({"period": 11, "role": "xlsx-verify", "leaf_dso": "/lib/libz.so.1",
                    "leaf_sym": "deflate", "entity_sym": "deflate", "entity_dso": "/lib/libz.so.1",
                    "stack": []}),
    ]) + "\n")
    roi = tmp_path / "roi.json"
    roi.write_text(json.dumps({"roi_samples": 2, "roi_period_total": 18, "perf_script_parse": {"headers": 2}}))
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"files": [{"path": "out/samples.jsonl", "sha256": "fixture-hash", "status": "hashed"}]}))
    got = v2.aggregate_sample_jsonl(samples, roi, index, "out/samples.jsonl", "fixture", {}, {})
    assert got["roi_samples"] == 2
    assert got["roi_period"] == 18
    assert math.isclose(sum(got["process_share"].values()), 1.0)
    assert math.isclose(sum(got["library_share"].values()), 1.0)
    assert got["leaf_function_weight_accounting"]["all_leaf_period"] == 18
    assert got["leaf_function_weight_accounting"]["displayed_top30_period"] == 18
    assert got["leaf_function_weight_accounting"]["unlisted_tail_period"] == 0
    assert got["source"]["parsed_samples_sha256"] == "fixture-hash"


def test_script_io_load_lazy_save_partition_and_process_only(tmp_path):
    raw = tmp_path / "fixture.pyspy.raw"
    raw.write_text("\n".join([
        'process 1:"python3 /tmp/inspect_xlsx.py";<module> (inspect_xlsx.py:1);load_workbook (openpyxl/reader/excel.py:10);_cells_by_row (openpyxl/worksheet/_read_only.py:20) 3',
        'process 1:"python3 /tmp/recalc.py";<module> (recalc.py:1);_cells_by_row (openpyxl/worksheet/_read_only.py:20);_get_row (openpyxl/worksheet/_read_only.py:30) 2',
        'process 1:"python3 /tmp/enhance_workbook.py";<module> (enhance_workbook.py:1);save (openpyxl/workbook/workbook.py:10) 4',
        'process 9:"" 5',
        'process 1:"python3 /tmp/verify_office.py";<module> (verify_office.py:1);check_formula (spreadsheet.py:10) 6',
    ]) + "\n")
    result = v2.scriptio_by_role(raw, "xlsx")
    assert result["denominator_samples"] == 20
    assert result["operation_samples"] == {
        "load_call": 3, "lazy_scan": 2, "save": 4, "no_python_frames": 5, "other": 6
    }
    assert result["C_load_union"] == 5 / 20
    assert result["E_load_and_save_union"] == 9 / 20
    assert sum(result["operation_samples"].values()) == result["denominator_samples"]


def test_industry_generated_helper_role_requires_identity_chain():
    sample = {"role": "python-unknown-script",
              "cmdline": "python3 /tmp/.industry_productivity_build.runtime.py",
              "identity_cmdlines": ["python3 /opt/office-trace-replay/compatibility/tools/run_xlsx_helper_atomic.py helpers/industry_productivity_build.py"]}
    assert v2.native_role(sample) == "xlsx-enhance"
    sample["identity_cmdlines"] = ["python3 /tmp/unrelated.py"]
    assert v2.native_role(sample) == "python-unknown-script"


def test_report_json_and_analysis_hash_match_generated_artifacts():
    out = ROOT / "reports/hotspot-version-comparison-v2"
    data = json.loads((out / "comparison.json").read_text())
    assert (out / "comparison-report.md").read_text() == v2.make_report(data)
    build = json.loads((out / "analysis-build.json").read_text())
    assert build["analysis_script_sha256"] == v2.sha(SCRIPT)
    for profile in data["native_profiles"].values():
        assert math.isclose(sum(profile["process_share"].values()), 1.0, abs_tol=1e-6)
        assert math.isclose(sum(profile["library_share"].values()), 1.0, abs_tol=1e-6)
    for cfg in ("historical_tlc", "current_tlc", "retail", "hr", "industry_productivity"):
        x = data["xlsx_load_save"][cfg]
        assert math.isclose(x["C_load_union"], x["A_load_workbook_internal"] + x["B_read_only_lazy_scan"])
        assert math.isclose(x["E_load_and_save_union"], x["C_load_union"] + x["D_workbook_save"])
        assert sum(x["operation_samples"].values()) == x["denominator_samples"]
