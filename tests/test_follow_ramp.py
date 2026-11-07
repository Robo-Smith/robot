import unittest

from robot_control import FollowRamp


class RampTests(unittest.TestCase):
    def test_acceleration_above_usable_minimum(self):
        ramp = FollowRamp()
        self.assertEqual(ramp.update(.65, .65, 0), (.18, .18))
        left, right = ramp.update(.65, .65, .1)
        self.assertAlmostEqual(left, .21)
        self.assertEqual(left, right)

    def test_normal_deceleration_is_faster(self):
        ramp = FollowRamp()
        for index in range(11):
            ramp.update(.65, .65, index * .1)
        self.assertAlmostEqual(ramp.outputs[0], .48)
        left, _ = ramp.update(.2, .2, 1.1)
        self.assertAlmostEqual(left, .42)

    def test_time_based_across_update_rates(self):
        results = []
        for dt, steps in ((.05, 20), (.1, 10)):
            ramp = FollowRamp()
            for index in range(steps + 1):
                ramp.update(.65, .65, index * dt)
            results.append(ramp.outputs)
        self.assertAlmostEqual(results[0][0], results[1][0])

    def test_reversal_passes_through_zero(self):
        ramp = FollowRamp()
        for index in range(11):
            ramp.update(.65, .65, index * .1)
        values = [ramp.update(-.65, .65, 1 + index * .1)[0] for index in range(1, 9)]
        self.assertIn(0, values)
        first_negative = next(index for index, value in enumerate(values) if value < 0)
        self.assertEqual(values[first_negative - 1], 0)
        self.assertAlmostEqual(values[first_negative], -.18)

    def test_safety_stop_is_immediate_and_restarts_from_rest(self):
        ramp = FollowRamp()
        for index in range(11):
            ramp.update(.65, .65, index * .1)
        self.assertEqual(ramp.update(0, 0, 1.01), (0, 0))
        self.assertEqual(ramp.update(.65, .65, 1.02), (.18, .18))

    def test_turning_minimum_and_wheel_limit(self):
        ramp = FollowRamp()
        self.assertEqual(ramp.update(.65, -.65, 0, .28), (.28, -.28))
        for index in range(1, 51):
            left, right = ramp.update(.65, -.65, index * .1, .28)
            self.assertTrue(.28 <= left <= .65)
            self.assertTrue(-.65 <= right <= -.28)
        self.assertEqual(ramp.outputs, (.65, -.65))

    def test_mode_reset_and_watchdog_length_pause_start_at_minimum(self):
        ramp = FollowRamp()
        for index in range(11):
            ramp.update(.65, .65, index * .1)
        self.assertEqual(ramp.update(.65, .65, 2), (.18, .18))
        ramp.reset()
        self.assertEqual(ramp.update(.65, -.65, 2.1, .28), (.28, -.28))

    def test_one_wheel_stops_without_stopping_other(self):
        ramp = FollowRamp()
        ramp.update(.3, .3, 0)
        left, right = ramp.update(0, .3, .1)
        self.assertEqual(left, 0)
        self.assertGreater(right, 0)
