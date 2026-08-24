#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time
import threading

from video_stream import (
    start_streaming,
    stop_streaming,
    start_web_server
)
from video_stream import capture_surface_photo, capture_underwater_photo
from gps import start_gps_reader, stop_gps_reader, get_gps_data, set_heading


# =========================================================
# CONFIG & FAILSAFE WEB GCS
# =========================================================
PORT = "/dev/ttyACM0"
BAUDRATE = 115200

last_gcs_heartbeat = time.time()
GCS_TIMEOUT = 1.5  # Batas toleransi sinyal Web terputus (1.5 detik)
is_gcs_connected = True

def update_gcs_heartbeat():
    """Panggil fungsi ini saat web frontend mengirim ping"""
    global last_gcs_heartbeat, is_gcs_connected
    last_gcs_heartbeat = time.time()
    is_gcs_connected = True

def monitor_gcs_failsafe():
    """Thread background untuk mendeteksi hilangnya sinyal Web/GCS"""
    global is_gcs_connected
    while True:
        if time.time() - last_gcs_heartbeat > GCS_TIMEOUT:
            if is_gcs_connected:
                print("\n[WARNING] WEB GCS DISCONNECTED! Stopping Auto Commands...")
                is_gcs_connected = False
        time.sleep(0.1)

# Jalankan monitoring thread GCS
threading.Thread(target=monitor_gcs_failsafe, daemon=True).start()


# =========================================================
# CASE & AUTO WAYPOINTS
# =========================================================
CASE_MANUAL = 0
CASE_AUTO = 1
current_case = CASE_MANUAL

foto1 = True
foto2 = True

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
CAPTURE_LABELS = ("CASE12", "CASE14")

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

SERVO_CENTER = 90
SERVO_MIN = 45
SERVO_MAX = 180

auto_servo = 90
auto_esc1 = 1700
auto_esc2 = 1700

ESC_FORWARD_VALUE = 1700
ESC_REVERSE_VALUE = 1000
REVERSE_CASE_LABELS = ("CASE13", "CASE15")


def reset_pid():
    global pid_integral, pid_previous_error, pid_previous_time
    pid_integral = 0.0
    pid_previous_error = 0.0
    pid_previous_time = None


# =========================================================
# SEND AUTO (TERPROTEKSI GCS FAILSAFE)
# =========================================================
def send_auto(ser, servo, esc1, esc2):
    # Jika Web GCS terputus, hentikan pengiriman serial ke STM32
    if not is_gcs_connected:
        print("FAILSAFE ACTIVE: Menghentikan transmisi AUTO ke STM32")
        return

    command = f"AUTO,SERVO={servo},ESC1={esc1},ESC2={esc2}\n"
    try:
        ser.write(command.encode())
        print("TX:", command.strip())
    except serial.SerialException:
        print("ERROR: gagal mengirim data ke STM32")


def heading_error(target, actual):
    error = target - actual
    while error > 180: error -= 360
    while error < -180: error += 360
    return error


def calculate_pid(actual_heading):
    global pid_integral, pid_previous_error, pid_previous_time
    now = time.monotonic()
    error = heading_error(target_heading, actual_heading)

    dt = 0.01 if pid_previous_time is None else (now - pid_previous_time)
    if dt <= 0: dt = 0.01

    pid_previous_time = now
    pid_integral += error * dt
    pid_integral = max(-PID_INTEGRAL_LIMIT, min(PID_INTEGRAL_LIMIT, pid_integral))

    derivative = (error - pid_previous_error) / dt
    pid_previous_error = error

    output = (Kp * error) + (Ki * pid_integral) + (Kd * derivative)
    servo = SERVO_CENTER + output
    servo = max(SERVO_MIN, min(SERVO_MAX, servo))

    return int(round(servo)), error, output


def read_mode(line):
    global current_case, target_heading, auto_sub_case, case_start_time, is_done_processed
    if not line.startswith("REMOTE"): return

    if "MODE=AUTO" in line:
        if current_case != CASE_AUTO:
            current_case = CASE_AUTO
            reset_pid()
            target_heading = WAYPOINT_1_HEADING
            auto_sub_case = AUTO_CASE_1
            case_start_time = None
            is_done_processed = False
            start_streaming()

            print("\n==============================\nMODE -> AUTO\n==============================\n")

    elif "MODE=MANUAL" in line or "MODE=STANDBY" in line:
        if current_case != CASE_MANUAL:
            current_case = CASE_MANUAL
            target_heading = None
            reset_pid()
            print(f"\n==============================\nMODE -> {line.split('MODE=')[1].split(',')[0]}\n==============================\n")


def capture_waypoint_photo(case_label):
    global foto1, foto2
    if case_label not in CAPTURE_LABELS: return
    if case_label == "CASE12" and foto1:
        capture_underwater_photo()
        foto1 = False
    elif case_label == "CASE14" and foto2:
        capture_surface_photo()
        foto2 = False


def run_case(ser, heading, duration_target, next_heading, next_case, case_label):
    global case_start_time, auto_sub_case, target_heading
    if case_start_time is None:
        case_start_time = time.monotonic()

    run_pid_case(ser, heading, case_label)

    elapsed = time.monotonic() - case_start_time
    if elapsed >= (duration_target * 0.5):
        capture_waypoint_photo(case_label)

    if elapsed >= duration_target:
        auto_sub_case = next_case
        case_start_time = None
        target_heading = next_heading
        reset_pid()


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

    send_auto(ser, auto_servo, auto_esc1, auto_esc2)


def read_heading(line, ser):
    global heading, auto_sub_case, auto_servo, is_done_processed
    if not line.startswith("COMPASS") or "HEADING=" not in line: return

    try:
        data = line.split("HEADING=", 1)[1].split(",", 1)[0]
        heading = float(data)
        set_heading(heading)
    except ValueError:
        return

    if current_case != CASE_AUTO: return

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
        send_auto(ser, auto_servo, 1500, 1500)
        stop_streaming()
        is_done_processed = True


def process_line(line, ser):
    if line.startswith("REMOTE"): read_mode(line)
    elif line.startswith("COMPASS"): read_heading(line, ser)


# =========================================================
# MAIN LOOP
# =========================================================
def main():
    global current_case
    ser = None

    try:
        start_gps_reader()
        start_web_server()

        ser = serial.Serial(PORT, BAUDRATE, timeout=0.05)
        ser.dtr = True
        ser.rts = True
        time.sleep(2)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        current_case = CASE_MANUAL
        reset_pid()

        print("\nSTM32 & GCS MONITORING READY...\n")

        while True:
            while ser.in_waiting:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if line:
                    process_line(line, ser)
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nProgram Dihentikan Pengguna.")
    finally:
        stop_streaming()
        stop_gps_reader()
        if ser and ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()