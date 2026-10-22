#!/usr/bin/env python3
"""Prepare frozen metadata/oracles for the two manually adapted XLSX inputs.

Each source workbook is opened once in read-only mode. The enhancement helpers
are separate implementations and do not import the oracle code in this file.
"""
from collections import Counter, defaultdict
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREA_CODE = '35620'
AREA_TITLE = 'New York-Newark-Jersey City, NY-NJ'
HR_SCOPE = {
    'AREA': AREA_CODE, 'AREA_TITLE': AREA_TITLE, 'AREA_TYPE': '4',
    'NAICS': '000000', 'I_GROUP': 'cross-industry', 'OWN_CODE': '1235',
}
RETAIL_POLICY = {
    'row_unit': 'one source transaction line; InvoiceNo is not unique per row',
    'currency': 'GBP, as stated for UnitPrice in the Online Retail dataset convention; no FX conversion',
    'eligible_sales': 'InvoiceNo is not blank after trimming ASCII spaces and is not prefixed C; Quantity and UnitPrice are native numeric cells greater than zero; InvoiceDate is a numeric Excel date serial in the valid range 1..2958465 (date-like text is excluded)',
    'cancellations': 'InvoiceNo beginning C (case-insensitive) excluded from positive-sales metrics',
    'returns': 'Quantity <= 0 excluded from positive-sales metrics; original rows remain unchanged',
    'price': 'UnitPrice <= 0 excluded; original values remain unchanged',
    'missing_fields': 'Blank InvoiceNo after ASCII-space trimming, nonnumeric/missing Quantity or UnitPrice, and nonnumeric/out-of-range/missing InvoiceDate are excluded from positive-sale metrics; missing CustomerID is retained and counted diagnostically',
    'invoice_metric': 'distinct InvoiceNo identifiers among eligible lines, not a count of unique orders or customers',
    'monthly_chart': 'eligible gross line sales for native dates from 2010-01-01 inclusive to 2011-01-01 exclusive; full-period KPIs use all eligible dates',
}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def is_suppressed(value):
    return isinstance(value, str) and value.strip().upper() in {'N', 'N.A.', 'NA', '*', '**', '#', '~'}


def as_number(value):
    if isinstance(value, bool) or value is None or is_suppressed(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _extent_tracker():
    return {'declared': [0, 0], 'row': 0, 'col': 0, 'populated': 0,
            'row_boundary': [], 'col_boundary': []}


def _track_cell(extent, cell):
    value = cell.value
    if value is None or value == '':
        return
    extent['populated'] += 1
    row, col = cell.row, cell.column
    if row > extent['row']:
        extent['row'] = row
        extent['row_boundary'] = [cell.coordinate]
    elif row == extent['row'] and len(extent['row_boundary']) < 2:
        extent['row_boundary'].append(cell.coordinate)
    else:
        if row == extent['row'] and extent['row_boundary'][-1] != cell.coordinate:
            extent['row_boundary'][-1] = cell.coordinate
    if col > extent['col']:
        extent['col'] = col
        extent['col_boundary'] = [cell.coordinate]
    elif col == extent['col'] and len(extent['col_boundary']) < 2:
        extent['col_boundary'].append(cell.coordinate)
    elif col == extent['col'] and extent['col_boundary'][-1] != cell.coordinate:
        extent['col_boundary'][-1] = cell.coordinate


def _complexity(path, sheet_stats):
    sheets = []
    for stat in sheet_stats:
        sheets.append({
            'name': stat['name'], 'used_cell_count': stat['populated_cell_count'],
            'populated_cell_count': stat['populated_cell_count'],
            'row_count': stat['effective_data_range'][0],
            'column_count': stat['effective_data_range'][1],
            'formula_count': stat['formula_count'], 'cross_sheet_formula_count': 0,
            'styled_cell_count': None, 'merged_ranges': [], 'chart_count': stat['chart_count'],
            'merged_range_count': 0,
            'declared_dimension': stat['declared_dimension'],
            'effective_data_range': stat['effective_data_range'],
            'counting_method': 'single openpyxl read_only populated-value pass; blank/style-only cells excluded',
        })
    return {
        'schema_version': 'office-workbook-complexity-v1', 'input_sha256': sha256(path),
        'file_size_bytes': Path(path).stat().st_size,
        'compressed_xlsx_size_bytes': Path(path).stat().st_size,
        'sheet_count': len(sheets), 'sheets': sheets,
        'used_cell_count': sum(x['used_cell_count'] for x in sheets),
        'populated_cell_count': sum(x['populated_cell_count'] for x in sheets),
        'formula_count': sum(x['formula_count'] for x in sheets), 'chart_count': sum(x['chart_count'] for x in sheets),
        'style_count': None, 'merged_range_count': 0, 'has_shared_strings': None,
        'cross_sheet_formula_count': 0,
        'counting_method': 'single openpyxl read_only value pass; dimensions describe populated values, not styled cells',
    }


def _base_requirements(sheet_stats):
    names = [s['name'] for s in sheet_stats]
    details = {}
    dimensions = {}
    for stat in sheet_stats:
        name = stat['name']
        dimensions[name] = stat['effective_data_range']
        details[name] = {
            'declared_dimension': stat['declared_dimension'],
            'serialized_cell_range': stat['effective_data_range'],
            'effective_data_range': stat['effective_data_range'],
            'effective_range_method': 'preparation-time read_only populated-value extent',
            'boundary_cells': stat['boundary_cells'],
        }
    return {'base_sheets': names, 'base_dimensions': dimensions,
            'base_dimension_details': details, 'raw_sheets': names,
            'empty_strings_policy': {'sheets': [],
                'rule': 'No source empty-string values are task inputs; source blanks are preserved.'}}


def select_hr_metro(rows, headers):
    """Independent OEWS selection: one exact metro total and major rows only.

    ``rows`` may be sequences zipped against ``headers`` (oracle passes) or
    pre-built dicts optionally carrying a ``_row`` worksheet row number; the
    preparation entry uses the latter to freeze cell coordinates without a
    second scan implementation.
    """
    def as_item(row):
        return dict(row) if isinstance(row, dict) else dict(zip(headers, row))

    selected = []
    for row in rows:
        item = as_item(row)
        if (str(item.get('AREA')) == AREA_CODE
                and str(item.get('AREA_TITLE')) == AREA_TITLE
                and str(item.get('AREA_TYPE')) == HR_SCOPE['AREA_TYPE']
                and str(item.get('NAICS')) == HR_SCOPE['NAICS']
                and str(item.get('I_GROUP')) == HR_SCOPE['I_GROUP']
                and str(item.get('OWN_CODE')) == HR_SCOPE['OWN_CODE']):
            selected.append(item)
    totals = [r for r in selected if r.get('O_GROUP') == 'total' and r.get('OCC_CODE') == '00-0000']
    if len(totals) != 1:
        raise ValueError(f'expected one selected MSA total row, found {len(totals)}')
    total = totals[0]
    metrics = {
        'total_employment': as_number(total.get('TOT_EMP')),
        'annual_mean_wage': as_number(total.get('A_MEAN')),
        'hourly_median_wage': as_number(total.get('H_MEDIAN')),
    }
    if any(value is None for value in metrics.values()):
        raise ValueError('selected official MSA total contains a suppressed required KPI')
    majors = [r for r in selected if r.get('O_GROUP') == 'major']
    numeric = [(as_number(row.get('TOT_EMP')), row) for row in majors]
    eligible = [(value, row) for value, row in numeric if value is not None]
    eligible.sort(key=lambda pair: (-pair[0], str(pair[1].get('OCC_CODE'))))
    top = eligible[:5]
    if len(top) < 5:
        raise ValueError('fewer than five unsuppressed major-group employment rows')
    suppression_counts = Counter()
    for row in selected:
        for field in ('TOT_EMP', 'A_MEAN', 'A_MEDIAN', 'H_MEAN', 'H_MEDIAN'):
            if is_suppressed(row.get(field)):
                suppression_counts[field] += 1
    return {
        'area_code': AREA_CODE, 'area_title': AREA_TITLE,
        'selected_record_count': len(selected), 'total_row': total,
        'metric_values': metrics,
        'chart_rows': [{'occupation_code': str(row['OCC_CODE']),
                        'occupation_title': str(row['OCC_TITLE']),
                        'employment': int(value),
                        'row': row.get('_row')}
                       for value, row in top],
        'major_group_count': len(majors),
        'major_group_suppressed_employment_count': sum(value is None for value, _ in numeric),
        'suppression_marker_counts': dict(suppression_counts),
    }


def _matches_hr_scope(row, headers):
    item = dict(zip(headers, row))
    return (str(item.get('AREA')) == AREA_CODE
            and str(item.get('AREA_TITLE')) == AREA_TITLE
            and str(item.get('AREA_TYPE')) == HR_SCOPE['AREA_TYPE']
            and str(item.get('NAICS')) == HR_SCOPE['NAICS']
            and str(item.get('I_GROUP')) == HR_SCOPE['I_GROUP']
            and str(item.get('OWN_CODE')) == HR_SCOPE['OWN_CODE'])


def _date_value(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool) and 1 <= value <= 2958465:
        from openpyxl.utils.datetime import from_excel
        converted = from_excel(value)
        if isinstance(converted, datetime):
            return converted.date()
        if isinstance(converted, date):
            return converted
    # Match Excel's serial gate; text that resembles a date is excluded.
    return None


def retail_line_decision(invoice, quantity, unit_price, invoice_date):
    """Return eligibility/reason without mutating or normalizing source data."""
    invoice_text = '' if invoice is None else str(invoice).strip(' ')
    if not invoice_text:
        return False, 'missing_invoice'
    if invoice_text.upper().startswith('C'):
        return False, 'cancelled_invoice'
    q = quantity if isinstance(quantity, (int, float)) and not isinstance(quantity, bool) else None
    price = unit_price if isinstance(unit_price, (int, float)) and not isinstance(unit_price, bool) else None
    if q is None:
        return False, 'missing_or_invalid_quantity'
    if q <= 0:
        return False, 'nonpositive_quantity'
    if price is None:
        return False, 'missing_or_invalid_unit_price'
    if price <= 0:
        return False, 'nonpositive_unit_price'
    parsed_date = _date_value(invoice_date)
    if parsed_date is None:
        return False, 'missing_or_invalid_invoice_date'
    return True, parsed_date


def select_retail_rows(headers, rows):
    index = {str(name).strip().casefold().replace(' ', ''): i for i, name in enumerate(headers)}
    invoice_i = index.get('invoiceno')
    quantity_i = index.get('quantity')
    price_i = index.get('unitprice', index.get('price'))
    date_i = index.get('invoicedate')
    customer_i = index.get('customerid')
    if None in (invoice_i, quantity_i, price_i, date_i):
        raise ValueError(f'Online Retail headers missing required fields: {headers!r}')
    sales = 0.0
    eligible_lines = eligible_units = 0
    invoices = set()
    monthly_2010 = [0.0] * 12
    reason_counts = Counter()
    missing_customer_eligible = 0
    source_rows = 0
    for row in rows:
        if not row or all(value is None for value in row):
            continue
        source_rows += 1
        invoice = row[invoice_i] if invoice_i < len(row) else None
        quantity = row[quantity_i] if quantity_i < len(row) else None
        price = row[price_i] if price_i < len(row) else None
        invoice_date = row[date_i] if date_i < len(row) else None
        eligible, reason = retail_line_decision(invoice, quantity, price, invoice_date)
        if not eligible:
            reason_counts[reason] += 1
            continue
        q, p = float(quantity), float(price)
        amount = q * p
        sales += amount
        eligible_lines += 1
        eligible_units += q
        invoices.add(str(invoice).strip())
        if customer_i is not None and (customer_i >= len(row) or row[customer_i] is None):
            missing_customer_eligible += 1
        if reason.year == 2010:
            monthly_2010[reason.month - 1] += amount
    return {
        'source_rows': source_rows,
        'gross_eligible_sales_gbp': sales, 'eligible_line_count': eligible_lines,
        'eligible_quantity_units': eligible_units, 'distinct_invoice_ids': invoices,
        'monthly_2010_sales_gbp': monthly_2010,
        'exclusion_counts': dict(reason_counts),
        'eligible_lines_missing_customer_id': missing_customer_eligible,
    }


def _make_manifest(dataset_id, workbook_name, output_name, input_hash, prompt_hash,
                   source_scope, requirements, task, analysis_metadata):
    return {
        'schema_version': 'office-dataset-v2',
        'workload_contract': 'spreadsheet-semantic-v3',
        'loop_verification_contract': 'document-oe-compatible-xlsx-loop-v1',
        'kind': 'xlsx', 'dataset_id': dataset_id, 'domain': dataset_id,
        'task': task, 'workbook': workbook_name, 'output_workbook': output_name,
        'input_files': {'input/' + workbook_name: input_hash},
        'expected_file': 'expected.json',
        'prompt_template': 'xlsx.txt', 'prompt_template_sha256': prompt_hash,
        'runtime_case': 'OFFICE-XLSX-' + dataset_id.upper().replace('_', '-'),
        'requirements': requirements,
        'publish_files': [],
        'trace_rules': [{'pattern': r'\bverify_office\.py\b', 'operation': 'verify_business'},
                        {'pattern': 'recalc\.py', 'operation': 'recalculate_formulas'}],
        'required_outputs': [output_name, 'workbook_features.json', 'formula_recalc.json',
                             'business_verification.json', 'xlsx_enhancement_summary.json'],
        'analysis_metadata': analysis_metadata,
        'analysis_scope': source_scope,
        'origin_type': 'manual_workflow_adaptation', 'agent_generated': False,
        'requires_llm': False,
    }


def prepare_hr(path, out_dir, prompt_hash):
    from openpyxl import load_workbook
    path, out_dir = Path(path), Path(out_dir)
    wb = load_workbook(path, read_only=True, data_only=True)
    stats, selected_rows, headers = [], [], None
    try:
        for ws in wb.worksheets:
            extent = _extent_tracker()
            extent['declared'] = [ws.max_row or 0, ws.max_column or 0]
            iterator = ws.iter_rows()
            first = next(iterator, ())
            sheet_headers = [cell.value for cell in first]
            for cell in first:
                _track_cell(extent, cell)
            if ws.title == 'MSA_M2025_dl':
                headers = sheet_headers
                for row in iterator:
                    for cell in row:
                        _track_cell(extent, cell)
                    values = tuple(cell.value for cell in row)
                    if _matches_hr_scope(values, headers):
                        selected_rows.append(values)
            else:
                for row in iterator:
                    for cell in row:
                        _track_cell(extent, cell)
            stats.append({'name': ws.title, 'declared_dimension': extent['declared'],
                          'effective_data_range': [extent['row'], extent['col']],
                          'populated_cell_count': extent['populated'], 'formula_count': 0,
                          'chart_count': 0,
                          'boundary_cells': sorted(set(extent['row_boundary'] + extent['col_boundary']))})
    finally:
        wb.close()
    selected = select_hr_metro(selected_rows, headers)
    digest = sha256(path)
    complexity = _complexity(path, stats)
    expected = {
        'schema_version': 'office-semantic-oracle-v2',
        'metric_values': selected['metric_values'],
        'scenario_values': {
            'Base': {'projected_mean_wage': selected['metric_values']['annual_mean_wage']},
            'Increase': {'projected_mean_wage': selected['metric_values']['annual_mean_wage'] * 1.05},
        },
        'chart_values': {'major_employment': [row['employment'] for row in selected['chart_rows']]},
        'oracle_provenance': 'Independent one-pass selection from the source MSA rows; total and major occupation groups are kept distinct; no suppressed marker is converted to zero.',
    }
    summary = {'dataset_id': 'hr_metro', 'input_sha256': digest,
               'selection': HR_SCOPE, 'area_title': selected['area_title'],
               'selected_record_count': selected['selected_record_count'],
               'selected_total_occupation_code': str(selected['total_row']['OCC_CODE']),
               'selected_total_values': selected['metric_values'],
               'major_group_count': selected['major_group_count'],
               'major_group_suppressed_employment_count': selected['major_group_suppressed_employment_count'],
               'top_major_groups': selected['chart_rows'],
               'suppression_marker_counts': selected['suppression_marker_counts'],
               'counting_method': 'one streaming read_only pass over the original worksheet'}
    provenance = _provenance('hr_metro', path, digest, 'BLS MSA May 2025 OEWS-style workbook; exact acquisition URL/source not independently verified in this repository.',
                             'hr', 'compatibility/recipes/hr.json',
                             'compatibility/helpers/hr_build.py')
    for name, value in [('complexity.json', complexity), ('expected.json', expected),
                        ('content-summary.json', summary), ('provenance.json', provenance)]:
        _write(out_dir / name, value)
    req = _hr_requirements(stats)
    req['empty_strings_policy'] = {
        'sheets': ['MSA_M2025_dl'],
        'rule': 'Only empty-string cells in the confirmed source table MSA_M2025_dl may normalize to blank during openpyxl serialization; nonempty values, formulas and suppression markers remain exact.'}
    manifest = _make_manifest('hr_metro', path.name, 'hr_metro_enhanced.xlsx', digest,
                              prompt_hash, {
        'area_code': AREA_CODE, 'area_name': AREA_TITLE,
        'area_type': '4 (metropolitan statistical area)',
        'filters': HR_SCOPE,
        'occupation_rule': 'Use the single O_GROUP=total / OCC_CODE=00-0000 row for total KPIs; use only O_GROUP=major rows for the comparison chart; do not combine major/detailed rows with the total.',
        'suppression_policy': 'Retain all source markers verbatim. Required total KPI cells must be numeric; suppressed major employment observations are excluded from ranking and counted, never replaced with zero.',
    }, req,
       'Analyze May 2025 employment and wages for one explicitly selected metropolitan area using its official all-occupations total and major occupation groups.',
       {'complexity.json': sha256(out_dir / 'complexity.json'),
        'content-summary.json': sha256(out_dir / 'content-summary.json'),
        'provenance.json': sha256(out_dir / 'provenance.json')})
    manifest['expected_sha256'] = sha256(out_dir / 'expected.json')
    manifest['required_outputs'].append('xlsx_business_diagnostics.json')
    _write(out_dir / 'manifest.json', manifest)
    return {'manifest': manifest, 'expected': expected, 'summary': summary}


def _hr_requirements(stats):
    req = {
        'summary_sheet': 'Metro Summary', 'metrics': [
            {'id': 'total_employment', 'name': 'Employment, all occupations',
             'meaning': 'Published estimate from the selected MSA all-occupations total row.', 'unit': 'employees'},
            {'id': 'annual_mean_wage', 'name': 'Annual mean wage, all occupations',
             'meaning': 'Published estimate from the same selected MSA total row; not an average of occupation wages.', 'unit': 'USD per year'},
            {'id': 'hourly_median_wage', 'name': 'Hourly median wage, all occupations',
             'meaning': 'Published median from the same selected MSA total row; occupation medians are not averaged.', 'unit': 'USD per hour'},
        ],
        'scenario': {'default': 'Base', 'dimensions': [{'id': 'wage_multiplier',
            'meaning': 'Illustrative multiplier applied to published annual mean wage; not a forecast.'}],
            'rows': [{'name': 'Base', 'assumptions': {'wage_multiplier': 1.0}},
                     {'name': 'Increase', 'assumptions': {'wage_multiplier': 1.05}}],
            'projections': [{'id': 'projected_mean_wage',
                'meaning': 'Selected MSA published mean wage multiplied by the chosen scenario assumption.',
                'unit': 'USD per year'}]},
        'charts': [{'id': 'major_employment',
            'meaning': 'Five largest unsuppressed major occupation groups for the same selected metro and all-industry/all-ownership scope.',
            'unit': 'employees'}],
        'minimum_comments': 2, 'minimum_conditional_formats': 2,
        'minimum_formula_count': 8, 'recalc_timeout': 600,
    }
    req.update(_base_requirements(stats))
    return req


def prepare_retail(path, out_dir, prompt_hash):
    from openpyxl import load_workbook
    path, out_dir = Path(path), Path(out_dir)
    wb = load_workbook(path, read_only=True, data_only=True)
    stats, source_sheets = [], []
    aggregate = {'gross_eligible_sales_gbp': 0.0, 'eligible_line_count': 0,
                 'eligible_quantity_units': 0.0, 'distinct_invoice_ids': set(),
                 'monthly_2010_sales_gbp': [0.0] * 12,
                 'exclusion_counts': Counter(), 'eligible_lines_missing_customer_id': 0}
    try:
        for ws in wb.worksheets:
            extent = _extent_tracker()
            extent['declared'] = [ws.max_row or 0, ws.max_column or 0]
            rows = ws.iter_rows()
            header_cells = next(rows, ())
            headers = [c.value for c in header_cells]
            for cell in header_cells:
                _track_cell(extent, cell)
            if not headers or not any(str(v).strip().casefold() == 'invoiceno' for v in headers if v is not None):
                # Preserve and size non-transaction worksheets without applying
                # transaction filters to them.
                for row in rows:
                    for cell in row:
                        _track_cell(extent, cell)
                stats.append({'name': ws.title, 'declared_dimension': extent['declared'],
                              'effective_data_range': [extent['row'], extent['col']],
                              'populated_cell_count': extent['populated'], 'formula_count': 0,
                              'chart_count': 0,
                              'boundary_cells': sorted(set(extent['row_boundary'] + extent['col_boundary']))})
                continue
            # Process the iterator exactly once for row-level aggregate evidence
            # and dimensions; do not retain the full transaction table.
            def counted_rows():
                for row in rows:
                    for cell in row:
                        _track_cell(extent, cell)
                    yield tuple(cell.value for cell in row)
            result = select_retail_rows(headers, counted_rows())
            for key in ('gross_eligible_sales_gbp', 'eligible_line_count',
                        'eligible_quantity_units', 'eligible_lines_missing_customer_id'):
                aggregate[key] += result[key]
            aggregate['distinct_invoice_ids'].update(result['distinct_invoice_ids'])
            aggregate['exclusion_counts'].update(result['exclusion_counts'])
            aggregate['monthly_2010_sales_gbp'] = [a + b for a, b in zip(
                aggregate['monthly_2010_sales_gbp'], result['monthly_2010_sales_gbp'])]
            source_sheets.append({'name': ws.title, 'headers': [str(h) if h is not None else '' for h in headers],
                                  'source_rows': result['source_rows'],
                                  'eligible_line_count': result['eligible_line_count'],
                                  'eligible_sales_gbp': result['gross_eligible_sales_gbp']})
            stats.append({'name': ws.title, 'declared_dimension': extent['declared'],
                          'effective_data_range': [extent['row'], extent['col']],
                          'populated_cell_count': extent['populated'], 'formula_count': 0,
                          'chart_count': 0,
                          'boundary_cells': sorted(set(extent['row_boundary'] + extent['col_boundary']))})
    finally:
        wb.close()
    digest = sha256(path)
    expected = {
        'schema_version': 'office-semantic-oracle-v2',
        'metric_values': {
            'gross_eligible_sales_gbp': aggregate['gross_eligible_sales_gbp'],
            'eligible_line_count': aggregate['eligible_line_count'],
            'eligible_quantity_units': aggregate['eligible_quantity_units'],
        },
        'scenario_values': {
            'Base': {'projected_sales_gbp': aggregate['gross_eligible_sales_gbp']},
            'Higher': {'projected_sales_gbp': aggregate['gross_eligible_sales_gbp'] * 1.05},
            'Lower': {'projected_sales_gbp': aggregate['gross_eligible_sales_gbp'] * 0.95},
        },
        'chart_values': {'monthly_2010_sales': aggregate['monthly_2010_sales_gbp']},
        'oracle_provenance': 'Independent one-pass aggregation of eligible transaction lines from the unmodified source sheets; helper code is not imported.',
    }
    summary = {'dataset_id': 'retail_online', 'input_sha256': digest,
               'sheets': source_sheets,
               'eligible_line_count': aggregate['eligible_line_count'],
               'eligible_quantity_units': aggregate['eligible_quantity_units'],
               'gross_eligible_sales_gbp': aggregate['gross_eligible_sales_gbp'],
               'distinct_invoice_ids': len(aggregate['distinct_invoice_ids']),
               'eligible_lines_missing_customer_id': aggregate['eligible_lines_missing_customer_id'],
               'exclusion_counts': dict(aggregate['exclusion_counts']),
               'monthly_2010_sales_gbp': aggregate['monthly_2010_sales_gbp'],
               'counting_method': 'one streaming read_only pass; one transaction line per row; no source rows are removed'}
    provenance = _provenance('retail_online', path, digest,
                             'Project-provided Online Retail workbook; acquisition URL and publisher attribution are not independently verified in this repository.',
                             'retail', 'compatibility/recipes/retail.json',
                             'compatibility/helpers/retail_build_enhance.py')
    complexity = _complexity(path, stats)
    for name, value in [('complexity.json', complexity), ('expected.json', expected),
                        ('content-summary.json', summary), ('provenance.json', provenance)]:
        _write(out_dir / name, value)
    req = _retail_requirements(stats)
    manifest = _make_manifest('retail_online', path.name, 'retail_online_enhanced.xlsx', digest,
                              prompt_hash, {
        'row_semantics': RETAIL_POLICY,
        'sheets': [s['name'] for s in source_sheets],
    }, req,
       'Analyze transaction-line sales in the complete Online Retail workbook. Keep each source row and report transparent positive-sale KPIs, a 2010 monthly trend, and an illustrative sales scenario.',
       {'complexity.json': sha256(out_dir / 'complexity.json'),
        'content-summary.json': sha256(out_dir / 'content-summary.json'),
        'provenance.json': sha256(out_dir / 'provenance.json')})
    manifest['expected_sha256'] = sha256(out_dir / 'expected.json')
    manifest['required_outputs'].append('xlsx_business_diagnostics.json')
    _write(out_dir / 'manifest.json', manifest)
    return {'manifest': manifest, 'expected': expected, 'summary': summary}


def _retail_requirements(stats):
    req = {
        'summary_sheet': 'Sales Overview', 'metrics': [
            {'id': 'gross_eligible_sales_gbp', 'name': 'Gross eligible sales',
             'meaning': 'Sum of Quantity × UnitPrice for eligible positive transaction lines under the manifest policy.', 'unit': 'GBP'},
            {'id': 'eligible_line_count', 'name': 'Eligible transaction lines',
             'meaning': 'Count of eligible source rows, not unique InvoiceNo values.', 'unit': 'lines'},
            {'id': 'eligible_quantity_units', 'name': 'Eligible quantity',
             'meaning': 'Sum of positive Quantity for eligible transaction lines.', 'unit': 'items'},
        ],
        'scenario': {'default': 'Base', 'dimensions': [{'id': 'sales_multiplier',
            'meaning': 'Illustrative gross-sales multiplier; not a forecast.'}],
            'rows': [{'name': 'Base', 'assumptions': {'sales_multiplier': 1.0}},
                     {'name': 'Higher', 'assumptions': {'sales_multiplier': 1.05}},
                     {'name': 'Lower', 'assumptions': {'sales_multiplier': 0.95}}],
            'projections': [{'id': 'projected_sales_gbp',
                'meaning': 'All-period gross eligible sales scaled by the selected illustrative assumption.',
                'unit': 'GBP'}]},
        'charts': [{'id': 'monthly_2010_sales',
            'meaning': 'Eligible gross transaction-line sales by calendar month during 2010.', 'unit': 'GBP'}],
        'minimum_comments': 2, 'minimum_conditional_formats': 2,
        'minimum_formula_count': 4, 'recalc_timeout': 600,
    }
    req.update(_base_requirements(stats))
    return req


def _provenance(dataset_id, path, input_hash, source_note, reference_dataset,
                reference_recipe, reference_helper):
    return {
        'schema_version': 'office-input-provenance-manual-adaptation-v1',
        'dataset_id': dataset_id, 'origin_type': 'manual_workflow_adaptation',
        'agent_generated': False, 'requires_llm': False,
        'filename': Path(path).name, 'sha256': input_hash,
        'file_size_bytes': Path(path).stat().st_size,
        'source_assessment': source_note,
        'synthetic_expansion': False,
        'conversion': 'None; the complete supplied workbook bytes are preserved.',
        'references': [{
            'dataset_id': reference_dataset, 'workflow_role': 'workflow shape reference only',
            'recipe_path': reference_recipe, 'recipe_sha256': sha256(reference_recipe),
            'helper_path': reference_helper, 'helper_sha256': sha256(reference_helper),
            'not_parent_execution': True,
        }],
        'agent_parent_run': None, 'canonical_trajectory': None,
        'status': 'registered_not_run',
    }


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    root = Path(__file__).resolve().parents[1]
    prompt_hash = sha256(root / 'compatibility/prompts/xlsx.txt')
    inputs = {
        'hr_metro': root / 'assets/cases/hr_metro/source/datasets/xlsx/hr_metro/input/MSA_M2025_dl.xlsx',
        'retail_online': root / 'assets/cases/retail_online/source/datasets/xlsx/retail_online/input/Online Retail.xlsx',
    }
    if sha256(inputs['hr_metro']) != 'faf00eee127763c8c082d8fb862717ef2ad3a75f16f8975dc1e70935f27bcbb0':
        raise ValueError('hr_metro input SHA256 mismatch')
    if sha256(inputs['retail_online']) != '43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d':
        raise ValueError('retail_online input SHA256 mismatch')
    for dataset_id, prepare in (('hr_metro', prepare_hr), ('retail_online', prepare_retail)):
        metadata = inputs[dataset_id].parents[1]
        result = prepare(inputs[dataset_id], metadata, prompt_hash)
        print(json.dumps({'dataset_id': dataset_id,
                          'input_sha256': sha256(inputs[dataset_id]),
                          'sheets': result['manifest']['requirements']['base_sheets'],
                          'summary': result['summary']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
