#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# KEYENCE のクランプオン式流量センサ FD-Q10C と IO-LINK で通信を行なって
# 流量を取得するスクリプトです．

import logging

import ltc2874 as driver


def sense():
    try:
        spi = driver.com_open()
        ser = driver.com_start(spi)

        flow = driver.isdu_read(spi, ser, 0x94, driver.DATA_TYPE_UINT16) * 0.01
        logging.info("flow: {flow} L/min".format(flow=flow))

        driver.com_stop(spi, ser)

        return round(flow, 2)
    except RuntimeError:
        driver.com_stop(spi, ser, True)
        raise


def stop():
    try:
        spi = driver.com_open()
        ser = driver.com_start(spi)
        driver.com_stop(spi, ser, True)
    except RuntimeError:
        raise


if __name__ == "__main__":
    import pprint

    pprint.pprint(sense())
