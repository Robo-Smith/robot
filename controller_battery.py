"""Read controller telemetry when Linux exposes it; never invent a voltage."""
from pathlib import Path
import re
import os
import subprocess
import time


def read_battery(controller_id='', controller_name='', root=Path('/sys/class/power_supply')):
    result = {'percent': None, 'voltage': None, 'status': 'Not reported'}
    address = re.sub(r'[^a-z0-9]', '', controller_id.lower())
    for supply in root.glob('*'):
        def read(name):
            try:
                return (supply / name).read_text().strip()
            except OSError:
                return ''
        identity = ' '.join([supply.name, read('serial_number'), read('model_name')])
        normalized = re.sub(r'[^a-z0-9]', '', identity.lower())
        matches_id = len(address) >= 12 and address in normalized
        matches_name = 'stadia' in identity.lower() and 'stadia' in controller_name.lower()
        if not (matches_id or (not address and matches_name)):
            continue
        if read('present') == '0':
            continue
        try:
            capacity = int(read('capacity'))
            if 0 <= capacity <= 100:
                result['percent'] = capacity
        except ValueError:
            pass
        try:
            microvolts = int(read('voltage_now'))
            if microvolts > 0:
                result['voltage'] = microvolts / 1_000_000
        except ValueError:
            pass
        result['status'] = read('status') or 'Not reported'
        break
    if result['percent'] is None or result['voltage'] is None:
        reported = read_upower(controller_id, controller_name)
        if reported:
            for field in ('percent', 'voltage'):
                if result[field] is None:
                    result[field] = reported[field]
            if result['status'] == 'Not reported':
                result['status'] = reported['status']
    return result


def parse_upower(info):
    fields = {}
    for line in info.splitlines():
        key, separator, value = line.strip().partition(':')
        if separator:
            fields[key] = value.strip()
    if fields.get('present') == 'no':
        return None
    result = {'percent': None, 'voltage': None,
              'status': fields['state'].replace('-', ' ').capitalize() if fields.get('state') else 'Reported by UPower'}
    percent = re.fullmatch(r'(\d+(?:\.\d+)?)%', fields.get('percentage', ''))
    if percent and 0 <= float(percent[1]) <= 100:
        value = float(percent[1])
        result['percent'] = int(value) if value.is_integer() else value
    voltage = re.fullmatch(r'(\d+(?:\.\d+)?)\s*V', fields.get('voltage', ''))
    if voltage and float(voltage[1]) > 0:
        result['voltage'] = float(voltage[1])
    level = fields.get('battery-level', 'none')
    if level not in ('none', 'unknown'):
        result['percent'] = None  # Coarse levels must not be presented as measured percentages.
        result['status'] = level.capitalize()
    return result


def read_upower(controller_id='', controller_name=''):
    address = re.sub(r'[^a-z0-9]', '', controller_id.lower())
    if not address and 'stadia' not in controller_name.lower():
        return None
    deadline = time.monotonic() + 1.5
    def run(*args):
        timeout = deadline - time.monotonic()
        if timeout <= 0:
            raise subprocess.TimeoutExpired(args, 1.5)
        return subprocess.run(['upower', *args], capture_output=True, text=True,
                              check=True, timeout=timeout, env={**os.environ, 'LC_ALL': 'C'}).stdout
    try:
        for path in run('-e').splitlines()[:32]:
            path = path.strip()
            if not path.startswith('/org/freedesktop/UPower/devices/gaming_input_'):
                continue
            normalized_path = re.sub(r'[^a-z0-9]', '', path.lower())
            if address and (len(address) < 12 or address not in normalized_path):
                continue
            info = run('-i', path)
            # With no evdev identity, require Stadia identification in the device details.
            if not address and 'stadia' not in info.lower():
                continue
            return parse_upower(info)
    except (OSError, subprocess.SubprocessError):
        return None
    return None
