#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import jsonify, Blueprint, current_app
from flask_cors import cross_origin

import logging
import pytz
import os

from webapp_config import APP_URL_PREFIX

from control import gen_control_msg
from flask_util import support_jsonp

from sensor_data import fetch_data, get_day_sum
from control_config import get_cooler_status, get_outdoor_status

blueprint = Blueprint("unit-cooler-info", __name__, url_prefix=APP_URL_PREFIX)


def get_sense_data(config):
    sense_data = {}
    timezone = pytz.timezone("Asia/Tokyo")

    if os.environ.get("DUMMY_MODE", "false") == "true":
        start = "-192h"
        stop = "-168h"
    else:
        start = "-24h"
        stop = "now()"

    for kind in config["controller"]["sensor"]:
        kind_data = []
        for sensor in config["controller"]["sensor"][kind]:
            data = fetch_data(
                config["controller"]["influxdb"],
                sensor["measure"],
                sensor["hostname"],
                kind,
                start=start,
                stop=stop,
                every_min=5,
                window_min=30,
                last=True,
            )
            if data["valid"]:
                kind_data.append(
                    {
                        "name": sensor["name"],
                        # NOTE: タイムゾーン情報を削除しておく．
                        "time": timezone.localize(
                            (data["time"][0].replace(tzinfo=None))
                        ),
                        "value": data["value"][0],
                    }
                )
            else:
                kind_data.append({"name": sensor["name"], "time": None, "value": None})

        sense_data[kind] = kind_data

    return sense_data


def watering(config):
    if os.environ.get("DUMMY_MODE", "false") == "true":
        offset_day = 7
    else:
        offset_day = 0

    amount = get_day_sum(
        config["controller"]["influxdb"],
        config["controller"]["watering"]["measure"],
        config["controller"]["watering"]["hostname"],
        "flow",
        offset_day,
    )

    return {
        "amount": amount,
        "price": amount * config["controller"]["watering"]["unit_price"] / 1000.0,
    }


def get_last_message(config, message_queue):
    if os.environ.get("DUMMY_MODE", "false") == "true":
        return gen_control_msg(config)
    else:
        # NOTE: 現在の実際の制御モードを取得する．
        # ダミーモードと同じ処理でも良い気がしないでもない．
        while not message_queue.empty():
            get_last_message.last_message = message_queue.get()
        return get_last_message.last_message


get_last_message.last_message = None


def get_stats(config, server_host, server_port, message_queue):
    sense_data = get_sense_data(config)

    return {
        "watering": watering(config),
        "sensor": sense_data,
        "mode": get_last_message(config, message_queue),
        "cooler_status": get_cooler_status(sense_data),
        "outdoor_status": get_outdoor_status(sense_data),
    }


@blueprint.route("/api/stat", methods=["GET"])
@support_jsonp
@cross_origin()
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
