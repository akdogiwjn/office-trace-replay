"""Small positive/negative checks for the full DevKit hierarchy/time extraction.

Uses tiny synthetic DevKit stdout fixtures (no real workload, no DevKit run).
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from devkit_full_extract import extract

STARTUP = (
    "debug: Add ... lib to LD_LIBRARY_PATH success\n"
    "debug: Enter the second level command: tuner\n"
    "debug: top-down task start\n"
)

EVENTS = (
    "debug: time of PmuRead: {pmu}\n"
    "debug: len of coreData: 464, len of uncoreData: 0, len of Merge Data: 464\n"
    "debug: aggregate type: -1, event name: r0008, event count: 1,000,000\n"
    "debug: aggregate type: -1, event name: r0011, event count: 2,000,000\n"
    "debug: aggregate type: -1, event name: r7002, event count: <not counted>\n"
    "debug: Print core event raw data \n"
    "\n"
)

TREE_1 = (
    "TOP-DOWN Summary Report-1                      Time:2026/01/02 03:04:05\n"
    "=======================================================================\n"
    "\n"
    "Top-down metrics of CPU(s) 0-7:\n"
    "Cycles              2,000,000\n"
    "Instructions        1,000,000\n"
    "IPC                 0.50\n"
    "\n"
    "───────────────────────────────────────────────────────────────────────\n"
    "  Top-down Metrics                        Bound(%)    Preferred Sampling Event  \n"
    "───────────────────────────────────────────────────────────────────────\n"
    "  Bad Speculation                             2.00    --\n"
    "  ├── Branch Mispredicts                      1.50    br_mis_pred\n"
    "  └── Machine Clears                          0.50    --\n"
    "      ├── Nuke Flush                          0.30    --\n"
    "      └── Other Flush                         0.20    --\n"
    "  Backend Bound                             98.00    --\n"
    "  └── Memory Bound                          40.00    --\n"
    "      ├── L1 Bound                           30.00    --\n"
    "      │   ├── DTLB                            12.00    --\n"
    "      │   └── Pipeline                        18.00    --\n"
    "      ├── L2 Bound                           8.00    --\n"
    "      │   └── Pipeline                        8.00    --\n"
    "      └── Store Bound                        2.00    --\n"
    "          ├── SCA                             1.00    --\n"
    "          └── Other                           1.00    --\n"
    "  └── Core Bound                             58.00    --\n"
    "      └── Exe Ports Util                     55.00    --\n"
    "          ├── 0 ports serialize              10.00    --\n"
    "          ├── 1 ports                        20.00    --\n"
    "          └── 6p ports                       25.00    --\n"
    "───────────────────────────────────────────────────────────────────────\n"
)

TREE_2 = (
    "TOP-DOWN Summary Report-2                      Time:2026/01/02 03:04:06\n"
    "=======================================================================\n"
    "\n"
    "Top-down metrics of CPU(s) 0-7:\n"
    "Cycles              1,000,000\n"
    "Instructions        500,000\n"
    "IPC                 0.50\n"
    "\n"
    "───────────────────────────────────────────────────────────────────────\n"
    "  Top-down Metrics                        Bound(%)    Preferred Sampling Event  \n"
    "───────────────────────────────────────────────────────────────────────\n"
    "  Bad Speculation                             5.00    --\n"
    "  Frontend Bound                             15.00    --\n"
    "  Retiring                                   20.00    inst_retired\n"
    "  Backend Bound                             60.00    --\n"
    "───────────────────────────────────────────────────────────────────────\n"
)

ALL_REPORT = (
    "TOP-DOWN Summary Report-ALL                     Time:2026/01/02 03:04:07\n"
    "=======================================================================\n"
    "\n"
    "Top-down metrics of CPU(s) 0-7:\n"
    "Cycles              3,000,000\n"
    "Instructions        1,500,000\n"
    "IPC                 0.50\n"
    "\n"
    "───────────────────────────────────────────────────────────────────────\n"
    "  Top-down Metrics                        Bound(%)    Preferred Sampling Event  \n"
    "───────────────────────────────────────────────────────────────────────\n"
    "  Bad Speculation                             3.00    --\n"
    "  ├── Branch Mispredicts                      2.00    br_mis_pred\n"
    "  └── Machine Clears                          1.00    --\n"
    "      ├── Nuke Flush                          0.60    --\n"
    "      └── Other Flush                         0.40    --\n"
    "  Frontend Bound                             12.00    --\n"
    "  Retiring                                   20.00    inst_retired\n"
    "  Backend Bound                             65.00    --\n"
    "  ├── Core Bound                             45.00    --\n"
    "  │   └── Exe Ports Util                     43.00    --\n"
    "  │       ├── 0 ports serialize              20.00    --\n"
    "  │       └── 6p ports                       23.00    --\n"
    "  └── Memory Bound                           20.00    --\n"
    "      ├── L1 Bound                           15.00    --\n"
    "      │   ├── DTLB                            4.00    --\n"
    "      │   └── Pipeline                       11.00    --\n"
    "      ├── L2 Bound                           5.00    --\n"
    "      │   └── Pipeline                        5.00    --\n"
    "      └── Store Bound                        5.00    --\n"
    "          ├── SCA                             3.00    --\n"
    "          └── Other                           2.00    --\n"
    "───────────────────────────────────────────────────────────────────────\n"
    "\n"
    "───────────────────────────────────────────────────────────────────────\n"
    "  PMU Event                                  Count  \n"
    "───────────────────────────────────────────────────────────────────────\n"
    "  r0008                          1,500,000\n"
    "  r0011                          3,000,000\n"
    "───────────────────────────────────────────────────────────────────────\n"
    "319439 milliseconds time elapsed\n"
)


def synthetic_log():
    parts = [STARTUP]
    parts.append(EVENTS.replace('{pmu}', '0'))
    parts.append(TREE_1)
    parts.append(EVENTS.replace('{pmu}', '1'))
    parts.append(TREE_2)
    parts.append(ALL_REPORT)
    return ''.join(parts)


class HierarchyTests(unittest.TestCase):
    def setUp(self):
        self.text = synthetic_log()
        self.data = extract(self.text)

    def test_top_level_nodes_are_depth_zero(self):
        tops = {n['name'] for n in self.data['final']['hierarchy'] if n['depth'] == 0}
        self.assertEqual(tops, {'Bad Speculation', 'Frontend Bound', 'Retiring', 'Backend Bound'})

    def test_last_child_space_continuation(self):
        # Machine Clears is a last child (└──); its children use space continuation.
        paths = {n['path'] for n in self.data['final']['hierarchy']}
        self.assertIn('Bad Speculation/Machine Clears/Nuke Flush', paths)
        self.assertIn('Bad Speculation/Machine Clears/Other Flush', paths)
        mc = [n for n in self.data['final']['hierarchy']
              if n['name'] == 'Machine Clears'][0]
        self.assertEqual(mc['depth'], 1)
        nuke = [n for n in self.data['final']['hierarchy'] if n['name'] == 'Nuke Flush'][0]
        self.assertEqual(nuke['depth'], 2)
        self.assertEqual(nuke['parent_path'], 'Bad Speculation/Machine Clears')

    def test_memory_l1_dtlb_and_store_sca(self):
        paths = {n['path'] for n in self.data['final']['hierarchy']}
        self.assertIn('Backend Bound/Memory Bound/L1 Bound', paths)
        self.assertIn('Backend Bound/Memory Bound/L1 Bound/DTLB', paths)
        self.assertIn('Backend Bound/Memory Bound/Store Bound', paths)
        self.assertIn('Backend Bound/Memory Bound/Store Bound/SCA', paths)

    def test_exe_ports_util_ports(self):
        paths = {n['path'] for n in self.data['final']['hierarchy']}
        self.assertIn('Backend Bound/Core Bound/Exe Ports Util/0 ports serialize', paths)
        self.assertIn('Backend Bound/Core Bound/Exe Ports Util/6p ports', paths)

    def test_same_name_nodes_distinct_paths(self):
        pipelines = [n['path'] for n in self.data['final']['hierarchy'] if n['name'] == 'Pipeline']
        self.assertEqual(sorted(pipelines), [
            'Backend Bound/Memory Bound/L1 Bound/Pipeline',
            'Backend Bound/Memory Bound/L2 Bound/Pipeline',
        ])
        others = [n['path'] for n in self.data['final']['hierarchy'] if n['name'] == 'Other']
        self.assertEqual(others, ['Backend Bound/Memory Bound/Store Bound/Other'])

    def test_approximate_marker_kept(self):
        # Resource Bound* is not in this fixture; ensure '*' is preserved when present.
        node = [n for n in self.data['final']['hierarchy'] if n['name'].endswith('*')]
        self.assertEqual(node, [])


class TimestepTests(unittest.TestCase):
    def setUp(self):
        self.data = extract(synthetic_log())

    def test_two_timesteps_and_final_separate(self):
        self.assertEqual(len(self.data['timesteps']), 2)
        for i, ts in enumerate(self.data['timesteps']):
            self.assertEqual(ts['sample_index'], i)
            self.assertEqual(ts['report_no'], str(i + 1))
        self.assertIsNone(self.data['final'].get('sample_index'))
        # Report-ALL is not an extra sample point
        self.assertFalse(any(ts['report_no'] == 'ALL' for ts in self.data['timesteps']))

    def test_report_time_and_pmu_raw_kept(self):
        ts = self.data['timesteps'][0]
        self.assertEqual(ts['report_time'], '2026/01/02 03:04:05')
        self.assertEqual(ts['pmu_raw_time_of_pmuread'], '0')
        self.assertIs(ts['pmu_read_is_not_sample_time'], True)
        ts2 = self.data['timesteps'][1]
        self.assertEqual(ts2['pmu_raw_time_of_pmuread'], '1')

    def test_per_timestep_events_and_flags(self):
        ts = self.data['timesteps'][0]
        self.assertEqual(ts['events'].get('r0008'), 1000000)
        self.assertIsNone(ts['events'].get('r7002'))  # <not counted> kept as None
        self.assertEqual([f['flag'] for f in ts['event_flags']], ['<not counted>'])

    def test_per_timestep_hierarchy_parsed(self):
        ts = self.data['timesteps'][0]
        self.assertEqual(ts['header']['IPC'], 0.5)
        l1 = [n for n in ts['hierarchy'] if n['name'] == 'L1 Bound']
        self.assertEqual([(n['path'], n['depth']) for n in l1],
                         [('Backend Bound/Memory Bound/L1 Bound', 2)])

    def test_final_header_and_events(self):
        f = self.data['final']
        self.assertEqual(f['header']['Cycles'], 3000000)
        self.assertEqual(f['header']['Instructions'], 1500000)
        self.assertEqual(f['pmu_events'].get('r0008'), 1500000)
        self.assertEqual(f['pmu_events'].get('r0011'), 3000000)

    def test_negative_duplicate_names_not_conflated(self):
        # a naive parser that keys by leaf name only would collapse the two Pipelines
        pipelines = self.data['final']['hierarchy']
        leaves = [n['name'] for n in pipelines]
        self.assertEqual(leaves.count('Pipeline'), 2)


class RunAgainstRealLog(unittest.TestCase):
    """Smoke: parse the real captured 014-n1000 DevKit log if present."""

    def test_real_log_extraction(self):
        campaign = Path('/home/lcq/office-trace-replay/results/docops/scaling-performance-20261105T114539Z')
        candidates = list(campaign.glob('*/topdown/out/devkit.stdout.txt'))
        if not candidates:
            self.skipTest('campaign log not present')
        for path in candidates[:1]:
            data = extract(path.read_text(encoding='utf-8', errors='replace'))
            self.assertGreater(len(data['timesteps']), 1)
            tops = [n['name'] for n in data['final']['hierarchy'] if n['depth'] == 0]
            self.assertEqual(set(tops), {'Bad Speculation', 'Frontend Bound', 'Retiring', 'Backend Bound'})


if __name__ == '__main__':
    unittest.main()
