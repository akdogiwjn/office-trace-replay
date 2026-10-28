"""Offline arithmetic checks of saved DevKit diagnostics; never runs a workload."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze(text):
    summary = text[text.index('TOP-DOWN Summary'):]
    events = {k: int(v.replace(',', '')) for k, v in re.findall(
        r'^  (r[0-9a-f]+) +([0-9,]+)\s*$', summary, re.M)}
    uncounted = sorted(set(re.findall(
        r'event name: (r[0-9a-f]+), event count: <not counted>', text)))
    c, i, s, f = (events[k] for k in ('r0011', 'r0008', 'r001b', 'r2011'))
    calculated = {'IPC': i / c, 'Retiring': 100 * i / (6 * c),
                  'Bad Speculation': 100 * (s - i) / (6 * c),
                  'Frontend Bound': 100 * f / (6 * c)}
    calculated['Backend Bound'] = 100 - sum(calculated[k] for k in
        ('Retiring', 'Bad Speculation', 'Frontend Bound'))
    if 'r2012' in events:
        calculated['Fetch Latency Bound'] = 100 * events['r2012'] / c
        calculated['Fetch Bandwidth Bound'] = calculated['Frontend Bound'] - calculated['Fetch Latency Bound']
    # These reproduce the printed result, not an independently sourced PMU specification.
    if all(k in events for k in ('r7001', 'r7005', 'r7006')) and events['r7001']:
        calculated['Memory Bound'] = calculated['Backend Bound'] * (events['r7005'] + events['r7006']) / events['r7001']
        calculated['Core Bound'] = calculated['Backend Bound'] - calculated['Memory Bound']
    checks = []
    for metric, value in calculated.items():
        match = re.search(r'\b' + re.escape(metric) + r'\s+(\d+\.\d+)', summary)
        if match:
            reported = float(match[1])
            error = abs(value - reported)
            if error > .00501:
                raise ValueError(f'{metric}: arithmetic mismatch {value} vs {reported}')
            checks.append(dict(metric=metric,reported=reported,recalculated=value,
                               absolute_error=error,within_print_precision=True))
    return dict(events=events,debug_not_counted_events=uncounted,checks=checks,
                printed_zero_is_not_independently_confirmed_zero=bool(uncounted))


def main(directory):
    directory = Path(directory)
    results = {}
    for path in sorted(directory.glob('devkit-*-short-probe.json')):
        saved = json.loads(path.read_text())
        if saved.get('returncode') != 0:
            results[path.name] = dict(status='failed_probe_preserved',sha256=sha(path))
            continue
        results[path.name] = dict(status='arithmetic_checked',sha256=sha(path),**analyze(saved['stdout']))
    cpu_file = directory/'devkit-cpu-scope-container.stdout.txt'
    results[cpu_file.name] = dict(status='arithmetic_checked',sha256=sha(cpu_file),**analyze(cpu_file.read_text()))
    direct = results['devkit-level1-short-probe.json']['events']['r0011']
    descendant = results['devkit-descendant-short-probe.json']['events']['r0011']
    output = dict(schema='devkit-probe-arithmetic-v1',analysis_sha256=sha(Path(__file__)),
        formula_evidence='Empirical reproduction of this pinned DevKit binary output; not an official HIP09 formula specification',
        probes=results,scope_test=dict(direct_cycles=direct,descendant_launcher_cycles=descendant,
            descendant_to_direct_ratio=descendant/direct,launch_mode_child_coverage_verified=False,
            cpu_scope_detected_separate_busy_process=True),formal_document_workload_started=False)
    (directory/'arithmetic-verification.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(f'Checked {sum(r["status"]=="arithmetic_checked" for r in results.values())} saved probes; failed attempts preserved.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    main(parser.parse_args().directory)
