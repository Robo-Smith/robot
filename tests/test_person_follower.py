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

    def test_preview_is_independent_of_follow_enable(self):
        self.follower.set_enabled(False)
        self.follower.request_preview()
        self.assertFalse(self.follower.enabled.is_set())
        self.assertGreater(self.follower.preview_until, time.monotonic())
        self.follower.jpeg = b'frame'
        self.follower.jpeg_time = time.monotonic()
        self.assertEqual(self.follower.preview_jpeg(), b'frame')
        self.assertIsNone(self.follower.detection()[0])

    def test_stale_preview_is_not_served(self):
        self.follower.jpeg = b'old-frame'
        self.follower.jpeg_time = time.monotonic() - 3
        self.assertIsNone(self.follower.preview_jpeg())

    def test_preview_without_model_uses_one_camera_and_never_enables_follow(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import Mock
        self.follower.set_enabled(False)
        self.follower.request_preview()
        camera = Mock()
        def capture():
            self.follower.stopping.set()
            return SimpleNamespace(shape=(480, 640, 3))
        camera.capture_array.side_effect = capture
        camera_type = Mock(return_value=camera)
        cv = SimpleNamespace(imencode=Mock(return_value=(True, SimpleNamespace(tobytes=lambda: b'jpeg'))),
                             IMWRITE_JPEG_QUALITY=1)
        with patch.dict(sys.modules, {'picamera2': SimpleNamespace(Picamera2=camera_type), 'cv2': cv}), \
             patch('person_follower.configure_camera'), \
             patch('person_follower.annotate_frame', side_effect=lambda frame, *args: frame), \
             patch('person_follower.PersonDetector') as detector:
            self.follower._run()
        camera_type.assert_called_once()
        detector.assert_not_called()
        camera.close.assert_called_once()
        self.assertEqual(self.follower.preview_jpeg(), b'jpeg')
        self.assertIsNone(self.follower.detection()[0])

    def test_preview_and_follow_share_camera_and_person_result(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import Mock
        self.follower.request_preview()
        camera = Mock()
        def capture():
            self.follower.stopping.set()
            return SimpleNamespace(shape=(480, 640, 3))
        camera.capture_array.side_effect = capture
        camera_type = Mock(return_value=camera)
        detector = Mock()
        detector.detect.return_value = ([self.box], [.9])
        cv = SimpleNamespace(imencode=Mock(return_value=(True, SimpleNamespace(tobytes=lambda: b'jpeg'))),
                             IMWRITE_JPEG_QUALITY=1)
        with patch.dict(sys.modules, {'picamera2': SimpleNamespace(Picamera2=camera_type), 'cv2': cv}), \
             patch('person_follower.configure_camera'), \
             patch('person_follower.annotate_frame', side_effect=lambda frame, *args: frame), \
             patch('person_follower.PersonDetector', return_value=detector):
            self.follower._run()
        camera_type.assert_called_once()
        detector.detect.assert_called_once()
        self.assertEqual(self.follower.preview_jpeg(), b'jpeg')
        self.assertEqual(self.follower.detection()[0], self.box)

    def test_detection_preview_does_not_publish_autonomous_drive_input(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import Mock
        self.follower.set_enabled(False)
        self.follower.request_preview(detect=True)
        camera = Mock()
        def capture():
            self.follower.stopping.set()
            return SimpleNamespace(shape=(480, 640, 3))
        camera.capture_array.side_effect = capture
        detector = Mock()
        detector.detect.return_value = ([self.box], [.9])
        cv = SimpleNamespace(imencode=Mock(return_value=(True, SimpleNamespace(tobytes=lambda: b'jpeg'))),
                             IMWRITE_JPEG_QUALITY=1)
        with patch.dict(sys.modules, {'picamera2': SimpleNamespace(Picamera2=Mock(return_value=camera)), 'cv2': cv}), \
             patch('person_follower.configure_camera'), \
             patch('person_follower.annotate_frame', side_effect=lambda frame, *args: frame) as overlay, \
             patch('person_follower.PersonDetector', return_value=detector):
            self.follower._run()
        overlay.assert_called_once()
        self.assertFalse(overlay.call_args.args[3])  # Preview, not follow target selection.
        self.assertIsNone(self.follower.detection()[0])
        self.assertTrue(self.follower.camera_status()['person_detected'])
        self.assertEqual(self.follower.camera_status()['detection_state'], 'person')
        self.assertFalse(self.follower.enabled.is_set())
