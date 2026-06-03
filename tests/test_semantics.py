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
                {"id": "layer1", "label": "Layer 1: grid/reference", "role": "reference"},
                {"id": "layer2", "label": "Layer 2: schematic objects", "role": "presentation"},
                {"id": "layer3", "label": "Layer 3: annotations", "role": "annotation"},
            ],
            "annotations": [
                {
                    "layer": {"label": "Layer 3: annotations", "role": "annotation"},
                    "inkscape_label": "region.buttons",
                    "annotation": {"kind": "region", "name": "buttons"},
                },
                {
                    "layer": {"label": "Layer 3: annotations", "role": "annotation"},
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
                    {"name": "Layer 1: grid/reference", "role": "reference"},
                    {"name": "Layer 2: schematic objects", "role": "presentation"},
                    {
                        "name": "Layer 3: annotations",
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
                {"name": "Layer 2: schematic objects", "role": "presentation", "items": []},
                {
                    "name": "Layer 3: annotations",
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
                    {"name": "Layer 2: schematic objects", "role": "presentation"},
                    {
                        "name": "Layer 3: annotations",
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
                {"label": "Layer 2: schematic objects", "role": "presentation"},
            ],
            "annotations": [],
        }
        self.assertEqual(
            format_semantics_json(data),
            '{"layers": [{"name": "Layer 2: schematic objects", "role": "presentation"}]}',
        )
