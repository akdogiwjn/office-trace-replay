import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, BASE / "scripts" / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

native = load("parse_native", "parse_native.py")
profiles = load("build_profiles", "build_profiles.py")
analysis = load("analyze_comparison", "analyze_comparison.py")
residuals = load("analyze_unconfirmed_residuals", "analyze_unconfirmed_residuals.py")

def frame(addr, symbol, dso, inline=False):
    return {"address": addr, "symbol": symbol, "raw_symbol": symbol,
            "dso": dso, "inline": inline}

class ParserTests(unittest.TestCase):
    def test_residual_priority_accepts_only_strong_reference_stack_prefix(self):
        stack = [frame(str(i), symbol, "libpython.so") for i, symbol in enumerate(
            ("pymalloc_alloc", "caller_one", "caller_two", "caller_three"))]
        sig = profiles.stack_prefix_fingerprint(stack)["fingerprint"]
        row = {"pid": 10, "role": "python", "leaf_sym": "pymalloc_alloc",
               "leaf_dso": "libpython.so", "stack": stack, "period": 7}
        result = residuals.classify_residual_sample(
            row, direct_path_matched=False, reference_mechanisms=set(),
            reference_fingerprints={sig}, reference_leaf_functions=set())
        self.assertEqual(result["category"], "R1")

    def test_unresolved_inline_frame_is_not_a_strong_stack_prefix(self):
        stack = [frame("a", "pymalloc_alloc", "inlined", True),
                 frame("b", "caller_one", "libpython.so"),
                 frame("c", "caller_two", "libpython.so"),
                 frame("d", "caller_three", "libpython.so")]
        self.assertEqual(profiles.stack_prefix_fingerprint(stack)["status"],
                         "weak-unknown-frame")

    def test_residual_leaf_match_requires_resolved_leaf_and_no_prefix_match(self):
        stack = [frame(str(i), symbol, "libpython.so") for i, symbol in enumerate(
            ("PyDict_Next", "different_a", "different_b", "different_c"))]
        sig = residuals.leaf_signature("PyDict_Next", "libpython")
        row = {"pid": 10, "role": "python", "leaf_sym": "PyDict_Next",
               "leaf_dso": "libpython.so", "stack": stack, "period": 3}
        result = residuals.classify_residual_sample(
            row, direct_path_matched=False, reference_mechanisms={"M-PY-GC"},
            reference_fingerprints=set(), reference_leaf_functions={sig})
        self.assertEqual(result["category"], "R2")
        unknown = dict(row, leaf_sym="[unknown]", leaf_dso="[unknown]",
                       stack=[frame("1", "[unknown]", "[unknown]")])
        unknown_sig = residuals.leaf_signature("[unknown]", "unknown")
        result = residuals.classify_residual_sample(
            unknown, direct_path_matched=False, reference_mechanisms=set(),
            reference_fingerprints=set(), reference_leaf_functions={unknown_sig})
        self.assertEqual(result["category"], "R5")

    def test_residual_categories_are_mutually_exclusive_and_period_conserves(self):
        def sample(pid, sym, dso, stack, period=10):
            return {"pid": pid, "role": "python", "leaf_sym": sym,
                    "leaf_dso": dso, "stack": stack, "period": period}
        def stack_for(symbol, tail):
            return [frame(str(i), name, "libpython.so") for i, name in enumerate([symbol] + tail)]
        strong_stack = stack_for("pymalloc_alloc", ["a", "b", "c"])
        r2_stack = stack_for("PyDict_Next", ["d", "e", "f"])
        r3_stack = [frame(str(i), name, "libz.so") for i, name in enumerate(
            ["deflate_fast", "a", "b", "c"])]
        r4_stack = stack_for("_PyRuntimeNoSpecificRule", ["a", "b", "c"])
        rows = [
            sample(1, "ordinary", "libc.so", [frame("1", "ordinary", "libc.so")]),  # A
            sample(2, "_PyGCHead_NEXT", "libpython.so", stack_for("_PyGCHead_NEXT", ["a", "b", "c"])),  # B
            sample(3, "pymalloc_alloc", "libpython.so", strong_stack),  # R1
            sample(4, "PyDict_Next", "libpython.so", r2_stack),  # R2
            sample(5, "deflate_fast", "libz.so", r3_stack),  # R3
            sample(6, "_PyRuntimeNoSpecificRule", "libpython.so", r4_stack),  # R4
            sample(7, "[unknown]", "[unknown]", [frame("7", "[unknown]", "[unknown]")]),  # R5
        ]
        reference_sig = profiles.stack_prefix_fingerprint(strong_stack)["fingerprint"]
        ref_leaf = residuals.leaf_signature("PyDict_Next", "libpython")
        result = residuals.decompose_repeat(
            rows, total_period=70, reference_mechanisms={"M-PY-GC"},
            reference_fingerprints={reference_sig}, reference_leaf_functions={ref_leaf},
            direct_pids={1})
        self.assertEqual(result["residual_period"], 50)
        self.assertEqual(result["category_period"], {"R1": 10, "R2": 10, "R3": 10, "R4": 10, "R5": 10})
        self.assertEqual(result["diagnostics"]["quality_reason"]["unknown-dso-and-symbol"], 10)

    def test_repeat_merge_is_period_weighted_and_conserves_categories(self):
        merged = residuals.merge_repeat_category_weights({
            "r1": {"roi_period": 100, "residual_period": 20, "category_period": {"R1": 20}},
            "r2": {"roi_period": 50, "residual_period": 10, "category_period": {"R1": 10}},
        })
        self.assertEqual(merged["roi_period"], 150)
        self.assertEqual(merged["residual_period"], 30)
        self.assertAlmostEqual(merged["roi_share"]["R1"], .2)
        self.assertAlmostEqual(merged["residual_share"]["R1"], 1.0)

    def test_residual_display_threshold_is_applied_after_repeat_merge_and_keeps_remainder(self):
        row_a = {"role": "xlsx-verify", "leaf_symbol": "often_once", "mechanism": "M-PY-GC"}
        row_b = {"role": "xlsx-enhance", "leaf_symbol": "small", "mechanism": "M-PY-ALLOC"}
        merged = residuals._merged_contributors_from_maps(
            {"a": 7, "b": 4}, {"a": row_a, "b": row_b}, {},
            total_period=1000, residual_period=100)
        self.assertEqual([x["leaf_symbol"] for x in merged["top_contributors"]], ["often_once"])
        self.assertEqual(merged["below_threshold_period"], 4)
        self.assertEqual(merged["all_contributors_period"], 11)
        self.assertEqual(merged["largest_contributors_all"][-1]["leaf_symbol"], "small")

    def test_cpp_symbol_spaces_and_frame_fields(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "samples.txt"
            p.write_text("worker 12 1.000: 99 cycles:u:\n    7f00 Foo::bar() const (libx.so)\n\n")
            parsed, stats = native.parse_samples(p)
            self.assertEqual(parsed[0][4][0]["symbol"], "Foo::bar() const")
            self.assertEqual(parsed[0][4][0]["address"], "7f00")
            self.assertEqual(stats["headers"], 1)

    def test_single_inline_frame_restores_same_address_dso(self):
        leaf = native.leaf_of([frame("a1", "normal_nameLength", "inlined", True),
                               frame("a1", "storeAtts", "pyexpat.so")])
        self.assertEqual(leaf["symbol"], "normal_nameLength")
        self.assertEqual(leaf["entity_symbol"], "storeAtts")
        self.assertEqual(leaf["dso"], "pyexpat.so")
        self.assertTrue(leaf["inline_recovered"])

    def test_multiple_inline_frames_resolve_entity_dso_and_keep_inner_leaf(self):
        leaf = native.leaf_of([frame("bb", "pymalloc_alloc", "inlined", True),
                               frame("bb", "_PyObject_Malloc", "inlined", True),
                               frame("bb", "PyObject_Malloc", "inlined", True),
                               frame("bb", "gc_alloc", "inlined", True),
                               frame("bb", "_PyObject_GC_New", "libpython.so")])
        self.assertEqual(leaf["symbol"], "pymalloc_alloc")
        self.assertEqual(leaf["entity_symbol"], "_PyObject_GC_New")
        self.assertEqual(leaf["dso"], "libpython.so")

    def test_unknown_leaf_does_not_inherit_different_address_caller(self):
        leaf = native.leaf_of([frame("a1", "[unknown]", "[unknown]"),
                               frame("b2", "caller", "libknown.so")])
        self.assertEqual(leaf["dso"], "[unknown]")
        self.assertEqual(leaf["unknown_reason"], "leaf-dso-unknown")

    def test_inline_expansion_is_one_sample_period(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "samples.txt"
            p.write_text("w 1 1.000: 123 cycles:u:\n    aa inner (inlined)\n    aa outer (libx.so)\n\n")
            rows, _ = native.parse_samples(p)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][3], 123)
            resolved = native.leaf_of(rows[0][4])
            self.assertEqual(resolved["dso"], "libx.so")

    def test_strace_errors_and_no_errors_rows_and_total_validation(self):
        text = """% time seconds usecs/call calls errors syscall
------ ------- ----------- ----- ------ -------
50.00 1.000 10 12 2 futex
50.00 1.000 20 8 read
100.00 2.000 15 20 2 total
"""
        parsed = profiles.parse_strace_summary(text)
        self.assertEqual(parsed["total_calls"], 20)
        self.assertEqual(parsed["calls_sum"], 20)
        self.assertTrue(parsed["calls_total_matches"])
        self.assertEqual(parsed["calls_ranked"][0]["syscall"], "futex")
        self.assertEqual(parsed["futex_call_share"], 12 / 20)
        self.assertEqual(parsed["futex_time_share"], .5)
        self.assertEqual(len(parsed["rows"]), 2)
        self.assertIsNone(parsed["rows"][1]["errors"])

    def test_real_retail_strace_count_and_time_match_reference(self):
        raw = (BASE / "tests/fixtures/retail-syscalls.txt").read_text()
        parsed = profiles.parse_strace_summary(raw)
        self.assertTrue(parsed["calls_total_matches"])
        self.assertAlmostEqual(parsed["futex_call_share"], 692512 / 1784034, places=7)
        self.assertAlmostEqual(parsed["futex_time_share"], 876.696429 / 990.813566, places=5)

    def test_perf_csv_empty_unit_event_is_valid_and_not_supported_is_distinct(self):
        events = profiles.parse_perf_stat_csv("# comment\n100,,cycles:u,1000,50.00,,\n<not supported>,,cycles:k,0,0.00,,\n")
        self.assertEqual(events["cycles:u"]["status"], "valid")
        self.assertEqual(events["cycles:u"]["value"], 100)
        self.assertEqual(events["cycles:u"]["unit"], "")
        self.assertEqual(events["cycles:k"]["status"], "not_supported")

    def test_all_14_legacy_slice_ids_have_explicit_script_mapping(self):
        with open(BASE / "legacy/legacy-slices.json") as f:
            legacy = json.load(f)
        ids = {s["slice_id"] for group in ("pdf_slices", "xlsx_slices") for s in legacy[group]}
        self.assertEqual(ids, set(profiles.LEGACY_SCRIPT_TOKENS))
        self.assertEqual(len(ids), 14)

    def test_all_14_slices_resolve_from_executed_script_paths(self):
        pdf_root = "/root/.openclaw/skills/pdf/scripts/"
        xlsx_root = "/root/.openclaw/skills/xlsx/scripts/"
        workspace_pdf = "/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01"
        workspace_xlsx = "/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01"
        cases = {
            "PDF-S1": (f"python3 {pdf_root}check_fillable_fields.py input/form.pdf", "pdf"),
            "PDF-S2": (f"python3 {pdf_root}extract_form_field_info.py input/form.pdf", "pdf"),
            "PDF-S3": (f"python3 {pdf_root}convert_pdf_to_images.py input/blank_form.pdf output/template", "pdf"),
            "PDF-S4": (f"python3 {pdf_root}fill_fillable_fields.py input/form.pdf", "pdf"),
            "PDF-S5": (f"python3 {pdf_root}convert_pdf_to_images.py output/filled/applicant_01.pdf output/rendered/applicant_01", "pdf"),
            "PDF-S6": (f"cd {workspace_pdf} && python3 input/verify_pdf_batch.py input/form.pdf input/applicants.json output", "pdf"),
            "X-S1": ("python3 /opt/document-bench/bin/inspect_xlsx_structure.py input.xlsx", "xlsx"),
            "X-S2": ("python3 /opt/document-bench/bin/inspect_xlsx_features.py input.xlsx", "xlsx"),
            "X-S3": (f"cd {workspace_xlsx} && python3 enhance_workbook.py input.xlsx", "xlsx"),
            "X-S4": (f"python3 {xlsx_root}recalc.py input.xlsx", "xlsx"),
            "X-S5": (f"cd {workspace_xlsx} && python3 inspect_xlsx_formulas.py input.xlsx", "xlsx"),
            "X-S6": (f"cd {workspace_xlsx} && python3 inspect_xlsx_cached_values.py input.xlsx", "xlsx"),
            "X-S7": (f"cd {workspace_xlsx} && python3 input/verify_xlsx_enhanced.py input.xlsx", "xlsx"),
            "X-S8": ("python3 /opt/document-bench/bin/write_xlsx_summary.py input.xlsx", "xlsx"),
        }
        for sid, (cmd, scene) in cases.items():
            with self.subTest(slice_id=sid):
                self.assertIn(sid, profiles.match_legacy_slices(cmd, scene))

    def test_direct_path_requires_actual_script_token_not_shared_role(self):
        self.assertIn("X-S7", profiles.match_legacy_slices(
            "python3 /opt/document-bench/xlsx/input/verify_xlsx_enhanced.py report.xlsx", "xlsx"))
        self.assertIn("PDF-S1", profiles.match_legacy_slices(
            "/bin/bash -c cd /root/.openclaw/skills/pdf && python3 scripts/check_fillable_fields.py x.pdf", "pdf"))
        self.assertNotIn("X-S7", profiles.match_legacy_slices(
            "python3 verify_new_workbook.py report.xlsx", "xlsx"))

    def test_same_basename_outside_frozen_root_and_cat_are_not_direct_execution(self):
        self.assertEqual(profiles.match_legacy_slices(
            "python3 /tmp/other/inspect_xlsx_structure.py input.xlsx", "xlsx"), [])
        self.assertEqual(profiles.match_legacy_slices(
            "/bin/bash -c cat /root/.openclaw/workspace/input/verify_xlsx_enhanced.py", "xlsx"), [])

    def test_path_mechanism_intersection_union_and_period_conservation(self):
        records = [
            {"period": 20, "mechanism": "M-XLSX-LOAD", "direct_path": True},
            {"period": 30, "mechanism": "M-UNCLASSIFIED", "direct_path": True},
            {"period": 50, "mechanism": "M-ORCH", "direct_path": False},
        ]
        result = profiles.coverage_partition(records)
        self.assertEqual(result["total_period"], 100)
        self.assertEqual(result["direct_period"], 50)
        self.assertEqual(result["mechanism_covered_period"], 20)
        self.assertEqual(result["intersection_period"], 20)
        self.assertEqual(result["union_period"], 50)
        self.assertEqual(result["path_only_period"], 30)
        self.assertEqual(result["mechanism_only_period"], 0)
        self.assertEqual(sum(result["mechanism_period"].values()), 100)

    def test_unknown_native_sample_stays_unclassified_even_in_old_script_role(self):
        mechanism, evidence = profiles.role_mechanism("xlsx-verify", "unknown", "check")
        self.assertEqual(mechanism, "M-UNCLASSIFIED")
        self.assertEqual(evidence, "unknown-dso")

    def test_unresolved_symbol_with_known_dso_is_not_covered(self):
        mechanism, evidence = profiles.role_mechanism("xlsx-verify", "expat-xml", "[unknown]")
        self.assertEqual(mechanism, "M-UNCLASSIFIED")
        self.assertEqual(evidence, "unknown-symbol")

    def test_frozen_directory_in_data_argument_is_not_script_source(self):
        self.assertEqual(profiles.match_legacy_slices(
            "python3 /tmp/other/recalc.py /root/.openclaw/skills/xlsx/scripts/anything.xlsx",
            "xlsx"), [])

    def test_relative_script_is_resolved_from_explicit_cwd(self):
        cwd = "/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01"
        cmd = "python3 inspect_xlsx_formulas.py output/monthly_operations_report.xlsx"
        self.assertIn("X-S5", profiles.match_legacy_slices(cmd, "xlsx", cwd=cwd, config="tlc"))
        inv = profiles.extract_python_invocations(cmd, cwd)[0]
        self.assertEqual(inv["resolved_script"], cwd + "/inspect_xlsx_formulas.py")

    def test_frozen_operation_command_reconstructs_relative_script_cwd(self):
        invocation = profiles.extract_python_invocations(
            "python3 scripts/extract_form_field_info.py "
            "/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/input/of306_aug2023.pdf "
            "/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/output/form_field_info.json")[0]
        resolved = profiles.resolve_invocation_context(invocation, "pdf")
        self.assertEqual(resolved["cwd"], "/root/.openclaw/skills/pdf")
        self.assertEqual(resolved["resolved_script"],
                         "/root/.openclaw/skills/pdf/scripts/extract_form_field_info.py")
        self.assertEqual(resolved["cwd_resolution"]["evidence_grade"],
                         "reconstructed from frozen operation command")
        sid, source = profiles._slice_by_script_path(resolved["resolved_script"], "pdf",
                                                     resolved["cwd"], "opm-n10")
        self.assertEqual(sid, "PDF-S2")
        self.assertTrue(source["repository_source_hash_verified"])
        self.assertFalse(source["runtime_hash_recorded"])
        self.assertEqual(source["origin"], "docker-installed-legacy")

    def test_filled_pdf_converter_is_not_also_reported_as_template_candidate(self):
        cmd = ("python3 /root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py "
               "/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/output/filled/applicant_01.pdf "
               "/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/output/rendered/applicant_01")
        self.assertIn("PDF-S5", profiles.match_legacy_slices(cmd, "pdf"))
        self.assertNotIn("PDF-S3", profiles.match_legacy_slices(cmd, "pdf"))
        self.assertFalse(any(x["slice_id"] == "PDF-S3" for x in
                             profiles.legacy_script_candidates(cmd, "pdf")))

    def test_relative_workspace_verifier_resolves_through_old_tlc_seed(self):
        cwd = "/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01"
        cmd = "python3 input/verify_xlsx_enhanced.py output/report.xlsx"
        self.assertIn("X-S7", profiles.match_legacy_slices(cmd, "xlsx", cwd=cwd, config="tlc"))
        sid, source = profiles._slice_by_script_path(cwd + "/input/verify_xlsx_enhanced.py",
                                                     "xlsx", cwd, "tlc")
        self.assertEqual(sid, "X-S7")
        self.assertEqual(source["origin"], "runner-seed-copy")
        self.assertTrue(source["repository_source_hash_verified"])

    def test_opm_seeded_verifier_and_skill_use_installed_legacy_sources(self):
        cwd = "/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01"
        sid, seed = profiles._slice_by_script_path(cwd + "/input/verify_pdf_batch.py", "pdf", cwd, "opm-n1")
        self.assertEqual(sid, "PDF-S6")
        self.assertEqual(seed["origin"], "runner-seed-copy")
        skill_sid, skill = profiles._slice_by_script_path(
            "/root/.openclaw/skills/xlsx/scripts/recalc.py", "xlsx", config="retail")
        self.assertEqual(skill_sid, "X-S4")
        self.assertEqual(skill["origin"], "docker-installed-legacy")
        self.assertEqual(skill["frozen_source_sha256"],
                         profiles.json.loads((BASE / "legacy/slice-source-hashes.json").read_text())["X-S4"]["frozen_source_sha256"])

    def test_source_snapshot_same_basename_is_not_used_as_runtime_content(self):
        sid, source = profiles._slice_by_script_path(
            "/root/.openclaw/skills/xlsx/scripts/recalc.py", "xlsx", config="manufacturing")
        self.assertEqual(sid, "X-S4")
        self.assertEqual(source["repository_path"], "legacy/document-oe/skills/xlsx/scripts/recalc.py")
        snapshot = BASE.parent.parent / "compatibility/cases/manufacturing/source/vendor/skills/xlsx/scripts/recalc.py"
        self.assertNotEqual(profiles.hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                            source["source_sha256"])

    def test_recipe_write_after_seed_overrides_final_source_and_real_conflict_rejected(self):
        path = "/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01/input/verify_xlsx_enhanced.py"
        original = (BASE.parent.parent / "legacy/document-oe/xlsx/input/verify_xlsx_enhanced.py").read_text()
        sid, source = profiles._slice_by_script_path(path, "xlsx", config="tlc",
                                                     recipe_writes={path: original + "# changed\n"})
        self.assertIsNone(sid)
        self.assertEqual(source["origin"], "recipe-written")
        self.assertIn("differs", source["reason"])

    def test_recipe_written_exact_frozen_content_can_be_verified_without_runtime_hash_claim(self):
        path = "/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01/input/verify_xlsx_enhanced.py"
        original = (BASE.parent.parent / "legacy/document-oe/xlsx/input/verify_xlsx_enhanced.py").read_text()
        sid, source = profiles._slice_by_script_path(path, "xlsx", config="tlc",
                                                     recipe_writes={path: original})
        self.assertEqual(sid, "X-S7")
        self.assertEqual(source["origin"], "recipe-written")
        self.assertFalse(source["runtime_hash_recorded"])

    def test_relative_legacy_source_chain_records_frozen_hash_without_runtime_hash_claim(self):
        cwd = "/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01"
        evidence = profiles.legacy_match_evidence(
            "python3 inspect_xlsx_formulas.py output/book.xlsx", "xlsx", cwd=cwd, config="tlc")
        row = next(x for x in evidence if x["slice_id"] == "X-S5")
        self.assertEqual(row["source"]["frozen_source_sha256"],
                         "d73007133f7389edad1229fc4c6e904d127cd2839dd0e672b3d740207f42419a")
        self.assertTrue(row["source"]["repository_source_hash_verified"])
        self.assertNotIn("executed_file_sha256", row)

    def test_same_basename_from_different_root_does_not_match(self):
        self.assertEqual(profiles.match_legacy_slices("python3 /tmp/recalc.py report.xlsx", "xlsx"), [])

    def test_parent_command_mentions_do_not_contaminate_unrelated_child(self):
        self.assertEqual(profiles.match_legacy_slices(
            "python3 /tmp/new_verifier.py report.xlsx", "xlsx",
            ancestor_cmdlines=["python3 /opt/document-bench/bin/inspect_xlsx_structure.py input.xlsx"],
            config="retail"), [])

    def test_recalc_scope_uses_timestamped_ppid_and_keeps_identity_window(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "identity.jsonl"
            events = [
                {"pid": 10, "ppid": 1, "t_ns": 100,
                 "cmdline": "/bin/bash -c cd /root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01 && python3 /root/.openclaw/skills/xlsx/scripts/recalc.py output/book.xlsx 600"},
                {"pid": 11, "ppid": 10, "t_ns": 110, "cmdline": "/usr/lib/libreoffice/program/soffice.bin --headless"},
                {"pid": 20, "ppid": 1, "t_ns": 120, "cmdline": "/usr/bin/other-helper unrelated"},
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in events))
            scoped, direct, _ = profiles.legacy_process_scope_index(path, "xlsx", None)
            self.assertIn("X-S4", {x["slice_id"] for x in direct[10]})
            child = next(x for x in scoped[11] if x["slice_id"] == "X-S4")
            self.assertEqual(child["process_pid"], 11)
            self.assertEqual(child["process_ppid"], 10)
            self.assertEqual(child["identity_first_t_ns"], 110)
            self.assertEqual(child["cwd_resolution"]["evidence_grade"],
                             "cwd recovered from timestamped parent shell argv")
            self.assertNotIn(20, scoped)

    def test_python_native_symbols_are_classified_by_function_evidence(self):
        expected = {
            "_PyEval_EvalFrameDefault": "M-PY-INTERPRETER",
            "Py_INCREF": "M-PY-REFCOUNT",
            "_PyGCHead_NEXT": "M-PY-GC",
            "pymalloc_alloc": "M-PY-ALLOC",
            "PyDict_Next": "M-PY-CONTAINER",
            "PyType_IsSubtype": "M-PY-TYPECHECK",
        }
        for symbol, mechanism in expected.items():
            with self.subTest(symbol=symbol):
                result = profiles.classify_native_mechanism(
                    "xlsx-verify", "libpython", symbol,
                    [{"symbol": symbol}, {"symbol": "caller"}])
                self.assertEqual(result["mechanism"], mechanism)
                self.assertEqual(result["native_status"], "known-native-mechanism")

    def test_native_mechanism_can_be_known_while_python_business_operation_is_unknown(self):
        result = profiles.classify_native_mechanism(
            "xlsx-verify", "libpython", "_PyEval_EvalFrameDefault",
            [{"symbol": "_PyEval_EvalFrameDefault"}, {"symbol": "PyEval_EvalCode"}])
        self.assertEqual(result["mechanism"], "M-PY-INTERPRETER")
        self.assertEqual(result["upper_operation"], "unknown")

    def test_generic_interpreter_evidence_does_not_name_specific_business_operation(self):
        result = profiles.classify_native_mechanism(
            "xlsx-enhance", "libpython", "_PyEval_EvalFrameDefault",
            [{"symbol": "_PyEval_EvalFrameDefault"}, {"symbol": "PyEval_EvalCode"}])
        self.assertNotIn(result["upper_operation"], ("XLSX load", "XLSX traversal", "XLSX save"))

    def test_leaf_mechanism_is_not_overridden_by_container_caller(self):
        result = profiles.classify_native_mechanism("xlsx-inspect-tool", "libpython",
            "_PyEval_EvalFrameDefault", [frame("a", "_PyEval_EvalFrameDefault", "libpython.so"),
                                           frame("b", "list_sort_impl", "libpython.so")])
        self.assertEqual(result["mechanism"], "M-PY-INTERPRETER")
        self.assertEqual(result["context_mechanisms"][0]["context_mechanism"], "M-PY-CONTAINER")
        self.assertTrue(result["context_conflict"])

    def test_allocation_leaf_is_not_overridden_by_refcount_caller(self):
        result = profiles.classify_native_mechanism("python", "libpython", "pymalloc_alloc",
            [frame("a", "pymalloc_alloc", "libpython.so"), frame("b", "Py_DECREF", "libpython.so")])
        self.assertEqual(result["mechanism"], "M-PY-ALLOC")
        self.assertIn("M-PY-REFCOUNT", [x["context_mechanism"] for x in result["context_mechanisms"]])

    def test_container_leaf_and_gc_caller_remain_separate(self):
        result = profiles.classify_native_mechanism("python", "libpython", "list_sort_impl",
            [frame("a", "list_sort_impl", "libpython.so"), frame("b", "_PyGCHead_NEXT", "libpython.so")])
        self.assertEqual(result["mechanism"], "M-PY-CONTAINER")
        self.assertIn("M-PY-GC", [x["context_mechanism"] for x in result["context_mechanisms"]])

    def test_set_substring_in_ordinary_name_does_not_trigger_container_rule(self):
        result = profiles.classify_native_mechanism("python", "libpython", "asset_setup_context",
            [frame("a", "asset_setup_context", "libpython.so"), frame("b", "PyEval_EvalCode", "libpython.so")])
        self.assertEqual(result["mechanism"], "M-PY-RUNTIME-OTHER")
        self.assertNotIn("M-PY-CONTAINER", [x["context_mechanism"] for x in result["context_mechanisms"]])

    def test_inline_leaf_mechanism_keeps_entity_library_and_period_is_single(self):
        result = profiles.classify_native_mechanism("python", "libpython", "pymalloc_alloc",
            [frame("a", "pymalloc_alloc", "inlined", True), frame("a", "_PyObject_Malloc", "libpython.so")])
        self.assertEqual(result["mechanism"], "M-PY-ALLOC")
        leaf = native.leaf_of([frame("a", "pymalloc_alloc", "inlined", True),
                               frame("a", "_PyObject_Malloc", "libpython.so")])
        self.assertEqual(profiles.dso_class(leaf["dso"]), "libpython")

    def test_old_context_precedence_impact_is_measured_as_diagnostic_only(self):
        stack = [frame("a", "_PyEval_EvalFrameDefault", "/opt/python/libpython3.12.so"),
                 frame("b", "list_sort_impl", "/opt/python/libpython3.12.so")]
        current = profiles.classify_native_mechanism("python", "libpython", "_PyEval_EvalFrameDefault", stack)
        old = profiles.legacy_context_sensitive_mechanism("libpython", "_PyEval_EvalFrameDefault", stack)
        self.assertEqual(current["mechanism"], "M-PY-INTERPRETER")
        self.assertEqual(old, "M-PY-CONTAINER")
        context = current["context_mechanisms"][0]
        self.assertEqual(context["stack_depth"], 2)
        self.assertEqual(context["confidence"], "contextual")

    def test_zlib_direction_uses_leaf_not_conflicting_caller(self):
        stack = [frame("a", "inflate_fast", "/lib/libz.so"),
                 frame("b", "deflate", "/lib/libz.so")]
        current = profiles.classify_native_mechanism("python", "zlib", "inflate_fast", stack)
        self.assertEqual(current["mechanism"], "M-ZIP-DECOMPRESS")
        self.assertIn("M-ZIP-COMPRESS", [x["context_mechanism"] for x in current["context_mechanisms"]])
        self.assertEqual(profiles.legacy_context_sensitive_mechanism("zlib", "inflate_fast", stack),
                         "M-ZIP-COMPRESS")

    def test_stack_prefix_fingerprint_quality_depth_and_prefix_difference(self):
        good = [frame(str(i), f"fn{i}", "libpython.so") for i in range(10)]
        a = profiles.stack_prefix_fingerprint(good)
        b = profiles.stack_prefix_fingerprint(good[:1] + [frame(str(i), f"other{i}", "libpython.so") for i in range(1, 10)])
        self.assertEqual(a["status"], "strong")
        self.assertEqual(a["depth_used"], 8)
        self.assertEqual(a["configured_depth"], 8)
        self.assertNotEqual(a["fingerprint"], b["fingerprint"])
        short = profiles.stack_prefix_fingerprint(good[:2])
        self.assertEqual(short["status"], "weak-short-stack")
        unknown = profiles.stack_prefix_fingerprint([frame("a", "[unknown]", "[unknown]")])
        self.assertEqual(unknown["status"], "weak-unknown-frame")

    def test_coverage_against_old_selected_slice_preserves_intersection_union_and_partition(self):
        baseline = {"repeats": {"r1": {"execution_path_layer": {
            "slice_mechanism_period": {"X-S1": {"M-PY-ALLOC": 60, "M-PY-GC": 40}},
            "slice_stack_prefix_fingerprints": {"X-S1": {"sig-a": 100}},
            "slice_leaf_function_period": {"X-S1": {json.dumps({"leaf":"PyObject_Malloc","dso_class":"libpython"}):100}}}}}}
        current = {"repeats": {"r1": {
            "total_period": 100,
            "direct_path_share": .3,
            "mechanism_layer": {"M-PY-ALLOC": .4, "M-PY-GC": .2, "M-ZIP-COMPRESS": .1},
            "execution_path_layer": {"direct_mechanism_period": {
                "M-PY-ALLOC": 10, "M-PY-GC": 20},
                "stack_prefix_fingerprint_period": {"sig-a": 25},
                "leaf_function_period": {json.dumps({"leaf":"PyObject_Malloc","dso_class":"libpython"}):20}},
        }}}
        reference = analysis.legacy_slice_reference({"tlc": baseline}, "retail")
        result = analysis.coverage_for("retail", current, reference)["merged"]
        self.assertAlmostEqual(result["mechanism_evidence_share"], .6)
        self.assertAlmostEqual(result["path_mechanism_intersection_share"], .3)
        self.assertAlmostEqual(result["coverage_union_share"], .6)
        self.assertAlmostEqual(result["normalized_stack_prefix_fingerprint_match_share"], .25)
        self.assertAlmostEqual(result["same_leaf_function_share"], .2)
        self.assertAlmostEqual(result["path_only_share"] + result["mechanism_only_share"] +
                               result["path_mechanism_intersection_share"],
                               result["coverage_union_share"])

    def test_documented_legacy_lo_mechanism_without_matched_slice_samples_stays_candidate(self):
        baseline = {"repeats": {"r1": {"total_period": 100,
            "mechanism_layer": {"M-PY-INTERPRETER": 1.0},
            "native_mechanism_status_layer": {}, "function_layer": [],
            "execution_path_layer": {"slice_mechanism_period": {
                "X-S1": {"M-PY-INTERPRETER": 100}},
                "slice_stack_prefix_fingerprints": {"X-S1": {"sig-old": 100}}}}}}
        current = {"repeats": {"r1": {"total_period": 100,
            "direct_path_share": 0.0,
            "mechanism_layer": {"M-LIBREOFFICE-NATIVE": .2, "M-PY-INTERPRETER": .8},
            "native_mechanism_status_layer": {"known-native-mechanism": 1.0},
            "execution_path_layer": {"direct_mechanism_period": {},
                                     "stack_prefix_fingerprint_period": {"sig-new": 100}},
            "function_layer": [{"role": "soffice.bin", "dso_class": "libreoffice",
                "dso": "libmergedlo.so", "symbol": "FormulaEngine", "entity_symbol": None,
                "entity_dso": None, "mechanism": "M-LIBREOFFICE-NATIVE",
                "upper_operation": "unknown", "native_status": "known-native-mechanism",
                "share_of_roi": .2, "direct_path_matched": False,
                "dominant_stack_prefix_fingerprint": "sig-new", "context_mechanisms": [],
                "top_callstack": []}]}}}
        profiles_data = {"tlc": baseline, "retail": current}
        reference = analysis.legacy_slice_reference(profiles_data, "retail")
        coverage = analysis.coverage_for("retail", current, reference)["merged"]
        self.assertEqual(coverage["mechanism_evidence_share"], .8)
        self.assertEqual(coverage["documented_legacy_mechanism_without_matched_slice_samples_share"], .2)
        hotspots = analysis.new_hotspots(profiles_data, write_outputs=False)
        row = next(x for x in hotspots if x["config"] == "retail")
        self.assertEqual(row["classification"],
                         "candidate-documented-legacy-mechanism-without-matched-slice-samples")

    def test_poll_metric_names_do_not_claim_simultaneity(self):
        renamed = native.rename_poll_metrics({"multi_active_share": .2,
            "peak_parallelism": 30, "method": "old label"})
        self.assertEqual(renamed["multi_active_poll_interval_share"], .2)
        self.assertEqual(renamed["max_active_threads_in_poll_interval"], 30)
        self.assertNotIn("peak_parallelism", renamed)
        self.assertIn("not simultaneity", renamed["method"])

    def test_one_repeat_hotspot_uses_zero_for_absent_repeat(self):
        merged = analysis.merge_function_weights(
            {"r1": {"f": .01}, "r2": {}}, {"r1": 100, "r2": 100})
        self.assertEqual(merged["f"], .005)

    def test_claim_control_selection_respects_pdf_scale_and_workload_scope(self):
        self.assertEqual(analysis.same_environment_control("irs_w4-n1"), "opm-n1")
        self.assertEqual(analysis.same_environment_control("sba1919-n10"), "opm-n10")
        self.assertEqual(analysis.same_environment_control("retail"), "tlc")
        self.assertIsNone(analysis.same_environment_control("unknown"))

if __name__ == "__main__":
    unittest.main()
