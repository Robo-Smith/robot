"""Read controller telemetry when Linux exposes it; never invent a voltage."""
from pathlib import Path
import re


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
    return result
