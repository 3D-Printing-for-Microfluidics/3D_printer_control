#include "Axis.h"
using namespace std;

//distances/mesurements
const long MAX_POS = 1750;
const int STEPS_PER_ROTATION = 3200; //microsteps
const int COUNTS_PER_ROTATION = 20000; //encoder
const float DISTANCE_PER_ROTATION = 396.875; //micron

//step counts
const long MAX_HOMING_STEPS = MAX_POS/DISTANCE_PER_ROTATION*STEPS_PER_ROTATION*2;
const long BACKLASH_OVERSHOOT_STEPS = STEPS_PER_ROTATION/8;
const long MINIMUM_NUMBER_OF_STEPS = 16;
const long INDEX_BACKUP_STEPS = STEPS_PER_ROTATION*1.1;

const int MINIMUM_STEPPER_SPEED = 100;


Axis::Axis(String name, bool inverted, int dir_pin, int step_pin, int en_pin, int encoder_i, int encoder_a, int encoder_b, int limit, float correction_factor){
  this->name = name;
  this->dir_pin = dir_pin;
  this->step_pin = step_pin;
  this->en_pin = en_pin;
  this->encoder_i = encoder_i;
  this->encoder_a = encoder_a;
  this->encoder_b = encoder_b;
  this->limit = limit;
  this->inverted = inverted;
  this->correction_factor = correction_factor;

  mirror_location = 0;
  homed = false;

  pinMode(encoder_i, INPUT);
  pinMode(limit, INPUT);
  pinMode(en_pin, OUTPUT);

  digitalWrite(en_pin, HIGH);

  stepper = new Stepper(step_pin, dir_pin);
  encoder = new Encoder(encoder_a, encoder_b);

  stepper->setInverseRotation(inverted);
}

Axis::~Axis(){
   delete stepper;
   delete encoder;
}

//actually move tipAxis by steps
/* The movement code is complicated. We have several issues that we need to address.
1) As we are using belts, there is a decent amount of backlash.
2) When the steppers are powered off, they will turn relieving tension in the belts.
3) The stepper does not always drive to the exact encoder position.
4) Occationally the stepper is unable to reach the desired position.

In order to compensate for these issues, we have implemented several fixes
1) The location can only be driven to from one direction (backlash).
2) There is a minimum movement size to account for tensioning (tensioning).
3) The mirror location must only be updated while the motors are on (tensioning).
4) To ensure precision, multiple attempts are taken to reach desired position (precision).
5) A memory element was implemented to track the error. This is used to correct the position insure it is reached (unable to reach).
6) If still unable to reach position, do a compination of increasing acceptable range and reseting memory. (unable to reach)*/
bool Axis::moveAxis(float move_location, bool coarseMove){
  
    //move_location = abs(move_location);             //desired location
    float stepper_location = calulateLocation();    //current position of the stepper
    float last_stepper_location = stepper_location; //memory variable to check if stepper actually moved
    float allowedError = 0.25;                      //position must be within +-um of this number      
    float failures[] = {0,0,0};                     //array of the last 3 errors (collected right before backlash prevention)
    int failure_index = 0;                          //index to next update in failures
    bool secondPass = false;                        //tracks if a failure reset did not work
    int attempts = 0;                               //track how many times we try. If this gets too big, we start worrying.

    if (coarseMove){
        allowedError = 2;             
    }

    //check if homed
    if(!homed){
        Serial.print("Error: Stage must be homed before motion.");
        return false;
    }
    
    //do location bound checks
    if(move_location < 0){
        Serial.print("Error: ");
        Serial.print(name);
        Serial.println(" value outside negitive bound.");
        return false;
    }
    else if(move_location > MAX_POS){
      Serial.print("Error: ");
        Serial.print(name);
        Serial.println(" value outside positive bound.");
        return false;
    }

    //turn on our motor
    digitalWrite(en_pin, LOW);
    
    //while we are ouside of our allowed error, move
    while(abs(move_location-mirror_location) > allowedError){

        //calculate offset based on failure array
        float failure_offset = 0;
        for(int i = 0; i < 3; i++){
            failure_offset += failures[i];
        }
        failure_offset = failure_offset/3;      //average error
        failure_offset = failure_offset/.125;   //convert error to steps
        failure_offset = failure_offset*2;      //no idea why, but this just works

        //calculate movement distanve
        int steps = (move_location-stepper_location)/DISTANCE_PER_ROTATION*STEPS_PER_ROTATION*correction_factor;

        //if movement is negitve (or less then our minimun number of steps), back off and try again as backlash correction
        if(steps < MINIMUM_NUMBER_OF_STEPS){
            //add value to failure array if not first positioning
            if(mirror_location == stepper_location){
                failures[failure_index] = move_location-stepper_location;
                failure_index++;
                if(failure_index >= 3){
                  failure_index = 0;
                }
            }
            steps -= BACKLASH_OVERSHOOT_STEPS;
        }
        else{
            //add failure offset to step
            steps += failure_offset;
            attempts++;
        }

        //actually move
        stepper->setTargetRel(steps);
        controller.move(*stepper);

        //wait for screw to settle and store locations
        delay(100);
        mirror_location = calulateLocation();
        last_stepper_location = stepper_location;
        stepper_location = calulateLocation();

        //check if move was succesful (encoder actually rotated)
        if(stepper_location == last_stepper_location){
            if(secondPass){
                //resetting the failure array did not work, so we have a hardware issue
                Serial.print("Error: ");
                Serial.print(name);
                Serial.println(" axis failed to move. Check power or encoder connections.");
                return false;
            }
            else{
                secondPass = true;
                //this resets the failure array if it gets stuck (software reset)
                failure_index = 0;
                for(int i = 0; i < 3; i++){
                    failures[i] = 0;
                }
            }
        }

        //all the movement code after this point tries different things if movement fails.
        
        if(attempts >= 20){
            //if it gets above 20 attempts, fail
            Serial.print("Error: ");
            Serial.print(name);
            Serial.println(" axis failed to move. Check power or encoder connections.");
            return false;
        }
        else if(attempts == 15){
            //if attempts gets to high, increase acceptable range to .75um
            allowedError = .75;
            //also does a software reset
            failure_index = 0;
            for(int i = 0; i < 3; i++){
                failures[i] = 0;
            }
        }
        else if(attempts == 10){
            //if attempts gets to high, increase acceptable range to .5um
            allowedError = .5;
            //also does a software reset
            failure_index = 0;
            for(int i = 0; i < 3; i++){
                failures[i] = 0;
            }
        }
        else if(attempts == 5){
            //does a software reset
            failure_index = 0;
            for(int i = 0; i < 3; i++){
                failures[i] = 0;
            }
        }
    }
    
    //turn off our motor
    digitalWrite(en_pin, HIGH);
    return true;
}


bool Axis::homeAxis(float offset_in_rotations){
    digitalWrite(en_pin, LOW);
    //if on limit get off it
    if(digitalRead(limit)){
        if(!moveOffLimitSwitch()){
            Serial.print("Error: ");
            Serial.print(name);
            Serial.println(" homing failed to leave limit switch.");
            digitalWrite(en_pin, HIGH);
            return false;
        }
    }

    //move to limit switch
    if(!moveToLimitSwitch()){
        Serial.print("Error: ");
        Serial.print(name);
        Serial.println(" homing failed to trip limit switch.");
        digitalWrite(en_pin, HIGH);
        return false;
    }

    if(offset_in_rotations != 0){
        int steps = offset_in_rotations*STEPS_PER_ROTATION*correction_factor;
        stepper->setTargetRel(steps);
        controller.move(*stepper);
    }

    //back up to index
    if(!backupToIndex()){
        Serial.print("Error: ");
        Serial.print(name);
        Serial.println(" homing failed to find encoder index.");
        digitalWrite(en_pin, HIGH);
        return false;
    }

    //wait for screw to settle (belt tension) before setting 0 point
    delay(100);
    resetLocation();
    digitalWrite(en_pin, HIGH);

    homed = true;
    return true;
}

//homing subroutine moves off of limit switch
bool Axis::moveOffLimitSwitch(){
    //move tilt to limit
    stepper->setTargetRel(MAX_HOMING_STEPS);
    controller.moveAsync(*stepper);

    delay(100);

    //wait for limit to be triggered and stop
    while(digitalRead(limit)){
        //throws an error if the axis has moved MAX_HOMING_STEPS without releasing limit
        if(controller.getCurrentSpeed() <= MINIMUM_STEPPER_SPEED){
            controller.stop();
            return false;
        }
    }
    controller.stop();
    return true;
}

//homing subroutine moves to limit switch
bool Axis::moveToLimitSwitch(){
    //move tilt to limit
    stepper->setTargetRel(-MAX_HOMING_STEPS);
    controller.moveAsync(*stepper);

    delay(100);

    //wait for limit to be triggered and stop
    while(!digitalRead(limit)){
        //throws an error if the axis has moved MAX_HOMING_STEPS finding finding limit
        if(controller.getCurrentSpeed() <= MINIMUM_STEPPER_SPEED){
            controller.stop();
            return false;
        }
    }
    controller.stop();
    return true;
}

//homing subroutine moves to nearest index to limit
bool Axis::backupToIndex(){
    //back up to index
    stepper->setTargetRel(INDEX_BACKUP_STEPS);
    controller.moveAsync(*stepper);

    delay(100);

    //move until encoder index pin triggered
    while(!digitalRead(encoder_i)){
        //throws error if axis has rotated over a single rotation
        if(controller.getCurrentSpeed() <= MINIMUM_STEPPER_SPEED){
            controller.stop();
            return false;
        }
    }
    controller.stop();
    return true;
}

//local: returns stepper value
long Axis::getLocation_Stepper(){
    return stepper->getPosition();
}

//local: returns encoder value
long Axis::getLocation_Encoder(){
    return encoder->read();
}

float Axis::calulateLocation(){
    //we return the location correcting for invertion and correction factor
    if(inverted){
        return getLocation_Encoder()*DISTANCE_PER_ROTATION/COUNTS_PER_ROTATION/correction_factor;
    }
    else{
        return -getLocation_Encoder()*DISTANCE_PER_ROTATION/COUNTS_PER_ROTATION/correction_factor;
    }
}

//returns location
float Axis::getLocation(){
    if(!homed){
        return 12345;
    }
    else{
        return mirror_location;
    }
}

//returns max position
float Axis::getMaxPos(){
    return MAX_POS;
}

//sets speed
void Axis::setSpeed(long s){
    stepper->setMaxSpeed(s/correction_factor);
}

//sets acceleration
void Axis::setAcceleration(long a){
    stepper->setAcceleration(a/correction_factor);
}

void Axis::resetLocation(){
    //zero motor locations
    stepper->setPosition(0);

    //zero encoder locations
    encoder->write(0);

    //reset mirror memory
    mirror_location = 0;
}
