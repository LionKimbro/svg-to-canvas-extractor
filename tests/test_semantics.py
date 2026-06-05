from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from svg2canvasx.semantics import format_semantics_data
from svg2canvasx.semantics import format_semantics_json


class SemanticsTests(unittest.TestCase):
    def test_extracted_semantics_lists_layers_and_region_names(self):
        data = {
            "layers": [
                {"id": "layer1", "label": "grid/reference", "role": "comment"},
                {"id": "layer2", "label": "schematic objects", "role": "presentation"},
                {"id": "layer3", "label": "annotations", "role": "annotation"},
            ],
            "annotations": [
                {
                    "layer": "layer3",
                    "inkscape_label": "region.buttons",
                    "annotation": {"kind": "region", "name": "buttons"},
                },
                {
                    "layer": "layer3",
                    "inkscape_label": "command.1.name",
                    "annotation": {"kind": "unknown", "name": None},
                },
            ],
        }
        brief = format_semantics_data(data)
        self.assertEqual(
            brief,
            {
                "layers": [
                    {"name": "grid/reference", "role": "comment"},
                    {"name": "schematic objects", "role": "presentation"},
                    {
                        "name": "annotations",
                        "role": "annotation",
                        "annotations": ["region.buttons", "command.1.name"],
                        "regions": ["buttons"],
                    },
                ]
            },
        )

    def test_flow_semantics_lists_annotation_region_names(self):
        data = {
            "format": "svg2canvasx-flow",
            "layers": [
                {"name": "schematic objects", "role": "presentation", "items": []},
                {
                    "name": "annotations",
                    "role": "annotation",
                    "regions": [
                        {"label": "region.buttons", "name": "buttons"},
                        {"label": "command.1.name"},
                    ],
                },
            ],
        }
        brief = format_semantics_data(data)
        self.assertEqual(
            brief,
            {
                "layers": [
                    {"name": "schematic objects", "role": "presentation"},
                    {
                        "name": "annotations",
                        "role": "annotation",
                        "annotations": ["region.buttons", "command.1.name"],
                        "regions": ["buttons"],
                    },
                ]
            },
        )

    def test_semantics_json_defaults_to_compact_json(self):
        data = {
            "layers": [
                {"label": "schematic objects", "role": "presentation"},
            ],
            "annotations": [],
        }
        self.assertEqual(
            format_semantics_json(data),
            '{"layers": [{"name": "schematic objects", "role": "presentation"}]}',
        )
