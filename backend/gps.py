#!/usr/bin/env python3

import serial
import pynmea2
import threading
import time
import os

# =========================================================
# CONFIG
# =========================================================

GPS_PORT = os.getenv("GPS_DEVICE", "/dev/ttyUSB0")
PORT = "/dev/ttyACM0"
GPS_BAUD = int(os.getenv("GPS_BAUD", "115200"))
GPS_BAUD_CANDIDATES = tuple(dict.fromkeys([
    GPS_BAUD,
    4800,
    9600,
    38400,
    115200
]))

# =========================================================
# GPS DATA (shared, thread-safe)
# =========================================================

gps_data = {
    "latitude": None,
    "longitude": None,
    "altitude": None,
    "speed_knots": None,
    "speed_kmh": None,
    "course": None,
    "heading": None,
    "left_rpm": None,
    "right_rpm": None,
    "motor_speed_mps": None,
    "motor_direction": "STOP",
    "satellites": None,
    "hdop": None,
    "fix": False,
    "timestamp": None,
    "reader_status": "STARTING",
    "reader_port": None,
    "reader_baud": None,
    "last_nmea": None,
    "last_nmea_at": None,
    "last_error": None
}

_gps_lock = threading.Lock()
_gps_thread = None
_gps_serial = None
_stop_event = threading.Event()
_gga_fix = False
_rmc_fix = False


# =========================================================
# NMEA PARSER
# =========================================================

def parse_nmea(line):

    global gps_data
    global _gga_fix
    global _rmc_fix

    try:

        # -------------------------------------------------
        # GGA
        # Posisi + altitude + satellite + HDOP
        # -------------------------------------------------

        msg = pynmea2.parse(line, check=False)

        with _gps_lock:
            gps_data["last_nmea"] = msg.sentence_type
            gps_data["last_nmea_at"] = time.time()
            gps_data["last_error"] = None

        if msg.sentence_type == "GGA":

            with _gps_lock:

                if msg.gps_qual is not None:
                    _gga_fix = int(msg.gps_qual) > 0

                if msg.latitude and msg.longitude:
                    gps_data["latitude"] = msg.latitude
                    gps_data["longitude"] = msg.longitude

                if msg.altitude:
                    gps_data["altitude"] = float(msg.altitude)

                if msg.num_sats:
                    gps_data["satellites"] = int(msg.num_sats)

                if msg.horizontal_dil:
                    gps_data["hdop"] = float(msg.horizontal_dil)

                gps_data["timestamp"] = str(msg.timestamp)
                gps_data["fix"] = _gga_fix or _rmc_fix


        # -------------------------------------------------
        # RMC
        # Speed + Course
        # -------------------------------------------------

        elif msg.sentence_type == "RMC":

            with _gps_lock:

                _rmc_fix = msg.status == "A"

                if msg.latitude and msg.longitude:
                    gps_data["latitude"] = msg.latitude
                    gps_data["longitude"] = msg.longitude

                if msg.spd_over_grnd not in (None, ""):

                    speed_knots = float(msg.spd_over_grnd)

                    gps_data["speed_knots"] = speed_knots

                    # knot -> km/h
                    gps_data["speed_kmh"] = speed_knots * 1.852

                if msg.true_course not in (None, ""):
                    gps_data["course"] = float(msg.true_course)

                gps_data["timestamp"] = str(msg.timestamp)
                gps_data["fix"] = _gga_fix or _rmc_fix

        # -------------------------------------------------
        # VTG
        # Course and ground speed fallback
        # -------------------------------------------------

        elif msg.sentence_type == "VTG":

            with _gps_lock:

                if msg.true_track not in (None, ""):
                    gps_data["course"] = float(msg.true_track)

                if msg.spd_over_grnd_kmph not in (None, ""):
                    speed_kmh = float(msg.spd_over_grnd_kmph)
                    gps_data["speed_kmh"] = speed_kmh
                    gps_data["speed_knots"] = speed_kmh / 1.852

                gps_data["fix"] = _gga_fix or _rmc_fix

    except Exception as e:
        with _gps_lock:
            gps_data["last_error"] = str(e)
        print(f"[GPS PARSE ERROR] {e}")


# =========================================================
# ACCESSOR (dipakai modul lain, mis. main.py)
# =========================================================

def get_gps_data():
    """Kembalikan salinan snapshot data GPS terbaru (thread-safe)."""
    with _gps_lock:
        return dict(gps_data)


def set_heading(heading):
    """Simpan heading kompas terbaru agar tersedia untuk telemetry web."""
    with _gps_lock:
        gps_data["heading"] = float(heading)


def set_motor_feedback(left_rpm, right_rpm, speed_mps, direction):
    """Simpan feedback kecepatan motor terbaru dari STM32."""
    with _gps_lock:
        gps_data["left_rpm"] = float(left_rpm)
        gps_data["right_rpm"] = float(right_rpm)
        gps_data["motor_speed_mps"] = float(speed_mps)
        gps_data["motor_direction"] = str(direction).upper()


# =========================================================
# DISPLAY
# =========================================================

def print_gps():

    data = get_gps_data()

    print("\n" + "=" * 60)

    print(f"TIME       : {data['timestamp']}")
    print(f"FIX        : {'VALID' if data['fix'] else 'NO FIX'}")
    print(f"LATITUDE   : {data['latitude']}")
    print(f"LONGITUDE  : {data['longitude']}")
    print(f"ALTITUDE   : {data['altitude']} m")
    print(f"SATELLITES : {data['satellites']}")
    print(f"HDOP       : {data['hdop']}")
    print(f"SPEED      : {data['speed_knots']} knots")
    print(f"SPEED      : {data['speed_kmh']} km/h")
    print(f"COURSE     : {data['course']} deg")

    print("=" * 60)


# =========================================================
# BACKGROUND READER THREAD
# =========================================================

def _connect_gps(port):
    for baud in GPS_BAUD_CANDIDATES:
        connection = None
        try:
            connection = serial.Serial(port, baud, timeout=0.5)
            deadline = time.monotonic() + 3

            while time.monotonic() < deadline:
                line = connection.readline().decode(
                    "ascii",
                    errors="ignore"
                ).strip()
                if not line:
                    continue

                try:
                    message = pynmea2.parse(line, check=False)
                except pynmea2.ParseError:
                    continue

                if message.sentence_type in ("RMC", "GGA"):
                    print(f"[OK] GPS connected on {port} at {baud} baud")
                    return connection, line

            connection.close()
        except Exception as error:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
            print(f"[GPS] Cannot read {port} at {baud} baud: {error}")

    return None, None

def _gps_loop(port, baud, verbose):

    global _gps_serial

    with _gps_lock:
        gps_data["reader_status"] = "CONNECTING"
        gps_data["reader_port"] = port

    last_display = 0

    while not _stop_event.is_set():
        if _gps_serial is None or not _gps_serial.is_open:
            _gps_serial, first_line = _connect_gps(port)
            if _gps_serial is None:
                with _gps_lock:
                    gps_data["reader_status"] = "NO_NMEA"
                print(f"[GPS] No NMEA data on {port}; retrying...")
                time.sleep(2)
                continue
            parse_nmea(first_line)
            with _gps_lock:
                gps_data["reader_status"] = "CONNECTED"
                gps_data["reader_baud"] = next(
                    baud_rate for baud_rate in GPS_BAUD_CANDIDATES
                    if baud_rate == _gps_serial.baudrate
                )

        try:
            line = _gps_serial.readline().decode(
                "ascii",
                errors="ignore"
            ).strip()

        except Exception as e:
            print(f"[GPS READ ERROR] {e}")
            with _gps_lock:
                gps_data["reader_status"] = "READ_ERROR"
                gps_data["last_error"] = str(e)
            try:
                _gps_serial.close()
            except Exception:
                pass
            _gps_serial = None
            time.sleep(0.5)
            continue

        if not line:
            continue

        parse_nmea(line)

        if verbose:
            now = time.time()
            if now - last_display >= 1:
                print_gps()
                last_display = now

    if _gps_serial is not None:
        try:
            _gps_serial.close()
        except Exception:
            pass

    print("[GPS] Reader thread stopped")


def start_gps_reader(port=GPS_PORT, baud=GPS_BAUD, verbose=False):
    """
    Mulai membaca GPS di thread terpisah (non-blocking).
    Panggil sekali saat program utama start.
    """

    global _gps_thread

    if _gps_thread is not None and _gps_thread.is_alive():
        print("[GPS] Reader sudah berjalan, skip start")
        return

    _stop_event.clear()

    _gps_thread = threading.Thread(
        target=_gps_loop,
        args=(port, baud, verbose),
        daemon=True
    )
    _gps_thread.start()


def stop_gps_reader():
    """Hentikan thread pembaca GPS dan tutup serial. Panggil saat cleanup."""

    _stop_event.set()

    if _gps_thread is not None:
        _gps_thread.join(timeout=2)


# =========================================================
# STANDALONE TEST (jalankan langsung: python3 gps.py)
# =========================================================

def main():

    print("==============================================")
    print(" GPS READER (standalone test)")
    print("==============================================")
    print(f"PORT : {GPS_PORT}")
    print(f"BAUD : {GPS_BAUD}")
    print()

    start_gps_reader(verbose=True)

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[STOP] GPS reader stopped")

    finally:
        stop_gps_reader()


if __name__ == "__main__":
    main()