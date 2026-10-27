#!/usr/bin/env python3
"""Dataset-private final-cache CSV export; no business recomputation or XLSX save."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import tempfile


def same(actual, expected):
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        try:
            value = float(actual)
        except (ValueError, TypeError):
            return False
        return math.isfinite(value) and math.isclose(value, expected, rel_tol=1e-8, abs_tol=1e-6)
    return actual == str(expected)


def rows_from_cache(workspace, contract):
    from openpyxl import load_workbook
    book = load_workbook(Path(workspace) / 'output' / contract['workbook'],
                         data_only=True, read_only=True)
    try:
        sheet = book[contract['sheet']]
        wanted = {a for item in contract['exports'] for row in item['rows'] for a in row['cells']}
        from openpyxl.utils.cell import coordinate_to_tuple
        max_row = max(coordinate_to_tuple(a)[0] for a in wanted)
        max_col = max(coordinate_to_tuple(a)[1] for a in wanted)
        values = {c.coordinate: c.value
                  for row in sheet.iter_rows(max_row=max_row, max_col=max_col)
                  for c in row if getattr(c, 'coordinate', None) in wanted}
        errors = {'#REF!', '#DIV/0!', '#VALUE!', '#N/A', '#NAME?', '#NUM!', '#NULL!'}
        for address in wanted:
            value = values.get(address)
            if value is None or (isinstance(value, str) and value in errors):
                raise ValueError('missing/error cache: ' + address)
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError('non-finite cache: ' + address)
        return [(item['filename'], [item['header']] +
                 [[row['label'], *[values[a] for a in row['cells']]] for row in item['rows']])
                for item in contract['exports']]
    finally:
        book.close()


def validate_csv(workspace, contract):
    for filename, expected in rows_from_cache(workspace, contract):
        with (Path(workspace) / 'output' / filename).open(newline='', encoding='utf-8') as stream:
            actual = list(csv.reader(stream))
        if len(actual) != len(expected) or actual[0] != expected[0]:
            raise ValueError('CSV header/row count mismatch: ' + filename)
        for found, wanted in zip(actual[1:], expected[1:]):
            if len(found) != len(wanted) or any(not same(a, b) for a, b in zip(found, wanted)):
                raise ValueError('CSV cache mismatch: ' + filename + ' ' + str(found))


def export(workspace, contract):
    rows = rows_from_cache(workspace, contract)
    staged = []
    try:
        for filename, content in rows:
            target = Path(workspace) / 'output' / filename
            fd, temp = tempfile.mkstemp(prefix='.' + target.name + '.', dir=target.parent)
            staged.append((Path(temp), target))
            with os.fdopen(fd, 'w', encoding='utf-8', newline='') as stream:
                csv.writer(stream).writerows(content)
        for temp, target in staged:
            os.replace(temp, target)
    finally:
        for temp, _ in staged:
            temp.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    contract = json.loads((root / 'csv-contract.json').read_text())
    (validate_csv if args.check_only else export)(root, contract)


if __name__ == '__main__':
    main()
