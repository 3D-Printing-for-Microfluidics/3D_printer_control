// These four pins should be connected to ALM+, ENA+, DIR+, PUL+ 
// on the Leadshine stepper motor. 
#define STEPPER_ALM 0x4
#define STEPPER_ENA 0x5
#define STEPPER_DIR 0x6
#define STEPPER_PUL 0x7

// The S1-S4 switches on Leadshine stepper motor is off, off, on, on. 
// It means 3200 steps per revolution. 
// The thread pitch of lead screw is 0.5 mm. 
const unsigned int stepPerRev = 3200;
const float stepsPerMicron = 500 / stepPerRev;

const uint8_t serStrLen = 60;    // max length of serial input string
char serInStr[ serStrLen ];  // array that will hold the serial input string

/////////////////////////////////////////////////////////////////
////////////////// setup & loop Functions ///////////////////////
/////////////////////////////////////////////////////////////////

void setup()
{
  pinMode(STEPPER_ALM, INPUT);
  pinMode(STEPPER_ENA, OUTPUT);
  pinMode(STEPPER_DIR, OUTPUT);
  pinMode(STEPPER_PUL, OUTPUT);
  digitalWrite(STEPPER_ENA, LOW);
  delay(60); // Must wait 60 ms for `Enable` to work
  digitalWrite(STEPPER_DIR, LOW);
  delay(1);
  digitalWrite(STEPPER_PUL, LOW);
  
  Serial.begin(9600);
  delay(2000); //To allow time for serial port to begin
}

void loop()
{
  GetSerialInput();
}

void GetSerialInput() {
  if( readSerialString() ) {
    if (serInStr[0] == 'Z') { // Z1000 300: move up
      int distanceMicrons = atoi(strtok(&serInStr[1], " "));
      unsigned int speedMillimetersPerMin = atoi(strtok (nullptr, " "));
      if (distanceMicrons >= 0) {
        moveUp(distanceMicrons, speedMillimetersPerMin);
      } else {
        moveDown(-distanceMicrons, speedMillimetersPerMin);
      }
    }
  }
} //GetSerialInput

uint8_t readSerialString() { //From http://www.inventige.com/arduino-reading-serial-input-with-commands-and-numbers/
  if(!Serial.available()) {
    return 0;
  }
  delay(2);  // wait a little for serial data
  memset( serInStr, 0, sizeof(serInStr) ); // set it all to zero (look up Arduino memset function)
  uint8_t i = 0;
  while(Serial.available() && i<serStrLen ) {
    serInStr[i] = Serial.read();   // FIXME: doesn't check buffer overrun
    i++;
  }
  return i;  // return number of chars read
} //readSerialString

void moveSteps(unsigned int steps, unsigned int microsecondsPerStep)
{
  // The specs sheet states pulse high should be >2.5 us, and that pulse low 
  // should be > 1 us. Here, we set the lowest pulse time is 10 us.
  microsecondsPerStep = microsecondsPerStep < 10 ? 10 : microsecondsPerStep;
  
  float halfStepMicroseconds = microsecondsPerStep / 2.;
  unsigned int microsecondsHigh = halfStepMicroseconds + 0.5;
  unsigned int microsecondsLow = halfStepMicroseconds;
  for(unsigned int i=0; i<steps; i++) {
    digitalWrite(STEPPER_PUL, HIGH);
    delayMicroseconds(microsecondsHigh);
    digitalWrite(STEPPER_PUL, LOW);
    delayMicroseconds(microsecondsLow);
  }
}

void moveMicrons(unsigned int distanceMicrons, unsigned int speedMillimetersPerMin)
{
  float steps = distanceMicrons * stepsPerMicron;
  float stepsPerSecond = speedMillimetersPerMin * 1000 * stepsPerMicron / 60;
  float microsecondsPerStep = 1000000 / stepsPerSecond;
  float decimalPoint = microsecondsPerStep - (unsigned int)microsecondsPerStep;
  moveSteps(decimalPoint*steps, microsecondsPerStep+1);
  moveSteps((1-decimalPoint)*steps, microsecondsPerStep);
}

void moveUp(unsigned int distanceMicrons, unsigned int speedMillimetersPerMin)
{
  // direction = 1, move up; direction = 0, move down
  digitalWrite(STEPPER_DIR, HIGH);
  delay(1);
  moveMicrons(distanceMicrons, speedMillimetersPerMin);
}

void moveDown(unsigned int distanceMicrons, unsigned int speedMillimetersPerMin)
{
  // direction = 1, move up; direction = 0, move down
  digitalWrite(STEPPER_DIR, LOW);
  delay(1);
  moveMicrons(LOW, distanceMicrons, speedMillimetersPerMin);
}

