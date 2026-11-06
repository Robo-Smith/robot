"""MobileNet-SSD VOC person detection through OpenCV's CPU DNN backend."""
from pathlib import Path
import math

MODEL_DIR = Path(__file__).resolve().parent / 'models'
PERSON_CLASS = 15  # VOC class ordering used by this model.
CONFIDENCE = 0.70


def filter_people(rows, width, height, threshold=CONFIDENCE):
    candidates = []
    for row in rows:
        if not all(math.isfinite(float(value)) for value in row):
            continue
        if int(row[1]) != PERSON_CLASS or float(row[2]) < threshold:
            continue
        x1, y1, x2, y2 = [float(value) for value in row[3:7]]
        x1, x2 = [round(max(0, min(1, value)) * width) for value in (x1, x2)]
        y1, y2 = [round(max(0, min(1, value)) * height) for value in (y1, y2)]
        if x2 > x1 and y2 > y1:
            candidates.append(((x1, y1, x2 - x1, y2 - y1), float(row[2])))
    # Suppress overlapping duplicate boxes, keeping the most confident first.
    kept = []
    for box, score in sorted(candidates, key=lambda item: item[1], reverse=True):
        x, y, w, h = box
        duplicate = False
        for (kx, ky, kw, kh), _ in kept:
            intersection = max(0, min(x + w, kx + kw) - max(x, kx)) * max(
                0, min(y + h, ky + kh) - max(y, ky))
            if intersection / (w * h + kw * kh - intersection) > 0.4:
                duplicate = True
                break
        if not duplicate:
            kept.append((box, score))
    return [box for box, _ in kept], [score for _, score in kept]


class PersonDetector:
    def __init__(self):
        import cv2
        self.cv2 = cv2
        proto = MODEL_DIR / 'deploy.prototxt'
        weights = MODEL_DIR / 'mobilenet_iter_73000.caffemodel'
        if not proto.is_file() or not weights.is_file():
            raise RuntimeError('Person model missing. Run /usr/bin/python3 download_person_model.py first.')
        self.net = cv2.dnn.readNetFromCaffe(str(proto), str(weights))
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

    def detect(self, frame):
        # Picamera2 RGB888 arrays are BGR on this platform; Caffe expects BGR.
        blob = self.cv2.dnn.blobFromImage(frame, 1 / 127.5, (300, 300),
                                          (127.5, 127.5, 127.5), swapRB=False, crop=False)
        self.net.setInput(blob)
        detections = self.net.forward()
        height, width = frame.shape[:2]
        return filter_people(detections[0, 0], width, height)
