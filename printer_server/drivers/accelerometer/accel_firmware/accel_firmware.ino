/*
 * Commands:
 *  - P X : Sets sample period to X in microseconds
 *  - B   : Begins sampling
 *  - P   : Pause sampling
 *  - E   : Ends sampling
 */

#include "Arduino.h"
#include "SparkFunLSM6DSO.h"
#include "Wire.h"

LSM6DSO myIMU;

// DEFINES AND ENUMS
#define DEFAULT_PERIOD 5000 // set default sampling period to 5 millisecond

// variables
char opcode;
String data = "";
double period = DEFAULT_PERIOD;
volatile uint32_t samples_counter = 0; // current number of samples counter
volatile uint32_t start_millis = 0;    // sampling starting time
uint32_t ellapsed_millis = 0;          // sampling ellapsed time counter
volatile bool timer_running = false;
volatile bool is_paused = false;

float x_offset = 0.0;
float y_offset = 0.0;
float z_offset = 0.0;

// #include <Wire.h> // library for I2C communication on Arduino platform
#include <Time.h>

// objects
IntervalTimer timer0; // timer
bool in_isr = false;

// declare helpers
void translate();

void setup()
{
    Serial.begin(115200);
    delay(500);

    Wire.begin();
    delay(10);
    myIMU.begin();
    myIMU.initialize(BASIC_SETTINGS);

    myIMU.setAccelRange(2);
    myIMU.setGyroRange(125);

    delay(1000);
    for (int i = 0; i < 10; i++)
    {
        x_offset += myIMU.readFloatAccelX();
        y_offset += myIMU.readFloatAccelY();
        z_offset += myIMU.readFloatAccelZ();
        delay(100);
    }
    x_offset = x_offset / 10;
    y_offset = y_offset / 10;
    z_offset = z_offset / 10;
}

void loop()
{
    // if Serial is available
    if (Serial.available() > 0)
    {
        // get the opcode
        opcode = Serial.read();
        data = "";

        bool endOfLine = false;
        // get remaining data
        while (!endOfLine)
        {
            int inChar = Serial.read();

            if (!(inChar == '\n' || inChar == '\r'))
            {
                data += (char)inChar;
            }
            // when new line hit, process command
            else
            {
                endOfLine = true;
                translate();
            }
        }
    }
}

void translate()
{
    // set sample period
    if (opcode == 'T' || opcode == 't')
    {
        if (data.toInt() == 0)
        {
            Serial.println("Error: Invalid input. Value must be a integer.");
            Serial.println("Done");
            return;
        }
        period = data.toInt();
        Serial.print("Info: Sample Period set to ");
        Serial.print(period);
        Serial.println(" us");
    }
    // begins sampling
    else if (opcode == 'B' || opcode == 'b')
    {
        setStartTime();
        Serial.print("Info: Starting Sampling at '");
        Serial.print(start_millis);
        Serial.println("' ms");
        // start sampling
        timerStart();
    }
    // ends sampling
    else if (opcode == 'P' || opcode == 'p')
    {
        timerPause();
        Serial.println("Info: Pausing Sampling");
    }
    // ends sampling
    else if (opcode == 'E' || opcode == 'e')
    {
        timerStop();
        Serial.println("Info: Stopped Sampling");
    }
    else
    {
        Serial.println("Error: Invalid opcode.");
        Serial.println("Done");
        return;
    }
    Serial.println("Done");
}

void setStartTime()
{
    if (!is_paused)
    { // is first
        start_millis = millis();
    }
}

void timerStart()
{
    if (!is_paused)
    {
        samples_counter = 0;
    }
    timer_running = true;
    is_paused = false;

    timer0.begin(samplingISR, period);
}

void timerPause()
{
    if (timer_running)
    {
        timer0.end();
        while (in_isr)
        {
            delay(10);
        }
        timer_running = false;
        is_paused = true;
    }
}

void timerStop()
{
    if (timer_running)
    {
        timer0.end();
        while (in_isr)
        {
            delay(10);
        }
        timer_running = false;
        is_paused = false;
    }
}

void samplingISR()
{
    in_isr = true;
    float x = myIMU.readFloatAccelX() - x_offset;
    float y = myIMU.readFloatAccelY() - y_offset;
    float z = myIMU.readFloatAccelZ() - z_offset;

    float accel = sqrt(sq(x) + sq(y) + sq(z));
    int scale = 16384;
    accel = accel * scale;

    uint32_t current_time = millis();

    byte buf1[4];
    // buf1[0] = samples_counter & 255;
    // buf1[1] = (samples_counter >> 8) & 255;
    // buf1[2] = (samples_counter >> 16) & 255;
    // buf1[3] = (samples_counter >> 24) & 255;
    // Serial.write(buf1, sizeof(buf1));

    Serial.print("AA");

    buf1[0] = current_time & 255;
    buf1[1] = (current_time >> 8) & 255;
    buf1[2] = (current_time >> 16) & 255;
    buf1[3] = (current_time >> 24) & 255;
    Serial.write(buf1, sizeof(buf1));

    byte buf2[2];
    buf2[0] = (uint16_t)accel & 255;
    buf2[1] = ((uint16_t)accel >> 8) & 255;
    Serial.write(buf2, sizeof(buf2));

    Serial.print("\r\n");

    // increment samples counter
    samples_counter++;
    in_isr = false;
}