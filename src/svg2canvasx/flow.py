import json
from pathlib import Path
import tkinter


def convert_extracted_file_to_flow(path):
    input_path = Path(path)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    return convert_extracted_data_to_flow(data)


def load_flow_file(path):
    input_path = Path(path)
    return json.loads(input_path.read_text(encoding="utf-8"))


def convert_extracted_data_to_flow(data):
    layers_by_key = {}
    ordered_keys = []
    layer_index = _index_extracted_layers(data)

    for layer in data.get("layers", []):
        role = "annotation" if layer.get("role") == "annotation" else "presentation"
        key = _layer_key(layer)
        if key not in layers_by_key:
            layers_by_key[key] = _make_flow_layer(layer, role)
            ordered_keys.append(key)

    for obj in data.get("objects", []):
        layer = _resolve_extracted_layer(data, layer_index, obj.get("layer"))
        key = _layer_key(layer)
        if key not in layers_by_key:
            layers_by_key[key] = _make_flow_layer(layer, "presentation")
            ordered_keys.append(key)
        item = _convert_presentation_item(obj)
        if item is not None:
            layers_by_key[key]["items"].append(item)

    for obj in data.get("annotations", []):
        layer = _resolve_extracted_layer(data, layer_index, obj.get("layer"))
        key = _layer_key(layer)
        if key not in layers_by_key:
            layers_by_key[key] = _make_flow_layer(layer, "annotation")
            ordered_keys.append(key)
        region = _convert_annotation_region(obj)
        if region is not None:
            layers_by_key[key]["regions"].append(region)

    output_layers = []
    for key in ordered_keys:
        layer = layers_by_key[key]
        if layer["role"] == "annotation":
            if layer["regions"]:
                output_layers.append(layer)
            continue
        if layer["items"] or layer["regions"]:
            output_layers.append(layer)

    source = data.get("source") or {}
    svg = data.get("svg") or {}
    return {
        "format": "svg2canvasx-flow",
        "version": 1,
        "source": {
            "path": source.get("path"),
            "extracted_from": source.get("path"),
        },
        "canvas": {
            "width": svg.get("width"),
            "height": svg.get("height"),
            "viewBox": svg.get("viewBox"),
        },
        "layers": output_layers,
    }


def flow_to_preview_data(data):
    objects = []
    annotations = []
    canvas = data.get("canvas") or {}
    for layer in data.get("layers", []):
        role = layer.get("role")
        for region in layer.get("regions", []):
            annotations.append(_annotation_region_to_preview_object(region, layer))
        if role == "annotation":
            continue
        for item in layer.get("items", []):
            objects.append(_presentation_item_to_preview_object(item, layer))
    return {
        "svg": {
            "width": canvas.get("width"),
            "height": canvas.get("height"),
            "viewBox": canvas.get("viewBox"),
        },
        "objects": objects,
        "annotations": annotations,
    }


def draw_flow_on_canvas(canvas, flow_data):
    for layer in flow_data.get("layers", []):
        if layer.get("role") != "presentation":
            continue
        for item in layer.get("items", []):
            _draw_flow_item_on_canvas(canvas, item)
    return canvas


def create_canvas_for_flow(parent, flow_data):
    canvas_info = flow_data.get("canvas") or {}
    width = _safe_int(canvas_info.get("width")) or 1100
    height = _safe_int(canvas_info.get("height")) or 900
    canvas = tkinter.Canvas(parent, width=width, height=height, background="white")
    canvas.pack(fill="both", expand=True)
    draw_flow_on_canvas(canvas, flow_data)
    return canvas


def create_toplevel_for_flow(root, flow_data):
    window = tkinter.Toplevel(root)
    canvas = create_canvas_for_flow(window, flow_data)
    return {
        "toplevel": window,
        "canvas": canvas,
    }


def generate_rawtkinter_source(flow_data):
    lines = [
        "def draw(canvas):",
        '    """Draw a svg2canvasx flow document onto an existing Tkinter Canvas."""',
    ]
    body_lines = []
    for layer in flow_data.get("layers", []):
        if layer.get("role") != "presentation":
            continue
        layer_name = layer.get("name") or "Unnamed Layer"
        body_lines.append(f"    # Layer: {layer_name}")
        for item in layer.get("items", []):
            body_lines.extend(_rawtkinter_lines_for_item(item))
    if not body_lines:
        body_lines.append("    return canvas")
    else:
        body_lines.append("    return canvas")
    lines.extend(body_lines)
    lines.append("")
    return "\n".join(lines)


def _make_flow_layer(layer, role):
    output = {
        "name": layer.get("label") or layer.get("uid") or layer.get("svg_id") or layer.get("id") or "Unnamed Layer",
        "role": role,
        "regions": [],
    }
    if role != "annotation":
        output["items"] = []
    return output


def _layer_key(layer):
    return (layer.get("uid"), layer.get("svg_id"), layer.get("id"), layer.get("label"), layer.get("role"))


def _index_extracted_layers(data):
    output = {}
    for layer in data.get("layers", []):
        for key in (layer.get("uid"), layer.get("svg_id"), layer.get("id")):
            if key is not None:
                output[key] = layer
    return output


def _resolve_extracted_layer(data, layer_index, layer_ref):
    if isinstance(layer_ref, dict):
        return layer_ref
    if layer_ref is not None and layer_ref in layer_index:
        return layer_index[layer_ref]
    if layer_ref is not None:
        return {"uid": layer_ref}
    return {}


def _convert_presentation_item(obj):
    kind = obj.get("kind")
    label = _choose_label(obj)
    if kind == "rect":
        world = obj.get("world") or {}
        item = {
            "kind": "rect",
            "label": label,
            "bbox": world.get("bbox"),
            "draw": _draw_style(obj),
        }
        if world.get("points") and not _is_axis_aligned_rect_points(world.get("points")):
            item["points"] = world.get("points")
        return item
    if kind in ("line", "path", "polyline", "polygon"):
        world = obj.get("world") or {}
        item = {
            "kind": kind,
            "label": label,
            "points": world.get("points"),
            "draw": _draw_style(obj, include_fill=(kind in ("path", "polygon"))),
        }
        if kind == "polygon":
            item["closed"] = True
        elif obj.get("closed"):
            item["closed"] = bool(obj.get("closed"))
        return item
    if kind in ("circle", "ellipse"):
        world = obj.get("world") or {}
        return {
            "kind": kind,
            "label": label,
            "bbox": world.get("bbox"),
            "draw": _draw_style(obj, include_fill=True),
        }
    if kind == "text":
        style = obj.get("style") or {}
        world = obj.get("world") or {}
        layout = obj.get("text_layout") or {}
        return {
            "kind": "text",
            "label": label,
            "text": obj.get("text", ""),
            "point": world.get("anchor_point"),
            "text_style": {
                "font_family": style.get("font_family"),
                "font_size": style.get("font_size"),
                "bold": _is_bold_style(style.get("font_weight")),
                "italic": _is_italic_style(style.get("font_style")),
                "anchor": layout.get("suggested_tk_anchor"),
                "angle": world.get("angle_degrees"),
                "fill": _normalize_paint(style.get("fill")) or _normalize_paint(style.get("stroke")),
            },
        }
    return None


def _convert_annotation_region(obj):
    label = _choose_label(obj)
    annotation = obj.get("annotation") or {}
    world = obj.get("world") or {}
    bbox = world.get("bbox")
    if not bbox:
        return None
    shape = "rect" if obj.get("kind") == "rect" else "bbox"
    return {
        "label": label,
        "name": _annotation_name(label, annotation),
        "shape": shape,
        "bbox": bbox,
        "source": annotation.get("source"),
    }


def _draw_style(obj, include_fill=False):
    style = obj.get("style") or {}
    draw = {
        "stroke": _normalize_paint(style.get("stroke")),
        "stroke_width": style.get("stroke_width"),
        "dash": style.get("stroke_dasharray_values"),
    }
    if include_fill or obj.get("kind") == "rect":
        draw["fill"] = _normalize_paint(style.get("fill"))
    return draw


def _normalize_paint(value):
    if value in (None, "", "none"):
        return None
    return value


def _choose_label(obj):
    for key in ("inkscape_label", "label", "svg_id"):
        value = obj.get(key)
        if value is not None and str(value).strip():
            return value
    return None


def _annotation_name(label, annotation):
    if annotation.get("name") is not None:
        return annotation.get("name")
    if label and label.startswith("region."):
        return label.split(".", 1)[1] or None
    return None


def _is_bold_style(value):
    if value is None:
        return False
    text = str(value).strip().lower()
    if text == "bold":
        return True
    try:
        return float(text) >= 700.0
    except ValueError:
        return False


def _is_italic_style(value):
    if value is None:
        return False
    return str(value).strip().lower() in ("italic", "oblique")


def _is_axis_aligned_rect_points(points):
    if not points or len(points) != 4:
        return False
    x_values = sorted({round(point[0], 6) for point in points})
    y_values = sorted({round(point[1], 6) for point in points})
    return len(x_values) == 2 and len(y_values) == 2


def _presentation_item_to_preview_object(item, layer):
    kind = item.get("kind")
    label = item.get("label")
    draw = item.get("draw") or {}
    base = {
        "uid": label or kind,
        "svg_id": label,
        "kind": kind,
        "layer": {"label": layer.get("name"), "role": layer.get("role")},
        "style": _preview_style_from_draw(draw),
    }
    if label is not None:
        base["label"] = label
        base["inkscape_label"] = label
    if kind in ("rect", "circle", "ellipse"):
        bbox = item.get("bbox")
        base["world"] = {"bbox": bbox}
        if kind == "rect":
            if item.get("points"):
                base["world"]["points"] = item.get("points")
                base["world"]["matrix"] = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
            else:
                x0, y0, x1, y1 = bbox
                base["world"]["points"] = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
                base["world"]["matrix"] = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        return base
    if kind in ("line", "path", "polyline", "polygon"):
        points = item.get("points") or []
        base["world"] = {"points": points}
        if points:
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            base["world"]["bbox"] = [min(xs), min(ys), max(xs), max(ys)]
        if item.get("closed") is not None:
            base["closed"] = item.get("closed")
        return base
    if kind == "text":
        text_style = item.get("text_style") or {}
        base["text"] = item.get("text", "")
        base["world"] = {
            "anchor_point": item.get("point"),
            "angle_degrees": text_style.get("angle") or 0.0,
        }
        base["style"] = {
            "font_family": text_style.get("font_family"),
            "font_size": text_style.get("font_size"),
            "font_weight": "bold" if text_style.get("bold") else None,
            "font_style": "italic" if text_style.get("italic") else None,
            "fill": text_style.get("fill"),
            "stroke": None,
        }
        base["text_layout"] = {
            "suggested_tk_anchor": text_style.get("anchor") or "sw",
        }
        return base
    return base


def _annotation_region_to_preview_object(region, layer):
    bbox = region.get("bbox")
    x0, y0, x1, y1 = bbox
    label = region.get("label")
    return {
        "uid": label or "region",
        "svg_id": label,
        "kind": "rect",
        "layer": {"label": layer.get("name"), "role": layer.get("role")},
        "label": label,
        "inkscape_label": label,
        "annotation": {
            "kind": "region" if region.get("name") is not None else "unknown",
            "name": region.get("name"),
            "raw_label": label,
        },
        "style": {
            "fill": None,
            "stroke": None,
            "stroke_width": 1.0,
        },
        "world": {
            "bbox": bbox,
            "points": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
            "matrix": [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
        },
    }


def _preview_style_from_draw(draw):
    return {
        "fill": draw.get("fill"),
        "stroke": draw.get("stroke"),
        "stroke_width": draw.get("stroke_width"),
        "stroke_dasharray_values": draw.get("dash"),
    }


def _draw_flow_item_on_canvas(canvas, item):
    kind = item.get("kind")
    if kind == "rect":
        _draw_flow_rect(canvas, item)
        return
    if kind in ("line", "path", "polyline"):
        _draw_flow_line_like(canvas, item)
        return
    if kind == "polygon":
        _draw_flow_polygon(canvas, item)
        return
    if kind in ("circle", "ellipse"):
        _draw_flow_ellipse(canvas, item)
        return
    if kind == "text":
        _draw_flow_text(canvas, item)
        return


def _draw_flow_rect(canvas, item):
    draw = item.get("draw") or {}
    if item.get("points"):
        canvas.create_polygon(
            _flatten_points(item.get("points") or []),
            fill=_tk_fill(draw.get("fill")),
            outline=_tk_paint(draw.get("stroke")),
            width=_tk_width(draw.get("stroke_width")),
            dash=_tk_dash(draw.get("dash")),
        )
        return
    bbox = item.get("bbox") or [0.0, 0.0, 0.0, 0.0]
    canvas.create_rectangle(
        bbox[0],
        bbox[1],
        bbox[2],
        bbox[3],
        fill=_tk_fill(draw.get("fill")),
        outline=_tk_paint(draw.get("stroke")),
        width=_tk_width(draw.get("stroke_width")),
        dash=_tk_dash(draw.get("dash")),
    )


def _draw_flow_line_like(canvas, item):
    draw = item.get("draw") or {}
    canvas.create_line(
        _flatten_points(item.get("points") or []),
        fill=_tk_paint(draw.get("stroke")),
        width=_tk_width(draw.get("stroke_width")),
        dash=_tk_dash(draw.get("dash")),
        smooth=False,
    )


def _draw_flow_polygon(canvas, item):
    draw = item.get("draw") or {}
    canvas.create_polygon(
        _flatten_points(item.get("points") or []),
        fill=_tk_fill(draw.get("fill")),
        outline=_tk_paint(draw.get("stroke")),
        width=_tk_width(draw.get("stroke_width")),
        dash=_tk_dash(draw.get("dash")),
    )


def _draw_flow_ellipse(canvas, item):
    bbox = item.get("bbox") or [0.0, 0.0, 0.0, 0.0]
    draw = item.get("draw") or {}
    canvas.create_oval(
        bbox[0],
        bbox[1],
        bbox[2],
        bbox[3],
        fill=_tk_fill(draw.get("fill")),
        outline=_tk_paint(draw.get("stroke")),
        width=_tk_width(draw.get("stroke_width")),
        dash=_tk_dash(draw.get("dash")),
    )


def _draw_flow_text(canvas, item):
    text_style = item.get("text_style") or {}
    canvas.create_text(
        (item.get("point") or [0.0, 0.0])[0],
        (item.get("point") or [0.0, 0.0])[1],
        text=item.get("text", ""),
        anchor=text_style.get("anchor") or "sw",
        angle=-(float(text_style.get("angle") or 0.0)),
        font=_tk_font_spec(text_style),
        fill=_tk_paint(text_style.get("fill")) or "black",
    )


def _tk_fill(value):
    return "" if value in (None, "", "none") else value


def _tk_paint(value):
    return "" if value in (None, "", "none") else value


def _tk_width(value):
    if value is None:
        return 1.0
    return max(1.0, float(value))


def _tk_dash(values):
    if not values:
        return None
    return tuple(max(1, int(round(float(value)))) for value in values)


def _tk_font_spec(text_style):
    family = text_style.get("font_family") or "Arial"
    size = max(1, int(round(float(text_style.get("font_size") or 12.0) * 0.75)))
    modifiers = []
    if text_style.get("bold"):
        modifiers.append("bold")
    if text_style.get("italic"):
        modifiers.append("italic")
    if modifiers:
        return (family, size, " ".join(modifiers))
    return (family, size)


def _flatten_points(points):
    output = []
    for point in points or []:
        output.extend(point)
    return output


def _safe_int(value):
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except Exception:
        return None


def _rawtkinter_lines_for_item(item):
    kind = item.get("kind")
    label = item.get("label")
    lines = []
    if label:
        lines.append(f"    # {label}")
    if kind == "rect":
        lines.append(_rawtkinter_rect_call(item))
        return lines
    if kind in ("line", "path", "polyline"):
        lines.append(_rawtkinter_line_call(item))
        return lines
    if kind == "polygon":
        lines.append(_rawtkinter_polygon_call(item))
        return lines
    if kind in ("circle", "ellipse"):
        lines.append(_rawtkinter_oval_call(item))
        return lines
    if kind == "text":
        lines.append(_rawtkinter_text_call(item))
        return lines
    lines.append(f"    # Unsupported item kind skipped: {kind!r}")
    return lines


def _rawtkinter_rect_call(item):
    draw = item.get("draw") or {}
    kwargs = _raw_kwargs(
        fill=_tk_fill(draw.get("fill")),
        outline=_tk_paint(draw.get("stroke")),
        width=_tk_width(draw.get("stroke_width")),
        dash=_tk_dash(draw.get("dash")),
    )
    if item.get("points"):
        return f"    canvas.create_polygon({_py(_flatten_points(item.get('points') or []))}, {kwargs})"
    bbox = item.get("bbox") or [0.0, 0.0, 0.0, 0.0]
    return f"    canvas.create_rectangle({bbox[0]!r}, {bbox[1]!r}, {bbox[2]!r}, {bbox[3]!r}, {kwargs})"


def _rawtkinter_line_call(item):
    draw = item.get("draw") or {}
    kwargs = _raw_kwargs(
        fill=_tk_paint(draw.get("stroke")),
        width=_tk_width(draw.get("stroke_width")),
        dash=_tk_dash(draw.get("dash")),
        smooth=False,
    )
    return f"    canvas.create_line({_py(_flatten_points(item.get('points') or []))}, {kwargs})"


def _rawtkinter_polygon_call(item):
    draw = item.get("draw") or {}
    kwargs = _raw_kwargs(
        fill=_tk_fill(draw.get("fill")),
        outline=_tk_paint(draw.get("stroke")),
        width=_tk_width(draw.get("stroke_width")),
        dash=_tk_dash(draw.get("dash")),
    )
    return f"    canvas.create_polygon({_py(_flatten_points(item.get('points') or []))}, {kwargs})"


def _rawtkinter_oval_call(item):
    draw = item.get("draw") or {}
    kwargs = _raw_kwargs(
        fill=_tk_fill(draw.get("fill")),
        outline=_tk_paint(draw.get("stroke")),
        width=_tk_width(draw.get("stroke_width")),
        dash=_tk_dash(draw.get("dash")),
    )
    bbox = item.get("bbox") or [0.0, 0.0, 0.0, 0.0]
    return f"    canvas.create_oval({bbox[0]!r}, {bbox[1]!r}, {bbox[2]!r}, {bbox[3]!r}, {kwargs})"


def _rawtkinter_text_call(item):
    text_style = item.get("text_style") or {}
    point = item.get("point") or [0.0, 0.0]
    kwargs = _raw_kwargs(
        text=item.get("text", ""),
        anchor=text_style.get("anchor") or "sw",
        angle=-(float(text_style.get("angle") or 0.0)),
        font=_tk_font_spec(text_style),
        fill=_tk_paint(text_style.get("fill")) or "black",
    )
    return f"    canvas.create_text({point[0]!r}, {point[1]!r}, {kwargs})"


def _raw_kwargs(**kwargs):
    parts = []
    for key, value in kwargs.items():
        parts.append(f"{key}={_py(value)}")
    return ", ".join(parts)


def _py(value):
    return repr(value)
