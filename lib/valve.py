#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from enum import IntEnum
import pathlib
import time
import logging

try:
    import RPi.GPIO as GPIO
except:
    # NOTE: Raspbeery Pi 以外で動かした時は，ダミーにする
    class GPIO:
        BCM = 0
        OUT = 0
        state = 0

        def setmode(mode):
            return

        def setup(gpio, direction):
            return

        def output(gpio, value):
            GPIO.state = value
            return

        def input(gpio):
            return GPIO.state

        def setwarnings(warnings):
            return


class VALVE_STATE(IntEnum):
    OPEN = 1
    CLOSE = 0


class COOLING_STATE(IntEnum):
    WORKING = 1
    IDLE = 0


STAT_DIR_PATH = pathlib.Path("/dev/shm")

# STATE が WORKING になった際に作られるファイル．Duty 制御している場合，
# OFF Duty から ON Duty に遷移する度に変更日時が更新される．
# STATE が IDLE になった際に削除される．
# (OFF Duty になって実際にバルブを閉じただけでは削除されない)
STAT_PATH_VALVE_STATE_WORKING = STAT_DIR_PATH / "valve_state_working"

# STATE が IDLE になった際に作られるファイル．
# (OFF Duty になって実際にバルブを閉じただけでは作られない)
# STATE が WORKING になった際に削除される．
STAT_PATH_VALVE_STATE_IDLE = STAT_DIR_PATH / "valve_state_idle"

# 実際にバルブを開いた際に作られるファイル．
# 実際にバルブを閉じた際に削除される．
STAT_PATH_VALVE_OPEN = STAT_DIR_PATH / "valve_open"

# 実際にバルブを閉じた際に作られるファイル．
# 実際にバルブを開いた際に削除される．
STAT_PATH_VALVE_CLOSE = STAT_DIR_PATH / "valve_close"

# 電磁弁制御用の GPIO 端子番号．
# この端子が H になった場合に，水が出るように回路を組んでおく．
GPIO_PIN_DEFAULT = 17

pin_no = GPIO_PIN_DEFAULT


def init(pin):
    global pin_no
    pin_no = pin

    STAT_PATH_VALVE_STATE_WORKING.unlink(missing_ok=True)
    STAT_PATH_VALVE_STATE_IDLE.touch()

    set_valve_state(VALVE_STATE.CLOSE)


# NOTE: 実際にバルブを開きます．
# 現在のバルブの状態と，バルブが現在の状態になってからの経過時間を返します．
def set_valve_state(valve_state):
    global pin_no

    curr_state = get_valve_state()

    if valve_state != curr_state:
        logging.info(
            "VALVE: {curr_state} -> {valve_state}".format(
                curr_state=curr_state.name, valve_state=valve_state.name
            )
        )

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin_no, GPIO.OUT)
    GPIO.output(pin_no, valve_state.value)

    if valve_state:
        STAT_PATH_VALVE_CLOSE.unlink(missing_ok=True)
        if STAT_PATH_VALVE_OPEN.exists():
            return (valve_state, time.time() - STAT_PATH_VALVE_OPEN.stat().st_mtime)
        else:
            STAT_PATH_VALVE_OPEN.touch()
            return (valve_state, 0)
    else:
        STAT_PATH_VALVE_OPEN.unlink(missing_ok=True)
        if STAT_PATH_VALVE_CLOSE.exists():
            return (valve_state, time.time() - STAT_PATH_VALVE_CLOSE.stat().st_mtime)
        else:
            STAT_PATH_VALVE_CLOSE.touch()
            return (valve_state, 0)


# NOTE: 実際のバルブの状態を返します
def get_valve_state():
    global pin_no

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin_no, GPIO.OUT)

    if GPIO.input(pin_no) == 1:
        return VALVE_STATE.OPEN
    else:
        return VALVE_STATE.CLOSE


# def get_interval_on(interm):
#     return INTERVAL_MIN_ON


# def get_interval_off(interm):
#     if interm == INTERM.LONG:
#         return INTERVAL_MIN_OFF * INTERVAL_SCALE
#     else:
#         return INTERVAL_MIN_OFF


# cooling_mode = {
#     "state": COOLER_STATE.IDLE,
#     "duty": {  "mode": False  }
# }


# NOTE: バルブを動作状態にします．
# Duty 制御を実現するため，OFF Duty 期間の場合はバルブを閉じます．
# 実際にバルブを開いてからの経過時間を返します．
# duty_info = { "mode": bool, "on": on_min, "off": off_min }
def set_cooling_working(duty_info):
    STAT_PATH_VALVE_STATE_IDLE.unlink(missing_ok=True)

    if not STAT_PATH_VALVE_STATE_WORKING.exists():
        STAT_PATH_VALVE_STATE_WORKING.touch()
        logging.info("COOLING: IDLE -> WORKING")
        return set_valve_state(VALVE_STATE.OPEN)

    if not duty_info["enable"]:
        # NOTE Duty 制御しない場合
        return set_valve_state(VALVE_STATE.OPEN)

    on_duration_sec = time.time() - STAT_PATH_VALVE_STATE_WORKING.stat().st_mtime

    if on_duration_sec < (duty_info["on_min"] * 60):
        logging.info(
            "COOLING: WORKING (ON duty, {left:.0f} sec left)".format(
                left=(duty_info["on_min"] * 60) - on_duration_sec
            )
        )
        return set_valve_state(VALVE_STATE.OPEN)
    elif on_duration_sec > ((duty_info["on_min"] + duty_info["off_min"]) * 60):
        STAT_PATH_VALVE_STATE_WORKING.touch()
        logging.info(
            "COOLING: WORKING (ON duty, {left:.0f} sec left)".format(
                left=((2 * duty_info["on_min"] + duty_info["off_min"]) * 60)
                - on_duration_sec
            )
        )
        return set_valve_state(VALVE_STATE.OPEN)
    else:
        logging.info(
            "COOLING: WORKING (OFF duty, {left:.0f} sec left)".format(
                left=((duty_info["on_min"] + duty_info["off_min"]) * 60)
                - on_duration_sec
            )
        )
        return set_valve_state(VALVE_STATE.CLOSE)


def set_cooling_idle():
    STAT_PATH_VALVE_STATE_WORKING.unlink(missing_ok=True)

    if not STAT_PATH_VALVE_STATE_IDLE.exists():
        STAT_PATH_VALVE_STATE_IDLE.touch()
        logging.info("COOLING: WORKING -> IDLE")
        return set_valve_state(VALVE_STATE.CLOSE)
    else:
        return set_valve_state(VALVE_STATE.CLOSE)


def set_cooling_state(cooling_mode):
    if cooling_mode["state"] == COOLING_STATE.WORKING:
        return set_cooling_working(cooling_mode["duty"])
    else:
        return set_cooling_idle()


if __name__ == "__main__":
    import logger

    logger.init("test", level=logging.INFO)

    GPIO_PIN = 17
    init(GPIO_PIN)

    while True:
        set_cooling_state(
            {
                "state": COOLING_STATE.WORKING,
                "duty": {"enable": True, "on_min": 1, "off_min": 2},
            }
        )
        time.sleep(30)
