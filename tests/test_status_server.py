import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.request

from controller_battery import read_battery
from status_server import Dashboard, RobotStatus


class BatteryTests(unittest.TestCase):
    def test_reads_only_matched_controller_and_converts_microvolts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unrelated = root / 'BAT0'
            unrelated.mkdir()
            (unrelated / 'capacity').write_text('99')
            supply = root / 'hid-aa:bb:cc:dd:ee:ff-battery'
            supply.mkdir()
            for key, value in {'capacity': '72', 'voltage_now': '3750000', 'status': 'Discharging'}.items():
                (supply / key).write_text(value)
            result = read_battery('aa:bb:cc:dd:ee:ff', 'Stadia', root)
            self.assertEqual(result, {'percent': 72, 'voltage': 3.75, 'status': 'Discharging'})
            self.assertIsNone(read_battery('11:22:33:44:55:66', 'Stadia', root)['percent'])

    def test_percentage_does_not_invent_voltage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            supply = root / 'stadia-battery'
            supply.mkdir()
            (supply / 'capacity').write_text('50')
            result = read_battery('', 'Google Stadia Controller', root)
            self.assertEqual(result['percent'], 50)
            self.assertIsNone(result['voltage'])
            (supply / 'capacity').write_text('999')
            self.assertIsNone(read_battery('', 'Stadia', root)['percent'])


class StatusTests(unittest.TestCase):
    def test_stalled_control_loop_is_marked_stale(self):
        status = RobotStatus()
        status.update(mode='follow', connected=True, outputs=[.4, .4, 0])
        self.assertTrue(status.snapshot()['live'])
        status.changed = time.monotonic() - 2
        self.assertFalse(status.snapshot()['live'])

    def test_battery_cached_and_cleared_on_disconnect(self):
        follower = Mock()
        follower.camera_status.return_value = {'state': 'idle', 'error': ''}
        dashboard = Dashboard(follower, port=0)
        dashboard.update(connected=True, controller_id='aa:bb:cc:dd:ee:ff', controller_name='Stadia')
        with patch('status_server.read_battery', return_value={'percent': 55, 'voltage': None}) as battery:
            self.assertEqual(dashboard.snapshot()['battery']['percent'], 55)
            self.assertNotIn('controller_id', dashboard.snapshot())
            self.assertEqual(battery.call_count, 1)
            dashboard.update(connected=False)
            self.assertIsNone(dashboard.snapshot()['battery']['percent'])


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.follower = Mock()
        self.follower.camera_status.return_value = {'state': 'preview', 'error': ''}
        self.follower.preview_jpeg.return_value = b'jpeg-fixture'
        # A real loopback server verifies routing and response behavior, not hardware.
        # Port 0 means disabled in production; bind via the OS-assigned ephemeral port.
        from status_server import ThreadingHTTPServer
        real_server = ThreadingHTTPServer
        with patch('status_server.ThreadingHTTPServer', side_effect=lambda address, handler:
                   real_server(('127.0.0.1', 0), handler)):
            self.dashboard = Dashboard(self.follower, host='127.0.0.1', port=8080)
        self.addCleanup(self.dashboard.close)
        self.base = f'http://127.0.0.1:{self.dashboard.server.server_port}'

    def get(self, path):
        return urllib.request.urlopen(self.base + path, timeout=2)

    def test_page_and_mode_json(self):
        with self.get('/') as response:
            self.assertIn(b'YardBot', response.read())
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.dashboard.update(mode='follow', connected=True, outputs=[.3, .2, 0])
        with patch('status_server.read_battery', return_value={'percent': None, 'voltage': None}):
            with self.get('/api/status') as response:
                data = json.load(response)
                self.assertEqual(data['mode'], 'follow')
                self.assertEqual(data['outputs'], [.3, .2, 0])

    def test_feed_uses_shared_camera_and_missing_frame_returns_unavailable(self):
        with self.get('/camera.jpg?t=1') as response:
            self.assertEqual(response.headers['Content-Type'], 'image/jpeg')
            self.assertEqual(response.read(), b'jpeg-fixture')
        self.follower.request_preview.assert_called_once()
        self.follower.preview_jpeg.return_value = None
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.get('/camera.jpg')
        self.assertEqual(error.exception.code, 503)

    def test_no_control_or_arbitrary_file_endpoints(self):
        for path in ('/api/shutdown', '/api/mode', '/../Pi.py'):
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.get(path)
            self.assertEqual(error.exception.code, 404)
        request = urllib.request.Request(self.base + '/api/status', data=b'{}', method='POST')
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request, timeout=2)
        self.assertEqual(error.exception.code, 501)
