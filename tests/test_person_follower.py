import threading
import time
import unittest
from unittest.mock import patch

from person_follower import PersonFollower


class DetectionTests(unittest.TestCase):
    def setUp(self):
        # Exercise freshness without starting camera hardware or its worker.
        with patch.object(threading.Thread, 'start'):
            self.follower = PersonFollower()
        self.follower.set_enabled(True)
        self.box = (100, 100, 80, 160)

    def test_fresh_detection_is_available(self):
        self.follower.latest = (time.monotonic(), self.box, 640, 480)
        self.assertEqual(self.follower.detection()[0], self.box)

    def test_slow_detection_stops(self):
        self.follower.latest = (time.monotonic() - .6, self.box, 640, 480)
        self.assertIsNone(self.follower.detection()[0])

    def test_old_mode_result_cannot_restart_motion(self):
        previous_frame = time.monotonic()
        self.follower.set_enabled(False)
        self.follower.set_enabled(True)
        self.follower.latest = (previous_frame, self.box, 640, 480)
        self.assertIsNone(self.follower.detection()[0])
