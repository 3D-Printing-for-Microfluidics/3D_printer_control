#include "Arduino.h"
#include "Tip_Tilt.h"

Tip_Tilt* tt;
char opcode[3];
String data = "";

//declare helpers
void translate();

void setup() {
    //setup
    tt = new Tip_Tilt();
    Serial.begin(115200);

    //precisionTestDigital();
    //precisionTestPhysical();
    //homingAccuracyTest();
}

void loop() {
    //if serial is available
    if (Serial.available() > 0) {
        //get the opcode
        opcode[0] = Serial.read();
        opcode[1] = Serial.read();
        opcode[2] = Serial.read();
        data = "";

        //get remaining data
        while (Serial.available() > 0) {
            int inChar = Serial.read();

            if (!(inChar == '\n' || inChar == '\r')) {
                data += (char)inChar;
            }
            //when new line hit, process command
            else {
                translate();
            }
        }
    }
}

void translate(){
    bool valid_op = true;
  //init
    if(opcode[0] == 'I'){
        Serial.println("Info: Connecting");
        if(tt->connectAxis()){
            Serial.println("Connected");
        }
    }
    //home
    else if(opcode[0] == 'H'){
        Serial.println("Info: Homing");
        if(tt->homeAxis()){
            Serial.println("Info: Homed");
        }
    }
    //reset
    else if(opcode[0] == 'R'){
        Serial.println("Info: Disconnecting");
        if(tt->disconnectAxis()){
            Serial.println("Disconnected");
        }
    }
    //move commands
    else if(opcode[0] == 'M'){
      //relative
      if(opcode[1] == 'R'){
          if(opcode[2] == '1'){
              Serial.print("Info: Moving tip axis by ");
              Serial.println(data.toFloat());
              tt->moveTipAxisByDistance(data.toFloat(), false);
              Serial.println("Info: Move finished");
          }
          else if(opcode[2] == '2'){
              Serial.print("Info: Moving tilt axis by ");
              Serial.println(data.toFloat());
              tt->moveTiltAxisByDistance(data.toFloat(), false);
              Serial.println("Info: Move finished");
          }
          else{
            valid_op = false;
          }
      }
      //coarse relative
      else if(opcode[1] == 'r'){
          if(opcode[2] == '1'){
              Serial.print("Info: Moving (quick) tip axis by ");
              Serial.println(data.toFloat());
              tt->moveTipAxisByDistance(data.toFloat(), true);
              Serial.println("Info: Move finished");
          }
          else if(opcode[2] == '2'){
              Serial.print("Info: Moving (quick) tilt axis by ");
              Serial.println(data.toFloat());
              tt->moveTiltAxisByDistance(data.toFloat(), true);
              Serial.println("Info: Move finished");
          }
          else{
            valid_op = false;
          }
      }
      //absolute
      else if(opcode[1] == 'A'){
          if(opcode[2] == '1'){
              Serial.print("Info: Moving tip axis to ");
              Serial.println(data.toFloat());
              tt->moveTipAxisToLocation(data.toFloat(), false);
              Serial.println("Info: Move finished");
          }
          else if(opcode[2] == '2'){
              Serial.print("Info: Moving tilt axis to ");
              Serial.println(data.toFloat());
              tt->moveTiltAxisToLocation(data.toFloat(), false);
              Serial.println("Info: Move finished");
          }
          else{
            valid_op = false;
          }
      }
      //absolute fast
      else if(opcode[1] == 'a'){
          if(opcode[2] == '1'){
              Serial.print("Info: Moving (quick) tip axis to ");
              Serial.println(data.toFloat());
              tt->moveTipAxisToLocation(data.toFloat(), true);
              Serial.println("Info: Move finished");
          }
          else if(opcode[2] == '2'){
              Serial.print("Info: Moving (quick) tilt axis to ");
              Serial.println(data.toFloat());
              tt->moveTiltAxisToLocation(data.toFloat(), true);
              Serial.println("Info: Move finished");
          }
          else{
            valid_op = false;
          }
      }
      else{
        valid_op = false;
      }
    }
    //getters
    else if(opcode[0] == 'G'){
      //position
      if(opcode[1] == 'P'){
          if(opcode[2] == '1'){
              Serial.println("Info: Getting Tip Position");
              Serial.println(tt->tipLocation());
          }
          else if(opcode[2] == '2'){
              Serial.println("Info: Getting Tilt Position");
              Serial.println(tt->tiltLocation());
          }
          else{
            valid_op = false;
          }
      }
      //max
      else if(opcode[1] == 'U'){
          if(opcode[2] == '1'){
              Serial.println("Info: Getting Max Tip");
              Serial.println(tt->getMaxTip());
          }
          else if(opcode[2] == '2'){
              Serial.println("Info: Getting Max Tilt");
              Serial.println(tt->getMaxTilt());
          }
          else{
            valid_op = false;
          }
      }
      //min
      else if(opcode[1] == 'L'){
          if(opcode[2] == '1'){
              Serial.println("Info: Getting Min Tip");
              Serial.println(tt->getMinTip());
          }
          else if(opcode[2] == '2'){
              Serial.println("Info: Getting Min Tilt");
              Serial.println(tt->getMinTilt());
          }
          else{
            valid_op = false;
          }
      }
      //acceleration
      else if(opcode[1] == 'A'){
          if(opcode[2] == '1'){
              Serial.println("Info: Getting Acceleration");
              Serial.println(tt->getStepperAcceleration());
          }
          else if(opcode[2] == '2'){
              Serial.println("Info: Getting Acceleration");
              Serial.println(tt->getStepperAcceleration());
          }
          else{
            valid_op = false;
          }
      }
      //velocity
      else if(opcode[1] == 'V'){
          if(opcode[2] == '1'){
              Serial.println("Info: Getting Speed");
              Serial.println(tt->getStepperSpeed());
          }
          else if(opcode[2] == '2'){
            Serial.println("Info: Getting Speed");
              Serial.println(tt->getStepperSpeed());
          }
          else{
            valid_op = false;
          }
      }
      else{
        valid_op = false;
      }
    }
    //setters
    else if(opcode[0] == 'S'){
      //acceleration
      if(opcode[1] == 'A'){
          if(opcode[2] == '1'){
              Serial.print("Info: Setting Acceleration to ");
              Serial.println(data.toInt());
              tt->setStepperAcceleration(data.toInt());
          }
          else if(opcode[2] == '2'){
              Serial.print("Info: Setting Acceleration to ");
              Serial.println(data.toInt());
              tt->setStepperAcceleration(data.toInt());
          }
          else{
            valid_op = false;
          }
      }
      //velocity
      else if(opcode[1] == 'V'){
          if(opcode[2] == '1'){
              Serial.print("Info: Setting Speed to ");
              Serial.println(data.toInt());
              tt->setStepperSpeed(data.toInt());
          }
          else if(opcode[2] == '2'){
              Serial.print("Info: Setting Speed to ");
              Serial.println(data.toInt());
              tt->setStepperSpeed(data.toInt());
          }
          else{
            valid_op = false;
          }
      }
      else{
        valid_op = false;
      }
    }

    if(!valid_op){
        Serial.println("Error: Invalid opcode");
    }
    Serial.println("Done");
}


//Precision Test (digital)
//Each axis is positioned randomly 100x location offsets are printed.
void precisionTestDigital(){
  
    tt->homeAxis();

    //optional speed change
    //tt->setStepperSpeed(1000);
    //tt->setStepperAcceleration(2500);

    Serial.println();
    Serial.println("Tilt test 1000x");
    
    //move tilt to 100 random locations and print error
    for(int i = 0; i < 1000; i++){
       float r = random(0,tt->getMaxTip()*100)/100;
       tt->moveTiltAxisToLocation(r, false);
       delay(100);
       float l = tt->tiltLocation();
       Serial.print(r);
       Serial.print("\t");
       Serial.print(l);
       Serial.print("\t");
       Serial.println(l-r);
    }
    
    Serial.println();
    Serial.println("Tip test 1000x");
    
    //move tip to 100 random locations and print error
    for(int i = 0; i < 1000; i++){
       float r = random(0,tt->getMaxTip()*100)/100;
       tt->moveTipAxisToLocation(r, false);
       delay(100);
       float l = tt->tipLocation();
       Serial.print(r);
       Serial.print("\t");
       Serial.print(l);
       Serial.print("\t");
       Serial.println(l-r);
    }
     
     //End Test

}

//Precision Test (physical)
//Each axis is positioned between 0 and 500um 10x. Physical location should be checked. 
//This can also be used to check physical accuracy
void precisionTestPhysical(){
    
    tt->homeAxis();
    
    Serial.println();
    Serial.println("Tip test");

    
    //optional speed change
    //tt->setStepperSpeed(1000);
    //tt->setStepperAcceleration(2500);
    
    //move tip between 500 and 0 3x
    //decrease the move location to see physical accuracy
    for(int i = 0; i < 3; i++){
       tt->moveTipAxisToLocation(500, false);
       delay(5000);
       tt->moveTipAxisToLocation(0, false);
       delay(5000);
    }
    
    Serial.println();
    Serial.println("Tilt test");
    
    //move tilt between 500 and 0 3x
    //decrease the move location to see physical accuracy
    for(int i = 0; i < 3; i++){
       tt->moveTiltAxisToLocation(500, false);
       delay(5000);
       tt->moveTiltAxisToLocation(0, false);
       delay(5000);
    }
    
    //End Test

}




//Homing Accuracy Test (Home from each corner twice)
//Home from each corner twice. Homing should end in same place each time
//Test using mirror and laser.
void homingAccuracyTest(){
    //optional speed change
    //tt->setStepperSpeed(1000);
    //tt->setStepperAcceleration(2500);
    
    //inital home
    tt->homeAxis();
    delay(5000);
    
    //home from max tip
    tt->moveTipAxisToLocation(tt->getMaxTip(), false);
    tt->homeAxis();
    delay(5000);
    
    //home from max tip & tilt
    tt->moveTipAxisToLocation(tt->getMaxTip(), false);
    tt->moveTiltAxisToLocation(tt->getMaxTilt(), false);
    tt->homeAxis();
    delay(5000);
    
    //home from max tilt
    tt->moveTiltAxisToLocation(tt->getMaxTilt(), false);
    tt->homeAxis();
    delay(5000);
    
    //home from origin
    tt->homeAxis();
    delay(5000);
     
     //End Test

}
