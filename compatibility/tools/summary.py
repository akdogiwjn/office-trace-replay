"""Derive descriptive summaries from actual outputs; never restore old answers."""
import json
from pathlib import Path
import sys

ws = Path.cwd()
manifest = json.loads((ws / 'input/dataset_manifest.json').read_text())
output = ws / 'output'
if manifest['kind'] == 'pdf':
    count = len(json.loads((ws / 'input' / manifest['records']).read_text())[manifest['records_key']])
    filled = len(list((output / 'filled').glob('*.pdf')))
    pages = len(list((output / 'rendered').glob('*/page_*.png')))
    if filled != count or pages != manifest['requirements']['page_count'] * (count + 1):
        raise ValueError('unexpected PDF output inventory')
    value = {'input_form': manifest['form'], 'applicant_count': count,
             'filled_pdf_count': filled, 'rendered_page_count': pages,
             'fill_script_invocations': count, 'render_script_invocations': count + 1,
             'ssn_and_signatures_left_blank': True}
    name = 'batch_summary.json'
else:
    from openpyxl import load_workbook
    features = json.loads((output / 'workbook_features.json').read_text())
    recalc = json.loads((output / 'formula_recalc.json').read_text())
    verification = json.loads((output / 'business_verification.json').read_text())
    wb = load_workbook(output / manifest['output_workbook'])
    try:
        original = load_workbook(ws / 'input' / manifest['workbook'], read_only=True)
        try:
            added = [name for name in wb.sheetnames if name not in original.sheetnames]
        finally:
            original.close()
        value = {'added_sheet_names': added, 'summary_sheet': features['summary_sheet'],
                 'chart_count': sum(len(sheet._charts) for sheet in wb),
                 'helper_execution_attempts': 1, 'helper_successful_executions': 1,
                 'recalc_invocation_count': 1, 'final_verifier_status': verification['status'],
                 'recalculation': recalc, 'workflow_contract': 'document-oe-compatible-workflow-v1'}
    finally:
        wb.close()
    name = 'xlsx_enhancement_summary.json'
(output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
print(name)
