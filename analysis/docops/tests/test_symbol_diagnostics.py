from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from symbol_diagnostics import components,counter_quality


class SymbolDiagnosticsTests(unittest.TestCase):
    def test_tiny_records_do_not_receive_equal_weight(self):
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp)/'counters'
            p.write_text('8/8 1.000000000: 500 cycles:u:\n2/2 2.000000000: 1 cycles:u:\n2/2 2.100000000: 99 cycles:u:\n9/9 2.200000000: 600 cycles:u:\n')
            q=counter_quality(p,[(2*10**9,3*10**9)],9,100,2)
            self.assertEqual(q['period_le_1_samples'],1)
            self.assertEqual(q['period_le_1_share_roi'],.01)
            with self.assertRaises(ValueError):counter_quality(p,[(2*10**9,3*10**9)],9,99,2)

    def test_component_unknown_uses_its_own_denominator(self):
        p={'roi_period':100,'functions':[
            {'dso':'/opt/python/libpython.so','function':'[unknown]','period':10},
            {'dso':'/opt/python/libpython.so','function':'eval','period':30},
            {'dso':'/opt/libreoffice25.8-symbols/program/libswlo.so','function':'layout','period':60}]}
        rows=components(p)
        self.assertEqual(rows['Python']['unknown_share_within_component'],.25)
        self.assertEqual(rows['Python']['share_roi'],.4)
        self.assertEqual(rows['LibreOffice']['unknown_share_within_component'],0)


if __name__=='__main__':unittest.main()
