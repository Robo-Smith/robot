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
    def setUp(self):
        self.enterContext(patch('controller_battery.read_upower', return_value=None))

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
        self.follower.request_preview.assert_called_once_with(detect=True)
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
        self.assertEqual(error.exception.code, 403)

    def post(self, action, body, origin=True, token=True):
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = self.base
        if token:
            headers['X-Robot-Control'] = self.dashboard.control_token
        request = urllib.request.Request(self.base + '/api/teleop/' + action,
                                         data=json.dumps(body).encode(), headers=headers, method='POST')
        return urllib.request.urlopen(request, timeout=2)

    def test_teleop_requires_same_origin_token_and_ready_robot(self):
        self.dashboard.update(teleop_ready=True)
        for origin, token in ((False, True), (True, False)):
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.post('enable', {}, origin, token)
            self.assertEqual(error.exception.code, 403)
        self.dashboard.update(teleop_ready=False)
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.post('enable', {})
        self.assertEqual(error.exception.code, 409)

    def test_enable_command_disable_without_stadia(self):
        self.dashboard.update(teleop_ready=True, connected=False)
        with self.post('enable', {}) as response:
            owner = json.load(response)['owner']
        with self.post('command', {'owner': owner, 'sequence': 1, 'x': 0, 'forward': 1}):
            pass
        self.assertEqual(self.dashboard.teleop.outputs(), (.65, .65, 0))
        with self.post('disable', {'owner': owner}):
            pass
        self.assertIsNone(self.dashboard.teleop.outputs())

    def test_session_token_is_not_in_status_and_page_has_request_token(self):
        with self.get('/') as response:
            page = response.read().decode()
        self.assertIn(self.dashboard.control_token, page)
        self.assertNotIn('__CONTROL_TOKEN__', page)
        with self.get('/api/status') as response:
            self.assertNotIn(self.dashboard.control_token, response.read().decode())

    def test_nano_telemetry_is_exposed_without_changing_motor_requests(self):
        self.dashboard.update(outputs=[.5, .5, 0], nano={
            'available': True, 'fresh': True, 'age_s': .1,
            'distance_cm': 15, 'signal': 1000, 'tof_state': 'stop',
            'applied_outputs': [0, 0, 0], 'watchdog': False})
        with self.get('/api/status') as response:
            data = json.load(response)
        self.assertEqual(data['outputs'], [.5, .5, 0])
        self.assertEqual(data['nano']['applied_outputs'], [0, 0, 0])
        self.assertEqual(data['nano']['distance_cm'], 15)
        self.assertIn('temperature_c', data['pi'])
        self.assertIn('uptime_s', data['pi'])

    def page_action(self, action, confirmed=False):
        request = urllib.request.Request(self.base + '/api/action', data=json.dumps({
            'action': action, 'confirmed': confirmed}).encode(),
            headers={'Origin': self.base, 'Content-Type': 'application/json',
                     'X-Robot-Control': self.dashboard.control_token}, method='POST')
        return urllib.request.urlopen(request, timeout=2)

    def test_page_modes_require_confirmation_and_single_requires_controller(self):
        self.dashboard.update(teleop_ready=True)
        for action in ('manual', 'wifi_off', 'single', 'follow'):
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.page_action(action)
            self.assertEqual(error.exception.code, 409)
        with self.page_action('follow', confirmed=True):
            pass
        self.assertEqual(self.dashboard.actions.take(), 'follow')

    def test_page_shutdown_is_queued_and_stop_can_override_it(self):
        self.dashboard.update(teleop_ready=True)
        with self.page_action('shutdown', confirmed=True):
            pass
        with self.page_action('stop'):
            pass
        self.assertEqual(self.dashboard.actions.take(), 'stop')

    def test_page_rejects_actions_when_robot_not_ready(self):
        self.dashboard.update(teleop_ready=False)
        with self.assertRaises(urllib.error.HTTPError):
            self.page_action('hotspot', confirmed=True)

    def test_http_dump_controls_follow_existing_enable_session(self):
        self.dashboard.update(teleop_ready=True)
        with self.post('enable', {}) as response:
            owner = json.load(response)['owner']
        for sequence, dump in enumerate((1, -1, 0), 1):
            with self.post('command', {'owner': owner, 'sequence': sequence, 'x': 0, 'forward': 0, 'dump': dump}):
                pass
            self.assertEqual(self.dashboard.teleop.outputs(), (0, 0, dump))

    def test_late_control_request_is_ignored_without_ending_active_session(self):
        self.dashboard.update(teleop_ready=True)
        with self.post('enable', {}) as response:
            owner = json.load(response)['owner']
        with self.post('command', {'owner': owner, 'sequence': 3, 'x': 0, 'forward': 0}) as response:
            self.assertTrue(json.load(response)['accepted'])
        with self.post('command', {'owner': owner, 'sequence': 2, 'x': 1, 'forward': 1}) as response:
            self.assertFalse(json.load(response)['accepted'])
        self.assertEqual(self.dashboard.teleop.outputs(), (0, 0, 0))
