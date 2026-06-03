from pathlib import Path
import io
import sys
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

    def test_help_layout_prints_layout_conventions(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = main(["help-layout"])
        output = stream.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("svg2canvasx Inkscape Layout Conventions", output)
        self.assertIn('contains "annotation"', output)
        self.assertIn("region.command_entries", output)
        self.assertEqual(output.strip(), LAYOUT_HELP_TEXT.strip())

