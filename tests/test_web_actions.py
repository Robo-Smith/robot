import unittest
from web_actions import WebActions


class PageActionTests(unittest.TestCase):
    def test_allowed_modes_and_excluded_actions(self):
        queue = WebActions()
        for action in ('manual', 'wifi', 'wifi_off', 'wifi_on', 'reboot', 'unknown'):
            with self.assertRaises(ValueError):
                queue.request(action)
        for action in ('stop', 'single', 'follow', 'hotspot', 'shutdown'):
            queue.request(action, controller_connected=True, confirmed=True, now=1)
            self.assertEqual(queue.take(now=1.1), action)

    def test_single_stick_requires_stadia(self):
        with self.assertRaises(ValueError):
            WebActions().request('single')

    def test_deliberate_confirmation_required(self):
        for action in ('follow', 'hotspot', 'shutdown'):
            with self.assertRaises(ValueError):
                WebActions().request(action, confirmed=False)

    def test_stop_preempts_pending_requests(self):
        queue = WebActions()
        queue.request('follow', confirmed=True, now=1)
        with self.assertRaises(ValueError):
            queue.request('shutdown', confirmed=True, now=1.1)
        queue.request('stop', now=1.2)
        self.assertEqual(queue.take(now=1.3), 'stop')
        self.assertIsNone(queue.take(now=1.4))

    def test_expired_or_physically_cancelled_requests_do_not_run(self):
        queue = WebActions()
        queue.request('shutdown', confirmed=True, now=1)
        self.assertIsNone(queue.take(now=4))
        queue.request('follow', confirmed=True, now=4)
        queue.clear()
        self.assertIsNone(queue.take(now=4.1))
