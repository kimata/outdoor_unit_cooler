#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import pathlib
import time
import logging
import threading
import traceback
import datetime
from valve_state import VALVE_STATE, COOLING_STATE
from work_log import work_log

if os.environ.get("DUMMY_MODE", "false") != "true":  # pragma: no cover
    import RPi.GPIO as GPIO
    from sensor.fd_q10c import FD_Q10C
else:
    # NOTE: 本物の GPIO のように振る舞うダミーのライブラリ
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

    class FD_Q10C:
        def __init__(self, lock_file="DUMMY", timeout=2):
            pass

        def get_value(self, force_power_on=True):
            if GPIO.state == VALVE_STATE.OPEN.value:
                return 1.23
            else:
                return 0

        def get_state(self):
            return True

        def stop(self):
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
valve_lock = None
ctrl_hist = []


def init(pin=GPIO_PIN_DEFAULT):
    global pin_no
    global valve_lock
    global fd_q10c

    fd_q10c = FD_Q10C()
    pin_no = pin
    valve_lock = threading.Lock()

    STAT_PATH_VALVE_STATE_WORKING.unlink(missing_ok=True)
    STAT_PATH_VALVE_STATE_IDLE.parent.mkdir(parents=True, exist_ok=True)
    STAT_PATH_VALVE_STATE_IDLE.touch()

    set_state(VALVE_STATE.CLOSE)


# NOTE: テスト用
def clear_stat():
    global ctrl_hist

    STAT_PATH_VALVE_STATE_WORKING.unlink(missing_ok=True)
    STAT_PATH_VALVE_STATE_IDLE.unlink(missing_ok=True)
    STAT_PATH_VALVE_OPEN.unlink(missing_ok=True)
    STAT_PATH_VALVE_CLOSE.unlink(missing_ok=True)
    ctrl_hist = []


# NOTE: テスト用
def get_hist():
    global ctrl_hist

    return ctrl_hist


# NOTE: 実際にバルブを開きます．
# 現在のバルブの状態と，バルブが現在の状態になってからの経過時間を返します．
def set_state(valve_state):
    global pin_no
    global valve_lock
    global ctrl_hist

    with valve_lock:
        curr_state = get_state()

        if valve_state != curr_state:
            logging.info(
                "VALVE: {curr_state} -> {valve_state}".format(
                    curr_state=curr_state.name, valve_state=valve_state.name
                )
            )
            ctrl_hist.append(curr_state)

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin_no, GPIO.OUT)
        GPIO.output(pin_no, valve_state.value)

        if valve_state == VALVE_STATE.OPEN:
            STAT_PATH_VALVE_CLOSE.unlink(missing_ok=True)
            if not STAT_PATH_VALVE_OPEN.exists():
                STAT_PATH_VALVE_OPEN.parent.mkdir(parents=True, exist_ok=True)
                set_start_time(STAT_PATH_VALVE_OPEN)
        else:
            STAT_PATH_VALVE_OPEN.unlink(missing_ok=True)
            if not STAT_PATH_VALVE_CLOSE.exists():
                STAT_PATH_VALVE_CLOSE.parent.mkdir(parents=True, exist_ok=True)
                set_start_time(STAT_PATH_VALVE_CLOSE)

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


def get_duration(stat_file):
    with open(stat_file, "r") as f:
        start = datetime.datetime.fromtimestamp(int(f.read()))
        now = datetime.datetime.now()

        return int((now - start).total_seconds())


def set_start_time(stat_file):
    with open(stat_file, "w") as f:
        f.write(str(int(datetime.datetime.now().timestamp())))


# NOTE: 実際のバルブの状態と，その状態になってからの経過時間を返します
def get_status():
    global valve_lock

    with valve_lock:
        valve_state = get_state()

        if valve_state == VALVE_STATE.OPEN:
            assert STAT_PATH_VALVE_OPEN.exists()

            return {
                "state": valve_state,
                "duration": get_duration(STAT_PATH_VALVE_OPEN),
            }
        else:
            if STAT_PATH_VALVE_CLOSE.exists():
                return {
                    "state": valve_state,
                    "duration": get_duration(STAT_PATH_VALVE_CLOSE),
                }
            else:
                return {"state": valve_state, "duration": 0}


def stop_flow_monitor():
    global fd_q10c

    fd_q10c.stop()


def get_power_state():
    global fd_q10c

    return fd_q10c.get_state()


def get_flow(force_power_on=True):
    global fd_q10c

    try:
        flow = fd_q10c.get_value(force_power_on)
    except:
        logging.error("バグの可能性あり．")
        logging.error(traceback.format_exc())
        flow = None

    if flow is not None:
        logging.info("Valve flow = {flow:.2f}".format(flow=flow))
    else:
        logging.info("Valve flow = UNKNOWN")

    return flow


def stop_sensing():
    global fd_q10c

    logging.info("Stop flow sensing")

    try:
        fd_q10c.stop()
    except RuntimeError as e:
        logging.error(str(e))


# NOTE: バルブを動作状態にします．
# Duty 制御を実現するため，OFF Duty 期間の場合はバルブを閉じます．
# 実際にバルブを開いてからの経過時間を返します．
# duty_info = { "enable": bool, "on": on_sec, "off": off_sec }
def set_cooling_working(duty_info):
    STAT_PATH_VALVE_STATE_IDLE.unlink(missing_ok=True)

    if not STAT_PATH_VALVE_STATE_WORKING.exists():
        STAT_PATH_VALVE_STATE_WORKING.parent.mkdir(parents=True, exist_ok=True)
        STAT_PATH_VALVE_STATE_WORKING.touch()
        work_log("冷却を開始します．")
        logging.info("COOLING: IDLE -> WORKING")
        return set_state(VALVE_STATE.OPEN)

    if not duty_info["enable"]:
        # NOTE Duty 制御しない場合
        logging.info("COOLING: WORKING")
        return set_state(VALVE_STATE.OPEN)

    status = get_status()

    logging.info([status["duration"], duty_info["on_sec"]])

    if status["state"] == VALVE_STATE.OPEN:
        # NOTE: 現在バルブが開かれている
        if status["duration"] >= duty_info["on_sec"]:
            logging.info(
                "COOLING: WORKING (OFF duty, {left:.0f} sec left)".format(
                    left=duty_info["off_sec"]
                )
            )
            work_log("OFF Duty になったのでバルブを締めます．")
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
            work_log("ON Duty になったのでバルブを開けます．")
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
        work_log("冷却を停止しました．")
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
                "mode_index": 1,
                "duty": {"enable": True, "on_sec": 1, "off_sec": 2},
            }
        )
        time.sleep(30)
