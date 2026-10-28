"""Export saved interval metrics with explicit boundaries between independent runs."""
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR', '/tmp/office-topdown-matplotlib')

from pilot import ROOT, sha

BOUNDS = ('Bad Speculation', 'Frontend Bound', 'Backend Bound', 'Retiring')
GROUPS = (('pdf', ('opm', 'irs_w4', 'sba1919')),
          ('xlsx', ('tlc', 'hr_metro', 'egrid', 'industry_productivity')))
LABELS = dict(opm='OPM', irs_w4='IRS W-4', sba1919='SBA 1919', tlc='TLC', hr_metro='HR Metro',
              egrid='eGRID', industry_productivity='Industry Productivity')
COLORS = {m: f'C{i}' for i, m in enumerate((*BOUNDS, 'Core Bound', 'Memory Bound',
                                        'Fetch Latency Bound', 'Fetch Bandwidth Bound', 'IPC'))}


def segments(runs):
    """Append real sample indices with a gap; never connect independent runs."""
    offset = 0
    result = []
    for run in sorted(runs, key=lambda r: r['repeat']):
        indices = [p['sample_index'] for p in run['points']]
        if indices != list(range(1, len(indices) + 1)):
            raise ValueError('noncontiguous plotted samples')
        xs = [offset + i for i in indices]
        result.append((run, xs))
        offset = xs[-1] + 2
    return result


def export(series, output):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.figure import Figure
    from matplotlib import rc_context
    output = Path(output)
    datasets = {ds: [r for r in series['runs'] if r['dataset_id'] == ds] for ds in LABELS}
    for ds, runs in datasets.items():
        if sorted(r['repeat'] for r in runs) != [1, 2, 3, 4, 5]:
            raise ValueError('interval plots require all five independent runs: ' + ds)
    figures = []

    def draw(ax, runs, metrics):
        for index, (run, xs) in enumerate(segments(runs)):
            for metric in metrics:
                ys = [p['metrics'][metric] for p in run['points']]
                ax.plot(xs, ys, color=COLORS[metric], linewidth=1.0, marker='.', markersize=2.0,
                        label=metric if index == 0 else None)
            ax.axvspan(xs[0] - .4, xs[-1] + .4, color='black', alpha=.025 if index % 2 == 0 else 0)
            ax.text((xs[0] + xs[-1]) / 2, 1.01, 'Run ' + str(run['repeat']),
                    transform=ax.get_xaxis_transform(), ha='center', fontsize=8)
            if index:
                ax.axvline(xs[0] - 1.5, color='gray', linestyle=':', linewidth=.7)
        ax.set_ylabel('IPC' if metrics == ('IPC',) else 'Metric (%)')
        if metrics != ('IPC',):
            ax.set_ylim(0, 100)
        ax.grid(axis='y', alpha=.22)
        ax.legend(loc='upper left', bbox_to_anchor=(1.005, 1), fontsize=7, frameon=False)
        ax.set_xlabel('Sample index (five runs concatenated; nominal interval 1 s)', fontsize=9)

    def save(fig, name, title, detail=False):
        for suffix in ('svg', 'png'):
            path = output / (name + '.' + suffix)
            fig.savefig(path, dpi=170, metadata={'Date': None} if suffix == 'svg' else {})
            if suffix == 'svg':
                figures.append(dict(filename=path.name, path=str(path.relative_to(ROOT)), sha256=sha(path),
                    title=title, detail=detail,
                    caption='每个点为原始 DevKit 编号报告，每条线为一个指标；横轴为五轮串联的采样点序号，轮间留空且不连线。名义间隔 1 秒，保留启动和停止包络，不平滑、不插值。'))

    with rc_context({'svg.hashsalt': 'office-devkit-intervals-v1', 'font.family': 'DejaVu Sans'}):
        for group, names in GROUPS:
            fig = Figure(figsize=(12, 2.8 * len(names)))
            axes = fig.subplots(len(names), 1, squeeze=False)
            fig.subplots_adjust(left=.07, right=.84, top=.94, bottom=.06, hspace=.65)
            for ds, row in zip(names, axes):
                ax = row[0]
                draw(ax, datasets[ds], BOUNDS)
                ax.set_title(LABELS[ds], loc='left', pad=18, fontsize=11)
            save(fig, group + '-bound-five-repeats', group.upper() + ' 五轮逐采样点顶层 Bound')
        panels = (BOUNDS, ('Core Bound', 'Memory Bound'),
                  ('Fetch Latency Bound', 'Fetch Bandwidth Bound'), ('IPC',))
        for ds, runs in datasets.items():
            fig = Figure(figsize=(12, 11.8))
            axes = fig.subplots(4, 1)
            fig.subplots_adjust(left=.07, right=.84, top=.94, bottom=.06, hspace=.65)
            for ax, metrics in zip(axes, panels):
                draw(ax, runs, metrics)
            fig.suptitle(LABELS[ds] + ': all nine saved PMU metrics, five independent runs', fontsize=12)
            save(fig, ds + '-interval-metrics', LABELS[ds] + ' 五轮全指标采样曲线', detail=True)
    return figures, matplotlib.__version__
