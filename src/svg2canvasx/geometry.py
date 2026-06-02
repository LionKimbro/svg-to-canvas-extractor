import re

from .styles import parse_number
from .transforms import apply_matrix


kPATH_TOKEN_RE = re.compile(r"[MmLlHhVvZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def parse_points(text, warnings):
    points = []
    tokens = re.split(r"[\s,]+", (text or "").strip())
    values = []
    for token in tokens:
        if not token:
            continue
        number = parse_number(token)
        if number is None:
            warnings.append("missing numeric coordinate: " + token)
            return []
        values.append(number)
    if len(values) % 2 != 0:
        warnings.append("missing numeric coordinate in points list")
        return []
    for index in range(0, len(values), 2):
        points.append([values[index], values[index + 1]])
    return points


def transform_points(matrix, points):
    return [clean_point(apply_matrix(matrix, point)) for point in points]


def bbox_from_points(points):
    if not points:
        return None
    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    return clean_point([min(x_values), min(y_values)]) + clean_point([max(x_values), max(y_values)])


def rect_points(x_value, y_value, width, height):
    return [
        [x_value, y_value],
        [x_value + width, y_value],
        [x_value + width, y_value + height],
        [x_value, y_value + height],
    ]


def clean_number(value):
    rounded = round(float(value), 6)
    if abs(rounded) < 1e-9:
        return 0.0
    return rounded


def clean_point(point):
    return [clean_number(point[0]), clean_number(point[1])]


def simplify_path(d_value, warnings):
    if not d_value:
        return None

    tokens = kPATH_TOKEN_RE.findall(d_value)
    if not tokens:
        return None

    points = []
    command = None
    cursor = [0.0, 0.0]
    start_point = None
    index = 0

    while index < len(tokens):
        token = tokens[index]
        if re.match(r"[A-Za-z]", token):
            command = token
            index += 1
            if command in ("Z", "z"):
                if start_point is not None:
                    points.append([start_point[0], start_point[1]])
                continue
        if command is None:
            warnings.append("path could not be simplified to points")
            return None

        if command in ("M", "L"):
            if index + 1 >= len(tokens):
                warnings.append("path could not be simplified to points")
                return None
            x_value = parse_number(tokens[index])
            y_value = parse_number(tokens[index + 1])
            if x_value is None or y_value is None:
                warnings.append("path could not be simplified to points")
                return None
            cursor = [x_value, y_value]
            if command == "M" and start_point is None:
                start_point = [cursor[0], cursor[1]]
            points.append([cursor[0], cursor[1]])
            command = "L" if command == "M" else command
            index += 2
            continue

        if command in ("m", "l"):
            if index + 1 >= len(tokens):
                warnings.append("path could not be simplified to points")
                return None
            dx_value = parse_number(tokens[index])
            dy_value = parse_number(tokens[index + 1])
            if dx_value is None or dy_value is None:
                warnings.append("path could not be simplified to points")
                return None
            cursor = [cursor[0] + dx_value, cursor[1] + dy_value]
            if command == "m" and start_point is None:
                start_point = [cursor[0], cursor[1]]
            points.append([cursor[0], cursor[1]])
            command = "l" if command == "m" else command
            index += 2
            continue

        if command == "H":
            x_value = parse_number(tokens[index])
            if x_value is None:
                warnings.append("path could not be simplified to points")
                return None
            cursor = [x_value, cursor[1]]
            points.append([cursor[0], cursor[1]])
            index += 1
            continue

        if command == "h":
            dx_value = parse_number(tokens[index])
            if dx_value is None:
                warnings.append("path could not be simplified to points")
                return None
            cursor = [cursor[0] + dx_value, cursor[1]]
            points.append([cursor[0], cursor[1]])
            index += 1
            continue

        if command == "V":
            y_value = parse_number(tokens[index])
            if y_value is None:
                warnings.append("path could not be simplified to points")
                return None
            cursor = [cursor[0], y_value]
            points.append([cursor[0], cursor[1]])
            index += 1
            continue

        if command == "v":
            dy_value = parse_number(tokens[index])
            if dy_value is None:
                warnings.append("path could not be simplified to points")
                return None
            cursor = [cursor[0], cursor[1] + dy_value]
            points.append([cursor[0], cursor[1]])
            index += 1
            continue

        warnings.append("path could not be simplified to points")
        return None

    return points
