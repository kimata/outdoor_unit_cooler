#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import jsonify, Blueprint, current_app

import logging
import pytz
import os

from webapp_config import APP_URL_PREFIX

from control import gen_control_msg, judge_control_mode
from flask_util import support_jsonp

from sensor_data import get_day_sum
from control_config import get_cooler_status, get_outdoor_status

blueprint = Blueprint("unit-cooler-info", __name__, url_prefix=APP_URL_PREFIX)


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
    mode = judge_control_mode(config)

    return {
        "watering": watering(config),
        "sensor": mode["sense_data"],
        "mode": get_last_message(config, message_queue),
        "cooler_status": mode["cooler_status"],
        "outdoor_status": mode["outdoor_status"],
    }


@blueprint.route("/api/stat", methods=["GET"])
@support_jsonp
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
