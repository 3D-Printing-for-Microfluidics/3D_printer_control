/*----------------------------------------------
 * Instructions - TBD
 * See https://www.pjrc.com/teensy/td_libs_Encoder.htmlvoid s-etup() {
  // put your setup code here, to run once:

}

void loop() {
  // put your main code here, to run repeatedly:

}
 * for details about how to use the Encoder library
 * ---------------------------------------------*/

// This optional setting causes Encoder to use more optimized code,
// It must be defined before Encoder.h is included.
#define ENCODER_OPTIMIZE_INTERRUPTS
#include <Encoder.h>

Encoder rotary_encoder(2, 3);

char receivedChar;
boolean newData = false;

void setup() {
    Serial.begin(115200);
    while (!Serial);
    delay(100);
//    Serial.println("Ready to receive commands, either 0 or 1 as below:");
//    Serial.println("  0 - Set encoder count to 0");
//    Serial.println("  1 - Read encoder count and write to serial");
}

int count;

void loop() {
    recvOneChar();
    // showNewData();
    switch(receivedChar) { 
        case '0':
          rotary_encoder.write(0);
          break;
           
        case '1':
          count = rotary_encoder.read();
          Serial.flush();
          Serial.println(count);
//          Serial.write(count);
          break;

        default:
           // handle unwanted input here
           break;
   }
}

void recvOneChar() {
    if (Serial.available() > 0) {
        receivedChar = Serial.read();
//        newData = true;
    }
}

void showNewData() {
    if (newData == true) {
        Serial.print("This just in ... ");
        Serial.println(receivedChar);
        newData = false;
    }
}
