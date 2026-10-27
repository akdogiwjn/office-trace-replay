#!/usr/bin/env python3
"""Dataset-local batch verification, adapted from the frozen OPM verifier.

No office-trace project imports or shared verification entry. Decode only one
representative page per filled record, as in OPM. Full schema, mapping-page,
all-page visibility and input integrity audits run after the Agent completes.
"""
import argparse
import json
from pathlib import Path

CONFIG = {'dataset_id': 'irs_w4',
 'form': 'fw4_2026.pdf',
 'records': 'synthetic_employees.json',
 'records_key': 'employees',
 'page_count': 5,
 'field_count': 48,
 'record_count': 10,
 'field_rules': [{'semantic': 'first_name',
                  'field_id': 'topmostSubform[0].Page1[0].Step1a[0].f1_01[0]',
                  'value_from': 'first_name'},
                 {'semantic': 'last_name',
                  'field_id': 'topmostSubform[0].Page1[0].Step1a[0].f1_02[0]',
                  'value_from': 'last_name'},
                 {'semantic': 'address',
                  'field_id': 'topmostSubform[0].Page1[0].Step1a[0].f1_03[0]',
                  'value_from': 'address'},
                 {'semantic': 'city_state_zip',
                  'field_id': 'topmostSubform[0].Page1[0].Step1a[0].f1_04[0]',
                  'value_from': 'city_state_zip'},
                 {'semantic': 'children_credit',
                  'field_id': 'topmostSubform[0].Page1[0].Step3_ReadOrder[0].f1_06[0]',
                  'value_from': 'children_credit'},
                 {'semantic': 'other_dependents_credit',
                  'field_id': 'topmostSubform[0].Page1[0].Step3_ReadOrder[0].f1_07[0]',
                  'value_from': 'other_dependents_credit'},
                 {'semantic': 'total_credit',
                  'field_id': 'topmostSubform[0].Page1[0].f1_08[0]',
                  'value_from': 'total_credit'},
                 {'semantic': 'other_income',
                  'field_id': 'topmostSubform[0].Page1[0].f1_09[0]',
                  'value_from': 'other_income'},
                 {'semantic': 'deductions',
                  'field_id': 'topmostSubform[0].Page1[0].f1_10[0]',
                  'value_from': 'deductions'},
                 {'semantic': 'extra_withholding',
                  'field_id': 'topmostSubform[0].Page1[0].f1_11[0]',
                  'value_from': 'extra_withholding'},
                 {'semantic': 'filing_single',
                  'field_id': 'topmostSubform[0].Page1[0].c1_1[0]',
                  'value_from': 'filing_flags.single',
                  'choices': {'true': '/1', 'false': '/Off'}},
                 {'semantic': 'filing_married',
                  'field_id': 'topmostSubform[0].Page1[0].c1_1[1]',
                  'value_from': 'filing_flags.married',
                  'choices': {'true': '/2', 'false': '/Off'}},
                 {'semantic': 'filing_head_of_household',
                  'field_id': 'topmostSubform[0].Page1[0].c1_1[2]',
                  'value_from': 'filing_flags.head_of_household',
                  'choices': {'true': '/3', 'false': '/Off'}},
                 {'semantic': 'multiple_jobs',
                  'field_id': 'topmostSubform[0].Page1[0].c1_2[0]',
                  'value_from': 'multiple_jobs',
                  'choices': {'true': '/1', 'false': '/Off'}}],
 'protected_blank': ['topmostSubform[0].Page1[0].c1_3[0]',
                     'topmostSubform[0].Page1[0].f1_05[0]',
                     'topmostSubform[0].Page1[0].f1_12[0]',
                     'topmostSubform[0].Page1[0].f1_13[0]',
                     'topmostSubform[0].Page1[0].f1_14[0]',
                     'topmostSubform[0].Page3[0].f3_01[0]',
                     'topmostSubform[0].Page3[0].f3_02[0]',
                     'topmostSubform[0].Page3[0].f3_03[0]',
                     'topmostSubform[0].Page3[0].f3_04[0]',
                     'topmostSubform[0].Page3[0].f3_05[0]',
                     'topmostSubform[0].Page3[0].f3_06[0]',
                     'topmostSubform[0].Page4[0].f4_01[0]',
                     'topmostSubform[0].Page4[0].f4_02[0]',
                     'topmostSubform[0].Page4[0].f4_03[0]',
                     'topmostSubform[0].Page4[0].f4_04[0]',
                     'topmostSubform[0].Page4[0].f4_05[0]',
                     'topmostSubform[0].Page4[0].f4_06[0]',
                     'topmostSubform[0].Page4[0].f4_07[0]',
                     'topmostSubform[0].Page4[0].f4_08[0]',
                     'topmostSubform[0].Page4[0].f4_09[0]',
                     'topmostSubform[0].Page4[0].f4_10[0]',
                     'topmostSubform[0].Page4[0].f4_11[0]',
                     'topmostSubform[0].Page4[0].f4_12[0]',
                     'topmostSubform[0].Page4[0].f4_13[0]',
                     'topmostSubform[0].Page4[0].f4_14[0]',
                     'topmostSubform[0].Page4[0].f4_15[0]',
                     'topmostSubform[0].Page4[0].f4_16[0]',
                     'topmostSubform[0].Page4[0].f4_17[0]',
                     'topmostSubform[0].Page4[0].f4_18[0]',
                     'topmostSubform[0].Page4[0].f4_19[0]',
                     'topmostSubform[0].Page4[0].f4_20[0]',
                     'topmostSubform[0].Page4[0].f4_21[0]',
                     'topmostSubform[0].Page4[0].f4_22[0]',
                     'topmostSubform[0].Page4[0].f4_23[0]'],
 'minimum_pdf_bytes': 100000,
 'minimum_png_bytes': 10000,
 'visible_change': {'page': 1, 'minimum_changed_pixels': 500, 'pixel_threshold': 12}}


def field_value(fields, name):
    value = (fields.get(name) or {}).get('/V')
    return '' if value is None else str(value).lstrip('/')


def terminal_field_count(fields):
    return sum(not f.get('/Kids') and f.get('/FT') in {'/Tx', '/Sig', '/Ch', '/Btn'}
               for f in fields.values()) + sum(bool(f.get('/Kids')) and f.get('/FT') == '/Btn'
                                              for f in fields.values())


def expected_fields(record, records):
    result = {}
    for rule in CONFIG['field_rules']:
        if 'constant' in rule:
            value = rule['constant']
        else:
            value = records if rule.get('source') == 'shared' else record
            for key in rule['value_from'].split('.'):
                value = value[key]
        if 'choices' in rule:
            key = str(value).lower() if isinstance(value, bool) else str(value)
            value = rule['choices'][key]
        result[rule['field_id']] = value
    return result


def changed_pixel_count(template_path, output_path):
    from PIL import Image, ImageChops
    with Image.open(template_path) as a, Image.open(output_path) as b:
        if a.size != b.size:
            return 0
        difference = ImageChops.difference(a.convert('RGB'), b.convert('RGB')).convert('L')
        return sum(value > CONFIG['visible_change'].get('pixel_threshold', 12) for value in difference.getdata())


def verify_one_pdf(record, records, output_dir):
    from pypdf import PdfReader
    ident = str(record['id'])
    path = output_dir / 'filled' / (ident + '.pdf')
    mapping = output_dir / 'field_values' / (ident + '.json')
    if not path.is_file() or not mapping.is_file():
        return False, {'error': 'missing PDF or field-values JSON'}
    try:
        reader = PdfReader(path)
        fields = reader.get_fields() or {}
        values = json.loads(mapping.read_text())
        supplied = {str(item.get('field_id')) for item in values if isinstance(item, dict)}
        wanted = expected_fields(record, records)
        rules = {r['field_id']: r for r in CONFIG['field_rules']}
        field_ok = all(field_value(fields, fid) in [str(v).lstrip('/') for v in
            [value, *rules[fid].get('value_aliases', {}).get(str(value), [])]] for fid, value in wanted.items())
        protected = CONFIG['protected_blank']
        renders = sorted((output_dir / 'rendered' / ident).glob('page_*.png'))
        page = 'page_' + str(CONFIG['visible_change']['page']) + '.png'
        changed = changed_pixel_count(output_dir / 'rendered/template' / page,
                                      output_dir / 'rendered' / ident / page)
        checks = {
            'pages': len(reader.pages) == CONFIG['page_count'],
            'file_size': path.stat().st_size >= CONFIG['minimum_pdf_bytes'],
            'field_values': field_ok,
            'sensitive_fields_blank': all(field_value(fields, n) in ('', 'Off') for n in protected),
            'sensitive_fields_omitted': not supplied.intersection(protected),
            'rendered_pages': {p.name for p in renders} == {
                f'page_{n}.png' for n in range(1, CONFIG['page_count'] + 1)}
                and all(p.stat().st_size >= CONFIG['minimum_png_bytes'] for p in renders),
            'visible_render_difference': changed > CONFIG['visible_change']['minimum_changed_pixels'],
        }
        return all(checks.values()), {'checks': checks, 'changed_pixels': changed}
    except Exception as exc:
        return False, {'error': f'{type(exc).__name__}: {exc}'}


def verify_workspace(workspace, report_path=None, *, template_path=None, records_path=None, output_dir=None):
    from pypdf import PdfReader
    workspace = Path(workspace)
    output = Path(output_dir) if output_dir is not None else workspace / 'output'
    checks, failures = {}, []
    def add(name, ok, detail=None):
        checks[name] = {'ok': bool(ok), 'detail': detail}
        if not ok:
            failures.append(name)
    try:
        source = Path(template_path) if template_path is not None else workspace / 'input' / CONFIG['form']
        records_file = Path(records_path) if records_path is not None else workspace / 'input' / CONFIG['records']
        records_data = json.loads(records_file.read_text())
        records = records_data[CONFIG['records_key']]
        template = PdfReader(source)
        add('template_form', len(template.pages) == CONFIG['page_count']
            and terminal_field_count(template.get_fields() or {}) == CONFIG['field_count'])
        info = json.loads((output / 'form_field_info.json').read_text())
        add('field_inspection_output', isinstance(info, list) and len(info) == CONFIG['field_count'])
        renders = sorted((output / 'rendered/template').glob('page_*.png'))
        add('template_render', {p.name for p in renders} == {
            f'page_{n}.png' for n in range(1, CONFIG['page_count'] + 1)}
            and all(p.stat().st_size >= CONFIG['minimum_png_bytes'] for p in renders))
        items = {}
        passed = 0
        for record in records:
            ok, detail = verify_one_pdf(record, records_data, output)
            items[str(record['id'])] = detail
            passed += int(ok)
        add('filled_pdf_batch', len(records) == CONFIG['record_count']
            and len(items) == len(records) and passed == CONFIG['record_count'],
            {'expected': CONFIG['record_count'], 'passed': passed, 'items': items})
        summary = json.loads((output / 'batch_summary.json').read_text())
        add('batch_summary', summary.get('filled_pdf_count') == CONFIG['record_count']
            and summary.get('rendered_page_count') == CONFIG['page_count'] * (CONFIG['record_count'] + 1)
            and summary.get('ssn_and_signatures_left_blank') is True, summary)
    except Exception as exc:
        add('verification_exception', False, f'{type(exc).__name__}: {exc}')
    result = {'dataset_id': CONFIG['dataset_id'], 'kind': 'pdf',
              'validation_scope': 'loop', 'validation_contract': 'dataset-local-opm-style-v1',
              'status': 'failed' if failures else 'success', 'checks': checks, 'failures': failures}
    if report_path is not None:
        Path(report_path).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('template_pdf', type=Path)
    parser.add_argument('records_json', type=Path)
    parser.add_argument('output_dir', type=Path)
    parser.add_argument('report_json', type=Path)
    args = parser.parse_args()
    report = verify_workspace(Path(__file__).resolve().parents[1], args.report_json,
                              template_path=args.template_pdf, records_path=args.records_json,
                              output_dir=args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
