from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import repeat_plots


class RepeatPlotTests(unittest.TestCase):
    def test_real_matplotlib_exports_all_five_points_without_external_data(self):
        datasets=('opm','irs_w4','sba1919','tlc','hr_metro','egrid','industry_productivity')
        stats={ds:dict(repeats=5,statistics={m:dict(values=[20,21,19,20,20],mean=20,
            sample_standard_deviation=1) for m in repeat_plots.BOUNDS}) for ds in datasets}
        with tempfile.TemporaryDirectory() as tmp,patch.object(repeat_plots,'ROOT',Path(tmp)):
            figures,version=repeat_plots.export(stats,Path(tmp))
            self.assertEqual(len(figures),2)
            self.assertTrue(version)
            for row in figures:
                path=Path(tmp)/row['filename']
                self.assertEqual(row['sha256'],repeat_plots.sha(path))
                self.assertIn('<svg',path.read_text())
                self.assertGreater(path.with_suffix('.png').stat().st_size,1000)


if __name__=='__main__':unittest.main()
