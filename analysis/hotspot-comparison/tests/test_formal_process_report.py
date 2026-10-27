"""Report-only script grouping; no replay, Docker or workbook loading."""
import importlib.util
from pathlib import Path
import unittest


PATH = Path(__file__).resolve().parents[1] / 'scripts/finish_formal_process_cpu_report.py'
SPEC = importlib.util.spec_from_file_location('formal_script_report', PATH)
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)


class FormalProcessReportTests(unittest.TestCase):
    def test_actual_script_operand_splits_checks_and_keeps_other_cpu(self):
        row = {'denominator_seconds': 10, 'processes': [
            {'command': 'python3 /tools/inspect_xlsx_structure.py', 'role': 'inspect', 'cpu_seconds': 2},
            {'command': 'python3 /tools/inspect_xlsx_features.py', 'role': 'inspect', 'cpu_seconds': 3},
            {'command': 'python3 /repo/replay/entry.py inspect_xlsx_structure.py', 'role': 'runner', 'cpu_seconds': 5}]}
        output = REPORT.table([row], ['fixture'], REPORT.XLSX_LABELS)
        structure = next(line for line in output.splitlines() if line.startswith('| `inspect_xlsx_structure.py`'))
        features = next(line for line in output.splitlines() if line.startswith('| `inspect_xlsx_features.py`'))
        self.assertIn('20.00%', structure)
        self.assertIn('30.00%', features)
        self.assertIn('| 其他进程 | runner、原子执行器及辅助命令等 | 50.00% |', output)

    def test_runtime_helper_basename_is_reported_with_enhancement(self):
        row = {'denominator_seconds': 2, 'processes': [
            {'command': 'python3 /ws/.enhance_workbook.runtime.py', 'role': 'helper', 'cpu_seconds': 2}]}
        output = REPORT.table([row], ['fixture'], REPORT.XLSX_LABELS)
        line = next(line for line in output.splitlines() if line.startswith('| TLC：`enhance_workbook.py`'))
        self.assertIn('100.00%', line)

    def test_pdf_mapping_and_batch_driver_are_separate(self):
        row = {'denominator_seconds': 4, 'processes': [
            {'command': 'python3 helpers/build_field_values.py', 'role': 'pdf-mapping-driver', 'cpu_seconds': 1},
            {'command': 'python3 run_batch_fill_render.py', 'role': 'pdf-mapping-driver', 'cpu_seconds': 3}]}
        output = REPORT.table([row], ['fixture'], REPORT.PDF_LABELS)
        mapping = next(line for line in output.splitlines() if line.startswith('| OPM：`generate_and_run_batch.py`'))
        driver = next(line for line in output.splitlines() if line.startswith('| `run_batch_fill_render.py`'))
        self.assertIn('25.00%', mapping)
        self.assertIn('75.00%', driver)


if __name__ == '__main__':
    unittest.main()
