from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

from network_status import read_network


class NetworkTests(unittest.TestCase):
    def read(self, replies):
        run = Mock(side_effect=replies)
        result = read_network(run=run, settings_path=Path('/nonexistent-network-settings'))
        return result, run

    def test_wifi_off_does_not_report_hotspot(self):
        state, run = self.read(['disabled'])
        self.assertEqual(state, 'off')
        self.assertEqual(run.call_count, 1)

    def test_ap_and_client_modes_are_distinguished(self):
        self.assertEqual(self.read(['enabled', 'active-uuid', 'ap'])[0], 'hotspot')
        self.assertEqual(self.read(['enabled', 'active-uuid', 'infrastructure'])[0], 'wifi')
        self.assertEqual(self.read(['enabled', '--'])[0], 'disconnected')

    def test_failure_reports_unknown(self):
        self.assertEqual(self.read([subprocess.TimeoutExpired('nmcli', 2)])[0], 'unknown')
        self.assertEqual(self.read(['unexpected'])[0], 'unknown')

    def test_uses_configured_interface(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Path(directory) / 'settings.json'
            settings.write_text('{"interface": "wlan1"}')
            run = Mock(side_effect=['enabled', '--'])
            self.assertEqual(read_network(run, settings), 'disconnected')
            run.assert_called_with('-g', 'GENERAL.CON-UUID', 'device', 'show', 'wlan1')
