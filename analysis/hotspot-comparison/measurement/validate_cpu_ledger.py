#!/usr/bin/env python3
"""Small synthetic validation of the CPU ledger measurement semantics.

Run with CPU_LEDGER_OUT set, plus this program's own dir importable, e.g.:

    CPU_LEDGER_OUT=/tmp/ledger python3 validate_cpu_ledger.py --json

Checks, each on a synthetic in-memory/temp workbook:

  1. CPU-bound work inside load_workbook/save buckets accrues CPU time.
  2. Sleep inside a bucket does NOT accrue CPU time (blocking excluded).
  3. Lazy read-only iteration counts only generator-side CPU: a consumer that
     sleeps between rows adds nothing to readonly_lazy_parse.
  4. Subprocess CPU shows up in the process's own os.times() children counters
     (the denominator sampler reads the same counters via /proc for the tree).
  5. Nested instrumented intervals de-duplicate: outer == total - inner.

Prints one JSON object with the measured numbers and a pass/fail verdict per
check.  This is a semantics validation only, not a performance result.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

MEASUREMENT_DIR = Path(__file__).resolve().parent


def busy_seconds(seconds):
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        pass


def build_workbook(path, rows):
    from openpyxl import Workbook
    book = Workbook()
    sheet = book.active
    sheet.title = 'S'
    for row in rows:
        sheet.append(row)
    book.save(path)
    book.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    results = {}

    import cpu_ledger
    from openpyxl import Workbook, load_workbook

    # --- 1 + 2: CPU-bound vs sleeping work inside save -------------------
    with tempfile.TemporaryDirectory() as tmp:
        book = Workbook()
        sheet = book.active
        for i in range(200):
            sheet.append([i, i * 2, f'row-{i}'])
        cpu_ledger.LEDGER.enter('workbook_save')
        busy_seconds(0.30)
        time.sleep(0.30)  # blocking: must not accrue
        cpu_ledger.LEDGER.exit('workbook_save')
        save_bucket = cpu_ledger.LEDGER.cpu_ns['workbook_save']
        results['save_cpu_ns'] = save_bucket
        results['check_cpu_accrues'] = 0.20 <= save_bucket / 1e9 <= 0.45
        results['check_sleep_excluded'] = save_bucket / 1e9 < 0.45

    # --- 3: lazy read-only parse excludes consumer time -------------------
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'book.xlsx'
        build_workbook(path, [(i, i) for i in range(2000)])
        cpu_ledger.LEDGER.cpu_ns['readonly_lazy_parse'] = 0
        cpu_ledger.LEDGER.calls['readonly_lazy_parse'] = 0
        cpu_ledger.LEDGER.yields = 0
        book = load_workbook(path, read_only=True)
        try:
            rows = 0
            for row in book['S'].iter_rows(values_only=True):
                rows += 1
                time.sleep(0.0002)  # consumer-side blocking, 2000 * 0.2ms = 0.4s
        finally:
            book.close()
        lazy = cpu_ledger.LEDGER.cpu_ns['readonly_lazy_parse']
        results['readonly_rows'] = cpu_ledger.LEDGER.yields
        results['readonly_cpu_ns'] = lazy
        # generator parse CPU must be far below the 0.4s of consumer sleeps
        results['check_consumer_excluded'] = lazy / 1e9 < 0.10
        results['check_rows_counted'] = cpu_ledger.LEDGER.yields == 2000

    # --- 4: subprocess CPU lands in children counters (sampler source) ---
    before = os.times()
    subprocess.run([sys.executable, '-c',
                    'end = __import__("time").perf_counter() + 0.30\n'
                    'while __import__("time").perf_counter() < end:\n    pass'],
                   check=True)
    after = os.times()
    children_cpu = (after.children_user - before.children_user) \
        + (after.children_system - before.children_system)
    results['children_cpu_seconds'] = children_cpu
    results['check_subprocess_cpu_visible'] = children_cpu >= 0.20

    # --- 5: nested interval de-duplication -------------------------------
    ledger = cpu_ledger.LEDGER
    ledger.cpu_ns['load_workbook'] = 0
    ledger.enter('load_workbook')
    busy_seconds(0.10)
    ledger.enter('readonly_lazy_parse')
    busy_seconds(0.20)
    ledger.exit('readonly_lazy_parse')
    busy_seconds(0.10)
    ledger.exit('load_workbook')
    outer = ledger.cpu_ns['load_workbook']
    inner = ledger.cpu_ns['readonly_lazy_parse']
    results['nested_outer_ns'] = outer
    results['nested_inner_ns'] = inner
    # De-duplication means the buckets never double-count: the inner
    # interval suspends the outer one, so outer covers only its exclusive
    # window, inner its own, and together they cover the total exactly once.
    results['check_nesting_dedup'] = (0.15 <= outer / 1e9 <= 0.28
                                      and 0.15 <= inner / 1e9 <= 0.28
                                      and 0.35 <= (outer + inner) / 1e9 <= 0.50)

    # --- estimate the actual wrapper cost, not just two clock calls -------
    # This excludes XML parsing on purpose: compare the same trivial generator
    # with/without bookkeeping. It is not a whole-workload overhead estimate.
    count = 20_000
    def synthetic_rows():
        yield from range(count)
    start = time.thread_time_ns()
    baseline_sum = sum(synthetic_rows())
    baseline_ns = time.thread_time_ns() - start
    start = time.thread_time_ns()
    wrapped_sum = sum(cpu_ledger._timed_rows(synthetic_rows()))
    wrapped_ns = time.thread_time_ns() - start
    results['check_wrapper_preserves_rows'] = baseline_sum == wrapped_sum
    results['hook_overhead_method'] = 'actual row wrapper minus unwrapped synthetic generator; thread CPU'
    overhead_per_yield = max(0, wrapped_ns - baseline_ns) / count
    results['hook_overhead_ns_per_yield'] = overhead_per_yield

    verdict = all(results[key] for key in results if key.startswith('check_'))
    results['all_checks_passed'] = verdict
    if args.json:
        print(json.dumps(results, indent=1))
    else:
        for key, value in results.items():
            print(f'{key}: {value}')
    return 0 if verdict else 1


if __name__ == '__main__':
    raise SystemExit(main())
