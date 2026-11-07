import unittest
from unittest.mock import patch

from robot_control import FollowSteering, FollowRamp, follow_command


class SteeringTests(unittest.TestCase):
    def test_center_jitter_does_not_start_turns(self):
        steering = FollowSteering()
        for error in (.09, -.11, .16, -.17, .02):
            self.assertEqual(steering.filter(error), 0)

    def test_hysteresis_releases_early_and_does_not_chatter(self):
        steering = FollowSteering()
        self.assertEqual(steering.filter(.25), .25)
        self.assertEqual(steering.filter(.12), .12)
        self.assertEqual(steering.filter(.07), 0)
        self.assertEqual(steering.filter(-.12), 0)
        self.assertEqual(steering.filter(-.20), -.20)

    def test_pivot_requires_large_error_and_exits_before_center(self):
        steering = FollowSteering()
        with patch('robot_control.FOLLOW_TARGET_SIZE', .44), patch('robot_control.FOLLOW_SIZE_METRIC', 'width'):
            left, right = follow_command((560, 0, 60, 200), 640, 480, steering)
            self.assertTrue(steering.pivot)
            self.assertGreater(left, 0)
            self.assertLess(right, 0)
            left, right = follow_command((390, 0, 60, 200), 640, 480, steering)
            self.assertFalse(steering.pivot)
            self.assertGreaterEqual(left, 0)
            self.assertGreaterEqual(right, 0)
            self.assertEqual(follow_command(None, 640, 480, steering), (0, 0))
            self.assertEqual(steering.direction, 0)

    def test_centered_target_clears_old_pivot_without_residual_spin(self):
        ramp = FollowRamp()
        ramp.update(.4, -.4, 0, .28)
        left, right = ramp.update(.4, .4, .05)
        self.assertEqual(left, right)
        self.assertGreaterEqual(left, 0)

    def test_opposite_correction_drops_old_turn_before_ramping(self):
        ramp = FollowRamp()
        for index in range(6):
            ramp.update(.6, .25, index * .1)
        left, right = ramp.update(.25, .6, .6)
        self.assertLessEqual(left, right)
        self.assertGreaterEqual(left, 0)


    def test_pivot_commands_restore_pre_boost_strength(self):
        with patch('robot_control.FOLLOW_TARGET_SIZE', .44), patch('robot_control.FOLLOW_SIZE_METRIC', 'width'):
            box = (560, 0, 60, 200)
            updated = follow_command(box, 640, 480)
            with patch('robot_control.FOLLOW_MIN_TURN', .39), patch('robot_control.FOLLOW_MAX_TURN', .52):
                previous = follow_command(box, 640, 480)
            self.assertAlmostEqual(updated[0], previous[0] / 1.3)
            self.assertAlmostEqual(updated[1], previous[1] / 1.3)

    def test_forward_arc_has_reduced_differential_without_reversing(self):
        with patch('robot_control.FOLLOW_TARGET_SIZE', .44), patch('robot_control.FOLLOW_SIZE_METRIC', 'width'):
            box = (368, 0, 120, 200)
            left, right = follow_command(box, 640, 480)
            with patch('robot_control.FOLLOW_ARC_STEERING_GAIN', 1.105):
                old_left, old_right = follow_command(box, 640, 480)
            self.assertAlmostEqual(left - right, (old_left - old_right) / 1.3)
            self.assertGreater(right, 0)


    def test_steering_reduction_preserves_fast_centered_forward_speed(self):
        with patch('robot_control.FOLLOW_TARGET_SIZE', .44), patch('robot_control.FOLLOW_SIZE_METRIC', 'width'):
            left, right = follow_command((288, 0, 64, 200), 640, 480)
            self.assertEqual((left, right), (.845, .845))
