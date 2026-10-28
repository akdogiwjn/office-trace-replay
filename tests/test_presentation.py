import importlib.util
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('office_html_presentation', ROOT / 'scripts/build_presentation.py')
presentation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(presentation)


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.slides = []
        self.external = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'section' and 'slide' in attrs.get('class', '').split():
            self.slides.append(attrs)
        if tag in ('script', 'img', 'link') and (attrs.get('src') or attrs.get('href')):
            self.external.append(attrs)


class PresentationTests(unittest.TestCase):
    def copy_sources(self, root):
        _, _, _, _, sources = presentation.load_inputs(ROOT)
        for path in sources:
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / path, target)
        (root / 'docs/evidence').mkdir(exist_ok=True)

    def test_generated_deck_is_self_contained_and_source_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.copy_sources(root)
            with redirect_stdout(io.StringIO()):
                path = presentation.build(root)
            html = path.read_text()
            parsed = Elements()
            parsed.feed(html)
            manifest = json.loads((root / 'docs/evidence/presentation.json').read_text())
            self.assertEqual(len(parsed.slides), manifest['slide_count'])
            self.assertEqual(parsed.slides[0]['data-title'], presentation.TITLE)
            self.assertFalse(parsed.external)
            self.assertFalse('hidden' in parsed.slides[0])
            self.assertTrue(all('hidden' in s for s in parsed.slides[1:]))
            self.assertEqual(manifest['output']['sha256'], presentation.sha(path))
            self.assertIn('requestFullscreen', html)
            self.assertIn('@media print', html)

    def test_modified_source_document_is_rejected_before_publishing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.copy_sources(root)
            p = root / 'docs/representativeness-assessment.md'
            p.write_text(p.read_text() + '\nchanged\n')
            with self.assertRaisesRegex(ValueError, 'report document changed'):
                presentation.build(root)
            self.assertFalse((root / 'docs/representativeness-assessment.html').exists())

    def test_curves_keep_every_point_and_separate_independent_runs(self):
        _, _, _, series, _ = presentation.load_inputs(ROOT)
        for ds in ('opm', 'irs_w4', 'sba1919', *presentation.XLSX):
            svg = presentation.interval_svg(series, ds)
            lines = re.findall(r'<polyline\b[^>]*>', svg)
            self.assertEqual(len(lines), 20)
            expected = {r['repeat']: len(r['points']) for r in series['runs'] if r['dataset_id'] == ds}
            for line in lines:
                repeat = int(re.search(r'data-repeat="(\d+)"', line)[1])
                point_count = int(re.search(r'data-point-count="(\d+)"', line)[1])
                coordinates = re.search(r' points="([^"]+)"', line)[1].split()
                self.assertEqual(len(coordinates), expected[repeat])
                self.assertEqual(point_count, expected[repeat])
            self.assertNotIn('smooth', svg)


if __name__ == '__main__':
    unittest.main()
