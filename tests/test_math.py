"""Pure Python formula and selection-name tests; no bpy import."""
import ast
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from clock_animator.core import hand_expression, match_role, time_expression  # noqa: E402


def evaluate(expression, t=None, tick=None, **variables):
    values = {'floor': math.floor, 't': t, 'tick': tick, **variables}
    tree = ast.parse(expression, mode='eval')
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name,
               ast.Load, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.Call)
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            raise ValueError('Unsafe expression')
        if isinstance(node, ast.Name) and node.id not in values:
            raise ValueError('Unsafe variable')
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id == 'floor' and len(node.args) == 1 and not node.keywords):
            raise ValueError('Unsafe function')
    return eval(compile(tree, '<clock>', 'eval'), {'__builtins__': {}}, values)


class MathTests(unittest.TestCase):
    def test_crown_time(self):
        for gear in (0, 12, 60, -60):
            for angle in (-20 * math.pi, -0.2, 0.0, math.pi / 2, 14 * math.pi):
                values = dict(h=3, m=45, s=10.5, frame=49, off=1, fb=1.001, fps=24,
                              speed=-2.0, c=angle + 0.45, cr=0.45, gear=gear)
                base = 3 * 3600 + 45 * 60 + 10.5 - 48 * 1.001 / 24 * 2
                self.assertAlmostEqual(evaluate(time_expression(True), **values),
                                       base + angle * gear * 60 / (2 * math.pi), delta=1e-9)
                self.assertAlmostEqual(evaluate(time_expression(), **values), base, delta=1e-9)

    def test_formulas(self):
        cases = [(0, 0, 0, 1, 24, 1), (1, 2, 3, 1, 24, 1),
                 (11, 59, 59, 1, 24, 1), (12, 0, 0, 1, 24, 1),
                 (0, 0, 0, -1, 24, 1), (3, 45, 10.25, 2, 24, 1.001)]
        for h, m, s, speed, fps, fb in cases:
            for frame in (1, 24, 25, 48, 1441, 86401):
                t = h * 3600 + m * 60 + s + (frame - 1) * fb / fps * speed
                for role, period in [('second', 60), ('minute', 3600), ('hour', 43200)]:
                    for tick in (0, 1):
                        for reverse in (False, True):
                            expression = hand_expression(0.123, role, reverse)
                            self.assertNotIn('e-', expression)
                            expected = 0.123 + (-1 if reverse else 1) * 2 * math.pi / period * (math.floor(t) if tick else t)
                            self.assertAlmostEqual(evaluate(expression, t, tick), expected, delta=1e-9)

    def test_names(self):
        for name, role in [('Hand_SEC', 'second'), ('MIN_pointer', 'minute'), ('hr_hand', 'hour'), ('Hour', 'hour'), ('box', None)]:
            self.assertEqual(match_role(name), role)
        with self.assertRaises(ValueError):
            match_role('sec_min')

    def test_validation(self):
        for base, role in [(float('nan'), 'second'), (0, 'invalid')]:
            with self.assertRaises(ValueError):
                hand_expression(base, role)
        with self.assertRaises(ValueError):
            evaluate('__import__("os")', 0, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
