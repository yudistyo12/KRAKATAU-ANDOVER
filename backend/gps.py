#!/usr/bin/env python3

import serial
import pynmea2
import time
from datetime import datetime

# =========================================================
# CONFIG
# =========================================================

GPS_PORT = "/dev/ttyUSB0"
GPS_BAUD = 115200

# =========================================================
# GPS DATA
# =========================================================

gps_data = {
    "latitude": None,
    "longitude": None,
    "altitude": None,
    "speed_knots": None,
    "speed_kmh": None,
    "course": None,
    "satellites": None,
    "hdop": None,
    "fix": False,
    "timestamp": None
}


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

        if line.startswith("$GPGGA") or line.startswith("$GNGGA"):

            msg = pynmea2.parse(line)

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

        elif line.startswith("$GPRMC") or line.startswith("$GNRMC"):

            msg = pynmea2.parse(line)

            # Status A = valid
            gps_data["fix"] = msg.status == "A"

            if msg.latitude and msg.longitude:

                gps_data["latitude"] = msg.latitude
                gps_data["longitude"] = msg.longitude

            if msg.spd_over_grnd is not None:

                speed_knots = float(msg.spd_over_grnd)

                gps_data["speed_knots"] = speed_knots

                # knot -> km/h
                gps_data["speed_kmh"] = speed_knots * 1.852

            if msg.true_course is not None:
                gps_data["course"] = float(msg.true_course)

            gps_data["timestamp"] = str(msg.timestamp)

    except Exception as e:

        print(f"[GPS PARSE ERROR] {e}")


# =========================================================
# DISPLAY
# =========================================================

def print_gps():

    lat = gps_data["latitude"]
    lon = gps_data["longitude"]

    print("\n" + "=" * 60)

    print(
        f"TIME       : {gps_data['timestamp']}"
    )

    print(
        f"FIX        : {'VALID' if gps_data['fix'] else 'NO FIX'}"
    )

    print(
        f"LATITUDE   : {lat}"
    )

    print(
        f"LONGITUDE  : {lon}"
    )

    print(
        f"ALTITUDE   : {gps_data['altitude']} m"
    )

    print(
        f"SATELLITES : {gps_data['satellites']}"
    )

    print(
        f"HDOP       : {gps_data['hdop']}"
    )

    print(
        f"SPEED      : {gps_data['speed_knots']} knots"
    )

    print(
        f"SPEED      : {gps_data['speed_kmh']} km/h"
    )

    print(
        f"COURSE     : {gps_data['course']} deg"
    )

    print("=" * 60)


# =========================================================
# MAIN
# =========================================================

def main():

    print("==============================================")
    print(" GPS READER")
    print("==============================================")
    print(f"PORT : {GPS_PORT}")
    print(f"BAUD : {GPS_BAUD}")
    print()

    try:

        ser = serial.Serial(
            GPS_PORT,
            GPS_BAUD,
            timeout=1
        )

        print("[OK] GPS connected")
        print("[INFO] Waiting for GPS data...")
        print()

    except Exception as e:

        print("[ERROR] Cannot open GPS")
        print(e)

        return

    last_display = 0

    try:

        while True:

            line = ser.readline().decode(
                "ascii",
                errors="ignore"
            ).strip()

            if not line:
                continue

            # Debug NMEA
            # print(line)

            parse_nmea(line)

            # tampilkan setiap 1 detik
            now = time.time()

            if now - last_display >= 1:

                print_gps()

                last_display = now

    except KeyboardInterrupt:

        print("\n[STOP] GPS reader stopped")

    finally:

        ser.close()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()