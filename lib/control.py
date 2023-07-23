#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging

import os
import pathlib
import pytz
from control_config import (
    MESSAGE_LIST,
    ON_SEC_MIN,
    OFF_SEC_MIN,
    get_cooler_status,
    get_outdoor_status,
)
from sensor_data import fetch_data
import notify_slack

error_hist = []


# NOTE: テスト用
def clear_hist():
    global error_hist

    error_hist = []


# NOTE: テスト用
def get_error_hist():
    global error_hist

    return error_hist


def notify_error(config, message, is_logging=True):
    global error_hist

    if is_logging:
        logging.error(message)

    if ("slack" not in config) or (os.environ.get("DUMMY_MODE", "false") == "true"):
        return

    notify_slack.error(
        config["slack"]["bot_token"],
        config["slack"]["error"]["channel"]["name"],
        config["slack"]["from"],
        message,
        config["slack"]["error"]["interval_min"],
    )

    error_hist.append(message)


def get_sense_data(config):
    timezone = pytz.timezone("Asia/Tokyo")

    if os.environ.get("DUMMY_MODE", "false") == "true":
        start = "-169h"
        stop = "-168h"
    else:
        start = "-1h"
        stop = "now()"

    sense_data = {}
    for kind in config["controller"]["sensor"]:
        kind_data = []
        for sensor in config["controller"]["sensor"][kind]:
            data = fetch_data(
                config["controller"]["influxdb"],
                sensor["measure"],
                sensor["hostname"],
                kind,
                start,
                stop,
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
                notify_error(
                    config, "{name} のデータを取得できませんでした．".format(name=sensor["name"])
                )
                kind_data.append({"name": sensor["name"], "value": None})

        sense_data[kind] = kind_data

    return sense_data


def dummy_control_mode():
    control_mode = (dummy_control_mode.prev_mode + 1) % len(MESSAGE_LIST)
    dummy_control_mode.prev_mode = control_mode

    logging.info("control_mode: {control_mode}".format(control_mode=control_mode))

    return {"control_mode": control_mode}


dummy_control_mode.prev_mode = 0


def judge_control_mode(config):
    logging.info("Judge control mode")

    sense_data = get_sense_data(config)

    try:
        cooler_status = get_cooler_status(sense_data)
    except RuntimeError as e:
        notify_error(config, e.args[0])
        cooler_status = {"status": 0, "message": None}

    if cooler_status["status"] == 0:
        outdoor_status = {"status": None, "message": None}
        control_mode = 0
    else:
        outdoor_status = get_outdoor_status(sense_data)
        control_mode = max(cooler_status["status"] + outdoor_status["status"], 0)

    if cooler_status["message"] is not None:
        logging.info(cooler_status["message"])
    if outdoor_status["message"] is not None:
        logging.info(outdoor_status["message"])

    logging.info(
        (
            "control_mode: {control_mode} "
            + "(cooler_status: {cooler_status}, "
            + "outdoor_status: {outdoor_status})"
        ).format(
            control_mode=control_mode,
            cooler_status=cooler_status["status"],
            outdoor_status=outdoor_status["status"],
        )
    )

    return {
        "control_mode": control_mode,
        "cooler_status": cooler_status,
        "outdoor_status": outdoor_status,
        "sense_data": sense_data,
    }


def gen_control_msg(config, dummy_mode=False, speedup=1):
    if dummy_mode:
        mode = dummy_control_mode()
    else:
        mode = judge_control_mode(config)

    mode_index = min(mode["control_mode"], len(MESSAGE_LIST) - 1)
    control_msg = MESSAGE_LIST[mode_index]

    # NOTE: 参考として，どのモードかも通知する
    control_msg["mode_index"] = mode_index

    pathlib.Path(config["controller"]["liveness"]["file"]).touch(exist_ok=True)

    if dummy_mode:
        control_msg["duty"]["on_sec"] = max(
            control_msg["duty"]["on_sec"] / speedup, ON_SEC_MIN
        )
        control_msg["duty"]["off_sec"] = max(
            control_msg["duty"]["off_sec"] / speedup, OFF_SEC_MIN
        )

    return control_msg


def print_control_msg():
    for control_msg in MESSAGE_LIST:
        if control_msg["duty"]["enable"]:
            logging.info(
                (
                    "state: {state}, on_se_sec: {on_sec:4,} sec, "
                    + "off_sec: {off_sec:5,} sec, on_ratio: {on_ratio:4.1f}%"
                ).format(
                    state=control_msg["state"].name,
                    on_sec=control_msg["duty"]["on_sec"],
                    off_sec=int(control_msg["duty"]["off_sec"]),
                    on_ratio=100.0
                    * control_msg["duty"]["on_sec"]
                    / (control_msg["duty"]["on_sec"] + control_msg["duty"]["off_sec"])
                    if (
                        (control_msg["duty"]["on_sec"] + control_msg["duty"]["off_sec"])
                        != 0
                    )
                    else 0,
                )
            )
        else:
            logging.info("state: {state}".format(state=control_msg["state"].name))
