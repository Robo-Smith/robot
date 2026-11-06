from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import robot_control as control


class FollowCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(control, 'FOLLOW_SIZE_METRIC', 'height'))
        self.enterContext(patch.object(control, 'FOLLOW_TARGET_SIZE', .65))

    def test_one_meter_calibration_stops_at_measured_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            measured = control.save_calibration([.49, .5, .51, .5, .5], path)
            self.assertEqual(measured, .5)
            with patch.object(control, 'FOLLOW_TARGET_SIZE', control.load_target_size(path)):
                self.assertEqual(control.follow_command((270, 0, 100, 240), 640, 480), (0, 0))
                left, right = control.follow_command((270, 0, 100, 200), 640, 480)
                self.assertGreaterEqual(left, .18)
                self.assertEqual(left, right)

    def test_width_calibration_works_with_vertical_crop(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            control.save_calibration([.4] * 5, path, metric='width')
            self.assertEqual(control.load_size_metric(path), 'width')
            with patch.object(control, 'FOLLOW_SIZE_METRIC', control.load_size_metric(path)), \
                 patch.object(control, 'FOLLOW_TARGET_SIZE', control.load_target_size(path)):
                # Full image height is allowed: width controls spacing.
                self.assertEqual(control.follow_command((192, 0, 256, 480), 640, 480), (0, 0))
                left, right = control.follow_command((224, 0, 192, 480), 640, 480)
                self.assertGreaterEqual(left, .18)
                self.assertEqual(left, right)
                self.assertEqual(control.follow_command((160, 0, 320, 480), 640, 480), (0, 0))

    def test_speed_rises_with_distance_and_stops_at_calibration(self):
        with patch.object(control, 'FOLLOW_SIZE_METRIC', 'width'), \
             patch.object(control, 'FOLLOW_TARGET_SIZE', .44):
            def speed(w):
                left, right = control.follow_command(((640 - w) / 2, 0, w, 480), 640, 480)
                self.assertEqual(left, right)
                return left
            self.assertEqual(speed(256), 0)  # calibrated 1m
            self.assertAlmostEqual(speed(192), .38)  # 25% smaller apparent width
            self.assertAlmostEqual(speed(128), .58)  # half calibrated width
            self.assertEqual(speed(64), .65)  # distant person reaches maximum
            self.assertGreater(speed(250), .18)
            self.assertLess(speed(250), speed(192))

    def test_slow_turns_have_more_power_and_mirror_correctly(self):
        with patch.object(control, 'FOLLOW_SIZE_METRIC', 'width'), \
             patch.object(control, 'FOLLOW_TARGET_SIZE', .44):
            # Just outside spacing target: forward request is near its minimum.
            left, right = control.follow_command((280, 0, 250, 480), 640, 480)
            self.assertGreater(left, 0)
            self.assertLess(right, 0)
            self.assertGreaterEqual(abs(left), .28)
            self.assertGreaterEqual(abs(right), .28)
            mirror = control.follow_command((110, 0, 250, 480), 640, 480)
            self.assertAlmostEqual(mirror[0], right)
            self.assertAlmostEqual(mirror[1], left)
            self.assertLessEqual(max(abs(left), abs(right)), .65)
            # Higher turn power must never bypass the close-person stop.
            self.assertEqual(control.follow_command((280, 0, 300, 480), 640, 480), (0, 0))

    def test_uncertain_calibration_does_not_replace_existing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            path.write_text('previous calibration')
            for heights in ([.5] * 4, [.5, .5, .5, .5, .9], [.98] * 5):
                with self.assertRaises(ValueError):
                    control.save_calibration(heights, path)
                self.assertEqual(path.read_text(), 'previous calibration')

    def test_nonzero_wheel_commands_clear_deadband_and_keep_limits(self):
        for x in range(0, 600, 40):
            for height in (100, 200, 280):
                left, right = control.follow_command((x, 0, 40, height), 640, 480)
                for value in (left, right):
                    self.assertTrue(value == 0 or .18 <= abs(value) <= .65)
        self.assertEqual(control.follow_command(None, 640, 480), (0, 0))
