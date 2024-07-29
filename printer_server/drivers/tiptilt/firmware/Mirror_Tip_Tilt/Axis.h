#ifndef AXIS_H
#define AXIS_H

#include "TeensyStep.h"
#include <Encoder.h>
#define ENCODER_OPTIMIZE_INTERRUPTS

class Axis {
public:

    Axis(String name, bool inverted, int dir_pin, int step_pin, int en_pin, int encoder_i, int encoder_a, int encoder_b, int limit, float correction_factor);
    ~Axis();
    
    bool moveAxis(float move_location, bool coarseMove);
    bool homeAxis(float offset_in_rotations);

    float getLocation();
    float getMaxPos();
    
    void setSpeed(long s);
    void setAcceleration(long a);
  
private:
    //inital variables
    String name;
    int dir_pin;
    int step_pin;
    int en_pin;
    int encoder_i;
    int encoder_a;
    int encoder_b;
    int limit;
    bool inverted;
    bool homed;

    //general variables
    float correction_factor;
    float mirror_location;

    StepControl controller; 
    Stepper* stepper;
    Encoder* encoder;

    //homing subroutines
    bool moveOffLimitSwitch();
    bool moveToLimitSwitch();
    bool backupToIndex();
    void resetLocation();

    //internal location variables
    long getLocation_Encoder();
    long getLocation_Stepper();
    float calulateLocation();

};

#endif
