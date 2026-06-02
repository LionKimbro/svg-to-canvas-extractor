import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from svg2canvasx.transforms import apply_matrix
from svg2canvasx.transforms import multiply_matrices
from svg2canvasx.transforms import parse_transform_list


class TransformTests(unittest.TestCase):
    def test_translate_then_scale_order(self):
        warnings = []
        matrix = parse_transform_list("translate(10,20) scale(2)", warnings)
        point = apply_matrix(matrix, [5, 5])
        self.assertEqual(warnings, [])
        self.assertEqual(point, [20.0, 30.0])

    def test_rotate_about_origin(self):
        warnings = []
        matrix = parse_transform_list("rotate(90)", warnings)
        point = apply_matrix(matrix, [2, 0])
        self.assertAlmostEqual(point[0], 0.0, places=6)
        self.assertAlmostEqual(point[1], 2.0, places=6)

    def test_matrix_multiplication(self):
        left = [1.0, 0.0, 0.0, 1.0, 10.0, 0.0]
        right = [2.0, 0.0, 0.0, 2.0, 0.0, 5.0]
        matrix = multiply_matrices(left, right)
        self.assertEqual(matrix, [2.0, 0.0, 0.0, 2.0, 10.0, 5.0])
