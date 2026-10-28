import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gate import Gate,exchange
from capture import idle


class GateTests(unittest.TestCase):
    def test_affinity_sequence_excludes_preflight_and_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            affinity={9};requests=[];observed=[]
            def change(pid,value):affinity.clear();affinity.update(value)
            def boundary(folder,recipe,index,scope,event):
                observed.append((scope,event,set(affinity)))
                return dict(scope=scope,event=event,monotonic_ns=len(observed))
            gate=Gate(Path(temp)/'socket',Path(temp)/'events')
            with patch('gate.os.sched_getaffinity',side_effect=lambda pid:set(affinity)),\
                 patch('gate.os.sched_setaffinity',side_effect=change),\
                 patch('gate.exchange',side_effect=lambda p,r:requests.append(r)):
                wrapped=gate.boundary(boundary)
                wrapped(None,{},1,'loop_including_reset','start')
                wrapped(None,{},1,'workflow','start')
                wrapped(None,{},1,'workflow','end')
                wrapped(None,{},1,'loop_including_reset','end')
                wrapped(None,{},1,'archive_excluded','start')
            self.assertEqual([r['action'] for r in requests],['begin','end'])
            self.assertTrue(all(row[2]==set(range(8)) for row in observed[:4]))
            self.assertEqual(observed[-1][2],{9})
            self.assertFalse(gate.active)

    def test_invalid_gate_sequences_and_initial_affinity_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            gate=Gate(Path(temp)/'socket',Path(temp)/'events')
            with self.assertRaises(ValueError):gate.end({'monotonic_ns':0})
            with patch('gate.os.sched_getaffinity',return_value={0}),patch('gate.exchange') as send:
                with self.assertRaises(ValueError):gate.begin()
                send.assert_not_called()

    def test_idle_avoids_guest_double_counting(self):
        before={'cpu0':[0]*10};after={'cpu0':[10,0,10,80,0,0,0,0,5,0]}
        self.assertEqual(idle(before,after)['idle_pct'],80)
        with self.assertRaises(ValueError):idle(after,before)


if __name__=='__main__':unittest.main()
