#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pathlib
import time

try:
    import RPi.GPIO as GPIO
except:
    # NOTE: Raspbeery Pi 以外で動かした時は，ダミーにする
    class GPIO:
        BCM = 0
        OUT = 0

        def setmode(dummy):
            return

        def setup(dummy1, dummy2):
            return

        def output(dummy1, dummy2):
            return

        def input(dummy):
            return

        def setwarnings(dummy):
            return


import logging


# NOTE: バルブを ON にする場合，常に ON にするわけではなく，
# 次の時間(分)毎に ON と OFF を繰り返すようにする
INTERVAL_MIN_ON = 0.85
INTERVAL_MIN_OFF = 0.85

STAT_DIR_PATH = pathlib.Path("/dev/shm")
STAT_PATH_VALVE_ON = STAT_DIR_PATH / "valve_on"
STAT_PATH_VALVE_OFF = STAT_DIR_PATH / "valve_off"

# 電磁弁制御用の GPIO 端子番号．
# この端子が H 担った場合に，水が出るように回路を組んでおく．
GPIO_PIN_DEFAULT = 17

pin_no = GPIO_PIN_DEFAULT


def init(pin):
    global pin_no

    pin_no = pin


def ctrl_valve(state):
    global pin_no

    logging.info("controll valve = {state}".format(state="on" if state else "off"))

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin_no, GPIO.OUT)
    GPIO.output(pin_no, state)


def set_valve_on(interm):
    STAT_PATH_VALVE_OFF.unlink(missing_ok=True)
    if not STAT_PATH_VALVE_ON.exists():
        STAT_PATH_VALVE_ON.touch()
        logging.info("controll OFF -> ON")
        ctrl_valve(True)
        return 0

    on_duration = time.time() - STAT_PATH_VALVE_ON.stat().st_mtime
    if interm:
        if (on_duration / 60.0) < INTERVAL_MIN_ON:
            logging.info("controll ON (ON duty)")
            ctrl_valve(True)
            return on_duration
        elif (on_duration / 60.0) > (INTERVAL_MIN_ON + INTERVAL_MIN_OFF):
            STAT_PATH_VALVE_ON.touch()
            logging.info("controll ON (ON duty)")
            ctrl_valve(True)
            return 0
        else:
            logging.info("controll ON (OFF duty)")
            ctrl_valve(False)
            return 0
    else:
        logging.info("controll ON")
        return on_duration


def set_valve_off(interm):
    STAT_PATH_VALVE_ON.unlink(missing_ok=True)

    if not STAT_PATH_VALVE_OFF.exists():
        STAT_PATH_VALVE_OFF.touch()
        logging.info("controll ON -> OFF")
        ctrl_valve(False)
        return 0
    else:
        logging.info("controll OFF")
        return time.time() - STAT_PATH_VALVE_OFF.stat().st_mtime


# バルブを間欠制御し，実際にバルブを開いたり閉じたりしてからの経過時間(秒)を出力します
def set_state(state, interm=True):
    if state:
        return set_valve_on(interm)
    else:
        return set_valve_off(interm)


# 実際のバルブの状態を返します
def get_state():
    global pin_no

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin_no, GPIO.OUT)

    return GPIO.input(pin_no)


if __name__ == "__main__":
    import logger

    logger.init("test")

    GPIO_PIN = 17
    init(GPIO_PIN)

    while True:
        set_state(True)
        print(get_state())
        time.sleep(60)
