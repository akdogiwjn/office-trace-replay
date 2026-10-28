#!/usr/bin/env python3
"""Build a self-contained HTML briefing from the current qualified report data."""
import argparse
import hashlib
from html import escape, unescape
import math
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CONFIG = 'analysis/hotspots/comparison-inputs-pdf5-20261027.json'
TITLE = '文档解析类 Agent 代表性评估报告'
LABELS = dict(opm='OPM', **{'opm-n10': 'OPM'}, irs_w4='IRS W-4', sba1919='SBA 1919',
              tlc='TLC', hr_metro='HR Metro', egrid='eGRID', industry_productivity='Industry Productivity')
PDF = ('opm-n10', 'irs_w4', 'sba1919')
XLSX = ('tlc', 'hr_metro', 'egrid', 'industry_productivity')
BOUNDS = ('Bad Speculation', 'Frontend Bound', 'Backend Bound', 'Retiring')
COLORS = ('#346a9f', '#cf792d', '#347d55', '#b3464c')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text(value):
    return escape(str(value), quote=True)


def code(value):
    return '<code>' + text(value) + '</code>'


def bullets(items):
    return '<ul>' + ''.join('<li>' + v + '</li>' for v in items) + '</ul>'


def resolved_functions(profile, limit):
    return [r for r in profile['functions'] if r['library'] != 'unknown'
            and r['function'] not in ('[unknown]', '[no-frame]')
            and not re.fullmatch(r'0x[0-9a-fA-F]+|[0-9a-fA-F]{12,}', r['function'])][:limit]


def interval_svg(series, dataset):
    """Draw the original points; separate runs without interpolation or smoothing."""
    runs = sorted((r for r in series['runs'] if r['dataset_id'] == dataset), key=lambda r: r['repeat'])
    if [r['repeat'] for r in runs] != [1, 2, 3, 4, 5]:
        raise ValueError('five runs required for curve: ' + dataset)
    parts = []
    offset = 0
    for run in runs:
        points = run['points']
        if [p['sample_index'] for p in points] != list(range(1, len(points) + 1)):
            raise ValueError('noncontiguous curve source')
        xs = [offset + p['sample_index'] for p in points]
        parts.append((run, xs))
        offset = xs[-1] + 2
    width, height = 1120, 398
    left, right, top, bottom = 60, 1098, 62, 338
    x = lambda v: left + (v - 1) / max(1, offset - 3) * (right - left)
    y = lambda v: bottom - v / 100 * (bottom - top)
    output = [f'<svg class="curve" viewBox="0 0 {width} {height}" role="img" aria-label="{text(LABELS[dataset])} 五轮真实采样点曲线">',
              '<rect width="1120" height="398" fill="white"/>']
    for value in range(0, 101, 20):
        yy = y(value)
        output += [f'<line x1="{left}" y1="{yy:.2f}" x2="{right}" y2="{yy:.2f}" stroke="#dce2e8"/>',
                   f'<text x="{left-12}" y="{yy+5:.2f}" text-anchor="end" font-size="16">{value}</text>']
    for index, metric in enumerate(BOUNDS):
        xx = 70 + index * 264
        output += [f'<line x1="{xx}" y1="16" x2="{xx+24}" y2="16" stroke="{COLORS[index]}" stroke-width="3"/>',
                   f'<text x="{xx+32}" y="21" font-size="17">{text(metric)}</text>']
    for index, (run, xs) in enumerate(parts):
        start, end = x(xs[0]), x(xs[-1])
        output.append(f'<text x="{(start+end)/2:.2f}" y="49" text-anchor="middle" font-size="16">第 {run["repeat"]} 轮</text>')
        if index:
            bx = x(xs[0] - 1.5)
            output.append(f'<line x1="{bx:.2f}" y1="{top}" x2="{bx:.2f}" y2="{bottom}" stroke="#8492a3" stroke-dasharray="3 4"/>')
        for m, metric in enumerate(BOUNDS):
            pairs = [(x(xx), y(point['metrics'][metric])) for xx, point in zip(xs, run['points'])]
            output.append('<polyline class="series" data-repeat="' + str(run['repeat']) + '" data-metric="' + text(metric) +
                          '" data-point-count="' + str(len(pairs)) + '" fill="none" stroke="' + COLORS[m] +
                          '" stroke-width="1.5" points="' + ' '.join(f'{a:.2f},{b:.2f}' for a, b in pairs) + '"/>')
        output += [f'<text x="{start:.2f}" y="360" text-anchor="middle" font-size="14">{xs[0]}</text>',
                   f'<text x="{end:.2f}" y="360" text-anchor="middle" font-size="14">{xs[-1]}</text>']
    output += ['<text x="32" y="53" font-size="16">%</text>',
               '<text x="580" y="388" text-anchor="middle" font-size="17">采样点序号（五轮依次展示；名义输出间隔 1 秒）</text>', '</svg>']
    return ''.join(output)


def load_inputs(root):
    sources = {}
    def read(path, expected=None):
        path = Path(path)
        digest = sha(root / path)
        if expected is not None and digest != expected:
            raise ValueError('presentation source hash mismatch: ' + str(path))
        sources[str(path)] = digest
        return json.loads((root / path).read_text())
    config = read(CONFIG)
    output = Path(config['output'])
    build = read(output / 'build.json')
    if build['config_sha256'] != sha(root / CONFIG):
        raise ValueError('report build belongs to a different config')
    comparison = read(output / 'comparison.json', build['output_sha256']['comparison.json'])
    for path, expected in build['document_sha256'].items():
        if sha(root / path) != expected:
            raise ValueError('report document changed: ' + path)
        sources[path] = expected
    joint = comparison['joint_comparison']
    binding = config['joint_comparison']
    if read(binding['path'], binding['sha256']) != joint:
        raise ValueError('embedded and qualified joint results differ')
    series = read(joint['time_series']['path'], joint['time_series']['sha256'])
    if len(series['runs']) != 35 or set(joint['statistics']) != set(LABELS) - {'opm-n10'}:
        raise ValueError('expected current seven-dataset five-run results')
    if {p['image_id'] for p in comparison['profiles'].values()} != {joint['image_id']}:
        raise ValueError('mixed image evidence')
    pdf_top5 = [{(r['library'], r['function']) for r in resolved_functions(comparison['profiles'][ds], 5)} for ds in PDF]
    if any(len(s) != 5 for s in pdf_top5) or any(s != pdf_top5[0] for s in pdf_top5[1:]):
        raise ValueError('PDF Top-5 headline must agree with current qualified data')
    return config, comparison, joint, series, sources


def inline_markdown(value):
    """Render the report's small Markdown vocabulary without external libraries."""
    value = unescape(value)
    token = re.compile(r'`[^`]+`|\[[^\]]+\]\([^)]+\)|\*\*.+?\*\*')
    parts = []
    offset = 0
    for match in token.finditer(value):
        parts.append(text(value[offset:match.start()]))
        item = match[0]
        if item.startswith('`'):
            parts.append(code(item[1:-1]))
        elif item.startswith('**'):
            parts.append('<strong>' + inline_markdown(item[2:-2]) + '</strong>')
        else:
            link = re.fullmatch(r'\[([^\]]+)\]\(([^)]+)\)', item)
            label, href = link.groups()
            if href == 'experimental-results.md':
                href = 'https://github.com/akdogiwjn/office-trace-replay/blob/main/docs/experimental-results.md'
            parts.append('<a href="' + text(href) + '" target="_blank" rel="noopener">' + text(label) + '</a>')
        offset = match.end()
    parts.append(text(value[offset:]))
    return ''.join(parts)


def report_blocks(markdown):
    lines = markdown.splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith('```'):
            i += 1
            content = []
            while i < len(lines) and not lines[i].strip().startswith('```'):
                content.append(lines[i])
                i += 1
            if i == len(lines):
                raise ValueError('unclosed Markdown code block')
            blocks.append(dict(kind='code', value='\n'.join(content)))
            i += 1
        elif line.startswith('# '):
            if line[2:] != TITLE:
                raise ValueError('unexpected source report title')
            i += 1
        elif line.startswith('## '):
            blocks.append(dict(kind='section', value=line[3:]))
            i += 1
        elif line.startswith('### '):
            blocks.append(dict(kind='heading', value=line[4:]))
            i += 1
        elif line.startswith('|'):
            data = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                data.append([cell.strip() for cell in lines[i].strip().strip('|').split('|')])
                i += 1
            if len(data) < 2 or not all(re.fullmatch(r'[-: ]+', cell) for cell in data[1]):
                raise ValueError('unsupported Markdown table')
            if any(len(row) != len(data[0]) for row in data[2:]):
                raise ValueError('table width mismatch')
            blocks.append(dict(kind='table', headers=data[0], rows=data[2:]))
        elif re.fullmatch(r'!\[[^\]]*\]\([^)]+\)', line):
            match = re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)', line)
            blocks.append(dict(kind='image', value=match[1], path=match[2]))
            i += 1
        elif line.startswith('- '):
            items = []
            while i < len(lines) and lines[i].strip().startswith('- '):
                items.append(lines[i].strip()[2:])
                i += 1
            blocks.append(dict(kind='list', items=items))
        else:
            content = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith(('#', '|', '```', '![', '- ')):
                content.append(lines[i].strip())
                i += 1
            blocks.append(dict(kind='paragraph', value=' '.join(content)))
    return blocks


def plain_text(value):
    value = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', value)
    value = re.sub(r'[`*]', '', value)
    return unescape(value)


def line_count(value, width, font=20):
    # Conservative estimate, verified after generation in the real browser.
    units = sum(1 if ord(c) > 255 else .57 for c in plain_text(value))
    return max(1, math.ceil(units * font / max(1, width)))


def table_widths(headers):
    count = len(headers)
    first = headers[0]
    if count == 2:
        return [.18, .82]
    if '基准热点' in first:
        return [.47] + [.53 / (count - 1)] * (count - 1)
    if '职责' in first:
        return [.40] + [.60 / (count - 1)] * (count - 1)
    if 'XLSX 数据集' in first:
        return [.15, .18, .26, .41]
    if 'PDF 数据集' in first:
        return [.20, .23, .19, .38]
    if '新增用例' in first:
        return [.16, .50, .34]
    if count == 3:
        if '证据' in first:
            return [.15, .55, .30]
        if '阶段' in first:
            return [.15, .425, .425]
        return [.21, .43, .36]
    return [.30] + [.70 / (count - 1)] * (count - 1)


def report_table(headers, rows, caption=''):
    widths = table_widths(headers)
    colgroup = '<colgroup>' + ''.join(f'<col style="width:{100*w:.3f}%">' for w in widths) + '</colgroup>'
    html = '<table>' + colgroup + '<thead><tr>' + ''.join('<th>' + inline_markdown(c) + '</th>' for c in headers) + '</tr></thead><tbody>'
    html += ''.join('<tr>' + ''.join('<td>' + inline_markdown(c) + '</td>' for c in row) + '</tr>' for row in rows)
    return html + '</tbody></table>'


def table_row_height(headers, row):
    widths = table_widths(headers)
    # 19px cells, 26px line height, 12px total vertical padding.
    return max(line_count(cell, 1188 * width - 20, 19) for cell, width in zip(row, widths)) * 26 + 12


def make_slides(config, comparison, joint, series, markdown):
    """Paginate the complete assessment rather than selecting short talking points."""
    blocks = report_blocks(markdown)
    slides = []
    body = []
    used = 0
    section = ''
    current_title = ''
    budget = 510
    part = 1

    def flush():
        nonlocal body, used, part
        if not body:
            return
        title = TITLE if not slides else current_title + ('（续）' if part > 1 else '')
        slides.append(dict(title=title, body=''.join(body), section=section,
                           subtitle='', cls='report-page'))
        body = []
        used = 0
        part += 1

    def put(html, height):
        nonlocal used
        if height > budget:
            raise ValueError('source block exceeds page budget; split at a meaningful boundary')
        if used and used + height + 9 > budget:
            flush()
        body.append(html)
        used += height + (9 if used else 0)

    for block_index, block in enumerate(blocks):
        kind = block['kind']
        if kind == 'section':
            flush()
            section = current_title = block['value']
            part = 1
        elif kind == 'heading':
            # Keep a heading with subsequent content; do not leave it at the page bottom.
            next_height = 100
            if block_index + 1 < len(blocks):
                following = blocks[block_index + 1]
                if following['kind'] == 'table' and following['rows']:
                    full_table = table_row_height(following['headers'], following['headers']) + sum(table_row_height(following['headers'], r) for r in following['rows'])
                    next_height = full_table if full_table + 49 <= budget else table_row_height(following['headers'], following['headers']) + table_row_height(following['headers'], following['rows'][0])
                elif following['kind'] == 'paragraph':
                    next_height = line_count(following['value'], 1188) * 29
                elif following['kind'] == 'code':
                    next_height = (len(following['value'].splitlines()) + 1) * 23
            if used and used + 49 + next_height > budget:
                flush()
            current_title = section
            put('<h2>' + text(block['value']) + '</h2>', 40)
        elif kind == 'paragraph':
            put('<p>' + inline_markdown(block['value']) + '</p>', line_count(block['value'], 1188) * 29)
        elif kind == 'code':
            put('<pre><code>' + text(block['value']) + '</code></pre>', (len(block['value'].splitlines()) + 1) * 23)
        elif kind == 'list':
            put(bullets([inline_markdown(item) for item in block['items']]),
                sum(line_count(item, 1150) * 29 + 6 for item in block['items']))
        elif kind == 'table':
            headers = block['headers']
            header_height = table_row_height(headers, headers)
            full_table = header_height + sum(table_row_height(headers, row) for row in block['rows'])
            if full_table <= budget:
                put(report_table(headers, block['rows']), full_table)
                continue
            rows = []
            cost = header_height
            for row in block['rows']:
                height = table_row_height(headers, row)
                if not rows and used and used + cost + height + 9 > budget:
                    flush()
                if rows and used + cost + height + 9 > budget:
                    put(report_table(headers, rows), cost)
                    flush()
                    rows, cost = [], header_height
                if cost + height > budget:
                    raise ValueError('individual table row cannot fit')
                rows.append(row)
                cost += height
            if rows:
                put(report_table(headers, rows), cost)
        elif kind == 'image':
            flush()
            if 'pdf-bound-five-repeats' in block['path']:
                datasets = ('opm', 'irs_w4', 'sba1919')
            elif 'xlsx-bound-five-repeats' in block['path']:
                datasets = XLSX
            else:
                raise ValueError('unbound chart source: ' + block['path'])
            for ds in datasets:
                runs = sorted((r for r in series['runs'] if r['dataset_id'] == ds), key=lambda r:r['repeat'])
                counts = '／'.join(str(len(r['points'])) for r in runs)
                slides.append(dict(title=LABELS[ds] + '：五轮 Topdown 过程曲线',
                    section=section, subtitle='', cls='report-page chart-slide',
                    body=interval_svg(series, ds) + '<p>横轴为五轮依次展示的真实指标输出点；各轮之间断开。每条线对应一个顶层 Bound，未平滑、未插值。</p>' +
                    '<p class="small">每轮点数：' + text(counts) + '；名义输出间隔 1 秒。保留启动／停止包络。相似度采用各轮 ALL 汇总的五轮均值。</p>'))
            current_title = '5.4 逐采样点过程与五轮稳定性'
            part = 1
    flush()
    return slides

CSS = r'''
:root{font-family:"Noto Sans CJK SC","Microsoft YaHei","PingFang SC",Arial,sans-serif;color:#000;background:#fff;font-synthesis:none}
*{box-sizing:border-box}body{margin:0;background:#fff;color:#000}button,select{font:inherit;color:#000}a{color:#000;text-decoration:underline;text-underline-offset:2px}strong,b{color:#000}
.viewport{height:calc(100vh - 44px);width:100vw;display:flex;align-items:center;justify-content:center;overflow:hidden}
.deck{position:relative;width:1280px;height:720px;flex:none;transform-origin:center center}
.slide{position:absolute;inset:0;background:#fff;color:#000;padding:26px 46px 48px;display:flex;flex-direction:column;overflow:hidden}
.slide[hidden]{display:none}.eyebrow{font-size:15px;line-height:22px;margin:0 0 8px;color:#000}h1{font-size:29px;line-height:1.3;margin:0 0 15px;font-weight:700}h2{font-size:22px;line-height:29px;margin:0 0 5px;font-weight:700}.subtitle{font-size:20px;color:#000;margin:0 0 12px}
.content{flex:1;min-height:0;display:flex;flex-direction:column;gap:9px;font-size:20px;line-height:1.45}.content>p{margin:0}.content>*{flex-shrink:0}p,li{color:#000}ul{margin:0;padding-left:1.25em}li{padding:3px 0}
table{border-collapse:collapse;width:100%;font-size:19px;line-height:26px;table-layout:fixed;color:#000}th{text-align:left;font-weight:700;background:#fff}th,td{padding:6px 9px;border:1px solid #aaa;vertical-align:top;overflow-wrap:anywhere}td:not(:first-child){font-variant-numeric:tabular-nums}
code{font-family:"DejaVu Sans Mono",Consolas,monospace;font-size:16px;color:#000;overflow-wrap:anywhere}pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font-size:17px;line-height:23px}pre code{font-size:17px;line-height:23px}.small{font-size:17px;line-height:1.45;color:#000}
.footer{position:absolute;left:46px;right:46px;bottom:15px;display:flex;justify-content:space-between;color:#000;font-size:13px;line-height:20px}.footer .number{font-variant-numeric:tabular-nums}
.curve{width:100%;height:390px;display:block;flex:none;font-family:Arial,"Noto Sans CJK SC",sans-serif}.curve text{fill:#000}.chart-slide h1{font-size:29px}.chart-slide .content{gap:10px}.chart-slide p{font-size:19px;line-height:1.45}
.toolbar{height:44px;display:flex;align-items:center;justify-content:center;gap:8px;padding:5px 12px;background:#fff;border-top:1px solid #aaa;font-size:14px;color:#000}.toolbar button,.toolbar select{border:1px solid #999;background:#fff;color:#000;border-radius:0;padding:4px 9px;cursor:pointer}.toolbar button:disabled{color:#000;cursor:default}.toolbar select{max-width:430px}.toolbar .hint{color:#000;margin-left:10px}.toolbar button:focus-visible,.toolbar select:focus-visible{outline:2px solid #000;outline-offset:2px}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
@media(max-width:700px){.toolbar .hint{display:none}.toolbar select{max-width:36vw}.toolbar{gap:4px}.toolbar button{padding:4px 6px}}
@page{size:338.6667mm 190.5mm;margin:0}
@media print{html,body{background:#fff;width:1280px!important}.toolbar{display:none!important}.viewport{display:block;width:1280px;height:auto;overflow:visible}.deck{position:static;transform:none!important;width:1280px;height:auto}.slide,.slide[hidden]{display:flex!important;position:relative;inset:auto;width:1280px;height:720px;break-after:page;page-break-after:always;print-color-adjust:exact;-webkit-print-color-adjust:exact}.slide:last-child{break-after:auto;page-break-after:auto}}
'''

JS = r'''
(() => {
  const slides = [...document.querySelectorAll('.slide')];
  const deck = document.getElementById('deck');
  const picker = document.getElementById('slide-picker');
  const previous = document.getElementById('previous');
  const next = document.getElementById('next');
  const announcement = document.getElementById('announcement');
  let index = 0;
  const hashIndex = () => {
    const match = location.hash.match(/^#slide=(\d+)$/);
    return match ? Number(match[1]) - 1 : 0;
  };
  function show(requested, updateHash = true) {
    index = Math.max(0, Math.min(slides.length - 1, requested));
    slides.forEach((slide, i) => {
      slide.hidden = i !== index;
      slide.setAttribute('aria-current', String(i === index));
    });
    picker.value = String(index);
    previous.disabled = index === 0;
    next.disabled = index === slides.length - 1;
    announcement.textContent = `第 ${index + 1} 页，共 ${slides.length} 页：${slides[index].dataset.title}`;
    if (updateHash) {
      try { history.replaceState(null, '', '#slide=' + (index + 1)); }
      catch (_) { location.hash = 'slide=' + (index + 1); }
    }
  }
  function resize() {
    const view = document.querySelector('.viewport');
    const scale = Math.max(.1, Math.min(view.clientWidth / 1280, view.clientHeight / 720));
    deck.style.transform = `scale(${scale})`;
  }
  async function fullscreen() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (document.documentElement.requestFullscreen) await document.documentElement.requestFullscreen();
      else announcement.textContent = '浏览器不支持全屏，可使用浏览器自带全屏功能。';
    } catch (_) { announcement.textContent = '请使用浏览器的全屏功能。'; }
  }
  previous.addEventListener('click', () => show(index - 1));
  next.addEventListener('click', () => show(index + 1));
  picker.addEventListener('change', () => show(Number(picker.value)));
  document.getElementById('fullscreen').addEventListener('click', fullscreen);
  document.getElementById('print').addEventListener('click', () => window.print());
  window.addEventListener('hashchange', () => show(hashIndex(), false));
  window.addEventListener('resize', resize);
  document.addEventListener('fullscreenchange', resize);
  document.addEventListener('keydown', event => {
    if (event.altKey || event.ctrlKey || event.metaKey || /^(INPUT|SELECT|TEXTAREA)$/.test(event.target.tagName)) return;
    if (['ArrowRight', 'ArrowDown', 'PageDown', ' '].includes(event.key)) { event.preventDefault(); show(index + 1); }
    else if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(event.key)) { event.preventDefault(); show(index - 1); }
    else if (event.key === 'Home') { event.preventDefault(); show(0); }
    else if (event.key === 'End') { event.preventDefault(); show(slides.length - 1); }
    else if (event.key.toLowerCase() === 'f') { event.preventDefault(); fullscreen(); }
    else if (event.key.toLowerCase() === 'p') { event.preventDefault(); window.print(); }
  });
  show(hashIndex(), false);
  resize();
})();
'''


def render(slides, metadata):
    sections = []
    for i, slide in enumerate(slides, 1):
        sections.append(f'<section class="slide {text(slide["cls"])}" data-title="{text(slide["title"])}" id="slide-{i}"'+
            (' hidden' if i > 1 else '')+' aria-label="'+text(f'第 {i} 页：{slide["title"]}')+'">'+
            '<p class="eyebrow">'+text(slide['section'] if i == 1 else TITLE)+'</p><h1>'+text(slide['title'])+'</h1>'+
            ('<p class="subtitle">'+text(slide['subtitle'])+'</p>' if slide['subtitle'] else '')+
            '<div class="content">'+slide['body']+'</div><footer class="footer"><span>'+TITLE+
            '</span><span class="number">'+str(i)+' / '+str(len(slides))+'</span></footer></section>')
    options = ''.join(f'<option value="{i}">{i+1}. {text(s["title"])}</option>' for i,s in enumerate(slides))
    embedded = json.dumps(metadata, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    return ('<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+
        '<title>'+TITLE+'</title><style>'+CSS+'</style></head><body>'+\
        '<main class="viewport"><div class="deck" id="deck">'+''.join(sections)+'</div></main>'+\
        '<nav class="toolbar" aria-label="放映控制"><button id="previous" type="button">上一页</button>'+\
        '<label class="sr-only" for="slide-picker">选择页面</label><select id="slide-picker">'+options+'</select>'+\
        '<button id="next" type="button">下一页</button><button id="fullscreen" type="button">全屏 F</button>'+\
        '<button id="print" type="button">打印 / PDF</button><span class="hint">← / → 翻页 · Home / End 首尾页</span></nav>'+\
        '<p id="announcement" class="sr-only" aria-live="polite"></p>'+\
        '<script type="application/json" id="presentation-provenance">'+embedded+'</script><script>'+JS+'</script>'+\
        '<noscript><style>.slide[hidden]{display:flex}.slide{position:relative}.deck,.viewport{height:auto;display:block;overflow:visible}</style>'+\
        '<p>JavaScript 未启用，已改为连续阅读模式。</p></noscript></body></html>\n')


def build(root=ROOT):
    root = Path(root)
    config, comparison, joint, series, sources = load_inputs(root)
    markdown = (root / 'docs/representativeness-assessment.md').read_text()
    slides = make_slides(config, comparison, joint, series, markdown)
    metadata = dict(schema='representativeness-html-presentation-v2', title=TITLE, slide_count=len(slides),
        image_id=joint['image_id'], sources=sources,
        generator_sha256=sha(Path(__file__)), measurement_changes=False,
        layout='Complete assessment text, plain black-on-white pages; only metric curves use distinguishing colors.',
        source_report_blocks=len(report_blocks(markdown)),
        interval_policy='Original points retained; five separate polylines per metric; no smoothing or interpolation.')
    destination = root / 'docs/representativeness-assessment.html'
    destination.write_text(render(slides, metadata))
    manifest = root / 'docs/evidence/presentation.json'
    manifest.write_text(json.dumps(dict(**metadata, output=dict(path=str(destination.relative_to(root)), sha256=sha(destination)),
        slide_titles=[s['title'] for s in slides]), ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(output=str(destination), slides=len(slides), bytes=destination.stat().st_size,
                         sha256=sha(destination)), ensure_ascii=False))
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    build()


if __name__ == '__main__':
    main()
