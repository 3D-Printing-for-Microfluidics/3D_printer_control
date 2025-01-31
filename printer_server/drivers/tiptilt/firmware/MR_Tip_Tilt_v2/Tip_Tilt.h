#ifndef TIP_TILT_H
#define TIP_TILT_H

#include "TeensyStep.h"
#include "Axis.h"

class Tip_Tilt {
public:
    Tip_Tilt();
    ~Tip_Tilt();

    void Tip_Tilt_Setup();
    
    //home
    bool homeAxis();
    
    //connection handshake
    bool connectAxis();
    
    //get pos
    float tipLocation(); //in rad
    float tiltLocation(); //in rad
    
    //set pos absolute
    bool moveTipAxisToLocation(float location, bool coarseMove); //in rad
    bool moveTiltAxisToLocation(float location, bool coarseMove); //in rad
    
    //set pos relative
    bool moveTipAxisByDistance(float distance, bool coarseMove); //in rad
    bool moveTiltAxisByDistance(float distance, bool coarseMove); //in rad
    
    //get max/min pos
    float getMinTip(); //in rad
    float getMaxTip(); //in rad
    float getMinTilt(); //in rad
    float getMaxTilt(); //in rad
    
    //get/set acceleration
    long getStepperAcceleration();
    void setStepperAcceleration(long a);
    
    //get/set velocity
    long getStepperSpeed();
    void setStepperSpeed(long s);
    
    //disconection handshake
    bool disconnectAxis();
  
  
private:
    Axis* tipAxis;
    Axis* tiltAxis;

    long default_speed;
    long default_acceleration;
};

#endif
