from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from hotspot import Hotspot, startup_fallback


class BootFallbackTests(unittest.TestCase):
    def fake(self, connected=lambda: False, initial=0):
        clock = [float(initial)]
        hotspot = Mock()
        hotspot.settings.return_value = {'interface': 'wlan0'}
        hotspot.wifi_connected.side_effect = lambda settings: connected()
        hotspot.run.return_value = 'enabled'
        hotspot.start_if_disconnected.return_value = True
        def wait(seconds):
            clock[0] += seconds
        return hotspot, clock, wait

    def test_disconnected_boot_starts_at_thirty_seconds(self):
        hotspot, clock, wait = self.fake()
        self.assertTrue(startup_fallback(hotspot, lambda: clock[0], wait))
        self.assertEqual(clock[0], 30)
        hotspot.start_if_disconnected.assert_called_once()

    def test_connection_during_grace_period_cancels_fallback(self):
        hotspot, clock, wait = self.fake()
        hotspot.wifi_connected.side_effect = lambda settings: clock[0] >= 12
        self.assertFalse(startup_fallback(hotspot, lambda: clock[0], wait))
        self.assertEqual(clock[0], 12)
        hotspot.start_if_disconnected.assert_not_called()

    def test_late_service_start_uses_boot_uptime_not_another_thirty_seconds(self):
        hotspot, clock, wait = self.fake(initial=18)
        startup_fallback(hotspot, lambda: clock[0], wait)
        self.assertEqual(clock[0], 30)

    def test_already_connected_network_or_hotspot_is_left_alone(self):
        hotspot, clock, wait = self.fake(connected=lambda: True, initial=30)
        self.assertFalse(startup_fallback(hotspot, lambda: clock[0], wait))
        hotspot.start_if_disconnected.assert_not_called()

    def test_deliberate_radio_off_cancels_fallback(self):
        hotspot, clock, wait = self.fake()
        hotspot.run.side_effect = lambda args: 'disabled' if clock[0] >= 5 else 'enabled'
        self.assertFalse(startup_fallback(hotspot, lambda: clock[0], wait))
        self.assertEqual(clock[0], 5)
        hotspot.start_if_disconnected.assert_not_called()

    def test_idempotent_start_rechecks_network_before_activation(self):
        with tempfile.TemporaryDirectory() as directory:
            hotspot = Hotspot(path=Path(directory) / 'settings.json')
            hotspot.settings = Mock(return_value={'interface': 'wlan0'})
            hotspot.wifi_connected = Mock(return_value=True)
            hotspot.prepare = Mock()
            self.assertFalse(hotspot.start_if_disconnected())
            hotspot.prepare.assert_not_called()

    def test_disconnected_activation_does_not_use_toggle(self):
        with tempfile.TemporaryDirectory() as directory:
            hotspot = Hotspot(path=Path(directory) / 'settings.json')
            settings = {'interface': 'wlan0', 'uuid': 'own-hotspot'}
            hotspot.settings = Mock(return_value=settings)
            hotspot.wifi_connected = Mock(return_value=False)
            hotspot.prepare = Mock(return_value=settings)
            hotspot._active = Mock(return_value=None)
            hotspot._activate = Mock()
            self.assertTrue(hotspot.start_if_disconnected())
            hotspot._activate.assert_called_once_with(settings, None)


    def test_connected_log_records_boot_relative_observation_time(self):
        hotspot, clock, wait = self.fake()
        hotspot.wifi_connected.side_effect = lambda settings: clock[0] >= 12
        with patch('builtins.print') as log:
            startup_fallback(hotspot, lambda: clock[0], wait)
        lines = [call.args[0] for call in log.call_args_list]
        self.assertTrue(any('[boot +12.0s]' in line and 'Wi-Fi connected' in line for line in lines))

    def test_hotspot_log_records_activation_duration(self):
        hotspot, clock, wait = self.fake()
        def activate():
            self.assertEqual(clock[0], 30)
            clock[0] += 2.5
            return True
        hotspot.start_if_disconnected.side_effect = activate
        with patch('builtins.print') as log:
            startup_fallback(hotspot, lambda: clock[0], wait)
        lines = [call.args[0] for call in log.call_args_list]
        self.assertTrue(any('[boot +32.5s]' in line and 'activation took 2.5s' in line for line in lines))
