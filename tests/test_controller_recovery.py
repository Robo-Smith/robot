import contextlib
import io
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import Pi


def event(kind, code, value=0):
    return SimpleNamespace(type=kind, code=code, value=value)


class RecoveryTests(unittest.TestCase):
    def test_overflow_stops_and_resynchronizes_without_reopening_serial(self):
        codes = Pi.evdev.ecodes
        controller = Mock()
        controller.absinfo.return_value = SimpleNamespace(value=127, min=0, max=255)
        controller.read.return_value = iter([
            event(codes.EV_SYN, codes.SYN_DROPPED),
            event(codes.EV_KEY, 308, 1),  # Incomplete packet: must not enable follow.
            event(codes.EV_ABS, codes.ABS_Y, 0),
            event(codes.EV_SYN, codes.SYN_REPORT),
        ])
        serial = Mock()
        follower = Mock()
        output = io.StringIO()
        with patch.object(Pi, 'find_stadia_controller', return_value=controller), \
             patch.object(Pi.serial, 'Serial', return_value=serial) as connect, \
             patch.object(Pi, 'PersonFollower', return_value=follower), \
             patch.object(Pi.signal, 'signal'), patch.object(Pi.time, 'sleep'), \
             patch.object(Pi.select, 'select', side_effect=[([controller], [], []), KeyboardInterrupt]), \
             contextlib.redirect_stdout(output):
            with self.assertRaises(KeyboardInterrupt):
                Pi.main()
        self.assertEqual(connect.call_count, 1)
        self.assertIn('Controller synchronized', output.getvalue())
        self.assertNotIn('Mode: follow', output.getvalue())
        self.assertGreaterEqual(controller.absinfo.call_count, 6)
        self.assertTrue(serial.write.called)
        self.assertTrue(all(call.args == (b'C0,0,0\n',) for call in serial.write.call_args_list))
        self.assertTrue(all(call.args == (False,) for call in follower.set_enabled.call_args_list))
        serial.close.assert_called_once()

    def test_shutdown_hold_stops_before_dispatch_and_ignores_mode_buttons(self):
        import threading
        codes = Pi.evdev.ecodes
        controller = Mock()
        controller.read.side_effect = [
            iter([event(codes.EV_ABS, codes.ABS_HAT0Y, 1)]),
            iter([event(codes.EV_KEY, 308, 1)]),
        ]
        ser = Mock()
        follower = Mock()
        actions = Mock()
        actions.shutdown_pending = threading.Event()
        def submit(action):
            self.assertEqual(action, 'shutdown')
            self.assertEqual(ser.write.call_args.args, (b'C0,0,0\n',))
            follower.set_enabled.assert_called_with(False)
            actions.shutdown_pending.set()
            return True
        actions.submit.side_effect = submit
        now = [0.0]
        steps = iter([(0, [controller]), (3.1, []), (3.2, [controller])])
        def select(*args):
            try:
                now[0], ready = next(steps)
            except StopIteration:
                raise KeyboardInterrupt
            return ready, [], []
        with patch.object(Pi, 'find_stadia_controller', return_value=controller), \
             patch.object(Pi.serial, 'Serial', return_value=ser), \
             patch.object(Pi, 'PersonFollower', return_value=follower), \
             patch.object(Pi, 'SystemActions', return_value=actions), \
             patch.object(Pi.signal, 'signal'), patch.object(Pi.time, 'sleep'), \
             patch.object(Pi.time, 'monotonic', side_effect=lambda: now[0]), \
             patch.object(Pi.select, 'select', side_effect=select), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(KeyboardInterrupt):
                Pi.main()
        actions.submit.assert_called_once_with('shutdown')
        self.assertTrue(all(call.args == (b'C0,0,0\n',) for call in ser.write.call_args_list))
        self.assertNotIn((True,), [call.args for call in follower.set_enabled.call_args_list])
