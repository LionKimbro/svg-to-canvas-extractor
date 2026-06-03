from pathlib import Path
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from svg2canvasx.extract import extract_svg_file


kSVG_HEADER = """\
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     width="200" height="200" viewBox="0 0 200 200">
"""


def run_extract(svg_body, flags=None):
    flags = flags or {}
    text = kSVG_HEADER + svg_body + "\n</svg>\n"
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "fixture.svg"
        path.write_text(textwrap.dedent(text), encoding="utf-8")
        return extract_svg_file(path, **flags)


class ExtractTests(unittest.TestCase):
    def test_rect_without_transform(self):
        data = run_extract(
            """
            <g id="layer2" inkscape:groupmode="layer" inkscape:label="Layer 2">
              <rect id="r1" x="10" y="20" width="30" height="40" />
            </g>
            """
        )
        obj = data["objects"][0]
        self.assertEqual(obj["kind"], "rect")
        self.assertEqual(obj["world"]["bbox"], [10.0, 20.0, 40.0, 60.0])

    def test_rect_inside_translate_group(self):
        data = run_extract(
            """
            <g id="layer2" inkscape:groupmode="layer" inkscape:label="Layer 2">
              <g id="grp" transform="translate(5,7)">
                <rect id="r1" x="10" y="20" width="30" height="40" />
              </g>
            </g>
            """
        )
        self.assertEqual(data["objects"][0]["world"]["bbox"], [15.0, 27.0, 45.0, 67.0])

    def test_rect_inside_nested_translate_groups(self):
        data = run_extract(
            """
            <g id="layer2" inkscape:groupmode="layer" inkscape:label="Layer 2">
              <g transform="translate(5,7)">
                <g transform="translate(2,3)">
                  <rect id="r1" x="10" y="20" width="30" height="40" />
                </g>
              </g>
            </g>
            """
        )
        self.assertEqual(data["objects"][0]["world"]["bbox"], [17.0, 30.0, 47.0, 70.0])

    def test_rect_inside_rotate_group(self):
        data = run_extract(
            """
            <g id="layer2" inkscape:groupmode="layer" inkscape:label="Layer 2">
              <g transform="rotate(90)">
                <rect id="r1" x="10" y="20" width="30" height="40" />
              </g>
            </g>
            """
        )
        self.assertEqual(data["objects"][0]["world"]["bbox"], [-60.0, 10.0, -20.0, 40.0])

    def test_text_with_bold_tspan(self):
        data = run_extract(
            """
            <g id="layer2" inkscape:groupmode="layer" inkscape:label="Layer 2">
              <text id="t1" x="10" y="20" font-family="Arial" font-size="12">
                Base<tspan font-weight="bold">Bold</tspan>
              </text>
            </g>
            """
        )
        obj = data["objects"][0]
        self.assertIn("BaseBold", obj["text"].replace("\n", "").replace(" ", ""))
        bold_spans = [span for span in obj["spans"] if span["style"].get("font_weight") == "bold"]
        self.assertTrue(bold_spans)

    def test_text_tspan_is_not_duplicated(self):
        data = run_extract(
            """
            <g id="layer2" inkscape:groupmode="layer" inkscape:label="Layer 2">
              <text id="t1">
                <tspan x="520" y="80" font-weight="bold">Command Interface Deck</tspan>
              </text>
            </g>
            """
        )
        spans = [span for span in data["objects"][0]["spans"] if span["text"].strip()]
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0]["text"].strip(), "Command Interface Deck")

    def test_text_with_italic_tspan(self):
        data = run_extract(
            """
            <g id="layer2" inkscape:groupmode="layer" inkscape:label="Layer 2">
              <text id="t1" x="10" y="20">
                A<tspan font-style="italic">B</tspan>
              </text>
            </g>
            """
        )
        italic_spans = [span for span in data["objects"][0]["spans"] if span["style"].get("font_style") == "italic"]
        self.assertTrue(italic_spans)

    def test_text_with_rotate_transform(self):
        data = run_extract(
            """
            <g id="layer2" inkscape:groupmode="layer" inkscape:label="Layer 2">
              <text id="t1" x="10" y="20" transform="rotate(-90)">Hello</text>
            </g>
            """
        )
        obj = data["objects"][0]
        self.assertAlmostEqual(obj["world"]["anchor_point"][0], 20.0, places=6)
        self.assertAlmostEqual(obj["world"]["anchor_point"][1], -10.0, places=6)
        self.assertAlmostEqual(obj["world"]["angle_degrees"], -90.0, places=6)

    def test_dashed_line_and_path_preserve_dasharray(self):
        data = run_extract(
            """
            <g id="layer2" inkscape:groupmode="layer" inkscape:label="Layer 2">
              <line id="ln1" x1="0" y1="0" x2="10" y2="10" stroke-dasharray="2, 1" />
              <path id="p1" d="M 0 0 L 5 5 L 10 0" stroke-dasharray="1 1" />
            </g>
            """
        )
        self.assertEqual(data["objects"][0]["style"]["stroke_dasharray_values"], [2.0, 1.0])
        self.assertEqual(data["objects"][1]["style"]["stroke_dasharray_values"], [1.0, 1.0])
        self.assertEqual(data["objects"][1]["local"]["points"], [[0.0, 0.0], [5.0, 5.0], [10.0, 0.0]])
        self.assertFalse(data["objects"][1]["local"]["path_was_flattened"])

    def test_cubic_path_produces_sampled_points(self):
        data = run_extract(
            """
            <g id="layer2" inkscape:groupmode="layer" inkscape:label="Layer 2">
              <path id="p1" d="M 0,0 C 10,0 10,10 20,10" />
            </g>
            """
        )
        obj = data["objects"][0]
        self.assertGreater(len(obj["local"]["points"]), 2)
        self.assertEqual(obj["local"]["points"][0], [0.0, 0.0])
        self.assertEqual(obj["local"]["points"][-1], [20.0, 10.0])
        self.assertTrue(obj["local"]["path_was_flattened"])
        self.assertEqual(obj["local"]["curve_segments"], 16)

    def test_quadratic_path_produces_sampled_points(self):
        data = run_extract(
            """
            <g id="layer2" inkscape:groupmode="layer" inkscape:label="Layer 2">
              <path id="p1" d="M 0,0 Q 10,20 20,0" />
            </g>
            """
        )
        obj = data["objects"][0]
        self.assertGreater(len(obj["local"]["points"]), 2)
        self.assertEqual(obj["local"]["points"][0], [0.0, 0.0])
        self.assertEqual(obj["local"]["points"][-1], [20.0, 0.0])

    def test_curve_segments_option_changes_sampling_density(self):
        data = run_extract(
            """
            <g id="layer2" inkscape:groupmode="layer" inkscape:label="Layer 2">
              <path id="p1" d="M 0,0 C 10,0 10,10 20,10" />
            </g>
            """,
            flags={"curve_segments": 4},
        )
        obj = data["objects"][0]
        self.assertEqual(len(obj["local"]["points"]), 5)
        self.assertEqual(obj["local"]["curve_segments"], 4)

    def test_arc_path_reports_warning(self):
        data = run_extract(
            """
            <g id="layer2" inkscape:groupmode="layer" inkscape:label="Layer 2">
              <path id="p1" d="M 0,0 A 10,10 0 0 1 20,0" />
            </g>
            """
        )
        self.assertIn("unsupported path arc command", data["warnings"])
        self.assertNotIn("points", data["objects"][0]["local"])

    def test_hidden_object_skipped_by_default(self):
        data = run_extract(
            """
            <g id="layer2" inkscape:groupmode="layer" inkscape:label="Layer 2">
              <rect id="hidden" x="1" y="1" width="2" height="3" style="display:none" />
            </g>
            """
        )
        self.assertEqual(data["objects"], [])

    def test_hidden_object_included_with_flag(self):
        data = run_extract(
            """
            <g id="layer2" inkscape:groupmode="layer" inkscape:label="Layer 2">
              <rect id="hidden" x="1" y="1" width="2" height="3" style="display:none" />
            </g>
            """,
            flags={"include_hidden": True},
        )
        self.assertEqual(len(data["objects"]), 1)

    def test_annotation_layers_go_to_annotations_by_default(self):
        data = run_extract(
            """
            <g id="layer_grid" inkscape:groupmode="layer" inkscape:label="Layer 1: grid/reference">
              <rect id="grid1" x="0" y="0" width="20" height="20" />
            </g>
            <g id="layer_draw" inkscape:groupmode="layer" inkscape:label="Layer 2: schematic objects">
              <rect id="draw1" x="10" y="20" width="30" height="40" inkscape:label="button.main" />
            </g>
            <g id="layer_anno" inkscape:groupmode="layer" inkscape:label="Layer 3: annotations">
              <rect id="anno1" x="50" y="60" width="70" height="80" inkscape:label="region.command_entries" />
            </g>
            """
        )
        self.assertEqual([item["svg_id"] for item in data["objects"]], ["draw1"])
        self.assertEqual([item["svg_id"] for item in data["annotations"]], ["anno1"])
        self.assertEqual(data["annotations"][0]["annotation"]["kind"], "region")
        self.assertEqual(data["annotations"][0]["annotation"]["name"], "command_entries")
        self.assertEqual(data["annotations"][0]["annotation"]["raw_label"], "region.command_entries")
        self.assertEqual(data["annotations"][0]["inkscape_label"], "region.command_entries")
        self.assertEqual([layer["role"] for layer in data["layers"]], ["reference", "drawable", "annotation"])

    def test_annotation_without_region_label_is_unknown(self):
        data = run_extract(
            """
            <g id="layer2" inkscape:groupmode="layer" inkscape:label="annotations">
              <rect id="anno1" x="1" y="2" width="3" height="4" inkscape:label="helper.box" />
            </g>
            """
        )
        self.assertEqual(data["objects"], [])
        self.assertEqual(data["annotations"][0]["annotation"]["kind"], "unknown")
        self.assertIsNone(data["annotations"][0]["annotation"]["name"])
        self.assertEqual(data["annotations"][0]["annotation"]["raw_label"], "helper.box")

    def test_reference_layers_are_skipped_by_default(self):
        data = run_extract(
            """
            <g id="layer_ref" inkscape:groupmode="layer" inkscape:label="grid/reference">
              <rect id="grid1" x="0" y="0" width="20" height="20" />
            </g>
            <g id="layer_draw" inkscape:groupmode="layer" inkscape:label="schematic">
              <rect id="draw1" x="10" y="20" width="30" height="40" />
            </g>
            """
        )
        self.assertEqual([item["svg_id"] for item in data["objects"]], ["draw1"])
        self.assertEqual(data["annotations"], [])

    def test_include_reference_layers_puts_reference_objects_in_objects(self):
        data = run_extract(
            """
            <g id="layer_ref" inkscape:groupmode="layer" inkscape:label="grid/reference">
              <rect id="grid1" x="0" y="0" width="20" height="20" />
            </g>
            """,
            flags={"include_reference_layers": True},
        )
        self.assertEqual([item["svg_id"] for item in data["objects"]], ["grid1"])

    def test_annotations_as_objects_routes_annotation_layer_into_objects(self):
        data = run_extract(
            """
            <g id="layer_anno" inkscape:groupmode="layer" inkscape:label="annotations">
              <rect id="anno1" x="1" y="2" width="3" height="4" inkscape:label="region.demo" />
            </g>
            """,
            flags={"annotations_as_objects": True},
        )
        self.assertEqual([item["svg_id"] for item in data["objects"]], ["anno1"])
        self.assertEqual(data["annotations"], [])
        self.assertEqual(data["objects"][0]["annotation"]["name"], "demo")

    def test_no_annotations_skips_annotation_layer_objects(self):
        data = run_extract(
            """
            <g id="layer_anno" inkscape:groupmode="layer" inkscape:label="annotations">
              <rect id="anno1" x="1" y="2" width="3" height="4" inkscape:label="region.demo" />
            </g>
            """,
            flags={"no_annotations": True},
        )
        self.assertEqual(data["objects"], [])
        self.assertEqual(data["annotations"], [])
