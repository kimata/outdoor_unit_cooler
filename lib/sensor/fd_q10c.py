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


def sense(force_power_on=True):
    if not _acquire():
        raise RuntimeError("Unable to acquire the lock.")

    try:
        spi = driver.com_open()

        if force_power_on or driver.com_status(spi):
            ser = driver.com_start(spi)

            flow = round(
                driver.isdu_read(spi, ser, 0x94, driver.DATA_TYPE_UINT16) * 0.01, 2
            )
            logging.info("flow: {flow:.2f} L/min".format(flow=flow))

            driver.com_stop(spi, ser)
            driver.com_close(spi)
        else:
            flow = None

        _release()

        return flow
    except:
        driver.com_close(spi)

        _release()
        raise


def stop():
    if not _acquire():
        raise RuntimeError("Unable to acquire the lock.")

    try:
        spi = driver.com_open()
        driver.com_stop(spi, is_power_off=True)
        driver.com_close(spi)
        _release()
    except:
        driver.com_close(spi)
        _release()
        raise


def _acquire():
    global lock_fd
    lock_fd = os.open(LOCK_FILE_PATH, os.O_RDWR | os.O_CREAT | os.O_TRUNC)

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

    logger.init("test", level=logging.DEBUG)

    sense()
