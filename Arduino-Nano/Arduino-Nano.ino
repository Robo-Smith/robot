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
int oldl=127;
int filtl=127;
int oldr=127;
int filtr=127;
int leftY=127;
int rightY=127;

const int leftPwmPin = 14;  // PWM output for left joystick is 14 on yardbot - test board is 6
const int rightPwmPin = 15; // PWM output for right joystick is 15 on yardbot - test board is 6
const int dumpPwmPin = 16;  // PWM output for dumping is 16 on yardbot - test board is 6
const int LR = 17; 

Servo leftPWM;   // create servo object to control a servo
Servo rightPWM;  // create servo object to control a servo
Servo dumpPWM;   // create servo object to control a servo
Servo LR;   // create servo object to control a servo


void setup() {
  pixels.begin();               //INITIALIZE NeoPixel strip object (REQUIRED)
  Wire.begin();                 //The I2C bus communication starts for ToF sensor
  Serial.begin(115200);         //Start serial communication with Pi
  leftPWM.attach(leftPwmPin);   //Attaches the servo on pin to the servo object
  rightPWM.attach(rightPwmPin); //Attaches the servo on pin to the servo object
  dumpPWM.attach(dumpPwmPin);   //Attaches the servo on pin to the servo object
  pixels.setPixelColor(0, pixels.Color(0, 50, 0)); //GRB
  pixels.setPixelColor(1, pixels.Color(0, 50, 0)); //GRB
  pixels.setPixelColor(2, pixels.Color(0, 50, 0)); //GRB
  pixels.setPixelColor(3, pixels.Color(50, 0, 0)); //GRB
  }

void loop() {
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
    distance = (data[1] << 8) | data[0]; //Distance Value
    signalStrength = (data[3] << 8) | data[2]; //Signal Strength Signal Dist value is unreliable when Amp < 100 or Amp = 65535 (Overexposure) 
  }
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    if (input.startsWith("L")) { //Left Joystick Input
      leftY = input.substring(1).toInt();
      pixels.setPixelColor(1, pixels.Color(0, 0, 100)); //GRB
      alivecount=0;
    } 
    else if (input.startsWith("R")) { //Right Joystick Input
      rightY = input.substring(1).toInt();
      pixels.setPixelColor(0, pixels.Color(0, 0, 100)); //GRB using Blue to indicate controller input
      alivecount=0;
    }
    else if (input.startsWith("D")) { //Right Trigger Input
      int lower_dump = input.substring(1).toInt();
      int DumpPwmValue = map(lower_dump, 0, 255, 90, 15); // Map joystick value to PWM range 90-0 full range
      dumpPWM.write(DumpPwmValue);
      pixels.setPixelColor(2, pixels.Color(0, 0, 100)); //GRB using Blue to indicate controller input
      alivecount=0;
    }
    else if (input.startsWith("U")) { //Left Trigger Input
      int raise_dump = input.substring(1).toInt();
      int RaisePwmValue = map(raise_dump, 0, 255, 90, 165); // Map joystick value to PWM range 90-180 full range
      dumpPWM.write(RaisePwmValue);
      pixels.setPixelColor(2, pixels.Color(0, 0, 100)); //GRB using Blue to indicate controller input
      alivecount=0;
    }
  }
 //Drive_Out-----------------------------------------------------------------------
  //Stop
  if ((distance<range_stop)&&(signalStrength>150)&&(signalStrength<55000)){
    if (leftY<127){
      filtl = 127;
    }
    if (rightY<127){
      filtr = 127;
    }
  }
  //Slow
  else if ((distance<=range_close)&&(signalStrength>150)&&(signalStrength<55000)){
    if (leftY<127){
      filtl = 127-((127-leftY)*.5);
    }
    if (rightY<127){
      filtr = 127-((127-rightY)*.5);
    }
  }
  //Go filtered
  else {
    if ((leftY<127)&&(oldl<leftY)){
      filtl = 127-((127-leftY)*((127-leftY)/(127-oldl)));
      oldl=leftY;
    }
    if ((rightY<127)&&(oldr<rightY)){
      filtr = 127-((127-rightY)*((127-rightY)/(127-oldr)));
      oldr=rightY;
    }
  }
  //Write drive out
    int leftPwmValue = map(filtl, 0, 255, 175, 5); // Map joystick value to PWM range 180-0 full range
    leftPWM.write(leftPwmValue);
    int rightPwmValue = map(filtl, 0, 255, 5, 175); // Map joystick value to PWM range 180-0 full range
    rightPWM.write(rightPwmValue);
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
