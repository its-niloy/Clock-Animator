"""Independent mathematical checks for deterministic animation tools."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from clock_animator.motion import clock_text, date_position, ramp_seconds  # noqa: E402


class MotionTests(unittest.TestCase):
    def test_ramp_integral(self):
        for smooth in (False, True):
            self.assertAlmostEqual(ramp_seconds(121, 1, 121, 1, 20, 24, smooth), 52.5)
            self.assertAlmostEqual(ramp_seconds(145, 1, 121, 1, 20, 24, smooth), 72.5)
            self.assertEqual(ramp_seconds(-30, 1, 121, 1, 20, 24, smooth), 0)
        self.assertAlmostEqual(ramp_seconds(61, 1, 121, 1, 20, 24), 14.375)
        self.assertAlmostEqual(ramp_seconds(121, 1, 121, -1, -3, 24), -10)
        with self.assertRaises(ValueError):
            ramp_seconds(1, 1, 1, 0, 1, 24)

    def test_date(self):
        self.assertEqual(date_position(0, 28), 27)
        self.assertEqual(date_position(4 * 86400, 28), 0)
        self.assertEqual(date_position(-1, 1), 30)
        self.assertAlmostEqual(date_position(86350, 1, 100), 0.5)
        self.assertEqual(date_position(86400, 1, 100), 1)

    def test_clock_text(self):
        self.assertEqual(clock_text(3661.9), '01:01:01')
        self.assertEqual(clock_text(-1), '23:59:59')
        self.assertEqual(clock_text(86400), '00:00:00')
        self.assertEqual(clock_text(float('nan')), '--:--:--')


if __name__ == '__main__':
    unittest.main(verbosity=2)
