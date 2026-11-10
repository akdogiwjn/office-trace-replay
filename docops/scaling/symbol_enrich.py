"""Offline symbol enrichment for the four scaling-campaign perf captures.

Reuses the existing verified recovery pipeline (recover_perf.py inside the
original unified image) and the build-id exact-match openEuler debug files from
`analysis/docops/symbol-search/20261104-unified/`. Each capture's perf.data is
re-exported inside the original image (cpuset 9, network none) with the matched
.debug files read-only mounted at their build-id debug path. The original
capture directory is mounted read-only; outputs go to a fresh directory.

No workload, replay, perf record or DevKit is run. Sample keys, period,
physical leaf address and DSO identity must remain byte-identical; only symbol
name resolution may change.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ANALYSIS = ROOT / 'analysis' / 'docops'
sys.path.insert(0, str(ANALYSIS))

from enrich_unified import prepare_symbols  # noqa: E402
from pilot import DOCKER, sha, write  # noqa: E402
from campaign import check_archive  # noqa: E402

VARIANTS = ['014-n1000', '014-n10000', '021-g5', '021-g10']
SOURCE_FILES = ('recover_perf.py', 'quality.py', 'native_adapter.py', 'enrich_unified.py',
                'native_profile.py', 'native_capture_helpers.py')


def copy_sources(destination: Path):
    src = destination / 'source'
    src.mkdir()
    for name in ('recover_perf.py', 'quality.py', 'native_adapter.py', 'enrich_unified.py'):
        shutil.copy2(ANALYSIS / name, src / name)
    shutil.copy2(ROOT / 'analysis/hotspots/native_profile.py', src / 'native_profile.py')
    shutil.copy2(ROOT / 'analysis/hotspots/collect_native.py', src / 'native_capture_helpers.py')
    return {p.name: sha(p) for p in src.iterdir()}


def verify_build_ids(original: Path, rows: list[dict]) -> dict:
    builds = {}
    for line in (original / 'buildids.txt').read_text().splitlines():
        bid, _, path = line.partition(' ')
        builds[path.strip()] = bid
    checked = []
    for row in rows:
        if row['runtime_path'] in builds:
            match = builds[row['runtime_path']] == row['build_id']
            checked.append({'runtime_path': row['runtime_path'],
                            'capture_build_id': builds[row['runtime_path']],
                            'symbol_build_id': row['build_id'], 'match': match})
            if not match:
                raise ValueError(f"capture ELF build-id mismatch: {row['runtime_path']}")
    return {'matched_runtime_paths': checked,
            'capture_elfs_with_symbols': len(checked)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True,
                        help='scaling campaign dir (results/docops/scaling-performance-<ts>)')
    parser.add_argument('--search', type=Path, required=True,
                        help='symbol-search dir with search-results.json + debugfiles/')
    parser.add_argument('--output', type=Path, required=True,
                        help='new output dir (must not exist)')
    args = parser.parse_args(argv)
    campaign = args.campaign.resolve()
    search = args.search.resolve()
    output = args.output.resolve()
    if output.exists() and any(output.rglob('*')):
        raise ValueError('refusing to reuse non-empty output: ' + str(output))
    output.mkdir(parents=True, exist_ok=True)
    os.sched_setaffinity(0, {9})

    state = json.loads((campaign / 'campaign.json').read_text())
    search_record = json.loads((search / 'search-results.json').read_text())
    image_id = state['preflight']['image_id']
    if image_id != search_record['image_id']:
        raise ValueError('capture/symbol image mismatch')
    if state['status'] != 'passed':
        raise ValueError('campaign not passed')

    symbols = output / 'symbols'
    rows = prepare_symbols(search, symbols)
    source_sha256 = copy_sources(output)
    record = dict(schema='docops-scaling-symbol-enrichment-v1', status='running',
                  image_id=image_id,
                  campaign=str(campaign.relative_to(ROOT)),
                  search=str(search.relative_to(ROOT)),
                  search_record_sha256=sha(search / 'search-results.json'),
                  symbol_index_sha256=sha(symbols / 'index.json'),
                  source_sha256=source_sha256,
                  workload_rerun=False, perf_record_rerun=False, topdown_rerun=False,
                  tasks={}, started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    path = output / 'enrichment.json'
    write(path, record)
    try:
        for variant in VARIANTS:
            raw = ROOT / state['tasks'][variant]['perf']['raw']
            original = raw / 'perf' / 'out'
            if not (original / 'perf.data').is_file():
                raise ValueError(f'{variant} perf.data missing')
            original_archive = check_archive(original)
            baseline_profile = json.loads((original / 'profile.json').read_text())
            builds_check = verify_build_ids(original, rows)
            folder = output / variant
            out = folder / 'out'
            folder.mkdir()
            out.mkdir()
            argv = DOCKER + ['create', '--name', f'docops-enrich-{variant}-{output.name}'.lower(),
                             '--network', 'none', '--cpuset-cpus', '9',
                             '--mount', f'type=bind,source={original},target=/original,readonly',
                             '--mount', f'type=bind,source={output/"source"},target=/opt/docops-measurement,readonly',
                             '--mount', f'type=bind,source={symbols},target=/analysis-symbols,readonly',
                             '--mount', f'type=bind,source={out},target=/results']
            for row in rows:
                argv += ['--mount',
                         f"type=bind,source={symbols / row['path']},target=/usr/lib/debug/{row['path']},readonly"]
            argv += ['--entrypoint', 'python3', image_id, '-B',
                     '/opt/docops-measurement/recover_perf.py', '--allow-limited',
                     '--symbols', '/analysis-symbols']
            cid = subprocess.check_output(argv, text=True, timeout=60).strip()
            before = json.loads(subprocess.check_output(DOCKER + ['inspect', cid], text=True))[0]
            write(folder / 'container-before.json', before)
            if before['Image'] != image_id or before['HostConfig']['NetworkMode'] != 'none':
                raise ValueError('wrong offline image/network')
            if any(m['RW'] for m in before['Mounts'] if m['Destination'] != '/results'):
                raise ValueError('writable offline input')
            record['active_task'] = variant
            write(path, record)
            print('OFFLINE EXPORT ' + variant, flush=True)
            with (folder / 'container.log').open('x') as log:
                try:
                    cp = subprocess.run(DOCKER + ['start', '-a', cid], stdout=log,
                                        stderr=subprocess.STDOUT, timeout=1800)
                except BaseException:
                    subprocess.run(DOCKER + ['stop', '-t', '3', cid], capture_output=True, timeout=15)
                    raise
            after = json.loads(subprocess.check_output(DOCKER + ['inspect', cid], text=True))[0]
            write(folder / 'container-after.json', after)
            value = json.loads((out / 'recovery-record.json').read_text())
            if cp.returncode or after['State']['ExitCode'] or value['status'] != 'passed':
                raise RuntimeError(f'offline export failed: {variant} {value.get("error")}')
            if not value['original_evidence_unchanged']:
                raise ValueError('original evidence changed')
            # compare enriched vs baseline functions (per-DSO totals, DSO improvement, new tops)
            enriched = json.loads((out / 'profile.json').read_text())
            before_totals = collections.Counter()
            for f in baseline_profile['functions']:
                before_totals[f['dso']] += f['period']
            after_totals = collections.Counter()
            for f in enriched['functions']:
                after_totals[f['dso']] += f['period']
            if dict(before_totals) != dict(after_totals):
                raise ValueError('DSO period accounting changed: ' + variant)
            unknown_before = [f for f in baseline_profile['functions']
                              if f.get('function') in ('[unknown]', None)]
            unknown_after = [f for f in enriched['functions']
                             if f.get('function') in ('[unknown]', None)]
            dso_improve = {}
            for f in unknown_before:
                dso_improve[f['dso']] = {'before_period': f['period']}
            for f in unknown_after:
                dso_improve.setdefault(f['dso'], {})['after_period'] = f['period']
            top_new = [r for r in enriched['functions'][:20] if not (r.get('function') in ('[unknown]', None))]
            record['tasks'][variant] = dict(
                status=value['status'], out=str(out.relative_to(ROOT)),
                container_id=cid, original_archive=original_archive,
                builds_check=builds_check,
                record_sha256=sha(out / 'recovery-record.json'),
                quality_before=value['quality_before'], quality_after=value['quality_after'],
                function_qualification=value['function_qualification'],
                roi_samples=value['roi_samples'], roi_period=value['roi_period'],
                unknown_leaf_share_before=value['quality_before']['unknown_leaf_symbol_share'],
                unknown_leaf_share_after=value['quality_after']['unknown_leaf_symbol_share'],
                dso_unknown_improvement={d: {k: v for k, v in x.items() if k in ('before_period', 'after_period')}
                                         for d, x in dso_improve.items()},
                top_resolved_functions_after=top_new,
                archive=check_archive(out), profile_sha256=sha(out / 'profile.json'))
            write(path, record)
            print(f"DONE {variant}: "
                  f"{100*value['quality_before']['unknown_leaf_symbol_share']:.3f}% -> "
                  f"{100*value['quality_after']['unknown_leaf_symbol_share']:.3f}%", flush=True)
        record['status'] = 'passed'
        record['active_task'] = None
    except BaseException as exc:
        record.update(status='failed', error=f'{type(exc).__name__}: {exc}',
                      traceback=traceback.format_exc())
    finally:
        record['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        record['not_processed'] = [v for v in VARIANTS if v not in record['tasks']]
        write(path, record)
    print(json.dumps({'status': record['status'], 'output': str(output),
                      'error': record.get('error')}, ensure_ascii=False), flush=True)
    return 0 if record['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
