#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# KEYENCE のクランプオン式流量センサ FD-Q10C と IO-LINK で通信を行なって
# 流量を取得するスクリプトです．

import os
import time
import fcntl
import logging

import ltc2874 as driver

LOCK_FILE_PATH = "/dev/shm/fd_q10c.lock"
TIMEOUT_SEC = 5

lock_fd = None


def sense(is_power_on=True):
    if not _acquire():
        raise RuntimeError("ロックを取得できませんでした．")

    try:
        spi = driver.com_open()

        if is_power_on or driver.com_status():
            ser = driver.com_start(spi)

            flow = driver.isdu_read(spi, ser, 0x94, driver.DATA_TYPE_UINT16) * 0.01
            logging.info("flow: {flow} L/min".format(flow=flow))

            driver.com_stop(spi, ser)
        else:
            flow = 0

        _release()

        return round(flow, 2)
    except RuntimeError:
        driver.com_stop(spi, ser, True)

        _release()
        raise


def stop():
    if not _acquire():
        raise RuntimeError("ロックを取得できませんでした．")

    try:
        spi = driver.com_open()
        ser = driver.com_start(spi)
        driver.com_stop(spi, ser, True)
        _release()
    except RuntimeError:
        _release()
        raise


def _acquire():
    global lock_fd
    lock_fd = os.open(LOCK_FILE_PATH, os.O_RDWR | os.O_CREAT | os.O_TRUNC)

    timeout = 5.0
    time_start = time.time()
    while time.time() < time_start + TIMEOUT_SEC:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            pass
        else:
            return True
        time.sleep(1)
    os.close(lock_fd)
    lock_fd = None

    return False


def _release():
    global lock_fd

    if lock_fd is None:
        return
    fcntl.flock(lock_fd, fcntl.LOCK_UN)
    os.close(lock_fd)

    lock_fd = None


if __name__ == "__main__":
    import logger

    logger.init("test")

    sense()
