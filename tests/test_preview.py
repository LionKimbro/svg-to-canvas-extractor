from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from svg2canvasx.preview import make_tk_font
from svg2canvasx.preview import scale_points
from svg2canvasx.preview import style_dash
from svg2canvasx.preview import style_fill
from svg2canvasx.preview import style_width
from svg2canvasx.preview import tk_text_angle


class PreviewTests(unittest.TestCase):
    def test_style_dash_scales_to_tuple(self):
        style = {"stroke_dasharray_values": [2.0, 1.0]}
        self.assertEqual(style_dash(style, 1.0), (2, 1))
        self.assertEqual(style_dash(style, 2.0), (4, 2))

    def test_fill_none_becomes_empty_string(self):
        self.assertEqual(style_fill({"fill": "none"}), "")
        self.assertEqual(style_fill({}), "")
        self.assertEqual(style_fill({"fill": "#ffffff"}), "#ffffff")

    def test_make_tk_font_builds_bold_italic(self):
        font_value = make_tk_font(
            {
                "font_family": "Arial",
                "font_size": 16.0,
                "font_weight": "bold",
                "font_style": "italic",
            },
            1.0,
        )
        self.assertEqual(font_value, ("Arial", 12, "bold italic"))

    def test_make_tk_font_accepts_numeric_bold_and_oblique(self):
        font_value = make_tk_font(
            {
                "font_family": "Arial",
                "font_size": 20.0,
                "font_weight": "700",
                "font_style": "oblique",
            },
            1.0,
            1.0,
        )
        self.assertEqual(font_value, ("Arial", 20, "bold italic"))

    def test_scale_points_multiplies_coordinates(self):
        points = [[10.0, 20.0], [30.0, 40.0]]
        self.assertEqual(scale_points(points, 2.0), [[20.0, 40.0], [60.0, 80.0]])

    def test_style_width_scales_and_has_minimum(self):
        self.assertEqual(style_width({"stroke_width": 2.0}, 1.5), 3.0)
        self.assertEqual(style_width({}, 0.5), 1.0)

    def test_tk_text_angle_reverses_sign(self):
        self.assertEqual(tk_text_angle(90.0), -90.0)
        self.assertEqual(tk_text_angle(-45.0), 45.0)
