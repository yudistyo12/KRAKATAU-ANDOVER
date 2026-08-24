#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cv2
import os
import time
import threading

from flask import Flask, Response, send_from_directory, abort, jsonify

from gps import get_gps_data

# =========================================================
# IMPORT HEARTBEAT DARI MAIN
# =========================================================
try:
    from main import update_gcs_heartbeat
except ImportError:
    # Fallback dummy agar video_stream tetap bisa di-test mandiri
    def update_gcs_heartbeat():
        pass


# =========================================================
# CONFIG
# =========================================================

SURFACE_CAMERA_INDEX = 0
UNDERWATER_CAMERA_INDEX = 2

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


# =========================================================
# CAMERA CONFIG
# =========================================================

SURFACE_WIDTH = 640
SURFACE_HEIGHT = 480
SURFACE_FPS = 30
SURFACE_FORMAT = "YUYV"

UNDERWATER_WIDTH = 640
UNDERWATER_HEIGHT = 480
UNDERWATER_FPS = 30
UNDERWATER_FORMAT = "MJPG"


# =========================================================
# STREAM CONFIG
# =========================================================

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

    def start(self):
        if self.running:
            print(f"Kamera {self.label} sudah berjalan")
            return

        print(f"Membuka kamera {self.label} /dev/video{self.camera_index}...")

        self.cap = cv2.VideoCapture(
            self.camera_index,
            cv2.CAP_V4L2
        )

        if not self.cap.isOpened():
            print(f"ERROR: kamera {self.label} tidak dapat dibuka")
            self.cap = None
            return

        fourcc = cv2.VideoWriter_fourcc(*self.pixel_format)
        self.cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)

        print(
            f"Kamera {self.label}: "
            f"{actual_width}x{actual_height} "
            f"@ {actual_fps:.1f} FPS "
            f"| {self.pixel_format}"
        )

        self.running = True
        self.thread = threading.Thread(
            target=self._read_loop,
            daemon=True,
            name=f"Camera-{self.label}"
        )
        self.thread.start()
        print(f"Streaming kamera {self.label} dimulai")

    def _read_loop(self):
        interval = 1.0 / READ_FPS
        while self.running:
            if self.cap is None:
                break

            ret, frame = self.cap.read()
            if ret:
                if self.rotate_left:
                    frame = cv2.rotate(
                        frame,
                        cv2.ROTATE_90_COUNTERCLOCKWISE
                    )

                with self.frame_lock:
                    self.latest_frame = frame
            else:
                print(f"WARNING: gagal membaca kamera {self.label}")

            time.sleep(interval)

    def stop(self):
        if not self.running:
            return

        print(f"Menghentikan kamera {self.label}...")
        self.running = False

        if self.thread is not None:
            if self.thread.is_alive():
                self.thread.join(timeout=2.0)
        self.thread = None

        if self.cap is not None:
            try:
                self.cap.release()
            except Exception as e:
                print(f"WARNING release {self.label}: {e}")
            self.cap = None

        with self.frame_lock:
            self.latest_frame = None

        print(f"Kamera {self.label} berhasil dihentikan")

    def get_frame(self):
        with self.frame_lock:
            return self.latest_frame

    def save_snapshot(self, save_dir):
        frame = self.get_frame()
        if frame is None:
            print(f"ERROR: belum ada frame {self.label}")
            return None

        os.makedirs(save_dir, exist_ok=True)
        filename = os.path.join(
            save_dir,
            f"{self.label}_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
        )

        success = cv2.imwrite(
            filename,
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
        )

        if not success:
            print(f"ERROR: gagal menyimpan foto {self.label}")
            return None

        print(f"Foto {self.label} disimpan: {filename}")
        return filename


# =========================================================
# CAMERA OBJECTS
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
# FLASK APP
# =========================================================

app = Flask(__name__)


# =========================================================
# CORS & OPTIONS HANDLER
# =========================================================

@app.after_request
def _add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# =========================================================
# GCS FAILSAFE HEARTBEAT ROUTE
# =========================================================

@app.route("/ping_gcs", methods=["POST", "OPTIONS"])
def ping_gcs():
    update_gcs_heartbeat()
    return jsonify({"status": "ok"}), 200


# =========================================================
# GPS TELEMETRY
# =========================================================

@app.route("/telemetry")
def telemetry():
    data = get_gps_data()
    speed_knots = data["speed_knots"]

    response = jsonify({
        "lat": data["latitude"],
        "lon": data["longitude"],
        "speed": (
            speed_knots * 0.514444
            if speed_knots is not None
            else None
        ),
        "course": data["course"] if data["course"] is not None else data["heading"],
        "heading": data["heading"],
        "fix": data["fix"],
        "speed_knots": speed_knots,
        "speed_kmh": data["speed_kmh"],
        "timestamp": data["timestamp"]
    })

    response.headers["Cache-Control"] = "no-store"
    return response


# =========================================================
# MJPEG GENERATOR
# =========================================================

def _mjpeg_generator(grabber):
    while True:
        frame = grabber.get_frame()
        if frame is not None:
            ok, buffer = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
            )

            if ok:
                jpg_bytes = buffer.tobytes()
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + jpg_bytes
                    + b"\r\n"
                )

        time.sleep(1.0 / READ_FPS)


# =========================================================
# PHOTO DIRECTORIES & API
# =========================================================

_PHOTO_DIRS = {
    "surface": SURFACE_PHOTO_DIR,
    "underwater": UNDERWATER_PHOTO_DIR
}

def _list_photos(photo_dir):
    if not os.path.isdir(photo_dir):
        return []

    files = [
        f for f in os.listdir(photo_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    files.sort(reverse=True)
    return files


@app.route("/api/photos/<camera>")
def api_list_photos(camera):
    photo_dir = _PHOTO_DIRS.get(camera)
    if photo_dir is None:
        abort(404)

    files = _list_photos(photo_dir)
    response = jsonify({
        "camera": camera,
        "count": len(files),
        "photos": [f"/photos/{camera}/{fn}" for fn in files]
    })
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


@app.route("/photos/<camera>/<path:filename>")
def get_photo_file(camera, filename):
    photo_dir = _PHOTO_DIRS.get(camera)
    if photo_dir is None:
        abort(404)

    return send_from_directory(photo_dir, filename)


# =========================================================
# CAMERA FEEDS
# =========================================================

@app.route("/surface_feed")
def surface_feed():
    return Response(
        _mjpeg_generator(_surface_grabber),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/underwater_feed")
def underwater_feed():
    return Response(
        _mjpeg_generator(_underwater_grabber),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


# =========================================================
# FLASK SERVER THREAD CONTROL
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
    if _flask_thread is None or not _flask_thread.is_alive():
        _flask_thread = threading.Thread(
            target=_run_flask,
            daemon=True,
            name="Flask-Streaming"
        )
        _flask_thread.start()
        print(f"Web API aktif di http://<IP_JETSON>:{STREAM_PORT}/")


def start_streaming():
    print("\n==========================================")
    print(" START CAMERA STREAMING")
    print("==========================================\n")

    _surface_grabber.start()
    _underwater_grabber.start()
    start_web_server()


def stop_streaming():
    _surface_grabber.stop()
    _underwater_grabber.stop()
    print("Semua kamera sudah di-release.")


# =========================================================
# CAPTURE PHOTO WRAPPERS
# =========================================================

def capture_surface_photo():
    return _surface_grabber.save_snapshot(SURFACE_PHOTO_DIR)


def capture_underwater_photo():
    return _underwater_grabber.save_snapshot(UNDERWATER_PHOTO_DIR)