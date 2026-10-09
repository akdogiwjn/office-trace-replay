"""Reviewed selections for exactly the seven imported canonical run IDs.

Indices refer to tool_events.events, NOT ATIF step IDs. The compiler binds every
selection to its original call ID. Shell reductions are explicit and reviewable.
"""
RUNS = {
    'irs_w4': 'pdf-irs_w4-20261009T060857Z-ef1696a0',
    'opm': 'pdf-opm-20261009T060618Z-87cbc811',
    'sba1919': 'pdf-sba1919-20261009T060857Z-b7a0ae3b',
    'hr': 'xlsx-hr-20261009T060833Z-5e454df8',
    'manufacturing': 'xlsx-manufacturing-20261009T101352Z-bd60f53e',
    'retail': 'xlsx-retail-20261009T101352Z-725a21b6',
    'tlc': 'xlsx-tlc-20261009T063937Z-9a06558f',
}

# Each tuple is (source event index, replacement command or None). None retains
# the archived call. Final summaries are emitted from frozen Agent metadata.
SELECTIONS = {
    'irs_w4': [[(8, None), (10, None)], [(13, None)], [(14, None), (15, None), (16, None)],
               [(17, 'python3 input/verify_office.py')]],
    'opm': [[(9, None)], [(12, None)], [(14, None), (16, None)],
            [(17, 'python3 input/verify_pdf_batch.py input/of306_aug2023.pdf input/synthetic_applicants.json output output/business_verification.json')]],
    'sba1919': [[(14, None), (15, None)], [(20, None)], [(23, None), (24, None)],
                [(26, 'python3 helpers/write_summary.py && python3 input/verify_office.py')]],
    'hr': [[(5, None)], [(35, 'python3 helpers/build.py')],
           [(37, 'cd helpers && timeout 220 python3 /root/.openclaw/skills/xlsx/scripts/recalc.py pre_recalc.xlsx 180 > recalc_out.json 2> recalc_err.txt'),
            (38, 'cp helpers/pre_recalc.xlsx helpers/rec_recalc.xlsx && python3 helpers/build.py'),
            (46, 'python3 helpers/patch.py'),
            (44, 'cp helpers/recalc_out.json output/formula_recalc.json')],
           [(54, None), (55, 'python3 input/verify_office.py')]],
    'manufacturing': [[(5, None)], [(22, None)],
                       [(24, None), (32, 'python3 inject_caches.py'), (33, None)],
                       [(36, None), (37, 'python3 input/verify_office.py')]],
    'retail': [[(5, None)], [(30, 'read:helpers/build_enhance.py')],
               [(47, 'bash helpers/run_pipeline.sh'), (41, None)],
               [(54, 'frozen-write:output/xlsx_enhancement_summary.json'), (55, 'python3 input/verify_office.py')]],
    'tlc': [[(10, None)], [(48, 'read:helpers/build_report.py')],
            [(68, 'python3 helpers/run_pipeline.py')],
            [(83, None), (84, 'python3 input/verify_office.py')]],
}

NOTES = {
    'irs_w4': 'The edited build_field_values.py is staged as its captured final version. Successful fill/render calls remain verbatim.',
    'opm': 'Successful prepare, field-value build and batch helper calls retained; read errors and inspection-only listings excluded.',
    'sba1919': 'Successful dry-run, fill/render shell helpers and generated summary writer retained.',
    'hr': 'Preserve the successful in-place recalc -> copy recalculated file -> rebuild pristine base -> final patch sequence. Earlier probe, broken patches and recalc with bad stderr redirection excluded.',
    'manufacturing': 'Pristine build and independent recalculated copy retained. Final edited cache injector replaces the failed initial version.',
    'retail': 'Final run_pipeline.sh executes build, recalc and assembly. Final helper versions selected after fixes; diagnostics and fabricated retrospective diagnostic log excluded.',
    'tlc': 'Compose run_pipeline.py with the final captured injector fixed at event 70 and successfully executed at event 71. This is a derived effective pipeline, not the exact helper bundle at event 68. Earlier preservation probes, debug and repeated polls excluded.',
}
