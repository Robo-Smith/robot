"""Bounded nonblocking reader for Nano telemetry frames; no motor control."""
import time


class NanoTelemetry:
    def __init__(self):
        self.buffer = bytearray()
        self.discarding = False
        self.latest = None
        self.received = 0.0
        self.sonar = None
        self.sonar_received = 0.0

    def feed(self, data, now=None):
        now = time.monotonic() if now is None else now
        for byte in data:
            if byte == 10:
                if not self.discarding:
                    self._line(bytes(self.buffer), now)
                self.buffer.clear()
                self.discarding = False
            elif not self.discarding:
                if len(self.buffer) >= 128:
                    self.buffer.clear()
                    self.discarding = True
                else:
                    self.buffer.append(byte)

    def _line(self, line, now):
        if line.startswith(b'S'):
            try:
                parts = line[1:].split(b',')
                if len(parts) != 4:
                    return
                left, right, left_age, right_age = map(int, parts)
                if not all(0 <= value <= 200 for value in (left, right)):
                    return
                if not all(0 <= value <= 65535 for value in (left_age, right_age)):
                    return
            except ValueError:
                return
            self.sonar = (left, right, left_age, right_age)
            self.sonar_received = now
            return
        if not line.startswith(b'T'):
            return
        try:
            parts = line[1:].split(b',')
            if len(parts) != 9:
                return
            distance, signal, sensor_age, command_age, watchdog, left, right, dump, uptime = map(int, parts)
            if not all(0 <= value <= 65535 for value in (distance, signal, sensor_age, command_age)):
                return
            if watchdog not in (0, 1) or not all(-1000 <= value <= 1000 for value in (left, right, dump)):
                return
            if not 0 <= uptime <= 4294967295:
                return
        except ValueError:
            return
        self.latest = {'distance_cm': distance, 'signal': signal, 'sensor_age_ms': sensor_age,
                       'command_age_ms': command_age, 'watchdog': bool(watchdog),
                       'applied_outputs': [left / 1000, right / 1000, dump / 1000],
                       'uptime_ms': uptime}
        self.received = now

    def read(self, serial_port):
        # The control loop reads at most 512 bytes per tick and never waits for a line.
        count = serial_port.in_waiting
        if isinstance(count, int) and count > 0:
            self.feed(serial_port.read(min(count, 512)))
        return self.snapshot()

    def snapshot(self, now=None):
        now = time.monotonic() if now is None else now
        if self.latest is None:
            return {'available': False, 'fresh': False, 'age_s': None, 'tof_state': 'unavailable',
                    'sonar': self.sonar_snapshot(now)}
        age = max(0, now - self.received)
        result = dict(self.latest)
        result.update(available=True, fresh=age < 1.0, age_s=round(age, 2))
        sensor_age = self.latest['sensor_age_ms'] + age * 1000
        if not result['fresh']:
            state = 'stale'
        elif sensor_age >= 500:
            state = 'sensor_stale'
        elif not 150 < result['signal'] < 55000:
            state = 'unreliable'
        elif result['distance_cm'] < 20:
            state = 'stop'
        elif result['distance_cm'] <= 100:
            state = 'slow'
        else:
            state = 'clear'
        result['tof_state'] = state
        result['sensor_valid'] = state in ('stop', 'slow', 'clear')
        result['sonar'] = self.sonar_snapshot(now)
        return result


    def sonar_snapshot(self, now):
        result = {}
        for index, name in enumerate(('left', 'right')):
            if self.sonar is None:
                result[name] = {'distance_cm': None, 'state': 'unavailable'}
                continue
            age_ms = self.sonar[index + 2] + max(0, now - self.sonar_received) * 1000
            distance = self.sonar[index]
            state = 'stale' if age_ms >= 500 else 'ok' if distance else 'no_echo'
            result[name] = {'distance_cm': distance if state == 'ok' else None,
                            'state': state, 'age_ms': round(age_ms)}
        return result
