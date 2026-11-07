"""Read-only LAN dashboard. No web endpoint changes robot or network state."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit

from controller_battery import read_battery

PAGE = Path(__file__).resolve().parent / 'web' / 'index.html'


class RobotStatus:
    def __init__(self):
        self.lock = threading.Lock()
        self.changed = time.monotonic()
        self.data = {'mode': 'stop', 'connected': False, 'controller_name': '',
                     'controller_id': '', 'message': 'Waiting for controller',
                     'outputs': [0, 0, 0]}

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
        self.follower = follower
        self.server = None
        self.battery_lock = threading.Lock()
        self.battery_key = None
        self.battery_time = 0.0
        self.battery = {'percent': None, 'voltage': None, 'status': 'Not reported'}
        if port:
            dashboard = self
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    path = urlsplit(self.path).path
                    if path == '/':
                        self.reply(200, 'text/html; charset=utf-8', PAGE.read_bytes())
                    elif path == '/api/status':
                        self.reply(200, 'application/json', json.dumps(dashboard.snapshot()).encode())
                    elif path == '/camera.jpg':
                        dashboard.follower.request_preview()
                        jpeg = dashboard.follower.preview_jpeg()
                        if jpeg is None:
                            self.reply(503, 'text/plain', b'Camera starting or unavailable')
                        else:
                            self.reply(200, 'image/jpeg', jpeg)
                    else:
                        self.reply(404, 'text/plain', b'Not found')

                def reply(self, code, content_type, body):
                    try:
                        self.send_response(code)
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
