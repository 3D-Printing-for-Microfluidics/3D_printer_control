#include "Arduino.h"
#include "Tip_Tilt.h"

Tip_Tilt *tt;
char opcode[3];
String data = "";

// declare helpers
void translate();

void setup() {
    // setup
    tt = new Tip_Tilt();
    Serial.begin(115200);
}

void loop() {
    // if serial is available
    if (Serial.available() > 0) {
        // get the opcode
        opcode[0] = Serial.read();
        opcode[1] = Serial.read();
        opcode[2] = Serial.read();
        data = "";

        // get remaining data
        while (Serial.available() > 0) {
            int inChar = Serial.read();

            if (!(inChar == '\n' || inChar == '\r')) {
                data += (char)inChar;
            }
            // when new line hit, process command
            else {
                translate();
            }
        }
    }
}

void translate() {
    // init
    if (opcode[0] == 'I') {
        tt->connectAxis();
        Serial.println("Info: Connecting");
        Serial.println("Connected");
        Serial.println("Done");

    }
    // home
    else if (opcode[0] == 'H') {
        Serial.println("Info: Homing");
        tt->homeAxis();
        Serial.println("Done");
    }
    // reset
    else if (opcode[0] == 'R') {
        Serial.println("Info: Disconnecting");
        tt->disconnectAxis();
        Serial.println("Disconnected");
        Serial.println("Done");
    }
    // move commands
    else if (opcode[0] == 'M') {
        // relative
        if (opcode[1] == 'R') {
            if (opcode[2] == '1') {
                tt->moveTipAxisByDistance(data.toFloat(), false);
            } else if (opcode[2] == '2') {
                tt->moveTiltAxisByDistance(data.toFloat(), false);
            } else {
            }
        }
        // coarse relative
        else if (opcode[1] == 'r') {
            if (opcode[2] == '1') {
                tt->moveTipAxisByDistance(data.toFloat(), true);
            } else if (opcode[2] == '2') {
                tt->moveTiltAxisByDistance(data.toFloat(), true);
            } else {
            }
        }
        // absolute
        else if (opcode[1] == 'A') {
            if (opcode[2] == '1') {
                tt->moveTipAxisToLocation(data.toFloat(), false);
            } else if (opcode[2] == '2') {
                tt->moveTiltAxisToLocation(data.toFloat(), false);
            } else {
            }
        }
        // absolute fast
        else if (opcode[1] == 'a') {
            if (opcode[2] == '1') {
                tt->moveTipAxisToLocation(data.toFloat(), true);
            } else if (opcode[2] == '2') {
                tt->moveTiltAxisToLocation(data.toFloat(), true);
            } else {
            }
        } else {
        }
        Serial.println("Done");
    }
    // getters
    else if (opcode[0] == 'G') {
        // position
        if (opcode[1] == 'P') {
            if (opcode[2] == '1') {
                Serial.println("Info: Getting Tip Position");
                Serial.println(tt->tipLocation(),3);
            } else if (opcode[2] == '2') {
                Serial.println("Info: Getting Tilt Position");
                Serial.println(tt->tiltLocation(),3);
            } else {
            }
            Serial.println("Done");
        }
        // max
        else if (opcode[1] == 'U') {
            if (opcode[2] == '1') {
                Serial.println("Info: Getting Max Tip");
                Serial.println(tt->getMaxTip(),3);
            } else if (opcode[2] == '2') {
                Serial.println("Info: Getting Max Tilt");
                Serial.println(tt->getMaxTilt(),3);
            } else {
            }
            Serial.println("Done");
        }
        // min
        else if (opcode[1] == 'L') {
            if (opcode[2] == '1') {
                Serial.println("Info: Getting Min Tip");
                Serial.println(tt->getMinTip(),3);
            } else if (opcode[2] == '2') {
                Serial.println("Info: Getting Min Tilt");
                Serial.println(tt->getMinTilt(),3);
            } else {
            }
            Serial.println("Done");
        }
        // acceleration
        else if (opcode[1] == 'A') {
            if (opcode[2] == '1') {
                Serial.println("Info: Getting Acceleration");
                Serial.println(tt->getStepperAcceleration());
            } else if (opcode[2] == '2') {
                Serial.println("Info: Getting Acceleration");
                Serial.println(tt->getStepperAcceleration());
            } else {
            }
            Serial.println("Done");
        }
        // velocity
        else if (opcode[1] == 'V') {
            if (opcode[2] == '1') {
                Serial.println("Info: Getting Speed");
                Serial.println(tt->getStepperSpeed());
            } else if (opcode[2] == '2') {
                Serial.println("Info: Getting Speed");
                Serial.println(tt->getStepperSpeed());
            } else {
            }
            Serial.println("Done");
        } else {
        }
    }
    // setters
    else if (opcode[0] == 'S') {
        // acceleration
        if (opcode[1] == 'A') {
            if (opcode[2] == '1') {
                Serial.print("Info: Setting Acceleration to ");
                Serial.println(data.toInt());
                tt->setStepperAcceleration(data.toInt());
            } else if (opcode[2] == '2') {
                Serial.print("Info: Setting Acceleration to ");
                Serial.println(data.toInt());
                tt->setStepperAcceleration(data.toInt());
            } else {
            }
            Serial.println("Done");
        }
        // velocity
        else if (opcode[1] == 'V') {
            if (opcode[2] == '1') {
                Serial.print("Info: Setting Speed to ");
                Serial.println(data.toInt());
                tt->setStepperSpeed(data.toInt());
            } else if (opcode[2] == '2') {
                Serial.print("Info: Setting Speed to ");
                Serial.println(data.toInt());
                tt->setStepperSpeed(data.toInt());
            } else {
            }
            Serial.println("Done");
        } else {
        }
    }
}
