"""The old fill/render subprocess pattern, with manifest paths and record IDs."""
import json
import os
from pathlib import Path
import subprocess

WS = Path.cwd()
manifest = json.loads((WS / 'input/dataset_manifest.json').read_text())
records = json.loads((WS / 'input' / manifest['records']).read_text())[manifest['records_key']]
selection = manifest['pdf_execution']
count = int(os.environ.get('DOCUMENT_BENCH_PDF_APPLICANT_COUNT', str(selection['record_count'])))
if count != selection['record_count'] or [r['id'] for r in records[:count]] != selection['record_ids']:
    raise ValueError('PDF runtime selection differs from the frozen execution contract')
records = records[:count]
skill = Path('/root/.openclaw/skills/pdf')
for record in records:
    ident = record['id']
    filled = WS / 'output/filled' / (ident + '.pdf')
    rendered = WS / 'output/rendered' / ident
    filled.parent.mkdir(parents=True, exist_ok=True)
    rendered.mkdir(parents=True, exist_ok=True)
    for command in (
        ['python3', str(skill / 'scripts/fill_fillable_fields.py'),
         str(WS / 'input' / manifest['form']), str(WS / 'output/field_values' / (ident + '.json')), str(filled)],
        ['python3', str(skill / 'scripts/convert_pdf_to_images.py'), str(filled), str(rendered)],
    ):
        result = subprocess.run(command, capture_output=True, text=True, cwd=skill)
        if result.returncode:
            raise RuntimeError(f'{ident}: {command[1]}: {result.stderr}')
    print('filled and rendered', ident)
