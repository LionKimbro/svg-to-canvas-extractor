from pathlib import Path
import xml.etree.ElementTree as ET

from .styles import parse_number


kSVG_NS = "http://www.w3.org/2000/svg"
kINKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"


def load_svg(path):
    root = ET.parse(path).getroot()
    return root


def local_name(tag):
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def get_svg_meta(root, warnings):
    width = _parse_length(root.get("width"), warnings)
    height = _parse_length(root.get("height"), warnings)
    view_box = None
    raw_view_box = root.get("viewBox")
    if raw_view_box:
        parts = raw_view_box.replace(",", " ").split()
        if len(parts) == 4:
            numbers = []
            for part in parts:
                number = parse_number(part)
                if number is None:
                    warnings.append("percentage or unit not yet supported: " + part)
                    numbers = []
                    break
                numbers.append(number)
            if numbers:
                view_box = numbers
    return {
        "width": width,
        "height": height,
        "viewBox": view_box,
    }


def get_node_id(node):
    return node.get("id")


def get_inkscape_label(node):
    return node.get("{" + kINKSCAPE_NS + "}label")


def is_layer(node):
    return node.get("{" + kINKSCAPE_NS + "}groupmode") == "layer"


def get_layer_info(node):
    return {
        "id": get_node_id(node),
        "label": get_inkscape_label(node),
        "role": classify_layer_role(get_node_id(node), get_inkscape_label(node)),
    }


def normalize_source_path(path):
    return str(Path(path))


def classify_layer_role(layer_id, layer_label):
    text = " ".join(filter(None, [layer_id, layer_label])).lower()
    if "annotation" in text:
        return "annotation"
    if "grid" in text or "reference" in text:
        return "reference"
    return "drawable"


def _parse_length(text, warnings):
    if text is None:
        return None
    value = parse_number(text)
    if value is None:
        warnings.append("percentage or unit not yet supported: " + str(text))
        return None
    return value
