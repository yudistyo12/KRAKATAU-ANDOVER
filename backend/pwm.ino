#include <Arduino.h>
#include <Wire.h>
#include <Servo.h>

// =========================================================
// HMC5883L
// =========================================================
#define HMC5883L_ADDR     0x1E
#define REG_CONFIG_A      0x00
#define REG_CONFIG_B      0x01
#define REG_MODE          0x02
#define REG_DATA_X_MSB    0x03

// =========================================================
// IBUS
// =========================================================
#define IBUS_CHANNELS     14
#define IBUS_PACKET_LEN   32
#define IBUS_SERIAL       Serial1
#define PC_SERIAL         Serial

// =========================================================
// CHANNEL REMOTE
// =========================================================
#define CH_SERVO          0       // CH1
#define CH_THROTTLE       2       // CH3
#define MODE_CHANNEL      6       // CH7
#define CH_MARK_WP        9       // CH10
#define CH_CLEAR_WP       11      // CH12

// =========================================================
// SERVO & ESC PINS
// =========================================================
#define SERVO1_PIN        PA5
#define SERVO2_PIN        PA4
#define SERVO_MIN_US      500
#define SERVO_MAX_US      2500
#define SERVO_MIN_ANGLE   0
#define SERVO_MAX_ANGLE   180

#define ESC1_PIN          PA7
#define ESC2_PIN          PB0
#define ESC_MIN_US        1000
#define ESC_STOP_US       1500
#define ESC_MAX_US        2000

// =========================================================
// TIMEOUT CONFIG
// =========================================================
#define IBUS_TIMEOUT      500     // Failsafe RC Sinyal Hilang (500ms)
#define AUTO_CMD_TIMEOUT  500     // Failsafe Jetson/GCS Sinyal Hilang (500ms)
#define COMPASS_INTERVAL       100
#define MOTOR_SEND_INTERVAL    150

// =========================================================
// MOTOR FEEDBACK (SEMENTARA - BERBASIS PWM)
// =========================================================
// PENTING:
// Firmware ini belum memiliki encoder/Hall sensor/ESC telemetry.
// RPM dan SPEED_MPS di bawah adalah ESTIMASI dari PWM,
// bukan kecepatan aktual motor.
#define ESTIMATED_MAX_RPM       3000.0f
#define ESTIMATED_MAX_SPEED_MPS 2.00f

#define MOTOR_STOP_THRESHOLD_US 1520

// =========================================================
// OBJECTS & VARIABLES
// =========================================================
Servo servo1, servo2;
Servo esc1, esc2;

uint8_t ibusPacket[IBUS_PACKET_LEN];
uint16_t channels[IBUS_CHANNELS];
unsigned long lastIBUSPacket = 0;

int autoServoAngle = 90;
int autoESC1us = ESC_STOP_US;
int autoESC2us = ESC_STOP_US;
unsigned long lastAutoCmd = 0;
unsigned long lastCompassSend = 0;
unsigned long lastMotorSend = 0;

// PWM ESC yang sedang aktif
int currentESC1us = ESC_MIN_US;
int currentESC2us = ESC_MIN_US;

// Feedback motor sementara (estimasi dari PWM)
float leftRPM = 0.0f;
float rightRPM = 0.0f;
float speedMps = 0.0f;
const char* motorDirection = "STOP";

enum Mode { MODE_MANUAL, MODE_STANDBY, MODE_AUTO };
Mode currentMode = MODE_MANUAL;

bool markWP = false, clearWP = false;
bool lastMarkWP = false, lastClearWP = false;

// =========================================================
// HELPER FUNCTIONS
// =========================================================
void hmcWriteByte(uint8_t reg, uint8_t value) {
    Wire.beginTransmission(HMC5883L_ADDR);
    Wire.write(reg);
    Wire.write(value);
    Wire.endTransmission();
}

bool hmcReadRaw(int16_t &x, int16_t &y, int16_t &z) {
    Wire.beginTransmission(HMC5883L_ADDR);
    Wire.write(REG_DATA_X_MSB);
    if (Wire.endTransmission(false) != 0) return false;

    Wire.requestFrom(HMC5883L_ADDR, 6);
    if (Wire.available() < 6) return false;

    x = ((int16_t)Wire.read() << 8) | Wire.read();
    z = ((int16_t)Wire.read() << 8) | Wire.read();
    y = ((int16_t)Wire.read() << 8) | Wire.read();
    return true;
}

bool initHMC5883L() {
    hmcWriteByte(REG_CONFIG_A, 0x70);
    hmcWriteByte(REG_CONFIG_B, 0x20);
    hmcWriteByte(REG_MODE, 0x00);
    delay(10);
    Wire.beginTransmission(HMC5883L_ADDR);
    return (Wire.endTransmission() == 0);
}

float calculateHeading(int16_t x, int16_t y) {
    float heading = atan2((float)y, (float)x) * 180.0f / PI;
    if (heading < 0) heading += 360.0f;
    return heading;
}

const char* modeName(Mode mode) {
    switch (mode) {
        case MODE_MANUAL: return "MANUAL";
        case MODE_STANDBY: return "STANDBY";
        case MODE_AUTO: return "AUTO";
    }
    return "UNKNOWN";
}

Mode getMode() {
    uint16_t value = channels[MODE_CHANNEL];
    if (value < 1300) return MODE_MANUAL;
    else if (value < 1700) return MODE_STANDBY;
    else return MODE_AUTO;
}

int ibusToServoAngle(uint16_t value) {
    value = constrain(value, 1000, 2000);
    return map(value, 1000, 2000, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);
}

void setServoAngle(Servo &servo, int angle) {
    angle = constrain(angle, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);
    int pulse = map(angle, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE, SERVO_MIN_US, SERVO_MAX_US);
    servo.writeMicroseconds(pulse);
}

int throttleToESC(uint16_t throttle) {
    throttle = constrain(throttle, 1000, 2000);
    return map(throttle, 1000, 2000, ESC_MIN_US, ESC_MAX_US);
}

void setESC1(int us) {
    currentESC1us = constrain(us, ESC_MIN_US, ESC_MAX_US);
    esc1.writeMicroseconds(currentESC1us);
}

void setESC2(int us) {
    currentESC2us = constrain(us, ESC_MIN_US, ESC_MAX_US);
    esc2.writeMicroseconds(currentESC2us);
}

void stopESC() {
    setESC1(ESC_STOP_US);
    setESC2(ESC_STOP_US);
}

// =========================================================
// MOTOR FEEDBACK
// =========================================================

float pwmToEstimatedRPM(int pwm) {
    pwm = constrain(pwm, ESC_MIN_US, ESC_MAX_US);

    if (abs(pwm - ESC_STOP_US) <= (MOTOR_STOP_THRESHOLD_US - ESC_STOP_US)) {
        return 0.0f;
    }

    if (pwm < ESC_STOP_US) {
        float ratio = (float)(ESC_STOP_US - pwm) /
                      (float)(ESC_STOP_US - ESC_MIN_US);
        return -constrain(ratio, 0.0f, 1.0f) * ESTIMATED_MAX_RPM;
    }

    float ratio = (float)(pwm - ESC_STOP_US) /
                  (float)(ESC_MAX_US - ESC_STOP_US);
    ratio = constrain(ratio, 0.0f, 1.0f);

    return ratio * ESTIMATED_MAX_RPM;
}

void updateMotorFeedback() {
    // SEMENTARA: RPM berasal dari PWM command, bukan sensor aktual.
    leftRPM = pwmToEstimatedRPM(currentESC1us);
    rightRPM = pwmToEstimatedRPM(currentESC2us);

    float averageRPM = (leftRPM + rightRPM) * 0.5f;

    if (abs(averageRPM) < 1.0f) {
        speedMps = 0.0f;
        motorDirection = "STOP";
    } else {
        speedMps = (averageRPM / ESTIMATED_MAX_RPM) *
                   ESTIMATED_MAX_SPEED_MPS;

        motorDirection = averageRPM > 0.0f ? "FORWARD" : "REVERSE";
    }
}

void sendMotorData() {
    updateMotorFeedback();

    PC_SERIAL.print("MOTOR,LEFT_RPM=");
    PC_SERIAL.print(leftRPM, 0);

    PC_SERIAL.print(",RIGHT_RPM=");
    PC_SERIAL.print(rightRPM, 0);

    PC_SERIAL.print(",SPEED_MPS=");
    PC_SERIAL.print(speedMps, 2);

    PC_SERIAL.print(",DIRECTION=");
    PC_SERIAL.println(motorDirection);
}

// =========================================================
// SERIAL & IBUS READERS
// =========================================================
void readPCCommand() {
    static String buffer = "";
    while (PC_SERIAL.available()) {
        char c = PC_SERIAL.read();
        if (c == '\n') {
            if (buffer.startsWith("AUTO,")) {
                int servoIdx = buffer.indexOf("SERVO=");
                int esc1Idx  = buffer.indexOf("ESC1=");
                int esc2Idx  = buffer.indexOf("ESC2=");

                if (servoIdx != -1 && esc1Idx != -1 && esc2Idx != -1) {
                    int requestedServo = buffer.substring(servoIdx + 6).toInt();
                    int requestedESC1 = buffer.substring(esc1Idx + 5).toInt();
                    int requestedESC2 = buffer.substring(esc2Idx + 5).toInt();

                    if (requestedServo >= SERVO_MIN_ANGLE &&
                        requestedServo <= SERVO_MAX_ANGLE &&
                        requestedESC1 >= ESC_MIN_US &&
                        requestedESC1 <= ESC_MAX_US &&
                        requestedESC2 >= ESC_MIN_US &&
                        requestedESC2 <= ESC_MAX_US) {
                        autoServoAngle = requestedServo;
                        autoESC1us = requestedESC1;
                        autoESC2us = requestedESC2;
                        lastAutoCmd = millis();
                    }
                }
            }
            buffer = "";
        } else {
            buffer += c;
        }
    }
}

bool readIBUS() {
    while (IBUS_SERIAL.available()) {
        uint8_t firstByte = IBUS_SERIAL.read();
        if (firstByte != 0x20) continue;

        unsigned long startTime = millis();
        while (!IBUS_SERIAL.available() && millis() - startTime < 10);
        if (!IBUS_SERIAL.available()) return false;

        uint8_t secondByte = IBUS_SERIAL.read();
        if (secondByte != 0x40) continue;

        ibusPacket[0] = firstByte;
        ibusPacket[1] = secondByte;
        int index = 2;

        startTime = millis();
        while (index < IBUS_PACKET_LEN && millis() - startTime < 20) {
            if (IBUS_SERIAL.available()) ibusPacket[index++] = IBUS_SERIAL.read();
        }
        if (index != IBUS_PACKET_LEN) return false;

        uint16_t checksum = 0xFFFF;
        for (int i = 0; i < IBUS_PACKET_LEN - 2; i++) checksum -= ibusPacket[i];
        uint16_t receivedChecksum = ibusPacket[30] | (ibusPacket[31] << 8);

        if (checksum != receivedChecksum) return false;

        for (int ch = 0; ch < IBUS_CHANNELS; ch++) {
            int idx = 2 + ch * 2;
            channels[ch] = ibusPacket[idx] | (ibusPacket[idx + 1] << 8);
        }

        lastIBUSPacket = millis(); // Reset timeout RC
        return true;
    }
    return false;
}

// =========================================================
// CONTROL MODES
// =========================================================
void manualControl() {
    int servoAngle = ibusToServoAngle(channels[CH_SERVO]);
    setServoAngle(servo1, servoAngle);
    setServoAngle(servo2, 180 - servoAngle);

    int escPWM = throttleToESC(channels[CH_THROTTLE]);
    setESC1(escPWM);
    setESC2(escPWM);
}

void standbyControl() {
    setServoAngle(servo1, 90);
    setServoAngle(servo2, 90);
    stopESC();
}

void autoControl() {
    // Failsafe jika komando dari Jetson Orin / GCS terputus (>500ms)
    if (millis() - lastAutoCmd > AUTO_CMD_TIMEOUT) {
        setServoAngle(servo1, 90);
        setServoAngle(servo2, 90);
        stopESC();
        return;
    }

    setServoAngle(servo1, autoServoAngle);
    setServoAngle(servo2, 180 - autoServoAngle);
    setESC1(autoESC1us);
    setESC2(autoESC2us);
}

void handleMarkWP() {
    bool state = channels[CH_MARK_WP] > 1500;
    markWP = (state && !lastMarkWP);
    lastMarkWP = state;
}

void handleClearWP() {
    bool state = channels[CH_CLEAR_WP] > 1500;
    clearWP = (state && !lastClearWP);
    lastClearWP = state;
}

void sendRemoteData() {
    PC_SERIAL.print("REMOTE");
    for (int ch = 0; ch < IBUS_CHANNELS; ch++) {
        PC_SERIAL.print(",CH"); PC_SERIAL.print(ch + 1);
        PC_SERIAL.print("="); PC_SERIAL.print(channels[ch]);
    }
    PC_SERIAL.print(",SERVO="); PC_SERIAL.print(channels[CH_SERVO]);
    PC_SERIAL.print(",THROTTLE="); PC_SERIAL.print(channels[CH_THROTTLE]);
    PC_SERIAL.print(",MODE="); PC_SERIAL.print(modeName(currentMode));
    PC_SERIAL.print(",MARK="); PC_SERIAL.print(markWP ? 1 : 0);
    PC_SERIAL.print(",CLEAR="); PC_SERIAL.print(clearWP ? 1 : 0);
    PC_SERIAL.println();
}

void sendCompassData() {
    int16_t x, y, z;
    if (hmcReadRaw(x, y, z)) {
        float heading = calculateHeading(x, y);
        PC_SERIAL.print("COMPASS,HEADING="); PC_SERIAL.print(heading, 2);
        PC_SERIAL.print(",X="); PC_SERIAL.print(x);
        PC_SERIAL.print(",Y="); PC_SERIAL.print(y);
        PC_SERIAL.print(",Z="); PC_SERIAL.println(z);
    } else {
        PC_SERIAL.println("COMPASS,ERROR=READ_FAILED");
    }
}

// =========================================================
// SETUP
// =========================================================
void setup() {
    PC_SERIAL.begin(115200);
    delay(1000);

    IBUS_SERIAL.begin(115200);
    Wire.begin();

    servo1.attach(SERVO1_PIN, SERVO_MIN_US, SERVO_MAX_US);
    servo2.attach(SERVO2_PIN, SERVO_MIN_US, SERVO_MAX_US);
    esc1.attach(ESC1_PIN, ESC_MIN_US, ESC_MAX_US);
    esc2.attach(ESC2_PIN, ESC_MIN_US, ESC_MAX_US);

    setServoAngle(servo1, 90);
    setServoAngle(servo2, 90);
    stopESC();

    if (initHMC5883L()) PC_SERIAL.println("HMC5883L TERDETEKSI");
    else PC_SERIAL.println("HMC5883L TIDAK TERDETEKSI");

    lastIBUSPacket = millis();
    PC_SERIAL.println("STM32 REMOTE + COMPASS READY");
}

// =========================================================
// LOOP REFACTORED
// =========================================================
void loop() {
    readPCCommand();
    readIBUS();

    // Prioritas 1: Failsafe Remote RC (Jika sinyal RC terputus total)
    if (millis() - lastIBUSPacket > IBUS_TIMEOUT) {
        stopESC();
        setServoAngle(servo1, 90);
        setServoAngle(servo2, 90);
    } 
    // Operasi Normal
    else {
        currentMode = getMode();
        handleMarkWP();
        handleClearWP();

        if (currentMode == MODE_MANUAL) manualControl();
        else if (currentMode == MODE_STANDBY) standbyControl();
        else if (currentMode == MODE_AUTO) autoControl();

        sendRemoteData();
    }

    // Telemetri Kompas
    if (millis() - lastCompassSend >= COMPASS_INTERVAL) {
        lastCompassSend = millis();
        sendCompassData();
    }

    // Feedback motor setiap 150 ms (~6.7 Hz)
    if (millis() - lastMotorSend >= MOTOR_SEND_INTERVAL) {
        lastMotorSend = millis();
        sendMotorData();
    }
}