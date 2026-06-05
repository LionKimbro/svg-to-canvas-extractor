from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .styles import parse_number


kSVG_NS = "http://www.w3.org/2000/svg"
kINKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
kBRACKET_TAG_RE = re.compile(r"\[([^\]]+)\]")


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


def get_layer_info(node, warnings=None):
    label = get_inkscape_label(node)
    label_info = parse_label_metadata(label)
    role = classify_layer_role(label)
    if role is None:
        message = "unrecognized layer role tag: " + str(label or get_node_id(node) or "(unnamed layer)")
        raise ValueError(message)
    return {
        "id": get_node_id(node),
        "label": label_info["clean_label"],
        "inkscape_label": label,
        "tags": label_info["tags"],
        "role": role,
    }


def normalize_source_path(path):
    return str(Path(path))


def classify_layer_role(layer_label):
    label_info = parse_label_metadata(layer_label)
    for tag in label_info["tags"]:
        if tag == "comment":
            return "comment"
        if tag == "visual":
            return "presentation"
        if tag == "annotate":
            return "annotation"
    return None


def parse_label_metadata(text):
    raw = text
    tags = []
    if text:
        for match in kBRACKET_TAG_RE.findall(text):
            for part in re.split(r"[\s,]+", match.strip()):
                if part:
                    tags.append(part.lower())
    clean = kBRACKET_TAG_RE.sub("", text or "")
    clean = re.sub(r"\s+", " ", clean).strip()
    return {
        "raw_label": raw,
        "clean_label": clean if clean else None,
        "tags": tags,
    }


def _parse_length(text, warnings):
    if text is None:
        return None
    value = parse_number(text)
    if value is None:
        warnings.append("percentage or unit not yet supported: " + str(text))
        return None
    return value
