from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from svg2canvasx.styles import build_style
from svg2canvasx.styles import is_visible
from svg2canvasx.styles import parse_dasharray
from svg2canvasx.styles import style_to_output


class StyleTests(unittest.TestCase):
    def test_style_attribute_overrides_parent(self):
        node = ET.fromstring('<rect style="fill:#fff;stroke:#000" stroke-width="2"/>')
        style = build_style(node, {"fill": "#111", "font-weight": "bold"}, [])
        output = style_to_output(style)
        self.assertEqual(output["fill"], "#fff")
        self.assertEqual(output["stroke"], "#000")
        self.assertEqual(output["stroke_width"], 2.0)
        self.assertEqual(output["font_weight"], "bold")

    def test_dasharray_parses_to_numbers(self):
        self.assertEqual(parse_dasharray("2, 1"), [2.0, 1.0])
        self.assertEqual(parse_dasharray("1 1"), [1.0, 1.0])
        self.assertIsNone(parse_dasharray("none"))

    def test_hidden_styles_are_skipped(self):
        self.assertFalse(is_visible({"display": "none"}, False))
        self.assertFalse(is_visible({"visibility": "hidden"}, False))
        self.assertFalse(is_visible({"opacity": "0"}, False))
        self.assertTrue(is_visible({"display": "none"}, True))
