#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
エアコン室外機の冷却モードの指示を出します．

Usage:
  unit_cooler.py [-f CONFIG] [-s SERVER_HOST] [-p SERVER_PORT] [-D] [-d]

Options:
  -f CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -s SERVER_HOST    : サーバーのホスト名を指定します． [default: localhost]
  -p SERVER_PORT    : ZeroMQ の Pub サーバーを動作させるポートを指定します． [default: 2222]
  -D                : ダミーモードで実行します．
  -d                : デバッグモードで動作します．
"""

from docopt import docopt

import os
import sys

import threading

import socket
import time

import pathlib
import queue
import logging

import fluent.sender

sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir, "lib"))

import control_pubsub

import traceback
from config import load_config
import notify_slack
import logger

# 電磁弁の故障を検出したときに作成するファイル
STAT_PATH_HAZARD = pathlib.Path("/dev/shm") / "hazard"

DUMMY_MODE_SPEEDUP = 12.0


def notify_error(config, message=traceback.format_exc()):
    notify_slack.error(
        config["slack"]["bot_token"],
        config["slack"]["error"]["channel"]["name"],
        config["slack"]["from"],
        traceback.format_exc(),
        config["slack"]["error"]["interval_min"],
    )


def hazard_detected(config, message):
    notify_error(config, message)

    STAT_PATH_HAZARD.touch()
    valve.set_state(valve.VALVE_STATE.CLOSE)


def set_cooling_state(cooling_mode):
    if STAT_PATH_HAZARD.exists():
        hazard_detected(config, "水漏れもしくは電磁弁の故障が過去に検出されているので制御を停止しています．")

    return valve.set_cooling_state(cooling_mode)


def check_valve_status(config, valve_status):
    logging.debug("Check valve")

    flow = -1
    if valve_status["state"] == valve.VALVE_STATE.OPEN:
        if valve_status["duration"] > 10:
            # バルブが開いてから時間が経っている場合
            flow = valve.get_flow()
            if flow < 0.02:
                notify_error(config, "元栓が閉じています．")
            elif flow > 2:
                hazard_detected(config, "水漏れしています．")
    else:
        if valve_status["duration"] > (60 * 60):
            # バルブが開いてから時間が経っている場合
            logging.info("Power off the flow sensor")
            valve.stop_sensing()
        else:
            flow = valve.get_flow()
            if (valve_status["duration"] > 120) and (flow > 0.01):
                hazard_detected(config, "電磁弁が壊れていますので制御を停止します．")

    if flow == -1:
        flow = valve.get_flow(False)

    if flow is None:
        if valve_status["state"] == valve.VALVE_STATE.OPEN:
            logging.error("バグがあります，")
        flow = 0.0

    return {"state": valve_status["state"], "flow": flow}


def send_valve_condition(sender, hostname, valve_condition):
    logging.info(
        "Valve Condition: {state} (flow = {flow:.2f} L/min)".format(
            state=valve_condition["state"].name, flow=valve_condition["flow"]
        )
    )

    valve_condition.update({"state": valve_condition["state"].value})
    valve_condition.update({"hostname": hostname})

    logging.debug("Send: {valve_condition}".format(valve_condition=valve_condition))

    if sender.emit("rasp", valve_condition):
        logging.debug("Send OK")
    else:
        logging.error(sender.last_error)


# NOTE: コントローラから制御指示を受け取ってキューに積むワーカ
def cmd_receive_worker(server_host, server_port, cmd_queue):
    logging.info(
        "Start command receive worker ({host}:{port})".format(
            host=server_host, port=server_port
        )
    )
    control_pubsub.start_client(
        server_host, server_port, lambda message: cmd_queue.put(message)
    )


# NOTE: バルブを制御するワーカ
def valve_ctrl_worker(config, cmd_queue, dummy_mode=False):
    logging.info("Start control worker")

    logging.info("Initialize valve")
    valve.init(config["valve"]["pin_no"])

    if dummy_mode:
        logging.warning("DUMMY mode")
        interval_sec = config["control"]["interval_sec"] / DUMMY_MODE_SPEEDUP
    else:
        interval_sec = config["control"]["interval_sec"]

    cooling_mode = {"state": valve.COOLING_STATE.IDLE}
    while True:
        start_time = time.time()

        if not cmd_queue.empty():
            cooling_mode = cmd_queue.get()
            logging.info(
                "Receive: {cooling_mode}".format(cooling_mode=str(cooling_mode))
            )
        set_cooling_state(cooling_mode)

        pathlib.Path(config["liveness"]["file"]).touch()

        sleep_sec = interval_sec - (time.time() - start_time)
        logging.debug("Seep {sleep_sec:.1f} sec...".format(sleep_sec=sleep_sec))
        time.sleep(sleep_sec)


# NOTE: バルブの状態をモニタするワーカ
def valve_monitor_worker(config):
    logging.info("Start monitor worker")

    sender = fluent.sender.FluentSender("sensor", host=config["fluent"]["host"])
    hostname = os.environ.get("NODE_HOSTNAME", socket.gethostname())
    while True:
        start_time = time.time()

        valve_status = valve.get_status()
        valve_condition = check_valve_status(config, valve_status)

        send_valve_condition(sender, hostname, valve_condition)

        sleep_sec = config["monitor"]["interval_sec"] - (time.time() - start_time)
        logging.debug("Seep {sleep_sec:.1f} sec...".format(sleep_sec=sleep_sec))
        time.sleep(sleep_sec)


######################################################################
args = docopt(__doc__)

config_file = args["-f"]
server_host = os.environ.get("HEMS_SERVER_HOST", args["-s"])
server_port = os.environ.get("HEMS_SERVER_PORT", args["-p"])
dummy_mode = args["-D"]
debug_mode = args["-d"]

if debug_mode:
    log_level = logging.DEBUG
else:
    log_level = logging.INFO

logger.init("hems.unit_cooler", level=log_level)

logging.info("Using config config: {config_file}".format(config_file=config_file))
config = load_config(config_file)

# NOTE: Raspberry Pi 以外で実行したときにログで通知したいので，
# ロガーを初期化した後に import する
import valve

cmd_queue = queue.Queue()

threading.Thread(
    target=cmd_receive_worker, args=(server_host, server_port, cmd_queue)
).start()

threading.Thread(target=valve_ctrl_worker, args=(config, cmd_queue, dummy_mode)).start()
threading.Thread(target=valve_monitor_worker, args=(config,)).start()
