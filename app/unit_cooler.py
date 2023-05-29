#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
エアコン室外機の冷却を行うと共に流量を Fluentd に送信します

Usage:
  unit_cooler.py [-c CONFIG] [-s SERVER_HOST] [-p SERVER_PORT] [-O] [-D] [-t SPEEDUP] [-d]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -s SERVER_HOST    : サーバーのホスト名を指定します． [default: localhost]
  -p SERVER_PORT    : ZeroMQ の Pub サーバーを動作させるポートを指定します． [default: 2222]
  -O                : 1回のみ実行
  -D                : ダミーモードで実行します．
  -t SPEEDUP        : 時短モード．演算間隔を SPEEDUP 分の一にします． [default: 1]
  -d                : デバッグモードで動作します．
"""

from docopt import docopt

import os
import sys

from multiprocessing.pool import ThreadPool

import socket
import time
import datetime
import math

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
STAT_PATH_HAZARD = pathlib.Path("/dev/shm") / "unit_cooler.hazard"

DUMMY_MODE_SPEEDUP = 12.0


def notify_error(config, message):
    logging.error(message)

    if "slack" not in config:
        return

    notify_slack.error(
        config["slack"]["bot_token"],
        config["slack"]["error"]["channel"]["name"],
        config["slack"]["from"],
        traceback.format_exc(),
        config["slack"]["error"]["interval_min"],
    )


def notify_hazard(config, message):
    notify_error(config, message)

    STAT_PATH_HAZARD.touch()
    valve.set_state(valve.VALVE_STATE.CLOSE)


def check_hazard(config):
    if STAT_PATH_HAZARD.exists():
        notify_error(config, "過去に故障が発生しているので制御を停止しています．")
        return True
    else:
        return False


def set_cooling_state(cooling_mode):
    if STAT_PATH_HAZARD.exists():
        notify_hazard(config, "水漏れもしくは電磁弁の故障が過去に検出されているので制御を停止しています．")

    return valve.set_cooling_state(cooling_mode)


def check_valve_status(config, valve_status):
    logging.debug("Check valve")

    flow = -1
    if valve_status["state"] == valve.VALVE_STATE.OPEN:
        flow = valve.get_flow()
        if valve_status["duration"] > 10:
            # バルブが開いてから時間が経っている場合
            if flow < config["actuator"]["valve"]["on"]["min"]:
                notify_error(config, "元栓が閉じています．")
            elif flow > config["actuator"]["valve"]["on"]["max"]:
                notify_hazard(config, "水漏れしています．")
    else:
        if valve_status["duration"] >= config["actuator"]["valve"]["power_off_sec"]:
            # バルブが開いてから時間が経っている場合
            valve.stop_sensing()
        else:
            flow = valve.get_flow()
            if (valve_status["duration"] > 120) and (
                flow > config["actuator"]["valve"]["off"]["max"]
            ):
                notify_hazard(config, "電磁弁が壊れていますので制御を停止します．")

    if flow == -1:
        flow = valve.get_flow(False)

    if flow is None:
        if valve_status["state"] == valve.VALVE_STATE.OPEN:
            logging.error("バグがあります，")
        flow = 0.0

    return {"state": valve_status["state"], "flow": flow}


def send_valve_condition(sender, hostname, valve_condition, dummy_mode=False):
    valve_condition.update({"state": valve_condition["state"].value})
    valve_condition.update({"hostname": hostname})

    logging.debug("Send: {valve_condition}".format(valve_condition=valve_condition))

    if dummy_mode:
        return

    if sender.emit("rasp", valve_condition):
        logging.debug("Send OK")
    else:
        logging.error(sender.last_error)


# NOTE: コントローラから制御指示を受け取ってキューに積むワーカ
def cmd_receive_worker(server_host, server_port, cmd_queue, is_one_time=False):
    logging.info(
        "Start command receive worker ({host}:{port})".format(
            host=server_host, port=server_port
        )
    )
    try:
        control_pubsub.start_client(
            server_host,
            server_port,
            lambda message: cmd_queue.put(message),
            is_one_time,
        )
        return 0
    except:
        logging.error("Stop receive worker")
        notify_error(config, traceback.format_exc())
        return -1


# NOTE: バルブを制御するワーカ
def valve_ctrl_worker(
    config, cmd_queue, dummy_mode=False, speedup=1, is_one_time=False
):
    logging.info("Start control worker")

    logging.info("Initialize valve")
    valve.init(config["actuator"]["valve"]["pin_no"])

    if dummy_mode:
        logging.warning("DUMMY mode")

    interval_sec = config["actuator"]["interval_sec"] / speedup
    cooling_mode = {"state": valve.COOLING_STATE.IDLE}
    receive_time = datetime.datetime.now()
    is_receive = False
    try:
        while True:
            start_time = time.time()

            if not cmd_queue.empty():
                cooling_mode = cmd_queue.get()
                receive_time = datetime.datetime.now()
                is_receive = True
                logging.info(
                    "Receive: {cooling_mode}".format(cooling_mode=str(cooling_mode))
                )
            if check_hazard(config):
                cooling_mode = {"state": valve.COOLING_STATE.IDLE}

            set_cooling_state(cooling_mode)

            pathlib.Path(config["liveness"]["file"]).touch()

            if is_one_time and is_receive:
                return 0

            if (datetime.datetime.now() - receive_time).total_seconds() > config[
                "controller"
            ]["interval_sec"] * 10:
                notify_error(config, "Unable to receive command.")

            sleep_sec = interval_sec - (time.time() - start_time)
            logging.debug("Seep {sleep_sec:.1f} sec...".format(sleep_sec=sleep_sec))
            time.sleep(sleep_sec)
    except:
        logging.error("Stop control worker")
        notify_error(config, traceback.format_exc())
        return -1


# NOTE: バルブの状態をモニタするワーカ
def valve_monitor_worker(config, dummy_mode=False, speedup=1, is_one_time=False):
    logging.info("Start monitor worker")

    sender = None
    try:
        sender = fluent.sender.FluentSender(
            "sensor", host=config["monitor"]["fluent"]["host"]
        )
        hostname = os.environ.get("NODE_HOSTNAME", socket.gethostname())
    except:
        notify_error(config, "Failed to initialize monitor worker")

    interval_sec = config["monitor"]["interval_sec"] / speedup
    if interval_sec < 60:
        log_period = math.ceil(60 / interval_sec)
    else:
        log_period = 1

    i = 0
    try:
        while True:
            start_time = time.time()

            valve_status = valve.get_status()
            valve_condition = check_valve_status(config, valve_status)

            if (i % log_period) == 0:
                logging.info(
                    "Valve Condition: {state} (flow = {flow:.2f} L/min)".format(
                        state=valve_condition["state"].name,
                        flow=valve_condition["flow"],
                    )
                )
            i += 1

            send_valve_condition(sender, hostname, valve_condition, dummy_mode)

            if is_one_time:
                return 0

            sleep_sec = interval_sec - (time.time() - start_time)
            logging.debug("Seep {sleep_sec:.1f} sec...".format(sleep_sec=sleep_sec))
            time.sleep(sleep_sec)
    except:
        logging.error("Stop monitor worker")
        notify_error(config, traceback.format_exc())
        return -1


######################################################################
args = docopt(__doc__)

config_file = args["-c"]
server_host = os.environ.get("HEMS_SERVER_HOST", args["-s"])
server_port = os.environ.get("HEMS_SERVER_PORT", args["-p"])
dummy_mode = args["-D"]
speedup = int(args["-t"])
is_one_time = args["-O"]
debug_mode = args["-d"]

if debug_mode:
    log_level = logging.DEBUG
else:
    log_level = logging.INFO

logger.init(
    "hems.unit_cooler",
    level=log_level,
    dir_path=pathlib.Path(os.path.dirname(__file__)).parent / "log",
)

logging.info("Using config config: {config_file}".format(config_file=config_file))
config = load_config(config_file)

# NOTE: Raspberry Pi 以外で実行したときにログで通知したいので，
# ロガーを初期化した後に import する
import valve

cmd_queue = queue.Queue()

# NOTE: テストしたいので，threading.Thread ではなく multiprocessing.pool.ThreadPool を使う
pool = ThreadPool(processes=3)

result_list = []
result_list.append(
    pool.apply_async(
        cmd_receive_worker, (server_host, server_port, cmd_queue, is_one_time)
    )
)
result_list.append(
    pool.apply_async(
        valve_ctrl_worker, (config, cmd_queue, dummy_mode, speedup, is_one_time)
    )
)
result_list.append(
    pool.apply_async(valve_monitor_worker, (config, dummy_mode, speedup, is_one_time))
)

for result in result_list:
    if result.get() != 0:
        sys.exit(-1)
sys.exit(0)
