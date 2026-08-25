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


def set_motor_data(
    left_rpm,
    right_rpm,
    speed_mps,
    direction
):

    global _motor_data

    direction = str(
        direction
    ).upper()


    if direction not in (
        "FORWARD",
        "REVERSE",
        "STOP"
    ):

        direction = "STOP"


    if direction == "STOP":

        speed_mps = 0.0

    elif direction == "FORWARD":

        speed_mps = abs(
            float(speed_mps)
        )

    elif direction == "REVERSE":

        speed_mps = -abs(
            float(speed_mps)
        )


    with _motor_lock:

        _motor_data = {

            "left_rpm": float(
                left_rpm
            ),

            "right_rpm": float(
                right_rpm
            ),

            "speed_mps": float(
                speed_mps
            ),

            "direction": direction,

            "updated_at": time.time()
        }


def get_motor_data():

    with _motor_lock:

        return dict(
            _motor_data
        )