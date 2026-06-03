import json
from pathlib import Path


def convert_extracted_file_to_flow(path):
    input_path = Path(path)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    return convert_extracted_data_to_flow(data)


def convert_extracted_data_to_flow(data):
    layers_by_key = {}
    ordered_keys = []

    for layer in data.get("layers", []):
        role = "annotation" if layer.get("role") == "annotation" else "presentation"
        key = _layer_key(layer)
        if key not in layers_by_key:
            layers_by_key[key] = _make_flow_layer(layer, role)
            ordered_keys.append(key)

    for obj in data.get("objects", []):
        layer = obj.get("layer") or {}
        key = _layer_key(layer)
        if key not in layers_by_key:
            layers_by_key[key] = _make_flow_layer(layer, "presentation")
            ordered_keys.append(key)
        item = _convert_presentation_item(obj)
        if item is not None:
            layers_by_key[key]["items"].append(item)

    for obj in data.get("annotations", []):
        layer = obj.get("layer") or {}
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
        if layer["items"]:
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
        if role == "annotation":
            for region in layer.get("regions", []):
                annotations.append(_annotation_region_to_preview_object(region, layer))
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


def _make_flow_layer(layer, role):
    output = {
        "name": layer.get("label") or layer.get("id") or "Unnamed Layer",
        "role": role,
    }
    if role == "annotation":
        output["regions"] = []
    else:
        output["items"] = []
    return output


def _layer_key(layer):
    return (layer.get("id"), layer.get("label"), layer.get("role"))


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
