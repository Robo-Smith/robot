"""Hardware-independent drive mixing and follow control. Positive means forward/right."""
import json
from pathlib import Path
from statistics import median

FOLLOW_SETTINGS = Path(__file__).resolve().parent / 'follow_settings.json'
FOLLOW_STOP_MARGIN = 0.04


def load_target_size(path=FOLLOW_SETTINGS):
    if not path.exists():
        return 0.65
    settings = json.loads(path.read_text())
    value = float(settings['target_size'] if 'target_size' in settings else settings['target_height'])
    if not 0.04 < value <= 1.0:
        raise ValueError('Invalid target size in follow_settings.json; recalibrate')
    return value


def load_size_metric(path=FOLLOW_SETTINGS):
    metric = json.loads(path.read_text()).get('metric', 'height') if path.exists() else 'height'
    if metric not in ('height', 'width'):
        raise ValueError('Invalid follow calibration metric; recalibrate')
    return metric


def save_calibration(sizes, path=FOLLOW_SETTINGS, metric='height'):
    if metric not in ('height', 'width'):
        raise ValueError('Calibration metric must be height or width')
    if len(sizes) < 5:
        raise ValueError('Need at least five frames containing exactly one person; calibration not saved')
    measured = median(sizes)
    if not 0.1 <= measured < 0.95 or max(sizes) - min(sizes) > 0.15:
        raise ValueError('Person box size is clipped or varies too much; face the camera, stay still and retry')
    # Compensate for the stopping margin so the measured size is the stop point.
    target = measured + FOLLOW_STOP_MARGIN
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'target_size': target, 'metric': metric, 'distance_m': 1.0}, indent=2) + '\n')
    temporary.replace(path)
    return measured


def clamp(value, limit=1.0):
    return max(-limit, min(limit, value))


def mix(forward, turn):
    return clamp(forward + turn), clamp(forward - turn)


def single_stick(left_x, left_y, right_x, right_y):
    return mix(clamp(left_y + right_y), clamp(left_x + right_x))


# Old height calibrations remain supported; new 1m calibrations use box width.
FOLLOW_TARGET_SIZE = load_target_size()
FOLLOW_SIZE_METRIC = load_size_metric()
FOLLOW_MAX_SPEED = 0.65
FOLLOW_SPEED_GAIN = 0.80
FOLLOW_MAX_WHEEL_SPEED = 0.65
FOLLOW_MIN_TURN = 0.30
FOLLOW_MAX_TURN = 0.40
FOLLOW_MIN_TURN_WHEEL_SPEED = 0.28
FOLLOW_MIN_WHEEL_SPEED = 0.18  # Minimum usable follow-mode wheel command.


class FollowSteering:
    """Start corrections outside a wider band; release near center without lag."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.direction = 0
        self.pivot = False

    def filter(self, error):
        direction = 1 if error > 0 else -1
        if self.direction and (abs(error) <= .08 or direction != self.direction):
            self.reset()
        if not self.direction and abs(error) >= .18:
            self.direction = direction
        if self.pivot and abs(error) < .50:
            self.pivot = False
        if abs(error) >= .70:
            self.pivot = True
        return error if self.direction else 0.0


def follow_command(box, width, height, steering_controller=None):
    if box is None:
        if steering_controller is not None:
            steering_controller.reset()
        return 0.0, 0.0
    x, y, w, h = box
    turn = clamp(((x + w / 2) / width - 0.5) * 2)
    if steering_controller is not None:
        turn = steering_controller.filter(turn)
    elif abs(turn) < .18:
        turn = 0.0
    size = w / width if FOLLOW_SIZE_METRIC == 'width' else h / height
    gap = FOLLOW_TARGET_SIZE - size
    # Never reverse automatically; stop both motors when already close enough.
    if gap <= FOLLOW_STOP_MARGIN + 1e-9:
        if steering_controller is not None:
            steering_controller.reset()
        return 0.0, 0.0
    # Normalize by the calibrated size: speed should not depend on how large
    # this particular person appears at the stop distance.
    stop_size = FOLLOW_TARGET_SIZE - FOLLOW_STOP_MARGIN
    relative_error = max(0.0, (stop_size - size) / stop_size)
    forward = min(FOLLOW_MAX_SPEED,
                  FOLLOW_MIN_WHEEL_SPEED + FOLLOW_SPEED_GAIN * relative_error)
    pivot = steering_controller.pivot if steering_controller is not None else abs(turn) >= .70
    if pivot:
        # Retain enough torque to pivot only for a person far to one side.
        strength = FOLLOW_MIN_TURN + (FOLLOW_MAX_TURN - FOLLOW_MIN_TURN) * abs(turn)
        return (strength, -strength) if turn > 0 else (-strength, strength)
    # Ordinary tracking uses forward arcs: never reverse the inside wheel.
    # Keep the outside wheel powered and reduce only the inside wheel.
    outside_minimum = FOLLOW_MIN_TURN_WHEEL_SPEED if turn else FOLLOW_MIN_WHEEL_SPEED
    speed = max(outside_minimum, forward * (1 - .35 * abs(turn)))
    inside = max(FOLLOW_MIN_WHEEL_SPEED, speed * (1 - .85 * abs(turn)))
    speed = min(FOLLOW_MAX_WHEEL_SPEED, speed)
    return (speed, inside) if turn >= 0 else (inside, speed)


def controller_command(mode, left_x, left_forward, right_x, right_forward, lower, raise_dump):
    """Return all three motor outputs; autonomous/unknown modes ignore controls."""
    if mode == 'manual':
        return clamp(left_forward), clamp(right_forward), clamp(raise_dump - lower)
    if mode == 'single':
        left, right = single_stick(left_x, left_forward, right_x, right_forward)
        return left, right, clamp(raise_dump - lower)
    return 0.0, 0.0, 0.0


FOLLOW_ACCELERATION = 0.30  # Command fraction per second, above motor minimum.
FOLLOW_DECELERATION = 0.60


def follow_wheel_minimum(box, width, steering_controller=None):
    pivot = steering_controller.pivot if steering_controller is not None else (
        box is not None and abs(((box[0] + box[2] / 2) / width - .5) * 2) >= .70)
    return FOLLOW_MIN_TURN_WHEEL_SPEED if pivot else FOLLOW_MIN_WHEEL_SPEED


class FollowRamp:
    """Slew usable wheel commands; all-zero requests are immediate safety stops."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.outputs = (0.0, 0.0)
        self.last_time = None

    def update(self, left, right, now, minimum=FOLLOW_MIN_WHEEL_SPEED):
        if left == 0 and right == 0:
            self.reset()
            return self.outputs
        dt = max(0.0, now - self.last_time) if self.last_time is not None else 0.0
        # After a pause long enough to trip the Nano watchdog, start from rest.
        if dt >= 0.5:
            self.outputs = (0.0, 0.0)
            dt = 0.0
        self.last_time = now
        old_turn = self.outputs[0] - self.outputs[1]
        new_turn = left - right
        if abs(old_turn) > 1e-9 and (abs(new_turn) < 1e-9 or old_turn * new_turn < 0):
            # Drop obsolete steering promptly instead of ramping through it.
            # Only lower output: opposed wheels go to zero; forward wheels match
            # the slower wheel before building the newly requested correction.
            common = min(self.outputs) if min(self.outputs) >= 0 else 0.0
            self.outputs = (common, common)
        self.outputs = tuple(self._wheel(current, target, dt, minimum)
                             for current, target in zip(self.outputs, (left, right)))
        return self.outputs

    @staticmethod
    def _wheel(current, target, dt, minimum):
        target = clamp(target, FOLLOW_MAX_WHEEL_SPEED)
        # Reversals must reach zero for at least one update before restarting.
        reversing = current * target < 0
        desired = 0.0 if reversing else abs(target)
        magnitude = abs(current)
        if desired == 0:
            magnitude -= FOLLOW_DECELERATION * dt
            if magnitude <= minimum + 1e-9:
                return 0.0
            return magnitude if current > 0 else -magnitude
        if current == 0:
            magnitude = min(minimum, desired)
        else:
            # Raising the usable minimum for a turn is a deliberate small step.
            magnitude = max(minimum, magnitude)
            rate = FOLLOW_ACCELERATION if desired > magnitude else FOLLOW_DECELERATION
            change = rate * dt
            magnitude += max(-change, min(change, desired - magnitude))
            magnitude = max(minimum, magnitude)
        return magnitude if target > 0 else -magnitude
