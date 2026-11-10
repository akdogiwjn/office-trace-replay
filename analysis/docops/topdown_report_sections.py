"""Publish seven-component section 7.4 without editing measured evidence/HTML."""
import argparse
import hashlib
import json
from pathlib import Path

import operation_comparison as method
import topdown_hierarchy_comparison as comparison
import unified_scaling_sections as sections

ROOT=method.ROOT
EVIDENCE='docs/evidence/topdown-original-report-update-20261108.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def part(text,a,b):
    return text[text.index(a):text.index(b)]


def publish():
    path=ROOT/sections.ASSESSMENT
    before=path.read_bytes();text=before.decode()
    html=ROOT/'docs/representativeness-assessment.html'
    experimental=ROOT/'docs/experimental-results.md'
    protected={str(p.relative_to(ROOT)):method.sha(p) for p in (html,experimental)}
    result=comparison.load_result()
    for p,h in result['input_sha256'].items():
        comparison.require(method.sha(ROOT/p)==h,'Topdown input changed: '+p)
    original_scale,_=sections.load()
    for p,h in original_scale['input_sha256'].items():
        comparison.require(method.sha(ROOT/p)==h,'Scale input changed: '+p)
    after_text=sections.revise_assessment(text)
    comparison.require(text[:text.index('### 7.4 ')]==after_text[:after_text.index('### 7.4 ')],
                       'Sections before 7.4 changed')
    comparison.require(part(text,'### 7.5 ','### 7.6 ')==part(after_text,'### 7.5 ','### 7.6 '),
                       'Original twelve time-series figures changed')
    comparison.require(text[text.index(method.END):]==after_text[after_text.index(method.END):],
                       'Report suffix changed')
    before76=part(text,'### 7.6 ',method.END)
    after76=part(after_text,'### 7.6 ',method.END)
    # Only the existing Topdown-summary bullet is synchronized in 7.6.
    clean=lambda s:'\n'.join(l for l in s.splitlines() if not l.startswith('- **覆盖权重与瓶颈分别阅读。**'))
    comparison.require(clean(before76)==clean(after76),'Unrelated 7.6 conclusions changed')
    after=after_text.encode()
    extension_path=ROOT/method.PUBLICATION
    extension=json.loads(extension_path.read_text())
    doc=extension['documents'][sections.ASSESSMENT]
    comparison.require(doc['sha256']==digest(before),'Current report identity mismatch')
    prefix=doc['prefix_bytes']
    comparison.require(digest(after[:prefix])==doc['prefix_sha256'],'Original seven-case report changed')
    doc.update(sha256=digest(after),append_sha256=digest(after[prefix:]))
    sources=[str(Path(__file__).relative_to(ROOT)),str(Path(comparison.__file__).relative_to(ROOT)),
        str(Path(sections.__file__).relative_to(ROOT)),comparison.OUTPUT+'/comparison.json',
        comparison.OUTPUT+'/analysis-build.json']
    extension['analysis_sources'].update({p:method.sha(ROOT/p) for p in sources})
    extension['topdown_hierarchy_analysis']=dict(path=comparison.OUTPUT+'/comparison.json',
        sha256=method.sha(ROOT/comparison.OUTPUT/'comparison.json'),
        targets=len(result['targets']),baseline_independent_runs=10,dimensions=7,reference_scale_pp=result['reference_scale_pp'],
        scope='Twelve original tasks: cumulative seven-component cosine and Euclidean comparison; partial PMU diagnostics retained; IPC separate.')
    buildpath=ROOT/'analysis/hotspots/reports/pdf-xlsx-common-hotspots-20261027/build.json'
    build=json.loads(buildpath.read_text())
    build['document_sha256'][sections.ASSESSMENT]=digest(after)
    build['output_sha256']['report.md']=digest(after)
    tmp=path.with_name(path.name+'.tmp');tmp.write_bytes(after);tmp.replace(path)
    method.write(extension_path,extension)
    build['document_extension']['sha256']=method.sha(extension_path)
    method.write(buildpath,build)
    for p,h in protected.items():comparison.require(method.sha(ROOT/p)==h,'Protected document changed: '+p)
    prior=json.loads((ROOT/EVIDENCE).read_text()) if (ROOT/EVIDENCE).exists() else {}
    review=dict(schema='seven-component-cosine-euclidean-report-update-v2',status='passed',
        scope='Section 7.4 plus one consistent 7.6 summary bullet; section 7.3 and figures unchanged',
        before_report_sha256=digest(before),after_report_sha256=method.sha(path),
        initial_report_before_sha256=prior.get('initial_report_before_sha256',prior.get('before_report_sha256',digest(before))),
        protected_files=protected,
        protected_section_sha256={'before_7.4':digest(text[:text.index('### 7.4 ')].encode()),
            '7.3':digest(part(text,'### 7.3 ','### 7.4 ').encode()),
            '7.5':digest(part(text,'### 7.5 ','### 7.6 ').encode())},
        dimensions=7,reference_scale_pp=result['reference_scale_pp'],target_configurations=len(result['targets']),
        nearest_baseline_repeat_envelopes={k:v['own_radius_pp'] for k,v in result['baselines'].items()},
        original_within_reference_scale=[p for p,row in result['targets'].items() if row['within_reference_scale']],
        data_inputs_rechecked=len(result['input_sha256']),scale_inputs_rechecked=len(original_scale['input_sha256']),
        presentation_binding_sha256=method.sha(extension_path),
        html_generated=False,workload_or_collector_run=False)
    method.write(ROOT/EVIDENCE,review)
    print(path)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--publish',action='store_true',required=True)
    p.parse_args()
    publish()
