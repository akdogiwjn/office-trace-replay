#!/usr/bin/env python3
"""Small, source-linked quality summaries for an existing native capture."""
from __future__ import annotations

import re
from collections import Counter

LOST_CHUNKS = re.compile(
    r"\b(?:lost\s+(?P<a>\d+)\s+chunks?|(?P<b>\d+)\s+chunks?\s+lost)\b",
    re.IGNORECASE)
LOST_SAMPLES = re.compile(r"Total Lost Samples:\s*([\d,]+)", re.IGNORECASE)
BUILD_ID_PATH = re.compile(r"/\.build-id/([0-9a-fA-F]{2})/([0-9a-fA-F]+)/elf\b")
ADDR2LINE_WARNING = re.compile(r"addr2line.*could not read first record", re.IGNORECASE)


def parse_lost_chunks(text: str) -> dict:
    """Count perf-record chunk-loss messages, not perf-report lost samples."""
    count = 0
    matched_lines = 0
    for line in text.splitlines():
        match = LOST_CHUNKS.search(line)
        if match:
            count += int(match.group('a') or match.group('b'))
            matched_lines += 1
    return {
        'count': count if matched_lines else None,
        'message_lines': matched_lines,
        'source': 'perf record diagnostic in timestamped stdout log',
        'scope': 'whole perf recording interval; ROI allocation is unknown',
    }


def parse_perf_report_lost_samples(text: str) -> dict:
    values = [int(value.replace(',', '')) for value in LOST_SAMPLES.findall(text)]
    unique = sorted(set(values))
    return {
        'count': unique[0] if len(unique) == 1 else None,
        'reported_values': unique,
        'conflicting_report_values': len(unique) > 1,
        'source': 'Total Lost Samples field in perf report text',
        'scope': 'reported perf.data capture; exact ROI allocation is unknown',
    }


def summarize_addr2line_warnings(text: str) -> dict:
    warning_count = 0
    build_ids = Counter()
    examples = []
    for line in text.splitlines():
        if not ADDR2LINE_WARNING.search(line):
            continue
        warning_count += 1
        match = BUILD_ID_PATH.search(line)
        build_id = (match.group(1) + match.group(2)).lower() if match else '[build-id-unparsed]'
        build_ids[build_id] += 1
        if len(examples) < 5:
            examples.append(line[:300])
    return {
        'warning_count': warning_count,
        'warnings_by_build_id': dict(sorted(build_ids.items())),
        'examples': examples,
        'source': 'perf script stderr log; original stderr file is retained',
        'scope': 'whole export; warning-to-ROI sample attribution is unavailable',
    }


def summarize_native_quality(*, perf_record_log: str, report_text: str,
                              perf_script_stderr: str, roi: dict,
                              export_status: str, parser_exit_code: int | None,
                              perf_report_exit_code: int | None) -> dict:
    parse = roi.get('perf_script_parse', {}) if isinstance(roi, dict) else {}
    recognized = parse.get('recognized_samples_total')
    reported = parse.get('perf_metadata_sample_count')
    text_parse_complete = bool(
        export_status == 'complete' and parser_exit_code == 0
        and recognized is not None and reported is not None
        and recognized == reported)

    roi_period = roi.get('roi_period_total') if isinstance(roi, dict) else None
    roi_metrics = {}
    for category in ('true_unknown_dso', 'unresolved_leaf_symbol',
                     'inline_owner_unresolved', 'inline_recovered', 'empty_stack'):
        samples = parse.get(f'{category}_samples')
        period = parse.get(f'{category}_period')
        roi_metrics[category] = {
            'samples': samples,
            'sample_period': period,
            'roi_period_share': (period / roi_period
                                 if isinstance(period, (int, float)) and roi_period else None),
            'scope': 'ROI samples emitted by parse_native.py',
        }

    return {
        'sample_text_export': {
            'status': 'complete' if export_status == 'complete' else export_status,
            'parser_exit_code': parser_exit_code,
            'recognized_sample_count': recognized,
            'perf_report_sample_count': reported,
            'counts_match': (recognized == reported
                             if recognized is not None and reported is not None else None),
            'complete_for_formal_parse_gate': text_parse_complete,
            'note': 'Text export completion and zero exit code do not establish lossless capture; count equality is checked separately.',
        },
        'capture_loss': {
            'lost_chunks': parse_lost_chunks(perf_record_log),
            'lost_samples': parse_perf_report_lost_samples(report_text),
            'note': 'These are separate counters with different sources; neither is converted into cycles or ROI period.',
        },
        'symbol_resolution': {
            'addr2line_warnings': summarize_addr2line_warnings(perf_script_stderr),
            'roi_categories': roi_metrics,
            'note': 'Unknown DSO, unknown symbol, unresolved inline owner, and recovered inline samples remain separate measures.',
        },
        'perf_report_exit_code': perf_report_exit_code,
    }
