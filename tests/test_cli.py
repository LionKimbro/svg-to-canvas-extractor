from pathlib import Path
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from svg2canvasx.cli import LAYOUT_HELP_TEXT
from svg2canvasx.cli import build_parser
from svg2canvasx.cli import main


class CliTests(unittest.TestCase):
    def test_help_layout_command_is_registered(self):
        parser = build_parser()
        args = parser.parse_args(["help-layout"])
        self.assertEqual(args.command, "help-layout")
        args = parser.parse_args(["rawtkinter", "input.json", "-o", "out.py"])
        self.assertEqual(args.command, "rawtkinter")

    def test_help_layout_prints_layout_conventions(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = main(["help-layout"])
        output = stream.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("svg2canvasx Inkscape Layout Conventions", output)
        self.assertIn("[annotation]", output)
        self.assertIn("command.1.entry [region]", output)
        self.assertEqual(output.strip(), LAYOUT_HELP_TEXT.strip())

    def test_rawtkinter_command_writes_draw_function(self):
        flow = {
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
                        }
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as folder:
            input_path = Path(folder) / "input.flow.json"
            output_path = Path(folder) / "draw_flow.py"
            input_path.write_text(json.dumps(flow), encoding="utf-8")
            code = main(["rawtkinter", str(input_path), "-o", str(output_path)])
            self.assertEqual(code, 0)
            source = output_path.read_text(encoding="utf-8")
            self.assertIn("def draw(canvas):", source)
            self.assertIn("canvas.create_rectangle", source)
