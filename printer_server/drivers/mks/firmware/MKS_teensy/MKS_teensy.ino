int ENCODER_PIN = A6;
int PWM_PIN = A5;
int DIR_PIN = A4;

int solenoid_pins[6] = {0,1,2,3,4,5};
int solenoid_state[6] = {0, 0, 0, 0, 0, 0};
int reed_pins[5] = {13,14,15,16,17};

int ADC_RANGE = 1024;
int ENCODER_RANGE_MM = 1000;
int upper_limit = 600;
int lower_limit = 0;

char opcode[2];
String data = "";

// the setup function runs once when you press reset or power the board
void setup() {
  Serial.begin(9600);

  // Setup solenoids
  for(int i = 0; i < 6; i++){
    pinMode(solenoid_pins[i], OUTPUT);
    digitalWrite(solenoid_pins[i], LOW);
  }

  // Setup reeds
  for(int i = 0; i < 5; i++){
    pinMode(reed_pins[i], INPUT);
  }
  
  // Setup crane
  analogReadAveraging(32);
  pinMode(DIR_PIN, OUTPUT);
  digitalWrite(DIR_PIN, LOW);
  analogWrite(PWM_PIN, 0);
}

void translate();

int get_encoder_position(){
  int position = analogRead(ENCODER_PIN);
  return map(position, 0, ADC_RANGE, 0, ENCODER_RANGE_MM);
}

void move(int target_position){
  int off = 0;
  int min_speed = 48;
  int max_speed = 192;
  int threshold_dist = 75;

  int position = get_encoder_position();
  int start_position = position;
  int distanceToTarget = abs(target_position - position);
  int distanceFromStart = abs(start_position - position);

  if(target_position - position > 0){
    if(target_position > upper_limit){
      analogWrite(PWM_PIN, off);
      return;
    }
    else{
      digitalWrite(DIR_PIN, LOW);
    }
  }
  else{
    if(target_position < lower_limit){
      analogWrite(PWM_PIN, off);
      return;
    }
    else{
      digitalWrite(DIR_PIN, HIGH);
    }
  }

  while((target_position - position > 0 && target_position - start_position > 0) || (position - target_position > 0 && target_position - start_position < 0)){
    position = get_encoder_position();

    if(position > upper_limit && target_position > position){
      analogWrite(PWM_PIN, off);
      return;
    }
    else if(position < lower_limit && target_position < position){
      analogWrite(PWM_PIN, off);
      return;
    }
    
    distanceFromStart = abs(start_position - position);
    int startpwmValue = map(distanceFromStart, 0, threshold_dist, min_speed, max_speed);
    startpwmValue = constrain(startpwmValue, 0, 255);

    distanceToTarget = abs(target_position - position);
    int endpwmValue = map(distanceToTarget, 0, threshold_dist, min_speed, max_speed);
    endpwmValue = constrain(endpwmValue, 0, 255);

    int pwm = min(startpwmValue, endpwmValue);
    analogWrite(PWM_PIN, pwm);
    delay(10);
  }
  delay(1000);
  analogWrite(PWM_PIN, off);
}

// the loop function runs over and over again forever
void loop() {
  //if serial is available
  if (Serial.available() > 0) {
      //get the opcode
      opcode[0] = Serial.read();
      if(opcode[0] == 'M' || opcode[0] == 'P'){
        opcode[1] = Serial.read();
      }
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
    if(opcode[0] == 'H'){ // Set relay high
      int pin = data.toInt();
      digitalWrite(solenoid_pins[pin], HIGH);
      solenoid_state[pin] = 1;
    }
    else if(opcode[0] == 'L'){ // Set relay low
      int pin = data.toInt();
      digitalWrite(solenoid_pins[pin], LOW);
      solenoid_state[pin] = 0;
    }
    else if(opcode[0] == 'R'){ // Get all relay status
      for(int i = 0; i < 6; i++){
        Serial.print(solenoid_state[i]);
      }
      Serial.println();
    }
    else if(opcode[0] == 'S'){ // Read all sensors
      for(int i = 0; i < 5; i++){
        Serial.print(digitalRead(reed_pins[i]));
      }
      Serial.println();
    }
    else if(opcode[0] == 'P'){ // Get encoder info
      if(opcode[1] == 'P'){ // Get encoder position
        Serial.println(get_encoder_position());
      }
      else if(opcode[1] == 'U'){ // Get upper limit
        Serial.println(upper_limit);
      }
      else if(opcode[1] == 'L'){ // Get lower limit
        Serial.println(lower_limit);
      }
      else{
        Serial.println("Error: Invalid opcode");
      }
    }
    else if(opcode[0] == 'M'){ // Movement commands
      if(opcode[1] == 'R'){ // Relative Move
        move(get_encoder_position()+data.toInt());
        Serial.println(get_encoder_position());
      }
      else if(opcode[1] == 'A'){ // Absolute Move
        move(data.toInt());
        Serial.println(get_encoder_position());
      }
      else if(opcode[1] == 'T'){  // Move to Top
        move(500);
        Serial.println(get_encoder_position());
      }
      else if(opcode[1] == 'B'){ // Move to Bottom
        move(20);
        Serial.println(get_encoder_position());
      }
      else{
        Serial.println("Error: Invalid opcode");
      }
    }
    else{
      Serial.println("Error: Invalid opcode");
    }
    Serial.println("Done");
  }