#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time

from video_stream import start_streaming, stop_streaming
from video_stream import capture_surface_photo, capture_underwater_photo

from gps import start_gps_reader, stop_gps_reader, get_gps_data


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
AUTO_CASE_DONE = 18   # selesai semua waypoint

auto_sub_case = AUTO_CASE_1
is_done_processed = False

WAYPOINT_1_HEADING  = 234.0
WAYPOINT_2_HEADING  = 197.0
WAYPOINT_3_HEADING  = 269.0 # isi sesuai kebutuhan
WAYPOINT_4_HEADING  = 224.0
WAYPOINT_5_HEADING  = 116.0
WAYPOINT_6_HEADING  = 110.0
WAYPOINT_7_HEADING  = 116.0
WAYPOINT_8_HEADING  = 42.0
WAYPOINT_9_HEADING  = 32.0
WAYPOINT_10_HEADING = 7.0
WAYPOINT_11_HEADING = 358.0
WAYPOINT_12_HEADING = 312.0
WAYPOINT_13_HEADING = 312.0
WAYPOINT_14_HEADING = 315.0
WAYPOINT_15_HEADING = 320.0
WAYPOINT_16_HEADING = 320.0
WAYPOINT_17_HEADING = 234.0

CASE_1_DURATION  = 5.0
CASE_2_DURATION  = 5.0
CASE_3_DURATION  = 5.0
CASE_4_DURATION  = 7.0
CASE_5_DURATION  = 5.0
CASE_6_DURATION  = 5.0
CASE_7_DURATION  = 4.0
CASE_8_DURATION  = 3.0
CASE_9_DURATION  = 5.0
CASE_10_DURATION = 4.0
CASE_11_DURATION = 4.0
CASE_12_DURATION = 5.0
CASE_13_DURATION = 5.0
CASE_14_DURATION = 5.0
CASE_15_DURATION = 5.0
CASE_16_DURATION = 6.0
CASE_17_DURATION = 6.0


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
# AUTO VALUE
# =========================================================

auto_servo = 90
auto_esc1 = 1700
auto_esc2 = 1700


# =========================================================
# KONTROL ARAH MOTOR PER CASE
# =========================================================

ESC_FORWARD_VALUE = 1700
ESC_REVERSE_VALUE = 1000   # sesuaikan sesuai kalibrasi ESC kapal

REVERSE_CASE_LABELS = ("CASE13", "CASE15")


# =========================================================
# PID RESET
# =========================================================

def reset_pid():
    global pid_integral
    global pid_previous_error
    global pid_previous_time

    pid_integral = 0.0
    pid_previous_error = 0.0
    pid_previous_time = None


# =========================================================
# SEND AUTO
# =========================================================

def send_auto(ser, servo, esc1, esc2):
    command = (
        f"AUTO,"
        f"SERVO={servo},"
        f"ESC1={esc1},"
        f"ESC2={esc2}\n"
    )

    try:
        ser.write(command.encode())
        print("TX:", command.strip())

    except serial.SerialException:
        print("ERROR: gagal mengirim data ke STM32")


# =========================================================
# HEADING ERROR
# =========================================================

def heading_error(target, actual):
    error = target - actual

    while error > 180:
        error -= 360

    while error < -180:
        error += 360

    return error


# =========================================================
# PID HEADING
# =========================================================

def calculate_pid(actual_heading):
    global pid_integral
    global pid_previous_error
    global pid_previous_time

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

    output = (
        Kp * error
        + Ki * pid_integral
        + Kd * derivative
    )

    servo = SERVO_CENTER + output
    servo = max(SERVO_MIN, min(SERVO_MAX, servo))
    servo = int(round(servo))

    return servo, error, output


# =========================================================
# BACA MODE DARI REMOTE
# =========================================================

def read_mode(line):
    global current_case
    global target_heading
    global auto_sub_case
    global case_start_time
    global is_done_processed

    if not line.startswith("REMOTE"):
        return

    if "MODE=AUTO" in line:
        if current_case != CASE_AUTO:
            current_case = CASE_AUTO
            reset_pid()
            target_heading = WAYPOINT_1_HEADING

            auto_sub_case = AUTO_CASE_1
            case_start_time = None
            is_done_processed = False

            start_streaming()

            print()
            print("==============================")
            print("MODE -> AUTO")
            print("CASE 1: koreksi heading ke waypoint 1")
            print("==============================")
            print()

    elif "MODE=MANUAL" in line:
        if current_case != CASE_MANUAL:
            current_case = CASE_MANUAL
            target_heading = None
            reset_pid()

            print()
            print("==============================")
            print("MODE -> MANUAL")
            print("Kontrol penuh oleh STM32")
            print("==============================")
            print()

    elif "MODE=STANDBY" in line:
        if current_case != CASE_MANUAL:
            current_case = CASE_MANUAL
            target_heading = None
            reset_pid()

            print()
            print("==============================")
            print("MODE -> STANDBY")
            print("==============================")
            print()


# =========================================================
# CAPTURE FOTO DI WAYPOINT
# =========================================================

def capture_waypoint_photo(case_label):
    if case_label not in CAPTURE_LABELS:
        return

    print()
    print("==============================")
    print(f"{case_label}: CAPTURE FOTO")
    print("==============================")

    # Perbaikan: disesuaikan dengan isi CAPTURE_LABELS
    if case_label == "CASE12" and foto1 == True:
        capture_underwater_photo()
    elif case_label == "CASE14" and foto2 == True:
        capture_surface_photo()


# =========================================================
# BACA HEADING & EKSEKUSI AUTO
# =========================================================

def run_case(ser, heading, duration_target, next_heading, next_case, case_label):
    global case_start_time
    global auto_sub_case
    global target_heading

    if case_start_time is None:
        case_start_time = time.monotonic()

        print()
        print("==============================")
        print(f"{case_label} MULAI, TARGET = {target_heading:.2f}")
        print("==============================")
        print()

    run_pid_case(ser, heading, case_label)

    elapsed = time.monotonic() - case_start_time
    durasi_foto = duration_target * 0.5
    if elapsed >= durasi_foto:
        capture_waypoint_photo(case_label)
    if elapsed > durasi_foto:
        foto1 = False
        foto2 = False
    if elapsed >= duration_target:
        auto_sub_case = next_case
        case_start_time = None
        target_heading = next_heading
        reset_pid()

        print()
        print("==============================")
        print(f"{case_label} SELESAI")
        if target_heading is not None:
            print(f"TARGET HEADING = {target_heading:.2f}")
        print("==============================")
        print()


def run_pid_case(ser, heading, case_label):
    global auto_servo
    global auto_esc1
    global auto_esc2

    servo, error, output = calculate_pid(heading)
    auto_servo = servo

    if case_label in REVERSE_CASE_LABELS:
        auto_esc1 = ESC_REVERSE_VALUE
        auto_esc2 = ESC_REVERSE_VALUE
    else:
        auto_esc1 = ESC_FORWARD_VALUE
        auto_esc2 = ESC_FORWARD_VALUE

    send_auto(ser, auto_servo, auto_esc1, auto_esc2)

    print(
        f"{case_label}"
#        f"TARGET = {target_heading:7.2f} | "
#        f"ERROR = {error:7.2f} | "
#        f"PID = {output:7.2f} | "
#        f"SERVO = {servo:3d}"
    )


def read_heading(line, ser):
    global heading
    global auto_sub_case
    global auto_servo
    global is_done_processed

    if not line.startswith("COMPASS"):
        return

    if "HEADING=" not in line:
        return

    try:
        data = line.split("HEADING=", 1)[1]
        data = data.split(",", 1)[0]
        heading = float(data)
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

    if auto_sub_case == AUTO_CASE_DONE:
        if not is_done_processed:
            auto_servo = 90
            send_auto(ser, auto_servo, 1500, 1500) # Stop ESC
            stop_streaming()
#            print(f"DONE | HEADING = {heading:7.2f}")
            is_done_processed = True


# =========================================================
# PROCESS DATA STM32
# =========================================================

def process_line(line, ser):
    if line.startswith("REMOTE"):
        read_mode(line)
        return

    if line.startswith("COMPASS"):
        read_heading(line, ser)
        return


# =========================================================
# MAIN
# =========================================================

def main():
    global current_case

    print()
    print("==========================================")
    print(" MINI PC - REMOTE / MANUAL / AUTO")
    print("==========================================")
    print(f"Port     : {PORT}")
    print(f"Baudrate : {BAUDRATE}")
    print()

    print("PID CONFIG")
    print(f"Kp = {Kp}")
    print(f"Ki = {Ki}")
    print(f"Kd = {Kd}")

    print()
    print(f"Servo range : {SERVO_MIN} - {SERVO_MAX}")
    print(f"Servo center: {SERVO_CENTER}")
    print()

    ser = None

    try:
        print(f"Membuka serial {PORT}...")

        ser = serial.Serial(
            PORT,
            BAUDRATE,
            timeout=0.05
        )

        # Mengaktifkan DTR/RTS untuk memicu transmisi USB CDC STM32
        ser.dtr = True
        ser.rts = True

        print("Serial berhasil dibuka.")

        time.sleep(2)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        current_case = CASE_MANUAL
        target_heading = None
        reset_pid()

        print()
        print("STM32 TERHUBUNG")
        print("Monitoring mode...")
        print()

        print("CASE 0 = MANUAL")
        print("CASE 1 = AUTO")
        print()

        print("Membuka GPS reader (background thread)...")
        start_gps_reader()
        print()

        while True:
            while ser.in_waiting:
                line = ser.readline().decode(
                    "utf-8",
                    errors="ignore"
                ).strip()

                if not line:
                    continue

                if not line.startswith("REMOTE"):
                    print("RX:", repr(line))

                process_line(line, ser)

            time.sleep(0.01)

    except KeyboardInterrupt:
        print()
        print("==========================================")
        print(" CTRL+C TERDETEKSI")
        print(" Menghentikan program...")
        print("==========================================")

    except serial.SerialException as e:
        print()
        print("ERROR SERIAL:")
        print(e)

    except Exception as e:
        print()
        print("ERROR PROGRAM:")
        print(e)

    finally:
        print()
        print("==========================================")
        print(" CLEANUP")
        print("==========================================")

        try:
            print("Menghentikan camera streaming...")
            stop_streaming()
            print("Camera streaming dihentikan.")
        except Exception as e:
            print(f"WARNING: gagal menghentikan streaming: {e}")

        try:
            print("Menghentikan GPS reader...")
            stop_gps_reader()
            print("GPS reader dihentikan.")
        except Exception as e:
            print(f"WARNING: gagal menghentikan GPS reader: {e}")

        if ser is not None:
            try:
                if ser.is_open:
                    print(f"Menutup serial {PORT}...")
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()
                    ser.close()
                    print(f"Serial {PORT} berhasil ditutup.")
            except Exception as e:
                print(f"WARNING: gagal menutup serial: {e}")

        print()
        print("Program selesai.")
        print("Serial dan kamera sudah dibersihkan.")
        print()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()