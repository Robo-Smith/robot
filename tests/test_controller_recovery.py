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
