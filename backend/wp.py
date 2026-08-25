import serial
import csv
import time
import os
from datetime import datetime

# =========================================================
# KONFIGURASI
# =========================================================
PORT = "/dev/ttyACM0"
BAUDRATE = 115200

CSV_FILE = "waypoint.csv"

# Channel IBUS
CH_MARK_WP = 10
CH_CLEAR_WP = 12

# Ambang switch
SWITCH_THRESHOLD = 1700


# =========================================================
# VARIABEL
# =========================================================
current_heading = None
current_x = None
current_y = None
current_z = None

current_ch10 = 988
current_ch12 = 988

wp_number = 0

# Mencegah satu kali tekan menghasilkan banyak WP
mark_latch = False
clear_latch = False


# =========================================================
# BUAT CSV
# =========================================================
def init_csv():

    if not os.path.exists(CSV_FILE):

        with open(CSV_FILE, "w", newline="") as file:

            writer = csv.writer(file)

            writer.writerow([
                "timestamp",
                "wp",
                "heading",
                "x",
                "y",
                "z"
            ])


# =========================================================
# LOAD JUMLAH WP DARI CSV
# =========================================================
def load_wp_number():

    global wp_number

    if not os.path.exists(CSV_FILE):
        wp_number = 0
        return

    try:

        with open(CSV_FILE, "r") as file:

            reader = csv.DictReader(file)

            rows = list(reader)

            if rows:
                wp_number = int(rows[-1]["wp"]) + 1
            else:
                wp_number = 0

    except Exception:

        wp_number = 0


# =========================================================
# SIMPAN WAYPOINT
# =========================================================
def save_waypoint():

    global wp_number

    if current_heading is None:
        print("[WP] Belum ada data heading!")
        return

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    with open(CSV_FILE, "a", newline="") as file:

        writer = csv.writer(file)

        writer.writerow([
            timestamp,
            wp_number,
            f"{current_heading:.2f}",
            current_x,
            current_y,
            current_z
        ])

    print()
    print("========================================")
    print(f"          WAYPOINT {wp_number}")
    print("========================================")
    print(f"Heading : {current_heading:.2f} deg")
    print(f"X       : {current_x}")
    print(f"Y       : {current_y}")
    print(f"Z       : {current_z}")
    print(f"Time    : {timestamp}")
    print(f"CSV     : {CSV_FILE}")
    print("========================================")
    print()

    wp_number += 1


# =========================================================
# CLEAR SEMUA WAYPOINT
# =========================================================
def clear_waypoints():

    global wp_number

    with open(CSV_FILE, "w", newline="") as file:

        writer = csv.writer(file)

        writer.writerow([
            "timestamp",
            "wp",
            "heading",
            "x",
            "y",
            "z"
        ])

    wp_number = 0

    print()
    print("========================================")
    print("       SEMUA WAYPOINT DIHAPUS")
    print("========================================")
    print()


# =========================================================
# PARSE COMPASS
# =========================================================
def parse_compass(line):

    global current_heading
    global current_x
    global current_y
    global current_z

    try:

        # COMPASS,HEADING=270.69,X=6,Y=-501,Z=224

        parts = line.split(",")

        current_heading = float(
            parts[1].split("=")[1]
        )

        current_x = int(
            parts[2].split("=")[1]
        )

        current_y = int(
            parts[3].split("=")[1]
        )

        current_z = int(
            parts[4].split("=")[1]
        )

        print(
            f"HEADING : {current_heading:7.2f} deg | "
            f"X : {current_x:5d} | "
            f"Y : {current_y:5d} | "
            f"Z : {current_z:5d}"
        )

    except Exception as e:

        print(
            f"[ERROR COMPASS] {line}"
        )

        print(e)


# =========================================================
# PARSE REMOTE
# =========================================================
def parse_remote(line):

    global current_ch10
    global current_ch12

    try:

        parts = line.split(",")

        for item in parts:

            if item.startswith("CH10="):

                current_ch10 = int(
                    item.split("=")[1]
                )

            elif item.startswith("CH12="):

                current_ch12 = int(
                    item.split("=")[1]
                )

        # ==========================================
        # MARK WP
        # ==========================================
        global mark_latch

        if current_ch10 > SWITCH_THRESHOLD:

            if not mark_latch:

                mark_latch = True

                save_waypoint()

        else:

            mark_latch = False


        # ==========================================
        # CLEAR WP
        # ==========================================
        global clear_latch

        if current_ch12 > SWITCH_THRESHOLD:

            if not clear_latch:

                clear_latch = True

                clear_waypoints()

        else:

            clear_latch = False

    except Exception as e:

        print(
            f"[ERROR REMOTE] {e}"
        )


# =========================================================
# MAIN
# =========================================================
def main():

    init_csv()
    load_wp_number()

    print("==========================================")
    print("       LOGGER KOMPAS + WAYPOINT")
    print("==========================================")
    print(f"Port       : {PORT}")
    print(f"Baudrate   : {BAUDRATE}")
    print(f"CSV        : {CSV_FILE}")
    print(f"WP awal    : {wp_number}")
    print()
    print("CH10 -> MARK WP")
    print("CH12 -> CLEAR WP")
    print("Ctrl+C -> Keluar")
    print("==========================================")
    print()

    ser = None

    try:

        ser = serial.Serial(
            PORT,
            BAUDRATE,
            timeout=1,
            exclusive=True
        )

        time.sleep(2)

        print("STM32 TERHUBUNG")
        print("Menunggu data...\n")

        while True:

            line = ser.readline().decode(
                "utf-8",
                errors="ignore"
            ).strip()

            if not line:
                continue

            # ======================================
            # HANYA COMPASS
            # ======================================
            if line.startswith("COMPASS,"):

                parse_compass(line)

            # ======================================
            # REMOTE HANYA UNTUK CH10 / CH12
            # ======================================
            elif line.startswith("REMOTE,"):

                parse_remote(line)

            # Data lain DIABAIKAN
            else:

                continue

    except serial.SerialException as e:

        print()
        print("GAGAL MEMBUKA STM32")
        print(e)

    except KeyboardInterrupt:

        print()
        print("Program dihentikan.")

    finally:

        if ser is not None:
            ser.close()

        print("Serial ditutup.")


# =========================================================
# START
# =========================================================
if __name__ == "__main__":
    main()