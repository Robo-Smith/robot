import subprocess
import unittest
from unittest.mock import Mock, patch

from controller_actions import DpadHolds, SystemActions


class HoldTests(unittest.TestCase):
    def test_all_actions_fire_only_after_three_seconds(self):
        for axis, value, action in [('y', 1, 'shutdown'), ('x', 1, 'wifi'), ('x', -1, 'hotspot')]:
            holds = DpadHolds()
            holds.update('hat', axis, value, 10)
            self.assertIsNone(holds.poll(12.99))
            self.assertEqual(holds.poll(13), action)
            self.assertIsNone(holds.poll(20))

    def test_release_and_repress_rearms(self):
        holds = DpadHolds()
        holds.update('hat', 'x', 1, 0)
        self.assertEqual(holds.poll(3), 'wifi')
        holds.update('hat', 'x', 0, 4)
        holds.update('hat', 'x', 1, 5)
        self.assertIsNone(holds.poll(7.99))
        self.assertEqual(holds.poll(8), 'wifi')

    def test_short_hold_and_diagonal_cancel(self):
        holds = DpadHolds()
        holds.update('hat', 'y', 1, 0)
        holds.update('hat', 'y', 0, 2)
        self.assertIsNone(holds.poll(5))
        holds.update('hat', 'y', 1, 6)
        holds.update('hat', 'x', 1, 8)
        self.assertIsNone(holds.poll(12))
        holds.update('hat', 'x', 0, 13)
        self.assertIsNone(holds.poll(15))
        self.assertEqual(holds.poll(16), 'shutdown')

    def test_button_repeat_does_not_restart_timer_or_retrigger(self):
        holds = DpadHolds()
        holds.update('key', 'left', 1, 0)
        holds.update('key', 'left', 2, 2)
        self.assertEqual(holds.poll(3), 'hotspot')
        holds.update('key', 'left', 2, 4)
        self.assertIsNone(holds.poll(8))

    def test_overflow_requires_release_and_fresh_hold(self):
        holds = DpadHolds()
        holds.update('hat', 'y', 1, 0)
        holds.reset(require_release=True)
        holds.update('hat', 'y', 1, 3)
        self.assertIsNone(holds.poll(7))
        holds.update('hat', 'y', 0, 8)
        holds.update('hat', 'y', 1, 9)
        self.assertEqual(holds.poll(12), 'shutdown')


class SystemActionTests(unittest.TestCase):
    def run_action(self, action, command):
        actions = SystemActions()
        # Test the worker synchronously with every OS operation mocked.
        actions.lock.acquire()
        with patch.object(actions, '_command', command):
            actions._run(action)
        self.assertFalse(actions.lock.locked())
        return actions

    def test_wifi_toggles_in_both_directions(self):
        for current, target in [('enabled', 'off'), ('disabled', 'on')]:
            command = Mock(side_effect=[current, ''])
            self.run_action('wifi', command)
            self.assertEqual(command.call_args_list[0].args[0], ['nmcli', '-t', '-f', 'WIFI', 'radio'])
            self.assertEqual(command.call_args_list[1].args[0], ['nmcli', '--wait', '10', 'radio', 'wifi', target])

    def test_unknown_wifi_state_does_not_change_radio(self):
        command = Mock(return_value='unavailable')
        self.run_action('wifi', command)
        self.assertEqual(command.call_count, 1)

    def test_hotspot_placeholder_never_runs_a_command(self):
        command = Mock()
        self.run_action('hotspot', command)
        command.assert_not_called()

    def test_shutdown_failure_releases_pending_state(self):
        actions = SystemActions()
        actions.shutdown_pending.set()
        actions.lock.acquire()
        with patch.object(actions, '_command', side_effect=subprocess.CalledProcessError(1, 'systemctl', stderr='Denied')):
            actions._run('shutdown')
        self.assertFalse(actions.shutdown_pending.is_set())
        self.assertFalse(actions.lock.locked())

    def test_busy_action_does_not_start_another_worker(self):
        actions = SystemActions()
        actions.lock.acquire()
        with patch('controller_actions.threading.Thread') as thread:
            self.assertFalse(actions.submit('wifi'))
            thread.assert_not_called()
        actions.lock.release()
