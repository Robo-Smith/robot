/*----Code for Arduino-Nano with pin layout------------
 Top Left
  --
  Pin 4 GND                             (Wired)
  PIN D6 Sonar REAR ECHO                (Wired)
  PIN D8 Sonar  FL ECHO                 (Wired)
  PIN D9 Sonar  FL TRIG                 (Wired)
  PIN D10 Neo                           (Wired) 0)RF-Bumper 1)LF-Bumper 2)Top (G,R,B)
  PIN D11 Sonar FR ECHO                 (Wired)
  PIN D12 Sonar FR TRIG                 (Wired)
  --
 USB
  --
  PIN D13 Sonar REAR TRIG               (Wired)
  PIN A0/D14 PWM Left/Throttle          (wired)
  PIN A1/D15 PWM Right/Steer            (wired)
  PIN A2/D16 PWM Dump			              (wired)
  PIN A4 ToF SDA I2C bus at 115200 baud (wired)
  PIN A5 ToF SCL I2C bus at 115200 baud (wired)
  PIN 29 GND                            (Wired)
  PIN 30 +5V (Vin 7-12V move to 27? +5) (wired)
  --
 Top Right

 Notes to add in code:
  PIN A7 Voltage divider                empty
  PWM Pins 3, 5, 6, 9, 10, 11

  alternative for mecanum
     PIN A0/D14 PWM LF		              (wired)
     PIN A1/D15 PWM RF		              (wired)
     PIN A2/D16 PWM RR		              (wired)
     PIN A3/D17 PWM LR		              (wired)
--------------------------------------------------------*/

#include <Servo.h>
#include <Adafruit_NeoPixel.h>
#include <Wire.h>
#include <stdio.h>

byte deviceAddress = 0x10;  // The address of the TF-Luna device is 0x10
#define PIN 10              //Neopixel is attached to  
#define NUMPIXELS   4       // number of neopixels in strip  
Adafruit_NeoPixel pixels(NUMPIXELS, PIN, NEO_GRB + NEO_KHZ800);
int delayval = 100;         // timing delay in milliseconds pause between pixels 
unsigned int distance = 0;  // TF-Luna signal
unsigned int signalStrength = 110; // TF-Luna signal range mp 100>Amp<65535
int counter=0;            // counts connected arduino and stadia devices
int alivecount=0;
int range_stop=20;
int range_close=100;
// Signed commands: positive drive is forward; positive dump raises the bed.
int leftDriveCommand = 0;
int rightDriveCommand = 0;
int dumpCommand = 0;
unsigned long lastCommandMs = 0;
const unsigned long commandTimeoutMs = 500;
char commandBuffer[48];
byte commandLength = 0;
bool commandOverflow = false;
unsigned long lastSensorMs = 0;
bool sensorSeen = false;
unsigned long lastTelemetryMs = 0;
bool sonarTelemetryNext = false;
const byte sonarTriggerPins[2] = {9, 12};
const byte sonarEchoPins[2] = {8, 11};
unsigned int sonarCm[2] = {0, 0}; // Zero means no usable echo, never zero distance.
unsigned long sonarSampleMs[2] = {0, 0};
bool sonarSampled[2] = {false, false};
unsigned long lastSonarPingMs = 0;
byte nextSonar = 0;

void updateSonar() {
  if (millis() - lastSonarPingMs < 70) return;
  lastSonarPingMs = millis();
  byte index = nextSonar;
  nextSonar = 1 - nextSonar;
  digitalWrite(sonarTriggerPins[index], LOW);
  delayMicroseconds(2);
  digitalWrite(sonarTriggerPins[index], HIGH);
  delayMicroseconds(10);
  digitalWrite(sonarTriggerPins[index], LOW);
  // Bound each measurement to 12ms (~2m); no default one-second pulseIn wait.
  unsigned long echoUs = pulseIn(sonarEchoPins[index], HIGH, 12000UL);
  unsigned int cm = (unsigned int)((echoUs + 29) / 58);
  sonarCm[index] = echoUs && cm >= 2 && cm <= 200 ? cm : 0;
  sonarSampleMs[index] = millis();
  sonarSampled[index] = true;
}

const int leftPwmPin = 14;  // PWM output for left joystick is 14 on yardbot - test board is 6
const int rightPwmPin = 15; // PWM output for right joystick is 15 on yardbot - test board is 6
const int dumpPwmPin = 16;  // PWM output for dumping is 16 on yardbot - test board is 6
const int spareMotorPin = 17;

Servo leftPWM;   // create servo object to control a servo
Servo rightPWM;  // create servo object to control a servo
Servo dumpPWM;   // create servo object to control a servo
// Pin 17 is reserved; no fourth motor is attached.


void setup() {
  for (byte index = 0; index < 2; index++) {
    pinMode(sonarTriggerPins[index], OUTPUT);
    digitalWrite(sonarTriggerPins[index], LOW);
    pinMode(sonarEchoPins[index], INPUT);
  }
  pixels.begin();               //INITIALIZE NeoPixel strip object (REQUIRED)
  Wire.begin();                 //The I2C bus communication starts for ToF sensor
  Serial.begin(115200);         //Start serial communication with Pi
  leftPWM.attach(leftPwmPin);   //Attaches the servo on pin to the servo object
  rightPWM.attach(rightPwmPin); //Attaches the servo on pin to the servo object
  dumpPWM.attach(dumpPwmPin);   //Attaches the servo on pin to the servo object
  leftPWM.write(90);
  rightPWM.write(90);
  dumpPWM.write(90);
  Wire.setWireTimeout(25000, true); // Bound a stalled I2C transaction (AVR Wire).
  pixels.setPixelColor(0, pixels.Color(0, 50, 0)); //GRB
  pixels.setPixelColor(1, pixels.Color(0, 50, 0)); //GRB
  pixels.setPixelColor(2, pixels.Color(0, 50, 0)); //GRB
  pixels.setPixelColor(3, pixels.Color(50, 0, 0)); //GRB
  }

void loop() {
  updateSonar();
  Wire.beginTransmission(deviceAddress);  //The I2C data transmission starts
  Wire.write(0x00);                       //Send command
  Wire.endTransmission();                 //The I2C data transfer is complete
  Wire.requestFrom((uint8_t)deviceAddress, (uint8_t)7); //Read 7 bytes of data 

 //Inputs&Dump_Out-----------------------------------------------------------------------
  if (Wire.available() == 7) { //ToF Sensor - 7 bytes of data are available
    byte data[7];
    for (int i = 0; i < 7; i++) {
      data[i] = Wire.read(); //Read data into an array
    }
    lastSensorMs = millis();
    sensorSeen = true;
    distance = (data[1] << 8) | data[0]; //Distance Value
    signalStrength = (data[3] << 8) | data[2]; //Signal Strength Signal Dist value is unreliable when Amp < 100 or Amp = 65535 (Overexposure) 
  }
  // Nonblocking parser: accept only complete, validated command frames.
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n') {
      commandBuffer[commandLength] = '\0';
      int left, right, dump;
      char extra;
      if (!commandOverflow && sscanf(commandBuffer, "C%d,%d,%d%c", &left, &right, &dump, &extra) == 3
          && left >= -1000 && left <= 1000 && right >= -1000 && right <= 1000
          && dump >= -1000 && dump <= 1000) {
        leftDriveCommand = left;
        rightDriveCommand = right;
        dumpCommand = dump;
        lastCommandMs = millis();
        alivecount = 0;
      }
      commandLength = 0;
      commandOverflow = false;
    } else if (commandLength < sizeof(commandBuffer) - 1) {
      commandBuffer[commandLength++] = ch;
    } else {
      commandOverflow = true;
    }
  }
  bool watchdogStopped = millis() - lastCommandMs >= commandTimeoutMs;
  if (watchdogStopped) {
    leftDriveCommand = rightDriveCommand = dumpCommand = 0;
  }
  int leftOutput = leftDriveCommand;
  int rightOutput = rightDriveCommand;
  // Keep the existing TF-Luna forward stop/slow thresholds. Reverse remains available.
  if (signalStrength > 150 && signalStrength < 55000) {
    if (distance < range_stop) {
      leftOutput = min(leftOutput, 0);
      rightOutput = min(rightOutput, 0);
    } else if (distance <= range_close) {
      if (leftOutput > 0) leftOutput /= 2;
      if (rightOutput > 0) rightOutput /= 2;
    }
  }
  // Preserve the opposing motor-controller orientations and neutral at 90.
  leftPWM.write(90 + leftOutput * 85L / 1000);
  rightPWM.write(90 - rightOutput * 85L / 1000);
  dumpPWM.write(90 + dumpCommand * 75L / 1000);
  // Low-rate telemetry: only enqueue a complete frame when UART space is free.
  // Age fields saturate at 65535 ms; the packet fits the AVR's 63 usable TX bytes.
  unsigned long now = millis();
  if (now - lastTelemetryMs >= 100) {
    lastTelemetryMs = now;
    unsigned int sensorAge = sensorSeen ? (unsigned int)min(now - lastSensorMs, 65535UL) : 65535;
    unsigned int commandAge = (unsigned int)min(now - lastCommandMs, 65535UL);
    char telemetry[64];
    int length;
    if (sonarTelemetryNext) {
      unsigned int leftAge = sonarSampled[0] ? (unsigned int)min(now - sonarSampleMs[0], 65535UL) : 65535;
      unsigned int rightAge = sonarSampled[1] ? (unsigned int)min(now - sonarSampleMs[1], 65535UL) : 65535;
      length = snprintf(telemetry, sizeof(telemetry), "S%u,%u,%u,%u\n",
                        sonarCm[0], sonarCm[1], leftAge, rightAge);
    } else {
      length = snprintf(telemetry, sizeof(telemetry), "T%u,%u,%u,%u,%u,%d,%d,%d,%lu\n",
                        distance, signalStrength, sensorAge, commandAge,
                        (unsigned int)watchdogStopped, leftOutput, rightOutput, dumpCommand, now);
    }
    sonarTelemetryNext = !sonarTelemetryNext;
    if (length > 0 && length < (int)sizeof(telemetry) && Serial.availableForWrite() >= length) {
      Serial.write((const uint8_t *)telemetry, length);
    }
  }
  //lights
  if ((distance<=range_stop)&&(signalStrength>150)&&(signalStrength<55000)){ //Too Close - Stop
    pixels.setPixelColor(2, pixels.Color(0, 200, 0));  //green, red, blue
  }
  else if ((distance<=range_stop)&&((signalStrength<150)||(signalStrength>55000))){ //Too Close - Stop
    pixels.setPixelColor(2, pixels.Color(150, 50, 50));  //green, red, blue
  }
  else if (distance<=range_close){ //Caution slow down
    pixels.setPixelColor(2, pixels.Color(150, 150, 0));  //green, red, blue
  }
  else if (distance > range_close){ //Safe Range
    pixels.setPixelColor(2, pixels.Color(200, 0, 0));  //green, red, blue
  }
  else{ //No distance set to on/ready
    pixels.setPixelColor(2, pixels.Color(100, 100, 100));  //green, red, blue
  }

  if (alivecount > 100){ //After a while no input reset to white signal
      pixels.setPixelColor(0, pixels.Color(50, 50, 50)); //GRB using White to illuminate while indicating on/ready 
      pixels.setPixelColor(1, pixels.Color(50, 50, 50)); //GRB using White to illuminate while indicating on/ready  
  }
  if (counter > 5){ //counter used to implement recommended delay for sending light updates 
    pixels.show();   // Send the updated pixel colors to the hardware.
    counter=0;
  }    
  counter++;
  alivecount++;
}
