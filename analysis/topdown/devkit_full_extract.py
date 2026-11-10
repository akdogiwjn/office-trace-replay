"""Offline machine-readable extraction of the full DevKit Topdown data.

Consumes a DevKit `devkit.stdout.txt` and produces:

- per-timestep blocks, each associated with a sample index, the original
  `TOP-DOWN Summary Report-N  Time:<ts>` report timestamp, the raw log line
  numbers, the full per-interval metric hierarchy (all levels, not only 9
  leaves), and the raw per-interval event counts including
  `<not counted>` / `<not supported>` markers;
- the final `TOP-DOWN Summary Report-ALL` aggregate report separately (never
  treated as an extra sample point): cycles / instructions / IPC, the full
  final hierarchy and the aggregate PMU event table;
- every `<not counted>` / `<not supported>` marker, kept and flagged; a printed
  0 is never treated as a confirmed zero.

Hierarchy depth is derived from the marker COLUMN of the box-drawing glyphs
(base indent 2 columns, one 4-column segment per depth level) plus the full
indentation, so last-child branches whose continuation is whitespace-only are
recovered correctly (e.g. Memory Bound / L1 Bound, Store Bound / SCA,
Machine Clears / Nuke Flush). Full parent/child paths keep same-named leaves
(e.g. multiple `Pipeline` / `Other`) distinct. Node records keep the original
name, value, '*' approximate marker and absolute log line number.

The `debug: time of PmuRead: <n>` field is retained with its raw value and is
explicitly NOT interpreted as a sampling time axis (values repeat 0/1). No
sampling time is synthesized or interpolated.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

BASE_INDENT = 2
SEG_WIDTH = 4
BOX_LEAF = re.compile(r'[├└]──')


def is_separator(line: str) -> bool:
    return bool(line.strip()) and set(line.strip()) <= {'─'}


def marker_depth(line: str) -> int | None:
    m = BOX_LEAF.search(line)
    if not m:
        return None
    col = m.start()
    return (col - BASE_INDENT) // SEG_WIDTH + 1


def strip_box_glyphs(line: str) -> str:
    return line.replace('├──', '').replace('└──', '').replace('│', '')


def parse_header(lines: list[str], i: int, end: int) -> dict:
    header = {}
    for key in ('Cycles', 'Instructions', 'IPC'):
        for j in range(i, end):
            m = re.match(rf'^{key}\s+([\d.,]+|-\d+\.\d+)\s*$', lines[j])
            if m:
                raw = m.group(1)
                header[key] = (float(raw.replace(',', '')) if (',' in raw or '.' in raw)
                               else int(raw.replace(',', '')))
                break
    return header


def parse_metrics_table(lines: list[str], header_idx: int) -> tuple[dict, list[dict], int]:
    """Parse the metrics table that starts after the header_idx line.

    Layout: `Top-down Metrics` header, a '─' separator, tree lines, then a '─'
    separator ending the table. Returns (header, nodes, table_end_line).
    """
    header = parse_header(lines, header_idx + 1, header_idx + 12)
    start = header_idx + 1
    while start < len(lines) and 'Top-down Metrics' not in lines[start]:
        start += 1
    start += 1
    while start < len(lines) and not is_separator(lines[start]):
        start += 1
    start += 1  # skip the header separator
    nodes = []
    stack = []
    end = start
    while end < len(lines) and not is_separator(lines[end]):
        line = lines[end]
        if not line.strip():
            end += 1
            continue
        depth = marker_depth(line)
        if depth is None:
            depth = 0
        rest = strip_box_glyphs(line).lstrip()
        m = re.match(r'^(.*?)\s+(-?\d+\.\d+)\s+(.*)$', rest)
        if not m:
            end += 1
            continue
        name, value, event = m.group(1).strip(), float(m.group(2)), m.group(3).strip()
        while len(stack) > depth:
            stack.pop()
        parent = stack[-1] if stack else None
        path = (parent + '/' + name) if parent else name
        stack.append(path)
        nodes.append({'name': name, 'depth': depth, 'path': path, 'value': value,
                      'value_pct': value,
                      'approximate': name.endswith('*'),
                      'preferred_event': None if event in ('--', '-') else event,
                      'parent_path': parent, 'line': end + 1})
        end += 1
    end += 1  # skip the table-end separator
    return header, nodes, end


def parse_event_block(lines: list[str], i: int, seg_end: int) -> tuple[dict, int]:
    """Event-count block between the `time of PmuRead` line and seg_end."""
    raw_line = lines[i]
    m = re.search(r'time of PmuRead:\s*(\S+)', raw_line)
    pmu_raw = m.group(1) if m else None
    events = {}
    flags = []
    for j in range(i + 1, seg_end):
        e = re.match(r'.*event name: (r[0-9a-f]+), event count: (.+)$', lines[j])
        if not e:
            continue
        name, raw = e.group(1), e.group(2).strip()
        if raw.startswith('<'):
            events[name] = None
            flags.append({'event': name, 'flag': raw, 'line': j + 1})
        else:
            events[name] = int(raw.replace(',', ''))
    return {'pmu_line': i + 1, 'pmu_raw': pmu_raw, 'events': events, 'flags': flags}, seg_end


def report_header_index(lines: list[str], start: int, end: int) -> tuple[str | None, str | None, int | None]:
    for j in range(start, end):
        m = re.match(r'^TOP-DOWN Summary Report-(\d+|ALL)\s+Time:(.+)$', lines[j])
        if m:
            return m.group(1), m.group(2).strip(), j
    return None, None, None


def parse_final_events(lines: list[str], start: int) -> dict:
    events = {}
    for j in range(start, len(lines)):
        m = re.match(r'^\s*(r[0-9a-f]+)\s+([\d,]+)\s*$', lines[j])
        if m:
            events[m.group(1)] = int(m.group(2).replace(',', ''))
    return events


def extract(text: str) -> dict:
    lines = text.splitlines()
    pmu_indices = [i for i, l in enumerate(lines) if 'time of PmuRead' in l]
    timesteps = []
    for idx, p in enumerate(pmu_indices):
        seg_end = pmu_indices[idx + 1] if idx + 1 < len(pmu_indices) else len(lines)
        events, _ = parse_event_block(lines, p, seg_end)
        report_no, report_time, report_line = report_header_index(lines, p, seg_end)
        header, hierarchy, _end = {}, [], seg_end
        if report_no is not None and report_no != 'ALL':
            header, hierarchy, _end = parse_metrics_table(lines, report_line)
        timesteps.append({
            'sample_index': idx,
            'report_no': report_no,
            'report_time': report_time,
            'report_line': report_line + 1 if report_line is not None else None,
            'pmu_line': events['pmu_line'],
            'pmu_raw_time_of_pmuread': events['pmu_raw'],
            'pmu_read_is_not_sample_time': True,
            'events': events['events'],
            'event_flags': events['flags'],
            'header': header,
            'hierarchy': hierarchy,
        })

    all_line = next((i for i, l in enumerate(lines) if 'TOP-DOWN Summary Report-ALL' in l), None)
    final = {'report_line': all_line + 1 if all_line is not None else None,
             'report_time': None, 'header': {}, 'hierarchy': [], 'pmu_events': {}}
    if all_line is not None:
        m = re.match(r'^TOP-DOWN Summary Report-ALL\s+Time:(.+)$', lines[all_line])
        final['report_time'] = m.group(1).strip() if m else None
        header, hierarchy, table_end = parse_metrics_table(lines, all_line)
        final['header'] = header
        final['hierarchy'] = hierarchy
        final['pmu_events'] = parse_final_events(lines, table_end)
    return {
        'schema': 'devkit-full-extract-v1',
        'final': final,
        'timesteps': timesteps,
        'not_counted_markers': sorted(set(re.findall(r'<(not counted|not supported)[^>]*>', text))),
        'note': ('per-timestep and final event counts are raw; <not counted>/<not supported> kept '
                 'and flagged; printed 0 is not treated as confirmed zero; children recorded with '
                 'full parent paths and not summed independently; "time of PmuRead" is a raw debug '
                 'field, not a sampling time axis (values repeat 0/1); Report-ALL is kept separate '
                 'from per-interval sample points.'),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stdout_txt', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    result = extract(args.stdout_txt.read_text(encoding='utf-8', errors='replace'))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tops = [n for n in result['final']['hierarchy'] if n['depth'] == 0]
    print(json.dumps({'schema': result['schema'],
                      'timesteps': len(result['timesteps']),
                      'final_hierarchy_nodes': len(result['final']['hierarchy']),
                      'final_top_nodes': [n['name'] for n in tops],
                      'final_pmu_events': len(result['final']['pmu_events']),
                      'not_counted_markers': result['not_counted_markers']},
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
