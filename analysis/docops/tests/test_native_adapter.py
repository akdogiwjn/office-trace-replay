from pathlib import Path
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE.parent/'hotspots'))
sys.path.insert(0,str(HERE))
import native_adapter as parser


class NativeAdapterTests(unittest.TestCase):
    def test_cpp_namespace_parentheses_are_not_a_dso(self):
        text='''python 4/4 1.000000001: 17 cycles:u:
\t10d2c std::Map<(anonymous namespace)::Hasher>::operator[]+0x10 (/usr/lib/libuno_cppu.so.3)
\t18884 caller+0x8 (/usr/lib/libpython.so)

'''
        with tempfile.TemporaryDirectory()as root:
            p=Path(root)/'samples.txt';p.write_text(text)
            samples=parser.parse(p);leaf=samples[0]['frames'][0]
            self.assertEqual(leaf['dso'],'/usr/lib/libuno_cppu.so.3')
            self.assertEqual(leaf['symbol'],'std::Map<(anonymous namespace)::Hasher>::operator[]')
            streamed=list(parser.leaf_records(p))
            self.assertEqual(streamed[0]['leaf'],('10d2c','/usr/lib/libuno_cppu.so.3'))
            self.assertEqual(streamed[0]['key'][3],17)

    def test_streaming_keeps_empty_stacks_and_unknown_dsos(self):
        text='''proc 1/1 1.0: 5 cycles:u:

proc 2/2 2.0: 9 cycles:u:
\tab [unknown] ([unknown])

'''
        with tempfile.TemporaryDirectory()as root:
            p=Path(root)/'samples.txt';p.write_text(text)
            records=list(parser.leaf_records(p))
            self.assertIsNone(records[0]['leaf'])
            self.assertEqual(records[1]['leaf'],('ab','[unknown]'))
            self.assertEqual(sum(r['key'][3]for r in records),14)


if __name__=='__main__':unittest.main()
