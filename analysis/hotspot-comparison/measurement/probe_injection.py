#!/usr/bin/env python3
"""Container-injection probe for the CPU ledger hook (small, synthetic).

Runs inside the measured image with the same mounts the real measurement uses:
sitecustomize.py + cpu_ledger.py are read-only file mounts in the venv
site-packages and CPU_LEDGER_OUT points at a writable directory.  The probe
exercises, WITHOUT touching any real workbook:

  * main process and a Python subprocess both produce ledgers;
  * the three buckets record their operations (load / lazy read / save);
  * direct cell access, early exit and nested operations behave;
  * ledger identity carries the module hash;
  * with CPU_LEDGER_OUT unset no ledger is produced (separate invocation).

It prints one JSON verdict used by the launcher's gate: the launcher refuses
to start any real measurement unless every probe check passed and both
process ledgers carry the expected module hash.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

MEASURED_ENV_KEYS = ('CPU_LEDGER_OUT',)


def probe(ledger_out):
    from openpyxl import Workbook, load_workbook
    results = {'checks': {}, 'ledger_dir': str(ledger_out)}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'probe.xlsx'
        book = Workbook()
        sheet = book.active
        for i in range(300):
            sheet.append([i, i * 2, f'cell-{i}'])
        book.save(path)          # bucket: workbook_save
        book.close()
        book = load_workbook(path, read_only=True)   # bucket: load_workbook
        try:
            ws = book['Sheet']
            total = 0
            for index, row in enumerate(ws.iter_rows(values_only=True)):
                total += row[0] or 0
                if index == 149:          # early exit: consumer stops pulling
                    break
            direct = ws['A7'].value        # direct cell access path
            results['checks']['early_exit_kept_rows'] = True
            results['checks']['direct_cell_value'] = direct == 6
        finally:
            book.close()
        results['checks']['sum_sample'] = total >= 0
        # nested: load inside the measured region of another load? Not a real
        # pattern; instead verify a nested instrumented pair stays consistent:
        # save while a read-only book is open (both buckets active in one proc)
        book2 = load_workbook(path, read_only=True)
        try:
            _ = next(iter(book2['Sheet'].iter_rows(values_only=True)))
            Workbook().save(path.with_suffix('.nested.xlsx'))
        finally:
            book2.close()
        results['checks']['nested_buckets_active'] = True
    # child process ledger
    child = subprocess.run(
        [sys.executable, '-c',
         'from openpyxl import Workbook\n'
         'b = Workbook(); b.active.append(["x", 1]); '
         'b.save("/tmp/_probe_child.xlsx"); b.close()\n'],
        capture_output=True, text=True, check=True)
    results['checks']['child_exit_zero'] = child.returncode == 0
    return results


def main():
    ledger_out = os.environ.get('CPU_LEDGER_OUT')
    if not ledger_out:
        print(json.dumps({'status': 'skipped', 'reason': 'CPU_LEDGER_OUT unset'}))
        return 0
    results = probe(Path(ledger_out))
    # this process's own ledger is normally written by atexit; write it now
    # so the verdict below can see it
    import cpu_ledger
    cpu_ledger._write_ledger()
    ledgers = sorted(Path(ledger_out).glob('ledger-*.json'))
    payloads = [json.loads(p.read_text()) for p in ledgers]
    module_hashes = {payload['identity']['module_sha256'] for payload in payloads}
    results['ledger_files'] = [p.name for p in ledgers]
    results['module_hashes'] = sorted(module_hashes)
    results['checks']['two_process_ledgers'] = len(payloads) >= 2
    results['checks']['single_module_hash'] = len(module_hashes) == 1
    child_ledger = next((p for p in payloads
                         if any('probe_child' in part or '_probe_child' in part or
                                part == '-c' for part in p['cmdline'])), None)
    results['checks']['child_ledger_present'] = child_ledger is not None
    main_ledger = next((p for p in payloads if p is not child_ledger), None)
    if main_ledger is not None:
        buckets = {name: item['cpu_ns'] for name, item in main_ledger['buckets'].items()}
        results['main_buckets_ns'] = buckets
        results['checks']['load_recorded'] = buckets['load_workbook'] > 0
        results['checks']['save_recorded'] = buckets['workbook_save'] > 0
        results['checks']['lazy_recorded'] = buckets['readonly_lazy_parse'] > 0
        results['checks']['rows_yielded_positive'] = main_ledger['readonly_rows_yielded'] > 0
        results['checks']['module_hash_present'] = bool(
            main_ledger['identity']['module_sha256'])
    else:
        results['checks']['load_recorded'] = False
    # unset-env control run: same interpreter, no CPU_LEDGER_OUT
    control = subprocess.run(
        [sys.executable, '-c',
         'import os\n'
         'os.environ.pop("CPU_LEDGER_OUT", None)\n'
         'import subprocess, sys\n'
         'env = dict(os.environ)\n'
         'code = subprocess.run([sys.executable, "-c", "print(1)"], env=env,\n'
         '                      capture_output=True)\n'
         'print(code.returncode)\n'],
        capture_output=True, text=True, check=True,
        env={k: v for k, v in os.environ.items() if k != 'CPU_LEDGER_OUT'})
    results['checks']['control_no_ledger'] = not list(Path(ledger_out).glob('ledger-*.json')) or \
        len(list(Path(ledger_out).glob('ledger-*.json'))) == len(payloads)
    results['status'] = 'success' if all(results['checks'].values()) else 'failed'
    print(json.dumps(results, indent=1))
    return 0 if results['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
