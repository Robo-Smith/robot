from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock
import uuid

from hotspot import Hotspot


class HotspotTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'hotspot_settings.json'
        self.run = Mock()
        self.hotspot = Hotspot(self.run, self.path)
        self.settings = self.hotspot.settings()
        self.home = str(uuid.uuid4())

    def configure_responses(self, active=None, fail=False, radio='enabled'):
        self.secret_files = []
        def execute(args):
            if args[:3] == ['nmcli', '-g', 'WIFI-PROPERTIES.AP']:
                return 'yes'
            if args[:3] == ['nmcli', '-g', 'connection.uuid']:
                return self.settings['uuid']
            if args[:3] == ['nmcli', '-g', 'GENERAL.CON-UUID']:
                return active or '--'
            if args == ['nmcli', '-t', '-f', 'WIFI', 'radio']:
                return radio
            if 'passwd-file' in args:
                path = Path(args[-1])
                self.secret_files.append(path)
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(path.read_text(), '802-11-wireless-security.psk:' + self.settings['password'] + '\n')
                self.assertNotIn(self.settings['password'], args)
                if fail:
                    raise subprocess.CalledProcessError(4, args, stderr='Activation failed')
            return ''
        self.run.side_effect = execute

    def test_generated_settings_are_private_and_password_is_stable(self):
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertGreaterEqual(len(self.settings['password']), 16)
        self.assertEqual(self.hotspot.settings()['password'], self.settings['password'])

    def test_setup_creates_secure_profile_without_activating_radio(self):
        def execute(args):
            if 'WIFI-PROPERTIES.AP' in args:
                return 'yes'
            if args[:3] == ['nmcli', '-g', 'connection.uuid']:
                raise subprocess.CalledProcessError(10, args)
            return ''
        self.run.side_effect = execute
        self.hotspot.prepare()
        args = self.run.call_args.args[0]
        self.assertIn('add', args)
        self.assertIn('wpa-psk', args)
        self.assertIn('rsn', args)
        self.assertIn('ccmp', args)
        self.assertIn('10.42.0.1/24', args)
        self.assertNotIn(self.settings['password'], args)
        self.assertEqual(args[args.index('connection.autoconnect') + 1], 'no')
        self.assertTrue(all('up' not in call.args[0] for call in self.run.call_args_list))

    def test_enter_hotspot_remembers_home_and_removes_temporary_secret(self):
        self.configure_responses(active=self.home)
        self.hotspot.toggle()
        self.assertEqual(self.hotspot.settings()['previous_uuid'], self.home)
        self.assertEqual(len(self.secret_files), 1)
        self.assertFalse(self.secret_files[0].exists())

    def test_exit_restores_previous_connection_even_after_restart(self):
        self.settings['previous_uuid'] = self.home
        self.hotspot._save(self.settings)
        self.configure_responses(active=self.settings['uuid'])
        Hotspot(self.run, self.path).toggle()
        calls = [call.args[0] for call in self.run.call_args_list]
        self.assertIn(['nmcli', '--wait', '10', 'connection', 'down', 'uuid', self.settings['uuid']], calls)
        self.assertIn(['nmcli', '--wait', '10', 'connection', 'up', 'uuid', self.home, 'ifname', 'wlan0'], calls)

    def test_failed_activation_restores_home_and_deletes_secret(self):
        self.configure_responses(active=self.home, fail=True)
        with self.assertRaises(subprocess.CalledProcessError):
            self.hotspot.toggle()
        self.assertEqual(self.run.call_args.args[0],
                         ['nmcli', '--wait', '10', 'connection', 'up', 'uuid', self.home, 'ifname', 'wlan0'])
        self.assertFalse(self.secret_files[0].exists())

    def test_wifi_off_is_restored_if_activation_fails(self):
        self.configure_responses(fail=True, radio='disabled')
        with self.assertRaises(subprocess.CalledProcessError):
            self.hotspot.toggle()
        self.assertEqual(self.run.call_args.args[0], ['nmcli', '--wait', '10', 'radio', 'wifi', 'off'])

    def test_publicly_readable_credentials_are_rejected(self):
        self.path.chmod(0o644)
        with self.assertRaises(RuntimeError):
            self.hotspot.settings()

    def test_missing_ap_support_does_not_change_network(self):
        self.run.return_value = 'no'
        with self.assertRaises(RuntimeError):
            self.hotspot.prepare()
        self.assertEqual(self.run.call_count, 1)
