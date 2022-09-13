#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from enum import Enum

import sense_data
import logging

# エアコン動作中と判定する電力閾値
POWER_THRESHOLD_WORK = 20
# エアコン平常運転中と判定する電力閾値
POWER_THRESHOLD_NORMAL = 500
# エアコンフル稼働中と判定する電力閾値
POWER_THRESHOLD_FULL = 1000
# エアコンの冷房動作と判定する温度閾値
TEMP_THRESHOLD = 20


class MODE(Enum):
    OFF = 0
    IDLE = 1
    NORMAL = 2
    FULL = 3


def get_cooler_state(config, measure, name, temp):
    try:
        power = sense_data.get_db_value(config["influxdb"], name, measure, "power")
        mode = MODE.OFF
        if temp > TEMP_THRESHOLD:
            if power > POWER_THRESHOLD_FULL:
                mode = MODE.FULL
            elif power > POWER_THRESHOLD_NORMAL:
                mode = MODE.NORMAL
            elif power > POWER_THRESHOLD_WORK:
                mode = MODE.IDLE
        logging.info(
            "{name}: {power:,}W, 外気温: {temp}℃  (mode: {mode})".format(
                name=name, power=int(power), temp=round(temp, 1), mode=mode
            )
        )

        return mode
    except:
        logging.warning("{name} の電力の取得に失敗しました．".format(name=name))
        return False


if __name__ == "__main__":
    from config import load_config
    import time
    import logger

    logger.init("test")

    config = load_config()

    dummy_temp = 30
    while True:
        for aircon in config["sensor"]["power"]:
            get_cooler_state(config, aircon["measure"], aircon["hostname"], dummy_temp),
        time.sleep(60)
