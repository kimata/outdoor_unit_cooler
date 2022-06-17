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
INTERVAL_MIN_ON = 2
INTERVAL_MIN_OFF = 2

GPIO_PIN = 17

STAT_DIR_PATH = pathlib.Path("/dev/shm")
STAT_PATH_VALVE_ON = STAT_DIR_PATH / "valve_on"
STAT_PATH_VALVE_OFF = STAT_DIR_PATH / "valve_off"


def ctrl_valve(state):
    logging.info("controll valve = {state}".format(state="on" if state else "off"))

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_PIN, GPIO.OUT)
    GPIO.output(GPIO_PIN, state)


def set_valve_on():
    STAT_PATH_VALVE_OFF.unlink(missing_ok=True)
    if not STAT_PATH_VALVE_ON.exists():
        STAT_PATH_VALVE_ON.touch()
        logging.info("controll OFF -> ON")
        ctrl_valve(True)
        return 0
    else:
        on_duration = time.time() - STAT_PATH_VALVE_ON.stat().st_mtime
        if (on_duration / 60) < INTERVAL_MIN_ON:
            logging.info("controll ON (ON duty)")
            ctrl_valve(True)
            return on_duration
        elif (on_duration / 60) > (INTERVAL_MIN_ON + INTERVAL_MIN_OFF):
            STAT_PATH_VALVE_ON.touch()
            logging.info("controll ON (ON duty)")
            ctrl_valve(True)
            return 0
        else:
            logging.info("controll ON (OFF duty)")
            ctrl_valve(False)
            return 0


def set_valve_off():
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
def set_state(state):
    if state:
        return set_valve_on()
    else:
        return set_valve_off()


# 実際のバルブの状態を返します
def get_state():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_PIN, GPIO.OUT)

    return GPIO.input(GPIO_PIN)


if __name__ == "__main__":
    import logger

    logger.init("test")

    while True:
        set_state(True)
        print(get_state())
        time.sleep(60)
