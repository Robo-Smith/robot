"""Camera worker; controller handling never waits for capture or detection."""
import threading
import time

from robot_control import follow_command, save_calibration, FOLLOW_SETTINGS, FOLLOW_SIZE_METRIC
from person_detector import PersonDetector


def configure_camera(camera):
    # The IMX219's native 640x480 mode crops the sensor. Select its binned
    # 4:3 mode, then downscale for detection so detection retains a wider view.
    camera.configure(camera.create_video_configuration(
        main={"size": (640, 480), "format": "RGB888"},
        raw={"size": (1640, 1232)}, buffer_count=2, queue=False))


def detect_people(detector, frame):
    return detector.detect(frame)


class PersonFollower:
    """Own the camera once; serve preview frames without a second camera client."""
    def __init__(self):
        self.lock = threading.Lock()
        self.latest = (0.0, None, 640, 480)
        self.enabled_since = float("inf")
        self.enabled = threading.Event()
        self.wake = threading.Event()
        self.stopping = threading.Event()
        self.preview_until = 0.0
        self.jpeg = None
        self.jpeg_time = 0.0
        self.state = 'idle'
        self.error = ''
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    def set_enabled(self, enabled):
        with self.lock:
            self.enabled_since = time.monotonic() if enabled else float("inf")
            self.latest = (0.0, None, 640, 480)
            if enabled:
                self.enabled.set()
            else:
                self.enabled.clear()
        self.wake.set()

    def detection(self):
        with self.lock:
            timestamp, box, width, height = self.latest
            enabled_since = self.enabled_since
        if timestamp < enabled_since or time.monotonic() - timestamp > 0.5:
            box = None
        return box, width, height

    def request_preview(self):
        with self.lock:
            self.preview_until = time.monotonic() + 3.0
        self.wake.set()

    def preview_jpeg(self):
        with self.lock:
            return self.jpeg if time.monotonic() - self.jpeg_time < 2.0 else None

    def camera_status(self):
        with self.lock:
            timestamp, box, _, _ = self.latest
            fresh = timestamp >= self.enabled_since and time.monotonic() - timestamp <= .5
            return {'state': self.state, 'error': self.error,
                    'person_detected': box is not None and fresh}

    def close(self):
        self.stopping.set()
        self.wake.set()
        if self.worker.is_alive():
            self.worker.join(timeout=1)

    def _run(self):
        camera = detector = None
        camera_retry = detector_retry = 0.0
        last_report = 0.0
        try:
            while not self.stopping.is_set():
                with self.lock:
                    preview = time.monotonic() < self.preview_until
                following = self.enabled.is_set()
                if not following and not preview:
                    with self.lock:
                        self.state = 'idle'
                    self.wake.wait(.25)
                    self.wake.clear()
                    continue
                if time.monotonic() < camera_retry:
                    self.stopping.wait(.2)
                    continue
                try:
                    import cv2
                    if camera is None:
                        from picamera2 import Picamera2
                        with self.lock:
                            self.state = 'starting'
                        camera = Picamera2()
                        configure_camera(camera)
                        camera.start()
                        print('Shared camera started: 640x480 preview / follow', flush=True)
                    started = time.monotonic()
                    frame = camera.capture_array()
                    boxes = []
                    detection_error = ''
                    if following:
                        try:
                            if detector is None and started >= detector_retry:
                                detector = PersonDetector()
                            if detector is not None:
                                boxes, _ = detect_people(detector, frame)
                        except Exception as exc:
                            detector = None
                            detector_retry = time.monotonic() + 5
                            detection_error = f'Person detection unavailable: {exc}'
                            print(detection_error, flush=True)
                        if detector is None and not detection_error:
                            detection_error = 'Person detector waiting to retry; follow stopped'
                        box = max(boxes, key=lambda value: value[2] * value[3], default=None)
                        with self.lock:
                            self.latest = (started, box, frame.shape[1], frame.shape[0])
                        if time.monotonic() - last_report >= 1.0:
                            elapsed = time.monotonic() - started
                            left, right = follow_command(box, frame.shape[1], frame.shape[0])
                            if elapsed > .5:
                                reason = 'result stale (>500ms); drive stopped'
                                left = right = 0
                            elif box is None:
                                reason = 'no person detected; drive stopped'
                            else:
                                size = box[2] / frame.shape[1] if FOLLOW_SIZE_METRIC == 'width' else box[3] / frame.shape[0]
                                reason = f'person {FOLLOW_SIZE_METRIC}={size:.2f} of image'
                                if left == 0 and right == 0:
                                    reason += '; at/inside target distance'
                            print(f'Follow: {elapsed * 1000:.0f}ms, {len(boxes)} person(s), '
                                  f'{reason}, requested L={left:.2f} R={right:.2f}', flush=True)
                            last_report = time.monotonic()
                    if preview and time.monotonic() - self.jpeg_time >= .2:
                        ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                        if ok:
                            with self.lock:
                                self.jpeg, self.jpeg_time = encoded.tobytes(), started
                    with self.lock:
                        self.state = 'following' if following else 'preview'
                        self.error = detection_error
                    if not following:
                        self.stopping.wait(.15)
                except Exception as exc:
                    with self.lock:
                        self.error = f'Camera unavailable: {exc}'
                        self.state = 'error'
                        self.latest = (0.0, None, 640, 480)
                        self.jpeg = None
                    print(self.error, flush=True)
                    if camera is not None:
                        try:
                            camera.close()
                        except Exception:
                            pass
                        camera = None
                    camera_retry = time.monotonic() + 5
        finally:
            if camera is not None:
                camera.close()


def diagnose():
    """Save annotated frames without opening the controller or motor serial port."""
    import argparse
    from pathlib import Path
    import cv2
    from picamera2 import Picamera2

    parser = argparse.ArgumentParser(description=diagnose.__doc__)
    parser.add_argument('--output', default='/tmp/yardbot-follow-debug')
    parser.add_argument('--calibrate-1m', action='store_true',
                        help='Save spacing calibration while one person stands one meter from the camera')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    detector = PersonDetector()
    camera = Picamera2()
    try:
        configure_camera(camera)
        camera.start()
        print('Camera-only test; no motor commands. Keep your full width in view.', flush=True)
        if args.calibrate_1m:
            print('Calibration: stand ONE METER from the camera, alone, facing it with arms at your sides. Keep your full width visible; head/feet may be cropped. Starting in 5 seconds.', flush=True)
        time.sleep(5 if args.calibrate_1m else 2)
        widths = []
        for index in range(10):
            started = time.monotonic()
            frame = camera.capture_array()
            boxes, weights = detect_people(detector, frame)
            elapsed = time.monotonic() - started
            if len(boxes) == 1:
                x, y, w, h = boxes[0]
                # Width calibration tolerates top/bottom cropping, not side cropping.
                if x > 2 and x + w < frame.shape[1] - 2:
                    widths.append(w / frame.shape[1])
            for (x, y, w, h), weight in zip(boxes, weights):
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(frame, f'{float(weight):.2f}', (x, max(20, y)),
                            cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 255, 0), 1)
            filename = output / f'frame-{index:02d}.jpg'
            if not cv2.imwrite(str(filename), frame):
                raise OSError(f'Could not save {filename}')
            print(f'{filename}: {len(boxes)} person(s), {elapsed * 1000:.0f}ms', flush=True)
            time.sleep(1)
        if args.calibrate_1m:
            try:
                measured = save_calibration(widths, metric='width')
            except ValueError as exc:
                parser.exit(1, f'Calibration not saved: {exc}\n')
            print(f'Saved 1m calibration: person width={measured:.3f}, {FOLLOW_SETTINGS}. Restart Pi.py.', flush=True)
    finally:
        camera.close()


if __name__ == '__main__':
    diagnose()
