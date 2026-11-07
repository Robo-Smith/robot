import unittest

from teleop import Teleop


class TeleopTests(unittest.TestCase):
    def setUp(self):
        self.control = Teleop()

    def test_enable_starts_neutral_and_only_one_owner(self):
        self.control.enable(now=0)
        self.assertEqual(self.control.outputs(now=.1), (0, 0, 0))
        with self.assertRaises(ValueError):
            self.control.enable(now=.1)

    def test_single_stick_outputs_are_capped_and_dump_stays_zero(self):
        owner = self.control.enable(now=0)
        self.control.command(owner, 1, 0, 1, now=.1)
        self.assertEqual(self.control.outputs(now=.2), (.65, .65, 0))
        self.control.command(owner, 2, 1, 0, now=.2)
        left, right, dump = self.control.outputs(now=.3)
        self.assertAlmostEqual(left, .455)
        self.assertAlmostEqual(right, -.455)
        self.assertEqual(dump, 0)

    def test_lost_heartbeat_revokes_lease_and_late_commands_cannot_restart(self):
        owner = self.control.enable(now=0)
        self.control.command(owner, 1, 0, 1, now=.1)
        self.assertIsNone(self.control.outputs(now=.6))
        self.assertTrue(self.control.take_stop())
        with self.assertRaises(ValueError):
            self.control.command(owner, 2, 0, 1, now=.6)
        new_owner = self.control.enable(now=.7)
        self.assertNotEqual(owner, new_owner)
        self.assertEqual(self.control.outputs(now=.8), (0, 0, 0))

    def test_release_zero_and_sequence_prevent_delayed_motion(self):
        owner = self.control.enable(now=0)
        self.control.command(owner, 2, 0, 0, now=.1)
        with self.assertRaises(ValueError):
            self.control.command(owner, 1, 1, 1, now=.2)
        self.assertEqual(self.control.outputs(now=.3), (0, 0, 0))

    def test_disable_and_physical_override_invalidate_old_session(self):
        owner = self.control.enable(now=0)
        self.control.disable(owner)
        self.assertTrue(self.control.take_stop())
        self.assertIsNone(self.control.outputs(now=.1))
        owner = self.control.enable(now=.2)
        self.control.reset()
        self.assertFalse(self.control.take_stop())
        with self.assertRaises(ValueError):
            self.control.command(owner, 1, 1, 1, now=.3)

    def test_rejects_invalid_values_and_wrong_owners(self):
        owner = self.control.enable(now=0)
        for value in (float('nan'), float('inf'), 2, True, '1', None):
            with self.assertRaises(ValueError):
                self.control.command(owner, 1, value, 0, now=.1)
        with self.assertRaises(ValueError):
            self.control.command('wrong-owner', 1, 1, 1, now=.1)
        self.control.disable('wrong-owner')
        self.assertEqual(self.control.outputs(now=.2), (0, 0, 0))
