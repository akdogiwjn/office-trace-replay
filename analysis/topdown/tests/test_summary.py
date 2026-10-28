from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from summarize import parse


def report():
    return '''TOP-DOWN Summary Report-ALL
IPC 1.00
Bad Speculation 0.00
Frontend Bound 16.67
Retiring 16.67
Backend Bound 66.67
Core Bound 50.00
Memory Bound 16.67
Fetch Latency Bound 10.00
Fetch Bandwidth Bound 6.67
  r0008 600
  r0011 600
  r001b 600
  r2011 600
  r2012 60
  r7001 400
  r7005 100
  r7006 0
'''


class SummaryTests(unittest.TestCase):
    def test_final_report_selected_not_interval_or_debug_percentage(self):
        value=parse(report().replace('IPC 1.00','IPC 9.00')+'\n'+report())
        self.assertEqual(value['metrics']['IPC'],1)

    def test_not_counted_preserved_with_printed_zero(self):
        value=parse('debug: event name: r7006, event count: <not counted>\n'+report())
        self.assertEqual(value['arithmetic']['debug_not_counted_events'],['r7006'])
        self.assertTrue(value['arithmetic']['printed_zero_is_not_independently_confirmed_zero'])

    def test_arithmetic_difference_is_visible_without_changing_tool_metrics(self):
        value=parse(report().replace('IPC 1.00','IPC 1.01'))
        self.assertEqual(value['metrics']['IPC'],1.01)
        self.assertFalse(value['arithmetic']['all_within_print_precision'])
        ipc=next(r for r in value['arithmetic']['checks'] if r['metric']=='IPC')
        self.assertEqual(ipc['recalculated'],1)

    def test_invalid_partition_or_missing_metric_rejected(self):
        for text in (report().replace('Core Bound 50.00','Core Bound 40.00'),
                     report().replace('IPC 1.00',''),report().replace('Backend Bound 66.67','Backend Bound -1.00')):
            with self.assertRaises(ValueError):parse(text)


if __name__=='__main__':unittest.main()
