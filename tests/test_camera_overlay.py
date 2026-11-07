import unittest
from unittest.mock import patch

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = np = None

from camera_overlay import annotate_frame


@unittest.skipIf(cv2 is None, 'OpenCV camera dependencies not installed')
class OverlayTests(unittest.TestCase):
    def test_target_and_other_people_colors_do_not_modify_source(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = annotate_frame(frame, [(50, 80, 100, 200), (300, 80, 50, 100)], [.92, .81], following=True)
        self.assertTrue(np.all(frame == 0))
        self.assertEqual(tuple(result[80, 50]), (0, 190, 255))
        self.assertEqual(tuple(result[80, 300]), (100, 235, 110))

    def test_no_person_is_distinct_from_error_or_stale(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        for kwargs, expected in (({}, 'No person detected'), ({'error': 'Model missing'}, 'Detection unavailable'),
                                 ({'elapsed': .6, 'following': True}, 'Detection stale - follow stopped')):
            with patch('cv2.putText', wraps=cv2.putText) as text:
                annotate_frame(frame, [], [], **kwargs)
            self.assertTrue(any(expected in call.args[1] for call in text.call_args_list))

    def test_preview_does_not_label_any_person_as_follow_target(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with patch('cv2.putText', wraps=cv2.putText) as text:
            annotate_frame(frame, [(50, 80, 100, 200)], [.92])
        labels = [call.args[1] for call in text.call_args_list]
        self.assertIn('Person 92%', labels)
        self.assertTrue(any('Preview only' in label for label in labels))
        self.assertFalse(any('Follow target' in label for label in labels))
