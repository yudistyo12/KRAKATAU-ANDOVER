#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time
import threading

from video_stream import (
    start_streaming,
    stop_streaming,
    start_web_server,
    is_gcs_active,
    reset_heartbeat,
    capture_surface_photo,
    capture_underwater_photo
)
from gps import start_gps_reader, stop_gps_reader, get_gps_data, set_heading
from motor_state import set_motor_data


# =========================================================
# CONFIG
# =========================================================

PORT = "/dev/ttyACM0"
BAUDRATE = 115200


# =========================================================
# CASE
# =========================================================

CASE_MANUAL = 0
CASE_AUTO = 1

current_case = CASE_MANUAL

foto1 = True
foto2 = True
prev_failsafe_state = False
has_printed_initial_rc = False

# Tracker Waktu & Error Kompas
last_compass_recv_time = time.time()
last_compass_err_print = 0.0

# =========================================================
# MOTOR FEEDBACK DARI STM32
# =========================================================
motor_data = {
    "left_rpm": 0.0,
    "right_rpm": 0.0,
    "speed_mps": 0.0,
    "direction": "STOP",
    "updated_at": 0.0,
}


# =========================================================
# AUTO SUB-CASE
# =========================================================

AUTO_CASE_1  = 1
AUTO_CASE_2  = 2
AUTO_CASE_3  = 3
AUTO_CASE_4  = 4
AUTO_CASE_5  = 5
AUTO_CASE_6  = 6
AUTO_CASE_7  = 7
AUTO_CASE_8  = 8
AUTO_CASE_9  = 9
AUTO_CASE_10 = 10
AUTO_CASE_11 = 11
AUTO_CASE_12 = 12
AUTO_CASE_13 = 13
AUTO_CASE_14 = 14
AUTO_CASE_15 = 15
AUTO_CASE_16 = 16
AUTO_CASE_17 = 17
AUTO_CASE_DONE = 18

auto_sub_case = AUTO_CASE_1
is_done_processed = False

WAYPOINT_1_HEADING  = 239.0
WAYPOINT_2_HEADING  = 210.0
WAYPOINT_3_HEADING  = 254.0
WAYPOINT_4_HEADING  = 230.0
WAYPOINT_5_HEADING  = 112.0
WAYPOINT_6_HEADING  = 117.0
WAYPOINT_7_HEADING  = 117.0
WAYPOINT_8_HEADING  = 117.0
WAYPOINT_9_HEADING  = 25.0
WAYPOINT_10_HEADING = 15.0
WAYPOINT_11_HEADING = 358.0
WAYPOINT_12_HEADING = 311.0
WAYPOINT_13_HEADING = 314.0
WAYPOINT_14_HEADING = 326.0
WAYPOINT_15_HEADING = 314.0
WAYPOINT_16_HEADING = 314.0
WAYPOINT_17_HEADING = 314.0

CASE_1_DURATION  = 5.0
CASE_2_DURATION  = 5.0
CASE_3_DURATION  = 5.0
CASE_4_DURATION  = 5.0
CASE_5_DURATION  = 5.0
CASE_6_DURATION  = 4.0
CASE_7_DURATION  = 4.0
CASE_8_DURATION  = 2.500
CASE_9_DURATION  = 6.0
CASE_10_DURATION = 3.0
CASE_11_DURATION = 5.0
CASE_12_DURATION = 7.0
CASE_13_DURATION = 3.0
CASE_14_DURATION = 2.0
CASE_15_DURATION = 3.0
CASE_16_DURATION = 5.0
CASE_17_DURATION = 5.0

case_start_time = None

# =========================================================
# WAYPOINT CAPTURE FOTO
# =========================================================

CAPTURE_LABELS = ("CASE12", "CASE14")


# =========================================================
# HEADING
# =========================================================

heading = None
target_heading = None


# =========================================================
# PID CONFIG
# =========================================================

Kp = 0.8
Ki = 0.02
Kd = 0.15

pid_integral = 0.0
pid_previous_error = 0.0
pid_previous_time = None

PID_INTEGRAL_LIMIT = 100.0


# =========================================================
# SERVO CONFIG
# =========================================================

SERVO_CENTER = 90
SERVO_MIN = 45
SERVO_MAX = 180


# =========================================================
# AUTO VALUE & ESC DIRECTION
# =========================================================

auto_servo = 90
auto_esc1 = 1700
auto_esc2 = 1700

ESC_FORWARD_VALUE = 1700
ESC_REVERSE_VALUE = 1000

REVERSE_CASE_LABELS = ("CASE13", "CASE15")


# =========================================================
# PID RESET
# =========================================================

def reset_pid():
    global pid_integral, pid_previous_error, pid_previous_time
    pid_integral = 0.0
    pid_previous_error = 0.0
    pid_previous_time = None


# =========================================================
# SEND AUTO (TERPROTEKSI FAILSAFE)
# =========================================================

def send_auto(ser, servo, esc1, esc2, case_label="AUTO"):
    global prev_failsafe_state

    # 1. Cek Sinyal GCS (Toleransi 4.0 detik)
    if not is_gcs_active(timeout=4.0):
        if not prev_failsafe_state:
            print("\n[FAILSAFE ACTIVE] Web GCS terputus! Menghentikan transmisi AUTO...")
            prev_failsafe_state = True
        return

    # 2. Cek apakah data kompas valid baru masuk (Toleransi 1.5 detik)
    if time.time() - last_compass_recv_time > 1.5:
        if not prev_failsafe_state:
            print("\n[FAILSAFE ACTIVE] Kompas READ_FAILED / Timeout! Menghentikan transmisi AUTO...")
            prev_failsafe_state = True
        return

    if prev_failsafe_state:
        print("\n[FAILSAFE CLEARED] Sensor & GCS Normal. Melanjutkan AUTO.")
        prev_failsafe_state = False

    command = f"AUTO,SERVO={servo},ESC1={esc1},ESC2={esc2}\n"
    try:
        ser.write(command.encode())
        print(f"TX [{case_label}]:", command.strip())
    except serial.SerialException:
        print("ERROR: gagal mengirim data ke STM32")


# =========================================================
# HEADING ERROR & PID
# =========================================================

def heading_error(target, actual):
    error = target - actual
    while error > 180: error -= 360
    while error < -180: error += 360
    return error


def calculate_pid(actual_heading):
    global pid_integral, pid_previous_error, pid_previous_time

    now = time.monotonic()
    error = heading_error(target_heading, actual_heading)

    if pid_previous_time is None:
        dt = 0.01
    else:
        dt = now - pid_previous_time
        if dt <= 0:
            dt = 0.01

    pid_previous_time = now
    pid_integral += error * dt

    if pid_integral > PID_INTEGRAL_LIMIT:
        pid_integral = PID_INTEGRAL_LIMIT
    elif pid_integral < -PID_INTEGRAL_LIMIT:
        pid_integral = -PID_INTEGRAL_LIMIT

    derivative = (error - pid_previous_error) / dt
    pid_previous_error = error

    output = (Kp * error) + (Ki * pid_integral) + (Kd * derivative)
    servo = SERVO_CENTER + output
    servo = max(SERVO_MIN, min(SERVO_MAX, servo))
    servo = int(round(servo))

    return servo, error, output


# =========================================================
# BACA MODE DARI REMOTE
# =========================================================

def read_mode(line):
    global current_case, target_heading, auto_sub_case, case_start_time, is_done_processed, pid_previous_error

    if "MODE=AUTO" in line:
        if current_case != CASE_AUTO:
            current_case = CASE_AUTO
            reset_pid()
            reset_heartbeat()
            target_heading = WAYPOINT_1_HEADING
            auto_sub_case = AUTO_CASE_1
            case_start_time = None
            is_done_processed = False

            if heading is not None:
                pid_previous_error = heading_error(target_heading, heading)

            threading.Thread(target=start_streaming, daemon=True).start()

            print("\n==============================")
            print("MODE -> AUTO")
            print("CASE 1: koreksi heading ke waypoint 1")
            print("==============================\n")

    elif "MODE=MANUAL" in line:
        if current_case != CASE_MANUAL:
            current_case = CASE_MANUAL
            target_heading = None
            reset_pid()

            print("\n==============================")
            print("MODE -> MANUAL")
            print("Kontrol penuh oleh STM32")
            print("==============================\n")

    elif "MODE=STANDBY" in line:
        if current_case != CASE_MANUAL:
            current_case = CASE_MANUAL
            target_heading = None
            reset_pid()

            print("\n==============================")
            print("MODE -> STANDBY")
            print("==============================\n")


# =========================================================
# CAPTURE FOTO DI WAYPOINT
# =========================================================

def capture_waypoint_photo(case_label):
    global foto1, foto2
    if case_label not in CAPTURE_LABELS:
        return

    if case_label == "CASE12" and foto1:
        print("\n==============================")
        print(f"{case_label}: CAPTURE FOTO UNDERWATER")
        print("==============================\n")
        capture_underwater_photo()
        foto1 = False

    elif case_label == "CASE14" and foto2:
        print("\n==============================")
        print(f"{case_label}: CAPTURE FOTO SURFACE")
        print("==============================\n")
        capture_surface_photo()
        foto2 = False


# =========================================================
# EKSEKUSI PID WAYPOINT CASE
# =========================================================

def run_case(ser, heading, duration_target, next_heading, next_case, case_label):
    global case_start_time, auto_sub_case, target_heading, pid_previous_error

    if case_start_time is None:
        case_start_time = time.monotonic()
        print("\n==============================")
        print(f"{case_label} MULAI, TARGET = {target_heading:.2f}")
        print("==============================\n")

    run_pid_case(ser, heading, case_label)

    elapsed = time.monotonic() - case_start_time
    durasi_foto = duration_target * 0.5
    
    if elapsed >= durasi_foto:
        capture_waypoint_photo(case_label)

    if elapsed >= duration_target:
        auto_sub_case = next_case
        case_start_time = None
        target_heading = next_heading
        reset_pid()

        if target_heading is not None:
            pid_previous_error = heading_error(target_heading, heading)

        print("\n==============================")
        print(f"{case_label} SELESAI")
        if target_heading is not None:
            print(f"TARGET HEADING = {target_heading:.2f}")
        print("==============================\n")


def run_pid_case(ser, heading, case_label):
    global auto_servo, auto_esc1, auto_esc2

    servo, error, output = calculate_pid(heading)
    auto_servo = servo

    if case_label in REVERSE_CASE_LABELS:
        auto_esc1 = ESC_REVERSE_VALUE
        auto_esc2 = ESC_REVERSE_VALUE
    else:
        auto_esc1 = ESC_FORWARD_VALUE
        auto_esc2 = ESC_FORWARD_VALUE

    send_auto(ser, auto_servo, auto_esc1, auto_esc2, case_label)


def read_heading(line, ser):
    global heading, auto_sub_case, auto_servo, is_done_processed, last_compass_recv_time

    if "HEADING=" not in line:
        return

    try:
        data = line.split("HEADING=", 1)[1].split(",", 1)[0]
        heading = float(data)
        last_compass_recv_time = time.time()  # Perbarui waktu data kompas valid
        set_heading(heading)
    except ValueError:
        return

    if current_case != CASE_AUTO:
        return

    CASE_CHAIN = [
        (AUTO_CASE_1,  CASE_1_DURATION,  WAYPOINT_2_HEADING,  AUTO_CASE_2,  "CASE1"),
        (AUTO_CASE_2,  CASE_2_DURATION,  WAYPOINT_3_HEADING,  AUTO_CASE_3,  "CASE2"),
        (AUTO_CASE_3,  CASE_3_DURATION,  WAYPOINT_4_HEADING,  AUTO_CASE_4,  "CASE3"),
        (AUTO_CASE_4,  CASE_4_DURATION,  WAYPOINT_5_HEADING,  AUTO_CASE_5,  "CASE4"),
        (AUTO_CASE_5,  CASE_5_DURATION,  WAYPOINT_6_HEADING,  AUTO_CASE_6,  "CASE5"),
        (AUTO_CASE_6,  CASE_6_DURATION,  WAYPOINT_7_HEADING,  AUTO_CASE_7,  "CASE6"),
        (AUTO_CASE_7,  CASE_7_DURATION,  WAYPOINT_8_HEADING,  AUTO_CASE_8,  "CASE7"),
        (AUTO_CASE_8,  CASE_8_DURATION,  WAYPOINT_9_HEADING,  AUTO_CASE_9,  "CASE8"),
        (AUTO_CASE_9,  CASE_9_DURATION,  WAYPOINT_10_HEADING, AUTO_CASE_10, "CASE9"),
        (AUTO_CASE_10, CASE_10_DURATION, WAYPOINT_11_HEADING, AUTO_CASE_11, "CASE10"),
        (AUTO_CASE_11, CASE_11_DURATION, WAYPOINT_12_HEADING, AUTO_CASE_12, "CASE11"),
        (AUTO_CASE_12, CASE_12_DURATION, WAYPOINT_13_HEADING, AUTO_CASE_13, "CASE12"),
        (AUTO_CASE_13, CASE_13_DURATION, WAYPOINT_14_HEADING, AUTO_CASE_14, "CASE13"),
        (AUTO_CASE_14, CASE_14_DURATION, WAYPOINT_15_HEADING, AUTO_CASE_15, "CASE14"),
        (AUTO_CASE_15, CASE_15_DURATION, WAYPOINT_16_HEADING, AUTO_CASE_16, "CASE15"),
        (AUTO_CASE_16, CASE_16_DURATION, WAYPOINT_17_HEADING, AUTO_CASE_17, "CASE16"),
        (AUTO_CASE_17, CASE_17_DURATION, None,                AUTO_CASE_DONE, "CASE17"),
    ]

    for case_id, duration, next_heading, next_case, label in CASE_CHAIN:
        if auto_sub_case == case_id:
            run_case(ser, heading, duration, next_heading, next_case, label)
            return

    if auto_sub_case == AUTO_CASE_DONE and not is_done_processed:
        auto_servo = 90
        send_auto(ser, auto_servo, 1500, 1500, "DONE")
        stop_streaming()
        is_done_processed = True


# =========================================================
# PARSE MOTOR FEEDBACK DARI STM32
# =========================================================
def read_motor_feedback(line):
    global motor_data

    if not line.startswith("MOTOR,"):
        return False

    try:
        fields = {}
        for item in line.strip().split(",")[1:]:
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            fields[key.strip()] = value.strip()

        direction = fields.get("DIRECTION", "STOP").upper()
        if direction not in ("FORWARD", "REVERSE", "STOP"):
            direction = "STOP"

        motor_data = {
            "left_rpm": float(fields.get("LEFT_RPM", 0.0)),
            "right_rpm": float(fields.get("RIGHT_RPM", 0.0)),
            "speed_mps": float(fields.get("SPEED_MPS", 0.0)),
            "direction": direction,
            "updated_at": time.time(),
        }
        set_motor_data(
            motor_data["left_rpm"],
            motor_data["right_rpm"],
            motor_data["speed_mps"],
            motor_data["direction"]
        )

        print(
            f"RX MOTOR: L={motor_data['left_rpm']:.0f} RPM | "
            f"R={motor_data['right_rpm']:.0f} RPM | "
            f"SPEED={motor_data['speed_mps']:.2f} m/s | "
            f"DIR={motor_data['direction']}"
        )
        return True

    except (ValueError, TypeError) as e:
        print(f"[MOTOR PARSE ERROR] {e} | RAW={line!r}")
        return False


# =========================================================
# MAIN LOOP
# =========================================================

def main():
    global current_case, has_printed_initial_rc, last_compass_err_print

    print("\n==========================================")
    print(" MINI PC - REMOTE / MANUAL / AUTO")
    print("==========================================")
    print(f"Port     : {PORT}")
    print(f"Baudrate : {BAUDRATE}\n")

    print(f"PID Config: Kp={Kp}, Ki={Ki}, Kd={Kd}")
    print(f"Servo range : {SERVO_MIN} - {SERVO_MAX} (Center: {SERVO_CENTER})\n")

    ser = None

    try:
        print("Membuka GPS reader (background thread)...")
        start_gps_reader()
        start_web_server()

        print(f"Membuka serial {PORT}...")
        ser = serial.Serial(PORT, BAUDRATE, timeout=0.05)
        ser.dtr = True
        ser.rts = True
        print("Serial berhasil dibuka.")

        time.sleep(2)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        current_case = CASE_MANUAL
        reset_pid()

        print("\nSTM32 TERHUBUNG\nMonitoring mode...\nCASE 0 = MANUAL\nCASE 1 = AUTO\n")

        while True:
            while ser.in_waiting:
                line = ser.readline().decode("utf-8", errors="ignore").strip()

                if not line:
                    continue

                # 1. Parsing Status REMOTE
                if "MODE=" in line:
                    if not has_printed_initial_rc:
                        print(f"[RC INIT] Status Remote Awal: {line}")
                        has_printed_initial_rc = True
                    read_mode(line)

                # 2. Parsing Nilai Heading Normal
                elif "HEADING=" in line:
                    print("RX:", repr(line))
                    read_heading(line, ser)

                # 3. Feedback motor periodik dari STM32
                elif line.startswith("MOTOR,"):
                    read_motor_feedback(line)

                # 4. Tangani Error Kompas STM32 (READ_FAILED / ERROR) dengan Pembatas Waktu
                elif "COMPASS" in line and "ERROR" in line:
                    now = time.time()
                    if now - last_compass_err_print >= 1.0:  # Cetak maksimal 1x per detik
                        print("RX:", repr(line), "<-- [PERINGATAN: Hardware I2C / Kompas Bermasalah]")
                        last_compass_err_print = now

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n==========================================\n CTRL+C TERDETEKSI\n Menghentikan program...\n==========================================")

    except Exception as e:
        print("\nERROR PROGRAM:", e)

    finally:
        print("\n==========================================\n CLEANUP\n==========================================")
        try:
            stop_streaming()
        except Exception:
            pass
        try:
            stop_gps_reader()
        except Exception:
            pass
        if ser is not None and ser.is_open:
            ser.close()
        print("Program selesai dan hardware di-release.\n")


if __name__ == "__main__":
    main()