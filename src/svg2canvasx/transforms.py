import math
import re


kIDENTITY_MATRIX = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
kTRANSFORM_RE = re.compile(r"([A-Za-z]+)\s*\(([^)]*)\)")


def copy_matrix(matrix):
    return [float(value) for value in matrix]


def multiply_matrices(left, right):
    a1, b1, c1, d1, e1, f1 = left
    a2, b2, c2, d2, e2, f2 = right
    return [
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    ]


def apply_matrix(matrix, point):
    x_value, y_value = point
    a_value, b_value, c_value, d_value, e_value, f_value = matrix
    return [
        a_value * x_value + c_value * y_value + e_value,
        b_value * x_value + d_value * y_value + f_value,
    ]


def parse_transform_list(text, warnings):
    matrix = copy_matrix(kIDENTITY_MATRIX)
    if not text:
        return matrix

    for name, raw_args in kTRANSFORM_RE.findall(text):
        values = _parse_transform_args(raw_args, warnings)
        local = _build_transform_matrix(name, values, warnings)
        matrix = multiply_matrices(matrix, local)
    return matrix


def extract_rotation_angle(matrix):
    a_value, b_value = matrix[0], matrix[1]
    if abs(a_value) < 1e-12 and abs(b_value) < 1e-12:
        return 0.0
    return math.degrees(math.atan2(b_value, a_value))


def _parse_transform_args(text, warnings):
    values = []
    for part in re.split(r"[\s,]+", text.strip()):
        if not part:
            continue
        try:
            values.append(float(part))
        except ValueError:
            warnings.append("unsupported transform argument: " + part)
    return values


def _build_transform_matrix(name, values, warnings):
    lower_name = name.lower()
    if lower_name == "matrix" and len(values) == 6:
        return values
    if lower_name == "translate" and len(values) in (1, 2):
        tx_value = values[0]
        ty_value = values[1] if len(values) == 2 else 0.0
        return [1.0, 0.0, 0.0, 1.0, tx_value, ty_value]
    if lower_name == "scale" and len(values) in (1, 2):
        sx_value = values[0]
        sy_value = values[1] if len(values) == 2 else sx_value
        return [sx_value, 0.0, 0.0, sy_value, 0.0, 0.0]
    if lower_name == "rotate" and len(values) in (1, 3):
        angle = math.radians(values[0])
        cos_value = math.cos(angle)
        sin_value = math.sin(angle)
        rotate_matrix = [cos_value, sin_value, -sin_value, cos_value, 0.0, 0.0]
        if len(values) == 1:
            return rotate_matrix
        cx_value = values[1]
        cy_value = values[2]
        return multiply_matrices(
            multiply_matrices(
                [1.0, 0.0, 0.0, 1.0, cx_value, cy_value],
                rotate_matrix,
            ),
            [1.0, 0.0, 0.0, 1.0, -cx_value, -cy_value],
        )
    if lower_name == "skewx" and len(values) == 1:
        tangent = math.tan(math.radians(values[0]))
        return [1.0, 0.0, tangent, 1.0, 0.0, 0.0]
    if lower_name == "skewy" and len(values) == 1:
        tangent = math.tan(math.radians(values[0]))
        return [1.0, tangent, 0.0, 1.0, 0.0, 0.0]
    warnings.append("unsupported transform function: " + name)
    return copy_matrix(kIDENTITY_MATRIX)

