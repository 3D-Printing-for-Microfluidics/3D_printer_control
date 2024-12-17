/*
 * Commands:
 *  - P X : Sets sample period to X in microseconds
 *  - B   : Begins sampling
 *  - P   : Pause sampling
 *  - E   : Ends sampling
 */

#include "Arduino.h"

// DEFINES AND ENUMS
#define ADC_WORD_WIDTH 16   // constant used for ADC configuration
#define ADC_NUM_AVGS 32     // constnat used for ADC configuration
#define DEFAULT_PERIOD 1000 // set default sampling period to 1 millisecond
#define CHANNEL0 A0         // channel 0 adc pin

// variables
char opcode;
String data = "";
double period = DEFAULT_PERIOD;
volatile uint32_t samples_counter = 0; // current number of samples counter
volatile uint32_t start_millis = 0;    // sampling starting time
uint32_t ellapsed_millis = 0;          // sampling ellapsed time counter
volatile bool timer_running = false;
volatile bool is_paused = false;

// #include <Wire.h> // library for I2C communication on Arduino platform
#include <ADC.h>
#include <ADC_util.h>
#include <Time.h>
ADC *adc = new ADC(); // adc object;

// objects
IntervalTimer timer0; // timer
bool in_isr = false;

// declare helpers
void translate();

void setup()
{
    Serial.begin(115200);
    while (!Serial)
        ;

    adc->adc0->setReference(ADC_REFERENCE::REF_3V3);
    adc->adc0->setAveraging(ADC_NUM_AVGS);    // set number of averages
    adc->adc0->setResolution(ADC_WORD_WIDTH); // set bits of resolution

    adc->adc0->setConversionSpeed(ADC_CONVERSION_SPEED::MED_SPEED); // change the conversion speed
    adc->adc0->setSamplingSpeed(ADC_SAMPLING_SPEED::MED_SPEED);     // change the sampling speed
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
        Serial.println("Info: Paused Sampling");
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
    // check if it's first time sampling for sampling set
    //    if(samples_counter == 0) { // is first
    //        start_millis = millis();
    //    }
    // calculate and save current time differentally to initial time
    //    ellapsed_millis = millis() - start_millis;

    uint16_t adc_value = adc->adc0->analogRead(CHANNEL0);
    //    uint16_t adc_value = analogRead(A0) >> 6;

    // relay sample data and time through Serial port
    //    Serial.printf("%d,%d,%d\r\n", samples_counter, ellapsed_millis, adc_value);

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
    buf2[0] = adc_value & 255;
    buf2[1] = (adc_value >> 8) & 255;
    Serial.write(buf2, sizeof(buf2));
    Serial.print("\r\n");

    //    Serial.printf("%d,%d,%d\r\n", (uint32_t) samples_counter, (uint32_t) millis(), (uint16_t) adc_value);

    // increment samples counter
    samples_counter++;
    in_isr = false;
}

///*
// * Commands:
// *  - P X : Sets sample period to X in microseconds
// *  - B   : Begins sampling
// *  - P   : Pause sampling
// *  - E   : Ends sampling
// */
//
// #include "Arduino.h"
//
//// DEFINES AND ENUMS
// #define ADC_WORD_WIDTH 16               // constant used for ADC configuration
// #define ADC_NUM_AVGS 32                 // constnat used for ADC configuration
// #define DEFAULT_PERIOD 1000             // set default sampling period to 1 millisecond
// #define CHANNEL0 A0                    // channel 0 adc pin
// #define USE_ADC_0
//
////variables
// char opcode;
// String data = "";
// double period = DEFAULT_PERIOD;
// volatile uint32_t samples_counter = 0;             // current number of samples counter
// volatile uint32_t start_millis = 0;                // sampling starting time
// uint32_t ellapsed_millis = 0;             // sampling ellapsed time counter
// volatile bool timer_running = false;
// volatile bool is_paused = false;
//
////#include <Wire.h> // library for I2C communication on Arduino platform
// #include <ADC.h>
// #include <ADC_util.h>
// #include <Time.h>
// ADC *adc = new ADC();       // adc object;
//
////objects
////IntervalTimer timer0;                     // timer
//
////declare helpers
// void translate();
//
// void setup() {
//   Serial.begin(115200);
//   while(!Serial);
//
//   adc->adc0->setReference(ADC_REFERENCE::REF_3V3);
//   adc->adc0->setAveraging(ADC_NUM_AVGS); // set number of averages
//   adc->adc0->setResolution(ADC_WORD_WIDTH); // set bits of resolution
//
//   adc->adc0->setConversionSpeed(ADC_CONVERSION_SPEED::HIGH_SPEED_16BITS); // change the conversion speed
//   adc->adc0->setSamplingSpeed(ADC_SAMPLING_SPEED::VERY_HIGH_SPEED); // change the sampling speed
// }
//
// void loop() {
//     //if Serial is available
//     if (Serial.available() > 0) {
//         //get the opcode
//         opcode = Serial.read();
//         data = "";
//
//         bool endOfLine = false;
//         //get remaining data
//         while (!endOfLine) {
//             int inChar = Serial.read();
//
//             if (!(inChar == '\n' || inChar == '\r')) {
//                 data += (char)inChar;
//             }
//             //when new line hit, process command
//             else {
//                 endOfLine = true;
//                 translate();
//             }
//         }
//     }
//     // Print errors, if any.
////    if (adc->adc0->fail_flag != ADC_ERROR::CLEAR) {
//////        Serial.print("ADC0: "); Serial.println(getStringADCError(adc->adc0->adc0->fail_flag));
////    }
////    adc->adc0->resetError();
//}
//
// void translate(){
//    //set sample period
//    if(opcode == 'F' || opcode == 'f'){
//        if(data.toInt() == 0){
//            Serial.print("Error: Invalid input. Value must be a integer.");
//            return;
//        }
//        period = data.toInt();
//        Serial.print("Info: Sample Period set to ");
//        Serial.println(period);
//    }
//    //begins sampling
//    else if(opcode == 'B' || opcode == 'b'){
//        setStartTime();
//        Serial.print("Info: Starting Sampling at '");
//        Serial.print(start_millis);
//        Serial.println("' ms");
//        //start sampling
//        timerStart();
//    }
//    //ends sampling
//    else if(opcode == 'P' || opcode == 'p'){
//        Serial.println("Info: Pausing Sampling");
//        //start sampling
//        timerPause();
//    }
//    //ends sampling
//    else if(opcode == 'E' || opcode == 'e'){
//        Serial.println("Info: Stopping Sampling");
//        //start sampling
//        timerStop();
//    }
//    else{
//        Serial.print("Error: Invalid opcode.");
//        return;
//    }
//}
//
// void setStartTime(){
//    if(!is_paused) { // is first
//        start_millis = millis();
//    }
//}
//
// void timerStart() {
//    if(!is_paused){
//        samples_counter = 0;
//    }
//    timer_running = true;
//    is_paused = false;
//
//    adc->adc0->stopTimer();
//    adc->adc0->startSingleRead(CHANNEL0); // call this to setup everything before the Timer starts, differential is also possible
//    adc->adc0->enableInterrupts(adc0_isr);
//    adc->adc0->startTimer(period); //frequency in Hz
//}
//
// void timerPause() {
//    if(timer_running){
//        adc->adc0->stopTimer();
//        timer_running = false;
//        is_paused = true;
//    }
//}
//
// void timerStop() {
//    if(timer_running){
//        adc->adc0->stopTimer();
//        timer_running = false;
//        is_paused = false;
//    }
//}
//
//// Make sure to call readSingle() to clear the interrupt.
// void adc0_isr() {
//     // check if it's first time sampling for sampling set
//     // calculate and save current time differentally to initial time
////    ellapsed_millis = millis() - start_millis;
//
//    uint16_t adc_value = adc->adc0->readSingle();
//
//    // relay sample data and time through Serial port
////    Serial.printf("%d,%d,%d\r\n", samples_counter, ellapsed_millis, adc_value);
//    Serial.printf("%d,%d,%d\r\n", samples_counter, millis(), adc_value);
//
//    // increment samples counter
//    samples_counter++;
//
// #if defined(__IMXRT1062__)  // Teensy 4.0
//    asm("DSB");
// #endif
//}
