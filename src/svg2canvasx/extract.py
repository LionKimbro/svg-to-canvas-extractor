from pathlib import Path

from .geometry import bbox_from_points
from .geometry import clean_number
from .geometry import clean_point
from .geometry import parse_points
from .geometry import rect_points
from .geometry import simplify_path
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
from .transforms import apply_matrix
from .transforms import copy_matrix
from .transforms import extract_rotation_angle
from .transforms import kIDENTITY_MATRIX
from .transforms import multiply_matrices
from .transforms import parse_transform_list


def extract_svg_file(
    path,
    layer_names=None,
    extract_all_layers=False,
    include_hidden=False,
    include_world_geometry=True,
    debug=False,
):
    warnings = []
    root = load_svg(path)
    svg_meta = get_svg_meta(root, warnings)
    state = {
        "warnings": warnings,
        "objects": [],
        "layers": [],
        "uid_counter": 0,
        "selected_layers": [],
        "include_hidden": include_hidden,
        "include_world_geometry": include_world_geometry,
        "debug": debug,
    }

    selected = _choose_layers(root, layer_names, extract_all_layers)
    state["selected_layers"] = selected
    state["layers"] = [_copy_layer(layer) for layer in selected]

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
        "warnings": warnings,
    }


def walk_node(node, state, parent_matrix, parent_style, layer_info, groups):
    name = local_name(node.tag)
    style = build_style(node, parent_style, state["warnings"])
    if not is_visible(style, state["include_hidden"]):
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
            current_layer = get_layer_info(node)
            if _should_skip_layer(current_layer, state["selected_layers"]):
                return
        else:
            current_groups = current_groups + [_group_info(node)]
        for child in list(node):
            walk_node(child, state, world_matrix, style, current_layer, current_groups)
        return

    if current_layer is None and state["selected_layers"]:
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
    if state["include_world_geometry"]:
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
    if state["include_world_geometry"]:
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
    if state["include_world_geometry"]:
        obj["world"] = {
            "matrix": _clean_matrix(world_matrix),
            "points": world_points,
            "bbox": bbox_from_points(world_points),
        }
    return obj


def extract_path(node, layer_info, groups, style, world_matrix, state):
    d_value = node.get("d", "")
    local_points = simplify_path(d_value, state["warnings"])
    obj = _base_object(node, "path", layer_info, groups, style, world_matrix, state)
    obj["local"] = {
        "d": d_value,
    }
    if local_points:
        obj["local"]["points"] = local_points
        obj["local"]["bbox"] = bbox_from_points(local_points)
    if state["include_world_geometry"]:
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
    anchor_name = style.get("text-anchor", "start")
    obj = _base_object(node, "text", layer_info, groups, style, world_matrix, state)
    obj["text"] = text_value
    obj["spans"] = spans
    obj["local"] = {
        "x": x_value,
        "y": y_value,
    }
    if state["include_world_geometry"]:
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
    if state["include_world_geometry"]:
        obj["world"] = {
            "matrix": _clean_matrix(world_matrix),
            "center": clean_point(apply_matrix(world_matrix, [cx_value, cy_value])),
            "bbox": bbox_from_points(world_points),
            "points": world_points,
        }
    return obj


def _choose_layers(root, layer_names, extract_all_layers):
    layers = []
    for child in list(root):
        if local_name(child.tag) == "g" and is_layer(child):
            layers.append(get_layer_info(child))
    if extract_all_layers:
        return layers
    if layer_names:
        wanted = set(layer_names)
        return [
            layer
            for layer in layers
            if layer.get("id") in wanted or layer.get("label") in wanted
        ]
    for layer in layers:
        if layer.get("label") == "Layer 2" or layer.get("id") == "Layer 2":
            return [layer]
    return [
        layer
        for layer in layers
        if not _looks_like_grid_layer(layer)
    ]


def _looks_like_grid_layer(layer_info):
    text = " ".join(filter(None, [layer_info.get("id"), layer_info.get("label")])).lower()
    return "grid" in text or "reference" in text


def _should_skip_layer(layer_info, selected_layers):
    if not selected_layers:
        return False
    for item in selected_layers:
        if item.get("id") == layer_info.get("id") and item.get("label") == layer_info.get("label"):
            return False
    return True


def _group_info(node):
    return {
        "id": get_node_id(node),
        "label": get_inkscape_label(node),
        "is_region": bool((get_node_id(node) or "").startswith("region_")),
    }


def _base_object(node, kind, layer_info, groups, style, world_matrix, state):
    state["uid_counter"] += 1
    return {
        "uid": get_node_id(node) or "auto_{:05d}".format(state["uid_counter"]),
        "svg_id": get_node_id(node),
        "kind": kind,
        "layer": _copy_layer(layer_info),
        "groups": [_copy_group(item) for item in groups if item.get("id") or item.get("label")],
        "style": style_to_output(style),
        "raw_style": node.get("style"),
    }


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


def _copy_layer(layer_info):
    if layer_info is None:
        return None
    return {
        "id": layer_info.get("id"),
        "label": layer_info.get("label"),
    }


def _copy_group(group_info):
    return {
        "id": group_info.get("id"),
        "label": group_info.get("label"),
        "is_region": group_info.get("is_region", False),
    }


def _push_object(state, obj):
    if obj is not None:
        state["objects"].append(obj)


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
