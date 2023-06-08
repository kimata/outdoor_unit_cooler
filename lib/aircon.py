#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from enum import Enum

import logging

# クーラー動作中と判定する電力閾値(min)
POWER_THRESHOLD_WORK = 20
# クーラー平常運転中と判定する電力閾値(min)
POWER_THRESHOLD_NORMAL = 500
# クーラーフル稼働中と判定する電力閾値(min)
POWER_THRESHOLD_FULL = 1000
# エアコンの冷房動作と判定する温度閾値(min)
TEMP_THRESHOLD = 20


class MODE(Enum):
    OFF = 0  # 停止中 or 暖房中 or 不明
    IDLE = 1  # アイドル動作中
    NORMAL = 2  # 平常運転中
    FULL = 3  # フル稼働中


def get_cooler_state(aircon_power, temp):
    mode = MODE.OFF
    if temp is None:
        logging.error("外気温が不明のため，エアコン動作モードを判断できません．")
        assert temp is not None

    if aircon_power["value"] is None:
        logging.warn(
            "{name} の消費電力が不明のため，動作モードを判断できません．".format(name=aircon_power["name"])
        )
        return MODE.OFF

    if temp >= TEMP_THRESHOLD:
        if aircon_power["value"] > POWER_THRESHOLD_FULL:
            mode = MODE.FULL
        elif aircon_power["value"] > POWER_THRESHOLD_NORMAL:
            mode = MODE.NORMAL
        elif aircon_power["value"] > POWER_THRESHOLD_WORK:
            mode = MODE.IDLE

    logging.info(
        "{name}: {power:,.0f} W, 外気温: {temp:.1f} ℃  (mode: {mode})".format(
            name=aircon_power["name"], power=aircon_power["value"], temp=temp, mode=mode
        )
    )

    return mode
