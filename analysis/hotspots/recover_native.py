"""Offline recovery after completed record/export; never launches a workload or perf."""
import argparse
import json
from pathlib import Path

from collect_native import capture_quality
from native_profile import attribute, crosscheck, parse, profile, roi
from pilot import HERE, ROOT, report, sha, write


def recover(raw):
    raw=Path(raw).resolve()
    out=raw/'out'
    original=json.loads((out/'collection.json').read_text())
    launch=json.loads((raw/'launch.json').read_text())
    if not (original['workload_status']=='success' and original['perf_record_status']=='success'
            and original['export_status']=='success' and original['perf_record_returncode']==0):
        raise ValueError('recovery requires a successful workload, recording, and complete export')
    index=json.loads((out/'sha256-index.json').read_text())
    for item in index['files']:
        p=out/item['path']
        if p.stat().st_size!=item['size'] or sha(p)!=item['sha256']:
            raise ValueError('original capture hash mismatch: '+str(p))
    samples=parse(out/'samples.txt')
    checked=crosscheck(samples,out/'counter-samples.txt')
    summary=out/original['runner_summary']
    value=profile(attribute(samples,out/'identities.jsonl'),roi(summary.parent/'iteration-0001/roi.jsonl'))
    dataset=original['dataset_id']
    value.update(dataset_id=dataset,pdf_applicant_count=10 if dataset in ('irs_w4','sba1919') else None,
                 image_id=original['actual_image_id'])
    value['capture_quality']=capture_quality((out/'perf-record.stderr').read_text(),
        (out/'perf-report.txt').read_text(),(out/'samples.txt.stderr').read_text())
    if value['capture_quality']['aggregated_sample_events']!=len(samples):
        raise ValueError('sample count differs from perf metadata')
    destination=HERE/'reports'/(raw.name+'-offline-recovery')
    destination.mkdir(parents=True,exist_ok=False)
    write(destination/'profile.json',value)
    record=dict(status='success',kind='offline_parse_recovery',workload_rerun=False,
        original_collection_status=original['status'],original_collection_sha256=sha(out/'collection.json'),
        raw_directory=str(raw.relative_to(ROOT)),raw_index_sha256=sha(out/'sha256-index.json'),
        raw_files_checked=len(index['files']),sample_crosscheck=checked,
        actual_image_id=value['image_id'],profile_sha256=sha(destination/'profile.json'),
        analysis_source_sha256={p.name:sha(p) for p in HERE.glob('*.py')})
    write(destination/'recovery.json',record)
    result=report(raw,launch,suffix='-recovered-report',profile_path=destination/'profile.json')
    pointer=dict(status='success',dataset_id=dataset,report=result,raw=str(raw.relative_to(ROOT)),
        image_id=value['image_id'],recovery=str((destination/'recovery.json').relative_to(ROOT)))
    write(HERE/f'reports/latest-{dataset}.json',pointer)
    print(json.dumps(pointer))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw',type=Path,required=True)
    recover(parser.parse_args().raw)
