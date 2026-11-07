"""D-pad hold timing and asynchronous Pi system actions."""
import os
import subprocess
import threading


class DpadHolds:
    """Require one direction continuously; diagonals cancel, repeats do not rearm."""
    ACTIONS = {'down': 'shutdown', 'right': 'wifi', 'left': 'hotspot'}

    def __init__(self):
        self.reset()

    def reset(self, require_release=False):
        self.hats = {'x': 0, 'y': 0}
        self.keys = set()
        self.direction = None
        self.started = None
        self.fired = False
        self.require_release = require_release

    def update(self, kind, control, value, now):
        if kind == 'hat':
            self.hats[control] = value
        elif kind == 'key':
            if value:
                self.keys.add(control)
            else:
                self.keys.discard(control)
        directions = set(self.keys)
        for axis, negative, positive in (('x', 'left', 'right'), ('y', 'up', 'down')):
            if self.hats[axis]:
                directions.add(negative if self.hats[axis] < 0 else positive)
        if self.require_release:
            if not directions:
                self.require_release = False
            return
        direction = next(iter(directions)) if len(directions) == 1 else None
        if direction != self.direction:
            self.direction = direction
            self.started = now if direction in self.ACTIONS else None
            self.fired = False

    def poll(self, now):
        if self.started is not None and not self.fired and now - self.started >= 3.0:
            self.fired = True
            return self.ACTIONS[self.direction]
        return None


class SystemActions:
    def __init__(self):
        self.lock = threading.Lock()
        self.shutdown_pending = threading.Event()

    def submit(self, action):
        if not self.lock.acquire(blocking=False):
            print('System action already running; release and hold again to retry', flush=True)
            return False
        if action == 'shutdown':
            self.shutdown_pending.set()
        threading.Thread(target=self._run, args=(action,), daemon=True).start()
        return True

    def _command(self, args):
        result = subprocess.run(args, capture_output=True, text=True, timeout=15, check=True,
                                env={**os.environ, 'LC_ALL': 'C'})
        return result.stdout.strip()

    def _run(self, action):
        try:
            if action == 'shutdown':
                print('Shutting down Pi; motors stopped', flush=True)
                self._command(['systemctl', '--no-ask-password', 'poweroff'])
            elif action == 'wifi':
                state = self._command(['nmcli', '-t', '-f', 'WIFI', 'radio'])
                if state not in ('enabled', 'disabled'):
                    raise RuntimeError(f'Unexpected Wi-Fi state: {state!r}')
                target = 'off' if state == 'enabled' else 'on'
                self._command(['nmcli', '--wait', '10', 'radio', 'wifi', target])
                print(f'Wi-Fi turned {target}', flush=True)
            elif action == 'hotspot':
                print('Hotspot requested: placeholder only; network configuration unchanged', flush=True)
            else:
                raise ValueError(f'Unknown system action: {action}')
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            detail = getattr(exc, 'stderr', None) or str(exc)
            print(f'System action {action} failed: {detail.strip()}', flush=True)
            if action == 'shutdown':
                self.shutdown_pending.clear()
        finally:
            self.lock.release()
