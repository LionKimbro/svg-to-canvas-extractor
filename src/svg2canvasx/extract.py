from pathlib import Path

from .geometry import bbox_from_points
from .geometry import clean_number
from .geometry import clean_point
from .geometry import flatten_path
from .geometry import parse_points
from .geometry import rect_points
from .geometry import transform_points
from .styles import build_style
from .styles import empty_style
from .styles import is_visible
from .styles import parse_number
from .styles import style_to_output
from .svgparse import get_inkscape_label
from .svgparse import get_layer_info
from .svgparse import get_node_id
from .svgparse import get_svg_meta
from .svgparse import is_layer
from .svgparse import load_svg
from .svgparse import local_name
from .svgparse import normalize_source_path
from .svgparse import parse_label_metadata
from .transforms import apply_matrix
from .transforms import copy_matrix
from .transforms import extract_rotation_angle
from .transforms import kIDENTITY_MATRIX
from .transforms import multiply_matrices
from .transforms import parse_transform_list


def extract_svg_file(
    path,
    debug=False,
    curve_segments=16,
):
    warnings = []
    root = load_svg(path)
    svg_meta = get_svg_meta(root, warnings)
    state = {
        "warnings": warnings,
        "objects": [],
        "annotations": [],
        "layers": [],
        "uid_counter": 0,
        "layer_uid_counter": 0,
        "layer_uid_by_node": {},
        "debug": debug,
        "curve_segments": curve_segments,
    }

    layers = _discover_layers(root, state)
    state["layers"] = [_copy_layer(layer) for layer in layers]

    walk_node(
        root,
        state,
        copy_matrix(kIDENTITY_MATRIX),
        empty_style(),
        None,
        [],
    )

    return {
        "source": {
            "path": normalize_source_path(path),
            "generator": "svg2canvasx",
            "stage": 1,
        },
        "svg": svg_meta,
        "layers": state["layers"],
        "objects": state["objects"],
        "annotations": state["annotations"],
        "warnings": warnings,
    }


def walk_node(node, state, parent_matrix, parent_style, layer_info, groups):
    name = local_name(node.tag)
    style = build_style(node, parent_style, state["warnings"])
    if not is_visible(style):
        return

    local_matrix = parse_transform_list(node.get("transform"), state["warnings"])
    world_matrix = multiply_matrices(parent_matrix, local_matrix)
    current_layer = layer_info
    current_groups = list(groups)

    if name == "svg":
        for child in list(node):
            walk_node(child, state, world_matrix, style, current_layer, current_groups)
        return

    if name == "g":
        if is_layer(node):
            current_layer = _register_layer_info(node, get_layer_info(node, state["warnings"]), state)
            if not _layer_is_walkable(current_layer, state):
                return
        else:
            current_groups = current_groups + [_group_info(node)]
        for child in list(node):
            walk_node(child, state, world_matrix, style, current_layer, current_groups)
        return

    if current_layer is None:
        return

    if name == "rect":
        obj = extract_rect(node, current_layer, current_groups, style, world_matrix, state)
        _push_object(state, obj)
        return
    if name == "line":
        obj = extract_line(node, current_layer, current_groups, style, world_matrix, state)
        _push_object(state, obj)
        return
    if name in ("polyline", "polygon"):
        obj = extract_poly(node, current_layer, current_groups, style, world_matrix, state, name)
        _push_object(state, obj)
        return
    if name == "path":
        obj = extract_path(node, current_layer, current_groups, style, world_matrix, state)
        _push_object(state, obj)
        return
    if name == "text":
        obj = extract_text(node, current_layer, current_groups, style, world_matrix, state)
        _push_object(state, obj)
        return
    if name in ("circle", "ellipse"):
        obj = extract_ellipse_like(node, current_layer, current_groups, style, world_matrix, state, name)
        _push_object(state, obj)
        return
    if name == "tspan":
        return

    state["warnings"].append("unsupported element kind: " + name)


def extract_rect(node, layer_info, groups, style, world_matrix, state):
    x_value = _num(node, "x", state)
    y_value = _num(node, "y", state)
    width = _num(node, "width", state)
    height = _num(node, "height", state)
    rx_value = _num(node, "rx", state, optional=True)
    ry_value = _num(node, "ry", state, optional=True)
    local_points = rect_points(x_value, y_value, width, height)
    local_bbox = [x_value, y_value, x_value + width, y_value + height]
    world_points = transform_points(world_matrix, local_points)
    world_bbox = bbox_from_points(world_points)
    obj = _base_object(node, "rect", layer_info, groups, style, world_matrix, state)
    obj["local"] = {
        "x": x_value,
        "y": y_value,
        "width": width,
        "height": height,
        "rx": rx_value,
        "ry": ry_value,
        "bbox": local_bbox,
    }
    obj["world"] = {
        "matrix": _clean_matrix(world_matrix),
        "points": world_points,
        "bbox": world_bbox,
    }
    return obj


def extract_line(node, layer_info, groups, style, world_matrix, state):
    x1_value = _num(node, "x1", state)
    y1_value = _num(node, "y1", state)
    x2_value = _num(node, "x2", state)
    y2_value = _num(node, "y2", state)
    world_points = transform_points(world_matrix, [[x1_value, y1_value], [x2_value, y2_value]])
    obj = _base_object(node, "line", layer_info, groups, style, world_matrix, state)
    obj["local"] = {
        "x1": x1_value,
        "y1": y1_value,
        "x2": x2_value,
        "y2": y2_value,
    }
    obj["world"] = {
        "matrix": _clean_matrix(world_matrix),
        "points": world_points,
        "bbox": bbox_from_points(world_points),
    }
    return obj


def extract_poly(node, layer_info, groups, style, world_matrix, state, name):
    local_points = parse_points(node.get("points", ""), state["warnings"])
    world_points = transform_points(world_matrix, local_points)
    obj = _base_object(node, name, layer_info, groups, style, world_matrix, state)
    obj["closed"] = name == "polygon"
    obj["local"] = {
        "points": local_points,
        "bbox": bbox_from_points(local_points),
    }
    obj["world"] = {
        "matrix": _clean_matrix(world_matrix),
        "points": world_points,
        "bbox": bbox_from_points(world_points),
    }
    return obj


def extract_path(node, layer_info, groups, style, world_matrix, state):
    d_value = node.get("d", "")
    flat = flatten_path(d_value, state["warnings"], state["curve_segments"])
    local_points = flat.get("points")
    obj = _base_object(node, "path", layer_info, groups, style, world_matrix, state)
    obj["local"] = {
        "d": d_value,
        "path_was_flattened": flat.get("path_was_flattened", False),
        "curve_segments": state["curve_segments"],
    }
    if local_points:
        obj["local"]["points"] = local_points
        obj["local"]["bbox"] = bbox_from_points(local_points)
    world = {
        "matrix": _clean_matrix(world_matrix),
    }
    if local_points:
        world_points = transform_points(world_matrix, local_points)
        world["points"] = world_points
        world["bbox"] = bbox_from_points(world_points)
    obj["world"] = world
    return obj


def extract_text(node, layer_info, groups, style, world_matrix, state):
    spans = []
    text_value = _collect_text_spans(node, style, spans, state["warnings"])
    x_value = _num(node, "x", state, optional=True)
    y_value = _num(node, "y", state, optional=True)
    if x_value is None or y_value is None:
        for span in spans:
            local = span.get("local", {})
            if x_value is None and local.get("x") is not None:
                x_value = local.get("x")
            if y_value is None and local.get("y") is not None:
                y_value = local.get("y")
    x_value = 0.0 if x_value is None else x_value
    y_value = 0.0 if y_value is None else y_value
    anchor_point = apply_matrix(world_matrix, [x_value, y_value])
    anchor_name = _effective_text_anchor(style, spans)
    obj = _base_object(node, "text", layer_info, groups, style, world_matrix, state)
    obj["text"] = text_value
    obj["spans"] = spans
    obj["local"] = {
        "x": x_value,
        "y": y_value,
    }
    obj["world"] = {
        "matrix": _clean_matrix(world_matrix),
        "anchor_point": clean_point(anchor_point),
        "angle_degrees": clean_number(extract_rotation_angle(world_matrix)),
    }
    obj["text_layout"] = {
        "svg_text_anchor": anchor_name,
        "svg_dominant_baseline": style.get("dominant-baseline"),
        "svg_alignment_baseline": style.get("alignment-baseline"),
        "suggested_tk_anchor": _suggest_tk_anchor(anchor_name),
    }
    return obj


def extract_ellipse_like(node, layer_info, groups, style, world_matrix, state, name):
    cx_value = _num(node, "cx", state)
    cy_value = _num(node, "cy", state)
    if name == "circle":
        r_value = _num(node, "r", state)
        local_points = rect_points(cx_value - r_value, cy_value - r_value, r_value * 2.0, r_value * 2.0)
        local = {
            "cx": cx_value,
            "cy": cy_value,
            "r": r_value,
            "bbox": [cx_value - r_value, cy_value - r_value, cx_value + r_value, cy_value + r_value],
        }
    else:
        rx_value = _num(node, "rx", state)
        ry_value = _num(node, "ry", state)
        local_points = rect_points(cx_value - rx_value, cy_value - ry_value, rx_value * 2.0, ry_value * 2.0)
        local = {
            "cx": cx_value,
            "cy": cy_value,
            "rx": rx_value,
            "ry": ry_value,
            "bbox": [cx_value - rx_value, cy_value - ry_value, cx_value + rx_value, cy_value + ry_value],
        }
    world_points = transform_points(world_matrix, local_points)
    obj = _base_object(node, name, layer_info, groups, style, world_matrix, state)
    obj["local"] = local
    obj["world"] = {
        "matrix": _clean_matrix(world_matrix),
        "center": clean_point(apply_matrix(world_matrix, [cx_value, cy_value])),
        "bbox": bbox_from_points(world_points),
        "points": world_points,
    }
    return obj


def _discover_layers(root, state):
    layers = []
    for child in list(root):
        if local_name(child.tag) == "g" and is_layer(child):
            layers.append(_register_layer_info(child, get_layer_info(child, state["warnings"]), state))
    return layers


def _register_layer_info(node, layer_info, state):
    node_key = id(node)
    layer_uid = state["layer_uid_by_node"].get(node_key)
    if layer_uid is None:
        layer_uid = layer_info.get("id")
        if not layer_uid:
            state["layer_uid_counter"] += 1
            layer_uid = "auto_layer_{:05d}".format(state["layer_uid_counter"])
        state["layer_uid_by_node"][node_key] = layer_uid
    output = dict(layer_info)
    output["uid"] = layer_uid
    output["svg_id"] = layer_info.get("id")
    return output

def _layer_is_walkable(layer_info, state):
    role = (layer_info or {}).get("role")
    if role in ("presentation", "annotation"):
        return True
    return False


def _group_info(node):
    return {
        "id": get_node_id(node),
        "label": get_inkscape_label(node),
        "is_region": bool((get_node_id(node) or "").startswith("region_")),
    }


def _base_object(node, kind, layer_info, groups, style, world_matrix, state):
    state["uid_counter"] += 1
    raw_label = get_inkscape_label(node)
    label_info = parse_label_metadata(raw_label)
    output = {
        "uid": get_node_id(node) or "auto_{:05d}".format(state["uid_counter"]),
        "svg_id": get_node_id(node),
        "kind": kind,
        "layer": _layer_id(layer_info),
        "_layer_role": (layer_info or {}).get("role"),
        "groups": [_copy_group(item) for item in groups if item.get("id") or item.get("label")],
        "style": style_to_output(style),
        "raw_style": node.get("style"),
        "tags": label_info["tags"],
    }
    if label_info["clean_label"] is not None:
        output["label"] = label_info["clean_label"]
    if raw_label is not None:
        output["inkscape_label"] = raw_label
    return output


def _collect_text_spans(node, base_style, spans, warnings):
    text_parts = []
    if node.text:
        text_parts.append(node.text)
        spans.append(
            {
                "text": node.text,
                "style": style_to_output(base_style),
                "local": {
                    "x": parse_number(node.get("x")),
                    "y": parse_number(node.get("y")),
                },
            }
        )
    for child in list(node):
        name = local_name(child.tag)
        if name != "tspan":
            warnings.append("complex text layout")
            continue
        child_style = build_style(child, base_style, warnings)
        child_text = _collect_text_spans(child, child_style, spans, warnings)
        text_parts.append(child_text)
        if child.tail:
            text_parts.append(child.tail)
            spans.append(
                {
                    "text": child.tail,
                    "style": style_to_output(base_style),
                    "local": {
                        "x": None,
                        "y": None,
                    },
                }
            )
    return "".join(text_parts)


def _suggest_tk_anchor(text_anchor):
    if text_anchor == "middle":
        return "s"
    if text_anchor == "end":
        return "se"
    return "sw"


def _effective_text_anchor(style, spans):
    for span in spans:
        if not str(span.get("text") or "").strip():
            continue
        span_style = span.get("style") or {}
        anchor_name = span_style.get("text_anchor")
        if anchor_name:
            return anchor_name
    return style.get("text-anchor", "start")


def _copy_layer(layer_info):
    if layer_info is None:
        return None
    output = {
        "uid": layer_info.get("uid"),
        "svg_id": layer_info.get("svg_id"),
        "label": layer_info.get("label"),
        "role": layer_info.get("role"),
    }
    if layer_info.get("tags"):
        output["tags"] = list(layer_info.get("tags"))
    if layer_info.get("inkscape_label") is not None:
        output["inkscape_label"] = layer_info.get("inkscape_label")
    return output


def _layer_id(layer_info):
    if layer_info is None:
        return None
    return layer_info.get("uid")


def _copy_group(group_info):
    return {
        "id": group_info.get("id"),
        "label": group_info.get("label"),
        "is_region": group_info.get("is_region", False),
    }


def _push_object(state, obj):
    if obj is not None:
        role = obj.pop("_layer_role", None) or "presentation"
        if role == "annotation":
            obj["annotation"] = _build_annotation_info(obj)
            state["annotations"].append(obj)
            return
        state["objects"].append(obj)
        if role == "presentation" and "region" in (obj.get("tags") or []):
            state["annotations"].append(_build_visual_region_annotation(obj))


def _build_annotation_info(obj):
    clean_label = obj.get("label")
    if clean_label and clean_label.startswith("region."):
        return {
            "kind": "region",
            "name": clean_label.split(".", 1)[1] or None,
            "raw_label": clean_label,
            "source": "annotation-layer",
        }
    return {
        "kind": "unknown",
        "name": None,
        "raw_label": clean_label,
        "source": "annotation-layer",
    }


def _build_visual_region_annotation(obj):
    bbox = ((obj.get("world") or {}).get("bbox")) or [0.0, 0.0, 0.0, 0.0]
    x0_value, y0_value, x1_value, y1_value = bbox
    return {
        "uid": (obj.get("uid") or "region") + "__region",
        "svg_id": obj.get("svg_id"),
        "kind": "rect",
        "label": obj.get("label"),
        "inkscape_label": obj.get("inkscape_label"),
        "tags": list(obj.get("tags") or []),
        "layer": obj.get("layer"),
        "annotation": {
            "kind": "region",
            "name": obj.get("label"),
            "raw_label": obj.get("label"),
            "source": "visual-item",
        },
        "world": {
            "bbox": bbox,
            "points": [[x0_value, y0_value], [x1_value, y0_value], [x1_value, y1_value], [x0_value, y1_value]],
            "matrix": [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
        },
    }


def _clean_matrix(matrix):
    return [clean_number(value) for value in copy_matrix(matrix)]


def _num(node, key, state, optional=False):
    value = parse_number(node.get(key))
    if value is None:
        if optional:
            return None
        state["warnings"].append("missing numeric coordinate: " + key)
        return 0.0
    raw = node.get(key)
    if raw and "%" in raw:
        state["warnings"].append("percentage or unit not yet supported: " + raw)
    return value
