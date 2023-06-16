#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import jsonify, Blueprint, current_app
import logging
import pytz
import datetime

from webapp_config import APP_URL_PREFIX

# from webapp_event import notify_event, EVENT_TYPE
# from webapp_log import app_log
from flask_util import support_jsonp, set_acao

from sensor_data import fetch_data, get_today_sum
from control_config import get_cooler_status, get_outdoor_status

blueprint = Blueprint("unit-cooler-info", __name__, url_prefix=APP_URL_PREFIX)


def get_sense_data(config):
    sense_data = {}
    timezone = pytz.timezone("Asia/Tokyo")

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
                        # NOTE: 特に設定しないと InfluxDB は UTC 表記で
                        # JST+9:00 の時刻を返す形になるので，ここで補正しておく．
                        "time": timezone.localize(
                            (data["time"][0].utcnow() + datetime.timedelta(hours=9))
                        ),
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


def get_last_message(server_host, server_port, message_queue):
    while not message_queue.empty():
        get_last_message.last_message = message_queue.get()
    return get_last_message.last_message


get_last_message.last_message = None


def get_stats(config, server_host, server_port, message_queue):
    sense_data = get_sense_data(config)

    return {
        "watering": watering_amount(config),
        "sensor": sense_data,
        "mode": get_last_message(server_host, server_port, message_queue),
        "cooler_status": get_cooler_status(sense_data),
        "outdoor_status": get_outdoor_status(sense_data),
    }


@blueprint.route("/api/stat", methods=["GET"])
@support_jsonp
@set_acao
def api_get_stats():
    config = current_app.config["CONFIG"]
    server_host = current_app.config["SERVER_HOST"]
    server_port = current_app.config["SERVER_PORT"]
    message_queue = current_app.config["MESSAGE_QUEUE"]

    return jsonify(get_stats(config, server_host, server_port, message_queue))


if __name__ == "__main__":
    import logger
    from config import load_config

    logger.init("test", level=logging.INFO)

    config = load_config()

    logging.info(get_stats(config))
