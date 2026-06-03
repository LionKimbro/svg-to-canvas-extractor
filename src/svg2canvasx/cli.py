import argparse

from .extract import extract_svg_file
from .flow import convert_extracted_file_to_flow
from .output import write_json_file
from .preview import preview_json_file


LAYOUT_HELP_TEXT = """svg2canvasx Inkscape Layout Conventions

svg2canvasx is intentionally Inkscape-oriented.
It uses Inkscape layer labels and inkscape:label values as authoring conventions during extraction.

Layer labels:
  contains "grid" or "reference"      skipped by default
  contains "annotation"               extracted into JSON annotations[]
  anything else visible               extracted into JSON objects[]

Annotation labels:
  region.NAME                         semantic region rectangle
  guide.NAME                          optional guide
  note.NAME                           optional note

region.NAME annotations are interpreted generally as semantic region markers.

Example layer setup:
  Layer 1: grid/reference
  Layer 2: schematic objects
  Layer 3: annotations

Example annotation object labels:
  region.command_entries
  region.argument_entries
  region.argument_type_matrix
  region.command_argument_matrix
  region.command_descriptions
  region.argument_descriptions
  region.buttons

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
    extract_parser.add_argument("--layer", action="append", dest="layers")
    extract_parser.add_argument("--all-layers", action="store_true")
    extract_parser.add_argument("--include-reference-layers", action="store_true")
    extract_parser.add_argument("--annotations-as-objects", action="store_true")
    extract_parser.add_argument("--no-annotations", action="store_true")
    extract_parser.add_argument("--pretty", action="store_true")
    extract_parser.add_argument("--debug", action="store_true")
    extract_parser.add_argument("--include-hidden", action="store_true")
    extract_parser.add_argument("--no-world-geometry", action="store_true")
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
            layer_names=args.layers,
            extract_all_layers=args.all_layers,
            include_reference_layers=args.include_reference_layers,
            annotations_as_objects=args.annotations_as_objects,
            no_annotations=args.no_annotations,
            include_hidden=args.include_hidden,
            include_world_geometry=not args.no_world_geometry,
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

    if args.command == "help-layout":
        print(LAYOUT_HELP_TEXT)
        return 0

    parser.print_help()
    return 1
