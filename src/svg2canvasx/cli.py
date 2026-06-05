import argparse

from .extract import extract_svg_file
from .flow import convert_extracted_file_to_flow
from .flow import generate_rawtkinter_source
from .flow import load_flow_file
from .output import write_json_file
from .preview import preview_json_file
from .semantics import format_semantics_data
from .semantics import format_semantics_file


LAYOUT_HELP_TEXT = """svg2canvasx Inkscape Layout Conventions

svg2canvasx is intentionally Inkscape-oriented.
It uses explicit bracket tags in Inkscape layer labels and object labels during extraction.

Layer tags:
  [comment]   ignored/skipped by default
  [visual]    extracted as presentation items
  [annotate]  extracted as annotation regions

Object tags:
  [region]    object is rendered normally and also creates an annotation region from its bbox

Example layer setup:
  [comment] grid/reference
  [visual] schematic objects
  [annotate] semantic regions

Example object label on visual layer:
  command.1.entry [region]

Meaning:
  The object is rendered normally and also creates an annotation region using its bbox.

Annotation layer labels:
  region.command_entries
  command.1.name
  command.2.arg.1.applicable

Preview behavior:
  preview renders objects[] by default
  preview --show-annotations renders annotations as diagnostic overlays
"""


def build_parser():
    parser = argparse.ArgumentParser(prog="svg2canvasx")
    subparsers = parser.add_subparsers(dest="command")

    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("input_svg")
    extract_parser.add_argument("-o", "--output", required=True)
    extract_parser.add_argument("--pretty", action="store_true")
    extract_parser.add_argument("--debug", action="store_true")
    extract_parser.add_argument("--curve-segments", type=int, default=16)

    preview_parser = subparsers.add_parser("preview")
    preview_parser.add_argument("input_json")
    preview_parser.add_argument("--width", type=int)
    preview_parser.add_argument("--height", type=int)
    preview_parser.add_argument("--scale", type=float, default=1.0)
    preview_parser.add_argument("--font-scale", type=float, default=0.75)
    preview_parser.add_argument("--show-bboxes", action="store_true")
    preview_parser.add_argument("--show-ids", action="store_true")
    preview_parser.add_argument("--show-annotations", action="store_true")

    flow_parser = subparsers.add_parser("flow")
    flow_parser.add_argument("input_json")
    flow_parser.add_argument("-o", "--output", required=True)
    flow_parser.add_argument("--pretty", action="store_true")

    rawtkinter_parser = subparsers.add_parser("rawtkinter")
    rawtkinter_parser.add_argument("input_json")
    rawtkinter_parser.add_argument("-o", "--output", required=True)

    semantics_parser = subparsers.add_parser("semantics")
    semantics_parser.add_argument("input_json")
    semantics_parser.add_argument("-o", "--output")
    semantics_parser.add_argument("--pretty", action="store_true")

    subparsers.add_parser(
        "help-layout",
        help="show Inkscape layout and annotation conventions",
        description="Print the Inkscape authoring conventions understood by svg2canvasx.",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "extract":
        data = extract_svg_file(
            args.input_svg,
            debug=args.debug,
            curve_segments=args.curve_segments,
        )
        write_json_file(args.output, data, pretty=args.pretty)
        return 0

    if args.command == "preview":
        preview_json_file(
            args.input_json,
            width=args.width,
            height=args.height,
            scale=args.scale,
            font_scale=args.font_scale,
            show_bboxes=args.show_bboxes,
            show_ids=args.show_ids,
            show_annotations=args.show_annotations,
        )
        return 0

    if args.command == "flow":
        data = convert_extracted_file_to_flow(args.input_json)
        write_json_file(args.output, data, pretty=args.pretty)
        return 0

    if args.command == "rawtkinter":
        data = load_flow_file(args.input_json)
        source = generate_rawtkinter_source(data)
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(source)
        return 0

    if args.command == "semantics":
        if args.output:
            with open(args.input_json, "r", encoding="utf-8") as handle:
                import json
                input_data = json.load(handle)
            write_json_file(args.output, format_semantics_data(input_data), pretty=args.pretty)
        else:
            print(format_semantics_file(args.input_json, pretty=args.pretty))
        return 0

    if args.command == "help-layout":
        print(LAYOUT_HELP_TEXT)
        return 0

    parser.print_help()
    return 1
