import tempfile
from pathlib import Path
import unittest
import queue
from unittest.mock import Mock
from screen_ui import Screen, display_connected
from web_actions import WebActions


class ScreenTests(unittest.TestCase):
    def test_display_hotplug(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertFalse(display_connected(root))
            connector = root / 'card1-HDMI-A-1'
            connector.mkdir()
            status = connector / 'status'
            status.write_text('disconnected\n')
            self.assertFalse(display_connected(root))
            status.write_text('connected\n')
            self.assertTrue(display_connected(root))
            status.write_text('disconnected\n')
            self.assertFalse(display_connected(root))

    def test_manual_selection_without_controller_and_stop_preempts(self):
        actions = WebActions()
        actions.request('manual')
        self.assertEqual(actions.take(), 'manual')
        actions.request('follow', confirmed=True)
        actions.request('stop')
        self.assertEqual(actions.take(), 'stop')

    def test_manual_dump_expires_and_stop_clears_it(self):
        actions = WebActions()
        actions.request('dump_up', now=10)
        self.assertEqual(actions.manual_dump(now=10.2), 1)
        self.assertEqual(actions.manual_dump(now=10.5), 0)
        actions.request('dump_down', now=11)
        self.assertEqual(actions.manual_dump(now=11.1), -1)
        actions.request('dump_stop', now=11.2)
        self.assertEqual(actions.manual_dump(now=11.3), 0)
        actions.request('dump_up', now=12)
        actions.request('stop', now=12.1)
        self.assertEqual(actions.manual_dump(now=12.2), 0)
        self.assertEqual(actions.take(now=12.2), 'stop')

    def test_status_refresh_keeps_shutdown_mapped_until_mode_changes(self):
        screen = Screen.__new__(Screen)
        for name in ('root', 'shutdown', 'extra', 'video', 'title', 'note', 'network_indicator', 'network_status', 'follow_canvas', 'set_follow_view'):
            setattr(screen, name, Mock())
        screen.system_buttons = {'shutdown': screen.shutdown, 'hotspot': Mock(), 'wifi': Mock()}
        screen.buttons = {'stop': Mock()}
        screen.dump_buttons = [Mock(), Mock()]
        screen.frames = queue.Queue()
        screen.follow_view = False
        screen.follow_image = 1
        screen.extra_layout = None
        screen.dump = 0

        def refresh(mode):
            screen.frames.put(({'live': True, 'mode': mode, 'teleop_ready': True}, None, ''))
            screen.render()

        refresh('stop')
        screen.shutdown.pack.assert_called_once()
        screen.shutdown.reset_mock()
        screen.extra.reset_mock()
        for button in screen.system_buttons.values():
            button.reset_mock()
        for _ in range(10):
            refresh('stop')
        screen.shutdown.pack.assert_not_called()
        screen.shutdown.pack_forget.assert_not_called()
        screen.extra.pack_forget.assert_not_called()
        for button in screen.system_buttons.values():
            button.pack.assert_not_called()
            button.pack_forget.assert_not_called()
        refresh('manual')
        screen.shutdown.pack_forget.assert_called_once()
        for button in screen.dump_buttons:
            button.pack.assert_called_once()
        refresh('single')
        for button in screen.dump_buttons:
            button.pack.assert_called_once()

    def test_follow_dimensions_ignore_hidden_video_resize(self):
        from types import SimpleNamespace
        screen = Screen.__new__(Screen)
        screen.draw_follow_overlay = Mock()
        screen.video_size = (300, 140)
        screen.resize_follow(SimpleNamespace(width=800, height=480))
        self.assertEqual(screen.follow_size, (800, 480))
        self.assertEqual(screen.video_size, (300, 140))

    def test_follow_touch_survives_overlay_redraw_without_pointer_motion(self):
        from types import SimpleNamespace
        screen = Screen.__new__(Screen)
        screen.follow_size = (800, 480)
        screen.follow_pressed = None
        screen.buttons = {action: Mock() for action in ('stop', 'manual', 'single', 'follow')}
        touch = SimpleNamespace(x=100, y=444)
        screen.follow_press(touch)
        # No canvas item tags or mouse motion are needed to identify a touch.
        screen.follow_release(touch)
        screen.buttons['stop'].invoke.assert_called_once()
        screen.follow_press(touch)
        screen.follow_release(SimpleNamespace(x=300, y=444))
        screen.buttons['manual'].invoke.assert_not_called()
        screen.follow_press(SimpleNamespace(x=100, y=200))
        screen.follow_release(touch)
        screen.buttons['stop'].invoke.assert_called_once()
