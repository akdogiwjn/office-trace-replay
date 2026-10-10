"""Export actual metric/scenario values without TLC-specific sheet references."""
import csv
import json
from pathlib import Path
from openpyxl import load_workbook

ws = Path.cwd()
manifest = json.loads((ws / 'input/dataset_manifest.json').read_text())
features = json.loads((ws / 'output/workbook_features.json').read_text())
wb = load_workbook(ws / 'output' / manifest['output_workbook'], data_only=True, read_only=True)
try:
    groups = {'metrics.csv': features['metrics'], 'scenario.csv': features['scenario']['projections']}
    for filename, refs in groups.items():
        with (ws / 'output' / filename).open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['metric', 'value'])
            for ident, ref in refs.items():
                value = wb[ref['sheet']][ref['cell']].value
                if value is None:
                    raise ValueError('missing calculated cache: ' + ident)
                writer.writerow([ident, value])
finally:
    wb.close()
