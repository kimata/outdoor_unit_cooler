#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from enum import IntEnum
import os
import pathlib
import time
import logging
import traceback


class VALVE_STATE(IntEnum):
    OPEN = 1
    CLOSE = 0


class COOLING_STATE(IntEnum):
    WORKING = 1
    IDLE = 0


try:
    import RPi.GPIO as GPIO
    import fd_q10c
except:
    logging.warning("Using dummy GPIO")

    # NOTE: Raspbeery Pi 以外で動かした時は，ダミーにする
    class GPIO:
        IS_DUMMY = True
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

    class fd_q10c:
        def sense(force_power_on=True):
            if GPIO.state == VALVE_STATE.OPEN.value:
                return 1.23
            else:
                return 0

        def stop():
            return


STAT_DIR_PATH = pathlib.Path("/dev/shm")

# STATE が WORKING になった際に作られるファイル．Duty 制御している場合，
# OFF Duty から ON Duty に遷移する度に変更日時が更新される．
# STATE が IDLE になった際に削除される．
# (OFF Duty になって実際にバルブを閉じただけでは削除されない)
STAT_PATH_VALVE_STATE_WORKING = (
    STAT_DIR_PATH / "unit_cooler" / "valve" / "state" / "working"
)

# STATE が IDLE になった際に作られるファイル．
# (OFF Duty になって実際にバルブを閉じただけでは作られない)
# STATE が WORKING になった際に削除される．
STAT_PATH_VALVE_STATE_IDLE = STAT_DIR_PATH / "unit_cooler" / "valve" / "state" / "idle"

# 実際にバルブを開いた際に作られるファイル．
# 実際にバルブを閉じた際に削除される．
STAT_PATH_VALVE_OPEN = STAT_DIR_PATH / "unit_cooler" / "valve" / "open"

# 実際にバルブを閉じた際に作られるファイル．
# 実際にバルブを開いた際に削除される．
STAT_PATH_VALVE_CLOSE = STAT_DIR_PATH / "unit_cooler" / "valve" / "close"


# 電磁弁制御用の GPIO 端子番号．
# この端子が H になった場合に，水が出るように回路を組んでおく．
GPIO_PIN_DEFAULT = 17

pin_no = GPIO_PIN_DEFAULT


def init(pin=GPIO_PIN_DEFAULT):
    global pin_no
    pin_no = pin

    STAT_PATH_VALVE_STATE_WORKING.unlink(missing_ok=True)
    STAT_PATH_VALVE_STATE_IDLE.parent.mkdir(parents=True, exist_ok=True)
    STAT_PATH_VALVE_STATE_IDLE.touch()

    set_state(VALVE_STATE.CLOSE)


# NOTE: 実際にバルブを開きます．
# 現在のバルブの状態と，バルブが現在の状態になってからの経過時間を返します．
def set_state(valve_state):
    global pin_no

    curr_state = get_state()

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

    if valve_state == VALVE_STATE.OPEN:
        STAT_PATH_VALVE_CLOSE.unlink(missing_ok=True)
        if not STAT_PATH_VALVE_OPEN.exists():
            STAT_PATH_VALVE_OPEN.parent.mkdir(parents=True, exist_ok=True)
            STAT_PATH_VALVE_OPEN.touch()
    else:
        STAT_PATH_VALVE_OPEN.unlink(missing_ok=True)
        if not STAT_PATH_VALVE_CLOSE.exists():
            STAT_PATH_VALVE_CLOSE.parent.mkdir(parents=True, exist_ok=True)
            STAT_PATH_VALVE_CLOSE.touch()

    return get_status()


# NOTE: 実際のバルブの状態を返します
def get_state():
    global pin_no

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin_no, GPIO.OUT)

    if GPIO.input(pin_no) == 1:
        return VALVE_STATE.OPEN
    else:
        return VALVE_STATE.CLOSE


# NOTE: 実際のバルブの状態と，その状態になってからの経過時間を返します
def get_status():
    valve_state = get_state()

    if valve_state == VALVE_STATE.OPEN:
        return {
            "state": valve_state,
            "duration": time.time() - STAT_PATH_VALVE_OPEN.stat().st_mtime,
        }
    else:
        if STAT_PATH_VALVE_CLOSE.exists():
            return {
                "state": valve_state,
                "duration": time.time() - STAT_PATH_VALVE_CLOSE.stat().st_mtime,
            }
        else:
            return {"state": valve_state, "duration": 0}


def get_flow(force_power_on=True):
    try:
        flow = fd_q10c.sense(force_power_on)
    except:
        logging.error("バグの可能性あり．")
        logging.error(traceback.format_exc())
        flow = None

    if flow is not None:
        logging.debug("Valve flow = {flow:.2f}".format(flow=flow))
    else:
        logging.debug("Valve flow = UNKNOWN")

    return flow


def stop_sensing():
    logging.info("Stop flow sensing")

    try:
        fd_q10c.stop()
    except RuntimeError as e:
        logging.error(e.name)


# NOTE: バルブを動作状態にします．
# Duty 制御を実現するため，OFF Duty 期間の場合はバルブを閉じます．
# 実際にバルブを開いてからの経過時間を返します．
# duty_info = { "enable": bool, "on": on_sec, "off": off_sec }
def set_cooling_working(duty_info):
    STAT_PATH_VALVE_STATE_IDLE.unlink(missing_ok=True)

    if not STAT_PATH_VALVE_STATE_WORKING.exists():
        STAT_PATH_VALVE_STATE_WORKING.parent.mkdir(parents=True, exist_ok=True)
        STAT_PATH_VALVE_STATE_WORKING.touch()
        logging.info("COOLING: IDLE -> WORKING")
        return set_state(VALVE_STATE.OPEN)

    if not duty_info["enable"]:
        # NOTE Duty 制御しない場合
        logging.info("COOLING: WORKING")
        return set_state(VALVE_STATE.OPEN)

    status = get_status()

    if status["state"] == VALVE_STATE.OPEN:
        # NOTE: 現在バルブが開かれている
        if status["duration"] >= duty_info["on_sec"]:
            logging.info(
                "COOLING: WORKING (OFF duty, {left:.0f} sec left)".format(
                    left=duty_info["off_sec"]
                )
            )
            return set_state(VALVE_STATE.CLOSE)
        else:
            logging.info(
                "COOLING: WORKING (ON duty, {left:.0f} sec left)".format(
                    left=duty_info["on_sec"] - status["duration"]
                )
            )
            return set_state(VALVE_STATE.OPEN)
    else:
        # NOTE: 現在バルブが閉じられている
        if status["duration"] >= duty_info["off_sec"]:
            logging.info(
                "COOLING: WORKING (ON duty, {left:.0f} sec left)".format(
                    left=duty_info["on_sec"]
                )
            )
            return set_state(VALVE_STATE.OPEN)
        else:
            logging.info(
                "COOLING: WORKING (OFF duty, {left:.0f} sec left)".format(
                    left=duty_info["off_sec"] - status["duration"]
                )
            )
            return set_state(VALVE_STATE.CLOSE)


def set_cooling_idle():
    STAT_PATH_VALVE_STATE_WORKING.unlink(missing_ok=True)

    if not STAT_PATH_VALVE_STATE_IDLE.exists():
        STAT_PATH_VALVE_STATE_IDLE.parent.mkdir(parents=True, exist_ok=True)
        STAT_PATH_VALVE_STATE_IDLE.touch()
        logging.info("COOLING: WORKING -> IDLE")
        return set_state(VALVE_STATE.CLOSE)
    else:
        logging.info("COOLING: IDLE")
        return set_state(VALVE_STATE.CLOSE)


def set_cooling_state(cooling_mode):
    if cooling_mode["state"] == COOLING_STATE.WORKING:
        return set_cooling_working(cooling_mode["duty"])
    else:
        return set_cooling_idle()


if __name__ == "__main__":
    import logger

    logger.init("test", level=logging.INFO)

    init()

    while True:
        set_cooling_state(
            {
                "state": COOLING_STATE.WORKING,
                "duty": {"enable": True, "on_sec": 1, "off_sec": 2},
            }
        )
        time.sleep(30)
