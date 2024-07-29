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
    void connectAxis();
    
    //get pos
    float tipLocation(); //in microns
    float tiltLocation(); //in microns
    
    //set pos absolute
    bool moveTipAxisToLocation(float location, bool coarseMove); //in microns
    bool moveTiltAxisToLocation(float location, bool coarseMove); //in microns
    
    //set pos relative
    bool moveTipAxisByDistance(float distance, bool coarseMove); //in microns
    bool moveTiltAxisByDistance(float distance, bool coarseMove); //in microns
    
    //get max/min pos
    float getMinTip();
    float getMaxTip();
    float getMinTilt();
    float getMaxTilt();
    
    //get/set acceleration
    long getStepperAcceleration();
    void setStepperAcceleration(long a);
    
    //get/set velocity
    long getStepperSpeed();
    void setStepperSpeed(long s);
    
    //disconection handshake
    void disconnectAxis();
  
  
private:
    Axis* tipAxis;
    Axis* tiltAxis;

    long default_speed;
    long default_acceleration;
};

#endif
