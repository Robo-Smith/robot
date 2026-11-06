import unittest
from unittest.mock import patch
from robot_control import single_stick, follow_command, controller_command


class ControlTests(unittest.TestCase):
    def setUp(self):
        # Local robot calibration must not change test scenarios.
        self.enterContext(patch('robot_control.FOLLOW_SIZE_METRIC', 'height'))
        self.enterContext(patch('robot_control.FOLLOW_TARGET_SIZE', .65))

    def test_manual_independent_drives_and_triggers(self):
        self.assertEqual(controller_command('manual', 1, .5, -1, -.25, .2, .8),
                         (.5, -.25, .8 - .2))

    def test_stop_ignores_all_inputs(self):
        self.assertEqual(controller_command('stop', 1, 1, 1, 1, 0, 1), (0, 0, 0))

    def test_single_keeps_dump_controls(self):
        self.assertEqual(controller_command('single', 0, .4, 0, .4, 1, 0),
                         (.8, .8, -1))

    def test_switch_from_stop_to_manual(self):
        inputs = (0, .5, 0, -.5, 0, 1)
        self.assertEqual(controller_command('stop', *inputs), (0, 0, 0))
        self.assertEqual(controller_command('manual', *inputs), (.5, -.5, 1))

    def test_follow_ignores_dump_triggers(self):
        self.assertEqual(controller_command('follow', 1, 1, 1, 1, 0, 1), (0, 0, 0))

    def test_either_stick_and_handoff(self):
        self.assertEqual(single_stick(0, .7, 0, 0), (.7, .7))
        self.assertEqual(single_stick(0, .35, 0, .35), (.7, .7))
        self.assertEqual(single_stick(0, 0, 0, .7), (.7, .7))

    def test_sum_clamps_and_opposition_cancels(self):
        self.assertEqual(single_stick(0, 1, 0, 1), (1, 1))
        self.assertEqual(single_stick(0, 1, 0, -1), (0, 0))
        self.assertEqual(single_stick(1, 0, 0, 0), (1, -1))

    def test_follow_stops_on_loss_or_close_person(self):
        self.assertEqual(follow_command(None, 640, 480), (0, 0))
        self.assertEqual(follow_command((200, 0, 200, 400), 640, 480), (0, 0))

    def test_follow_direction_and_limit(self):
        left, right = follow_command((280, 0, 80, 100), 640, 480)
        self.assertGreater(left, 0)
        self.assertEqual(left, right)
        left, right = follow_command((500, 0, 80, 100), 640, 480)
        self.assertGreater(left, right)
        self.assertLessEqual(max(abs(left), abs(right)), .65)


if __name__ == '__main__':
    unittest.main()
