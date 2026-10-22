#!/usr/bin/env python3
"""Freeze the per-dataset input preparation (selection/aggregation) for XLSX workloads.

This is the explicit preparation stage for the manually adapted XLSX datasets
(``hr_metro``, ``retail_online``).  It runs OUTSIDE the measured replay loop and
produces one small frozen JSON artifact (``prepared_selection.json``) that the
enhancement helpers consume instead of rescanning the complete business table
in every iteration.

The selection/aggregation logic is imported from
``scripts/prepare_manual_xlsx_assets.py`` -- the independent oracle
implementation that also produced ``expected.json``.  The enhancement helpers
never import this module, and in formal (non-fixture) mode every prepared
value is cross-checked against the frozen ``expected.json`` before anything is
written, so this entry never generates the expectation and proves itself.

Formal mode additionally binds the artifact through the asset manifest
(``input_files`` + ``preparation`` metadata); regenerating the recipes with
``scripts/compile_compatible.py`` then propagates it into ``seed/input`` and
the runtime source dataset.  The artifact's own hash is recorded only in those
external bindings, never inside the artifact itself.

Safety rules:
  * ``--help`` and argument errors exit before any file is written.
  * Only the explicitly selected datasets are processed.
  * Existing artifacts are never silently overwritten; ``--force`` keeps the
    previous version beside the new file (``prepared_selection.superseded-<sha8>.json``).
  * All writes are atomic (temporary file + ``os.replace``); a failed run
    publishes nothing.
  * Fixture runs (custom ``--input``) may not write inside the formal assets
    tree and must declare themselves with ``--fixture``.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.prepare_manual_xlsx_assets import (  # noqa: E402
    HR_SCOPE, RETAIL_POLICY, select_hr_metro, select_retail_rows)

DATASETS = ('hr_metro', 'retail_online')
ARTIFACT_NAME = 'prepared_selection.json'
ARTIFACT_SCHEMA = 'xlsx-prepared-selection-v1'
WORKLOAD_VERSION = 'manual-workflow-adaptation-v2'
SCRIPT_PATH = 'scripts/prepare_xlsx_selection.py'

# Fixed layout of the retail derived summary sheet written by the helper.  The
# helper reads these anchors from the artifact, and the manifest records the
# same declaration (plus the frozen-content bindings the verifier checks) so
# all consumers share one source of truth.
RETAIL_DERIVED_LAYOUT = {
    'sheet': 'Derived Totals',
    'metric_anchors': {
        'gross_eligible_sales_gbp': 'B4',
        'eligible_line_count': 'B5',
        'eligible_quantity_units': 'B6',
    },
    'metric_value_paths': {
        'gross_eligible_sales_gbp': 'selection.totals.gross_eligible_sales_gbp',
        'eligible_line_count': 'selection.totals.eligible_line_count',
        'eligible_quantity_units': 'selection.totals.eligible_quantity_units',
    },
    'chart_series': {
        'monthly_2010_sales': {
            'value_range': 'B20:B31', 'category_range': 'A20:A31',
            'value_path': 'selection.monthly_2010_sales_gbp',
            'category_dates': {'start': '2010-01-01', 'months': 12},
        },
    },
    'frozen_cells': [
        {'address': 'B9', 'path': 'selection.totals.eligible_lines_missing_customer_id'},
        {'address': 'B11', 'path': 'selection.totals.exclusion_counts.cancelled_invoice'},
        {'address': 'B12', 'path': 'selection.totals.exclusion_counts.missing_invoice'},
        {'address': 'B13', 'path': 'selection.totals.exclusion_counts.nonpositive_quantity'},
        {'address': 'B14', 'path': 'selection.totals.exclusion_counts.nonpositive_unit_price'},
        {'address': 'B15', 'path': 'selection.totals.exclusion_counts.missing_or_invalid_quantity'},
        {'address': 'B16', 'path': 'selection.totals.exclusion_counts.missing_or_invalid_unit_price'},
        {'address': 'B17', 'path': 'selection.totals.exclusion_counts.missing_or_invalid_invoice_date'},
        {'address': 'B18', 'path': 'selection.currency'},
    ],
    'max_rows': 40,
}
RETAIL_DIAGNOSTICS_BINDINGS = {
    'file': 'xlsx_business_diagnostics.json',
    'prepared_selection': 'input/prepared_selection.json',
    'keys': {
        'gross_eligible_sales_gbp': 'selection.totals.gross_eligible_sales_gbp',
        'eligible_line_count': 'selection.totals.eligible_line_count',
        'eligible_quantity_units': 'selection.totals.eligible_quantity_units',
        'eligible_lines_missing_customer_id': 'selection.totals.eligible_lines_missing_customer_id',
        'exclusion_counts': 'selection.totals.exclusion_counts',
        'currency': 'selection.currency',
    },
}
HR_DIAGNOSTICS_BINDINGS = {
    'file': 'xlsx_business_diagnostics.json',
    'prepared_selection': 'input/prepared_selection.json',
    'keys': {
        'area_code': 'selection.scope.AREA',
        'area_title': 'selection.scope.AREA_TITLE',
        'total_row': 'selection.total.row',
        'selected_chart_rows': 'selection.chart_rows[].occupation_code',
        'selected_record_count': 'selection.diagnostics.selected_record_count',
        'major_group_count': 'selection.diagnostics.major_group_count',
        'major_group_suppressed_employment_count':
            'selection.diagnostics.major_group_suppressed_employment_count',
    },
}
HR_SHEET = 'MSA_M2025_dl'
RETAIL_SHEET = 'Online Retail'
HR_COLUMNS = ('AREA', 'AREA_TITLE', 'AREA_TYPE', 'NAICS', 'I_GROUP', 'OWN_CODE',
              'O_GROUP', 'OCC_CODE', 'OCC_TITLE', 'TOT_EMP', 'A_MEAN', 'H_MEDIAN')
HR_KPI_SOURCE = {'total_employment': 'TOT_EMP', 'annual_mean_wage': 'A_MEAN',
                 'hourly_median_wage': 'H_MEDIAN'}
RETAIL_COLUMN_KEYS = ('invoiceno', 'quantity', 'unitprice', 'invoicedate', 'customerid')
RETAIL_EXCLUSION_ORDER = ('cancelled_invoice', 'missing_invoice',
                          'nonpositive_quantity', 'nonpositive_unit_price',
                          'missing_or_invalid_quantity', 'missing_or_invalid_unit_price',
                          'missing_or_invalid_invoice_date')


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _self_sha256():
    return _sha256(Path(__file__))


def _close(left, right):
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-9)
    return left == right


def asset_directory(root, dataset):
    return root / 'assets/cases' / dataset / 'source/datasets/xlsx' / dataset


def _column_letters(headers, names):
    from openpyxl.utils import get_column_letter
    letters = {}
    for name in names:
        try:
            index = headers.index(name)
        except ValueError:
            raise ValueError(f'workbook header row is missing required column {name!r}')
        letters[name] = get_column_letter(index + 1)
    return letters


def prepare_hr_selection(workbook_path):
    """One read-only streaming pass: scope matches with row numbers, frozen once."""
    from openpyxl import load_workbook

    workbook_path = Path(workbook_path)
    wb = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        if HR_SHEET not in wb.sheetnames:
            raise ValueError(f'workbook is missing the {HR_SHEET} worksheet')
        ws = wb[HR_SHEET]
        rows = ws.iter_rows()
        first = next(rows, ())
        if not first:
            raise ValueError('source worksheet is empty')
        headers = [cell.value for cell in first]
        items = []
        for row in rows:
            if not row:
                continue
            values = tuple(cell.value for cell in row)
            item = dict(zip(headers, values))
            item['_row'] = row[0].row
            if (str(item.get('AREA')) == HR_SCOPE['AREA']
                    and str(item.get('AREA_TITLE')) == HR_SCOPE['AREA_TITLE']
                    and str(item.get('AREA_TYPE')) == HR_SCOPE['AREA_TYPE']
                    and str(item.get('NAICS')) == HR_SCOPE['NAICS']
                    and str(item.get('I_GROUP')) == HR_SCOPE['I_GROUP']
                    and str(item.get('OWN_CODE')) == HR_SCOPE['OWN_CODE']):
                items.append(item)
    finally:
        wb.close()

    selected = select_hr_metro(items, headers)
    columns = _column_letters(headers, HR_COLUMNS)
    total = selected['total_row']
    kpis = {}
    for metric, column in HR_KPI_SOURCE.items():
        kpis[metric] = {
            'cell': f"{columns[column]}{total['_row']}",
            'value': selected['metric_values'][metric],
        }
    chart_rows = [{
        'row': row['row'],
        'occupation_code': row['occupation_code'],
        'occupation_title': row['occupation_title'],
        'occupation_title_cell': f"{columns['OCC_TITLE']}{row['row']}",
        'employment_cell': f"{columns['TOT_EMP']}{row['row']}",
        'employment': row['employment'],
    } for row in selected['chart_rows']]
    if any(row['row'] is None for row in chart_rows) or total.get('_row') is None:
        raise ValueError('selection rows are missing worksheet row numbers')
    return {
        'sheet': HR_SHEET,
        'header_row': 1,
        'scope': dict(HR_SCOPE),
        'columns': columns,
        'occupation_rule': ('Use the single O_GROUP=total / OCC_CODE=00-0000 row for total KPIs; '
                            'use only O_GROUP=major rows ranked by TOT_EMP for the comparison chart; '
                            'suppressed employment observations are excluded from ranking and counted.'),
        'total': {
            'row': total['_row'],
            'o_group': 'total',
            'occ_code': str(total.get('OCC_CODE')),
            'occ_title': str(total.get('OCC_TITLE')),
            'kpis': kpis,
        },
        'chart_rows': chart_rows,
        'diagnostics': {
            'selected_record_count': selected['selected_record_count'],
            'major_group_count': selected['major_group_count'],
            'major_group_suppressed_employment_count': selected['major_group_suppressed_employment_count'],
            'suppression_marker_counts': selected['suppression_marker_counts'],
            'counting_method': 'one streaming read_only pass over the original worksheet',
        },
    }


def prepare_retail_selection(workbook_path):
    """One read-only streaming pass: full-period aggregation and the 2010 monthly totals."""
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

    workbook_path = Path(workbook_path)
    wb = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        if RETAIL_SHEET not in wb.sheetnames:
            raise ValueError(f'workbook is missing the {RETAIL_SHEET} worksheet')
        ws = wb[RETAIL_SHEET]
        rows = ws.iter_rows()
        first = next(rows, ())
        if not first:
            raise ValueError('source worksheet is empty')
        headers = [cell.value for cell in first]

        def value_rows():
            for row in rows:
                yield tuple(cell.value for cell in row)

        result = select_retail_rows(headers, value_rows())
    finally:
        wb.close()

    index = {str(name).strip().casefold().replace(' ', ''): i
             for i, name in enumerate(headers) if name is not None}
    columns = {}
    for key in RETAIL_COLUMN_KEYS:
        i = index.get(key, index.get('price') if key == 'unitprice' else None)
        if i is None:
            raise ValueError(f'Online Retail header row is missing the {key} column')
        columns[key] = {'header': str(headers[i]), 'column': get_column_letter(i + 1)}
    monthly = [float(value) for value in result['monthly_2010_sales_gbp']]
    if len(monthly) != 12:
        raise ValueError('monthly 2010 aggregation must produce twelve values')
    return {
        'sheet': RETAIL_SHEET,
        'header_row': 1,
        'columns': columns,
        'row_policy': dict(RETAIL_POLICY),
        'totals': {
            'gross_eligible_sales_gbp': float(result['gross_eligible_sales_gbp']),
            'eligible_line_count': int(result['eligible_line_count']),
            'eligible_quantity_units': float(result['eligible_quantity_units']),
            'eligible_lines_missing_customer_id': int(result['eligible_lines_missing_customer_id']),
            'exclusion_counts': {reason: int(result['exclusion_counts'].get(reason, 0))
                                 for reason in RETAIL_EXCLUSION_ORDER},
            'source_rows': int(result['source_rows']),
        },
        'monthly_2010_sales_gbp': monthly,
        'currency': 'GBP',
        'time_scope': {
            'full_period_kpis': 'All eligible InvoiceDate values across the complete source table.',
            'monthly_chart': 'Native dates from 2010-01-01 inclusive to 2011-01-01 exclusive only; a different time range than the full-period KPIs.',
        },
        'derived_layout': copy.deepcopy(RETAIL_DERIVED_LAYOUT),
        'diagnostics': {
            'distinct_invoice_count': None,
            'distinct_invoice_note': 'InvoiceNo is repeated across lines; not treated as a row count.',
            'counting_method': 'one streaming read_only pass; one transaction line per row; no source rows are removed',
        },
    }


def check_against_expected(dataset, selection, expected):
    """Refuse to publish preparation values that disagree with the frozen oracle."""
    problems = []
    if dataset == 'hr_metro':
        for metric, value in expected['metric_values'].items():
            prepared = selection['total']['kpis'].get(metric, {}).get('value')
            if not _close(prepared, value):
                problems.append(f'{metric}: {prepared!r} != expected {value!r}')
        wanted = expected['chart_values']['major_employment']
        actual = [row['employment'] for row in selection['chart_rows']]
        if len(actual) != len(wanted) or not all(_close(a, b) for a, b in zip(actual, wanted)):
            problems.append(f'chart employment {actual!r} != expected {wanted!r}')
    else:
        for metric, value in expected['metric_values'].items():
            prepared = selection['totals'].get(metric)
            if not _close(prepared, value):
                problems.append(f'{metric}: {prepared!r} != expected {value!r}')
        wanted = expected['chart_values']['monthly_2010_sales']
        actual = selection['monthly_2010_sales_gbp']
        if len(actual) != len(wanted) or not all(_close(a, b) for a, b in zip(actual, wanted)):
            problems.append(f'monthly 2010 totals differ from the frozen oracle')
    if problems:
        raise ValueError('prepared selection disagrees with the frozen expected oracle: '
                         + '; '.join(problems))


def build_artifact(dataset, workbook_path):
    if dataset == 'hr_metro':
        selection = prepare_hr_selection(workbook_path)
    elif dataset == 'retail_online':
        selection = prepare_retail_selection(workbook_path)
    else:
        raise ValueError(f'unsupported dataset: {dataset}')
    return {
        'schema_version': ARTIFACT_SCHEMA,
        'dataset_id': dataset,
        'workload_version': WORKLOAD_VERSION,
        'input_file': Path(workbook_path).name,
        'input_sha256': _sha256(workbook_path),
        'prepared_by': {
            'script': SCRIPT_PATH,
            'script_sha256': _self_sha256(),
            'oracle_module': 'scripts/prepare_manual_xlsx_assets.py',
            'method': ('single read-only streaming pass over the official input; '
                       'independent of the enhancement helper'),
            'checked_against_expected': False,
        },
        'selection': selection,
    }


def _atomic_write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n',
                         encoding='utf-8')
    temporary.replace(path)


def _artifact_already_published(out_path, manifest_path):
    """Early refusal when an artifact exists, before scanning the large input."""
    if out_path.exists() and not Path(manifest_path).exists():
        # Publication writes the artifact and the manifest binding together; a
        # manifest without the binding plus an existing artifact file means a
        # previous run left an unbound file that must not be silently reused.
        return True
    return out_path.exists()


def publish_artifact(out_path, artifact, manifest_path=None, *, force):
    """Publish the artifact with rollback-safe staging.

    Order of operations (the previous active file survives every failure):
      1. refuse an existing output early unless ``--force`` (callers check
         before scanning the large input);
      2. write and validate the new content in a temporary file first;
      3. with ``--force``, copy the previous file to a versioned backup
         (never overwriting an existing backup), keeping the active file;
      4. atomically replace the active file (``os.replace``);
      5. on any failure, remove only files this call created.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not force:
        raise FileExistsError(
            f'{out_path} already exists; pass --force to supersede it '
            '(the previous version is kept as a .superseded-<sha8>.json file)')
    temporary = out_path.with_name('.' + out_path.name + '.staging')
    backup = None
    backup_created = False
    replaced = False
    try:
        # Stage and validate the complete new content before touching anything.
        temporary.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + '\n',
                             encoding='utf-8')
        staged = json.loads(temporary.read_text(encoding='utf-8'))
        if staged != artifact:
            raise ValueError('staged artifact does not round-trip; refusing to publish')
        if out_path.exists():
            backup = out_path.with_name(
                f'{out_path.stem}.superseded-{_sha256(out_path)[:8]}{out_path.suffix}')
            if backup.exists():
                if _sha256(backup) != _sha256(out_path):
                    raise FileExistsError(
                        f'backup {backup} already exists with different content; '
                        'resolve it manually before superseding')
                # A pre-existing identical backup is historical evidence; this
                # call did not create it and must never delete it.
            else:
                backup.write_bytes(out_path.read_bytes())
                backup_created = True
        temporary.replace(out_path)
        replaced = True
        return backup, backup_created
    finally:
        if not replaced and backup_created and backup is not None:
            backup.unlink()
        if temporary.exists():
            temporary.unlink()


def update_asset_manifest(directory, artifact, artifact_path):
    """Bind the artifact and the derived-sheet declaration into the asset manifest.

    Writes the updated manifest atomically; on failure the previous manifest
    stays in place so the caller can roll the artifact back to a consistent
    state.
    """
    manifest_path = Path(directory) / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest = copy.deepcopy(manifest)
    manifest['input_files']['input/' + ARTIFACT_NAME] = _sha256(artifact_path)
    manifest['preparation'] = {
        'artifact': 'input/' + ARTIFACT_NAME,
        'schema_version': ARTIFACT_SCHEMA,
        'workload_version': WORKLOAD_VERSION,
        'script': SCRIPT_PATH,
        'script_sha256': _self_sha256(),
        'input_sha256': artifact['input_sha256'],
        'note': ('Frozen preparation artifact derived once from the official input outside '
                 'the measured loop; formal derived input, not official source data, not an '
                 'Agent answer, and it contains no final script, tool order or formulas.'),
    }
    if artifact['dataset_id'] == 'retail_online':
        manifest['requirements']['derived_sheets'] = {
            RETAIL_DERIVED_LAYOUT['sheet']: {
                'provenance': ('Frozen preparation artifact derived once from the complete '
                               'original Online Retail worksheet; not an official source worksheet.'),
                'prepared_selection': 'input/prepared_selection.json',
                'metric_anchors': dict(RETAIL_DERIVED_LAYOUT['metric_anchors']),
                'metric_value_paths': dict(RETAIL_DERIVED_LAYOUT['metric_value_paths']),
                'chart_series': copy.deepcopy(RETAIL_DERIVED_LAYOUT['chart_series']),
                'frozen_cells': copy.deepcopy(RETAIL_DERIVED_LAYOUT['frozen_cells']),
                'max_rows': RETAIL_DERIVED_LAYOUT['max_rows'],
            },
        }
        manifest['requirements']['diagnostics_bindings'] = copy.deepcopy(RETAIL_DIAGNOSTICS_BINDINGS)
    else:
        manifest['requirements']['diagnostics_bindings'] = copy.deepcopy(HR_DIAGNOSTICS_BINDINGS)
    _atomic_write_json(manifest_path, manifest)
    return manifest


def _inside(path, directory):
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def run_one(root, dataset, args):
    root = Path(root)
    directory = asset_directory(root, dataset)
    fixture_mode = args.input is not None
    if fixture_mode:
        workbook = args.input.resolve()
        if not workbook.is_file():
            raise FileNotFoundError(f'input workbook does not exist: {workbook}')
        out_path = args.output.resolve()
        if _inside(out_path, root / 'assets'):
            raise ValueError('fixture outputs must not be written inside the formal assets tree')
        expected_path = args.expected.resolve() if args.expected else None
    else:
        manifest_path = directory / 'manifest.json'
        if not manifest_path.is_file():
            raise FileNotFoundError(f'asset manifest missing for {dataset}: {manifest_path}')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        workbook = directory / 'input' / manifest['workbook']
        if not workbook.is_file():
            raise FileNotFoundError(f'official input workbook missing: {workbook}')
        recorded = manifest['input_files'].get('input/' + manifest['workbook'])
        actual = _sha256(workbook)
        if recorded != actual:
            raise ValueError(
                f'official input SHA-256 does not match the asset manifest for {dataset}: '
                f'{actual} != {recorded}')
        out_path = directory / 'input' / ARTIFACT_NAME
        expected_path = directory / manifest['expected_file']

    # Refuse an existing artifact BEFORE scanning the large input workbook.
    if out_path.exists() and not args.force:
        raise FileExistsError(
            f'{out_path} already exists; pass --force to supersede it '
            '(the previous version is kept as a .superseded-<sha8>.json file)')

    artifact = build_artifact(dataset, workbook)
    if expected_path is not None:
        expected = json.loads(Path(expected_path).read_text(encoding='utf-8'))
        check_against_expected(dataset, artifact['selection'], expected)
        artifact['prepared_by']['checked_against_expected'] = True

    previous_bytes = out_path.read_bytes() if out_path.exists() else None
    backup = None
    backup_created = False
    published = False
    try:
        backup, backup_created = publish_artifact(out_path, artifact, force=args.force)
        published = True
        if not fixture_mode:
            update_asset_manifest(directory, artifact, out_path)
    except BaseException:
        # Roll the artifact back to its pre-publication state so a manifest
        # failure never leaves an unbound or half-published artifact behind.
        # Only files this call created are cleaned up: a pre-existing
        # identical backup is historical evidence and stays untouched.
        if published:
            if previous_bytes is None:
                out_path.unlink(missing_ok=True)
            else:
                out_path.write_bytes(previous_bytes)
            if backup_created and backup is not None and backup.is_file():
                backup.unlink(missing_ok=True)
        raise
    return {
        'dataset_id': dataset,
        'mode': 'fixture' if fixture_mode else 'formal',
        'input': str(workbook),
        'input_sha256': artifact['input_sha256'],
        'artifact': str(out_path),
        'artifact_sha256': _sha256(out_path),
        'checked_against_expected': artifact['prepared_by']['checked_against_expected'],
        'superseded': str(backup) if backup else None,
        'manifest_updated': not fixture_mode,
    }


def cli(argv=None, root=None):
    root = Path(ROOT if root is None else root)
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog='Formal mode reads the official asset input, cross-checks the frozen '
               'expected.json oracle and binds the artifact into the asset manifest. '
               'Fixture mode (--input) is for small tests and must write outside assets/.')
    parser.add_argument('--dataset', action='append', choices=DATASETS, required=True,
                        help='dataset to prepare (repeatable)')
    parser.add_argument('--input', type=Path,
                        help='custom input workbook (fixture testing only)')
    parser.add_argument('--output', type=Path,
                        help='artifact output path (required with --input)')
    parser.add_argument('--expected', type=Path,
                        help='expected.json used for the formal cross-check '
                             '(default: the asset oracle; required with --input unless --fixture)')
    parser.add_argument('--fixture', action='store_true',
                        help='declare a test run: skip the expected cross-check and '
                             'forbid writes inside the formal assets tree')
    parser.add_argument('--force', action='store_true',
                        help='replace an existing artifact, keeping the previous '
                             'version as a .superseded-<sha8>.json file')
    args = parser.parse_args(argv)
    datasets = list(dict.fromkeys(args.dataset))
    if args.input and len(datasets) > 1:
        parser.error('--input selects one workbook and cannot be combined with multiple --dataset')
    if args.input and not args.output:
        parser.error('--input requires an explicit --output path')
    if args.input and not args.expected and not args.fixture:
        parser.error('--input requires either --expected or an explicit --fixture declaration')
    if not args.input and (args.output or args.expected or args.fixture):
        parser.error('--output/--expected/--fixture only apply to fixture runs with --input')
    results = [run_one(root, dataset, args) for dataset in datasets]
    for item in results:
        print(json.dumps(item, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(cli())
