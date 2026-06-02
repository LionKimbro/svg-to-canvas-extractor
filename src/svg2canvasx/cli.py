import argparse

from .extract import extract_svg_file
from .output import write_json_file
from .preview import preview_json_file


def build_parser():
    parser = argparse.ArgumentParser(prog="svg2canvasx")
    subparsers = parser.add_subparsers(dest="command")

    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("input_svg")
    extract_parser.add_argument("-o", "--output", required=True)
    extract_parser.add_argument("--layer", action="append", dest="layers")
    extract_parser.add_argument("--all-layers", action="store_true")
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
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "extract":
        data = extract_svg_file(
            args.input_svg,
            layer_names=args.layers,
            extract_all_layers=args.all_layers,
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
        )
        return 0

    parser.print_help()
    return 1
