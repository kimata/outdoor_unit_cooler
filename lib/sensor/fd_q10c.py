#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KEYENCE のクランプオン式流量センサ FD-Q10C と IO-LINK で通信を行なって
流量を取得するスクリプトです．

Usage:
  fd_q10c.py [-l LOCK] [-t TIMEOUT]

Options:
  -l LOCK       : ロックファイル． [default: /dev/shm/fd_q10c.lock]
  -t TIMEOUT    : タイムアウト時間． [default: 5]
"""

import os
import time
import fcntl
import logging
import sys
import pathlib
import traceback

if __name__ == "__main__":
    sys.path.append(str(pathlib.Path(__file__).parent.parent))

import sensor.ltc2874 as driver


class FD_Q10C:
    NAME = "FD_Q10C"
    LOCK_FILE = "/dev/shm/fd_q10c.lock"
    TIMEOUT = 5

    def __init__(self, lock_file=LOCK_FILE, timeout=TIMEOUT):
        self.lock_file = lock_file
        self.lock_fd = None
        self.timeout = timeout

    def ping(self):
        return self.read_param(0x12, driver.DATA_TYPE_STRING)[0:4] == "FD-Q"

    def get_value(self, force_power_on=True):
        try:
            return round(
                self.read_param(0x94, driver.DATA_TYPE_UINT16, force_power_on) * 0.01, 2
            )
        except:
            logging.warning(traceback.format_exc())
            return None

    def get_state(self):
        # NOTE: 電源 ON なら True
        try:
            spi = driver.com_open()
            return driver.com_status(spi)
        except:
            driver.com_close(spi)
            return False

    def read_param(self, index, data_type, force_power_on=True):
        if not self._acquire():
            raise RuntimeError("Unable to acquire the lock.")

        try:
            spi = driver.com_open()

            if force_power_on or driver.com_status(spi):
                ser = driver.com_start(spi)

                value = driver.isdu_read(spi, ser, index, data_type)

                driver.com_stop(spi, ser)
                driver.com_close(spi)
            else:
                value = None

            self._release()

            return value
        except:
            driver.com_close(spi)

            self._release()
            raise

    def stop(self):
        if not self._acquire():
            raise RuntimeError("Unable to acquire the lock.")

        spi = None
        try:
            spi = driver.com_open()
            driver.com_stop(spi, is_power_off=True)
            driver.com_close(spi)
            self._release()
        except:
            if spi is not None:
                driver.com_close(spi)
                self._release()
                raise

    def _acquire(self):
        self.lock_fd = os.open(self.lock_file, os.O_RDWR | os.O_CREAT | os.O_TRUNC)

        time_start = time.time()
        while time.time() < time_start + self.timeout:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (IOError, OSError):
                pass
            else:
                return True
            time.sleep(0.5)
        os.close(self.lock_fd)
        self.lock_fd = None

        return False

    def _release(self):
        assert self.lock_fd is not None

        fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
        os.close(self.lock_fd)

        self.lock_fd = None

    def get_value_map(self, force_power_on=True):
        value = self.get_value()

        return {"flow": value}


if __name__ == "__main__":
    # TEST Code
    from docopt import docopt

    sys.path.append(str(pathlib.Path(__file__).parent.parent))

    import sensor.fd_q10c

    args = docopt(__doc__)
    lock_file = args["-l"]
    timeout = int(args["-t"], 0)

    logging.getLogger().setLevel(logging.DEBUG)

    sensor = sensor.fd_q10c.FD_Q10C(lock_file, timeout)

    logging.info("VALUE: {value}".format(value=sensor.get_value_map()))
