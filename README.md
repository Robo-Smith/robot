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
| Left | Toggle the password-protected YardBot hotspot |

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


### Follow-mode speed increase

`FOLLOW_SPEED_SCALE = 1.30` multiplies the forward speed request by 30%, and the
forward/wheel caps are now 84.5% (previously 65%). Centered-person requests of
38% and 58% become 49.4% and 75.4%. Pivot power, steering thresholds, motor
minimum constants, acceleration/deceleration rates, and immediate stops retain
their existing values. Actual ground speed depends on motor response and load.
Update `robot_control.py` and restart robot.service; calibration and Nano firmware
remain valid. Check stopping distance and tracking response at the higher speed.


### Faster follow steering

Pivot commands now span 39–52% instead of 30–40%, and the turning minimum is
36.4% instead of 28% (30% increases). The forward-arc differential gain is
1.105 instead of 0.85, giving 30% stronger wheel-speed differences until motor
minimums limit them. Ordinary arcs still keep both wheels forward. Center
hysteresis, steering release, ramps, and safety stops retain their behavior.
Update `robot_control.py` and restart robot.service. Watch for renewed overshoot
when checking the faster steering on the robot.


## Single-stick steering adjustment

Single-stick mode now scales the summed/clamped horizontal joystick input by
`SINGLE_STICK_STEERING_GAIN = 0.70`, reducing the steering request by 30%.
Full turn at rest requests +70%/-70%; combining both sticks cannot exceed this
steering limit. Forward/reverse throttle retains its full range, and manual,
follow, and dump control are unaffected. Mixing still clips individual wheels
at full scale, so the change in wheel-speed difference at full throttle depends
on saturation; this is a steering-input reduction, not a guaranteed 30% reduction
in physical yaw rate.

Update `robot_control.py` and restart robot.service. Possible later refinements
are a curved steering response for gentler center corrections, reduced steering
gain at high throttle, and acceleration ramps for single-stick mode. Evaluate the
new gain first before combining additional changes.


### Follow steering overshoot at higher forward speed

Follow steering has been restored to its pre-boost settings: 30–40% pivot
commands, 28% turning minimum, and 0.85 arc differential gain. This removes the
later 30% steering boost (about 23% lower than the boosted requests), while keeping
`FOLLOW_SPEED_SCALE = 1.30` and the 84.5% forward/wheel caps. Center hysteresis,
steering release, ramps, calibrated spacing, and single-stick settings retain
their behavior. Update `robot_control.py` and restart robot.service; check steering
on the robot because software tests do not measure actual overshoot.

## Self-hosted robot status page

`Pi.py` now starts a status dashboard on port **8080** in the same process as
the controller. From a phone/computer on the robot's network, open:

```text
http://YardBot.local:8080
```

If your network does not resolve `.local`, run `hostname -I` on the Pi and use
`http://<PI-IP-ADDRESS>:8080` (for example `http://192.168.1.42:8080`). This works
with the current Wi-Fi or Ethernet connection; hotspot setup is still a future
feature. Turning Wi-Fi off disconnects Wi-Fi clients from this page too.

Deploy updated `Pi.py` and `person_follower.py`, add `status_server.py` and
`controller_battery.py`, and copy the **web/** directory (including index.html)
beside them. Existing model/control modules must remain present. Restart with:

```sh
sudo systemctl restart robot.service
```

No service-file, Arduino firmware, calibration, or additional web framework install
is required. The existing OpenCV/Picamera2 packages provide camera support. If the
port is occupied, the robot logs the error and continues controller operation.

The responsive page shows current mode, controller connection, requested motor
outputs, battery telemetry when available, and a live camera feed. Status refreshes
once per second. Camera JPEGs refresh up to four times per second; a single shared
encoder caps image production at five frames per second. Pause feed stops requests,
and background browser tabs also stop asking for frames. With no viewers, preview
processing expires after three seconds. Follow detection continues independently
while follow mode is selected. The camera is opened only by the shared camera
worker, never by HTTP handlers, avoiding the earlier camera-in-use conflict.
Preview can work in manual/stop modes and without downloaded person models. A
preview request does **not** enable follow mode or send any motor commands.
The worker retains camera ownership while idle; stop robot.service before running
standalone camera diagnostics or calibration, as before. Camera and detector
errors are displayed and retried every five seconds. Stale preview images are
not served; a stalled robot heartbeat is displayed as unknown, not live telemetry.

### Controller battery versus voltage

The page reads `/sys/class/power_supply` for the connected Stadia controller using
its Bluetooth identity (or Stadia name when no identity is available). It shows
capacity if Linux exposes `capacity` and volts if it exposes `voltage_now` (the
kernel reports microvolts). Percentage is never converted into an estimated
voltage. Unsupported fields say **Not reported**; this depends on the controller
and driver. It does not measure robot battery or motor-controller supply voltage.
That would require voltage-sensing hardware and additional Nano telemetry.
See the [Linux power-supply ABI](https://github.com/torvalds/linux/blob/master/Documentation/ABI/testing/sysfs-class-power).

### Server settings

Defaults: `ROBOT_STATUS_HOST=0.0.0.0`, `ROBOT_STATUS_PORT=8080`. Port `0` disables
the web server. To change them for the service, use `sudo systemctl edit
robot.service` and add, for example:

```ini
[Service]
Environment=ROBOT_STATUS_PORT=8081
```

Then restart robot.service. For a terminal test: `ROBOT_STATUS_PORT=8081
/usr/bin/python3 Pi.py` (on one line), with robot.service stopped first.
The dashboard has explicitly enabled tele-operation endpoints; shutdown remains controller-only. It is
intended for a trusted local network: anyone on that network who can reach the
port can view the feed and telemetry. It has no authentication or HTTPS; do not
forward this port to the public internet. No external scripts, fonts or services
are needed by the page. Hotspot mode will use the same server once configured.

Verification includes loopback HTTP routes, mode updates, stale heartbeat handling,
shared camera ownership, preview isolation from autonomous mode, and conditional
battery/voltage parsing. Tests mock camera/controller/motor hardware. Real phone
layout and Pi streaming performance should be checked on the robot, especially
while follow mode is active.


## YardBot hotspot / field network

D-pad **left held for three seconds** now toggles a password-protected hotspot.
The Pi's Wi-Fi adapter was checked for AP support and an inactive profile was
prepared on this Pi. No active network was switched during setup. The profile
uses 2.4 GHz, WPA2-PSK/CCMP, no WPS, DHCP via NetworkManager, and fixed Pi address
**10.42.0.1**. It does not autoconnect on reboot; enter it explicitly with left.

Update `controller_actions.py` and add `hotspot.py` beside it, then restart:

```sh
sudo systemctl restart robot.service
```

On this Pi, obtain the generated credentials in your own terminal:

```sh
cd ~/robot
sudo /usr/bin/python3 hotspot.py --show-password
```

1. Save the displayed password before disconnecting from your home network.
2. Hold D-pad left for three seconds. The Pi leaves its current Wi-Fi and hosts
   the **YardBot** network. Bluetooth robot control continues independently.
3. Join YardBot from your phone/computer with the generated password.
4. If the device reports **No internet**, choose to stay connected. An internet
   connection is not required for robot control, the camera, or the dashboard.
5. Open **http://10.42.0.1:8080** in the browser (type the full address).
6. Release, then hold left for three seconds again to stop the hotspot and restore
   the previously active Wi-Fi profile. If it is out of range, restoration may
   fail; left can activate the hotspot again. Right still toggles the Wi-Fi radio.

The single onboard Wi-Fi adapter switches between client and access-point use;
it does not simultaneously stay connected to home/public Wi-Fi. The dashboard
is already bound to all interfaces, so no separate web service or camera process
is needed. The local robot network works away from home without joining a public
network. If Ethernet provides internet, NetworkManager's shared mode may share it;
internet access is not required or guaranteed. Existing public/saved Wi-Fi profiles
are not deleted or changed by this feature.

Credentials, the owned profile UUID, and previous Wi-Fi UUID are persisted in
`hotspot_settings.json` (mode 600, excluded from Git). Never commit or publish that
file. The Wi-Fi secret is supplied to nmcli via a private, short-lived password
file, not shell arguments or normal logs. It is not exposed by the dashboard.
The hotspot is not started automatically when robot.service starts. It continues
if only the Python service restarts, because NetworkManager owns the connection;
left can still exit it after the service restarts. Reboot returns to normal saved
Wi-Fi behavior (unless the radio was left disabled).

For a fresh installation on another Pi, prepare without disconnecting Wi-Fi:

```sh
cd ~/robot
sudo /usr/bin/python3 hotspot.py --setup
sudo /usr/bin/python3 hotspot.py --show-password
```

NetworkManager and dnsmasq are required; this Pi already has both. If shared-mode
activation reports a missing dnsmasq binary on another installation, install
`dnsmasq-base` using apt. The default adapter is wlan0; settings can be adjusted
before the initial setup on other hardware. Keep the credential file private.
Configuration follows the [NetworkManager connection settings](https://networkmanager.pages.freedesktop.org/NetworkManager/NetworkManager/nm-settings-nmcli.html)
and [nmcli activation/password-file documentation](https://networkmanager.pages.freedesktop.org/NetworkManager/NetworkManager/nmcli.html).

Actual hotspot activation, phone association, DHCP, and streaming in hotspot mode
still need a field test. Automated tests cover profile security, no activation
at setup, toggling, restoring the remembered home connection across service
restarts, temporary-secret cleanup, and restoring the previous radio/connection
when activation fails. These tests never change real network state.


## Web tele-operation

The dashboard now includes an explicit **Tele-operate** mode, available over the
home LAN or YardBot hotspot. It works without a connected Stadia controller.
Hold **Hold 1 second to enable** for a full second, then pick up the center of the
on-screen joystick and drag. A short enable tap or a tap on the joystick rim does
not drive. Touch and mouse are supported. Up/down controls forward/reverse and
left/right uses the same 70% steering gain as physical single-stick mode. Web
wheel commands are limited to 65%; the dump motor remains neutral.

Release the joystick to command zero while staying enabled. **Disable & stop web
driving**, Escape, page focus loss, hiding the tab, or leaving the page disables
the control session. On a phone the enabled layout prioritizes camera + joystick
and hides secondary telemetry until web driving is disabled. Only one browser
can hold control at a time. Another browser can still view status and camera.

Browser commands heartbeat every 100 ms. The server revokes the lease after
400 ms without a valid heartbeat and the motor loop stops on its next 50 ms tick.
A late command cannot reactivate an expired session: enable again explicitly.
Increasing sequence numbers reject delayed/out-of-order movement after a stop.
The Nano's independent serial watchdog and TF-Luna forward obstacle checks remain
active. Commands are not ramped; joystick release and disable stop immediately.

Stadia **A/B/X/Y** revokes browser control and selects that physical mode. Physical
axis/trigger inputs are ignored while web control is active. Shutdown and serial
or controller errors also revoke web control. A newly connected Stadia controller
does not automatically take over from an enabled browser; select a mode with a
button. Without Stadia, the robot starts stopped and can be enabled on the page.
Expired or disabled web control returns to stop, not an earlier driving mode.

The HTTP control endpoints require the page's request token and a matching
same-origin header. This prevents cross-site form commands; it is not user
account authentication. Anyone who can load this dashboard on your trusted LAN
or password-protected hotspot can deliberately enable driving. Keep it off the
public internet. The web page cannot activate hotspot, change Wi-Fi or shut down
the Pi. Tele-operation tokens are per-session and not stored on disk.

Deploy updated `Pi.py`, `status_server.py`, `web/index.html`, new `teleop.py`, and
`web/teleop.js`, then restart robot.service and reload the browser page. No Arduino
update or calibration is needed. Start with wheels lifted: verify short taps do
nothing, enable/drag/release, disable, physical X override, tab hiding, and loss of
Wi-Fi stop the robot. Software tests mock motors and camera; actual phone/browser
and radio behavior still require robot testing.

## OpenCV detection overlays in the web feed

The web camera feed now uses OpenCV to draw detection results directly onto the
JPEG frames. Green boxes show detected people and model confidence; in follow
mode the largest box (the selected target) is gold and labeled **Follow target**.
The banner explicitly distinguishes **No person detected**, **Detection stale**,
and **Detection unavailable**. A missing box on a visible person means the model
has not identified them; the robot cannot independently recognize a false negative.

Viewing the feed requests person detection even outside follow mode. These
preview-only results do not enable follow mode or provide autonomous motor input.
Labels say **Preview only** outside follow mode, including web tele-operation.
The camera and model are shared with follow mode, so overlays use the same frame
and inference result rather than a second camera connection/model. Motor mixing,
steering hysteresis and ramps still run separately in the controller loop.
The matching result is drawn on a frame copy, preserving the original image.
Preview-only detection may lower feed refresh rate on the Pi compared with raw
JPEG preview. It expires with viewer demand after three seconds; follow detection
continues when explicitly enabled. Stale results still stop autonomous drive.

Deploy updated `person_follower.py`, `status_server.py`, `web/index.html`, and new
`camera_overlay.py`; restart robot.service and reload the page. No calibration,
firmware or model download changes are needed. Check annotations on the Pi's real
camera feed; rendering tests use synthetic frames and worker tests mock hardware.

## ToF and robot telemetry on the dashboard

The Motor Requests panel now also shows:

- TF-Luna distance in centimeters and raw signal strength.
- Signal validity, sensor/packet freshness, and the existing forward stop/slow zone.
- Nano-applied left/right/dump commands after obstacle limiting, alongside the
  Pi's requested commands (neither is a wheel-speed measurement).
- Nano command watchdog state, telemetry age, and uptime.
- Pi CPU temperature and uptime, where the OS exposes them.

**Upload the updated `Arduino-Nano/Arduino-Nano.ino`** for the ToF/Nano fields.
Stop robot.service before uploading. Then deploy updated `Pi.py`, `status_server.py`,
`web/index.html`, new `nano_telemetry.py` and `web/telemetry.js`, restart robot.service,
and reload the page. Existing command frames and motor behavior are unchanged;
older firmware remains compatible but reports no telemetry. Pi temperature/uptime
do not require the Nano update. The A7 voltage-divider input remains unwired in
the documented hardware, so robot battery voltage is not invented or displayed.

Nano sends a bounded ASCII line five times per second:

```text
Tdistance_cm,signal,sensor_age_ms,command_age_ms,watchdog,left,right,dump,uptime_ms
```

Motor commands are signed -1000..1000. Ages saturate at 65535 milliseconds; sensor
age starts at 65535 until an I2C reading arrives. A complete frame is queued only
when Serial.availableForWrite reports enough space, so telemetry never waits for
UART capacity. The Pi reads at most 512 currently available bytes per control tick,
assembles partial lines, rejects malformed/oversized data, and marks packets stale
after one second. This follows the [Arduino nonblocking serial guidance](https://docs.arduino.cc/language-reference/en/functions/communication/serial/write/).

Signal validity matches the existing motor filter: strictly greater than 150 and
less than 55000. A sensor reading older than 500 ms is flagged on the page; the
firmware's existing use of its last sensor sample is unchanged. Forward output
is stopped below 20 cm and halved through 100 cm with a valid signal. The UI
shows raw unreliable readings as **unverified**, rather than treating them as a
confirmed obstacle distance. The Nano watchdog still stops all motors after
500 ms without a valid command. Its reported output is the command sent to PWM,
not physical motor feedback. Firmware uptime rolls over with Arduino millis().

Verification covers fragmented telemetry, malformed data, read-size limits,
staleness, threshold boundaries and dashboard JSON. A host C++ harness compiled
and exercised the sketch with stubbed hardware, checking telemetry against
obstacle limiting/watchdog behavior and a full transmit buffer. An actual AVR
build and physical ToF/dashboard check remain necessary on the robot.

## Front HC-SR04 sonar readings

The two documented front sonars are now read by the Nano and displayed in the
Motor Requests panel: front-left trigger D9 / echo D8, front-right trigger D12 /
echo D11. The rear sonar listed in the pin comments is still unused.

Pings alternate every 70 ms (each sensor roughly every 140 ms), reducing acoustic
cross-talk. Each uses a 10 microsecond trigger and echo width / 58 for centimeters,
following the [HC-SR04 datasheet](https://cdn.sparkfun.com/datasheets/Sensors/Proximity/HCSR04.pdf).
The echo wait is explicitly capped at 12000 microseconds, limiting the added wait
to about 12 ms per ping and the configured usable range to 2–200 cm. Missing,
too-short, or out-of-range echoes clear the reading; they are not interpreted as
zero distance or a confirmed clear path. Sensor readings expire after 500 ms.

Sonar is **telemetry-only** in this version. The existing TF-Luna is still the
source of motor obstacle limiting; sonar samples do not change drive commands.
Verify the corner readings on real obstacles before using them for motor control.

The Nano now alternates `T` and `S` frames every 100 ms, keeping both types at five
messages/second without exceeding the UART transmit buffer. Sonar frame format:

```text
Sleft_cm,right_cm,left_age_ms,right_age_ms
```

A zero distance means no usable echo. Ages saturate at 65535 ms. Each frame is
independently nonblocking on transmit and independently timestamped on the Pi.
Older T-only firmware still works, with the sonar fields showing Not reported.

Stop robot.service, upload the updated Nano sketch, update `nano_telemetry.py`,
`web/index.html`, and `web/telemetry.js`, then start robot.service and reload the
page. Verify each side separately with a large flat target 20–100 cm ahead of it,
and check that unplugged/no-echo readings do not appear as zero centimeters.
The host firmware harness covers timing/pin selection/conversion/telemetry and
the watchdog with simulated hardware; actual AVR compilation and sonar wiring
still need checking on the robot.

## Page mode selection and system controls

The Robot Controls panel now exposes Stop, physical Stadia single-stick mode,
follow-me, Wi-Fi **on**, hotspot switching, and Pi shutdown. Manual and Wi-Fi-off
are intentionally unavailable from the page. Web tele-operation retains its
separate hold-to-enable joystick controls.

Drive modes are mutually exclusive. Stop is immediate on the next control tick.
Single-stick selection requires a connected Stadia controller and clears cached
stick/trigger values, requiring fresh input. Follow-me uses a slide-to-confirm
control and keeps following if the page closes, like selecting Y on Stadia.
The current-mode display remains the source of truth even when the physical
controller changes modes.

Hotspot switching and shutdown use momentary **sliding confirmations**, not
independent on/off toggles. Begin near the left end and drag fully right; a tap
at the right edge does not execute the action. Keyboard users can move the
focused slider right and then press Enter to confirm. Sliders return to the left
after a request. Hotspot can switch either to YardBot or back to the previous
Wi-Fi and will disconnect the page during the transition. Retrieve credentials
locally before using it, then open http://10.42.0.1:8080 on YardBot. Shutdown
stops all motors first. Wi-Fi-on never turns a working radio off.

All actions use the same-origin/token checks as tele-operation and a bounded,
two-second request queue. The HTTP server never changes motors or system state
directly. The motor loop stops outputs and revokes browser joystick control before
applying a page selection, then dispatches system actions to the background worker.
Stop can replace a queued request. Physical mode selections cancel pending page
selections. Stale requests and disallowed modes are rejected. Existing controller
and web-driving timeout behavior remains in place. System completion/failure
messages are shown in the panel; network switching/shutdown may interrupt delivery.

Deploy updated `Pi.py`, `status_server.py`, `controller_actions.py`, `web/index.html`,
`web/teleop.js`, new `web_actions.py` and `web/controls.js`, then restart robot.service
and reload the page. No Nano update is required for these page controls.
The earlier statement that the web page cannot switch networks or shut down is
superseded by these explicitly confirmed actions. Use the trusted LAN/hotspot only.


### Blue/grey controls refresh

The dashboard now uses a blue and grey robot theme, with red reserved for the
prominent Stop All Motors button. Sliders are labeled “Slide to follow-me →”,
“Slide home / hotspot →”, and “Slide to shutdown Pi →”. Their existing deliberate
slide-to-confirm behavior is retained. The Wi-Fi-on button and web action have
been removed; the controller's existing Wi-Fi toggle is unaffected. This
supersedes the earlier page-control instructions mentioning a Wi-Fi-on button.

Deploy updated `web/index.html`, `web/controls.js`, `web_actions.py`, `Pi.py`, and
`controller_actions.py`; restart robot.service and reload the page. No Nano
firmware or calibration change is needed for this UI update.

## Tele-operation dump controls

The web tele-operation panel now has **Dump** (raise) and **Lower** buttons.
Enable tele-operation with the existing one-second hold first. Hold a button to
run the dump motor; release, pointer cancellation, or lost pointer capture stops
that command. Touch/mouse and Space/Enter holds are supported. Holding both
opposing controls commands neutral; releasing one continues the remaining held
direction. Joystick driving and dump operation can be used together.

The dump uses the same full-speed signed commands as fully pressed physical
triggers. Releasing the joystick stops the drives but leaves an independently
held dump button active. Disabling tele-operation, leaving/hiding the page,
losing focus, an expired heartbeat, physical mode override or Stop resets both
driving and dump. Dump is not available to a browser without its own valid enabled
lease. Old clients that omit dump still command neutral. This supersedes the
earlier description that web tele-operation always disables dump.

The extra camera-preview and joystick instruction sentences were removed from
the page to reduce clutter. Update `teleop.py`, `status_server.py`, `web/index.html`
and `web/teleop.js`, restart robot.service, and reload the page. No Nano update is
needed for these controls. Check direction/release/disable with the robot stopped
before operating the dump under load.


## UPower controller battery fallback

The battery reader now falls back to UPower when sysfs lacks charge percentage or
voltage. It enumerates gaming-input devices and matches the connected controller's
Bluetooth address, rather than selecting an unrelated battery. The observed
Stadia UPower object reports 99% charge and no voltage; the page displays the
percentage and leaves voltage as Not reported. No percentage-to-voltage conversion
is used. When no evdev identity is available, device details must identify Stadia.

The optional `upower` utility is queried in the HTTP status worker with a total
1.5-second budget; results use the existing ten-second dashboard cache. Missing
UPower or permissions do not affect driving. Coarse battery levels are shown as
levels rather than invented precise percentages, following the
[UPower device specification](https://upower.freedesktop.org/docs/Device.html).
Update `controller_battery.py` and restart robot.service to load the fallback.

### Phone hold buttons and text selection

The tele-operation controls now suppress text selection and touch callout menus
using WebKit-prefixed CSS, prevent default pointer-down behavior on enable, and
register non-passive touch gesture handlers on the enable/joystick/dump controls.
Context-menu/selection/drag gestures are suppressed only in the control area;
ordinary scrolling elsewhere on the page remains available. Hold/release and
pointer-cancellation behavior is retained. Update `web/index.html` and
`web/teleop.js`, then reload or close/reopen the page on the phone. No service or
firmware change is required. Simulated gesture checks pass; actual iOS/Android
long-press behavior needs checking on the device. See the
[Safari CSS reference](https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/SafariCSSRef/Articles/StandardCSSProperties.html)
for selection/callout properties.

### Mobile tele-operation connection stability

The HTTP server now supports persistent HTTP/1.1 connections, reducing repeated
TCP setup while video/status/control requests share a phone connection. Browser
command requests have a one-second response timeout instead of 300 ms, with up
to two regular control requests in flight and immediate release commands allowed
through. An isolated transport error does not disable control if a recent valid
acknowledgment still proves the session alive; server rejection still disables it.
Disconnect reasons remain visible rather than being replaced at the next status
refresh. This helps distinguish focus loss, robot readiness, network timeouts,
and an expired/overridden session on a phone without a developer console.

Out-of-order commands now receive a successful ignored acknowledgment and do not
extend the lease or change motor outputs. This avoids treating an old request
arriving after a release as a lost session. The server's **400 ms command lease**
and the Nano's watchdog remain unchanged; a prolonged network interruption still
stops motors and requires enabling again. No automatic re-enabling is added.
Update `status_server.py`, `teleop.py`, and `web/teleop.js`, restart robot.service,
and reopen the page. Check real phone behavior with wheels lifted. If control
still disables, record the displayed reason before pressing enable again.
