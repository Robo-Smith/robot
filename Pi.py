"""Stadia mode control and 20 Hz motor command heartbeat to the Nano."""
import select
import signal
import time

import evdev
import serial

from person_follower import PersonFollower
from controller_actions import DpadHolds, SystemActions
from robot_control import clamp, follow_command, controller_command, FollowRamp, follow_wheel_minimum, FollowSteering

SERIAL_PORT = '/dev/ttyUSB0'
BAUD_RATE = 115200
BUTTON_MODES = {304: 'manual', 305: 'single', 307: 'stop', 308: 'follow'}
DPAD_KEYS = {evdev.ecodes.BTN_DPAD_DOWN: 'down', evdev.ecodes.BTN_DPAD_UP: 'up',
             evdev.ecodes.BTN_DPAD_LEFT: 'left', evdev.ecodes.BTN_DPAD_RIGHT: 'right'}
DPAD_HATS = {evdev.ecodes.ABS_HAT0X: 'x', evdev.ecodes.ABS_HAT0Y: 'y'}
TICK = 0.05


def find_stadia_controller():
    for path in evdev.list_devices():
        device = evdev.InputDevice(path)
        if 'Stadia' in device.name:
            return device
        device.close()
    raise RuntimeError('Stadia controller not found')


def normalized(device, code, value, trigger=False):
    info = device.absinfo(code)
    span = info.max - info.min
    if span <= 0:
        return 0.0
    value = (value - info.min) / span
    if trigger:
        return max(0.0, min(1.0, value))
    value = clamp(value * 2 - 1)
    return 0.0 if abs(value) < 0.08 else value


def send(ser, left=0, right=0, dump=0):
    # One complete frame avoids partially updated left/right/dump commands.
    values = [round(clamp(v) * 1000) for v in (left, right, dump)]
    ser.write(('C%d,%d,%d\n' % tuple(values)).encode('ascii'))


def main():
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    follower = PersonFollower()
    system_actions = SystemActions()
    while True:
        controller = ser = None
        try:
            controller = find_stadia_controller()
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0, write_timeout=0.1)
            time.sleep(2)  # Nano resets when the serial port opens.
            send(ser)
            mode = 'manual'
            axes = {}  # Require fresh input after reconnecting.
            resyncing = False
            holds = DpadHolds()
            follow_ramp = FollowRamp()
            follow_steering = FollowSteering()
            print('Connected; mode: manual', flush=True)
            next_tick = time.monotonic()
            while True:
                ready, _, _ = select.select([controller], [], [], max(0, next_tick - time.monotonic()))
                if ready:
                    for event in controller.read():
                        if event.type == evdev.ecodes.EV_SYN and event.code == evdev.ecodes.SYN_DROPPED:
                            send(ser)
                            mode = 'stop'
                            follow_ramp.reset()
                            follow_steering.reset()
                            axes.clear()
                            holds.reset(require_release=True)
                            follower.set_enabled(False)
                            resyncing = True
                            print('Controller events lost; motors stopped, resynchronizing', flush=True)
                            continue
                        if resyncing:
                            # Linux evdev requires discarding through SYN_REPORT.
                            if event.type == evdev.ecodes.EV_SYN and event.code == evdev.ecodes.SYN_REPORT:
                                for code in (evdev.ecodes.ABS_X, evdev.ecodes.ABS_Y,
                                             evdev.ecodes.ABS_Z, evdev.ecodes.ABS_RZ,
                                             evdev.ecodes.ABS_BRAKE, evdev.ecodes.ABS_GAS):
                                    info = controller.absinfo(code)
                                    if info is not None:
                                        axes[code] = normalized(controller, code, info.value,
                                            code in (evdev.ecodes.ABS_BRAKE, evdev.ecodes.ABS_GAS))
                                resyncing = False
                                print('Controller synchronized; center controls and press A/B/Y to resume', flush=True)
                            continue
                        if event.type == evdev.ecodes.EV_ABS and event.code in DPAD_HATS:
                            holds.update('hat', DPAD_HATS[event.code], event.value, time.monotonic())
                            continue
                        if event.type == evdev.ecodes.EV_KEY and event.code in DPAD_KEYS:
                            holds.update('key', DPAD_KEYS[event.code], event.value, time.monotonic())
                            continue
                        if system_actions.shutdown_pending.is_set():
                            continue
                        if event.type == evdev.ecodes.EV_KEY and event.value == 1 and event.code in BUTTON_MODES:
                            mode = BUTTON_MODES[event.code]
                            follow_ramp.reset()
                            follow_steering.reset()
                            send(ser)
                            follower.set_enabled(mode == 'follow')
                            print(f'Mode: {mode}', flush=True)
                        elif event.type == evdev.ecodes.EV_ABS:
                            axes[event.code] = normalized(controller, event.code, event.value,
                                event.code in (evdev.ecodes.ABS_BRAKE, evdev.ecodes.ABS_GAS))
                if time.monotonic() < next_tick:
                    continue
                next_tick = time.monotonic() + TICK
                action = holds.poll(time.monotonic())
                if action and not system_actions.shutdown_pending.is_set():
                    if action == 'shutdown':
                        send(ser)
                        mode = 'stop'
                        follower.set_enabled(False)
                    system_actions.submit(action)
                if system_actions.shutdown_pending.is_set():
                    mode = 'stop'
                    follower.set_enabled(False)
                get = lambda code: axes.get(code, 0.0)
                left, right, dump = controller_command(mode,
                    get(evdev.ecodes.ABS_X), -get(evdev.ecodes.ABS_Y),
                    get(evdev.ecodes.ABS_Z), -get(evdev.ecodes.ABS_RZ),
                    get(evdev.ecodes.ABS_BRAKE), get(evdev.ecodes.ABS_GAS))
                if mode == 'follow':
                    box, width, height = follower.detection()
                    left, right = follow_command(box, width, height, follow_steering)
                    left, right = follow_ramp.update(left, right, time.monotonic(),
                                                    follow_wheel_minimum(box, width, follow_steering))
                else:
                    follow_ramp.reset()
                    follow_steering.reset()
                send(ser, left, right, dump)
        except (OSError, RuntimeError, serial.SerialException) as exc:
            print(f'Connection error: {exc}', flush=True)
        finally:
            follower.set_enabled(False)
            if ser is not None:
                try:
                    send(ser)
                except (OSError, serial.SerialException):
                    pass
                ser.close()
            if controller is not None:
                controller.close()
        time.sleep(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Stopped', flush=True)
