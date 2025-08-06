// Teensy motor controller firmware using MP6550 and current sensing
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
const int IN1 = 3;              // PWM-capable
const int IN2 = 4;              // PWM-capable
const int VISEN_PIN = A0;       // Analog input for VISEN
const int SLEEP_HB_LDO = 5;     // Combined enable (board-specific wiring)

// ---------------- System configuration ----------------
static constexpr float kVref = 3.3f;       // ADC analog reference (Teensy 4.x default 3.3 V)
static constexpr int   kADC_Bits = 12;     // 12-bit resolution
static constexpr float kADC_Max = float((1 << kADC_Bits) - 1);

// MP6550 with ISET = 2 kΩ (carrier default) => 0.2 V/A
static constexpr float kVisen_V_per_A = 0.200f;   // 200 mV/A

// Your motor current model: I(A) = I0 + K * t(kg·mm)
static constexpr float kI_intercept_A = 0.025f;        // I0
static constexpr float kI_per_t_A_per_kgmm = 0.0049f;  // K

// Safety timeout
const unsigned long TIMEOUT_MS = 5000;    // ms

// Default PWM duty (0..255). Adjust as needed for speed/torque ramping.
uint8_t kPWM = 200;

// Target torque in kg·mm (runtime-configurable via "s <kgmm>")
float torqueTarget_kgmm = 40.0f;


// ---------------- State tracking ----------------
bool running = false;
unsigned long startTime = 0;
int direction = 1;  // 1 = tighten, -1 = untighten


// ---------------- Helpers: ADC / VISEN / Torque ----------------

// Convert ADC counts -> VISEN volts
inline float visenVoltsFromADC(int adcCounts) {
  return (float(adcCounts) / kADC_Max) * kVref;
}

// Convert VISEN volts -> current (A) using 0.2 V/A
inline float currentFromVisenVolts(float visenV) {
  return visenV / kVisen_V_per_A;
}

// Convert VISEN volts -> torque (kg·mm) using inverse of your motor model
float torqueFromVisenVolts(float visenV) {
  const float I = currentFromVisenVolts(visenV);                 // A
  float t = (I - kI_intercept_A) / kI_per_t_A_per_kgmm;          // kg·mm
  if (t < 0.0f) t = 0.0f;                                        // guard small negatives
  return t;
}

// Optional: torque -> VISEN volts (useful if you ever want to set a voltage threshold internally)
float visenVoltsFromTorque(float torque_kgmm) {
  const float I = kI_intercept_A + kI_per_t_A_per_kgmm * torque_kgmm;
  return I * kVisen_V_per_A;  // V
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
MovingAverage<8> torqueFilt;   // 8-sample average for stability


// ---------------- Motor control ----------------
void driveTighten() {
  // Forward: IN1 PWM, IN2 low
  analogWrite(IN1, kPWM);
  digitalWrite(IN2, LOW);
}

void driveUntighten() {
  // Reverse: IN2 PWM, IN1 low
  analogWrite(IN2, kPWM);
  digitalWrite(IN1, LOW);
}

void brakeCoastOff() {
  // Turn off both PWM outputs
  analogWrite(IN1, 0);
  analogWrite(IN2, 0);
}


// ---------------- Firmware lifecycle ----------------
void setup() {
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(SLEEP_HB_LDO, OUTPUT);
  pinMode(VISEN_PIN, INPUT);

  // Enable H-bridge + 3.3 V LDO (board-specific combined line)
  digitalWrite(SLEEP_HB_LDO, HIGH);

  // Quiet PWM (20 kHz)
  analogWriteFrequency(IN1, 20000);
  analogWriteFrequency(IN2, 20000);

  // Initialize ADC with desired settings
  adc->adc0->setReference(ADC_REFERENCE::REF_3V3);              // Teensy 4.x default
  adc->adc0->setAveraging(32);                                  // Average 32 samples
  adc->adc0->setResolution(12);                                 // 12-bit resolution
  adc->adc0->setConversionSpeed(ADC_CONVERSION_SPEED::MED_SPEED);
  adc->adc0->setSamplingSpeed(ADC_SAMPLING_SPEED::MED_SPEED);

  Serial.begin(115200);
}


// Start motor with desired direction
void startMotor(int dir) {
  direction = dir;
  running   = true;
  startTime = millis();

  torqueFilt = MovingAverage<8>();  // reset filter

  if (dir == 1) {
    driveTighten();
  } else {
    driveUntighten();
  }

  controlTimer.begin(torqueControlISR, 10000);  // 100 Hz = every 10,000 µs
  Serial.println("start");
}



// Stop motor and report
void stopMotor() {
  controlTimer.end();  // Stop ISR
  brakeCoastOff();
  running = false;
  Serial.println("stop");
}


// ---------------- Command parsing ----------------
// We read a full line so we can support "s 37.5" etc.
void handleLine(const String& line) {
  if (line.length() == 0) return;

  if (line == "t") {
    startMotor(1);
  } else if (line == "u") {
    startMotor(-1);
  } else if (line == "e") {
    stopMotor();
  } else if (line.startsWith("s ")) {
    // Set torque target in kg·mm
    float newTarget = line.substring(2).toFloat();
    if (newTarget >= 0.0f) {
      torqueTarget_kgmm = newTarget;
      Serial.print("target_kgmm ");
      Serial.println(torqueTarget_kgmm, 3);
    }
  } else if (line == "q") {
    // Query instantaneous torque
    int adc = adc->adc0->analogRead(VISEN_PIN);
    float visenV = visenVoltsFromADC(adc);
    float tq = torqueFromVisenVolts(visenV);
    Serial.print("torque ");
    Serial.println(tq, 3);
  }
}


// ---------------- Main loop ----------------
void loop() {
  // Only handle serial commands here
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    handleLine(cmd);
  }
}


// ---------------- Control ISR ----------------
void torqueControlISR() {
  if (!running || inISR) return;
  inISR = true;

  // Record time at ISR entry
  uint32_t now_ms = millis();

  // Read ADC
  int adcCounts = adc->adc0->analogRead(VISEN_PIN);
  float visenV  = visenVoltsFromADC(adcCounts);
  float torque  = torqueFromVisenVolts(visenV);

  // Filter + telemetry
  torqueFilt.add(torque);
  float torqueAvg = torqueFilt.mean();

  // Report timestamp and torque
  Serial.print("torque ");
  Serial.print(torqueAvg, 3);
  Serial.print(" @ ");
  Serial.print(now_ms);
  Serial.println(" ms");

  // Stop if torque reached
  if (torqueAvg >= torqueTarget_kgmm) {
    stopMotor();
    Serial.println("done");
  }

  // Timeout check
  if (now_ms - startTime > TIMEOUT_MS) {
    stopMotor();
    Serial.println("timeout");
  }

  inISR = false;
}

