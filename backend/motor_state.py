#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
import time

_motor_lock = threading.Lock()
_motor_data = {
    "left_rpm": 0.0,
    "right_rpm": 0.0,
    "speed_mps": 0.0,
    "direction": "STOP",
    "updated_at": 0.0,
}

def set_motor_data(left_rpm, right_rpm, speed_mps, direction):
    global _motor_data
    with _motor_lock:
        _motor_data = {
            "left_rpm": float(left_rpm),
            "right_rpm": float(right_rpm),
            "speed_mps": float(speed_mps),
            "direction": str(direction).upper(),
            "updated_at": time.time(),
        }

def get_motor_data():
    with _motor_lock:
        return dict(_motor_data)