import unittest
from person_detector import filter_people


class DetectorTests(unittest.TestCase):
    def test_only_confident_people_are_used(self):
        boxes, scores = filter_people([
            [0, 15, .9, .1, .2, .5, .8],
            [0, 15, .69, .1, .2, .5, .8],
            [0, 9, .99, .1, .2, .5, .8]], 640, 480)
        self.assertEqual(boxes, [(64, 96, 256, 288)])
        self.assertEqual(scores, [.9])

    def test_duplicate_person_suppressed(self):
        boxes, scores = filter_people([
            [0, 15, .8, .1, .2, .5, .8],
            [0, 15, .95, .1, .2, .5, .8]], 640, 480)
        self.assertEqual(len(boxes), 1)
        self.assertEqual(scores, [.95])

    def test_clips_bounds_and_rejects_invalid_boxes(self):
        boxes, _ = filter_people([
            [0, 15, .9, -1, -1, 2, 2],
            [0, 15, .9, .7, .5, .1, .2],
            [0, 15, .9, float('nan'), 0, 1, 1]], 640, 480)
        self.assertEqual(boxes, [(0, 0, 640, 480)])

    def test_empty_frame_detections_stop(self):
        self.assertEqual(filter_people([], 640, 480), ([], []))
