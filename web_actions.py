"""Bounded requests from the web page, executed only in the motor loop."""
import threading
import time


class WebActions:
    ALLOWED = {'stop', 'manual', 'single', 'follow', 'hotspot', 'wifi', 'shutdown', 'dump_up', 'dump_down', 'dump_stop'}

    def __init__(self):
        self.lock = threading.Lock()
        self.pending = None
        self.dump_value = 0
        self.dump_deadline = 0

    def manual_dump(self, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            return self.dump_value if now < self.dump_deadline else 0

    def clear(self):
        with self.lock:
            self.pending = None
            self.dump_value = 0
            self.dump_deadline = 0

    def request(self, action, controller_connected=False, confirmed=False, now=None):
        now = time.monotonic() if now is None else now
        if action not in self.ALLOWED:
            raise ValueError('Action is not available on the web page')
        if action == 'single' and not controller_connected:
            raise ValueError('Single-stick mode requires the Stadia controller; use web tele-operation instead')
        if action in ('follow', 'hotspot', 'wifi', 'shutdown') and confirmed is not True:
            raise ValueError('Slide to confirm this action')
        with self.lock:
            if action.startswith('dump_'):
                self.dump_value = {'dump_up': 1, 'dump_down': -1, 'dump_stop': 0}[action]
                self.dump_deadline = now + .4
                return
            self.dump_value = 0
            self.dump_deadline = 0
            if self.pending and now - self.pending[1] < 2 and action != 'stop':
                raise ValueError('A page action is already pending')
            self.pending = (action, now)

    def take(self, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            pending, self.pending = self.pending, None
        return pending[0] if pending and now - pending[1] < 2 else None
