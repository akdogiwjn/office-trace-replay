"""Physical leaf-function profiles; exact monotonic ROI, raw period weighting."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

HEADER = re.compile(r'^\s*(?P<comm>.+?)\s+(?P<pid>\d+)/(?P<tid>\d+)\s+(?P<time>\d+\.\d+):\s+(?P<period>\d+)\s+(?P<event>\S+):\s*$')
COUNTER = re.compile(r'^\s*(?P<pid>\d+)/(?P<tid>\d+)\s+(?P<time>\d+\.\d+):\s+(?P<period>\d+)\s+(?P<event>\S+):\s*$')
FRAME = re.compile(r'^\s+([a-fA-F0-9]+)\s+(.+?)\s+\((.+)\)\s*$')


def ns(value):
    seconds, fraction = value.split('.')
    if len(fraction) > 9:
        raise ValueError('timestamp exceeds nanosecond precision')
    return int(seconds) * 1_000_000_000 + int(fraction.ljust(9, '0'))


def key(match):
    return (int(match['pid']), int(match['tid']), ns(match['time']), int(match['period']), match['event'])


def parse(path):
    samples, current = [], None
    for line in Path(path).read_text().splitlines():
        match = HEADER.match(line)
        if match:
            if current is not None:
                samples.append(current)
            pid, tid, stamp, period, event = key(match)
            if event != 'cycles:u':
                raise ValueError('unexpected sampling event: ' + event)
            current = dict(pid=pid, tid=tid, t_ns=stamp, period=period, event=event,
                           comm=match['comm'].strip(), frames=[])
            continue
        frame = FRAME.match(line)
        if frame and current is not None:
            address, symbol, dso = frame.groups()
            if dso == 'inlined':
                raise ValueError('inline expansion found in physical-stack export')
            current['frames'].append(dict(address=address, symbol=re.sub(r'\+0x[0-9a-fA-F]+(?:/0x[0-9a-fA-F]+)?$', '', symbol), dso=dso))
        elif re.search(r'\d+\.\d+:\s+\d+\s+\S+:', line):
            raise ValueError('unrecognized perf sample header: ' + line)
        elif current is not None and re.match(r'^\s+[0-9a-fA-F]+\s+', line):
            raise ValueError('unrecognized physical frame: ' + line)
    if current is not None:
        samples.append(current)
    return samples


def crosscheck(samples, counter_path):
    actual = Counter((s['pid'], s['tid'], s['t_ns'], s['period'], s['event']) for s in samples)
    expected = Counter()
    for line in Path(counter_path).read_text().splitlines():
        if not line.strip():
            continue
        match = COUNTER.match(line)
        if not match:
            raise ValueError('unrecognized counter-only sample: ' + line)
        expected[key(match)] += 1
    if not actual or actual != expected:
        raise ValueError('full-stack and counter-only sample multisets differ')
    return dict(status='success', sample_count=sum(actual.values()),
                period=sum(k[3] * count for k, count in actual.items()))


def loss_diagnostics(record_stderr, perf_report):
    # read_format = ID|LOST describes an enabled capability, not a lost event.
    aggregated = perf_report.split('Aggregated stats:', 1)
    text = aggregated[1].split('cycles:u stats:', 1)[0] if len(aggregated) == 2 else ''
    counts = {name: int(count) for name, count in
              re.findall(r'^\s*([A-Z_]+) events:\s*(\d+)', text, re.M)}
    chunks = [int(v) for v in re.findall(r'lost\s+(\d+)\s+chunks?', record_stderr, re.I)]
    return dict(aggregated_sample_events=counts.get('SAMPLE'),
                reported_lost_records=(counts.get('LOST',0) if text else None),
                reported_lost_sample_records=(counts.get('LOST_SAMPLES',0) if text else None),
                perf_record_reported_lost_chunks=sum(chunks),
                quantified_lost_samples=None,
                note='No reported loss is not proof of lossless acquisition; missing sample weights and ROI membership are unknown.')


def roi(path):
    marks = [json.loads(line) for line in Path(path).read_text().splitlines()]
    selected = [m for m in marks if m['scope'] == 'loop_including_reset']
    if len(selected) != 2 or [m['event'] for m in selected] != ['start', 'end']:
        raise ValueError('expected one complete loop ROI')
    start, end = [m['monotonic_ns'] for m in selected]
    if not start < end:
        raise ValueError('invalid ROI order')
    return start, end


def script(argv):
    if not argv:
        return None
    program = Path(argv[0]).name
    if not re.fullmatch(r'python(?:3(?:\.\d+)?)?', program):
        return program
    for item in argv[1:]:
        if item in ('-c', '-m', '-'):
            return 'python-inline-or-module'
        if not item.startswith('-'):
            return Path(item).name
    return 'python-unknown-script'


def attribute(samples, identity_path):
    windows = defaultdict(list)
    alive = {}
    end = 0
    for line in Path(identity_path).read_text().splitlines():
        item = json.loads(line)
        end = max(end, item['t_ns'])
        pid = item.get('pid')
        if item['event'] == 'identity':
            if pid in alive:
                alive[pid]['end_ns'] = item['t_ns']
            window = dict(item, end_ns=None)
            windows[pid].append(window)
            alive[pid] = window
        elif item['event'] == 'gone' and pid in alive:
            alive.pop(pid)['end_ns'] = item['t_ns']
    for window in alive.values():
        window['end_ns'] = end
    for sample in samples:
        candidates = windows.get(sample['pid'], [])
        # /proc is sampled, so identities are evidence windows, not exact exec times.
        window = next((w for w in reversed(candidates)
                       if w['t_ns'] <= sample['t_ns'] <= w['end_ns'] and w['comm'] == sample['comm']), None)
        reason = 'observed_identity_window'
        if window is None:
            # Bound first-observation uncertainty by one nominal polling interval.
            window = next((w for w in candidates
                           if 0 < w['t_ns'] - sample['t_ns'] <= 10_000_000 and w['comm'] == sample['comm']), None)
            reason = 'first_observation_within_10ms' if window else 'unresolved'
        label = script(window['argv']) if window else None
        sample.update(script=label or ('unknown:' + sample['comm']), identity_basis=reason,
                      argv=window['argv'] if window else [])
    return samples


def profile(samples, interval):
    start, end = interval
    inside = [s for s in samples if start <= s['t_ns'] < end]
    denominator = sum(s['period'] for s in inside)
    if not denominator:
        raise ValueError('no ROI period')
    processes, libraries, functions, contexts = Counter(), Counter(), Counter(), Counter()
    unknown, empty, unknown_symbols, unknown_scripts, estimated_identity = 0, 0, 0, 0, 0
    for sample in inside:
        weight = sample['period']
        frames = sample['frames']
        leaf = frames[0] if frames else dict(symbol='[no-frame]', dso='[unknown]')
        processes[sample['script']] += weight
        libraries[leaf['dso']] += weight
        functions[(leaf['dso'], leaf['symbol'])] += weight
        contexts[(sample['script'], leaf['dso'], leaf['symbol'])] += weight
        unknown += weight if leaf['dso'] == '[unknown]' else 0
        empty += weight if not frames else 0
        unknown_symbols += weight if leaf['symbol'] in ('[unknown]', '[no-frame]') or re.fullmatch(r'0x[0-9a-fA-F]+|[0-9a-fA-F]{12,}', leaf['symbol']) else 0
        unknown_scripts += weight if sample['identity_basis'] == 'unresolved' else 0
        estimated_identity += weight if sample['identity_basis'] == 'first_observation_within_10ms' else 0
    def rows(counter, fields):
        return [dict(zip(fields, k if isinstance(k, tuple) else (k,)), period=v,
                     share_roi=v/denominator) for k, v in counter.most_common()]
    assert sum(libraries.values()) == sum(functions.values()) == sum(processes.values()) == denominator
    return dict(denominator='Complete loop ROI cycles:u raw sample-period sum; unknown samples retained',
                roi_start_ns=start,roi_end_ns=end,roi_samples=len(inside),roi_period=denominator,
                total_samples=len(samples),total_period=sum(s['period'] for s in samples),
                outside_roi_samples=len(samples)-len(inside),
                outside_roi_period=sum(s['period'] for s in samples)-denominator,
                processes=rows(processes,('script',)), libraries=rows(libraries,('dso',)),
                functions=rows(functions,('dso','function')), contexts=rows(contexts,('script','dso','function')),
                quality=dict(unknown_leaf_dso_share=unknown/denominator,empty_stack_share=empty/denominator,
                             unknown_leaf_symbol_share=unknown_symbols/denominator,
                             unresolved_script_share=unknown_scripts/denominator,
                             first_observation_inference_share=estimated_identity/denominator,
                             unknown_categories_may_overlap=True))
