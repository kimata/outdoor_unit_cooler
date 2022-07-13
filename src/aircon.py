#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

import influxdb_client

FLUX_QUERY = """
from(bucket: "{bucket}")
    |> range(start: -{period})
    |> filter(fn:(r) => r._measurement == "{measure}")
    |> filter(fn: (r) => r.hostname == "{hostname}")
    |> filter(fn: (r) => r["_field"] == "{param}")
    |> aggregateWindow(every: 3m, fn: mean, createEmpty: false)
    |> exponentialMovingAverage(n: 3)
    |> sort(columns: ["_time"], desc: true)
    |> limit(n: 1)
"""

# InfluxDB から外気温を取得するためのパラメータ
TEMP_MEASURE = "sensor.rasp"
TEMP_HOSTNAME = "rasp-meter-8"

# エアコン動作中と判定する温度閾値
POWER_THRESHOLD = 20
# クーラー動作と判定する温度閾値
TEMP_THRESHOLD = 20


def get_db_value(
    config,
    hostname,
    measure,
    param,
):
    client = influxdb_client.InfluxDBClient(
        url=config["influxdb"]["url"],
        token=config["influxdb"]["token"],
        org=config["influxdb"]["org"],
    )

    query_api = client.query_api()

    table_list = query_api.query(
        query=FLUX_QUERY.format(
            bucket=config["influxdb"]["bucket"],
            measure=measure,
            hostname=hostname,
            param=param,
            period="1h",
        )
    )

    return table_list[0].records[0].get_value()


def get_outdoor_temp(config):
    return get_db_value(config, TEMP_HOSTNAME, TEMP_MEASURE, "temp")


def get_state(config, tag, name):
    try:

        power = get_db_value(config, name, "fplug", "power")
        temp = get_outdoor_temp(config)

        judge = (power > POWER_THRESHOLD) and (temp > TEMP_THRESHOLD)

        logging.info(
            "{name}: {power:,}W, 外気温: {temp}℃  [state: {judge}]".format(
                name=name, power=int(power), temp=round(temp, 1), judge=judge
            )
        )
        return judge
    except Exception as e:
        logging.warning("{name} の電力，もしくは，外気温の取得に失敗しました．".format(name=name))
        logging.warning(e)
        return False


if __name__ == "__main__":
    import yaml
    import os
    import logger
    import time
    import pathlib

    logger.init("test")
    with open(str(pathlib.Path(os.path.dirname(__file__), "config.yml"))) as file:
        config = yaml.safe_load(file)

    while True:
        get_state(config, "hems.sharp", "リビングエアコン")
        get_state(config, "fplug", "書斎エアコン")
        get_state(config, "fplug", "和室エアコン")
        time.sleep(60)
