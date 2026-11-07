"""Exclusive, expiring browser control lease; never writes hardware directly."""
import math
import secrets
import threading
import time

from robot_control import single_stick


class Teleop:
    TIMEOUT = .4
    MAX_SPEED = .65

    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        with self.lock:
            self.owner = None
            self.deadline = 0.0
            self.sequence = -1
            self.axes = (0.0, 0.0)
            self.dump = 0.0
            self.stop_requested = False

    def take_stop(self):
        with self.lock:
            stop = self.stop_requested
            self.stop_requested = False
            return stop

    def _expire(self, now):
        if self.owner and now >= self.deadline:
            self.stop_requested = True
            self.owner = None
            self.axes = (0.0, 0.0)
            self.dump = 0.0

    def enable(self, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            self._expire(now)
            if self.owner:
                raise ValueError('Another browser is controlling the robot')
            self.stop_requested = False
            self.owner = secrets.token_urlsafe(24)
            self.deadline = now + self.TIMEOUT
            self.sequence = -1
            self.axes = (0.0, 0.0)
            self.dump = 0.0
            return self.owner

    def command(self, owner, sequence, x, forward, now=None, dump=0):
        now = time.monotonic() if now is None else now
        if type(sequence) is not int or sequence < 0:
            raise ValueError('Invalid sequence')
        if any(type(v) not in (float, int) or not math.isfinite(v) or abs(v) > 1 for v in (x, forward)):
            raise ValueError('Joystick values must be finite and between -1 and 1')
        if type(dump) not in (int, float) or dump not in (-1, 0, 1):
            raise ValueError('Dump command must be -1, 0, or 1')
        with self.lock:
            self._expire(now)
            if not self.owner or not secrets.compare_digest(str(owner), self.owner):
                raise ValueError('Control disabled or expired; enable again')
            if sequence <= self.sequence:
                return False  # A late packet is harmless; do not renew the lease.
            self.sequence = sequence
            self.axes = (x, forward)
            self.dump = float(dump)
            self.deadline = now + self.TIMEOUT
            return True

    def disable(self, owner):
        with self.lock:
            if self.owner and secrets.compare_digest(str(owner), self.owner):
                self.stop_requested = True
                self.owner = None
                self.axes = (0.0, 0.0)
                self.dump = 0.0

    def outputs(self, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            self._expire(now)
            if not self.owner:
                return None
            x, forward = self.axes
            dump = self.dump
        left, right = single_stick(x, forward, 0, 0)
        return left * self.MAX_SPEED, right * self.MAX_SPEED, dump

    def active(self):
        return self.outputs() is not None
