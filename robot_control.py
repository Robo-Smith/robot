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


def follow_command(box, width, height):
    if box is None:
        return 0.0, 0.0
    x, y, w, h = box
    turn = clamp(((x + w / 2) / width - 0.5) * 2)
    if abs(turn) < 0.10:
        turn = 0.0
    size = w / width if FOLLOW_SIZE_METRIC == 'width' else h / height
    gap = FOLLOW_TARGET_SIZE - size
    # Never reverse automatically; stop both motors when already close enough.
    if gap <= FOLLOW_STOP_MARGIN + 1e-9:
        return 0.0, 0.0
    # Normalize by the calibrated size: speed should not depend on how large
    # this particular person appears at the stop distance.
    stop_size = FOLLOW_TARGET_SIZE - FOLLOW_STOP_MARGIN
    relative_error = max(0.0, (stop_size - size) / stop_size)
    forward = min(FOLLOW_MAX_SPEED,
                  FOLLOW_MIN_WHEEL_SPEED + FOLLOW_SPEED_GAIN * relative_error)
    forward *= max(0, 1 - abs(turn) * 2)
    steering = 0.0
    wheel_minimum = FOLLOW_MIN_WHEEL_SPEED
    if turn != 0:
        # A small proportional turn used to fall inside the motor deadband.
        strength = FOLLOW_MIN_TURN + (FOLLOW_MAX_TURN - FOLLOW_MIN_TURN) * abs(turn)
        steering = strength if turn > 0 else -strength
        wheel_minimum = FOLLOW_MIN_TURN_WHEEL_SPEED
    left, right = mix(forward, steering)
    def compensate(value):
        if abs(value) < 1e-9:
            return 0.0
        magnitude = min(FOLLOW_MAX_WHEEL_SPEED, max(wheel_minimum, abs(value)))
        return magnitude if value > 0 else -magnitude
    return compensate(left), compensate(right)


def controller_command(mode, left_x, left_forward, right_x, right_forward, lower, raise_dump):
    """Return all three motor outputs; autonomous/unknown modes ignore controls."""
    if mode == 'manual':
        return clamp(left_forward), clamp(right_forward), clamp(raise_dump - lower)
    if mode == 'single':
        left, right = single_stick(left_x, left_forward, right_x, right_forward)
        return left, right, clamp(raise_dump - lower)
    return 0.0, 0.0, 0.0
