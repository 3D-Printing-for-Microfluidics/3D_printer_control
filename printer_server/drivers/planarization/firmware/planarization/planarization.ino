// Teensy 4.0 motor controller firmware using MP6550 and current sensing
// Tightens/untightens to a target *torque* specified in kg·mm.
// Uses VISEN -> current (A) via 200 mV/A, then current -> torque with your model:
//   I(A) = 0.025 + 0.0049 * t(kg·mm)  =>  t = (I - 0.025)/0.0049
//
// Serial commands (one per line):
//   "t"             : start tightening to current torqueTarget_kgmm
//   "u"             : start untightening to current torqueTarget_kgmm (typically lower)
//   "e"             : emergency stop
//   "s <kgmm>"      : set new torque target in kg·mm (e.g., "s 40")
//   "q"             : query: prints "torque <kgmm>" (instantaneous)
//

#include <ADC.h>
#include <ADC_util.h>
ADC *adc = new ADC(); // ADC object
IntervalTimer controlTimer;
volatile bool inISR = false;

// ---------------- Pin assignments ----------------
const int IN1 = 2;              // PWM-capable
const int IN2 = 3;              // PWM-capable
const int VISEN_PIN = A0;       // Analog input for VISEN (Pin 14 on Teensy 4.0)
const int SLEEP_HB_LDO = 4;     // Combined enable (board-specific wiring)

// ---------------- System configuration ----------------
static constexpr float kVref = 3.3f;       // ADC analog reference
static constexpr int   kADC_Bits = 12;     // 12-bit resolution
static constexpr float kADC_Max = float((1 << kADC_Bits) - 1);

// MP6550 with ISET = 2 kΩ => 0.2 V/A
static constexpr float kVisen_V_per_A = 0.200f;   // 200 mV/A

// Your motor current model: I(A) = I0 + K * t(kg·mm)
static constexpr float kI_intercept_A = 0.05f;        
static constexpr float kI_per_t_A_per_kgmm = 0.0065f;  
static constexpr float no_load_current = 0.081f;

// Safety timeout
const unsigned long TIMEOUT_MS = 10000;    // ms

// Default PWM duty (0..255). Adjust as needed for speed/torque ramping.
uint8_t kPWM = 200;

// Target torque in kg·mm (Must be volatile since it's shared between main and ISR)
volatile float torqueTarget_kgmm = 40.0f;


// ---------------- State tracking ----------------
volatile bool running = false;
volatile bool motor_engaged = false;
volatile unsigned long startTime = 0;
volatile int direction = 1;  // 1 = tighten, -1 = untighten

// Extra spin-down tracking for untightening
const unsigned long EXTRA_SPIN_MS = 1000; // ms to spin after hitting 0
volatile bool spinning_down = false;
volatile uint32_t spin_down_start_time = 0;

// ---------------- ISR to Main Loop Communication ----------------
volatile float isr_torqueAvg = 0.0f;
volatile uint32_t isr_time_ms = 0;
volatile bool isr_data_ready = false;
volatile int isr_stop_reason = 0; // 0=none, 1=done, 2=timeout, 3=extra spin started, 4=fully loose


// ---------------- Helpers: ADC / VISEN / Torque ----------------

inline float visenVoltsFromADC(int adcCounts) {
  return (float(adcCounts) / kADC_Max) * kVref;
}

float torqueFromVisenVolts(float visenV) {
  const float I = visenV / kVisen_V_per_A;                       
  if (I < no_load_current) return 0.0f;                           
  float t = (I - kI_intercept_A) / kI_per_t_A_per_kgmm;          
  if (t < 0.0f) t = 0.0f;                                        
  return t;
}

// ---------------- Simple moving average filter ----------------
template <size_t N>
struct MovingAverage {
  float buf[N] = {0};
  size_t idx = 0;
  bool filled = false;

  void add(float v) {
    buf[idx++] = v;
    if (idx >= N) { idx = 0; filled = true; }
  }
  float mean() const {
    const size_t count = filled ? N : idx;
    if (count == 0) return 0.0f;
    float s = 0.0f;
    for (size_t i = 0; i < count; ++i) s += buf[i];
    return s / float(count);
  }
};
MovingAverage<8> torqueFilt;   


// ---------------- Motor control ----------------
void driveTighten() {
  analogWrite(IN1, kPWM);
  digitalWrite(IN2, LOW);
}

void driveUntighten() {
  analogWrite(IN2, kPWM);
  digitalWrite(IN1, LOW);
}

void brakeCoastOff() {
  analogWrite(IN1, 0);
  analogWrite(IN2, 0);
}


// ---------------- Firmware lifecycle ----------------
void setup() {
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(SLEEP_HB_LDO, OUTPUT);

  digitalWrite(SLEEP_HB_LDO, HIGH);

  // Quiet PWM (20 kHz)
  analogWriteFrequency(IN1, 20000);
  analogWriteFrequency(IN2, 20000);

  adc->adc0->setAveraging(32);                                  
  adc->adc0->setResolution(12);                                 
  adc->adc0->setConversionSpeed(ADC_CONVERSION_SPEED::MED_SPEED);
  adc->adc0->setSamplingSpeed(ADC_SAMPLING_SPEED::MED_SPEED);

  Serial.begin(115200);

  Serial.print("ADC0 resolution: ");
  Serial.println(adc->adc0->getResolution());
  Serial.println(adc->adc0->analogRead(VISEN_PIN));
}


// Start motor
void startMotor(int dir) {
  uint32_t now_ms = millis();
  Serial.print("start ");
  Serial.print(" @ ");
  Serial.print(now_ms);
  Serial.println(" ms");

  direction = dir;
  running   = true;
  startTime = millis();
  spinning_down = false;
  isr_stop_reason = 0;

  torqueFilt = MovingAverage<8>(); 

  if (dir == 1) {
    driveTighten();
  } else {
    driveUntighten();
  }

  controlTimer.begin(torqueControlISR, 10000);  // 100 Hz
  delay(500);
  motor_engaged = true;
}

// Stop called from inside the ISR (NO SERIAL PRINTS HERE)
void stopMotorFromISR() {
  controlTimer.end(); 
  brakeCoastOff();
  running = false;
  motor_engaged = false;
}

// Stop called from main loop manually via command 'e'
void stopMotor() {
  stopMotorFromISR();
  Serial.println("stop");
}


// ---------------- Command parsing ----------------
void handleLine(const String& line) {
  if (line.length() == 0) return;

  if (line == "t") {
    startMotor(1);
  } else if (line == "u") {
    startMotor(-1);
  } else if (line == "e") {
    stopMotor();
  } else if (line.startsWith("s ")) {
    float newTarget = line.substring(2).toFloat();
    if (newTarget >= 0.0f) {
      torqueTarget_kgmm = newTarget;
      Serial.print("target_kgmm ");
      Serial.println(torqueTarget_kgmm, 3);
    }
  } else if (line == "q") {
    uint16_t adcVal = adc->adc0->analogRead(VISEN_PIN);
    float visenV = visenVoltsFromADC(adcVal);
    float tq = torqueFromVisenVolts(visenV);
    Serial.print("torque ");
    Serial.println(tq, 3);
  }
}


// ---------------- Main loop ----------------
void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    handleLine(cmd);
  }

  // Handle telemetry and printing OUTSIDE the ISR
  if (isr_data_ready) {
    // Disable interrupts briefly to copy the volatile variables safely
    noInterrupts();
    float tq = isr_torqueAvg;
    uint32_t t_ms = isr_time_ms;
    int reason = isr_stop_reason;
    isr_data_ready = false;
    isr_stop_reason = 0;
    interrupts();

    // Always print the standard telemetry line
    Serial.print("torque ");
    Serial.print(tq, 3);
    Serial.print(" @ ");
    Serial.print(t_ms);
    Serial.println(" ms");

    // Output EXACTLY what the external parser expects
    if (reason == 1 || reason == 4) {
      // Reason 1: Normal target reached
      // Reason 4: Fully loose (extra spin finished)
      Serial.println("stop");
      Serial.println("done");
    } 
    else if (reason == 2) {
      // Reason 2: Safety timeout
      Serial.println("stop");
      Serial.println("timeout");
    }
    // Note: We silently ignore reason == 3 ("extra spin started") 
    // so we don't confuse the connected system's text parser.
  }
}


// ---------------- Control ISR ----------------
void torqueControlISR() {
  if (!running || inISR) return;
  inISR = true;

  uint32_t now_ms = millis();
  uint16_t adcCounts = adc->adc0->analogRead(VISEN_PIN);
  float visenV = visenVoltsFromADC(adcCounts);
  float torque = torqueFromVisenVolts(visenV);

  torqueFilt.add(torque);
  float torqueAvg = torqueFilt.mean();

  // Send data to main loop
  isr_torqueAvg = torqueAvg;
  isr_time_ms = now_ms;
  isr_data_ready = true;

  if (motor_engaged && torqueFilt.filled) {
    if (direction == 1) {
      if (torqueAvg >= torqueTarget_kgmm) {
        isr_stop_reason = 1;
        stopMotorFromISR();
      }
    }
    else {
      if (!spinning_down) {
        if (torqueAvg <= torqueTarget_kgmm) {
          if (torqueTarget_kgmm <= 0.01f) { 
            spinning_down = true;
            spin_down_start_time = now_ms;
            isr_stop_reason = 3; 
          } else {
            isr_stop_reason = 1;
            stopMotorFromISR();
          }
        }
      } else {
        if ((now_ms - spin_down_start_time) >= EXTRA_SPIN_MS) {
          isr_stop_reason = 4;
          stopMotorFromISR();
        }
      }
    }
  }

  // Timeout check
  if (running && (now_ms - startTime > TIMEOUT_MS)) {
    isr_stop_reason = 2;
    stopMotorFromISR();
  }

  inISR = false;
}