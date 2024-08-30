#include "TeensyStep.h"
#include <Encoder.h>
#define ENCODER_OPTIMIZE_INTERRUPTS

#include "Tip_Tilt.h"
using namespace std;

//physical pins
const int TIP_DIR_PIN = 4;
const int TIP_STEP_PIN = 3;
const int TIP_EN = 2;

const int TILT_DIR_PIN = 5;
const int TILT_STEP_PIN = 6;
const int TILT_EN = 7;

const int TILT_ENCODER_I_PIN = 14;
const int TILT_ENCODER_A_PIN = 15;
const int TILT_ENCODER_B_PIN = 16;
const int TIP_ENCODER_I_PIN = 17;
const int TIP_ENCODER_A_PIN = 18;
const int TIP_ENCODER_B_PIN = 19;
const int TILT_LIMIT = 20;
const int TIP_LIMIT = 21;

//use to correct physical accuracy of axis
const float TIP_CORRECTION_FACTOR = 1.0; //tip was only moving 70% of distance
const float TILT_CORRECTION_FACTOR = 1.0;
//HR3.3_1
//const float TIP_HOMING_OFFSET = 0.0;
//const float TILT_HOMING_OFFSET = 0.5;
//HR3.3_2
const float TIP_HOMING_OFFSET = 0.0;
const float TILT_HOMING_OFFSET = 0.0;

//homing speed settings
const int FAST_SPEED = 6000; //fast homing speed
const int MEDIUM_SPEED = 4000; //medium homing speed
const int SLOW_SPEED = 1000; //slow homing speed

//default settings
const int DEFAULT_SPEED = 4000; //default speed
const int DEFAULT_ACCELERATION = 100000;

const int TIP_BASE = 292100; //11.5
const int TILT_BASE = 165100; //6.5

float um_to_rad(float o, float a){
    return atan(o/a);
}

float rad_to_um(float rad, float a){
    return tan(rad)*a;
}

//set up device on power up
Tip_Tilt::Tip_Tilt(){

    //create axis
    tipAxis = new Axis("Tip", false, TIP_DIR_PIN, TIP_STEP_PIN, TIP_EN, TIP_ENCODER_I_PIN, 
                  TIP_ENCODER_A_PIN, TIP_ENCODER_B_PIN, TIP_LIMIT, TIP_CORRECTION_FACTOR);
    tiltAxis = new Axis("Tilt", false, TILT_DIR_PIN, TILT_STEP_PIN, TILT_EN, TILT_ENCODER_I_PIN, 
                  TILT_ENCODER_A_PIN, TILT_ENCODER_B_PIN, TILT_LIMIT, TILT_CORRECTION_FACTOR);

    //set default speed/acceleration
    default_speed = DEFAULT_SPEED;
    default_acceleration = DEFAULT_ACCELERATION;

    setStepperSpeed(default_speed);
    setStepperAcceleration(default_acceleration);
}

Tip_Tilt::~Tip_Tilt(){
    delete tipAxis;
    delete tiltAxis;
}

//homing
bool Tip_Tilt::homeAxis(){
//inital homing on fast speed
    tipAxis->setSpeed(FAST_SPEED);
    tiltAxis->setSpeed(FAST_SPEED);

    Serial.println("Info: Homing-Tip Inital positioning");
    
    //home tip - inital
    if(!tipAxis->homeAxis(TIP_HOMING_OFFSET)){
        //if homing failed power down and return false
        return false;
    }
    
    //move tip to somewhat arbitrary position (should be fairly repeatable)
    //not entirely sure if this is nessicary, but it seemed to help
    if(!tipAxis->moveAxis(500, true)){
        //if homing failed power down and return false
        return false;
    }
    
    Serial.println("Info: Homing-Tilt Inital positioning");
    if(!tiltAxis->homeAxis(TILT_HOMING_OFFSET)){
        //if homing failed power down and return false
        return false;
    }
    
    //move tilt to somewhat arbitrary position (should be fairly repeatable)
    //not entirely sure if this is nessicary, but it seemed to help
    if(!tiltAxis->moveAxis(500, true)){
        //if homing failed power down and return false
        return false;
    }

//second homing on medium speed
    tipAxis->setSpeed(MEDIUM_SPEED);
    tiltAxis->setSpeed(MEDIUM_SPEED);
    
    //home axis
    Serial.println("Info: Homing-1st Homing");
    if(!tipAxis->homeAxis(TIP_HOMING_OFFSET)){
        //if homing failed power down and return false
        return false;
    }
    if(!tiltAxis->homeAxis(TILT_HOMING_OFFSET)){
        //if homing failed power down and return false
        return false;
    }
    

////last homing on slow speed
//    tipAxis->setSpeed(SLOW_SPEED);
//    tiltAxis->setSpeed(SLOW_SPEED);
//
//    //home axis
//    Serial.println("Info: Homing-2nd Homing");
//    
//    if(!tipAxis->homeAxis(TIP_HOMING_OFFSET)){
//        //if homing failed power down and return false
//        return false;
//    }
//    if(!tiltAxis->homeAxis(TILT_HOMING_OFFSET)){
//        //if homing failed power down and return false
//        return false;
//    }
//
    //restore to default speed
    tipAxis->setSpeed(default_speed);
    tiltAxis->setSpeed(default_speed);

    Serial.println("Info: Homing-Finished");
    return true;
}

//this function is called on serial connection
void Tip_Tilt::connectAxis(){
    //reset to defaults?
    return true;
}

//query location for tip using encoder location (converted to rad)
float Tip_Tilt::tipLocation(){
    return um_to_rad(tipAxis->getLocation(), TIP_BASE);
}

//query location for tilt using encoder location (converted to rad)
float Tip_Tilt::tiltLocation(){
    return um_to_rad(tiltAxis->getLocation(), TILT_BASE);
}

//move tip axis to location in rad (absolute positioning)
bool Tip_Tilt::moveTipAxisToLocation(float location, bool coarseMove){
    return tipAxis->moveAxis(rad_to_um(location, TIP_BASE), coarseMove);
}

//move tilt axis to location in rad (absolute positioning)
bool Tip_Tilt::moveTiltAxisToLocation(float location, bool coarseMove){
    return tiltAxis->moveAxis(rad_to_um(location, TILT_BASE), coarseMove);
}

//move tip axis by number of rad (relative positioning (uses absolute internally))
bool Tip_Tilt::moveTipAxisByDistance(float distance, bool coarseMove){
    return tipAxis->moveAxis(rad_to_um(this->tipLocation() + distance, TIP_BASE), coarseMove);
}

//move tilt axis by number of rad (relative positioning (uses absolute internally))
bool Tip_Tilt::moveTiltAxisByDistance(float distance, bool coarseMove){
    return tiltAxis->moveAxis(rad_to_um(this->tiltLocation() + distance, TILT_BASE), coarseMove);
}

//returns the minimum tip (set distance from machine 0)
float Tip_Tilt::getMinTip(){
    return um_to_rad(0, TIP_BASE);
}

//returns the minimum tilt in rad (set distance from machine 0)
float Tip_Tilt::getMaxTip(){
    return um_to_rad(tipAxis->getMaxPos(), TIP_BASE);
}

//returns the minimum tip (defined 0 by hardware)
float Tip_Tilt::getMinTilt(){
    return um_to_rad(0, TILT_BASE);
}

//returns the minimum tilt in rad (defined 0 by hardware)
float Tip_Tilt::getMaxTilt(){
    return um_to_rad(tiltAxis->getMaxPos(), TILT_BASE);
}

//gets global acceleration
long Tip_Tilt::getStepperAcceleration(){
    return default_acceleration;
}

//sets global acceleration
void Tip_Tilt::setStepperAcceleration(long a){
    default_acceleration = a;
    tipAxis->setAcceleration(a);
    tiltAxis->setAcceleration(a);
}

//gets movement velocity
long Tip_Tilt::getStepperSpeed(){
    return default_speed;
}

//sets movement velocity
void Tip_Tilt::setStepperSpeed(long s){
    default_speed = s;
    tipAxis->setSpeed(s);
    tiltAxis->setSpeed(s);
}

//this is called when serial is closed
void Tip_Tilt::disconnectAxis(){
    return true;
}
