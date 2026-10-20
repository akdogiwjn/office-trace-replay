import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'script_io', BASE / 'scripts/analyze_script_io_comparison.py')
module = importlib.util.module_from_spec(spec)
with patch.object(sys, 'path', [str(BASE / 'scripts'), *sys.path]):
    spec.loader.exec_module(module)


class ScriptIOTests(unittest.TestCase):
    def test_inclusive_loading_and_save_not_only_leaf(self):
        self.assertEqual(module.category([
            'load_workbook (openpyxl/reader/excel.py:348)',
            'feed (xml/etree/ElementTree.py:1284)']), 'load_call')
        self.assertEqual(module.category([
            'save (openpyxl/workbook/workbook.py:386)',
            'write (zipfile/__init__.py:1214)']), 'save')
        self.assertEqual(module.category(['write (zipfile/__init__.py:1214)']), 'other')

    def test_lazy_scan_counted_outside_load_and_not_double_counted_inside(self):
        lazy = '_cells_by_row (openpyxl/worksheet/_read_only.py:85)'
        self.assertEqual(module.category([lazy, 'parse_cell (_reader.py:208)']), 'lazy_scan')
        self.assertEqual(module.category(['load_workbook (excel.py:348)', lazy]), 'load_call')
        self.assertEqual(module.category(['<module> (_read_only.py:6)']), 'other')

    def test_zip_import_basename_and_business_comparison(self):
        self.assertEqual(module.category(['load_workbook (excel.py:348)']), 'load_call')
        self.assertEqual(module.category(['_cells_by_row (_read_only.py:85)']), 'lazy_scan')
        self.assertEqual(module.category(['original_content (office_trace_bench/spreadsheet.py:229)']), 'other')
        self.assertEqual(module.category(['load_workbook (different/excel.py:348)']), 'other')
        with self.assertRaises(ValueError):
            module.category(['load_workbook (excel.py:348)', 'save (workbook.py:386)'])

    def test_unresolved_samples_retained_in_raw_denominator(self):
        raw = ('process 1:"python3 recalc.py file.xlsx";'
               'load_workbook (openpyxl/reader/excel.py:348) 2\n'
               'process 1:"python3 recalc.py file.xlsx" 3\n'
               'process 1:"python3 recalc.py file.xlsx";'
               '_cells_by_row (_read_only.py:85);parse (_reader.py:156) 5\n')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'capture.raw'
            path.write_text(raw)
            result = module.analyze_raw(path, 'xlsx')
        self.assertEqual(result['total_samples'], 10)
        self.assertEqual(result['operation_samples']['no_python_frames'], 3)
        self.assertEqual(result['load_including_lazy_percent'], 70)

    def test_new_dataset_helpers_are_enhancement_roles_only_when_executed(self):
        for script in ('hr_metro_build.py', '.hr_metro_build.runtime.py',
                       'retail_online_build.py', '.retail_online_build.runtime.py'):
            with self.subTest(script=script):
                self.assertEqual(module.role_for(f'python3 /workspace/{script}', 'xlsx'),
                                 'xlsx-enhance')
        command = ('python3 /opt/office-trace-replay/replay/entry.py '
                   '--dataset retail_online /workspace/retail_online_build.py')
        self.assertEqual(module.role_for(command, 'xlsx'), 'runner')

    def test_svg_integer_intervals_preserve_unknown_and_deduplicate(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg"
            xmlns:fg="http://github.com/jonhoo/inferno">
          <svg id="frames" total_samples="10">
            <g><title>all (10 samples, 100.00%)</title>
              <rect fg:x="0" fg:w="10" y="52"/></g>
            <g><title>process 1:"python3 recalc.py f.xlsx" (10 samples, 100.00%)</title>
              <rect fg:x="0" fg:w="10" y="68"/></g>
            <g><title>load_workbook (openpyxl/reader/excel.py:348) (4 samples, 40.00%)</title>
              <rect fg:x="0" fg:w="4" y="84"/></g>
            <g><title>_cells_by_row (openpyxl/worksheet/_read_only.py:85) (2 samples, 20.00%)</title>
              <rect fg:x="1" fg:w="2" y="100"/></g>
            <g><title>_cells_by_row (openpyxl/worksheet/_read_only.py:85) (3 samples, 30.00%)</title>
              <rect fg:x="4" fg:w="3" y="84"/></g>
          </svg></svg>'''
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'capture.svg'
            path.write_text(svg)
            result = module.analyze_svg(path, 'xlsx')
        self.assertEqual(result['operation_samples'],
                         {'load_call': 4, 'lazy_scan': 3, 'no_python_frames': 3})
        self.assertEqual(result['load_and_save_percent'], 70)
        self.assertEqual(result['role_samples'], {'xlsx-recalc': 10})


if __name__ == '__main__':
    unittest.main()
