#!/usr/bin/env python3

import serial
import pynmea2
import threading
import time
import re

# =========================================================
# CONFIG
# =========================================================

GPS_PORT = "/dev/ttyUSB0"
PORT = "/dev/ttyACM0"
GPS_BAUD = 115200

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
    "satellites": None,
    "hdop": None,
    "fix": False,
    "timestamp": None
}

_gps_lock = threading.Lock()
_gps_thread = None
_gps_serial = None
_stop_event = threading.Event()


# =========================================================
# NMEA PARSER
# =========================================================

def parse_nmea(line):

    global gps_data

    try:

        # -------------------------------------------------
        # GGA
        # Posisi + altitude + satellite + HDOP
        # -------------------------------------------------

        if re.match(r"^\$..GGA(?:,|\*)", line):

            msg = pynmea2.parse(line)

            with _gps_lock:

                if msg.gps_qual is not None:
                    gps_data["fix"] = int(msg.gps_qual) > 0

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


        # -------------------------------------------------
        # RMC
        # Speed + Course
        # -------------------------------------------------

        elif re.match(r"^\$..RMC(?:,|\*)", line):

            msg = pynmea2.parse(line)

            with _gps_lock:

                # Status A = valid
                gps_data["fix"] = msg.status == "A"

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

    except Exception as e:

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

def _gps_loop(port, baud, verbose):

    global _gps_serial

    try:
        _gps_serial = serial.Serial(port, baud, timeout=1)
        print(f"[OK] GPS connected on {port}")

    except Exception as e:
        print("[ERROR] Cannot open GPS")
        print(e)
        return

    last_display = 0

    while not _stop_event.is_set():

        try:
            line = _gps_serial.readline().decode(
                "ascii",
                errors="ignore"
            ).strip()

        except Exception as e:
            print(f"[GPS READ ERROR] {e}")
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