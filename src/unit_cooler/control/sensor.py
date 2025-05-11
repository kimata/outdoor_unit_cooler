#!/usr/bin/env python3
import logging
from enum import Enum

# クーラー動作中と判定する電力閾値(min)
AIRCON_POWER_THRESHOLD_WORK = 20
# クーラー平常運転中と判定する電力閾値(min)
AIRCON_POWER_THRESHOLD_NORMAL = 500
# クーラーフル稼働中と判定する電力閾値(min)
AIRCON_POWER_THRESHOLD_FULL = 900
# エアコンの冷房動作と判定する温度閾値(min)
AIRCON_TEMP_THRESHOLD = 20


class AIRCON_MODE(Enum):  # noqa: N801
    OFF = 0  # 停止中 or 暖房中 or 不明
    IDLE = 1  # アイドル動作中
    NORMAL = 2  # 平常運転中
    FULL = 3  # フル稼働中


def get_cooler_state(aircon_power, temp):
    mode = AIRCON_MODE.OFF
    if temp is None:
        # NOTE: 外気温がわからないと暖房と冷房の区別がつかないので，致命的エラー扱いにする
        raise RuntimeError("外気温が不明のため，エアコン動作モードを判断できません．")  # noqa: EM101

    if aircon_power["value"] is None:
        logging.warning(
            "%s の消費電力が不明のため，動作モードを判断できません．OFFとみなします．", aircon_power["name"]
        )
        return AIRCON_MODE.OFF

    if temp >= AIRCON_TEMP_THRESHOLD:
        if aircon_power["value"] > AIRCON_POWER_THRESHOLD_FULL:
            mode = AIRCON_MODE.FULL
        elif aircon_power["value"] > AIRCON_POWER_THRESHOLD_NORMAL:
            mode = AIRCON_MODE.NORMAL
        elif aircon_power["value"] > AIRCON_POWER_THRESHOLD_WORK:
            mode = AIRCON_MODE.IDLE

    logging.info(
        "%s: %s W, 外気温: %.1f ℃  (mode: %s)",
        aircon_power["name"],
        f"{aircon_power['value']:,.0f}",
        temp,
        mode,
    )

    return mode
