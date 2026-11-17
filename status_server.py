"""LAN dashboard with explicit, leased web driving."""
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit

from controller_battery import read_battery
from teleop import Teleop
from web_actions import WebActions

PAGE = Path(__file__).resolve().parent / 'web' / 'index.html'


def pi_health():
    data = {'temperature_c': None, 'uptime_s': None}
    try:
        data['temperature_c'] = round(float(Path('/sys/class/thermal/thermal_zone0/temp').read_text()) / 1000, 1)
    except (OSError, ValueError):
        pass
    try:
        data['uptime_s'] = int(float(Path('/proc/uptime').read_text().split()[0]))
    except (OSError, ValueError, IndexError):
        pass
    return data


class RobotStatus:
    def __init__(self):
        self.lock = threading.Lock()
        self.changed = time.monotonic()
        self.data = {'mode': 'stop', 'connected': False, 'controller_name': '',
                     'controller_id': '', 'message': 'Waiting for controller',
                     'outputs': [0, 0, 0], 'teleop_ready': False,
                     'nano': {'available': False, 'fresh': False, 'age_s': None, 'tof_state': 'unavailable'}}

    def update(self, **values):
        with self.lock:
            self.data.update(values)
            self.changed = time.monotonic()

    def snapshot(self):
        with self.lock:
            data = dict(self.data)
            age = time.monotonic() - self.changed
        data['heartbeat_age'] = round(age, 2)
        data['live'] = age < 1.5
        return data


class Dashboard:
    def __init__(self, follower, host='0.0.0.0', port=8080):
        self.state = RobotStatus()
        self.teleop = Teleop()
        self.actions = WebActions()
        self.control_token = secrets.token_urlsafe(32)
        self.follower = follower
        self.server = None
        self.battery_lock = threading.Lock()
        self.battery_key = None
        self.battery_time = 0.0
        self.battery = {'percent': None, 'voltage': None, 'status': 'Not reported'}
        if port:
            dashboard = self
            class Handler(BaseHTTPRequestHandler):
                protocol_version = 'HTTP/1.1'

                def setup(self):
                    super().setup()
                    self.connection.settimeout(3)
                def do_GET(self):
                    path = urlsplit(self.path).path
                    if path == '/':
                        self.reply(200, 'text/html; charset=utf-8', PAGE.read_text().replace('__CONTROL_TOKEN__', dashboard.control_token).encode())
                    elif path in ('/teleop.js', '/telemetry.js', '/controls.js'):
                        self.reply(200, 'text/javascript; charset=utf-8', (PAGE.parent / path[1:]).read_bytes())
                    elif path == '/api/status':
                        self.reply(200, 'application/json', json.dumps(dashboard.snapshot()).encode())
                    elif path == '/camera.jpg':
                        dashboard.follower.request_preview(detect=True)
                        jpeg = dashboard.follower.preview_jpeg()
                        if jpeg is None:
                            self.reply(503, 'text/plain', b'Camera starting or unavailable')
                        else:
                            self.reply(200, 'image/jpeg', jpeg)
                    else:
                        self.reply(404, 'text/plain', b'Not found')

                def do_POST(self):
                    # Custom header + same-origin checks prevent cross-site form control.
                    origin = urlsplit(self.headers.get('Origin', ''))
                    if (origin.scheme not in ('http', 'https') or origin.netloc != self.headers.get('Host')
                            or not self.headers.get('X-Robot-Control', '').isascii()
                            or not secrets.compare_digest(self.headers.get('X-Robot-Control', ''), dashboard.control_token)):
                        self.reply(403, 'text/plain', b'Control requires the robot dashboard')
                        return
                    path = urlsplit(self.path).path
                    if path not in ('/api/teleop/enable', '/api/teleop/command', '/api/teleop/disable', '/api/action'):
                        self.reply(404, 'text/plain', b'Not found')
                        return
                    try:
                        length = int(self.headers.get('Content-Length', '0'))
                        if not 0 < length <= 1024:
                            raise ValueError('Invalid request size')
                        self.connection.settimeout(2)
                        data = json.loads(self.rfile.read(length))
                        if not isinstance(data, dict):
                            raise ValueError('Expected object')
                        if path == '/api/action':
                            state = dashboard.state.snapshot()
                            if not state['live'] or (not state['teleop_ready'] and data.get('action') != 'stop'):
                                raise ValueError('Robot is not ready for page controls')
                            if state.get('system_action', {}).get('busy') and data.get('action') != 'stop':
                                raise ValueError('A system action is already running')
                            if str(data.get('action', '')).startswith('dump_') and state.get('mode') not in ('manual', 'single'):
                                raise ValueError('Dump buttons require manual or single-stick mode')
                            dashboard.actions.request(data.get('action'), state['connected'], data.get('confirmed'))
                            result = {'accepted': True}
                        elif path.endswith('/disable'):
                            dashboard.teleop.disable(data.get('owner', ''))
                            result = {'enabled': False}
                        else:
                            state = dashboard.state.snapshot()
                            if not state['live'] or not state['teleop_ready']:
                                dashboard.teleop.reset()
                                raise ValueError('Robot is not ready for web driving')
                            if path.endswith('/enable'):
                                result = {'owner': dashboard.teleop.enable(), 'enabled': True}
                            else:
                                accepted = dashboard.teleop.command(data.get('owner', ''), data.get('sequence'),
                                                         data.get('x'), data.get('forward'), dump=data.get('dump', 0))
                                result = {'enabled': True, 'accepted': accepted}
                        self.reply(200, 'application/json', json.dumps(result).encode())
                    except (ValueError, TypeError, TimeoutError) as exc:
                        self.reply(409, 'text/plain', str(exc).encode())

                def reply(self, code, content_type, body):
                    try:
                        self.send_response(code)
                        if code >= 400:
                            self.close_connection = True
                            self.send_header('Connection', 'close')
                        self.send_header('Content-Type', content_type)
                        self.send_header('Content-Length', str(len(body)))
                        self.send_header('Cache-Control', 'no-store')
                        self.send_header('X-Content-Type-Options', 'nosniff')
                        self.end_headers()
                        self.wfile.write(body)
                    except (BrokenPipeError, ConnectionResetError):
                        pass

                def log_message(self, *args):
                    pass
            self.server = ThreadingHTTPServer((host, port), Handler)
            self.server.daemon_threads = True
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
            print(f'Robot status page listening on port {self.server.server_port}', flush=True)

    def update(self, **values):
        self.state.update(**values)

    def snapshot(self):
        data = self.state.snapshot()
        key = (data['connected'], data['controller_id'], data['controller_name'])
        with self.battery_lock:
            if key != self.battery_key or time.monotonic() - self.battery_time >= 10:
                self.battery = (read_battery(key[1], key[2]) if key[0] else
                                {'percent': None, 'voltage': None, 'status': 'Disconnected'})
                self.battery_key, self.battery_time = key, time.monotonic()
            data['battery'] = dict(self.battery)
        data.pop('controller_id', None)
        data['camera'] = self.follower.camera_status()
        data['teleop_active'] = self.teleop.active()
        data['pi'] = pi_health()
        return data

    def close(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()


def start_dashboard(follower):
    host = os.environ.get('ROBOT_STATUS_HOST', '0.0.0.0')
    port = int(os.environ.get('ROBOT_STATUS_PORT', '8080'))
    try:
        return Dashboard(follower, host, port)
    except OSError as exc:
        print(f'Status web server unavailable: {exc}; robot controls remain active', flush=True)
        return Dashboard(follower, port=0)
