#!/usr/bin/env python3
import logging
import os
import random

import my_lib.rpi
import unit_cooler.const

fd_q10c = None
pin_no = None

if os.environ.get("DUMMY_MODE", "false") != "true":  # pragma: no cover
    from my_lib.sensor.fd_q10c import FD_Q10C
else:

    class FD_Q10C:  # noqa: N801
        def __init__(self, lock_file="DUMMY", timeout=2):  # noqa: D107
            pass

        def get_value(self, force_power_on=True):  # noqa: ARG002
            global pin_no
            if my_lib.rpi.gpio.input(pin_no) == unit_cooler.const.VALVE_STATE.OPEN.value:
                return 1 + random.random() * 2  # noqa: S311
            else:
                return 0

        def get_state(self):
            return True

        def stop(self):
            return


def init(pin_no_):
    global fd_q10c  # noqa: PLW0603
    global pin_no  # noqa: PLW0603

    pin_no = pin_no_
    fd_q10c = FD_Q10C()


def stop():
    global fd_q10c

    logging.info("Stop flow sensing")

    try:
        fd_q10c.stop()
    except RuntimeError:
        logging.exception("Failed to stop FD-Q10C")


def get_power_state():
    global fd_q10c

    return fd_q10c.get_state()


def get_flow(force_power_on=True):
    global fd_q10c

    try:
        flow = fd_q10c.get_value(force_power_on)
    except Exception:
        logging.exception("バグの可能性あり。")
        flow = None

    if flow is not None:
        logging.info("Valve flow = %.2f", flow)
    else:
        logging.info("Valve flow = UNKNOWN")

    return flow
