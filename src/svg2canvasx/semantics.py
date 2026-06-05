import json
from pathlib import Path


def format_semantics_file(path, pretty=False):
    input_path = Path(path)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    return format_semantics_json(data, pretty=pretty)


def format_semantics_data(data):
    if data.get("format") == "svg2canvasx-flow":
        return _flow_semantics_data(data)
    return _extracted_semantics_data(data)


def format_semantics_json(data, pretty=False):
    semantics = format_semantics_data(data)
    return json.dumps(semantics, ensure_ascii=True, indent=2 if pretty else None)


def _extracted_semantics_data(data):
    layers = data.get("layers") or []
    annotations = data.get("annotations") or []
    layer_index = _index_layers(layers)
    names_by_layer = {}
    regions_by_layer = {}
    for obj in annotations:
        layer = _resolve_layer(layer_index, obj.get("layer"))
        layer_name = _layer_name(layer)
        raw_name = _annotation_label(obj)
        if raw_name:
            names_by_layer.setdefault(layer_name, [])
            if raw_name not in names_by_layer[layer_name]:
                names_by_layer[layer_name].append(raw_name)
        annotation = obj.get("annotation") or {}
        name = annotation.get("name")
        if not name:
            continue
        regions_by_layer.setdefault(layer_name, [])
        if name not in regions_by_layer[layer_name]:
            regions_by_layer[layer_name].append(name)
    return _build_semantics_brief(layers, names_by_layer, regions_by_layer)


def _flow_semantics_data(data):
    flow_layers = data.get("layers") or []
    names_by_layer = {}
    regions_by_layer = {}
    ordered_layers = []
    for layer in flow_layers:
        layer_name = layer.get("name") or "Unnamed Layer"
        ordered_layers.append({"label": layer_name, "role": layer.get("role")})
        for region in layer.get("regions") or []:
            raw_name = region.get("label") or region.get("name")
            if raw_name:
                names_by_layer.setdefault(layer_name, [])
                if raw_name not in names_by_layer[layer_name]:
                    names_by_layer[layer_name].append(raw_name)
            name = region.get("name")
            if not name:
                continue
            regions_by_layer.setdefault(layer_name, [])
            if name not in regions_by_layer[layer_name]:
                regions_by_layer[layer_name].append(name)
    return _build_semantics_brief(ordered_layers, names_by_layer, regions_by_layer)


def _build_semantics_brief(layers, names_by_layer, regions_by_layer):
    output_layers = []
    seen = set()
    for layer in layers:
        layer_name = _layer_name(layer)
        if layer_name in seen:
            continue
        seen.add(layer_name)
        item = {
            "name": layer_name,
            "role": layer.get("role") or _infer_role_from_names(layer_name, names_by_layer, regions_by_layer),
        }
        annotations = names_by_layer.get(layer_name, [])
        if annotations:
            item["annotations"] = annotations
        regions = regions_by_layer.get(layer_name, [])
        if regions:
            item["regions"] = regions
        output_layers.append(item)
    for layer_name, annotations in names_by_layer.items():
        if layer_name in seen:
            continue
        regions = regions_by_layer.get(layer_name, [])
        output_layers.append(
            {
                "name": layer_name,
                "role": "annotation",
                "annotations": annotations,
                "regions": regions,
            }
        )
    return {"layers": output_layers}


def _layer_name(layer):
    return layer.get("label") or layer.get("name") or layer.get("id") or "Unnamed Layer"


def _index_layers(layers):
    output = {}
    for layer in layers:
        layer_id = layer.get("id")
        if layer_id is not None:
            output[layer_id] = layer
    return output


def _resolve_layer(layer_index, layer_ref):
    if isinstance(layer_ref, dict):
        return layer_ref
    if layer_ref is not None and layer_ref in layer_index:
        return layer_index[layer_ref]
    if layer_ref is not None:
        return {"id": layer_ref}
    return {}


def _infer_role_from_names(layer_name, names_by_layer, regions_by_layer):
    if names_by_layer.get(layer_name) or regions_by_layer.get(layer_name):
        return "annotation"
    return None


def _annotation_label(obj):
    return obj.get("label") or obj.get("inkscape_label") or obj.get("svg_id") or obj.get("uid")
