"""Read-only NetworkManager status, polled separately from robot controls."""
import json
import os
from pathlib import Path
import subprocess
import threading

from hotspot import SETTINGS


def nmcli(*args):
    return subprocess.run(['nmcli', *args], capture_output=True, text=True,
                          timeout=2, check=True, env={**os.environ, 'LC_ALL': 'C'}).stdout.strip()


def read_network(run=nmcli, settings_path=SETTINGS):
    try:
        radio = run('-t', '-f', 'WIFI', 'radio')
        if radio == 'disabled':
            return 'off'
        if radio != 'enabled':
            return 'unknown'
        interface = 'wlan0'
        try:
            interface = json.loads(Path(settings_path).read_text()).get('interface', interface)
        except (OSError, ValueError, AttributeError):
            # The backend may own the private settings file; default Pi radio is wlan0.
            pass
        active = run('-g', 'GENERAL.CON-UUID', 'device', 'show', interface)
        if active in ('', '--'):
            return 'disconnected'
        mode = run('-g', '802-11-wireless.mode', 'connection', 'show', 'uuid', active)
        if mode == 'ap':
            return 'hotspot'
        if mode in ('infrastructure', ''):
            return 'wifi'
        return 'unknown'
    except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError):
        return 'unknown'


class NetworkStatus:
    def __init__(self):
        self.state = 'unknown'
        self.closed = threading.Event()
        threading.Thread(target=self.worker, daemon=True).start()

    def worker(self):
        while not self.closed.is_set():
            self.state = read_network()
            self.closed.wait(2)

    def snapshot(self):
        return self.state

    def close(self):
        self.closed.set()
