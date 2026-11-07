"""Bounded requests from the web page, executed only in the motor loop."""
import threading
import time


class WebActions:
    ALLOWED = {'stop', 'single', 'follow', 'hotspot', 'shutdown'}

    def __init__(self):
        self.lock = threading.Lock()
        self.pending = None

    def clear(self):
        with self.lock:
            self.pending = None

    def request(self, action, controller_connected=False, confirmed=False, now=None):
        now = time.monotonic() if now is None else now
        if action not in self.ALLOWED:
            raise ValueError('Action is not available on the web page')
        if action == 'single' and not controller_connected:
            raise ValueError('Single-stick mode requires the Stadia controller; use web tele-operation instead')
        if action in ('follow', 'hotspot', 'shutdown') and confirmed is not True:
            raise ValueError('Slide to confirm this action')
        with self.lock:
            if self.pending and now - self.pending[1] < 2 and action != 'stop':
                raise ValueError('A page action is already pending')
            self.pending = (action, now)

    def take(self, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            pending, self.pending = self.pending, None
        return pending[0] if pending and now - pending[1] < 2 else None
