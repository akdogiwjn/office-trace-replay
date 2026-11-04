"""Offline symbol recovery. Run in the original image with /original read-only."""
import hashlib
import json
from pathlib import Path
import sys
import traceback
import argparse
from collections import Counter
from itertools import zip_longest

from quality import function_qualification, select_samples, verify_symbols, workload_records
from native_adapter import attribute, crosscheck, leaf_records, loss_diagnostics, parse, profile
from native_capture_helpers import bounded, write


def file_sha256(path):
    """Hash multi-GB perf inputs without allocating their complete contents."""
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-limited',action='store_true',help='Keep valid acquisition with incomplete symbols explicitly limited')
    parser.add_argument('--symbols',default='/usr/lib/debug',help='Verified analysis-only symbol index root')
    args=parser.parse_args()
    original, out = Path('/original'), Path('/results')
    if list(out.iterdir()):
        raise ValueError('recovery output must be empty')
    record = {'schema':'docops-offline-symbol-recovery-v1', 'status':'running',
              'workload_rerun':False, 'perf_record_rerun':False,
              'formal_similarity_eligible':False}
    try:
        before = {name:file_sha256(original/name)
                  for name in ('perf.data','collection.json','samples.txt','sha256-index.json')}
        old = json.loads((original/'collection.json').read_text())
        record.update(original_sha256=before, original_collection_status=old['status'],
                      debug_symbols=verify_symbols(args.symbols),
                      perf_version=__import__('subprocess').check_output(['perf','version'],text=True).strip())
        counts, _, intervals = workload_records(original, old['task'], old['loops'])
        bounded(['perf','script','--no-inline','--ns','-F','+pid','-i',str(original/'perf.data')],out/'samples.txt')
        samples = parse(out/'samples.txt')
        record['sample_crosscheck'] = crosscheck(samples, original/'counter-samples.txt')
        dispatcher = json.loads((original/'measurement-ready.json').read_text())['pid']
        selected, excluded = select_samples(samples, intervals, dispatcher)
        attribute(selected, original/'identities.jsonl')
        result = profile(selected, (intervals[0][0],intervals[-1][1]))
        result.update(denominator='Union of workflow intervals, dispatcher excluded; raw cycles:u sample period',
                      all_recorded_samples=len(samples),all_recorded_period=sum(s['period'] for s in samples),
                      excluded_period=excluded,exact_interval_filtering=True,dispatcher_pid_excluded=dispatcher,
                      capture_quality=loss_diagnostics((original/'perf-record.stderr').read_text(),
                                                       (original/'perf-report.txt').read_text()))
        baseline = json.loads((original/'profile.json').read_text())
        for key in ('roi_samples','roi_period','all_recorded_samples','all_recorded_period','excluded_period','processes'):
            if result[key] != baseline[key]:
                raise ValueError('symbol recovery changed sample/DSO accounting: '+key)
        original_dso=Counter()
        for before_leaf,after_sample in zip_longest(leaf_records(original/'samples.txt'),samples):
            if before_leaf is None or after_sample is None:raise ValueError('original sample count changed')
            key=tuple(after_sample[k]for k in ('pid','tid','t_ns','period','event'))
            leaf=(after_sample['frames'][0]['address'],after_sample['frames'][0]['dso'])if after_sample['frames']else None
            if before_leaf['key']!=key or before_leaf['leaf']!=leaf:
                raise ValueError('original physical leaf address, DSO or sample key changed')
            if after_sample['pid']!=dispatcher and any(s<=after_sample['t_ns']<e for s,e in intervals):
                original_dso[leaf[1]if leaf else'[unknown]']+=after_sample['period']
        if dict(original_dso)!= {r['dso']:r['period']for r in result['libraries']}:
            raise ValueError('original physical DSO period changed')
        prior_dso={r['dso']:r['period']for r in baseline['libraries']}
        record['dso_parser_correction']={'needed':prior_dso!=dict(original_dso),
            'old_library_totals':prior_dso if prior_dso!=dict(original_dso)else None,
            'corrected_library_totals':dict(original_dso)if prior_dso!=dict(original_dso)else None,
            'all_original_sample_keys_addresses_and_dsos_verified':True}
        write(out/'profile.json',result)
        record.update(counts=counts, roi_seconds=sum(e-s for s,e in intervals)/1e9,
                      quality_before=baseline['quality'],quality_after=result['quality'],
                      roi_samples=result['roi_samples'],roi_period=result['roi_period'])
        qualification=function_qualification(result['quality'])
        record['function_qualification']=qualification
        if not qualification['stack_eligible'] or (not qualification['function_profile_eligible'] and not args.allow_limited):
            raise ValueError('symbol quality still insufficient')
        after = {name:file_sha256(original/name) for name in before}
        if before != after:
            raise ValueError('original evidence changed')
        record.update(status='passed', original_evidence_unchanged=True,
                      qualification='process, DSO and physical leaf-function pilot; unresolved symbols retained')
    except BaseException as exc:
        record.update(status='failed',error=f'{type(exc).__name__}: {exc}',traceback=traceback.format_exc())
    finally:
        write(out/'recovery-record.json',record)
        write(out/'sha256-index.json',{'files':{str(p.relative_to(out)):{'bytes':p.stat().st_size,
              'sha256':file_sha256(p)} for p in sorted(out.rglob('*'))
              if p.is_file() and p.name!='sha256-index.json'}})
    print(json.dumps(record,ensure_ascii=False),flush=True)
    return 0 if record['status']=='passed' else 1


if __name__=='__main__':
    raise SystemExit(main())
