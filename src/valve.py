#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import pathlib
import time
import logging
import logging.handlers

sys.path.append(os.path.join(os.path.dirname(__file__)))

import logger

# NOTE: バルブを ON にする場合，常に ON にするわけではなく，
# 次の時間(分)毎に ON と OFF を繰り返すようにする
INTERVAL_MIN_ON = 2
INTERVAL_MIN_OFF = 8

STAT_DIR_PATH = pathlib.Path("/dev/shm")
STAT_PATH_VALVE_ON = STAT_DIR_PATH / "valve_on"
STAT_PATH_VALVE_OFF = STAT_DIR_PATH / "valve_off"


def ctrl_valve(state):
    logging.info("controll valve = {state}".format(state="on" if state else "off"))


def set_valve_on():
    STAT_PATH_VALVE_OFF.unlink(missing_ok=True)
    if not STAT_PATH_VALVE_ON.exists():
        STAT_PATH_VALVE_ON.touch()
        logging.info("controll OFF -> ON")
        ctrl_valve(True)
    else:
        on_duration = (time.time() - STAT_PATH_VALVE_ON.stat().st_mtime) / 60
        if on_duration < INTERVAL_MIN_ON:
            logging.info("controll ON (ON duty)")
            ctrl_valve(True)
        elif on_duration > (INTERVAL_MIN_ON + INTERVAL_MIN_OFF):
            STAT_PATH_VALVE_ON.touch()
            logging.info("controll ON (ON duty)")
            ctrl_valve(True)
        else:
            logging.info("controll ON (OFF duty)")
            ctrl_valve(False)


def set_valve_off():
    STAT_PATH_VALVE_ON.unlink(missing_ok=True)

    if not STAT_PATH_VALVE_OFF.exists:
        STAT_PATH_VALVE_OFF.touch()
        logging.info("controll ON -> OFF")
        ctrl_valve(False)
    else:
        STAT_PATH_VALVE_OFF.touch()
        logging.info("controll OFF")


def set_valve(state):
    if state:
        set_valve_on()
    else:
        set_valve_off()


if __name__ == "__main__":
    logger.init("test")

    while True:
        set_valve(True)
        time.sleep(60)
