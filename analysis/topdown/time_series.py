"""Read saved DevKit interval reports; never collect or rescale PMU events."""
import json
import math
import re
from pathlib import Path

from pilot import ROOT, sha
from summarize import METRICS

HEADER = re.compile(r'^TOP-DOWN Summary Report-(\d+|ALL)\s+Time:([^\n]+)$', re.M)


def parse_intervals(text):
    headers = list(HEADER.finditer(text))
    points = []
    final = None
    for i, header in enumerate(headers):
        block = text[header.end():headers[i + 1].start() if i + 1 < len(headers) else len(text)]
        values = {}
        for metric in METRICS:
            match = re.search(r'^[^\w\n]*' + re.escape(metric) + r'[ \t]+(-?\d+(?:\.\d+)?)(?=\s|$)', block, re.M)
            if not match:
                raise ValueError('interval metric missing: ' + metric)
            values[metric] = float(match[1])
        if not all(math.isfinite(x) for x in values.values()):
            raise ValueError('nonfinite interval metric')
        if any(not 0 <= values[m] <= 100 for m in METRICS if m != 'IPC'):
            raise ValueError('interval bound outside [0,100]')
        for keys, target in ((('Bad Speculation', 'Frontend Bound', 'Backend Bound', 'Retiring'), 100),
                             (('Core Bound', 'Memory Bound'), values['Backend Bound']),
                             (('Fetch Latency Bound', 'Fetch Bandwidth Bound'), values['Frontend Bound'])):
            if abs(sum(values[k] for k in keys) - target) > .03001:
                raise ValueError('interval metric hierarchy mismatch')
        counts = {}
        for name in ('Cycles', 'Instructions'):
            match = re.search(r'^' + name + r'\s+([\d,]+)\s*$', block, re.M)
            if not match:
                raise ValueError('interval counter missing: ' + name)
            counts[name.lower()] = int(match[1].replace(',', ''))
        row = dict(timestamp=header[2].strip(), metrics=values, **counts)
        if header[1] == 'ALL':
            if final is not None or i != len(headers) - 1:
                raise ValueError('duplicate or misplaced ALL report')
            final = row
        else:
            number = int(header[1])
            if number != len(points) + 1:
                raise ValueError('noncontiguous interval sequence')
            row['sample_index'] = number
            points.append(row)
    if not points or final is None:
        raise ValueError('interval or final reports missing')
    deltas = {name: sum(p[name] for p in points) - final[name]
              for name in ('cycles', 'instructions')}
    # Printed integer counts can differ by one unit after tool aggregation.
    # Record the actual delta; do not repair or scale either representation.
    if any(abs(v) > 1 for v in deltas.values()):
        raise ValueError('interval counter sum differs from ALL beyond one printed unit')
    return dict(points=points, final=final, interval_counter_deltas=deltas,
                counter_check='absolute printed count delta <= 1; original values retained')


def load_campaign(campaign, root=ROOT):
    root = Path(root)
    runs = []
    for entry in campaign['completed']:
        raw = root / entry['raw']
        summary = json.loads((root / entry['summary']).read_text())
        source = raw / 'out/devkit.stdout.txt'
        relative = 'out/devkit.stdout.txt'
        if sha(source) != summary['evidence_hashes'][relative]:
            raise ValueError('interval source hash mismatch')
        parsed = parse_intervals(source.read_text())
        if parsed['final']['metrics'] != summary['metrics']:
            raise ValueError('interval ALL differs from qualified summary')
        runs.append(dict(dataset_id=entry['dataset_id'], repeat=entry['repeat'],
            source=dict(path=str(source.relative_to(root)), sha256=sha(source)), **parsed))
    keys = {(r['dataset_id'], r['repeat']) for r in runs}
    if len(keys) != len(runs):
        raise ValueError('duplicate time-series run')
    return dict(schema='devkit-interval-series-v1', runs=runs, interval_seconds_nominal=1,
        metric_order=list(METRICS), total_points=sum(len(r['points']) for r in runs),
        scope='Saved CPU 0-7 profiler envelope, including initial/final margins; no exact ROI cropping, smoothing or interpolation.',
        aggregate_policy='Original ALL values remain authoritative for five-run statistics and similarity; interval percentages are not averaged.',
        idle_policy='Only whole-ROI idle was captured; no per-interval idle series is reconstructed.')
