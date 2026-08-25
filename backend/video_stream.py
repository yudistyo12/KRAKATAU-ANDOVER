#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cv2
import os
import time
import threading
import logging

from flask import Flask, Response, send_from_directory, abort, jsonify, request

from gps import get_gps_data
from motor_state import get_motor_data


# =========================================================
# SILENCE HTTP REQUEST LOGS
# =========================================================

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)


# =========================================================
# CONFIG
# =========================================================

SURFACE_CAMERA_INDEX = os.getenv(
    "SURFACE_CAMERA_DEVICE",
    "/dev/video0"
)
UNDERWATER_CAMERA_INDEX = os.getenv(
    "UNDERWATER_CAMERA_DEVICE",
    "/dev/video2"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SURFACE_PHOTO_DIR = os.path.join(
    BASE_DIR,
    "surface"
)

UNDERWATER_PHOTO_DIR = os.path.join(
    BASE_DIR,
    "underwater"
)

STREAM_HOST = "0.0.0.0"
STREAM_PORT = 5001
ALLOWED_ORIGINS = {
    origin.strip()
    for origin in os.getenv(
        "GCS_ALLOWED_ORIGINS",
        "null,http://localhost:5500,http://127.0.0.1:5500,http://192.168.1.102:5500"
    ).split(",")
    if origin.strip()
}


# =========================================================
# HEARTBEAT / GCS FAILSAFE
# =========================================================

last_gcs_heartbeat = time.time()

heartbeat_lock = threading.Lock()


def trigger_heartbeat():
    """
    Memperbarui waktu terakhir GCS aktif.
    """
    global last_gcs_heartbeat

    with heartbeat_lock:
        last_gcs_heartbeat = time.time()


def reset_heartbeat():
    """
    Reset heartbeat GCS.
    """
    global last_gcs_heartbeat

    with heartbeat_lock:
        last_gcs_heartbeat = time.time()


def is_gcs_active(timeout=3.0):
    """
    True jika GCS masih aktif dalam batas timeout.
    """

    with heartbeat_lock:
        elapsed = time.time() - last_gcs_heartbeat

    return elapsed <= timeout


def get_heartbeat_age():
    """
    Mengembalikan umur heartbeat dalam detik.
    """

    with heartbeat_lock:
        return time.time() - last_gcs_heartbeat


# =========================================================
# CAMERA CONFIG
# =========================================================

# ---------------------------------------------------------
# SURFACE CAMERA
# ---------------------------------------------------------
#
# /dev/video0
# YUYV
# 640x480
# 30 FPS
#

SURFACE_WIDTH = 640
SURFACE_HEIGHT = 480
SURFACE_FPS = 30
SURFACE_FORMAT = "YUYV"


# ---------------------------------------------------------
# UNDERWATER CAMERA
# ---------------------------------------------------------
#
# /dev/video2
# MJPG
# 640x480
# 30 FPS
#

UNDERWATER_WIDTH = 640
UNDERWATER_HEIGHT = 480
UNDERWATER_FPS = 30
UNDERWATER_FORMAT = "MJPG"


# ---------------------------------------------------------
# STREAM
# ---------------------------------------------------------

READ_FPS = 20.0
JPEG_QUALITY = 80


# =========================================================
# CAMERA GRABBER
# =========================================================

class _CameraGrabber:

    def __init__(
        self,
        camera_index,
        label,
        width,
        height,
        fps,
        pixel_format,
        rotate_left=False
    ):

        self.camera_index = camera_index
        self.label = label

        self.width = width
        self.height = height
        self.fps = fps

        self.pixel_format = pixel_format
        self.rotate_left = rotate_left

        self.cap = None
        self.thread = None

        self.running = False

        self.latest_frame = None

        self.frame_lock = threading.Lock()

    # =====================================================
    # START CAMERA
    # =====================================================

    def start(self):

        if self.running:

            print(
                f"Kamera {self.label} "
                f"sudah berjalan"
            )

            return True

        print(
            f"Membuka kamera {self.label} "
            f"{self.camera_index}..."
        )

        # -------------------------------------------------
        # V4L2
        # -------------------------------------------------

        self.cap = cv2.VideoCapture(
            self.camera_index,
            cv2.CAP_V4L2
        )

        if not self.cap.isOpened():
            self.cap.release()
            self.cap = cv2.VideoCapture(
                self.camera_index
            )

        if not self.cap.isOpened():

            print(
                f"ERROR: kamera {self.label} "
                f"tidak dapat dibuka"
            )

            self.cap = None

            return False

        # -------------------------------------------------
        # PIXEL FORMAT
        # -------------------------------------------------

        fourcc = cv2.VideoWriter_fourcc(
            *self.pixel_format
        )

        self.cap.set(
            cv2.CAP_PROP_FOURCC,
            fourcc
        )

        # -------------------------------------------------
        # RESOLUTION
        # -------------------------------------------------

        self.cap.set(
            cv2.CAP_PROP_FRAME_WIDTH,
            self.width
        )

        self.cap.set(
            cv2.CAP_PROP_FRAME_HEIGHT,
            self.height
        )

        # -------------------------------------------------
        # FPS
        # -------------------------------------------------

        self.cap.set(
            cv2.CAP_PROP_FPS,
            self.fps
        )

        # -------------------------------------------------
        # LOW BUFFER
        # -------------------------------------------------

        try:

            self.cap.set(
                cv2.CAP_PROP_BUFFERSIZE,
                1
            )

        except Exception:
            pass

        # -------------------------------------------------
        # CEK SETTING AKTUAL
        # -------------------------------------------------

        actual_width = int(
            self.cap.get(
                cv2.CAP_PROP_FRAME_WIDTH
            )
        )

        actual_height = int(
            self.cap.get(
                cv2.CAP_PROP_FRAME_HEIGHT
            )
        )

        actual_fps = self.cap.get(
            cv2.CAP_PROP_FPS
        )

        ret = False
        first_frame = None

        for attempt in range(10):
            ret, first_frame = self.cap.read()
            if ret and first_frame is not None:
                break
            time.sleep(0.1)

        if not ret or first_frame is None:
            print(
                f"ERROR: kamera {self.label} terbuka, "
                "tetapi tidak mengirim frame"
            )
            self.cap.release()
            self.cap = None
            return False

        if self.rotate_left:
            first_frame = cv2.rotate(
                first_frame,
                cv2.ROTATE_90_COUNTERCLOCKWISE
            )

        with self.frame_lock:
            self.latest_frame = first_frame

        print(
            f"Kamera {self.label}: "
            f"{actual_width}x{actual_height} "
            f"@ {actual_fps:.1f} FPS | "
            f"{self.pixel_format}"
        )

        # -------------------------------------------------
        # START THREAD
        # -------------------------------------------------

        self.running = True

        self.thread = threading.Thread(
            target=self._read_loop,
            daemon=True,
            name=f"Camera-{self.label}"
        )

        self.thread.start()

        print(
            f"Streaming kamera "
            f"{self.label} dimulai"
        )

        return True

    # =====================================================
    # READ LOOP
    # =====================================================

    def _read_loop(self):

        interval = 1.0 / READ_FPS

        while self.running:

            if self.cap is None:
                break

            try:

                ret, frame = self.cap.read()

            except Exception as e:

                print(
                    f"ERROR read kamera "
                    f"{self.label}: {e}"
                )

                time.sleep(0.1)

                continue

            if ret and frame is not None:

                # -------------------------------------------------
                # ROTATE UNDERWATER
                # -------------------------------------------------

                if self.rotate_left:

                    frame = cv2.rotate(
                        frame,
                        cv2.ROTATE_90_COUNTERCLOCKWISE
                    )

                # -------------------------------------------------
                # SIMPAN FRAME TERBARU
                # -------------------------------------------------

                with self.frame_lock:

                    self.latest_frame = frame

            else:

                print(
                    f"WARNING: gagal membaca "
                    f"kamera {self.label}"
                )

                time.sleep(0.05)

            time.sleep(interval)

    # =====================================================
    # STOP CAMERA
    # =====================================================

    def stop(self):

        if not self.running:

            return

        print(
            f"Menghentikan kamera "
            f"{self.label}..."
        )

        self.running = False

        # -------------------------------------------------
        # WAIT THREAD
        # -------------------------------------------------

        if (
            self.thread is not None
            and self.thread.is_alive()
        ):

            self.thread.join(
                timeout=2.0
            )

        self.thread = None

        # -------------------------------------------------
        # RELEASE CAMERA
        # -------------------------------------------------

        if self.cap is not None:

            try:

                self.cap.release()

            except Exception as e:

                print(
                    f"WARNING release "
                    f"{self.label}: {e}"
                )

            self.cap = None

        # -------------------------------------------------
        # CLEAR FRAME
        # -------------------------------------------------

        with self.frame_lock:

            self.latest_frame = None

        print(
            f"Kamera {self.label} "
            f"berhasil dihentikan"
        )

    # =====================================================
    # GET FRAME
    # =====================================================

    def get_frame(self):

        with self.frame_lock:

            return self.latest_frame

    # =====================================================
    # SAVE SNAPSHOT
    # =====================================================

    def save_snapshot(self, save_dir):

        frame = self.get_frame()

        if frame is None:

            print(
                f"ERROR: belum ada frame "
                f"{self.label}"
            )

            return None

        # -------------------------------------------------
        # CREATE DIRECTORY
        # -------------------------------------------------

        os.makedirs(
            save_dir,
            exist_ok=True
        )

        # -------------------------------------------------
        # FILENAME
        # -------------------------------------------------

        filename = os.path.join(
            save_dir,
            f"{self.label}_"
            f"{time.strftime('%Y%m%d_%H%M%S')}.jpg"
        )

        # -------------------------------------------------
        # SAVE
        # -------------------------------------------------

        success = cv2.imwrite(
            filename,
            frame,
            [
                int(
                    cv2.IMWRITE_JPEG_QUALITY
                ),
                JPEG_QUALITY
            ]
        )

        if not success:

            print(
                f"ERROR: gagal menyimpan "
                f"foto {self.label}"
            )

            return None

        print(
            f"Foto {self.label} disimpan: "
            f"{filename}"
        )

        return filename


# =========================================================
# CAMERA OBJECT
# =========================================================

_surface_grabber = _CameraGrabber(

    SURFACE_CAMERA_INDEX,

    "surface",

    SURFACE_WIDTH,
    SURFACE_HEIGHT,

    SURFACE_FPS,

    SURFACE_FORMAT,

    rotate_left=False
)


_underwater_grabber = _CameraGrabber(

    UNDERWATER_CAMERA_INDEX,

    "underwater",

    UNDERWATER_WIDTH,
    UNDERWATER_HEIGHT,

    UNDERWATER_FPS,

    UNDERWATER_FORMAT,

    rotate_left=True
)


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)


# =========================================================
# CORS
# =========================================================

@app.after_request
def _add_cors_headers(response):

    origin = request.headers.get("Origin")

    if origin in ALLOWED_ORIGINS:
        response.headers[
            "Access-Control-Allow-Origin"
        ] = origin
        response.headers[
            "Vary"
        ] = "Origin"

    response.headers[
        "Access-Control-Allow-Methods"
    ] = "GET, POST, OPTIONS"

    response.headers[
        "Access-Control-Allow-Headers"
    ] = "Content-Type"

    return response


# =========================================================
# GCS HEARTBEAT
# =========================================================

@app.route(
    "/ping_gcs",
    methods=[
        "GET",
        "POST",
        "OPTIONS"
    ]
)
def ping_gcs():

    trigger_heartbeat()

    return jsonify({
        "status": "ok",
        "gcs_active": True,
        "timestamp": time.time()
    }), 200


# =========================================================
# TELEMETRY
# =========================================================

@app.route("/telemetry")
def telemetry():
    # -----------------------------------------------------
    # GPS
    # -----------------------------------------------------

    data = get_gps_data()

    if data is None:
        data = {}

    speed_knots = data.get(
        "speed_knots"
    )

    if speed_knots is not None:

        try:

            gps_speed_mps = (
                float(speed_knots)
                * 0.514444
            )

        except (
            ValueError,
            TypeError
        ):

            gps_speed_mps = None

    else:

        gps_speed_mps = None

    course = data.get(
        "course"
    )

    heading = data.get(
        "heading"
    )

    # -----------------------------------------------------
    # MOTOR
    # -----------------------------------------------------

    motor = get_motor_data()

    if motor is None:
        motor = {}

    try:

        left_rpm = float(
            motor.get(
                "left_rpm",
                0.0
            )
        )

    except (
        ValueError,
        TypeError
    ):

        left_rpm = 0.0

    try:

        right_rpm = float(
            motor.get(
                "right_rpm",
                0.0
            )
        )

    except (
        ValueError,
        TypeError
    ):

        right_rpm = 0.0

    try:

        motor_speed_mps = float(
            motor.get(
                "speed_mps",
                0.0
            )
        )

    except (
        ValueError,
        TypeError
    ):

        motor_speed_mps = 0.0

    motor_direction = str(
        motor.get(
            "direction",
            "STOP"
        )
    ).upper()

    if motor_direction not in (
        "FORWARD",
        "REVERSE",
        "STOP"
    ):

        motor_direction = "STOP"

    motor_updated_at = motor.get(
        "updated_at",
        0.0
    )

    # -----------------------------------------------------
    # DISPLAY SPEED
    # -----------------------------------------------------
    #
    # Motor feedback diprioritaskan.
    #
    # Jika motor_state belum menerima data STM32,
    # speed motor default 0.0 sehingga GPS menjadi
    # fallback.
    # -----------------------------------------------------

    if motor_updated_at:

        display_speed = motor_speed_mps

    elif gps_speed_mps is not None:

        display_speed = gps_speed_mps

    else:

        display_speed = 0.0

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    response = jsonify({

        # =========================
        # GPS
        # =========================

        "lat": data.get(
            "latitude"
        ),

        "lon": data.get(
            "longitude"
        ),

        "speed": display_speed,

        "course": (
            course
            if course is not None
            else heading
        ),

        "heading": heading,

        "fix": data.get(
            "fix",
            False
        ),

        "speed_knots": speed_knots,

        "speed_kmh": data.get(
            "speed_kmh"
        ),

        "altitude": data.get(
            "altitude"
        ),

        "satellites": data.get(
            "satellites"
        ),

        "hdop": data.get(
            "hdop"
        ),

        "timestamp": data.get(
            "timestamp"
        ),

        # =========================
        # MOTOR
        # =========================

        "left_rpm": left_rpm,

        "right_rpm": right_rpm,

        "motor_speed_mps": motor_speed_mps,

        "motor_direction": motor_direction,

        "motor_updated_at": motor_updated_at,

        # =========================
        # GCS
        # =========================

        "gcs_active": is_gcs_active(),

        "heartbeat_age": get_heartbeat_age()
    })

    # -----------------------------------------------------
    # NO CACHE
    # -----------------------------------------------------

    response.headers[
        "Cache-Control"
    ] = (
        "no-store, "
        "no-cache, "
        "must-revalidate"
    )

    response.headers[
        "Pragma"
    ] = "no-cache"

    response.headers[
        "Expires"
    ] = "0"

    return response


# =========================================================
# MJPEG GENERATOR
# =========================================================

def _mjpeg_generator(grabber):

    while True:

        frame = grabber.get_frame()

        if frame is not None:

            try:

                ok, buffer = cv2.imencode(
                    ".jpg",
                    frame,
                    [
                        int(
                            cv2.IMWRITE_JPEG_QUALITY
                        ),
                        JPEG_QUALITY
                    ]
                )

            except Exception as e:

                print(
                    f"ERROR encode "
                    f"{grabber.label}: {e}"
                )

                ok = False
                buffer = None

            if ok and buffer is not None:

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Cache-Control: no-cache\r\n\r\n"
                    + buffer.tobytes()
                    + b"\r\n"
                )

        time.sleep(
            1.0 / READ_FPS
        )


# =========================================================
# PHOTO DIRECTORIES
# =========================================================

_PHOTO_DIRS = {

    "surface":
        SURFACE_PHOTO_DIR,

    "underwater":
        UNDERWATER_PHOTO_DIR
}


# =========================================================
# LIST PHOTOS
# =========================================================

def _list_photos(photo_dir):

    if not os.path.isdir(
        photo_dir
    ):

        return []

    files = [

        f

        for f in os.listdir(
            photo_dir
        )

        if f.lower().endswith(
            (
                ".jpg",
                ".jpeg",
                ".png"
            )
        )
    ]

    files.sort(
        reverse=True
    )

    return files


# =========================================================
# API LIST PHOTOS
# =========================================================

@app.route(
    "/api/photos/<camera>"
)
def api_list_photos(camera):
    photo_dir = _PHOTO_DIRS.get(
        camera
    )

    if photo_dir is None:

        abort(404)

    files = _list_photos(
        photo_dir
    )

    response = jsonify({

        "camera": camera,

        "count": len(files),

        "photos": [
            f"/photos/{camera}/{fn}"
            for fn in files
        ]
    })

    response.headers[
        "Cache-Control"
    ] = (
        "no-store, "
        "no-cache, "
        "must-revalidate"
    )

    return response


# =========================================================
# PHOTO FILE
# =========================================================

@app.route(
    "/photos/<camera>/<path:filename>"
)
def get_photo_file(
    camera,
    filename
):
    photo_dir = _PHOTO_DIRS.get(
        camera
    )

    if photo_dir is None:

        abort(404)

    return send_from_directory(
        photo_dir,
        filename
    )


# =========================================================
# SURFACE FEED
# =========================================================

@app.route(
    "/surface_feed"
)
def surface_feed():
    return Response(

        _mjpeg_generator(
            _surface_grabber
        ),

        mimetype=(
            "multipart/"
            "x-mixed-replace;"
            " boundary=frame"
        )
    )


# =========================================================
# UNDERWATER FEED
# =========================================================

@app.route(
    "/underwater_feed"
)
def underwater_feed():
    return Response(

        _mjpeg_generator(
            _underwater_grabber
        ),

        mimetype=(
            "multipart/"
            "x-mixed-replace;"
            " boundary=frame"
        )
    )


# =========================================================
# SERVER CONTROL
# =========================================================

_flask_thread = None


def _run_flask():

    app.run(

        host=STREAM_HOST,

        port=STREAM_PORT,

        threaded=True,

        use_reloader=False
    )


def start_web_server():

    global _flask_thread

    if (
        _flask_thread is None
        or not _flask_thread.is_alive()
    ):

        _flask_thread = threading.Thread(

            target=_run_flask,

            daemon=True,

            name="Flask-Streaming"
        )

        _flask_thread.start()

        print(
            f"Web API aktif di "
            f"http://<IP_JETSON>:"
            f"{STREAM_PORT}/"
        )


# =========================================================
# START STREAMING
# =========================================================

def start_streaming():

    print()
    print(
        "=========================================="
    )
    print(
        " START CAMERA STREAMING"
    )
    print(
        "=========================================="
    )
    print()

    surface_ok = (
        _surface_grabber.start()
    )

    underwater_ok = (
        _underwater_grabber.start()
    )

    # Web server tetap dijalankan walaupun
    # salah satu kamera gagal.

    start_web_server()

    print()

    print(
        f"Surface camera   : "
        f"{'OK' if surface_ok else 'FAILED'}"
    )

    print(
        f"Underwater camera: "
        f"{'OK' if underwater_ok else 'FAILED'}"
    )

    print()


# =========================================================
# STOP STREAMING
# =========================================================

def stop_streaming():

    print(
        "Menghentikan camera streaming..."
    )

    _surface_grabber.stop()

    _underwater_grabber.stop()

    print(
        "Semua kamera sudah di-release."
    )


# =========================================================
# CAPTURE PHOTO
# =========================================================

def capture_surface_photo():

    return _surface_grabber.save_snapshot(
        SURFACE_PHOTO_DIR
    )


def capture_underwater_photo():

    return _underwater_grabber.save_snapshot(
        UNDERWATER_PHOTO_DIR
    )