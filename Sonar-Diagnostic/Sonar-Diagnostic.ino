/* Standalone HC-SR04 test. Stop robot.service before upload/Serial Monitor.
   This temporarily replaces the robot firmware. Restore Arduino-Nano.ino after.
   Motors are held at their existing neutral setting; no drive commands accepted.
   Front left: TRIG D9, ECHO D8. Front right: TRIG D12, ECHO D11.
*/
#include <Servo.h>

const byte triggerPins[2] = {9, 12};
const byte echoPins[2] = {8, 11};
Servo leftMotor, rightMotor, dumpMotor;

void setup() {
  leftMotor.write(90);
  rightMotor.write(90);
  dumpMotor.write(90);
  leftMotor.attach(14);
  rightMotor.attach(15);
  dumpMotor.attach(16);
  for (byte index = 0; index < 2; index++) {
    pinMode(triggerPins[index], OUTPUT);
    digitalWrite(triggerPins[index], LOW);
    pinMode(echoPins[index], INPUT);
  }
  Serial.begin(115200);
  delay(1000);
  Serial.println("HC-SR04 diagnostic: FL trig=9 echo=8; FR trig=12 echo=11");
}

void loop() {
  for (byte index = 0; index < 2; index++) {
    int idleLevel = digitalRead(echoPins[index]);
    digitalWrite(triggerPins[index], LOW);
    delayMicroseconds(5);
    digitalWrite(triggerPins[index], HIGH);
    delayMicroseconds(15);
    digitalWrite(triggerPins[index], LOW);
    unsigned long echoUs = pulseIn(echoPins[index], HIGH, 30000UL);
    Serial.print(index == 0 ? "FL" : "FR");
    Serial.print(" echo_idle="); Serial.print(idleLevel);
    Serial.print(" pulse_us="); Serial.print(echoUs);
    if (echoUs) {
      Serial.print(" distance_cm="); Serial.print(echoUs / 58.0, 1);
    } else {
      Serial.print(" NO_COMPLETE_ECHO");
    }
    Serial.print(" echo_after="); Serial.println(digitalRead(echoPins[index]));
    delay(500);  // Deliberately slow, separated pings; no NeoPixels or I2C.
  }
}
