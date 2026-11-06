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
    def __init__(self):
        self.lock = threading.Lock()
        self.latest = (0.0, None, 640, 480)
        self.enabled_since = float("inf")
        self.enabled = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def set_enabled(self, enabled):
        self.enabled_since = time.monotonic() if enabled else float("inf")
        if enabled:
            self.enabled.set()
        else:
            self.enabled.clear()
        with self.lock:
            self.latest = (0.0, None, 640, 480)

    def detection(self):
        with self.lock:
            timestamp, box, width, height = self.latest
        if timestamp < self.enabled_since or time.monotonic() - timestamp > 0.5:
            box = None
        return box, width, height

    def _run(self):
        camera = None
        try:
            # Manual, stop and single-stick need no camera packages or hardware.
            self.enabled.wait()
            from picamera2 import Picamera2
            detector = PersonDetector()
            camera = Picamera2()
            configure_camera(camera)
            camera.start()
            print("Follow camera started: MobileNet-SSD, confidence >=70%, 640x480; stand with your full body in view", flush=True)
            last_report = 0.0
            while True:
                self.enabled.wait()
                started = time.monotonic()
                frame = camera.capture_array()
                boxes, weights = detect_people(detector, frame)
                # Initial policy: choose the largest detected person.
                box = max(boxes, key=lambda b: b[2] * b[3], default=None)
                with self.lock:
                    self.latest = (started, box, frame.shape[1], frame.shape[0])
                finished = time.monotonic()
                if self.enabled.is_set() and finished - last_report >= 1.0:
                    elapsed = finished - started
                    height, width = frame.shape[:2]
                    if started < self.enabled_since:
                        reason = "waiting for a frame from this mode selection"
                        left = right = 0.0
                    elif elapsed > 0.5:
                        reason = "result stale (>500ms); drive stopped"
                        left = right = 0.0
                    elif box is None:
                        reason = "no person detected; drive stopped"
                        left = right = 0.0
                    else:
                        left, right = follow_command(box, width, height)
                        size = box[2] / width if FOLLOW_SIZE_METRIC == 'width' else box[3] / height
                        reason = f"person {FOLLOW_SIZE_METRIC}={size:.2f} of image"
                        if left == 0 and right == 0:
                            reason += "; at/inside target distance"
                    print(f"Follow: {elapsed * 1000:.0f}ms, {len(boxes)} person(s), "
                          f"{reason}, requested L={left:.2f} R={right:.2f}", flush=True)
                    last_report = finished
        except Exception as exc:
            print(f"Follow camera unavailable; follow mode will stop: {exc}", flush=True)
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
