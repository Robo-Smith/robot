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
        self.assertFalse(self.control.command(owner, 1, 1, 1, now=.2))
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

    def test_dump_and_lower_require_valid_enabled_session(self):
        owner = self.control.enable(now=0)
        self.control.command(owner, 1, 0, 0, now=.1, dump=1)
        self.assertEqual(self.control.outputs(now=.2), (0, 0, 1))
        self.control.command(owner, 2, 0, 0, now=.2, dump=-1)
        self.assertEqual(self.control.outputs(now=.3), (0, 0, -1))
        self.control.command(owner, 3, 0, 0, now=.3, dump=0)
        self.assertEqual(self.control.outputs(now=.4), (0, 0, 0))

    def test_expiry_disable_and_mode_override_stop_dump(self):
        for method in ('expiry', 'disable', 'reset'):
            control = Teleop()
            owner = control.enable(now=0)
            control.command(owner, 1, 0, 0, now=.1, dump=1)
            if method == 'disable':
                control.disable(owner)
            elif method == 'reset':
                control.reset()
            self.assertIsNone(control.outputs(now=.6))
            self.assertEqual(control.dump, 0)

    def test_dump_validation_and_out_of_order_release(self):
        owner = self.control.enable(now=0)
        for value in (True, 2, .5, float('nan'), '1'):
            with self.assertRaises(ValueError):
                self.control.command(owner, 1, 0, 0, now=.1, dump=value)
        self.control.command(owner, 2, 0, 0, now=.1, dump=0)
        self.assertFalse(self.control.command(owner, 1, 0, 0, now=.2, dump=1))
        self.assertEqual(self.control.outputs(now=.3), (0, 0, 0))

    def test_delayed_commands_are_ignored_without_extending_lease(self):
        owner = self.control.enable(now=0)
        self.assertTrue(self.control.command(owner, 3, 0, 0, now=.1, dump=0))
        self.assertFalse(self.control.command(owner, 2, 1, 1, now=.3, dump=1))
        self.assertEqual(self.control.outputs(now=.35), (0, 0, 0))
        self.assertIsNone(self.control.outputs(now=.51))
