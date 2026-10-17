"""Verify all prepared mappings and only the explicitly selected PDF outputs.

Installed into the private compatible source; parent Agent verifiers are frozen.
"""
from pathlib import Path
import sys


def selected_records(manifest, records):
    ids = [r['id'] for r in records]
    selection = manifest['pdf_execution']
    wanted = selection['record_ids']
    if (len(ids) != len(set(ids)) or not wanted
            or selection['record_count'] != len(wanted)
            or wanted != ids[:len(wanted)]):
        raise ValueError('PDF execution must select the declared nonempty prefix of prepared records')
    return records[:len(wanted)]


def verify_pdf(manifest, expected, workspace, checks):
    from pypdf import PdfReader
    from PIL import Image, ImageChops
    from .verify import read_json, expected_pdf_fields, pdf_field_matches, pdf_value

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'vendor/skills/pdf/scripts'))
    from extract_form_field_info import get_field_info

    req = manifest['requirements']
    records_data = read_json(workspace / 'input' / manifest['records'])
    records = records_data[manifest['records_key']]
    selected = selected_records(manifest, records)
    reader = PdfReader(workspace / 'input' / manifest['form'])
    schema = get_field_info(reader)
    schema_ids = {v['field_id']: v for v in schema}
    rules_by_id = {rule['field_id']: rule for rule in req['field_rules']}
    protected = req['protected_blank']
    output = workspace / 'output'
    checks.add('template_form', len(reader.pages) == req['page_count'] and len(schema) == req['field_count'])
    checks.add('field_inspection', read_json(output / 'form_field_info.json') == schema)
    checks.add('record_count', len(records) == req['record_count'])
    checks.add('execution_record_count', len(selected) == manifest['pdf_execution']['record_count'])

    # Unselected records are prepared work, not unverified extra files.
    for record in records:
        ident = record['id']
        values = read_json(output / 'field_values' / (ident + '.json'))
        by_id = {v['field_id']: v for v in values}
        wanted = expected_pdf_fields(record, records_data, req['field_rules'])
        checks.add('mapping:' + ident, len(by_id) == len(values) and set(by_id) == set(wanted)
                   and all(pdf_field_matches(by_id[fid].get('value'), v, rules_by_id[fid]) for fid, v in wanted.items()))
        checks.add('mapping_pages:' + ident, all(fid in schema_ids and item['page'] == schema_ids[fid]['page'] for fid, item in by_id.items()))
        checks.add('mapping_protected_blank:' + ident, not set(by_id).intersection(protected))

    def check_images(directory, label):
        paths = list(directory.glob('page_*.png'))
        ok = {p.name for p in paths} == {f'page_{n}.png' for n in range(1, req['page_count'] + 1)}
        for path in paths:
            try:
                with Image.open(path) as image:
                    image.verify()
                ok = ok and path.stat().st_size >= req.get('minimum_png_bytes', 1)
            except (OSError, ValueError):
                ok = False
        checks.add('render:' + label, ok, len(paths))

    template_dir = output / 'rendered/template'
    check_images(template_dir, 'template')
    for record in selected:
        ident = record['id']
        pdf_path = output / 'filled' / (ident + '.pdf')
        pdf = PdfReader(pdf_path)
        fields = pdf.get_fields() or {}
        wanted = expected_pdf_fields(record, records_data, req['field_rules'])
        checks.add('pages:' + ident, len(pdf.pages) == req['page_count'])
        checks.add('pdf_size:' + ident, pdf_path.stat().st_size >= req.get('minimum_pdf_bytes', 1))
        checks.add('field_values:' + ident, all(pdf_field_matches(fields.get(fid, {}).get('/V'), v, rules_by_id[fid]) for fid, v in wanted.items()))
        checks.add('protected_blank:' + ident, all(pdf_value(fields.get(fid, {}).get('/V')) in ('', 'Off') for fid in protected))
        check_images(output / 'rendered' / ident, ident)
        for spec in req.get('visible_changes', []):
            filename = f'page_{spec["page"]}.png'
            with Image.open(template_dir / filename) as a, Image.open(output / 'rendered' / ident / filename) as b:
                if a.size == b.size:
                    diff = ImageChops.difference(a.convert('RGB'), b.convert('RGB')).convert('L')
                    changed = sum(v > spec.get('pixel_threshold', 12) for v in diff.getdata())
                else:
                    changed = 0
            checks.add(f'visible_change:{ident}:{spec["page"]}', changed > spec['minimum_changed_pixels'], changed)

    ids = {r['id'] for r in selected}
    checks.add('exact_pdf_inventory', {p.stem for p in (output / 'filled').glob('*.pdf')} == ids)
    checks.add('exact_mapping_inventory', {p.stem for p in (output / 'field_values').glob('*.json')} == {r['id'] for r in records})
    checks.add('exact_render_inventory', {p.name for p in (output / 'rendered').iterdir()} == ids | {'template'})
    summary = read_json(output / 'batch_summary.json')
    for key, value in expected['summary_values'].items():
        checks.add('summary:' + key, summary.get(key) in [value, *manifest.get('summary_aliases', {}).get(key, [])], summary.get(key))
    for filename in manifest['required_outputs']:
        if filename != 'business_verification.json':
            checks.add('deliverable:' + filename, (output / filename).exists())
