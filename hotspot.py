"""Password-protected NetworkManager hotspot, activated only on explicit request."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import uuid

SETTINGS = Path(__file__).resolve().parent / 'hotspot_settings.json'
ADDRESS = '10.42.0.1/24'
URL = 'http://10.42.0.1:8080'


def command(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=20, check=True,
                            env={**os.environ, 'LC_ALL': 'C'})
    return result.stdout.strip()


class Hotspot:
    def __init__(self, run=command, path=SETTINGS):
        self.run = run
        self.path = path

    def _save(self, settings):
        descriptor, temporary = tempfile.mkstemp(prefix='.hotspot-', dir=self.path.parent)
        try:
            with os.fdopen(descriptor, 'w') as output:
                json.dump(settings, output, indent=2)
                output.write('\n')
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def settings(self):
        if not self.path.exists():
            self._save({'ssid': 'YardBot', 'interface': 'wlan0',
                        'password': secrets.token_urlsafe(18), 'uuid': str(uuid.uuid4()),
                        'previous_uuid': None})
        if self.path.stat().st_mode & 0o077:
            raise RuntimeError('hotspot_settings.json must have permission 600 (chmod 600)')
        settings = json.loads(self.path.read_text())
        if not re.fullmatch(r'[a-zA-Z0-9_.-]+', settings['interface']):
            raise ValueError('Invalid hotspot interface')
        if not 1 <= len(settings['ssid'].encode()) <= 32 or any(c in settings['ssid'] for c in '\n\r\0'):
            raise ValueError('Hotspot SSID must be 1–32 bytes without control characters')
        password = settings['password']
        if not 8 <= len(password) <= 63 or not all(32 <= ord(c) < 127 for c in password):
            raise ValueError('Hotspot password must be 8–63 printable ASCII characters')
        uuid.UUID(settings['uuid'])
        if settings.get('previous_uuid'):
            uuid.UUID(settings['previous_uuid'])
        return settings

    def prepare(self):
        settings = self.settings()
        interface = settings['interface']
        if self.run(['nmcli', '-g', 'WIFI-PROPERTIES.AP', 'device', 'show', interface]) != 'yes':
            raise RuntimeError(f'{interface} does not report Wi-Fi access-point support')
        try:
            self.run(['nmcli', '-g', 'connection.uuid', 'connection', 'show', 'uuid', settings['uuid']])
        except subprocess.CalledProcessError as exc:
            if exc.returncode != 10:  # nmcli: connection does not exist
                raise
            self.run(['nmcli', 'connection', 'add', 'type', 'wifi',
                      'ifname', interface, 'con-name', 'YardBot Hotspot',
                      'connection.uuid', settings['uuid'], 'connection.autoconnect', 'no',
                      '802-11-wireless.ssid', settings['ssid'], '802-11-wireless.mode', 'ap',
                      '802-11-wireless.band', 'bg',
                      '802-11-wireless-security.key-mgmt', 'wpa-psk',
                      '802-11-wireless-security.proto', 'rsn',
                      '802-11-wireless-security.pairwise', 'ccmp',
                      '802-11-wireless-security.group', 'ccmp',
                      '802-11-wireless-security.wps-method', 'disabled',
                      '802-11-wireless-security.psk-flags', '2',
                      'ipv4.method', 'shared', 'ipv4.addresses', ADDRESS,
                      'ipv6.method', 'disabled'])
        return settings

    def _active(self, interface):
        value = self.run(['nmcli', '-g', 'GENERAL.CON-UUID', 'device', 'show', interface])
        try:
            return str(uuid.UUID(value))
        except ValueError:
            return None

    def toggle(self):
        settings = self.prepare()
        interface = settings['interface']
        active = self._active(interface)
        if active == settings['uuid']:
            self.run(['nmcli', '--wait', '10', 'connection', 'down', 'uuid', settings['uuid']])
            if settings.get('previous_uuid'):
                self.run(['nmcli', '--wait', '10', 'connection', 'up', 'uuid', settings['previous_uuid'],
                          'ifname', interface])
                print('Hotspot stopped; previous Wi-Fi connection restored', flush=True)
            else:
                self.run(['nmcli', '--wait', '10', 'device', 'connect', interface])
                print('Hotspot stopped; reconnecting saved Wi-Fi', flush=True)
            return
        original_radio = self.run(['nmcli', '-t', '-f', 'WIFI', 'radio'])
        if original_radio not in ('enabled', 'disabled'):
            raise RuntimeError(f'Unexpected Wi-Fi radio state: {original_radio!r}')
        if active:
            settings['previous_uuid'] = active
        self._save(settings)
        # Pass the secret through a private temporary file, never command arguments/logs.
        descriptor, password_file = tempfile.mkstemp(prefix='yardbot-wifi-')
        try:
            with os.fdopen(descriptor, 'w') as output:
                output.write('802-11-wireless-security.psk:' + settings['password'] + '\n')
            self.run(['nmcli', '--wait', '10', 'radio', 'wifi', 'on'])
            self.run(['nmcli', '--wait', '10', 'connection', 'up', 'uuid', settings['uuid'],
                      'ifname', interface, 'passwd-file', password_file])
        except (OSError, subprocess.SubprocessError):
            try:
                if original_radio == 'disabled':
                    self.run(['nmcli', '--wait', '10', 'radio', 'wifi', 'off'])
                elif active:
                    self.run(['nmcli', '--wait', '10', 'connection', 'up', 'uuid', active, 'ifname', interface])
            except (OSError, subprocess.SubprocessError):
                print('Could not restore previous Wi-Fi after hotspot activation failed', flush=True)
            raise
        finally:
            os.unlink(password_file)
        print(f'Hotspot {settings["ssid"]} active; join it and open {URL}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--setup', action='store_true', help='Prepare inactive profile; do not disconnect Wi-Fi')
    choice.add_argument('--show-password', action='store_true', help='Display credentials locally; never shared via HTTP')
    args = parser.parse_args()
    hotspot = Hotspot()
    if args.setup:
        settings = hotspot.prepare()
        print(f'Hotspot profile ready: {settings["ssid"]}. No connections changed. Address: {URL}')
        print('Use --show-password locally to see the generated Wi-Fi password.')
    else:
        settings = hotspot.settings()
        print(f'Network: {settings["ssid"]}\nPassword: {settings["password"]}\nStatus page: {URL}')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        detail = getattr(exc, 'stderr', None) or str(exc)
        raise SystemExit('Hotspot setup failed: ' + detail.strip())
