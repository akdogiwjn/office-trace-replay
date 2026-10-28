"""Export reproducible scientific plots of all five independent final results."""
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/office-topdown-matplotlib')

from pilot import ROOT,sha

BOUNDS=('Bad Speculation','Frontend Bound','Backend Bound','Retiring')
GROUPS=(('pdf',('opm','irs_w4','sba1919')),('xlsx',('tlc','hr_metro','egrid','industry_productivity')))
LABELS=dict(opm='OPM',irs_w4='IRS W-4',sba1919='SBA 1919',tlc='TLC',hr_metro='HR Metro',
            egrid='eGRID',industry_productivity='Industry Productivity')


def export(stats,output):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.figure import Figure
    from matplotlib import rc_context
    output=Path(output);figures=[]
    for ds,row in stats.items():
        if row['repeats']!=5 or any(len(row['statistics'][m]['values'])!=5 for m in BOUNDS):
            raise ValueError('plots require all five observed repeats')
    with rc_context({'svg.hashsalt':'office-five-independent-runs','font.family':'DejaVu Sans'}):
        for name,datasets in GROUPS:
            fig=Figure(figsize=(10,5.2));ax=fig.subplots()
            fig.subplots_adjust(left=.08,right=.98,bottom=.18,top=.88)
            for index,ds in enumerate(datasets):
                offset=(index-(len(datasets)-1)/2)*.13
                xs=[i+offset for i in range(4)]
                means=[stats[ds]['statistics'][m]['mean'] for m in BOUNDS]
                sd=[stats[ds]['statistics'][m]['sample_standard_deviation'] for m in BOUNDS]
                color=f'C{index}'
                for feature,m in enumerate(BOUNDS):
                    ys=stats[ds]['statistics'][m]['values']
                    ax.scatter([xs[feature]+(r-2)*.012 for r in range(5)],ys,color=color,
                        alpha=.5,s=28,zorder=3,marker=('o','s','^','D')[index])
                ax.errorbar(xs,means,yerr=sd,fmt='o-',color=color,label=LABELS[ds],capsize=4,
                    linewidth=2.3 if index==0 else 1.6,markersize=5,zorder=4)
            ax.set(xticks=range(4),xticklabels=('Bad speculation','Frontend bound','Backend bound','Retiring'),
                ylabel='Topdown metric (%)',ylim=(0,100),title=name.upper()+': five independent runs per dataset')
            ax.grid(axis='y',alpha=.25);ax.legend(loc='upper center',ncols=2,frameon=False)
            fig.text(.5,.035,'Faint points: all 5 runs. Lines: means. Error bars: sample SD. Horizontal offsets aid visibility.',
                     ha='center',fontsize=8)
            for suffix in ('svg','png'):
                path=output/f'{name}-bound-five-repeats.{suffix}'
                fig.savefig(path,dpi=180,metadata={'Date':None} if suffix=='svg' else {})
                if suffix=='svg':figures.append(dict(filename=path.name,path=str(path.relative_to(ROOT)),
                    sha256=sha(path),title=name.upper()+' 五次独立运行的顶层 Bound 特征',
                    caption='淡点为每次独立运行的最终指标，连线为五次均值，误差棒为样本标准差；横向错位只为区分数据集。'))
    return figures,matplotlib.__version__
