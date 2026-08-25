#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time
import threading
import os

from video_stream import (
    start_streaming,
    stop_streaming,
    is_gcs_active,
    reset_heartbeat,
    capture_surface_photo,
    capture_underwater_photo
)

from gps import (
    start_gps_reader,
    stop_gps_reader,
    get_gps_data,
    set_heading
)

from motor_state import set_motor_data


# =========================================================
# CONFIG SERIAL STM32
# =========================================================

PORT = os.getenv("STM32_DEVICE", "/dev/ttyACM0")
BAUDRATE = 115200


# =========================================================
# CASE
# =========================================================

CASE_MANUAL = 0
CASE_AUTO = 1

current_case = CASE_MANUAL


# =========================================================
# FOTO
# =========================================================

foto1 = True
foto2 = True


# =========================================================
# FAILSAFE
# =========================================================

prev_failsafe_state = False
has_printed_initial_rc = False

last_compass_recv_time = time.time()
last_compass_err_print = 0.0


# =========================================================
# AUTO SUB CASE
# =========================================================

AUTO_CASE_1 = 1
AUTO_CASE_2 = 2
AUTO_CASE_3 = 3
AUTO_CASE_4 = 4
AUTO_CASE_5 = 5
AUTO_CASE_6 = 6
AUTO_CASE_7 = 7
AUTO_CASE_8 = 8
AUTO_CASE_9 = 9
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


# =========================================================
# WAYPOINT HEADING
# =========================================================

WAYPOINT_1_HEADING = 234.0
WAYPOINT_2_HEADING = 197.0
WAYPOINT_3_HEADING = 269.0
WAYPOINT_4_HEADING = 224.0
WAYPOINT_5_HEADING = 116.0
WAYPOINT_6_HEADING = 110.0
WAYPOINT_7_HEADING = 116.0
WAYPOINT_8_HEADING = 42.0
WAYPOINT_9_HEADING = 32.0
WAYPOINT_10_HEADING = 7.0
WAYPOINT_11_HEADING = 358.0
WAYPOINT_12_HEADING = 312.0
WAYPOINT_13_HEADING = 312.0
WAYPOINT_14_HEADING = 315.0
WAYPOINT_15_HEADING = 320.0
WAYPOINT_16_HEADING = 320.0
WAYPOINT_17_HEADING = 234.0


# =========================================================
# DURASI CASE
# =========================================================

CASE_1_DURATION = 5.0
CASE_2_DURATION = 5.0
CASE_3_DURATION = 5.0
CASE_4_DURATION = 7.0
CASE_5_DURATION = 5.0
CASE_6_DURATION = 5.0
CASE_7_DURATION = 4.0
CASE_8_DURATION = 3.0
CASE_9_DURATION = 5.0
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
# FOTO WAYPOINT
# =========================================================

CAPTURE_LABELS = (
    "CASE12",
    "CASE14"
)


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
# ESC
# =========================================================

ESC_FORWARD_VALUE = 1700
ESC_REVERSE_VALUE = 1000

REVERSE_CASE_LABELS = (
    "CASE13",
    "CASE15"
)


# =========================================================
# RESET PID
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

def send_auto(
    ser,
    servo,
    esc1,
    esc2,
    case_label="AUTO"
):

    global prev_failsafe_state
    global last_compass_recv_time

    # -----------------------------------------------------
    # FAILSAFE GCS
    # -----------------------------------------------------

    if not is_gcs_active(timeout=4.0):

        if not prev_failsafe_state:

            print()
            print(
                "[FAILSAFE ACTIVE] "
                "GCS heartbeat timeout."
            )

            print(
                "AUTO tidak dikirim ke STM32."
            )

            prev_failsafe_state = True

        return False


    # -----------------------------------------------------
    # FAILSAFE KOMPAS
    # -----------------------------------------------------

    if time.time() - last_compass_recv_time > 1.5:

        if not prev_failsafe_state:

            print()
            print(
                "[FAILSAFE ACTIVE] "
                "Kompas timeout."
            )

            print(
                "AUTO tidak dikirim ke STM32."
            )

            prev_failsafe_state = True

        return False


    # -----------------------------------------------------
    # FAILSAFE CLEAR
    # -----------------------------------------------------

    if prev_failsafe_state:

        print()
        print(
            "[FAILSAFE CLEARED] "
            "GCS dan kompas normal."
        )

        prev_failsafe_state = False


    # -----------------------------------------------------
    # KIRIM COMMAND
    # -----------------------------------------------------

    command = (
        f"AUTO,"
        f"SERVO={int(servo)},"
        f"ESC1={int(esc1)},"
        f"ESC2={int(esc2)}\n"
    )

    try:

        ser.write(command.encode("utf-8"))

        print(
            f"TX [{case_label}]: "
            f"{command.strip()}"
        )

        return True

    except serial.SerialException as e:

        print(
            "ERROR: gagal mengirim "
            f"AUTO ke STM32: {e}"
        )

        return False


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

    if target_heading is None:

        return (
            SERVO_CENTER,
            0.0,
            0.0
        )


    now = time.monotonic()

    error = heading_error(
        target_heading,
        actual_heading
    )


    if pid_previous_time is None:

        dt = 0.01

    else:

        dt = now - pid_previous_time

        if dt <= 0:

            dt = 0.01


    pid_previous_time = now


    # -----------------------------------------------------
    # INTEGRAL
    # -----------------------------------------------------

    pid_integral += error * dt

    pid_integral = max(
        -PID_INTEGRAL_LIMIT,
        min(
            PID_INTEGRAL_LIMIT,
            pid_integral
        )
    )


    # -----------------------------------------------------
    # DERIVATIVE
    # -----------------------------------------------------

    derivative = (
        error - pid_previous_error
    ) / dt

    pid_previous_error = error


    # -----------------------------------------------------
    # PID OUTPUT
    # -----------------------------------------------------

    output = (
        Kp * error
        + Ki * pid_integral
        + Kd * derivative
    )


    servo = (
        SERVO_CENTER
        + output
    )


    servo = max(
        SERVO_MIN,
        min(
            SERVO_MAX,
            servo
        )
    )

    servo = int(
        round(servo)
    )


    return (
        servo,
        error,
        output
    )


# =========================================================
# BACA MODE REMOTE
# =========================================================

def read_mode(line):

    global current_case
    global target_heading
    global auto_sub_case
    global case_start_time
    global is_done_processed
    global foto1
    global foto2
    global pid_previous_error


    if not line.startswith("REMOTE"):

        return


    # =====================================================
    # AUTO
    # =====================================================

    if "MODE=AUTO" in line:

        if current_case != CASE_AUTO:

            current_case = CASE_AUTO

            reset_pid()

            reset_heartbeat()

            target_heading = (
                WAYPOINT_1_HEADING
            )

            auto_sub_case = (
                AUTO_CASE_1
            )

            case_start_time = None

            is_done_processed = False

            # Reset foto
            foto1 = True
            foto2 = True


            if heading is not None:

                pid_previous_error = (
                    heading_error(
                        target_heading,
                        heading
                    )
                )


            print()
            print(
                "=============================="
            )
            print(
                "MODE -> AUTO"
            )
            print(
                "CASE 1: heading waypoint 1"
            )
            print(
                "=============================="
            )
            print()


    # =====================================================
    # MANUAL
    # =====================================================

    elif "MODE=MANUAL" in line:

        if current_case != CASE_MANUAL:

            current_case = CASE_MANUAL

            target_heading = None

            reset_pid()


            print()
            print(
                "=============================="
            )
            print(
                "MODE -> MANUAL"
            )
            print(
                "Kontrol penuh oleh STM32"
            )
            print(
                "=============================="
            )
            print()


    # =====================================================
    # STANDBY
    # =====================================================

    elif "MODE=STANDBY" in line:

        if current_case != CASE_MANUAL:

            current_case = CASE_MANUAL

            target_heading = None

            reset_pid()


            print()
            print(
                "=============================="
            )
            print(
                "MODE -> STANDBY"
            )
            print(
                "=============================="
            )
            print()


# =========================================================
# CAPTURE FOTO
# =========================================================

def capture_waypoint_photo(case_label):

    global foto1
    global foto2


    if case_label == "CASE12":

        if foto1:

            print()
            print(
                "=============================="
            )
            print(
                "CASE12: CAPTURE UNDERWATER"
            )
            print(
                "=============================="
            )

            filename = None
            try:

                filename = (
                    capture_underwater_photo()
                )

                if filename is None:
                    print(
                        "Foto underwater belum berhasil disimpan; "
                        "akan dicoba lagi."
                    )
                    return

                print(
                    f"Foto underwater: "
                    f"{filename}"
                )

            except Exception as e:

                print(
                    "ERROR capture "
                    f"underwater: {e}"
                )

            foto1 = True
            if filename is not None:
                foto1 = False


    elif case_label == "CASE14":

        if foto2:

            print()
            print(
                "=============================="
            )
            print(
                "CASE14: CAPTURE SURFACE"
            )
            print(
                "=============================="
            )

            filename = None
            try:

                filename = (
                    capture_surface_photo()
                )

                if filename is None:
                    print(
                        "Foto surface belum berhasil disimpan; "
                        "akan dicoba lagi."
                    )
                    return

                print(
                    f"Foto surface: "
                    f"{filename}"
                )

            except Exception as e:

                print(
                    "ERROR capture "
                    f"surface: {e}"
                )

            foto2 = True
            if filename is not None:
                foto2 = False


# =========================================================
# RUN PID CASE
# =========================================================

def run_pid_case(
    ser,
    actual_heading,
    case_label
):

    global auto_servo
    global auto_esc1
    global auto_esc2


    servo, error, output = (
        calculate_pid(
            actual_heading
        )
    )


    auto_servo = servo


    # -----------------------------------------------------
    # ARAH MOTOR
    # -----------------------------------------------------

    if case_label in REVERSE_CASE_LABELS:

        auto_esc1 = (
            ESC_REVERSE_VALUE
        )

        auto_esc2 = (
            ESC_REVERSE_VALUE
        )

    else:

        auto_esc1 = (
            ESC_FORWARD_VALUE
        )

        auto_esc2 = (
            ESC_FORWARD_VALUE
        )


    # -----------------------------------------------------
    # SEND
    # -----------------------------------------------------

    send_auto(
        ser,
        auto_servo,
        auto_esc1,
        auto_esc2,
        case_label
    )


    print(
        f"{case_label} | "
        f"TARGET={target_heading:.2f} | "
        f"ACTUAL={actual_heading:.2f} | "
        f"ERROR={error:.2f} | "
        f"PID={output:.2f} | "
        f"SERVO={servo}"
    )


# =========================================================
# RUN CASE
# =========================================================

def run_case(
    ser,
    actual_heading,
    duration_target,
    next_heading,
    next_case,
    case_label
):

    global case_start_time
    global auto_sub_case
    global target_heading
    global pid_previous_error


    # -----------------------------------------------------
    # START CASE
    # -----------------------------------------------------

    if case_start_time is None:

        case_start_time = (
            time.monotonic()
        )


        print()
        print(
            "=============================="
        )

        print(
            f"{case_label} MULAI"
        )

        print(
            f"TARGET = "
            f"{target_heading:.2f}"
        )

        print(
            "=============================="
        )
        print()


    # -----------------------------------------------------
    # PID
    # -----------------------------------------------------

    run_pid_case(
        ser,
        actual_heading,
        case_label
    )


    # -----------------------------------------------------
    # TIMER
    # -----------------------------------------------------

    elapsed = (
        time.monotonic()
        - case_start_time
    )


    # -----------------------------------------------------
    # FOTO
    # -----------------------------------------------------

    if (
        case_label in CAPTURE_LABELS
        and elapsed >= duration_target * 0.5
    ):

        capture_waypoint_photo(
            case_label
        )


    # -----------------------------------------------------
    # CASE SELESAI
    # -----------------------------------------------------

    if elapsed >= duration_target:

        auto_sub_case = (
            next_case
        )

        case_start_time = None

        target_heading = (
            next_heading
        )

        reset_pid()


        if (
            target_heading is not None
            and actual_heading is not None
        ):

            pid_previous_error = (
                heading_error(
                    target_heading,
                    actual_heading
                )
            )


        print()
        print(
            "=============================="
        )

        print(
            f"{case_label} SELESAI"
        )

        if target_heading is not None:

            print(
                f"TARGET HEADING = "
                f"{target_heading:.2f}"
            )

        print(
            "=============================="
        )
        print()


# =========================================================
# BACA HEADING
# =========================================================

def read_heading(
    line,
    ser
):

    global heading
    global auto_sub_case
    global auto_servo
    global is_done_processed
    global last_compass_recv_time


    if not line.startswith("COMPASS"):

        return


    if "HEADING=" not in line:

        return


    try:

        data = (
            line.split(
                "HEADING=",
                1
            )[1]
        )

        data = (
            data.split(
                ",",
                1
            )[0]
        )

        heading = float(data)


        # -------------------------------------------------
        # NORMALISASI HEADING
        # -------------------------------------------------

        heading %= 360.0


        # -------------------------------------------------
        # UPDATE COMPASS TIMER
        # -------------------------------------------------

        last_compass_recv_time = (
            time.time()
        )


        # -------------------------------------------------
        # GPS MODULE
        # -------------------------------------------------

        set_heading(
            heading
        )


    except (
        ValueError,
        TypeError
    ):

        return


    # -----------------------------------------------------
    # BUKAN AUTO
    # -----------------------------------------------------

    if current_case != CASE_AUTO:

        return


    # =====================================================
    # CASE CHAIN
    # =====================================================

    CASE_CHAIN = [

        (
            AUTO_CASE_1,
            CASE_1_DURATION,
            WAYPOINT_2_HEADING,
            AUTO_CASE_2,
            "CASE1"
        ),

        (
            AUTO_CASE_2,
            CASE_2_DURATION,
            WAYPOINT_3_HEADING,
            AUTO_CASE_3,
            "CASE2"
        ),

        (
            AUTO_CASE_3,
            CASE_3_DURATION,
            WAYPOINT_4_HEADING,
            AUTO_CASE_4,
            "CASE3"
        ),

        (
            AUTO_CASE_4,
            CASE_4_DURATION,
            WAYPOINT_5_HEADING,
            AUTO_CASE_5,
            "CASE4"
        ),

        (
            AUTO_CASE_5,
            CASE_5_DURATION,
            WAYPOINT_6_HEADING,
            AUTO_CASE_6,
            "CASE5"
        ),

        (
            AUTO_CASE_6,
            CASE_6_DURATION,
            WAYPOINT_7_HEADING,
            AUTO_CASE_7,
            "CASE6"
        ),

        (
            AUTO_CASE_7,
            CASE_7_DURATION,
            WAYPOINT_8_HEADING,
            AUTO_CASE_8,
            "CASE7"
        ),

        (
            AUTO_CASE_8,
            CASE_8_DURATION,
            WAYPOINT_9_HEADING,
            AUTO_CASE_9,
            "CASE8"
        ),

        (
            AUTO_CASE_9,
            CASE_9_DURATION,
            WAYPOINT_10_HEADING,
            AUTO_CASE_10,
            "CASE9"
        ),

        (
            AUTO_CASE_10,
            CASE_10_DURATION,
            WAYPOINT_11_HEADING,
            AUTO_CASE_11,
            "CASE10"
        ),

        (
            AUTO_CASE_11,
            CASE_11_DURATION,
            WAYPOINT_12_HEADING,
            AUTO_CASE_12,
            "CASE11"
        ),

        (
            AUTO_CASE_12,
            CASE_12_DURATION,
            WAYPOINT_13_HEADING,
            AUTO_CASE_13,
            "CASE12"
        ),

        (
            AUTO_CASE_13,
            CASE_13_DURATION,
            WAYPOINT_14_HEADING,
            AUTO_CASE_14,
            "CASE13"
        ),

        (
            AUTO_CASE_14,
            CASE_14_DURATION,
            WAYPOINT_15_HEADING,
            AUTO_CASE_15,
            "CASE14"
        ),

        (
            AUTO_CASE_15,
            CASE_15_DURATION,
            WAYPOINT_16_HEADING,
            AUTO_CASE_16,
            "CASE15"
        ),

        (
            AUTO_CASE_16,
            CASE_16_DURATION,
            WAYPOINT_17_HEADING,
            AUTO_CASE_17,
            "CASE16"
        ),

        (
            AUTO_CASE_17,
            CASE_17_DURATION,
            None,
            AUTO_CASE_DONE,
            "CASE17"
        )
    ]


    for (
        case_id,
        duration,
        next_heading,
        next_case,
        label
    ) in CASE_CHAIN:

        if auto_sub_case == case_id:

            run_case(
                ser,
                heading,
                duration,
                next_heading,
                next_case,
                label
            )

            return


    # =====================================================
    # AUTO DONE
    # =====================================================

    if (
        auto_sub_case == AUTO_CASE_DONE
        and not is_done_processed
    ):

        auto_servo = 90


        send_auto(
            ser,
            auto_servo,
            1500,
            1500,
            "DONE"
        )


        print()
        print(
            "=============================="
        )

        print(
            "AUTO SELESAI"
        )

        print(
            "MOTOR STOP"
        )

        print(
            "=============================="
        )


        stop_streaming()

        is_done_processed = True


# =========================================================
# PARSE MOTOR FEEDBACK STM32
# =========================================================

def read_motor_feedback(line):

    if not line.startswith("MOTOR,"):

        return False


    try:

        fields = {}


        # -------------------------------------------------
        # PARSE
        # -------------------------------------------------

        parts = (
            line.strip()
            .split(",")
        )


        for item in parts[1:]:

            if "=" not in item:

                continue


            key, value = (
                item.split(
                    "=",
                    1
                )
            )


            fields[
                key.strip().upper()
            ] = value.strip()


        # -------------------------------------------------
        # DATA
        # -------------------------------------------------

        left_rpm = float(
            fields.get(
                "LEFT_RPM",
                0.0
            )
        )


        right_rpm = float(
            fields.get(
                "RIGHT_RPM",
                0.0
            )
        )


        speed_mps = float(
            fields.get(
                "SPEED_MPS",
                0.0
            )
        )


        direction = (
            fields
            .get(
                "DIRECTION",
                "STOP"
            )
            .upper()
        )


        if direction not in (
            "FORWARD",
            "REVERSE",
            "STOP"
        ):

            direction = "STOP"


        # -------------------------------------------------
        # VALIDASI SPEED
        # -------------------------------------------------

        if direction == "STOP":

            speed_mps = 0.0

        elif direction == "FORWARD":

            speed_mps = abs(
                speed_mps
            )

        elif direction == "REVERSE":

            speed_mps = -abs(
                speed_mps
            )


        # -------------------------------------------------
        # SIMPAN KE MOTOR STATE
        # -------------------------------------------------

        set_motor_data(
            left_rpm,
            right_rpm,
            speed_mps,
            direction
        )


        print(
            f"RX MOTOR | "
            f"L={left_rpm:.0f} RPM | "
            f"R={right_rpm:.0f} RPM | "
            f"SPEED={speed_mps:.2f} m/s | "
            f"DIR={direction}"
        )


        return True


    except (
        ValueError,
        TypeError
    ) as e:

        print(
            "[MOTOR PARSE ERROR] "
            f"{e} | RAW={line!r}"
        )

        return False


# =========================================================
# PROCESS LINE STM32
# =========================================================

def process_line(
    line,
    ser
):

    # -----------------------------------------------------
    # REMOTE
    # -----------------------------------------------------

    if line.startswith("REMOTE"):

        read_mode(line)

        return


    # -----------------------------------------------------
    # COMPASS
    # -----------------------------------------------------

    if line.startswith("COMPASS"):

        if "ERROR" in line:

            global last_compass_err_print

            now = time.time()

            if (
                now
                - last_compass_err_print
                >= 1.0
            ):

                print(
                    "RX:",
                    repr(line),
                    "<-- "
                    "[KOMPAS ERROR]"
                )

                last_compass_err_print = (
                    now
                )

        else:

            read_heading(
                line,
                ser
            )

        return


    # -----------------------------------------------------
    # MOTOR
    # -----------------------------------------------------

    if line.startswith("MOTOR,"):

        read_motor_feedback(
            line
        )

        return


    # -----------------------------------------------------
    # DATA LAIN
    # -----------------------------------------------------

    print(
        "RX:",
        repr(line)
    )


# =========================================================
# MAIN
# =========================================================

def main():

    global current_case
    global has_printed_initial_rc
    global last_compass_err_print


    print()
    print(
        "=========================================="
    )

    print(
        " MINI PC - REMOTE / MANUAL / AUTO"
    )

    print(
        "=========================================="
    )

    print(
        f"Port     : {PORT}"
    )

    print(
        f"Baudrate : {BAUDRATE}"
    )

    print()


    print(
        "PID CONFIG"
    )

    print(
        f"Kp = {Kp}"
    )

    print(
        f"Ki = {Ki}"
    )

    print(
        f"Kd = {Kd}"
    )

    print()


    print(
        f"Servo range : "
        f"{SERVO_MIN} - {SERVO_MAX}"
    )

    print(
        f"Servo center: "
        f"{SERVO_CENTER}"
    )

    print()


    ser = None


    try:

        # =================================================
        # GPS
        # =================================================

        print(
            "Memulai GPS reader..."
        )

        start_gps_reader()


        # =================================================
        # WEB SERVER
        # =================================================

        print(
            "Memulai Web Server dan kamera..."
        )

        start_streaming()


        # =================================================
        # SERIAL STM32
        # =================================================

        print(
            f"Membuka serial "
            f"{PORT}..."
        )


        ser = serial.Serial(
            PORT,
            BAUDRATE,
            timeout=0.05,
            exclusive=True
        )


        # STM32 USB CDC
        ser.dtr = True
        ser.rts = True


        print(
            "Serial berhasil dibuka."
        )


        # Tunggu STM32 reset
        time.sleep(2)


        ser.reset_input_buffer()
        ser.reset_output_buffer()


        # =================================================
        # RESET STATE
        # =================================================

        current_case = (
            CASE_MANUAL
        )

        target_heading = None

        reset_pid()


        print()
        print(
            "STM32 TERHUBUNG"
        )

        print(
            "Monitoring data..."
        )

        print()

        print(
            "CASE 0 = MANUAL"
        )

        print(
            "CASE 1 = AUTO"
        )

        print()


        # =================================================
        # MAIN LOOP
        # =================================================

        while True:

            while ser.in_waiting:

                raw = ser.readline()


                if not raw:

                    continue


                line = (
                    raw
                    .decode(
                        "utf-8",
                        errors="ignore"
                    )
                    .strip()
                )


                if not line:

                    continue


                # -----------------------------------------
                # REMOTE
                # -----------------------------------------

                if line.startswith(
                    "REMOTE"
                ):

                    if not has_printed_initial_rc:

                        print(
                            "[RC INIT]",
                            line
                        )

                        has_printed_initial_rc = (
                            True
                        )


                    process_line(
                        line,
                        ser
                    )


                # -----------------------------------------
                # COMPASS
                # -----------------------------------------

                elif line.startswith(
                    "COMPASS"
                ):

                    process_line(
                        line,
                        ser
                    )


                # -----------------------------------------
                # MOTOR
                # -----------------------------------------

                elif line.startswith(
                    "MOTOR,"
                ):

                    process_line(
                        line,
                        ser
                    )


                # -----------------------------------------
                # LAINNYA
                # -----------------------------------------

                else:

                    print(
                        "RX:",
                        repr(line)
                    )


            time.sleep(
                0.01
            )


    except KeyboardInterrupt:

        print()
        print(
            "=========================================="
        )

        print(
            " CTRL+C TERDETEKSI"
        )

        print(
            " Menghentikan program..."
        )

        print(
            "=========================================="
        )


    except serial.SerialException as e:

        print()
        print(
            "ERROR SERIAL:"
        )

        print(e)


    except Exception as e:

        print()
        print(
            "ERROR PROGRAM:"
        )

        print(e)


    finally:

        print()
        print(
            "=========================================="
        )

        print(
            " CLEANUP"
        )

        print(
            "=========================================="
        )


        # =================================================
        # CAMERA
        # =================================================

        try:

            stop_streaming()

            print(
                "Camera streaming dihentikan."
            )

        except Exception as e:

            print(
                f"WARNING camera: {e}"
            )


        # =================================================
        # GPS
        # =================================================

        try:

            stop_gps_reader()

            print(
                "GPS reader dihentikan."
            )

        except Exception as e:

            print(
                f"WARNING GPS: {e}"
            )


        # =================================================
        # SERIAL
        # =================================================

        if ser is not None:

            try:

                if ser.is_open:

                    ser.reset_input_buffer()
                    ser.reset_output_buffer()

                    ser.close()

                    print(
                        f"Serial {PORT} "
                        "ditutup."
                    )

            except Exception as e:

                print(
                    f"WARNING serial: {e}"
                )


        print()
        print(
            "Program selesai."
        )
        print()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    main()