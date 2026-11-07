"""Stadia mode control and 20 Hz motor command heartbeat to the Nano."""
import select
import signal
import time

import evdev
import serial

from person_follower import PersonFollower
from controller_actions import DpadHolds, SystemActions
from status_server import start_dashboard
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
    dashboard = start_dashboard(follower)
    try:
        while True:
            controller = ser = None
            try:
                dashboard.update(mode='stop', connected=False, outputs=[0, 0, 0],
                                 controller_name='', controller_id='', teleop_ready=False, message='Connecting to Nano')
                ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0, write_timeout=0.1)
                time.sleep(2)  # Nano resets when the serial port opens.
                send(ser)
                try:
                    controller = find_stadia_controller()
                except RuntimeError:
                    controller = None
                mode = 'manual' if controller else 'stop'
                next_controller_scan = time.monotonic() + 1
                axes = {}  # Require fresh input after reconnecting.
                resyncing = False
                holds = DpadHolds()
                follow_ramp = FollowRamp()
                follow_steering = FollowSteering()
                dashboard.update(mode=mode, connected=controller is not None,
                                 controller_name=controller.name if controller else '',
                                 controller_id=controller.uniq if controller else '',
                                 teleop_ready=True, message='Ready')
                print(f'Nano connected; mode: {mode}', flush=True)
                next_tick = time.monotonic()
                while True:
                    if controller is None and time.monotonic() >= next_controller_scan:
                        next_controller_scan = time.monotonic() + 1
                        try:
                            controller = find_stadia_controller()
                            print('Stadia connected; select a mode to drive', flush=True)
                        except RuntimeError:
                            pass
                    ready, _, _ = select.select([controller] if controller else [], [], [],
                                                max(0, next_tick - time.monotonic()))
                    if ready:
                        try:
                            events = list(controller.read())
                        except OSError:
                            send(ser)
                            dashboard.teleop.reset()
                            controller.close()
                            controller = None
                            axes.clear()
                            holds.reset(require_release=True)
                            resyncing = False
                            follow_ramp.reset()
                            follow_steering.reset()
                            mode = 'stop'
                            follower.set_enabled(False)
                            continue
                        for event in events:
                            if event.type == evdev.ecodes.EV_SYN and event.code == evdev.ecodes.SYN_DROPPED:
                                send(ser)
                                mode = 'stop'
                                dashboard.teleop.reset()
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
                                dashboard.teleop.reset()
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
                            dashboard.teleop.reset()
                            follower.set_enabled(False)
                        system_actions.submit(action)
                    if system_actions.shutdown_pending.is_set():
                        mode = 'stop'
                        dashboard.teleop.reset()
                        follower.set_enabled(False)
                    web_outputs = dashboard.teleop.outputs()
                    if dashboard.teleop.take_stop():
                        mode = 'stop'
                        follower.set_enabled(False)
                        web_outputs = None
                    if web_outputs is not None and not resyncing and not system_actions.shutdown_pending.is_set():
                        mode = 'teleop'
                        follower.set_enabled(False)
                    elif mode == 'teleop':
                        mode = 'stop'
                    get = lambda code: axes.get(code, 0.0)
                    left, right, dump = controller_command(mode,
                        get(evdev.ecodes.ABS_X), -get(evdev.ecodes.ABS_Y),
                        get(evdev.ecodes.ABS_Z), -get(evdev.ecodes.ABS_RZ),
                        get(evdev.ecodes.ABS_BRAKE), get(evdev.ecodes.ABS_GAS))
                    if mode == 'teleop':
                        left, right, dump = web_outputs
                        follow_ramp.reset()
                        follow_steering.reset()
                    elif mode == 'follow':
                        box, width, height = follower.detection()
                        left, right = follow_command(box, width, height, follow_steering)
                        left, right = follow_ramp.update(left, right, time.monotonic(),
                                                        follow_wheel_minimum(box, width, follow_steering))
                    else:
                        follow_ramp.reset()
                        follow_steering.reset()
                    send(ser, left, right, dump)
                    dashboard.update(mode=mode, connected=controller is not None, outputs=[left, right, dump],
                                     controller_name=controller.name if controller else '',
                                     controller_id=controller.uniq if controller else '',
                                     teleop_ready=not resyncing and not system_actions.shutdown_pending.is_set(),
                                     message=('Shutting down' if system_actions.shutdown_pending.is_set() else
                                              'Controller resynchronizing' if resyncing else 'Ready'))
            except (OSError, RuntimeError, serial.SerialException) as exc:
                dashboard.update(mode='stop', connected=False, outputs=[0, 0, 0], message=str(exc))
                print(f'Connection error: {exc}', flush=True)
            finally:
                dashboard.teleop.reset()
                dashboard.update(mode='stop', connected=False, teleop_ready=False, outputs=[0, 0, 0], message='Disconnected')
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
    finally:
        dashboard.close()
        follower.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Stopped', flush=True)
