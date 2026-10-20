#!/usr/bin/env python3
"""Compare scripts and inclusive openpyxl operations using existing py-spy captures.

This is a separate view; it does not change native-cycle coverage results.
Retain samples without Python frames in the denominator as unresolved activity.
SVG fg:x/fg:w are integer sample coordinates, not rounded displayed percentages.
"""
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from parse_pyspy import MODULE_FRAME, PRELOOP_FRAMES, PROC, script_role

BASE = Path(__file__).resolve().parents[1]
CONFIGS = ('opm-n1', 'opm-n10', 'irs_w4-n1', 'irs_w4-n10',
           'sba1919-n1', 'sba1919-n10', 'tlc', 'retail', 'manufacturing', 'hr')
LAZY_FUNCTIONS = ('_cells_by_row', '_get_row', '_get_cell', '_get_source',
                  '_calculate_dimension', 'calculate_dimension', '_get_size')


def operation(frame):
    # Zip-imported openpyxl in verify_office.py has basename-only filenames.
    # Frozen verifier imports bind load_workbook to openpyxl, as checked in source.
    if re.fullmatch(r'load_workbook \((?:openpyxl/reader/)?excel\.py:\d+\)', frame):
        return 'load_call'
    if re.fullmatch(r'save \((?:openpyxl/workbook/)?workbook\.py:\d+\)', frame):
        return 'save'
    lazy = '|'.join(LAZY_FUNCTIONS)
    if re.fullmatch(r'(?:' + lazy + r') \((?:openpyxl/worksheet/)?_read_only\.py:\d+\)', frame):
        return 'lazy_scan'
    return None


def category(frames):
    hits = {operation(f) for f in frames} - {None}
    if 'save' in hits and ('load_call' in hits or 'lazy_scan' in hits):
        raise ValueError('unexpected nested load/save; inspect before classifying')
    # A read-only dimension scan nested inside load_workbook is counted once.
    for key in ('load_call', 'save', 'lazy_scan'):
        if key in hits:
            return key
    return 'other' if frames else 'no_python_frames'


def role_for(command, scene):
    role = script_role(command, scene)
    if role == 'python-inline' and scene == 'xlsx':
        if 'data_only=False' in command:
            return 'xlsx-inspect-formulas'
        if 'data_only=True' in command:
            return 'xlsx-inspect-cached'
    return role


def result(roles, operations, dropped=0):
    total = sum(roles.values())
    assert total == sum(operations.values()) and total > 0
    operations = dict(operations)
    load_total = operations.get('load_call', 0) + operations.get('lazy_scan', 0)
    return {
        'total_samples': total, 'excluded_known_preflight_samples': dropped,
        'role_samples': dict(roles),
        'role_percent': {k: 100 * n / total for k, n in roles.items()},
        'operation_samples': operations,
        'operation_percent': {k: 100 * n / total for k, n in operations.items()},
        'load_including_lazy_percent': 100 * load_total / total,
        'load_and_save_percent': 100 * (load_total + operations.get('save', 0)) / total,
    }


def analyze_raw(path, scene):
    roles, operations = Counter(), Counter()
    dropped = 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        stack, _, count = line.rpartition(' ')
        count = int(count)
        procs, frames = [], []
        for segment in stack.split(';'):
            match = PROC.fullmatch(segment)
            if match:
                procs.append(match.groups())
            else:
                frames.append(segment)
        if not procs:
            raise ValueError('missing process identity')
        command = procs[-1][1]
        role = role_for(command, scene)
        if role is None or (role == 'runner' and len(procs) > 1 and command == procs[0][1]):
            for frame in frames:
                match = MODULE_FRAME.search(frame)
                recovered = role_for(match[1], scene) if match else None
                if recovered and recovered != 'runner':
                    role = recovered
                    break
        role = role or ('runner' if len(procs) == 1 and not command.strip() else 'other')
        if role == 'runner' and any(PRELOOP_FRAMES.search(f) for f in frames):
            dropped += count
            continue
        roles[role] += count
        operations[category(frames) if scene == 'xlsx' else
                   ('other' if frames else 'no_python_frames')] += count
    return result(roles, operations, dropped)


def analyze_svg(path, scene):
    ns, fg = '{http://www.w3.org/2000/svg}', '{http://github.com/jonhoo/inferno}'
    root = ET.parse(path).getroot()
    container = next(n for n in root.iter(ns + 'svg') if n.get('id') == 'frames')
    total = int(container.get('total_samples'))
    hits = [set() for _ in range(total)]
    has_frame = [False] * total
    roles = [(-1, 'other')] * total
    for group in container:
        rect, title = group.find(ns + 'rect'), group.find(ns + 'title')
        if rect is None:
            continue
        name = re.sub(r' \([\d,]+ samples?, [\d.]+%\)$', '', title.text)
        start, count = int(rect.get(fg + 'x')), int(rect.get(fg + 'w'))
        depth = int(rect.get('y'))
        assert 0 <= start <= start + count <= total
        process = name.startswith('process ')
        role = role_for(name, scene) if process else None
        op = operation(name) if scene == 'xlsx' else None
        for i in range(start, start + count):
            if role is not None and depth > roles[i][0]:
                roles[i] = (depth, role)
            if name != 'all' and not name.startswith(('process ', 'thread ', 'all (')):
                has_frame[i] = True
            if op:
                hits[i].add(op)
    operations = Counter()
    for h, resolved in zip(hits, has_frame):
        assert not ('save' in h and ('load_call' in h or 'lazy_scan' in h))
        key = next((k for k in ('load_call', 'save', 'lazy_scan') if k in h),
                   'other' if resolved else 'no_python_frames')
        operations[key] += 1
    return result(Counter(r for _, r in roles), operations)


def provenance(path):
    return {'path': str(path.relative_to(BASE)), 'size_bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    inputs, historical, current = [], {}, {}
    for scene, config in (('pdf', 'opm-n1'), ('xlsx', 'tlc')):
        path = BASE / 'legacy/evidence/python3123-pyspy' / f'{scene}-python.svg'
        historical[config] = analyze_svg(path, scene)
        inputs.append(provenance(path))
    for config in CONFIGS:
        path = BASE / 'raw' / config / 'pyspy/raw' / f'{config}.pyspy.raw'
        meta_path = BASE / 'raw' / config / 'pyspy/out/metadata.json'
        scene = 'xlsx' if config in ('tlc', 'retail', 'manufacturing', 'hr') else 'pdf'
        data = analyze_raw(path, scene)
        meta = json.loads(meta_path.read_text())
        data['collector_rc'] = meta['rc']
        data['qualified'] = meta['rc'] == 0
        data['requested_loops'] = meta['runner_summary']['requested_iterations']
        current[config] = data
        inputs.extend((provenance(path), provenance(meta_path)))
    output = {
        'schema': 'script-io-comparison-v1',
        'denominator': 'All py-spy sample counts, including process-only samples; current captures exclude identified runner preflight stacks.',
        'interpretation': 'Python sampled active-time estimates, not whole replay wall time; excludes native-only LibreOffice/Poppler activity and idle waiting. Single Python profiling run per configuration.',
        'lazy_scan_boundary': 'Inclusive executed read-only worksheet generator/accessor stacks, excluding scans already nested in load_workbook. Downstream business comparisons after yielded cells remain separate.',
        'historical_baseline': 'document-oe Python 3.12.3, PDF N=1 ten loops, XLSX two loops; historical affinity differs from current.',
        'unresolved_policy': 'Process-only samples remain in denominator, unassigned to load/save; measured shares may omit unresolved operation samples.',
        'pdf_comparison_limit': 'Historical Python-stack baseline is N=1. IRS W-4 N=1 collector failed; N=10 comparison uses rerun OPM N=10 as a bridge, not as historical N=10 evidence.',
        'historical': historical, 'current': current, 'inputs': inputs,
        'analysis_sources': [provenance(Path(__file__)), provenance(BASE / 'scripts/parse_pyspy.py')],
    }
    target = BASE / 'processed/script-io-comparison.json'
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(target)


if __name__ == '__main__':
    main()
