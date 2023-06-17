#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
エアコン室外機の冷却モードの指示を出します．

Usage:
  cooler_controller.py [-c CONFIG] [-p SERVER_PORT] [-r REAL_PORT] [-O] [-D] [-t SPEEDUP] [-d]
  cooler_controller.py -C [-c CONFIG] [-s SERVER_HOST] [-p SERVER_PORT] [-P PROXY_PORT] [-d]
  cooler_controller.py -V

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -p SERVER_PORT    : ZeroMQ の サーバーを動作させるポートを指定します． [default: 2222]
  -r REAL_PORT      : ZeroMQ の 本当のサーバーを動作させるポートを指定します． [default: 2200]
  -O                : 1回のみ実行
  -D                : 冷却モードをランダムに生成するモードで動作すします．
  -t SPEEDUP        : 時短モード．演算間隔を SPEEDUP 分の一にします． [default: 1]
  -d                : デバッグモードで動作します．
  -V                : 制御メッセージの一覧を表示します．
  -C                : クライアントモード(ダミー)で動作します．CI でのテスト用．
  -s SERVER_HOST    : サーバーのホスト名を指定します． [default: localhost]
"""

from docopt import docopt

import os
import sys
import logging
import pathlib
import traceback
import threading

sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

import control_pubsub
from sensor_data import fetch_data
import aircon
import notify_slack
from config import load_config
from control_config import MESSAGE_LIST, get_cooler_status, get_outdoor_status
import logger


def notify_error(config, message):
    logging.error(message)

    if "slack" not in config:
        return

    notify_slack.error(
        config["slack"]["bot_token"],
        config["slack"]["error"]["channel"]["name"],
        config["slack"]["from"],
        message,
        config["slack"]["error"]["interval_min"],
    )


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
                "1h",
                last=True,
            )
            if data["valid"]:
                kind_data.append({"name": sensor["name"], "value": data["value"][0]})
            else:
                notify_error(
                    config, "{name} のデータを取得できませんでした．".format(name=sensor["name"])
                )
                kind_data.append({"name": sensor["name"], "value": None})

        sense_data[kind] = kind_data

    return sense_data


def dummy_control_mode():
    import random

    # NOTE: ある程度連続性を持ったランダムな制御量を生成する
    dice = int(random.random() * 10)
    if dice < 2:
        control_mode = max(min(int(random.random() * 15) - 4, 8), 0)
    elif dice < 8:
        control_mode = max(
            min(int(dummy_control_mode.prev_mode + (random.random() - 0.5) * 4), 8), 0
        )
    else:
        control_mode = dummy_control_mode.prev_mode

    logging.info("control_mode: {control_mode}".format(control_mode=control_mode))

    dummy_control_mode.prev_mode = control_mode

    return control_mode


dummy_control_mode.prev_mode = 0


def judge_control_mode(config):
    logging.info("Judge control mode")

    sense_data = get_sense_data(config)

    cooler_status = get_cooler_status(sense_data)

    if cooler_status["status"] == 0:
        outdoor_status = {"status": None, "message": None}
        control_mode = cooler_status["status"]
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

    return control_mode


def gen_control_msg(config, dummy_mode=False, speedup=1):
    if dummy_mode:
        control_mode = dummy_control_mode()
    else:
        control_mode = judge_control_mode(config)

    mode_index = min(control_mode, len(MESSAGE_LIST) - 1)
    control_msg = MESSAGE_LIST[mode_index]

    # NOTE: 参考として，どのモードかも通知する
    control_msg["mode_index"] = mode_index

    pathlib.Path(config["controller"]["liveness"]["file"]).touch(exist_ok=True)

    if dummy_mode:
        control_msg["duty"]["on_sec"] = int(control_msg["duty"]["on_sec"] / speedup)
        control_msg["duty"]["off_sec"] = int(control_msg["duty"]["off_sec"] / speedup)

    return control_msg


def test_client(server_host, server_port):
    logging.info(
        "Start test client (host: {host}:{port})".format(
            host=server_host, port=server_port
        )
    )
    control_pubsub.start_client(
        server_host,
        server_port,
        lambda message: (
            logging.info("receive: {message}".format(message=message)),
            os._exit(0),
        ),
    )


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
                    / (control_msg["duty"]["on_sec"] + control_msg["duty"]["off_sec"]),
                )
            )
        else:
            logging.info("state: {state}".format(state=control_msg["state"].name))

    sys.exit(0)


######################################################################
args = docopt(__doc__)

config_file = args["-c"]
server_port = os.environ.get("HEMS_SERVER_PORT", args["-p"])
real_port = args["-r"]
dummy_mode = args["-D"]
speedup = int(args["-t"])
debug_mode = args["-d"]
client_mode = args["-C"]
server_host = args["-s"]
is_one_time = args["-O"]
view_msg_mode = args["-V"]

if debug_mode:
    log_level = logging.DEBUG
else:
    log_level = logging.INFO

logger.init("hems.unit_cooler", level=log_level)

if client_mode:
    test_client(server_host, server_port)
    sys.exit(0)
elif view_msg_mode:
    print_control_msg()

logging.info("Start controller (port: {port})".format(port=server_port))

logging.info("Using config config: {config_file}".format(config_file=config_file))
config = load_config(config_file)

if dummy_mode:
    logging.warning("DUMMY mode")

try:
    # NOTE: Last Value Caching Proxy
    threading.Thread(
        target=control_pubsub.start_proxy,
        args=(server_host, real_port, server_port, is_one_time),
    ).start()

    control_pubsub.start_server(
        real_port,
        lambda: gen_control_msg(config, dummy_mode, speedup),
        config["controller"]["interval_sec"] / speedup,
        is_one_time,
    )
except:
    notify_error(config, traceback.format_exc())
    raise
