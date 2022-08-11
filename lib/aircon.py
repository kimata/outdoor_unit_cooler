#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sense_data
import logging

# エアコン動作中と判定する電力閾値
POWER_THRESHOLD = 20
# エアコンの冷房動作と判定する温度閾値
TEMP_THRESHOLD = 20


def get_cooler_state(config, measure, name, temp):
    try:
        power = sense_data.get_db_value(config["influxdb"], name, measure, "power")
        judge = (power > POWER_THRESHOLD) and (temp > TEMP_THRESHOLD)

        logging.info(
            "{name}: {power:,}W, 外気温: {temp}℃  [state: {judge}]".format(
                name=name, power=int(power), temp=round(temp, 1), judge=judge
            )
        )

        return judge
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