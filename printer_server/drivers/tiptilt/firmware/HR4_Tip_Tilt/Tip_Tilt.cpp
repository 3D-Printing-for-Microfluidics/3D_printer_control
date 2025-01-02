#include "TeensyStep.h"
#include <Encoder.h>

#define ENCODER_OPTIMIZE_INTERRUPTS

#include "Tip_Tilt.h"
using namespace std;

// physical pins
const int TILT_DIR_PIN = 4;
const int TILT_STEP_PIN = 3;
const int TILT_EN = 2;

const int TIP_DIR_PIN = 5;
const int TIP_STEP_PIN = 6;
const int TIP_EN = 7;

const int TIP_ENCODER_I_PIN = 14;
const int TIP_ENCODER_A_PIN = 15;
const int TIP_ENCODER_B_PIN = 16;
const int TILT_ENCODER_I_PIN = 17;
const int TILT_ENCODER_A_PIN = 18;
const int TILT_ENCODER_B_PIN = 19;
const int TIP_LIMIT = 20;
const int TILT_LIMIT = 21;

// use to correct physical accuracy of axis
const float TILT_CORRECTION_FACTOR = 1.0;
const float TIP_CORRECTION_FACTOR = 1.0;

// homing speed settings
const int FAST_SPEED = 10000;  // fast homing speed
const int MEDIUM_SPEED = 5000; // medium homing speed
const int SLOW_SPEED = 1000;   // slow homing speed

// default settings
const int DEFAULT_SPEED = 10000; // default speed
const int DEFAULT_ACCELERATION = 100000;

// set up device on power up
Tip_Tilt::Tip_Tilt() {

    // create axis
    tiltAxis =
        new Axis("Tilt", false, TILT_DIR_PIN, TILT_STEP_PIN, TILT_EN, TILT_ENCODER_I_PIN,
                 TILT_ENCODER_A_PIN, TILT_ENCODER_B_PIN, TILT_LIMIT, TILT_CORRECTION_FACTOR, 6000);
    tipAxis =
        new Axis("Tip", false, TIP_DIR_PIN, TIP_STEP_PIN, TIP_EN, TIP_ENCODER_I_PIN,
                 TIP_ENCODER_A_PIN, TIP_ENCODER_B_PIN, TIP_LIMIT, TIP_CORRECTION_FACTOR, 5000);

    // set default speed/acceleration
    default_speed = DEFAULT_SPEED;
    default_acceleration = DEFAULT_ACCELERATION;

    tiltAxis->setSpeed(default_speed);
    tipAxis->setSpeed(default_speed);
    tiltAxis->setAcceleration(default_acceleration);
    tipAxis->setAcceleration(default_acceleration);
}

Tip_Tilt::~Tip_Tilt() {
    delete tiltAxis;
    delete tipAxis;
}

// homing
bool Tip_Tilt::homeAxis() {
    // inital homing on fast speed
    tiltAxis->setSpeed(FAST_SPEED);
    tipAxis->setSpeed(FAST_SPEED);

    Serial.println("Info: Homing-Inital positioning");
    bool is_running = true;
    bool tilt = true;
    bool tip = true;
    while (is_running) {
        if (tiltAxis->stepIntoLimitSwitch()) {
            tilt = false;
        }
        if (tipAxis->stepIntoLimitSwitch()) {
            tip = false;
        }
        if (!tilt && !tip) {
            is_running = false;
        }
//        delay(10);
    }

    Serial.println("Info: Homing-Tip Inital positioning");
    if (!tipAxis->homeAxis()) {
        // if homing failed power down and return false
        return false;
    }

    // move tip to somewhat arbitrary position (should be fairly repeatable)
    // not entirely sure if this is nessicary, but it seemed to help
    if (!tipAxis->moveAxis(500, true)) {
        // if homing failed power down and return false
        return false;
    }

    Serial.println("Info: Homing-Tilt Inital positioning");
    // home tilt - inital
    if (!tiltAxis->homeAxis()) {
        // if homing failed power down and return false
        return false;
    }

    // move tilt to somewhat arbitrary position (should be fairly repeatable)
    // not entirely sure if this is nessicary, but it seemed to help
    if (!tiltAxis->moveAxis(500, true)) {
        // if homing failed power down and return false
        return false;
    }

    // second homing on medium speed
    tiltAxis->setSpeed(MEDIUM_SPEED);
    tipAxis->setSpeed(MEDIUM_SPEED);

    // home axis
    Serial.println("Info: Homing-1st Homing");
    if (!tipAxis->homeAxis()) {
        // if homing failed power down and return false
        return false;
    }
    if (!tiltAxis->homeAxis()) {
        // if homing failed power down and return false
        return false;
    }

    // last homing on slow speed
    tiltAxis->setSpeed(SLOW_SPEED);
    tipAxis->setSpeed(SLOW_SPEED);

    // home axis
    Serial.println("Info: Homing-2nd Homing");
    if (!tipAxis->homeAxis()) {
        // if homing failed power down and return false
        return false;
    }
    if (!tiltAxis->homeAxis()) {
        // if homing failed power down and return false
        return false;
    }

    // restore to default speed
    tiltAxis->setSpeed(default_speed);
    tipAxis->setSpeed(default_speed);

    Serial.println("Info: Homing-Finished");
    return true;
}

// this function is called on serial connection
void Tip_Tilt::connectAxis() {
    // reset to defaults?
}

// query location for tilt using encoder location (converted to microns)
float Tip_Tilt::tiltLocation() {
    return tiltAxis->getLocation();
}

// query location for tip using encoder location (converted to microns)
float Tip_Tilt::tipLocation() { return tipAxis->getLocation(); }

// move tilt axis to location (absolute positioning)
bool Tip_Tilt::moveTiltAxisToLocation(float location, bool coarseMove) {
    // do location bound checks
    if (location < -1) {
        Serial.println("Error: Tilt value outside negitive bound.");
        return false;
    } else if (location > getMaxTilt()) {
        Serial.println("Error: Tilt value outside positive bound.");
        return false;
    }

    Serial.print("Info: Moving Tilt Axis to ");
    Serial.println(location,4);
    return tiltAxis->moveAxis(location, coarseMove);
}

// move tip axis to location (absolute positioning)
bool Tip_Tilt::moveTipAxisToLocation(float location, bool coarseMove) {
    // do location bound checks
    if (location < -1) {
        Serial.println("Error: Tip value outside negitive bound.");
        return false;
    } else if (location > getMaxTip()) {
        Serial.println("Error: Tip value outside positive bound.");
        return false;
    }

    Serial.print("Info: Moving Tip Axis to ");
    Serial.println(location,4);
    return tipAxis->moveAxis(location, coarseMove);
    
}

// move tilt axis by number of microns (relative positioning (uses absolute internally))
bool Tip_Tilt::moveTiltAxisByDistance(float distance, bool coarseMove) {

    Serial.print("Info: Moving Tilt Axis by ");
    Serial.println(distance,4);
    Serial.print("Info: Moving Tilt Axis to ");
    Serial.println(tiltAxis->getLocation() + distance,4);
    return moveTiltAxisToLocation(tiltAxis->getLocation() + distance, coarseMove);

}

// move tip axis by number of microns (relative positioning (uses absolute internally))
bool Tip_Tilt::moveTipAxisByDistance(float distance, bool coarseMove) {
    Serial.print("Info: Moving Tip Axis by ");
    Serial.println(distance,4);
    Serial.print("Info: Moving Tip Axis to ");
    Serial.println(tipAxis->getLocation() + distance,4);
    return moveTipAxisToLocation(tipAxis->getLocation() + distance, coarseMove);
}

// returns the minimum tilt (set distance from machine 0)
float Tip_Tilt::getMinTilt() { return 0; }

// returns the minimum tip (set distance from machine 0)
float Tip_Tilt::getMaxTilt() { return tiltAxis->getMaxPos();}

// returns the minimum tilt (defined 0 by hardware)
float Tip_Tilt::getMinTip() { return 0; }

// returns the minimum tip (defined 0 by hardware)
float Tip_Tilt::getMaxTip() { return tipAxis->getMaxPos(); }

// gets global acceleration
long Tip_Tilt::getStepperAcceleration() { return default_acceleration; }

// sets global acceleration
void Tip_Tilt::setStepperAcceleration(long a) {
    default_acceleration = a;
    tiltAxis->setAcceleration(a);
    tipAxis->setAcceleration(a);
}

// gets movement velocity
long Tip_Tilt::getStepperSpeed() { return default_speed; }

// sets movement velocity
void Tip_Tilt::setStepperSpeed(long s) {
    default_speed = s;
    tiltAxis->setSpeed(s);
    tipAxis->setSpeed(s);
}

// this is called when serial is closed
void Tip_Tilt::disconnectAxis() {}
