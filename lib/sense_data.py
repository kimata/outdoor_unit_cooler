#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import logging
import influxdb_client
import traceback

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


def get_db_value(config, hostname, measure, param, period="1h", window="3m"):
    token = os.environ.get("INFLUXDB_TOKEN", config["token"])
    query = FLUX_QUERY.format(
        bucket=config["bucket"],
        measure=measure,
        hostname=hostname,
        param=param,
        period=period,
    )
    try:
        client = influxdb_client.InfluxDBClient(
            url=config["url"], token=token, org=config["org"]
        )

        query_api = client.query_api()
        table_list = query_api.query(query=query)

        return table_list[0].records[0].get_value()
    except:
        logging.error(traceback.format_exc())
        logging.error("Flux query = {query}".format(query=query))
        return None


if __name__ == "__main__":
    from config import load_config
    import logger

    logger.init("test")

    config = load_config()
    for sensor_type, sensor_list in config["sensor"].items():
        for sensor in sensor_list:
            value = get_db_value(
                config["influxdb"], sensor["hostname"], sensor["measure"], sensor_type
            )
            print(
                "{name} ({sensor_type}): {value:.1f}".format(
                    name=sensor["name"], sensor_type=sensor_type, value=value
                )
            )
