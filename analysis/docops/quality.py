"""Pure validation and ROI selection shared by the DocOps pilot and tests."""
import json
import hashlib
from pathlib import Path


def file_sha256(path):
    """Hash large evidence files with bounded memory."""
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def function_qualification(quality):
    """Separate acquired data from function-comparison quality; keep unknown weight."""
    empty = quality['empty_stack_share']
    unknown = quality['unknown_leaf_symbol_share']
    if not 0 <= empty <= 1 or not 0 <= unknown <= 1:
        raise ValueError('invalid sample quality fraction')
    return {'stack_eligible':empty <= .2, 'function_profile_eligible':empty <= .2 and unknown <= .2,
            'empty_stack_share_max':.2, 'unknown_leaf_symbol_share_max':.2,
            'status':'passed' if empty <= .2 and unknown <= .2 else 'limited',
            'note':'Acquisition success does not imply complete symbols; threshold unchanged from pilot; unresolved period retained.'}


def verify_symbols(root):
    root = Path(root).resolve()
    path = root/'index.json'
    index = json.loads(path.read_text())
    verified = []
    for row in index['files']:
        if row['status'] != 'downloaded':
            continue
        file = (root/row['path']).resolve()
        if not file.is_relative_to(root) or not row.get('build_id_verified'):
            raise ValueError('invalid symbol provenance')
        if file.stat().st_size != row['bytes'] or file_sha256(file) != row['sha256']:
            raise ValueError('debug symbol hash mismatch: '+str(file))
        verified.append(row)
    if not verified:
        raise ValueError('no verified debug symbols')
    return {'index_sha256':file_sha256(path), 'files':verified}


def workload_records(out, task, loops):
    root = Path(out)/'runner'/task
    summary = json.loads((root/'summary.json').read_text())
    counts = {k: summary[k] for k in ('requested', 'completed', 'successes', 'failures')}
    if counts != dict(requested=loops, completed=loops, successes=loops, failures=0):
        raise ValueError(f'unsuccessful workload: {counts}')
    records = [json.loads(p.read_text()) for p in sorted(root.glob('round-*/run.json'))]
    if len(records) != loops:
        raise ValueError('round record count mismatch')
    intervals = []
    for record in records:
        if record['status'] != 'completed' or record['failures'] or record['environment_restore']['status'] != 'ok':
            raise ValueError('round failed')
        if record['roi_clock'] != 'CLOCK_MONOTONIC':
            raise ValueError('unsupported ROI clock')
        intervals += [(round(i['start']*1e9), round(i['end']*1e9)) for i in record['roi_intervals']]
    intervals.sort()
    for number, (start, end) in enumerate(intervals):
        if start >= end or (number and start < intervals[number-1][1]):
            raise ValueError('invalid or overlapping ROI intervals')
    return counts, records, intervals


def select_samples(samples, intervals, dispatcher):
    selected, excluded = [], {'outside_workflow': 0, 'dispatcher_inside_workflow': 0}
    for sample in samples:
        inside = any(start <= sample['t_ns'] < end for start, end in intervals)
        if not inside:
            excluded['outside_workflow'] += sample['period']
        elif sample['pid'] == dispatcher:
            excluded['dispatcher_inside_workflow'] += sample['period']
        else:
            selected.append(sample)
    if sum(s['period'] for s in selected)+sum(excluded.values()) != sum(s['period'] for s in samples):
        raise ValueError('period partition does not conserve')
    return selected, excluded
