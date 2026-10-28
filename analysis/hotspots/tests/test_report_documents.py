import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from report_documents import publish


class ReportDocumentsTests(unittest.TestCase):
    def fixture(self):
        ids = ('opm', 'irs_w4', 'sba1919', 'tlc', 'hr_metro', 'egrid', 'industry_productivity')
        names = ('opm-n10', *ids[1:])
        metrics = ('IPC', 'Bad Speculation', 'Frontend Bound', 'Backend Bound', 'Retiring',
                   'Core Bound', 'Memory Bound', 'Fetch Latency Bound', 'Fetch Bandwidth Bound', 'idle_pct')
        stats = {ds: dict(statistics={m: dict(values=[1, 2, 3, 4, 5], mean=3,
                    sample_standard_deviation=1.5, cv_percent=50) for m in metrics}) for ds in ids}
        pairs = [dict(reference='opm' if target in ids[1:3] else 'tlc', target=target,
                      common_top10_count=6, hotspot_jaccard=6/14, bound_cosine=.95,
                      raw_euclid_auxiliary=2) for target in (*ids[1:3], *ids[4:])]
        profiles = {n: dict(processes=[], libraries=[], functions=[
            dict(library='libpython', function='frame', share_roi=.2)]) for n in names}
        groups = [dict(title='PDF', datasets=list(names[:3])), dict(title='XLSX', datasets=list(names[3:]))]
        row = dict(reference_rank=1, library='libpython', function='frame',
                   datasets={n: dict(share_roi=.2, top10=True) for n in names})
        presentation = dict(xlsx_process_groups={n: [] for n in names[3:]},
                            function_tables={'PDF': [row], 'XLSX': [row]})
        methods = dict(hotspot_captures=[], topdown_captures=[])
        joint = dict(statistics=stats, pairs=pairs, measurement_methodology=methods,
            measurement_section='### 4.1 硬件、软件与容器\n\n| test-hardware | test-image-id |\n\n### 4.2 other\n',
            hotspot_repeatability={ds: dict(pairwise_common_min=6, pairwise_common_max=9) for ds in ids},
            figures=[], time_series=dict(path='points.json', runs=35, points=100),
            sources=dict(topdown_statistics=dict(path='statistics.json'), topdown_verification=dict(path='verification.json')))
        config = dict(groups=groups, assessment=dict(xlsx_datasets=[], pdf_datasets=[], trace_sources=[
            ['example', 'trace-id', 'helper.py']]), output='analysis/report', joint_comparison=dict(path='joint.json'),
            document_outputs=dict(assessment='docs/assessment.md', experiment_record='docs/experimental-results.md'))
        return config, profiles, presentation, joint

    def test_two_documents_keep_method_and_separate_detailed_values(self):
        config, profiles, presentation, joint = self.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'docs').mkdir()
            report = root / 'docs/assessment.md'
            hashes = publish(config, profiles, presentation, joint,
                '# 文档解析类 Agent 代表性评估报告\n\nPreserved full data\n', root, report)
            assessment = report.read_text()
            record = (root / 'docs/experimental-results.md').read_text()
            self.assertEqual(len(hashes), 2)
            for required in ('关键发现', 'test-hardware', 'test-image-id', 'trace-id', 'P01',
                             'perf record', 'tuner top-down', 'cycles:u', '相似度', 'Jaccard',
                             'CPU 0–7', 'Word/PPT', '0.950000'):
                self.assertIn(required, assessment)
            self.assertIn('共享 6／6 个', assessment)
            self.assertNotIn('共享 9／7 个', assessment)
            self.assertNotIn('Preserved full data', assessment)
            self.assertIn('Preserved full data', record)
            self.assertIn('| 指标 | R1 | R2 | R3 | R4 | R5 |', record)
            self.assertIn('合并物理函数 Top-20', record)
            self.assertNotIn('| 指标 | R1 |', assessment)
            # Regeneration must rewrite both from source, rather than appending duplicates.
            publish(config, profiles, presentation, joint,
                '# 文档解析类 Agent 代表性评估报告\n\nPreserved full data\n', root, report)
            self.assertEqual(report.read_text(), assessment)
            self.assertEqual((root / 'docs/experimental-results.md').read_text(), record)

    def test_declared_assessment_path_mismatch_is_rejected_before_writing(self):
        config, profiles, presentation, joint = self.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'docs').mkdir()
            report = root / 'docs/wrong.md'
            with self.assertRaisesRegex(ValueError, 'declared document path'):
                publish(config, profiles, presentation, joint, '', root, report)
            self.assertFalse(report.exists())


if __name__ == '__main__':
    unittest.main()
