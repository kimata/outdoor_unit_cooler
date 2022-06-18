#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

from influxdb import InfluxDBClient

INFLUXDB_ADDR = "192.168.0.10"
INFLUXDB_PORT = 8086
INFLUXDB_DB = "sensor"

INFLUXDB_POWER_QUERY = """
SELECT mean("power") FROM "fplug" WHERE ("hostname" = \'{name}\') AND time >= now() - 1h GROUP BY time(5m) fill(previous) ORDER by time desc LIMIT 10
"""
INFLUXDB_TEMP_QUERY = """
SELECT mean("temp") FROM "sensor.esp32" WHERE ("hostname" = \'{name}\') AND time >= now() - 1h GROUP BY time(5m) fill(previous) ORDER by time desc LIMIT 10
"""

TEMP_THRESHOLD = 20
POWER_THRESHOLD = 50


def get_db_value(query):
    client = InfluxDBClient(
        host=INFLUXDB_ADDR, port=INFLUXDB_PORT, database=INFLUXDB_DB
    )
    result = client.query(query)

    points = list(
        filter(lambda x: not x is None, map(lambda x: x["mean"], result.get_points()))
    )

    return points[0]


def get_state(name):
    try:
        power = get_db_value(INFLUXDB_POWER_QUERY.format(name=name))
        temp = get_db_value(INFLUXDB_TEMP_QUERY.format(name="ESP32-outdoor-1"))

        judge = (power > POWER_THRESHOLD) and (temp > TEMP_THRESHOLD)

        logging.info(
            "{name}: {power:,}W, 外気温: {temp}℃  [state: {judge}]".format(
                name=name, power=round(power, 1), temp=round(temp, 1), judge=judge
            )
        )
        return judge
    except Exception as e:
        logging.warn(e)
        return False


if __name__ == "__main__":
    import logger
    import time

    logger.init("test")

    while True:
        get_state("書斎エアコン")
        get_state("和室エアコン")
        time.sleep(60)
