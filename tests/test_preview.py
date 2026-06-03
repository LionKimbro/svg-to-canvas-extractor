from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from svg2canvasx.preview import adjusted_text_position
from svg2canvasx.preview import annotation_display_label
from svg2canvasx.preview import annotation_style_object
from svg2canvasx.preview import baseline_offset
from svg2canvasx.preview import configure_preview_close_behavior
from svg2canvasx.preview import make_tk_font
from svg2canvasx.preview import safe_destroy
from svg2canvasx.preview import scale_points
from svg2canvasx.preview import style_dash
from svg2canvasx.preview import style_fill
from svg2canvasx.preview import style_width
from svg2canvasx.preview import tk_text_angle


class PreviewTests(unittest.TestCase):
    def test_configure_preview_close_behavior_destroys_toplevel_and_root(self):
        events = []

        class FakeWidget:
            def __init__(self, name):
                self.name = name
                self.exists = True
                self.handler = None

            def protocol(self, name, handler):
                events.append((self.name, "protocol", name))
                self.handler = handler

            def destroy(self):
                events.append((self.name, "destroy"))
                self.exists = False

            def winfo_exists(self):
                return 1 if self.exists else 0

        root = FakeWidget("root")
        window = FakeWidget("window")
        handle_close = configure_preview_close_behavior(root, window)
        handle_close()
        self.assertEqual(
            events,
            [
                ("window", "protocol", "WM_DELETE_WINDOW"),
                ("window", "destroy"),
                ("root", "destroy"),
            ],
        )

    def test_safe_destroy_ignores_missing_widget(self):
        class FakeWidget:
            def winfo_exists(self):
                return 0

            def destroy(self):
                raise AssertionError("destroy should not be called")

        safe_destroy(FakeWidget())

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

    def test_baseline_offset_moves_south_anchors_down(self):
        offset = baseline_offset("sw", {"descent": 4})
        self.assertEqual(offset, 4.0)
        self.assertEqual(baseline_offset("center", {"descent": 4}), 0.0)

    def test_adjusted_text_position_applies_baseline_offset(self):
        point = adjusted_text_position([100.0, 50.0], 1.0, "s", {"descent": 4})
        self.assertEqual(point, [100.0, 54.0])

    def test_annotation_display_label_prefers_annotation_name(self):
        obj = {
            "uid": "u1",
            "svg_id": "r1",
            "annotation": {"kind": "region", "name": "command_entries", "raw_label": "region.command_entries"},
        }
        self.assertEqual(annotation_display_label(obj), "command_entries")

    def test_annotation_display_label_falls_back_to_raw_label_then_ids(self):
        self.assertEqual(
            annotation_display_label({"uid": "u1", "svg_id": "r1", "annotation": {"kind": "unknown", "name": None, "raw_label": "helper.box"}}),
            "helper.box",
        )
        self.assertEqual(annotation_display_label({"uid": "u1", "svg_id": "r1"}), "r1")
        self.assertEqual(annotation_display_label({"uid": "u1"}), "u1")

    def test_annotation_style_object_uses_overlay_styling(self):
        styled = annotation_style_object({"style": {"fill": "#ffffff", "stroke": "#000000"}})
        self.assertEqual(styled["style"]["fill"], "")
        self.assertEqual(styled["style"]["stroke"], "#1a8f8f")
        self.assertEqual(styled["style"]["stroke_dasharray_values"], [4.0, 2.0])
