#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import pprint
from influxdb import InfluxDBClient
from datetime import datetime

INFLUXDB_ADDR = "192.168.0.10"
INFLUXDB_PORT = 8086
INFLUXDB_DB = "sensor"

INFLUXDB_QUERY = """
SELECT mean("power") FROM "fplug" WHERE ("hostname" = \'{name}\') AND time >= now() - 1h GROUP BY time(5m) fill(previous) ORDER by time desc LIMIT 2
"""

POWER_THRESHOLD = 100


def get_state(name):
    try:
        client = InfluxDBClient(
            host=INFLUXDB_ADDR, port=INFLUXDB_PORT, database=INFLUXDB_DB
        )
        result = client.query(INFLUXDB_QUERY.format(name=name))

        points = list(
            filter(
                lambda x: not x is None, map(lambda x: x["mean"], result.get_points())
            )
        )

        return points[0] > POWER_THRESHOLD
    except:
        return False


if __name__ == "__main__":
    print(get_state("書斎エアコン"))
