#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import jsonify, Blueprint, current_app
import logging

import control_pubsub
from webapp_config import APP_URL_PREFIX

# from webapp_event import notify_event, EVENT_TYPE
# from webapp_log import app_log
from flask_util import support_jsonp


from sensor_data import fetch_data, get_today_sum

blueprint = Blueprint("unit-cooler-info", __name__, url_prefix=APP_URL_PREFIX)


def get_sense_data(config):
    sense_data = {}

    for kind in config["controller"]["sensor"]:
        kind_data = []
        for sensor in config["controller"]["sensor"][kind]:
            data = fetch_data(
                config["controller"]["influxdb"],
                sensor["measure"],
                sensor["hostname"],
                kind,
                period="24h",
                every_min=5,
                window_min=30,
                last=True,
            )
            if data["valid"]:
                kind_data.append(
                    {
                        "name": sensor["name"],
                        "time": data["time"][0],
                        "value": data["value"][0],
                    }
                )
            else:
                kind_data.append({"name": sensor["name"], "time": None, "value": None})

        sense_data[kind] = kind_data

    return sense_data


def watering_amount(config):
    return get_today_sum(
        config["controller"]["influxdb"],
        config["controller"]["watering"]["measure"],
        config["controller"]["watering"]["hostname"],
        "flow",
    )


def get_stats(config):
    return {
        "watering": watering_amount(config),
        "sensor": get_sense_data(config),
        "mode": control_pubsub.get_last_message("127.0.0.1", 2222),
    }


@blueprint.route("/api/stat", methods=["GET"])
@support_jsonp
def api_get_stats():
    config = current_app.config["CONFIG"]
    return jsonify(get_stats(config))


if __name__ == "__main__":
    import logger
    from config import load_config

    logger.init("test", level=logging.INFO)

    config = load_config()

    logging.info(get_stats(config))
