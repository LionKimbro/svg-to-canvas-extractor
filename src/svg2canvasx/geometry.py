import re

from .styles import parse_number
from .transforms import apply_matrix


kPATH_TOKEN_RE = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


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


def flatten_path(d_value, warnings, curve_segments=16):
    if not d_value:
        return {"points": None, "path_was_flattened": False}

    tokens = kPATH_TOKEN_RE.findall(d_value)
    if not tokens:
        return {"points": None, "path_was_flattened": False}

    state = {
        "points": [],
        "cursor": [0.0, 0.0],
        "start_point": None,
        "command": None,
        "index": 0,
        "curve_segments": max(1, int(curve_segments or 16)),
        "path_was_flattened": False,
        "last_cubic_control": None,
        "last_quadratic_control": None,
    }

    while state["index"] < len(tokens):
        token = tokens[state["index"]]
        if re.match(r"[A-Za-z]", token):
            state["command"] = token
            state["index"] += 1
            if token in ("Z", "z"):
                _close_path(state)
                continue
        if state["command"] is None:
            warnings.append("path could not be simplified to points")
            return {"points": None, "path_was_flattened": False}

        if not _handle_path_command(tokens, state, warnings):
            return {"points": None, "path_was_flattened": state["path_was_flattened"]}

    return {
        "points": state["points"] or None,
        "path_was_flattened": state["path_was_flattened"],
    }


def _handle_path_command(tokens, state, warnings):
    command = state["command"]
    if command in ("M", "m"):
        return _handle_move(tokens, state, command, warnings)
    if command in ("L", "l", "H", "h", "V", "v"):
        return _handle_line_command(tokens, state, command, warnings)
    if command in ("C", "c"):
        return _handle_cubic_command(tokens, state, command, warnings)
    if command in ("S", "s"):
        return _handle_smooth_cubic_command(tokens, state, command, warnings)
    if command in ("Q", "q"):
        return _handle_quadratic_command(tokens, state, command, warnings)
    if command in ("T", "t"):
        return _handle_smooth_quadratic_command(tokens, state, command, warnings)
    if command in ("A", "a"):
        warnings.append("unsupported path arc command")
        return False
    warnings.append("path could not be simplified to points")
    return False


def _handle_move(tokens, state, command, warnings):
    is_relative = command == "m"
    if state["index"] + 1 >= len(tokens):
        warnings.append("path could not be simplified to points")
        return False
    first = True
    while state["index"] + 1 < len(tokens) and not _is_command_token(tokens[state["index"]]):
        point = _read_point(tokens, state["index"], warnings)
        if point is None:
            return False
        state["index"] += 2
        if is_relative:
            point = [state["cursor"][0] + point[0], state["cursor"][1] + point[1]]
        state["cursor"] = point
        if first:
            state["start_point"] = [point[0], point[1]]
            _append_point(state, point)
            first = False
        else:
            _append_point(state, point)
    state["command"] = "l" if is_relative else "L"
    state["last_cubic_control"] = None
    state["last_quadratic_control"] = None
    return True


def _handle_line_command(tokens, state, command, warnings):
    while state["index"] < len(tokens) and not _is_command_token(tokens[state["index"]]):
        if command in ("L", "l"):
            point = _read_point(tokens, state["index"], warnings)
            if point is None:
                return False
            state["index"] += 2
            if command == "l":
                point = [state["cursor"][0] + point[0], state["cursor"][1] + point[1]]
        elif command in ("H", "h"):
            x_value = parse_number(tokens[state["index"]])
            if x_value is None:
                warnings.append("path could not be simplified to points")
                return False
            state["index"] += 1
            if command == "h":
                point = [state["cursor"][0] + x_value, state["cursor"][1]]
            else:
                point = [x_value, state["cursor"][1]]
        else:
            y_value = parse_number(tokens[state["index"]])
            if y_value is None:
                warnings.append("path could not be simplified to points")
                return False
            state["index"] += 1
            if command == "v":
                point = [state["cursor"][0], state["cursor"][1] + y_value]
            else:
                point = [state["cursor"][0], y_value]
        state["cursor"] = point
        _append_point(state, point)
    state["last_cubic_control"] = None
    state["last_quadratic_control"] = None
    return True


def _handle_cubic_command(tokens, state, command, warnings):
    is_relative = command == "c"
    while state["index"] + 5 < len(tokens) and not _is_command_token(tokens[state["index"]]):
        p1_value = _read_point(tokens, state["index"], warnings)
        p2_value = _read_point(tokens, state["index"] + 2, warnings)
        p3_value = _read_point(tokens, state["index"] + 4, warnings)
        if p1_value is None or p2_value is None or p3_value is None:
            return False
        state["index"] += 6
        if is_relative:
            p1_value = _offset_point(state["cursor"], p1_value)
            p2_value = _offset_point(state["cursor"], p2_value)
            p3_value = _offset_point(state["cursor"], p3_value)
        _sample_cubic_segment(state, state["cursor"], p1_value, p2_value, p3_value)
        state["cursor"] = p3_value
        state["last_cubic_control"] = p2_value
        state["last_quadratic_control"] = None
        state["path_was_flattened"] = True
    return True


def _handle_smooth_cubic_command(tokens, state, command, warnings):
    is_relative = command == "s"
    while state["index"] + 3 < len(tokens) and not _is_command_token(tokens[state["index"]]):
        p2_value = _read_point(tokens, state["index"], warnings)
        p3_value = _read_point(tokens, state["index"] + 2, warnings)
        if p2_value is None or p3_value is None:
            return False
        state["index"] += 4
        p1_value = _reflected_control(state["cursor"], state["last_cubic_control"])
        if is_relative:
            p2_value = _offset_point(state["cursor"], p2_value)
            p3_value = _offset_point(state["cursor"], p3_value)
        _sample_cubic_segment(state, state["cursor"], p1_value, p2_value, p3_value)
        state["cursor"] = p3_value
        state["last_cubic_control"] = p2_value
        state["last_quadratic_control"] = None
        state["path_was_flattened"] = True
    return True


def _handle_quadratic_command(tokens, state, command, warnings):
    is_relative = command == "q"
    while state["index"] + 3 < len(tokens) and not _is_command_token(tokens[state["index"]]):
        p1_value = _read_point(tokens, state["index"], warnings)
        p2_value = _read_point(tokens, state["index"] + 2, warnings)
        if p1_value is None or p2_value is None:
            return False
        state["index"] += 4
        if is_relative:
            p1_value = _offset_point(state["cursor"], p1_value)
            p2_value = _offset_point(state["cursor"], p2_value)
        _sample_quadratic_segment(state, state["cursor"], p1_value, p2_value)
        state["cursor"] = p2_value
        state["last_quadratic_control"] = p1_value
        state["last_cubic_control"] = None
        state["path_was_flattened"] = True
    return True


def _handle_smooth_quadratic_command(tokens, state, command, warnings):
    is_relative = command == "t"
    while state["index"] + 1 < len(tokens) and not _is_command_token(tokens[state["index"]]):
        p2_value = _read_point(tokens, state["index"], warnings)
        if p2_value is None:
            return False
        state["index"] += 2
        p1_value = _reflected_control(state["cursor"], state["last_quadratic_control"])
        if is_relative:
            p2_value = _offset_point(state["cursor"], p2_value)
        _sample_quadratic_segment(state, state["cursor"], p1_value, p2_value)
        state["cursor"] = p2_value
        state["last_quadratic_control"] = p1_value
        state["last_cubic_control"] = None
        state["path_was_flattened"] = True
    return True


def _sample_cubic_segment(state, p0_value, p1_value, p2_value, p3_value):
    segments = state["curve_segments"]
    for step in range(1, segments + 1):
        t_value = step / segments
        omt_value = 1.0 - t_value
        point = [
            (omt_value ** 3) * p0_value[0]
            + 3.0 * (omt_value ** 2) * t_value * p1_value[0]
            + 3.0 * omt_value * (t_value ** 2) * p2_value[0]
            + (t_value ** 3) * p3_value[0],
            (omt_value ** 3) * p0_value[1]
            + 3.0 * (omt_value ** 2) * t_value * p1_value[1]
            + 3.0 * omt_value * (t_value ** 2) * p2_value[1]
            + (t_value ** 3) * p3_value[1],
        ]
        _append_point(state, point)


def _sample_quadratic_segment(state, p0_value, p1_value, p2_value):
    segments = state["curve_segments"]
    for step in range(1, segments + 1):
        t_value = step / segments
        omt_value = 1.0 - t_value
        point = [
            (omt_value ** 2) * p0_value[0] + 2.0 * omt_value * t_value * p1_value[0] + (t_value ** 2) * p2_value[0],
            (omt_value ** 2) * p0_value[1] + 2.0 * omt_value * t_value * p1_value[1] + (t_value ** 2) * p2_value[1],
        ]
        _append_point(state, point)


def _close_path(state):
    if state["start_point"] is not None:
        _append_point(state, state["start_point"])
    state["cursor"] = state["start_point"] or state["cursor"]
    state["last_cubic_control"] = None
    state["last_quadratic_control"] = None


def _append_point(state, point):
    clean = clean_point(point)
    if state["points"] and state["points"][-1] == clean:
        return
    state["points"].append(clean)


def _read_point(tokens, index, warnings):
    if index + 1 >= len(tokens):
        warnings.append("path could not be simplified to points")
        return None
    x_value = parse_number(tokens[index])
    y_value = parse_number(tokens[index + 1])
    if x_value is None or y_value is None:
        warnings.append("path could not be simplified to points")
        return None
    return [x_value, y_value]


def _offset_point(origin, point):
    return [origin[0] + point[0], origin[1] + point[1]]


def _reflected_control(cursor, control):
    if control is None:
        return [cursor[0], cursor[1]]
    return [2.0 * cursor[0] - control[0], 2.0 * cursor[1] - control[1]]


def _is_command_token(token):
    return bool(re.match(r"^[A-Za-z]$", token))
