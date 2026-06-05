import re


kSTYLE_KEYS = {
    "fill",
    "stroke",
    "stroke-width",
    "stroke-dasharray",
    "stroke-linecap",
    "stroke-linejoin",
    "opacity",
    "fill-opacity",
    "stroke-opacity",
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "text-anchor",
    "dominant-baseline",
    "alignment-baseline",
    "display",
    "visibility",
}

kPRESENTATION_KEYS = set(kSTYLE_KEYS)


def empty_style():
    return {}


def build_style(node, parent_style, warnings):
    style = dict(parent_style or {})
    for key, value in _parse_style_attribute(node.get("style", "")).items():
        style[key] = value
    for key in kPRESENTATION_KEYS:
        if node.get(key) is not None:
            style[key] = node.get(key)
    if node.get("class"):
        warnings.append("CSS class not resolved: " + node.get("class"))
    return style


def style_to_output(style):
    output = {}
    for key in sorted(style):
        mapped_key = key.replace("-", "_")
        if key == "stroke-dasharray":
            output[mapped_key] = style[key]
            output["stroke_dasharray_values"] = parse_dasharray(style[key])
            continue
        value = style[key]
        if key in ("stroke-width", "font-size", "opacity", "fill-opacity", "stroke-opacity"):
            number = parse_number(value)
            output[mapped_key] = number if number is not None else value
            continue
        output[mapped_key] = value
    return output


def is_visible(style):
    if style.get("display") == "none":
        return False
    if style.get("visibility") == "hidden":
        return False
    opacity = parse_number(style.get("opacity"))
    if opacity == 0.0:
        return False
    return True


def parse_dasharray(text):
    if not text or text == "none":
        return None
    values = []
    for part in re.split(r"[\s,]+", text.strip()):
        if not part:
            continue
        number = parse_number(part)
        if number is None:
            return None
        values.append(number)
    return values or None


def parse_number(text):
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    if raw.endswith("%"):
        return None
    match = re.match(r"^[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", raw)
    if not match:
        return None
    token = match.group(0)
    try:
        return float(token)
    except ValueError:
        return None


def _parse_style_attribute(text):
    style = {}
    for chunk in text.split(";"):
        if ":" not in chunk:
            continue
        key, value = chunk.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        style[key] = value
    return style
