# Code useful for home robots
* Motor controls and digital sensor integration on the Arduino Nano.
    * Rationale: they have large example sets, are pretty forgiving hardware, cheap, and already are on hand.
* Higher level and more complex logic will be handled through Python on the Raspberry Pi 4.
    * Rationale: adequate guides and similar examples, relatively cheap, and are already on hand.
* This code will be used with differential drive robots, that will share the same root code and much of its functionality, with special configurations being addressed as the time comes.

## To Do:(Not in any order)
 * voice activation PicoVoice control of modes https://picovoice.ai/docs/quick-start/orca-python/
 * Serial exchange from Pi to Arduino heartbeats and watchdog  https://roboticsbackend.com/raspberry-pi-arduino-serial-communication/
 * Camera functionality tensor flow or https://www.raspberrypi.com/documentation/computers/camera_software.html#rpicam-apps
 * Establish Modes through controller buttons
    1. Stop
    2. Stadia controlled
    3. OpenCV tracking or Open Bot
 * CAN motor control https://forums.raspberrypi.com/viewtopic.php?t=296117
 * ROS integration https://docs.ros.org/en/foxy/How-To-Guides/Installing-on-Raspberry-Pi.html
 * Start script in terminal on startup - https://forums.raspberrypi.com/viewtopic.php?f=66&t=294014
       * sudo nano /etc/xdg/lxsession/LXDE-pi/autostart
          * @lxpanel --profile LXDE-pi
          * @pcmanfm --desktop --profile LXDE-pi
          * @xscreensaver -no-splash
          * @lxterminal -e python3 /path/Pi.py - BROKE BLUETOOTH and did not open a terminal
     * Alaternatively??? start script Pi.py sudo nano /etc/xdg/autostart/display.desktop https://www.makeuseof.com/how-to-run-a-raspberry-pi-program-script-at-startup/
 * Bluetooth use rfcomm https://forums.raspberrypi.com/viewtopic.php?t=320455

## References: 
   * Pi safe shutdown button https://scribles.net/adding-power-switch-on-raspberry-pi/
   * Setup Arduino on Pi (scroll down to ARM) https://magpi.raspberrypi.com/articles/program-arduino-uno-raspberry-pi
   * Setup Github on Pi (Remember SSH no longer works) https://www.theserverside.com/blog/Coffee-Talk-Java-News-Stories-and-Opinions/Fix-GitHubs-support-for-password-authentication-was-removed-error
      1. cd robot
	   2. git pull (without login: git clone https://github.com/rsmith8/robot.git)
	   3. git add --all #or file name eg. README.md
     	4. git commit -am "Notes..."
     	5. git push
   * Pi4 case https://www.printables.com/model/106225-modular-snap-together-raspberry-pi-2b3b3b4-case-w-
   * https://www.raspberrypi.com/documentation/computers/
   * Pin out and Pi references https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio
   * https://docs.arduino.cc/learn/electronics/servo-motors/
   * Kitronik Simply Servos Board for Raspberry Pi Pico https://www.sparkfun.com/products/20040
        https://github.com/KitronikLtd/Kitronik-Pico-Simply-Servos-MicroPython
   * Mount and SD card https://www.wikihow.com/Linux-How-to-Mount-Drive#:~:text=To%20mount%20a%20drive%20on,to%20mount%20and%20unmount%20drives.
      * lsblk -lf
      * sudo mkdir /media/mydrive
      * sudo mount /dev/XXXX /media/mydrive
      * sudo umount /media/myflashdrive
   * Bluetoothctl issues fixed: https://raspberrypi.stackexchange.com/questions/122429/raspberry-pi-4-wont-pair-to-bluetooth-devices
   * Fix Bluetooth from https://return2.net/fix-bluetooth-problems-on-raspberry-pi-running-raspbian/
      * Reinstall Bluetooth packages: sudo apt purge bluez && sudo apt install bluez. 
      * Reinstall pi-bluetooth: sudo apt purge pi-bluetooth && sudo apt install pi-bluetooth. 
   * Bluetooth use rfcomm https://forums.raspberrypi.com/viewtopic.php?t=320455
   * TF Luna sensor example https://www.waveshare.com/wiki/TF-Luna_LiDAR_Range_Sensor
   * Run code on startup use 'systemd' from https://learn.sparkfun.com/tutorials/how-to-run-a-raspberry-pi-program-on-startup/method-3-systemd
   https://forums.raspberrypi.com/viewtopic.php?p=2292242&hilit=Bluetooth#p2292242
raspi-info

## Build Instructions
 1. Hardware:
    * Yardbot - endless hours to build
    * Raspberry Pi4 and supplies
    * Wide FoV Pi camera
    * TF-Luna Sensor on I2C
    * 5x Jaguar Speed controllers or other PWM motor controller
    * circuit breaker for battery and fuse bus for each peripherial
    * Wiring pin layout in Arduino firmware
 2. Install Raspberry Pi OS using Raspberry Pi Imager https://www.raspberrypi.com/software/
 3. Configure Pi for wifi (2.4 ghz), VNC enabled, and bluetooth connection for controller
 4. Startup and configure software 
    * Get github personal access token - settings - developer settings, copy and paste as password on clone command
    * git clone https://github.com/rsmith8/robot.git
    * setup Arduino https://magpi.raspberrypi.com/articles/program-arduino-uno-raspberry-pi
      * install library -> Adafruit NeoPixel      
      * install 'Arduino-Nano.ino' firmware
    * sudo apt install python3-evdev
       * python -m evdev.evtest
    * Configure service to start Pi.py
       * sudo cp robot/robot.service /lib/systemd/system/
       * sudo systemctl daemon-reload
       * sudo systemctl enable robot.service
    * python3 -m pip config set global.break-system-packages true
    * pip3 install pvorca
    * Automate STARTUP....
 5. Run from terminal
   * cd robot
   * python3 Pi.py


## Controller modes (Pi.py + Arduino-Nano/Arduino-Nano.ino)

Upload the updated Nano sketch and update the Pi files together: the new protocol
is `Cleft,right,dump\n`, with signed values from -1000 to 1000. The Pi sends a
complete frame every 50 ms. The Nano stops **all three motors** after 500 ms
without a valid frame. Neutral is 90 for every motor controller.

| Button | Mode | Drive | Dump |
| --- | --- | --- | --- |
| A | Manual (also startup/reconnect default) | Left/right stick Y independently | Triggers |
| X | Stop | Disabled | Disabled |
| B | Single stick | Both sticks' X and Y summed, clamped, then differential mixed | Triggers |
| Y | Follow | Camera person detection | Disabled |

Single-stick forward = clamp(left forward + right forward); turn = clamp(left X +
right X). Left = clamp(forward + turn), right = clamp(forward - turn). Opposing
sticks cancel; either stick can take over seamlessly. An 8% center deadband is
applied. Existing Stadia mappings are retained: left X/Y = ABS_X/ABS_Y, right X/Y
= ABS_Z/ABS_RZ, lower/raise = ABS_BRAKE/ABS_GAS. Simultaneous triggers subtract.
Selecting a mode sends neutral immediately; manual/single then use current stick
and trigger positions on the next control tick. Center the controls before switching.

### Check the Pi when it is available

Run these on the Pi and save their output:

```sh
cat /etc/os-release
uname -m
cat /proc/device-tree/model
rpicam-hello --list-cameras
```

On older systems, use `libcamera-hello --list-cameras` if `rpicam-hello` is absent.
The camera list identifies the attached sensor. The camera itself may also have
its model printed on the board. The follow implementation uses Picamera2 (the
modern libcamera stack), not legacy Picamera. See the
[Raspberry Pi camera documentation](https://www.raspberrypi.com/documentation/accessories/camera-software.html)
and [Picamera2 support requirements](https://github.com/raspberrypi/picamera2).

On a compatible Raspberry Pi OS installation:

```sh
sudo apt update
sudo apt install python3-evdev python3-serial python3-picamera2 python3-opencv
```

Use `/usr/bin/python3` as in robot.service so the OS camera packages are visible.
No display is needed. Detection uses MobileNet-SSD through OpenCV DNN;
run `/usr/bin/python3 download_person_model.py` once to download its model files.
Only the VOC person class at confidence >= 0.70 is accepted. Camera initialization happens on the first Y press. Camera errors leave
follow mode stopped; restart Pi.py after correcting them.

### Following distance and initial checks

Following uses the largest person detection in each frame, not identity tracking.
It can change targets when multiple people appear. No detection or a result older
than 0.5 seconds commands zero drive; there is no search motion or automatic
reverse. Detection runs separately from the controller loop. Slow camera processing
may therefore keep the robot stopped until resolution/detection performance is tuned.

Image height is an **approximation of spacing**, not a measurement in meters.
In `robot_control.py`, tune `FOLLOW_TARGET_SIZE` (default 0.65) to the fraction of
the image occupied vertically by a person at the desired distance. Larger values
allow closer following. The 0.04 margin stops slightly before that target.
`FOLLOW_MAX_SPEED` and `FOLLOW_MAX_TURN` default to 0.25 and 0.20 of full output;
combined wheel output can reach 0.45. The existing TF-Luna thresholds remain:
stop forward motion below 20 cm, halve it through 100 cm when signal is valid.
It is an obstacle safeguard, not the source of person distance.

First verify with drive wheels lifted: startup neutral, manual directions,
each single stick, combined sticks, trigger directions, X stopping all motors,
and the Nano stopping when the Pi process is terminated or USB is disconnected.
Then test Y in a clear space at low speed with X readily available, checking
turn direction, person loss, close-person stopping, and spacing calibration.
Hardware/camera performance must be checked on the robot before unattended use.

Local logic checks: `python3 -m unittest discover -s tests`.

### Bring up the controller modes without a camera

Manual, stop and single-stick do not require OpenCV, Picamera2, or a connected
camera. Camera packages are imported only after Y is pressed. With no camera,
Y leaves drive and dump stopped; A or B returns to controller operation.

1. Stop the running service before uploading/testing: `sudo systemctl stop robot.service`.
2. Install controller dependencies: `sudo apt install python3-evdev python3-serial`.
3. Upload `Arduino-Nano/Arduino-Nano.ino` using the Arduino IDE (Nano board;
   Servo and Adafruit NeoPixel libraries; current Arduino AVR Boards core for
   `Wire.setWireTimeout`). Keep the service stopped until both sides are updated.
4. From the updated repository run `/usr/bin/python3 Pi.py`. Keep `Pi.py`,
   `robot_control.py`, and `person_follower.py` in the same directory.
5. With wheels lifted, check independent drives and triggers in manual, both
   sticks and triggers in B, X while all controls are held, then A to resume.
   Hold a drive input steady for several seconds to verify the heartbeat keeps
   it running. Ctrl+C must stop everything; the Nano watchdog is the fallback
   if the Pi stops sending commands.
6. When these checks pass, use `sudo systemctl start robot.service` and inspect
   `tail -f /home/rs/robot.log`. Do not run the service and a terminal copy at
   the same time, because they would compete for the controller/serial port.

If connection fails, check `ls -l /dev/ttyUSB* /dev/ttyACM*` for the Nano's port
and `python3 -m evdev.evtest` for controller detection. Update `SERIAL_PORT` in
`Pi.py` if the Nano is not `/dev/ttyUSB0`.

### Inspect missed person detections

Stop robot.service and any terminal Pi.py first, then run:

```sh
/usr/bin/python3 person_follower.py
```

This camera-only diagnostic sends no motor commands. It saves ten frames, about
one second apart, to `/tmp/yardbot-follow-debug/frame-00.jpg` through
`frame-09.jpg`, with green boxes and detector scores for detected people. Inspect
these images to check orientation, lighting, and whether head and feet are visible.
The follow camera now requests the IMX219's 1640x1232 sensor mode and downscales
to 640x480, avoiding its cropped native VGA mode. See the
[Picamera2 manual](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf)
for how raw stream size selects the sensor mode. Detector processing remains at
640x480; lost-person stopping and speed limits are unchanged.


### MobileNet-SSD person detector (replaces HOG)

The earlier HOG detector produced background false positives in this setup.
Both camera diagnostics and follow mode now use the same MobileNet-SSD detector,
filtering for the VOC person class at 70% confidence with duplicate suppression.
This is a candidate improvement, not a guarantee against false positives.

Update `person_follower.py`, `person_detector.py`, and `download_person_model.py`
on the Pi, stop robot.service/any running Pi.py, then run:

```sh
cd ~/robot
/usr/bin/python3 download_person_model.py
/usr/bin/python3 person_follower.py
```

The downloader fetches about 23 MB into `models/` beside the scripts from the
[upstream MobileNet-SSD project](https://github.com/chuanqi305/MobileNet-SSD).
Internet is needed only for this explicit setup step. The model is not bundled
in git. Manual, stop, and single-stick modes do not load it. Missing models stop
follow mode with setup instructions. Existing OpenCV packages provide the DNN
backend; TensorFlow, PyTorch, and pip installs are not required.

Inspect the saved images for boxes on the actual person and check empty scenes,
including the background light. Counts alone do not establish correct detection.
Images are overwritten by each diagnostic run. Report inference times too: the
500 ms freshness limit still stops follow output if processing takes too long.
The model's preprocessing and class ordering follow the upstream demo. If results
are correct, retry Pi.py with wheels lifted before checking movement on the ground.

Controller queue overflow (`SYN_DROPPED`) now stops all motors, discards events
through the next synchronization report, and rereads current axes without
reopening serial/resetting the Nano. It stays in stop mode until a fresh A/B/Y
press; center the controls first. This follows the Linux evdev recovery protocol.

With the default follow settings, a detected height >= 0.61 of image height
commands zero output (0.65 target minus 0.04 margin). Stand farther back so the
logged height is about 0.40–0.50 for an initial wheels-lifted movement check.
At height 0.59, output is only about 0.04, possibly below the motor deadband;
a nonzero logged request does not prove that the motors physically move.

### One-meter spacing and motor deadband

Follow mode now floors each nonzero wheel request to 12% to clear the observed
~10% motor deadband. Zero remains zero; person-loss and close-person stopping
remain immediate. Existing maximum commands are unchanged. This compensation
only applies to follow mode. It can make motion near the stopping boundary more
abrupt; check behavior with wheels lifted before a ground test.

To set approximate one-meter spacing, update `robot_control.py` and
`person_follower.py`, stop robot.service and any running Pi.py, then run:

```sh
cd ~/robot
/usr/bin/python3 person_follower.py --calibrate-1m
```

During the five-second countdown, stand one meter from the camera, centered and
alone, with head and feet visible. Stay still through the ten samples. Calibration
uses the median height of frames containing exactly one person. It requires at
least five such frames and rejects inconsistent or nearly full-image heights.
Inspect the annotated images to confirm that the boxes cover the person.
It writes `follow_settings.json` beside the scripts; restart Pi.py to load it.
The calibration offsets the existing stop margin so your measured image size
corresponds to the stop point. Change camera angle/height or the person and this
approximation can change; it is not a measured metric range. To undo calibration,
rename that settings file and restart Pi.py. Recalibrate after changing the camera.


### One-meter calibration when head or feet are outside the image

New `--calibrate-1m` runs use detected person **box width**, not height. Top and
bottom cropping is allowed; keep the full width of the person visible, face the
camera, arms at your sides, and stand still one meter from the camera. Side-clipped
boxes and frames with multiple detections are excluded. At least five stable
single-person samples are needed. Run the same calibration command again after
updating `robot_control.py` and `person_follower.py`, then restart Pi.py.

The saved file records `metric: width`; existing height calibrations continue to
load until replaced. A failed calibration leaves any existing settings untouched.
This supersedes the earlier full-body requirement for one-meter calibration.
Turning sideways or moving arms changes apparent width, so it remains approximate
spacing for a person facing the camera. Check boxes in the saved images before
using the calibration. No motor commands are sent by calibration.


### Follow speed tuning

Follow mode now uses relative error from the calibrated person size instead of
raw image-size difference. Defaults in `robot_control.py` are `FOLLOW_MAX_SPEED =
0.65`, `FOLLOW_SPEED_GAIN = 0.80`, `FOLLOW_MIN_WHEEL_SPEED = 0.18`, and
`FOLLOW_MAX_WHEEL_SPEED = 0.65`. Every wheel is capped at 65%, including during
steering. For a centered person, a width 25% smaller than the calibrated width
requests about 38% drive; half the calibrated width requests 58%. It slows toward
the 18% minimum near the target and stops at the calibrated size. These replace
the earlier 25% forward limit and raw-size gain. Existing calibration files remain
valid. TF-Luna can still halve forward output within its 100 cm caution zone.
Update `robot_control.py` and restart Pi.py to apply; no firmware upload or
recalibration is needed. First test the changed response with wheels lifted.


### Stronger low-speed follow turns

Steering outside the existing center deadband now starts at a 30% differential
command and rises to 40% (`FOLLOW_MIN_TURN`, `FOLLOW_MAX_TURN`). During turns,
each nonzero wheel command has a 28% floor (`FOLLOW_MIN_TURN_WHEEL_SPEED`).
This gives more power to slow turns/pivots and can reverse the inside wheel.
Straight driving retains its 18% minimum; every wheel is still capped at 65%.
Close-person, missing-person and stale-result stops still command zero. Update
`robot_control.py` and restart Pi.py; calibration and firmware do not change.

## D-pad system controls

In any drive mode, hold exactly one direction continuously for three seconds:

| Direction | Action |
| --- | --- |
| Down | Stop all motors and request Pi shutdown |
| Right | Toggle the Wi-Fi radio off/on according to its current state |
| Left | Log a hotspot request (placeholder; no network changes yet) |

Short holds and diagonals cancel. Each action fires once per hold; release and
hold again to repeat. Wi-Fi toggling leaves Bluetooth available for controller
input, but turning Wi-Fi off disconnects Wi-Fi SSH/VNC sessions. Hold right again
to enable the radio; reconnection depends on the existing network profiles.
Shutdown locks out drive-mode selection while the OS request is pending. If the
request fails, motors stay stopped and a fresh mode selection can resume control.
System commands run in a background worker, keeping the controller loop and motor
heartbeat responsive. Errors are printed to the normal robot log. Lost controller
events cancel holds and require a release/fresh hold before another system action.

Update `Pi.py` and add `controller_actions.py` beside it, then restart robot.service.
The existing service runs as root and can execute system commands. Ordinary
terminal runs may lack permission; failures are logged without prompting for a
password. No sudoers changes are needed for service operation. Right requires
NetworkManager/nmcli; check its availability without changing network state:

```sh
command -v nmcli
nmcli -t -f WIFI radio
```

Wi-Fi commands follow the
[NetworkManager nmcli documentation](https://networkmanager.pages.freedesktop.org/NetworkManager/NetworkManager/nmcli.html).
Shutdown uses `systemctl --no-ask-password poweroff`, following the
[systemd documentation](https://freedesktop.org/software/systemd/man/latest/systemctl.html).
Neither Wi-Fi changes nor shutdown commands are executed by the automated tests;
hold timing, command dispatch, and failure handling are tested with mocks.

## Follow-mode wheel ramps

`Pi.py` now applies an independent time-based ramp to each follow-mode wheel
command after person detection and steering mixing. Acceleration above the usable
motor minimum is 30 percentage points/second (`FOLLOW_ACCELERATION = 0.30`),
normal deceleration is 60 points/second (`FOLLOW_DECELERATION = 0.60`). Reversing
a wheel first decelerates it to zero, keeps zero for that update, then starts
in the opposite direction. At startup it steps to 18% for straight driving or
28% during turns; commands below those minima are skipped because they do not
reliably move this robot. Switching into turning can therefore still create a
small step when the usable minimum increases. Wheel commands remain capped at 65%.

Both-zero follow requests (person loss, stale camera results, close-person stop)
reset the ramp and command zero immediately. X, mode changes, controller recovery,
shutdown, and reconnecting also reset/bypass it. The Nano's TF-Luna obstacle stop
and serial timeout remain independent of this Pi-side ramp. A control-loop pause
of at least 500 ms resets ramp history to avoid resuming at a previous high speed.
Manual and single-stick inputs are not ramped. Camera-position/box smoothing has
not been added at this stage.

Copy updated `Pi.py` and `robot_control.py` to the Pi and restart robot.service.
No firmware update or recalibration is required. Check forward speed changes,
low-speed turns, reversal, X, and person loss with wheels lifted before driving.
Follow log lines show the requested detection-based outputs **before** the ramp;
the serial commands sent to the Nano contain the ramped outputs.

## Follow steering stability

Ordinary tracking now uses forward arcs instead of reversing the inside wheel
for small corrections. The outside wheel has a 28% target minimum during a turn;
the inside wheel stays forward with an 18% minimum. Pivots remain available for
large horizontal offsets (normalized error >= 0.70), retaining 30–40% differential
power. Stateful pivot handling returns to arcs below 0.50 error.

Corrections begin outside normalized error 0.18 and release inside 0.08. Between
those thresholds the existing correction is retained, reducing chatter. An error
of 0.18 means the person center is 9% of the full image width from image center.
No temporal camera filter is added, avoiding extra delay while approaching center.
When the requested turn centers or changes direction, the ramp promptly removes
the old wheel difference by lowering the faster wheel to the slower forward
wheel, or stopping opposed wheels. It then ramps toward the new request. This
steering-release behavior supersedes a strict independent wheel deceleration
limit for obsolete turn commands. Safety stops still bypass all ramps.

Update `robot_control.py` and `Pi.py`, then restart robot.service. Existing spacing
calibration is retained. Detection-worker logs remain stateless requested outputs;
the control loop also applies steering hysteresis and the motor ramp before
sending commands. Check center tracking and large turns with wheels lifted, then
check for oscillation on the ground; hardware dynamics are not simulated by tests.
