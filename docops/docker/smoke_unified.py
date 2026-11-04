"""Tiny synthetic format/CLI compatibility checks; never runs a DocOps task."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from core_identity import identity


def run(argv, **kwargs):
    return subprocess.run(argv, check=True, capture_output=True, text=True,
                          timeout=90, **kwargs)


def main():
    result = {'schema': 'docops-unified-smoke-v1', 'status': 'failed',
              'real_workload_executed': False, 'profiling_started': False}
    try:
        baseline = json.loads(Path('/opt/docops/core-baseline.json').read_text())
        actual = identity()
        assert actual == baseline, 'core ELF or original seven-case entry changed'
        for name, item in actual.items():
            if 'libpython' in name or name.endswith(('libsclo.so', 'libswlo.so', 'libsdlo.so')):
                assert item['symtab'] and item['debug_info'], f'missing full symbols: {name}'
        result['core_identity'] = actual
        code = 'import sys,json,openpyxl,pypdf; print(json.dumps([sys.prefix,sys.version.split()[0],openpyxl.__version__,pypdf.__version__]))'
        child = [json.loads(run(argv).stdout) for argv in (
            ['python3', '-c', code], ['bash', '-lc', 'python3 -c ' + __import__('shlex').quote(code)],
            ['bash', '-lc', 'python -c ' + __import__('shlex').quote(code)])]
        assert all(row == ['/opt/docops/venv', '3.12.3', '3.1.5', '6.10.0'] for row in child), child
        result['child_interpreters'] = child
        from docx import Document
        from pptx import Presentation
        from pptx.util import Inches
        from openpyxl import Workbook, load_workbook
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas
        from PIL import Image
        from fontTools.ttLib import TTFont
        from fontTools.fontBuilder import FontBuilder
        from lxml import etree
        assert etree.fromstring(b'<a/>').tag == 'a'
        with tempfile.TemporaryDirectory(prefix='docops-unified-fixture-') as temp:
            root = Path(temp)
            doc = Document(); doc.add_heading('Runtime fixture', 0); doc.add_paragraph('Compatibility test')
            doc.save(root/'fixture.docx')
            assert Document(root/'fixture.docx').paragraphs[1].text == 'Compatibility test'
            prs = Presentation(); slide = prs.slides.add_slide(prs.slide_layouts[6])
            slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1)).text = 'Runtime fixture'
            prs.save(root/'fixture.pptx')
            assert len(Presentation(root/'fixture.pptx').slides) == 1
            book = Workbook(); book.active.append([3, 4, '=A1+B1']); book.save(root/'fixture.xlsx')
            c = canvas.Canvas(str(root/'fixture.pdf')); c.drawString(72, 720, 'Runtime fixture'); c.save()
            writer = PdfWriter(); writer.append(PdfReader(root/'fixture.pdf')); writer.write(root/'copied.pdf')
            assert len(PdfReader(root/'copied.pdf').pages) == 1
            Image.new('RGB', (32, 32), 'white').save(root/'one.png')
            run(['montage', str(root/'one.png'), str(root/'one.png'), '-tile', '2x1', '-geometry', '+0+0', str(root/'contact.png')])
            assert Image.open(root/'contact.png').size == (64, 32)
            run(['unzip', '-t', str(root/'fixture.docx')])
            diagnostic = root/'diagnostic.txt'; diagnostic.write_text('Draft: fixture\n')
            assert run(['rg', '-n', 'Draft:|Obsolete|Superseded', str(diagnostic)]).stdout.strip() == '1:Draft: fixture'
            ldd = run(['ldd', '/opt/docops/venv/bin/rg'])
            assert 'not found' not in ldd.stdout
            result['rg_runtime_libraries'] = ldd.stdout.splitlines()
            conversions = []
            for suffix in ('docx', 'pptx'):
                out = root/suffix; out.mkdir()
                cp = run(['soffice', '-env:UserInstallation='+ (root/('profile-'+suffix)).as_uri(),
                          '--headless', '--convert-to', 'pdf', '--outdir', str(out), str(root/('fixture.'+suffix))])
                assert len(PdfReader(out/'fixture.pdf').pages) == 1
                conversions.append({'format': suffix, 'stdout': cp.stdout.strip()})
            # Real rounds clear their user profile before executing. A fresh HOME
            # tests that setup path rather than relying on inherited macros.
            home = root/'fresh-home'; home.mkdir()
            cp = run([sys.executable, '/root/.codex/skills/xlsx/scripts/recalc.py', str(root/'fixture.xlsx'), '30'],
                     env=dict(os.environ, HOME=str(home)))
            recalc = json.loads(cp.stdout)
            assert recalc.get('status') == 'success', recalc
            cached = load_workbook(root/'fixture.xlsx', data_only=True)
            assert cached.active['C1'].value == 7, 'LibreOffice cache mismatch'
            cached.close()
            run(['pdftoppm', '-f', '1', '-l', '1', '-scale-to', '64', '-png', str(root/'fixture.pdf'), str(root/'page')])
            result.update(formats=['docx', 'pptx', 'xlsx', 'pdf'], conversions=conversions,
                          frozen_skill_recalc=recalc, fresh_profile_recalc=True,
                          synthetic_checks='passed')
        import lxml.etree
        result['additional_native_modules'] = {}
        for module in (lxml.etree,):
            path = Path(module.__file__)
            sections = run(['readelf', '-SW', str(path)]).stdout
            result['additional_native_modules'][str(path)] = {
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'symtab': '.symtab' in sections, 'debug_info': '.debug_info' in sections}
        result['status'] = 'passed'
    except Exception as exc:
        import traceback
        result.update(error=f'{type(exc).__name__}: {exc}', traceback=traceback.format_exc())
    Path(os.environ.get('DOC_UNIFIED_SMOKE_OUT', '/results/unified-smoke.json')).write_text(
        json.dumps(result, indent=2)+'\n')
    print(json.dumps({'status': result['status'], 'error': result.get('error')}))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
