#!/usr/bin/env python3

import serial
import pynmea2
import threading
import time
import os
from serial.tools import list_ports


# =========================================================
# CONFIG
# =========================================================

<<<<<<< HEAD
GPS_PORT = os.getenv("GPS_DEVICE", "")
STM32_PORT = os.getenv("STM32_DEVICE", "/dev/ttyACM0")
GPS_BAUD = int(os.getenv("GPS_BAUD", "115200"))
=======
# =========================================================
# STM32
# =========================================================
#
# PORT INI HANYA UNTUK REFERENSI.
# gps.py TIDAK PERNAH MEMBUKA PORT INI.
#
STM32_PORT = "/dev/ttyACM0"

>>>>>>> ae4d561 (gps)

# =========================================================
# GPS
# =========================================================
#
# Arduino Nano + GPS
#
# Default:
# /dev/ttyUSB0
#
GPS_PORT = os.getenv(
    "GPS_DEVICE",
    "/dev/ttyUSB0"
)

# Default baud GPS:
# 9600
#
# Bisa override:
#
# GPS_BAUD=9600 python3 gps.py
#
GPS_BAUD = int(
    os.getenv(
        "GPS_BAUD",
        "9600"
    )
)


# =========================================================
# GPS DATA
# =========================================================

gps_data = {

    # GPS
    "latitude": None,
    "longitude": None,
    "altitude": None,

    "speed_knots": None,
    "speed_kmh": None,

    "course": None,

    # Heading berasal dari kompas STM32
    "heading": None,

    # Motor feedback dari STM32
    "left_rpm": None,
    "right_rpm": None,
    "motor_speed_mps": None,
    "motor_direction": "STOP",

    # GPS quality
    "satellites": None,
    "hdop": None,
    "fix": False,
<<<<<<< HEAD
    "timestamp": None,
    "gps_connected": False,
    "last_update": None
=======

    "timestamp": None,

    # Connection info
    "port": None,
    "baud": None,

    "connected": False
>>>>>>> ae4d561 (gps)
}


# =========================================================
# GLOBAL
# =========================================================

_gps_lock = threading.Lock()

_gps_thread = None

_gps_serial = None

_stop_event = threading.Event()

_gga_fix = False
_rmc_fix = False


# =========================================================
# NMEA CHECK
# =========================================================

def is_nmea_sentence(line):

    if not line:
        return False

    line = line.strip()

    if not line.startswith("$"):
        return False

    prefixes = (
        "$GPGGA",
        "$GNGGA",

        "$GPRMC",
        "$GNRMC",

        "$GPVTG",
        "$GNVTG",

        "$GPGSA",
        "$GNGSA",

        "$GPGSV",
        "$GNGSV"
    )

    return line.startswith(prefixes)


# =========================================================
# NMEA PARSER
# =========================================================

def parse_nmea(line):

    global _gga_fix
    global _rmc_fix

    try:

        line = line.strip()

        if not line:
            return False

        if not line.startswith("$"):
            return False

        # -------------------------------------------------
        # Parse NMEA
        # -------------------------------------------------

        msg = pynmea2.parse(line)

        # =================================================
        # GGA
        # =================================================

        if msg.sentence_type == "GGA":

            with _gps_lock:

                # -------------------------------------------------
                # FIX
                # -------------------------------------------------

                try:

                    if msg.gps_qual not in (
                        None,
                        ""
                    ):

                        _gga_fix = (
                            int(msg.gps_qual) > 0
                        )

                except Exception:

<<<<<<< HEAD
                gps_data["timestamp"] = str(msg.timestamp)
                gps_data["last_update"] = time.time()
                gps_data["fix"] = _gga_fix or _rmc_fix
            return True
=======
                    pass
>>>>>>> ae4d561 (gps)

                # -------------------------------------------------
                # LATITUDE
                # -------------------------------------------------

                try:

                    if msg.latitude not in (
                        None,
                        ""
                    ):

                        gps_data["latitude"] = float(
                            msg.latitude
                        )

                except Exception:

                    pass

                # -------------------------------------------------
                # LONGITUDE
                # -------------------------------------------------

                try:

                    if msg.longitude not in (
                        None,
                        ""
                    ):

                        gps_data["longitude"] = float(
                            msg.longitude
                        )

                except Exception:

                    pass

                # -------------------------------------------------
                # ALTITUDE
                # -------------------------------------------------

                try:

                    if msg.altitude not in (
                        None,
                        ""
                    ):

                        gps_data["altitude"] = float(
                            msg.altitude
                        )

                except Exception:

                    pass

                # -------------------------------------------------
                # SATELLITES
                # -------------------------------------------------

                try:

                    if msg.num_sats not in (
                        None,
                        ""
                    ):

                        gps_data["satellites"] = int(
                            msg.num_sats
                        )

                except Exception:

                    pass

                # -------------------------------------------------
                # HDOP
                # -------------------------------------------------

                try:

                    if msg.horizontal_dil not in (
                        None,
                        ""
                    ):

                        gps_data["hdop"] = float(
                            msg.horizontal_dil
                        )

                except Exception:

                    pass

                # -------------------------------------------------
                # TIMESTAMP
                # -------------------------------------------------

                try:

                    if msg.timestamp is not None:

                        gps_data["timestamp"] = str(
                            msg.timestamp
                        )

                except Exception:

                    pass

                # -------------------------------------------------
                # FIX FINAL
                # -------------------------------------------------

                gps_data["fix"] = (
                    _gga_fix or _rmc_fix
                )

            return True

        # =================================================
        # RMC
        # =================================================

        elif msg.sentence_type == "RMC":

            with _gps_lock:

                # -------------------------------------------------
                # FIX
                # -------------------------------------------------

                _rmc_fix = (
                    msg.status == "A"
                )

                # -------------------------------------------------
                # LATITUDE
                # -------------------------------------------------

                try:

                    if msg.latitude not in (
                        None,
                        ""
                    ):

                        gps_data["latitude"] = float(
                            msg.latitude
                        )

                except Exception:

<<<<<<< HEAD
                gps_data["timestamp"] = str(msg.timestamp)
                gps_data["last_update"] = time.time()
                gps_data["fix"] = _gga_fix or _rmc_fix
            return True
=======
                    pass

                # -------------------------------------------------
                # LONGITUDE
                # -------------------------------------------------

                try:

                    if msg.longitude not in (
                        None,
                        ""
                    ):

                        gps_data["longitude"] = float(
                            msg.longitude
                        )

                except Exception:

                    pass

                # -------------------------------------------------
                # SPEED
                # -------------------------------------------------

                try:

                    if msg.spd_over_grnd not in (
                        None,
                        ""
                    ):

                        speed_knots = float(
                            msg.spd_over_grnd
                        )

                        gps_data[
                            "speed_knots"
                        ] = speed_knots

                        gps_data[
                            "speed_kmh"
                        ] = (
                            speed_knots * 1.852
                        )

                except Exception:

                    pass

                # -------------------------------------------------
                # COURSE
                # -------------------------------------------------

                try:

                    if msg.true_course not in (
                        None,
                        ""
                    ):

                        gps_data[
                            "course"
                        ] = float(
                            msg.true_course
                        )

                except Exception:

                    pass

                # -------------------------------------------------
                # TIMESTAMP
                # -------------------------------------------------

                try:

                    if msg.timestamp is not None:

                        gps_data[
                            "timestamp"
                        ] = str(
                            msg.timestamp
                        )

                except Exception:

                    pass

                # -------------------------------------------------
                # FIX FINAL
                # -------------------------------------------------

                gps_data["fix"] = (
                    _gga_fix or _rmc_fix
                )

            return True

    except pynmea2.ParseError:

        return False
>>>>>>> ae4d561 (gps)

    except Exception as e:

        print(
            f"[GPS PARSE ERROR] {e}"
        )

        return False

    return False

    return False


# =========================================================
# GET GPS DATA
# =========================================================

def get_gps_data():

    with _gps_lock:

        return dict(
            gps_data
        )


# =========================================================
# SET HEADING
# =========================================================

def set_heading(heading):

    try:

        with _gps_lock:

            gps_data[
                "heading"
            ] = float(
                heading
            )

    except Exception:

        pass


# =========================================================
# SET MOTOR FEEDBACK
# =========================================================

def set_motor_feedback(
    left_rpm,
    right_rpm,
    speed_mps,
    direction
):

    with _gps_lock:

        try:

            gps_data[
                "left_rpm"
            ] = float(
                left_rpm
            )

        except Exception:

            gps_data[
                "left_rpm"
            ] = None

        try:

            gps_data[
                "right_rpm"
            ] = float(
                right_rpm
            )

        except Exception:

            gps_data[
                "right_rpm"
            ] = None

        try:

            gps_data[
                "motor_speed_mps"
            ] = float(
                speed_mps
            )

        except Exception:

            gps_data[
                "motor_speed_mps"
            ] = None

        gps_data[
            "motor_direction"
        ] = str(
            direction
        ).upper()


# =========================================================
# DISPLAY GPS
# =========================================================

def print_gps():

    data = get_gps_data()

    print()
    print(
        "=" * 60
    )

    print(
        f"GPS PORT   : {data['port']}"
    )

    print(
        f"GPS BAUD   : {data['baud']}"
    )

    print(
        f"CONNECTED  : {data['connected']}"
    )

    print(
        f"TIME       : {data['timestamp']}"
    )

    print(
        f"FIX        : "
        f"{'VALID' if data['fix'] else 'NO FIX'}"
    )

    print(
        f"LATITUDE   : {data['latitude']}"
    )

    print(
        f"LONGITUDE  : {data['longitude']}"
    )

    print(
        f"ALTITUDE   : {data['altitude']} m"
    )

    print(
        f"SATELLITES : {data['satellites']}"
    )

    print(
        f"HDOP       : {data['hdop']}"
    )

    print(
        f"SPEED      : {data['speed_knots']} knots"
    )

    print(
        f"SPEED      : {data['speed_kmh']} km/h"
    )

    print(
        f"COURSE     : {data['course']} deg"
    )

    print(
        f"HEADING    : {data['heading']} deg"
    )

    print(
        f"MOTOR L    : {data['left_rpm']} RPM"
    )

    print(
        f"MOTOR R    : {data['right_rpm']} RPM"
    )

    print(
        f"MOTOR SPEED: {data['motor_speed_mps']} m/s"
    )

    print(
        f"DIRECTION  : {data['motor_direction']}"
    )

    print(
        "=" * 60
    )


# =========================================================
# OPEN GPS
# =========================================================

def open_gps():

    global _gps_serial

<<<<<<< HEAD
=======
    print()
    print(
        "=========================================="
    )

    print(
        " GPS CONNECTION"
    )

    print(
        "=========================================="
    )

    print(
        f"GPS PORT : {GPS_PORT}"
    )

    print(
        f"GPS BAUD : {GPS_BAUD}"
    )

    print()

    # =====================================================
    # CEK PORT
    # =====================================================

    if not os.path.exists(
        GPS_PORT
    ):

        print(
            f"[GPS ERROR] "
            f"Port tidak ditemukan: {GPS_PORT}"
        )

        print(
            "[GPS] Pastikan Arduino Nano terhubung."
        )

        print(
            "[GPS] gps.py TIDAK akan mencoba "
            "/dev/ttyACM0."
        )

        return False

    # =====================================================
    # OPEN SERIAL
    # =====================================================

    try:

        _gps_serial = serial.Serial(
            GPS_PORT,
            GPS_BAUD,
            timeout=1
        )

        print(
            f"[GPS] Serial berhasil dibuka."
        )

        print(
            f"[GPS] Port : {GPS_PORT}"
        )

        print(
            f"[GPS] Baud : {GPS_BAUD}"
        )

        # Bersihkan buffer
        _gps_serial.reset_input_buffer()

        return True

    except Exception as e:

        print(
            "[GPS ERROR] "
            "Tidak bisa membuka serial GPS."
        )

        print(e)

        _gps_serial = None

        return False


# =========================================================
# GPS LOOP
# =========================================================

def _gps_loop(
    port,
    baud,
    verbose
):

    global _gps_serial
    global GPS_PORT
    global GPS_BAUD

    # =====================================================
    # Pakai port yang diberikan
    # =====================================================

    GPS_PORT = port
    GPS_BAUD = baud

    # =====================================================
    # OPEN
    # =====================================================

    if not open_gps():

        print(
            "[GPS] Reader dihentikan."
        )

        return

    # =====================================================
    # SET STATUS
    # =====================================================

    with _gps_lock:

        gps_data[
            "port"
        ] = GPS_PORT

        gps_data[
            "baud"
        ] = GPS_BAUD

        gps_data[
            "connected"
        ] = True

    print()
    print(
        "=========================================="
    )

    print(
        " GPS TERHUBUNG"
    )

    print(
        "=========================================="
    )

    print(
        f"PORT : {GPS_PORT}"
    )

    print(
        f"BAUD : {GPS_BAUD}"
    )

    print(
        "=========================================="
    )

>>>>>>> ae4d561 (gps)
    last_display = 0
    baud_rates = list(dict.fromkeys((baud, 9600, 4800, 38400, 115200)))
    baud_index = 0
    last_valid_sentence = 0.0
    selected_port = port

    def available_ports():
        configured = [selected_port] if selected_port else []
        detected = [
            item.device
            for item in list_ports.comports()
            if item.device != STM32_PORT
        ]
        candidates = list(dict.fromkeys(configured + detected))
        available = [candidate for candidate in candidates if os.path.exists(candidate)]

        if configured and configured[0] not in available:
            print(
                f"[GPS] Port konfigurasi tidak tersedia: {configured[0]}; "
                "mencoba port serial lain yang terdeteksi"
            )

        return available

    # =====================================================
    # READ LOOP
    # =====================================================

    while not _stop_event.is_set():

        if _gps_serial is None or not _gps_serial.is_open:
            ports = available_ports()
            if not ports:
                with _gps_lock:
                    gps_data["gps_connected"] = False
                print("[GPS] Tidak ada port serial GPS yang terdeteksi")
                time.sleep(2)
                continue

            connected = False
            for candidate_port in ports:
                try:
                    current_baud = baud_rates[baud_index]
                    _gps_serial = serial.Serial(
                        candidate_port,
                        current_baud,
                        timeout=1
                    )
                    selected_port = candidate_port
                    with _gps_lock:
                        gps_data["gps_connected"] = True
                    print(
                        f"[GPS] Mencoba {candidate_port} "
                        f"@ {current_baud}"
                    )
                    last_valid_sentence = time.time()
                    connected = True
                    break
                except Exception as error:
                    print(
                        f"[GPS] Tidak dapat membuka {candidate_port} "
                        f"@ {current_baud}: {error}"
                    )
                    _gps_serial = None

            if not connected:
                with _gps_lock:
                    gps_data["gps_connected"] = False
                time.sleep(2)
                continue

        try:

            raw = _gps_serial.readline()

            if not raw:

                continue

            line = raw.decode(
                "ascii",
                errors="ignore"
            ).strip()

            if not line:

                continue

            # =================================================
            # HANYA PROSES NMEA
            # =================================================

            if not is_nmea_sentence(
                line
            ):

                continue

            parsed = parse_nmea(
                line
            )

            # =================================================
            # DISPLAY
            # =================================================

            if parsed and verbose:

                now = time.time()

                if (
                    now - last_display
                    >= 1
                ):

                    print_gps()

                    last_display = now

        except serial.SerialException as e:

            print(
                f"[GPS SERIAL ERROR] {e}"
            )

            break

        except Exception as e:
<<<<<<< HEAD
            print(f"[GPS READ ERROR] {e}")
            with _gps_lock:
                gps_data["gps_connected"] = False
            try:
                _gps_serial.close()
            except Exception:
                pass
            _gps_serial = None
            time.sleep(0.5)
            continue
=======
>>>>>>> ae4d561 (gps)

            print(
                f"[GPS READ ERROR] {e}"
            )

<<<<<<< HEAD
        if parse_nmea(line):
            last_valid_sentence = time.time()

        if time.time() - last_valid_sentence > 8:
            try:
                _gps_serial.close()
            except Exception:
                pass
            _gps_serial = None
            baud_index = (baud_index + 1) % len(baud_rates)
            last_valid_sentence = 0.0
            continue
=======
            time.sleep(
                0.2
            )
>>>>>>> ae4d561 (gps)

    # =====================================================
    # CLEANUP
    # =====================================================

    if _gps_serial is not None:

        try:

            _gps_serial.close()

        except Exception:

            pass

<<<<<<< HEAD
    with _gps_lock:
        gps_data["gps_connected"] = False

    print("[GPS] Reader thread stopped")
=======
        _gps_serial = None
>>>>>>> ae4d561 (gps)

    with _gps_lock:

        gps_data[
            "connected"
        ] = False

    print(
        "[GPS] Reader thread stopped"
    )


# =========================================================
# START GPS
# =========================================================

def start_gps_reader(
    port=GPS_PORT,
    baud=GPS_BAUD,
    verbose=False
):

    global _gps_thread

    # =====================================================
    # Jangan start dua kali
    # =====================================================

    if (
        _gps_thread is not None
        and _gps_thread.is_alive()
    ):

        print(
            "[GPS] Reader sudah berjalan."
        )

        return

    # =====================================================
    # Validasi port
    # =====================================================

    if not port:

        port = "/dev/ttyUSB0"

    if not baud:

        baud = 9600

    _stop_event.clear()

    # =====================================================
    # START THREAD
    # =====================================================

    _gps_thread = threading.Thread(
        target=_gps_loop,
        args=(
            port,
            int(baud),
            verbose
        ),
        daemon=True
    )

    _gps_thread.start()


# =========================================================
# STOP GPS
# =========================================================

def stop_gps_reader():

    global _gps_serial

    _stop_event.set()

    # Tutup serial supaya readline() tidak menggantung
    if _gps_serial is not None:

        try:

            _gps_serial.close()

        except Exception:

            pass

        _gps_serial = None

    # Tunggu thread
    if (
        _gps_thread is not None
        and _gps_thread.is_alive()
    ):

        _gps_thread.join(
            timeout=2
        )

    with _gps_lock:

        gps_data[
            "connected"
        ] = False

    print(
        "[GPS] Reader dihentikan."
    )


# =========================================================
# STANDALONE TEST
# =========================================================

def main():

    print()
    print(
        "=============================================="
    )

    print(
        " GPS READER - STANDALONE TEST"
    )

    print(
        "=============================================="
    )

    print(
        f"GPS PORT : {GPS_PORT}"
    )

    print(
        f"GPS BAUD : {GPS_BAUD}"
    )

    print()

    # =====================================================
    # START
    # =====================================================

    start_gps_reader(
        port=GPS_PORT,
        baud=GPS_BAUD,
        verbose=True
    )

    try:

        while True:

            time.sleep(
                1
            )

    except KeyboardInterrupt:

        print()
        print(
            "[STOP] CTRL+C"
        )

    finally:

        stop_gps_reader()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    main()