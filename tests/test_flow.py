from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from svg2canvasx.flow import convert_extracted_data_to_flow
from svg2canvasx.flow import create_canvas_for_flow
from svg2canvasx.flow import create_toplevel_for_flow
from svg2canvasx.flow import draw_flow_on_canvas
from svg2canvasx.flow import flow_to_preview_data
from svg2canvasx.flow import generate_rawtkinter_source


class FakeCanvas:
    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.kwargs = kwargs
        self.calls = []
        self.packed = False

    def pack(self, **kwargs):
        self.packed = True
        self.pack_kwargs = kwargs

    def create_rectangle(self, *args, **kwargs):
        self.calls.append(("create_rectangle", args, kwargs))

    def create_polygon(self, *args, **kwargs):
        self.calls.append(("create_polygon", args, kwargs))

    def create_line(self, *args, **kwargs):
        self.calls.append(("create_line", args, kwargs))

    def create_oval(self, *args, **kwargs):
        self.calls.append(("create_oval", args, kwargs))

    def create_text(self, *args, **kwargs):
        self.calls.append(("create_text", args, kwargs))


class FakeToplevel:
    def __init__(self, root):
        self.root = root


def sample_flow():
    return {
        "format": "svg2canvasx-flow",
        "version": 1,
        "source": {"path": "example.svg", "extracted_from": "example.svg"},
        "canvas": {"width": 100.0, "height": 80.0, "viewBox": [0.0, 0.0, 100.0, 80.0]},
        "layers": [
            {
                "name": "Presentation",
                "role": "presentation",
                "items": [
                    {
                        "kind": "rect",
                        "label": "box.main",
                        "bbox": [0.0, 0.0, 10.0, 20.0],
                        "draw": {"fill": None, "stroke": "#111111", "stroke_width": 2.0, "dash": None},
                    },
                    {
                        "kind": "text",
                        "label": "title",
                        "text": "Hello",
                        "point": [5.0, 6.0],
                        "text_style": {
                            "font_family": "Arial",
                            "font_size": 14.0,
                            "bold": True,
                            "italic": False,
                            "anchor": "sw",
                            "angle": 0.0,
                            "fill": "#333333",
                        },
                    },
                ],
            },
            {
                "name": "Annotations",
                "role": "annotation",
                "regions": [
                    {
                        "label": "region.main_panel",
                        "name": "main_panel",
                        "shape": "rect",
                        "bbox": [1.0, 2.0, 3.0, 4.0],
                    }
                ],
            },
        ],
    }


class FlowTests(unittest.TestCase):
    def test_flow_groups_objects_by_layer(self):
        extracted = {
            "source": {"path": "example.svg"},
            "svg": {"width": 100.0, "height": 80.0, "viewBox": [0.0, 0.0, 100.0, 80.0]},
            "layers": [
                {"id": "layer2", "label": "schematic objects", "role": "presentation"},
                {"id": "layer3", "label": "semantic regions", "role": "annotation"},
            ],
            "objects": [
                {
                    "svg_id": "r1",
                    "kind": "rect",
                    "layer": "layer2",
                    "inkscape_label": "main.rect",
                    "style": {"fill": "none", "stroke": "#000000", "stroke_width": 2.0, "stroke_dasharray_values": [2.0, 1.0]},
                    "world": {"bbox": [10.0, 20.0, 40.0, 60.0], "points": [[10.0, 20.0], [40.0, 20.0], [40.0, 60.0], [10.0, 60.0]], "matrix": [1, 0, 0, 1, 0, 0]},
                },
                {
                    "svg_id": "t1",
                    "kind": "text",
                    "layer": "layer2",
                    "label": "title.text",
                    "text": "Hello",
                    "style": {"font_family": "Arial", "font_size": 18.0, "font_weight": "700", "font_style": "italic", "fill": "#222222"},
                    "world": {"anchor_point": [50.0, 30.0], "angle_degrees": 15.0},
                    "text_layout": {"suggested_tk_anchor": "s"},
                },
            ],
            "annotations": [
                {
                    "svg_id": "a1",
                    "kind": "rect",
                    "layer": "layer3",
                    "inkscape_label": "region.main_panel",
                    "annotation": {"kind": "region", "name": "main_panel", "raw_label": "region.main_panel"},
                    "style": {"stroke": "#00ffff"},
                    "world": {"bbox": [1.0, 2.0, 3.0, 4.0]},
                }
            ],
        }
        flow = convert_extracted_data_to_flow(extracted)
        self.assertEqual(flow["format"], "svg2canvasx-flow")
        self.assertEqual(flow["version"], 1)
        self.assertEqual(flow["canvas"]["width"], 100.0)
        self.assertEqual(len(flow["layers"]), 2)
        self.assertEqual(flow["layers"][0]["role"], "presentation")
        self.assertEqual(flow["layers"][1]["role"], "annotation")
        self.assertEqual(len(flow["layers"][0]["items"]), 2)
        self.assertEqual(len(flow["layers"][1]["regions"]), 1)

    def test_presentation_rect_becomes_compact_rect_item(self):
        extracted = {
            "source": {"path": "example.svg"},
            "svg": {},
            "layers": [],
            "objects": [
                {
                    "svg_id": "r1",
                    "kind": "rect",
                    "layer": {"id": "layer2", "label": "Presentation", "role": "presentation"},
                    "inkscape_label": "box.main",
                    "style": {"fill": "none", "stroke": "#111111", "stroke_width": 2.0, "stroke_dasharray_values": [4.0, 2.0]},
                    "world": {"bbox": [0.0, 0.0, 10.0, 20.0], "points": [[0.0, 0.0], [10.0, 0.0], [10.0, 20.0], [0.0, 20.0]], "matrix": [1, 0, 0, 1, 0, 0]},
                }
            ],
            "annotations": [],
        }
        item = convert_extracted_data_to_flow(extracted)["layers"][0]["items"][0]
        self.assertEqual(item["kind"], "rect")
        self.assertEqual(item["label"], "box.main")
        self.assertEqual(item["bbox"], [0.0, 0.0, 10.0, 20.0])
        self.assertEqual(item["draw"]["fill"], None)
        self.assertEqual(item["draw"]["stroke"], "#111111")
        self.assertEqual(item["draw"]["dash"], [4.0, 2.0])
        self.assertNotIn("layer", item)

    def test_presentation_text_becomes_compact_text_item(self):
        extracted = {
            "source": {"path": "example.svg"},
            "svg": {},
            "layers": [],
            "objects": [
                {
                    "svg_id": "t1",
                    "kind": "text",
                    "layer": {"id": "layer2", "label": "Presentation", "role": "presentation"},
                    "label": "title",
                    "text": "Hello",
                    "style": {"font_family": "Arial", "font_size": 14.0, "font_weight": "bold", "font_style": "oblique", "fill": "#333333"},
                    "world": {"anchor_point": [5.0, 6.0], "angle_degrees": -30.0},
                    "text_layout": {"suggested_tk_anchor": "sw"},
                    "spans": [
                        {
                            "text": "Hello",
                            "style": {"font_family": "Arial", "font_size": 14.0, "font_weight": "bold", "font_style": "oblique", "fill": "#333333"},
                            "local": {"x": 5.0, "y": 6.0},
                            "svg_id": "t1",
                            "parent_svg_id": None,
                        }
                    ],
                }
            ],
            "annotations": [],
        }
        item = convert_extracted_data_to_flow(extracted)["layers"][0]["items"][0]
        self.assertEqual(item["kind"], "text")
        self.assertEqual(item["label"], "title")
        self.assertEqual(item["text"], "Hello")
        self.assertEqual(item["point"], [5.0, 6.0])
        self.assertEqual(item["text_style"]["font_family"], "Arial")
        self.assertTrue(item["text_style"]["bold"])
        self.assertTrue(item["text_style"]["italic"])
        self.assertEqual(item["text_style"]["anchor"], "sw")
        self.assertEqual(item["text_style"]["angle"], -30.0)
        self.assertEqual(item["tags"], ["source:t1", "span:t1"])

    @mock.patch("svg2canvasx.flow._measure_text_width", side_effect=[40.0, 30.0, 20.0, 50.0])
    def test_multiline_styled_text_flattens_to_multiple_flow_items(self, _measure_text_width):
        extracted = {
            "source": {"path": "example.svg"},
            "svg": {},
            "layers": [
                {"uid": "layer2", "svg_id": "layer2", "label": "Presentation", "role": "presentation"},
            ],
            "objects": [
                {
                    "svg_id": "text7068",
                    "kind": "text",
                    "layer": "layer2",
                    "label": "note.body",
                    "style": {"font_family": "Arial", "font_size": 12.0, "font_weight": "400", "font_style": "normal", "fill": "#111111"},
                    "groups": [{"id": "panel-main", "label": "panel-main"}],
                    "world": {"anchor_point": [650.0, 154.0], "angle_degrees": 0.0, "matrix": [1, 0, 0, 1, 0, 0]},
                    "text_layout": {"suggested_tk_anchor": "sw"},
                    "spans": [
                        {
                            "text": "and I'm not sure ",
                            "style": {"font_family": "Arial", "font_size": 12.0, "font_style": "normal", "fill": "#111111"},
                            "local": {"x": 650.0, "y": 154.0},
                            "svg_id": "tspan7074",
                            "parent_svg_id": None,
                        },
                        {
                            "text": "how this is",
                            "style": {"font_family": "Arial", "font_size": 12.0, "font_style": "italic", "fill": "#111111"},
                            "local": {"x": None, "y": None},
                            "svg_id": "tspan7078",
                            "parent_svg_id": "tspan7074",
                        },
                        {
                            "text": "handled",
                            "style": {"font_family": "Arial", "font_size": 12.0, "font_style": "italic", "fill": "#111111"},
                            "local": {"x": 650.0, "y": 162.0},
                            "svg_id": "tspan7080",
                            "parent_svg_id": "tspan7076",
                        },
                        {
                            "text": " in Inkscape.",
                            "style": {"font_family": "Arial", "font_size": 12.0, "font_style": "normal", "fill": "#111111"},
                            "local": {"x": None, "y": None},
                            "svg_id": "tspan7076",
                            "parent_svg_id": None,
                        },
                    ],
                }
            ],
            "annotations": [],
        }
        items = convert_extracted_data_to_flow(extracted)["layers"][0]["items"]
        self.assertEqual(len(items), 4)
        self.assertEqual([item["text"] for item in items], [
            "and I'm not sure ",
            "how this is",
            "handled",
            " in Inkscape.",
        ])
        self.assertEqual(items[0]["point"], [650.0, 154.0])
        self.assertEqual(items[1]["point"], [690.0, 154.0])
        self.assertEqual(items[2]["point"], [650.0, 162.0])
        self.assertEqual(items[3]["point"], [670.0, 162.0])
        self.assertFalse(items[0]["text_style"]["italic"])
        self.assertTrue(items[1]["text_style"]["italic"])
        self.assertTrue(items[2]["text_style"]["italic"])
        self.assertFalse(items[3]["text_style"]["italic"])
        self.assertIn("source:text7068", items[0]["tags"])
        self.assertIn("span:tspan7078", items[1]["tags"])
        self.assertIn("parent-span:tspan7074", items[1]["tags"])
        self.assertIn("group:panel-main", items[0]["tags"])

    @mock.patch("svg2canvasx.flow._measure_text_width", side_effect=[40.0, 8.0, 30.0])
    def test_whitespace_only_text_segments_are_dropped_but_still_advance_layout(self, _measure_text_width):
        extracted = {
            "source": {"path": "example.svg"},
            "svg": {},
            "layers": [
                {"uid": "layer2", "svg_id": "layer2", "label": "Presentation", "role": "presentation"},
            ],
            "objects": [
                {
                    "svg_id": "text100",
                    "kind": "text",
                    "layer": "layer2",
                    "label": "note.inline",
                    "style": {"font_family": "Arial", "font_size": 12.0, "fill": "#111111"},
                    "world": {"anchor_point": [100.0, 50.0], "angle_degrees": 0.0, "matrix": [1, 0, 0, 1, 0, 0]},
                    "text_layout": {"suggested_tk_anchor": "sw"},
                    "spans": [
                        {
                            "text": "hello",
                            "style": {"font_family": "Arial", "font_size": 12.0, "fill": "#111111"},
                            "local": {"x": 100.0, "y": 50.0},
                            "svg_id": "tspan1",
                            "parent_svg_id": None,
                        },
                        {
                            "text": " ",
                            "style": {"font_family": "Arial", "font_size": 12.0, "fill": "#111111"},
                            "local": {"x": None, "y": None},
                            "svg_id": "tspan_space",
                            "parent_svg_id": "tspan1",
                        },
                        {
                            "text": "world",
                            "style": {"font_family": "Arial", "font_size": 12.0, "fill": "#111111"},
                            "local": {"x": None, "y": None},
                            "svg_id": "tspan2",
                            "parent_svg_id": "tspan1",
                        },
                    ],
                }
            ],
            "annotations": [],
        }
        items = convert_extracted_data_to_flow(extracted)["layers"][0]["items"]
        self.assertEqual([item["text"] for item in items], ["hello", "world"])
        self.assertEqual(items[0]["point"], [100.0, 50.0])
        self.assertEqual(items[1]["point"], [148.0, 50.0])

    def test_annotation_rect_becomes_compact_region(self):
        extracted = {
            "source": {"path": "example.svg"},
            "svg": {},
            "layers": [],
            "objects": [],
            "annotations": [
                {
                    "svg_id": "a1",
                    "kind": "rect",
                    "layer": {"id": "layer3", "label": "Annotations", "role": "annotation"},
                    "inkscape_label": "region.command_entries",
                    "annotation": {"kind": "region", "name": "command_entries", "raw_label": "region.command_entries"},
                    "style": {"fill": "none", "stroke": "#ff00ff"},
                    "world": {"bbox": [1.0, 2.0, 30.0, 40.0]},
                }
            ],
        }
        region = convert_extracted_data_to_flow(extracted)["layers"][0]["regions"][0]
        self.assertEqual(region, {
            "label": "region.command_entries",
            "name": "command_entries",
            "shape": "rect",
            "bbox": [1.0, 2.0, 30.0, 40.0],
            "source": None,
        })

    def test_annotation_styles_are_omitted_and_item_layer_field_is_omitted(self):
        extracted = {
            "source": {"path": "example.svg"},
            "svg": {},
            "layers": [],
            "objects": [
                {
                    "svg_id": "r1",
                    "kind": "rect",
                    "layer": {"id": "layer2", "label": "Presentation", "role": "presentation"},
                    "style": {"fill": "#fff"},
                    "world": {"bbox": [0.0, 0.0, 1.0, 1.0], "points": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], "matrix": [1, 0, 0, 1, 0, 0]},
                }
            ],
            "annotations": [
                {
                    "svg_id": "a1",
                    "kind": "path",
                    "layer": {"id": "layer3", "label": "Annotations", "role": "annotation"},
                    "label": "guide.main",
                    "style": {"stroke": "#0ff"},
                    "world": {"bbox": [1.0, 2.0, 3.0, 4.0]},
                }
            ],
        }
        flow = convert_extracted_data_to_flow(extracted)
        item = flow["layers"][0]["items"][0]
        region = flow["layers"][1]["regions"][0]
        self.assertNotIn("layer", item)
        self.assertNotIn("style", region)
        self.assertEqual(region["shape"], "bbox")
        self.assertIsNone(region["name"])

    def test_visual_region_annotation_stays_with_presentation_layer_and_adds_region(self):
        extracted = {
            "source": {"path": "example.svg"},
            "svg": {},
            "layers": [
                {"id": "layer2", "label": "Presentation", "role": "presentation"},
            ],
            "objects": [
                {
                    "svg_id": "r1",
                    "kind": "rect",
                    "layer": {"id": "layer2", "label": "Presentation", "role": "presentation"},
                    "label": "command.1.entry",
                    "inkscape_label": "command.1.entry [region]",
                    "tags": ["region"],
                    "style": {"fill": "none", "stroke": "#111111", "stroke_width": 2.0},
                    "world": {"bbox": [0.0, 0.0, 10.0, 20.0], "points": [[0.0, 0.0], [10.0, 0.0], [10.0, 20.0], [0.0, 20.0]], "matrix": [1, 0, 0, 1, 0, 0]},
                }
            ],
            "annotations": [
                {
                    "svg_id": "r1",
                    "kind": "rect",
                    "layer": {"id": "layer2", "label": "Presentation", "role": "presentation"},
                    "label": "command.1.entry",
                    "annotation": {"kind": "region", "name": "command.1.entry", "raw_label": "command.1.entry", "source": "visual-item"},
                    "world": {"bbox": [0.0, 0.0, 10.0, 20.0]},
                }
            ],
        }
        flow = convert_extracted_data_to_flow(extracted)
        self.assertEqual(flow["layers"][0]["role"], "presentation")
        self.assertEqual(flow["layers"][0]["regions"][0]["name"], "command.1.entry")
        self.assertEqual(flow["layers"][0]["regions"][0]["source"], "visual-item")

    def test_flow_preview_conversion_supports_flow_documents(self):
        flow = sample_flow()
        preview = flow_to_preview_data(flow)
        self.assertEqual(preview["svg"]["width"], 100.0)
        self.assertEqual(preview["objects"][0]["svg_id"], "box.main")
        self.assertEqual(preview["annotations"][0]["annotation"]["name"], "main_panel")

    def test_draw_flow_on_canvas_draws_presentation_only(self):
        canvas = FakeCanvas()
        draw_flow_on_canvas(canvas, sample_flow())
        self.assertEqual([call[0] for call in canvas.calls], ["create_rectangle", "create_text"])

    @mock.patch("svg2canvasx.flow.tkinter.Canvas", new=FakeCanvas)
    def test_create_canvas_for_flow_returns_canvas_and_draws(self):
        canvas = create_canvas_for_flow(object(), sample_flow())
        self.assertIsInstance(canvas, FakeCanvas)
        self.assertTrue(canvas.packed)
        self.assertEqual(canvas.kwargs["width"], 100)
        self.assertEqual(canvas.kwargs["height"], 80)
        self.assertEqual([call[0] for call in canvas.calls], ["create_rectangle", "create_text"])

    @mock.patch("svg2canvasx.flow.tkinter.Canvas", new=FakeCanvas)
    @mock.patch("svg2canvasx.flow.tkinter.Toplevel", new=FakeToplevel)
    def test_create_toplevel_for_flow_returns_window_and_canvas(self):
        root = object()
        created = create_toplevel_for_flow(root, sample_flow())
        self.assertIsInstance(created["toplevel"], FakeToplevel)
        self.assertIs(created["toplevel"].root, root)
        self.assertIsInstance(created["canvas"], FakeCanvas)

    def test_generate_rawtkinter_source_emits_draw_function(self):
        source = generate_rawtkinter_source(sample_flow())
        self.assertIn("def draw(canvas):", source)
        self.assertIn("canvas.create_rectangle", source)
        self.assertIn("canvas.create_text", source)
        self.assertNotIn("region.main_panel", source)
