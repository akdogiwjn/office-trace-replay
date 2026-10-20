"""Small fixtures for physical-frame normalization used by v1 analysis."""
import importlib.util
import sys
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[1]
SCRIPT = BASE / "scripts/analyze_new_xlsx_hotspots_v1.py"
spec = importlib.util.spec_from_file_location("new_xlsx_hotspot_analysis", SCRIPT)
analysis = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = analysis
assert spec.loader
spec.loader.exec_module(analysis)


class PhysicalFrameNormalizationTests(unittest.TestCase):
    def test_inline_and_noinline_leaf_normalize_to_same_physical_function(self):
        inline = {
            "leaf_sym": "normal_nameLength", "leaf_dso": "inlined",
            "entity_sym": "storeAtts", "entity_dso": "/lib/pyexpat.cpython-312.so",
            "inline_recovered": True,
        }
        noinline = {
            "leaf_sym": "storeAtts", "leaf_dso": "/lib/pyexpat.cpython-312.so",
            "entity_sym": "storeAtts", "entity_dso": "/lib/pyexpat.cpython-312.so",
            "inline_recovered": False,
        }
        self.assertEqual(analysis.physical_leaf(inline), analysis.physical_leaf(noinline))
        self.assertEqual(analysis.physical_leaf(inline),
                         ("storeAtts", "/lib/pyexpat.cpython-312.so", "expat-xml"))

    def test_unknown_leaf_does_not_inherit_known_caller_dso(self):
        sample = {
            "leaf_sym": "[unknown-symbol]", "leaf_dso": "[unknown]",
            "entity_sym": "should_not_be_used", "entity_dso": "/lib/libpython3.12.so",
            "inline_recovered": False,
            "stack": [
                {"symbol": "[unknown-symbol]", "dso": "[unknown]", "inline": False},
                {"symbol": "PyObject_Call", "dso": "/lib/libpython3.12.so", "inline": False},
            ],
        }
        self.assertEqual(analysis.physical_leaf(sample),
                         ("[unknown-symbol]", "[unknown]", "unknown"))

    def test_physical_context_drops_inline_expansions_and_preserves_order(self):
        sample = {"stack": [
            {"symbol": "inlined_helper", "dso": "inlined", "inline": True},
            {"symbol": "physical_leaf", "dso": "/lib/libpython3.12.so", "inline": False},
            {"symbol": "inline_caller", "dso": "inlined", "inline": True},
            {"symbol": "physical_caller", "dso": "/lib/libz.so.1", "inline": False},
        ]}
        self.assertEqual(analysis.physical_stack_prefix(sample),
                         ("physical_leaf [libpython]", "physical_caller [zlib]"))
