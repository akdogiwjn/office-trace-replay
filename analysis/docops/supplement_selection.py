"""Compare original-task supplements on the frozen twelve large-task profiles."""
from collections import Counter
from itertools import combinations
import json
from pathlib import Path

import operation_comparison as method
import operation_equivalence_deep as operation
import unified_scaling_sections as scaling

ROOT=method.ROOT
OUTPUT='analysis/docops/processed/supplement-selection-20261116'
TARGET_MEAN=90.0


def require(ok,message):
    if not ok:raise ValueError(message)


def make_model(scale,accounted,mode):
    require(mode in ('exact','operation'),'Unknown coverage mode')
    names=sorted(scale['groups'])
    old={method.key(f) for c in scale['references'].values() for f in c['functions']}
    keys={p:{method.key(f) for f in scale['cases'][p]['functions']} for p in names}
    proof={p:operation.witnesses({p:scale['cases'][p]}) for p in names}
    cases={}
    for p in names:
        c=accounted['cases'][p]
        base=c['periods']['exact']+(c['periods']['same_operation'] if mode=='operation' else 0)
        masks=Counter();functions=[]
        for f in c['functions']:
            eligible=method.key(f) not in old if mode=='exact' else f['bucket'] in ('separate_operation','other_resolved')
            if not eligible:continue
            family=operation.family(f)
            witnesses={}
            for n in names:
                if method.key(f) in keys[n]:
                    witnesses[n]=dict(kind='exact',library=f['library'],function=f['function'])
                elif mode=='operation' and proof[n].get(family):
                    witness=proof[n][family][0]
                    witnesses[n]=dict(kind='operation',family=family,library=witness['library'],function=witness['function'])
            mask=sum(1<<names.index(n) for n in witnesses)
            masks[mask]+=f['period']
            functions.append(dict(library=f['library'],function=f['function'],period=f['period'],
                                  family=family,mask=mask,witnesses=witnesses))
        require(base+sum(masks.values())+c['periods']['unresolved']==c['roi_period'],
                'Coverage partition does not conserve ROI: '+mode+'/'+p)
        cases[p]=dict(base_period=base,roi_period=c['roi_period'],unresolved_period=c['periods']['unresolved'],
                      masks=dict(masks),functions=functions)
    return dict(mode=mode,candidates=names,cases=cases)


def evaluate(model,selected,detail=False):
    require(len(set(selected))==len(selected),'Duplicate candidate')
    require(set(selected)<=set(model['candidates']),'Unknown candidate')
    mask=sum(1<<model['candidates'].index(p) for p in selected)
    cases={}
    for p,c in model['cases'].items():
        gain=sum(period for k,period in c['masks'].items() if k&mask)
        cases[p]=dict(base_pct=100*c['base_period']/c['roi_period'],
            added_pct=100*gain/c['roi_period'],coverage_pct=100*(c['base_period']+gain)/c['roi_period'],
            added_period=gain,roi_period=c['roi_period'],unresolved_pct=100*c['unresolved_period']/c['roi_period'])
        if detail:
            rows=[]
            for f in c['functions']:
                matched=[n for n in selected if n in f['witnesses']]
                if matched:
                    winner=min(matched,key=lambda n:(f['witnesses'][n]['kind']!='exact',n))
                    rows.append(dict(library=f['library'],function=f['function'],period=f['period'],
                        share_pct=100*f['period']/c['roi_period'],candidate=winner,witness=f['witnesses'][winner]))
            require(sum(r['period'] for r in rows)==gain,'Supplement double count: '+p)
            cases[p]['functions']=rows
    scores=[c['coverage_pct'] for c in cases.values()]
    return dict(selected=sorted(selected),mean_pct=sum(scores)/len(scores),min_pct=min(scores),max_pct=max(scores),
                at_least90_count=sum(v>=90 for v in scores),cases=cases)


def search(model):
    frontier=[];solutions=[]
    for count in range(len(model['candidates'])+1):
        best=None;qualified=[]
        for ids in combinations(model['candidates'],count):
            row=evaluate(model,ids)
            if best is None or row['mean_pct']>best['mean_pct']:best=row
            if row['mean_pct']>=TARGET_MEAN:qualified.append(row)
        frontier.append(best)
        if qualified and not solutions:
            solutions=sorted(qualified,key=lambda r:(-r['mean_pct'],r['selected']))
    return dict(reference_mean_pct=TARGET_MEAN,minimum_count=len(solutions[0]['selected']) if solutions else None,
                minimum_solutions=solutions,frontier=frontier,subsets_evaluated=2**len(model['candidates']))


def gather():
    scale,_=scaling.load();accounted=operation.load()
    modes={}
    for mode in ('exact','operation'):
        model=make_model(scale,accounted,mode)
        selected=search(model)
        selected.update(base=evaluate(model,[]),all_originals=evaluate(model,model['candidates']),
            primary=evaluate(model,['013','021'] if mode=='exact' else ['009','021'],True),
            ppt_only=evaluate(model,['021']),with_table_styles=evaluate(model,['009','021','029']))
        modes[mode]=selected
    oldlibs={r['library'] for c in scale['references'].values() for r in c['functions']}
    new=Counter();shared=Counter()
    for c in accounted['cases'].values():
        for f in c['functions']:
            if f['bucket']!='exact':
                (shared if f['library'] in oldlibs else new)[f['library']]+=100*f['period']/c['roi_period']/12
    return dict(schema='original-supplement-selection-v1',targets={p:c['task'] for p,c in accounted['cases'].items()},
        candidates=sorted(scale['groups']),modes=modes,
        averaging='Arithmetic mean of twelve per-task full-ROI cycle-weight coverages; not pooled periods or function counts',
        selection_reference='Mean coverage 90% is a compact-selection target, not a representativeness test or a per-task guarantee',
        operation_selection='021 for image/deck paths; 009 for long-document Writer paths; alternatives may witness the same broad Word family',
        unknown_policy='Unresolved weight retained in each full ROI denominator and never credited',
        new_library_residual_mean_pct=dict(new.most_common()),existing_library_residual_mean_pct=dict(shared.most_common()),
        inputs={scaling.ANALYSIS+'/comparison.json':method.sha(ROOT/scaling.ANALYSIS/'comparison.json'),
                operation.OUTPUT+'/comparison.json':method.sha(ROOT/operation.OUTPUT/'comparison.json'),
                operation.OUTPUT+'/analysis-build.json':method.sha(ROOT/operation.OUTPUT/'analysis-build.json')},
        workload_or_collector_run=False,html_modified=False)


def build():
    data=gather();folder=ROOT/OUTPUT
    folder.mkdir(parents=True,exist_ok=True)
    method.write(folder/'comparison.json',data)
    lines=['# 原始用例补充组合核算','',data['averaging'],'',data['selection_reference'],'']
    for mode in ('exact','operation'):
        r=data['modes'][mode]
        lines.extend(['## '+mode,'',f"Base mean: {r['base']['mean_pct']:.6f}%",'',
            f"Minimum count for mean >=90%: {r['minimum_count']}",'',
            method.table(['Count','Best mean','Selected','Minimum individual'],[
                [len(s['selected']),f"{s['mean_pct']:.6f}%",','.join(s['selected']),f"{s['min_pct']:.6f}%"] for s in r['frontier']]),'',
            '### Report pair','',method.table(['Task','Before','After','Added'],[
                [p,f"{c['base_pct']:.6f}%",f"{c['coverage_pct']:.6f}%",f"{c['added_pct']:.6f} pp"]
                for p,c in r['primary']['cases'].items()]),''])
    (folder/'analysis.md').write_text('\n'.join(lines))
    source=str(Path(__file__).relative_to(ROOT))
    method.write(folder/'analysis-build.json',dict(inputs=data['inputs'],sources={source:method.sha(ROOT/source)},
        outputs={p:method.sha(folder/p) for p in ('comparison.json','analysis.md')}))


def load():
    folder=ROOT/OUTPUT;b=json.loads((folder/'analysis-build.json').read_text())
    for p,h in {**b['inputs'],**b['sources']}.items():require(method.sha(ROOT/p)==h,'Selection input changed: '+p)
    for p,h in b['outputs'].items():require(method.sha(folder/p)==h,'Selection output changed: '+p)
    return json.loads((folder/'comparison.json').read_text())


if __name__=='__main__':build()
