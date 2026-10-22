"""PDF loop contract: document-oe-compatible-pdf-loop-v1.

Detailed business validation is limited to selected, actually executed records.
Deep checks for prepared but unselected mappings and whole-page image decoding are
reserved for independent acceptance after the measured loop.
"""
from pathlib import Path
import sys


def selected_records(manifest, records):
    ids = [record['id'] for record in records]
    selection = manifest['pdf_execution']
    wanted = selection['record_ids']
    if (len(ids) != len(set(ids)) or not wanted
            or selection['record_count'] != len(wanted)
            or wanted != ids[:len(wanted)]):
        raise ValueError('PDF execution must select the declared nonempty prefix of prepared records')
    return records[:len(wanted)]


def check_representative_changes(template_dir, output_dir, selected, requirements, checks):
    """Check one configured page for every record actually executed."""
    from PIL import Image, ImageChops

    spec = (requirements.get('representative_visible_change')
            or (requirements.get('visible_changes') or [None])[0])
    if selected and spec is None:
        checks.add('representative_visible_change', False, 'no page configured')
        return
    if spec is None:
        return
    for record in selected:
        ident = record['id']
        filename = f"page_{spec['page']}.png"
        a_path = Path(template_dir) / filename
        b_path = Path(output_dir) / ident / filename
        try:
            with Image.open(a_path) as a, Image.open(b_path) as b:
                if a.size == b.size:
                    difference = ImageChops.difference(a.convert('RGB'), b.convert('RGB')).convert('L')
                    changed = sum(value > spec.get('pixel_threshold', 12) for value in difference.getdata())
                else:
                    changed = 0
        except (OSError, ValueError):
            changed = 0
        checks.add(f'representative_visible_change:{ident}', changed > spec['minimum_changed_pixels'],
                   {'record_id': ident, 'page': spec['page'], 'changed_pixels': changed})


def verify_pdf(manifest, expected, workspace, checks):
    from pypdf import PdfReader
    from PIL import Image, ImageChops
    from .verify import read_json, expected_pdf_fields, pdf_field_matches, pdf_value

    req = manifest['requirements']
    records_data = read_json(workspace / 'input' / manifest['records'])
    records = records_data[manifest['records_key']]
    selected = selected_records(manifest, records)
    output = Path(workspace) / 'output'
    template = PdfReader(workspace / 'input' / manifest['form'])
    source_root = Path(__file__).resolve().parents[1]
    extractor_dirs = [source_root / 'vendor/skills/pdf/scripts',
                      source_root / 'cases' / manifest['dataset_id'] / 'source' / 'vendor/skills/pdf/scripts']
    cases_root = source_root / 'cases'
    extractor_dirs.extend(cases_root.glob('*/source/vendor/skills/pdf/scripts'))
    if not any(path.is_dir() for path in extractor_dirs):
        extractor_dirs.append(source_root / 'compatibility/cases' / manifest['dataset_id']
                              / 'source/vendor/skills/pdf/scripts')
    extractor = next((path for path in extractor_dirs if path.is_dir()), None)
    if extractor is None:
        raise FileNotFoundError('frozen PDF field extractor is missing for ' + manifest['dataset_id'])
    sys.path.insert(0, str(extractor))
    from extract_form_field_info import get_field_info
    template_schema = get_field_info(template)
    inspection = read_json(output / 'form_field_info.json')
    checks.add('template_form', len(template.pages) == req['page_count']
               and len(template_schema) == req['field_count'])
    checks.add('field_inspection_output', isinstance(inspection, list)
               and inspection == template_schema, len(inspection) if isinstance(inspection, list) else None)
    checks.add('prepared_record_count', len(records) == req['record_count'])
    checks.add('execution_record_count', len(selected) == manifest['pdf_execution']['record_count'])

    def check_render_files(directory, label):
        paths = sorted(directory.glob('page_*.png')) if directory.is_dir() else []
        names = {path.name for path in paths}
        required = {f'page_{index}.png' for index in range(1, req['page_count'] + 1)}
        minimum = req.get('minimum_png_bytes', 1)
        ok = names == required and all(path.is_file() and path.stat().st_size >= minimum for path in paths)
        checks.add('render_files:' + label, ok,
                   {'count': len(paths), 'required_count': len(required), 'minimum_bytes': minimum})
        return ok

    template_dir = output / 'rendered' / 'template'
    check_render_files(template_dir, 'template')
    values_dir = output / 'field_values'
    all_ids = {record['id'] for record in records}
    selected_ids = {record['id'] for record in selected}
    # Prepared, unexecuted mappings are only checked as deliverable JSON here;
    # their business semantics are covered by independent acceptance.
    for record in records:
        ident = record['id']
        values_path = values_dir / (ident + '.json')
        try:
            mapping = read_json(values_path)
            readable = isinstance(mapping, list) and len(mapping) == len(req['field_rules'])
        except (OSError, ValueError):
            mapping, readable = [], False
        checks.add('prepared_mapping_file:' + ident, readable)
        if record not in selected:
            continue

        pdf_path = output / 'filled' / (ident + '.pdf')
        try:
            values = read_json(values_path)
            by_id = {item['field_id']: item for item in values if isinstance(item, dict)}
            reader = PdfReader(pdf_path)
            fields = reader.get_fields() or {}
            expected_values = expected_pdf_fields(record, records_data, req['field_rules'])
            rules = {rule['field_id']: rule for rule in req['field_rules']}
            mapping_ok = (len(by_id) == len(values) and set(by_id) == set(expected_values)
                          and all(pdf_field_matches(by_id[field_id].get('value'), value, rules[field_id])
                                  for field_id, value in expected_values.items()))
            checks.add('mapping:' + ident, mapping_ok)
            checks.add('filled_pdf_pages:' + ident, len(reader.pages) == req['page_count'])
            checks.add('filled_pdf_size:' + ident,
                       pdf_path.is_file() and pdf_path.stat().st_size >= req.get('minimum_pdf_bytes', 1))
            checks.add('filled_field_values:' + ident,
                       all(pdf_field_matches(fields.get(field_id, {}).get('/V'), value, rules[field_id])
                           for field_id, value in expected_values.items()))
            protected = req['protected_blank']
            checks.add('protected_fields_blank:' + ident,
                       not set(by_id).intersection(protected)
                       and all(pdf_value(fields.get(field_id, {}).get('/V')) in ('', 'Off')
                               for field_id in protected))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            checks.add('executed_record_readable:' + ident, False, f'{type(exc).__name__}: {exc}')
            continue

        check_render_files(output / 'rendered' / ident, ident)

    # This checks one configured page per executed record, never all pages or
    # unselected prepared records.
    check_representative_changes(template_dir, output / 'rendered', selected, req, checks)

    checks.add('filled_pdf_inventory',
               {path.stem for path in (output / 'filled').glob('*.pdf')} == selected_ids)
    checks.add('prepared_mapping_inventory',
               {path.stem for path in values_dir.glob('*.json')} == all_ids)
    rendered = output / 'rendered'
    checks.add('render_directory_inventory',
               {path.name for path in rendered.iterdir()} == selected_ids | {'template'} if rendered.is_dir() else False)
    summary = read_json(output / 'batch_summary.json')
    for key, value in expected['summary_values'].items():
        checks.add('summary:' + key, summary.get(key) in [value, *manifest.get('summary_aliases', {}).get(key, [])],
                   summary.get(key))
    for filename in manifest['required_outputs']:
        if filename != 'business_verification.json':
            checks.add('deliverable:' + filename, (output / filename).exists())
