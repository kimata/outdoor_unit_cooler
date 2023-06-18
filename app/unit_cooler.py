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
from multiprocessing import Queue

import socket
import time
import datetime
import math
import signal
import pathlib
import logging

import fluent.sender

sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

import control_pubsub

import traceback
from config import load_config
import notify_slack
import logger

DUMMY_MODE_SPEEDUP = 12.0

recv_cooling_mode = None
should_terminate = False


def sig_handler(num, frame):
    global should_terminate

    logging.warning("receive signal {num}".format(num=num))

    if num == signal.SIGTERM:
        should_terminate = True


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


def notify_hazard(config, message):
    notify_error(config, message)

    pathlib.Path(config["actuator"]["hazard"]["file"]).touch()
    valve.set_state(valve.VALVE_STATE.CLOSE)


def check_hazard(config):
    if pathlib.Path(config["actuator"]["hazard"]["file"]).exists():
        notify_error(config, "過去に故障が発生しているので制御を停止しています．")
        return True
    else:
        return False


def set_cooling_state(cooling_mode):
    if pathlib.Path(config["actuator"]["hazard"]["file"]).exists():
        notify_hazard(config, "水漏れもしくは電磁弁の故障が過去に検出されているので制御を停止しています．")

    return valve.set_cooling_state(cooling_mode)


def check_valve_status(config, valve_status):
    logging.debug("Check valve")

    flow = -1
    if valve_status["state"] == valve.VALVE_STATE.OPEN:
        flow = valve.get_flow()
        if (flow is not None) and (valve_status["duration"] > 10):
            # バルブが開いてから時間が経っている場合
            if flow < config["actuator"]["valve"]["on"]["min"]:
                notify_error(config, "元栓が閉じています．")
            elif flow > config["actuator"]["valve"]["on"]["max"]:
                notify_hazard(config, "水漏れしています．")
    else:
        logging.debug(
            "Valve is close for {duration:.1f} sec".format(
                duration=valve_status["duration"]
            )
        )
        if valve_status["duration"] >= config["actuator"]["valve"]["power_off_sec"]:
            # バルブが閉じてから時間が経っている場合
            flow = 0.0
            valve.stop_sensing()
        else:
            flow = valve.get_flow()
            if (
                (valve_status["duration"] > 120)
                and (flow is not None)
                and (flow > config["actuator"]["valve"]["off"]["max"])
            ):
                notify_hazard(config, "電磁弁が壊れていますので制御を停止します．")

    return {"state": valve_status["state"], "flow": flow}


def send_valve_condition(sender, hostname, valve_condition, dummy_mode=False):
    global recv_cooling_mode

    # NOTE: 少し加工して送りたいので，まずコピーする
    send_data = {"state": valve_condition["state"]}

    if valve_condition["flow"] is not None:
        send_data["flow"] = valve_condition["flow"]

    if recv_cooling_mode is not None:
        send_data["cooling_mode"] = recv_cooling_mode["mode_index"]

    send_data["state"] = valve_condition["state"].value
    send_data["hostname"] = hostname

    logging.debug("Send: {valve_condition}".format(valve_condition=send_data))

    if dummy_mode:
        return

    if sender.emit("rasp", send_data):
        logging.debug("Send OK")
    else:
        logging.error(sender.last_error)


def queue_put(config, cmd_queue, message):
    cmd_queue.put(message)
    pathlib.Path(config["receiver"]["liveness"]["file"]).touch()


# NOTE: コントローラから制御指示を受け取ってキューに積むワーカ
def cmd_receive_worker(config, server_host, server_port, cmd_queue, is_one_time=False):
    logging.info(
        "Start command receive worker ({host}:{port})".format(
            host=server_host, port=server_port
        )
    )
    try:
        control_pubsub.start_client(
            server_host,
            server_port,
            lambda message: queue_put(config, cmd_queue, message),
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
    global recv_cooling_mode

    logging.info("Start control worker")

    logging.info("Initialize valve")
    valve.init(config["actuator"]["valve"]["pin_no"])

    if dummy_mode:
        logging.warning("DUMMY mode")

    cooling_mode = {"state": valve.COOLING_STATE.IDLE}
    interval_sec = config["actuator"]["interval_sec"] / speedup
    receive_time = datetime.datetime.now()
    is_receive = False
    try:
        while True:
            start_time = time.time()

            if not cmd_queue.empty():
                cooling_mode = cmd_queue.get()
                recv_cooling_mode = cooling_mode
                receive_time = datetime.datetime.now()
                is_receive = True
                logging.info(
                    "Receive: {cooling_mode}".format(cooling_mode=str(cooling_mode))
                )
            if check_hazard(config):
                cooling_mode = {"state": valve.COOLING_STATE.IDLE}

            set_cooling_state(cooling_mode)

            pathlib.Path(config["actuator"]["liveness"]["file"]).touch()

            if is_one_time and is_receive:
                return 0

            if (datetime.datetime.now() - receive_time).total_seconds() > config[
                "controller"
            ]["interval_sec"] * 10:
                notify_error(config, "Unable to receive command.")

            if should_terminate:
                logging.info("Terminate control worker")
                break

            sleep_sec = max(interval_sec - (time.time() - start_time), 1)
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
    flow_unknown = 0
    try:
        while True:
            start_time = time.time()

            valve_status = valve.get_status()
            valve_condition = check_valve_status(config, valve_status)

            send_valve_condition(sender, hostname, valve_condition, dummy_mode)

            if (i % log_period) == 0:
                logging.info(
                    "Valve Condition: {state} (flow = {flow_str} L/min)".format(
                        state=valve_condition["state"].name,
                        flow_str="?"
                        if valve_condition["flow"] is None
                        else "{flow:.2f}".format(flow=valve_condition["flow"]),
                    )
                )
                i += 1

            if valve_status["state"] == valve.VALVE_STATE.OPEN:
                if valve_condition["flow"] is None:
                    flow_unknown += 1
                else:
                    flow_unknown = 0

            pathlib.Path(config["monitor"]["liveness"]["file"]).touch()

            if is_one_time:
                return 0

            if flow_unknown > config["monitor"]["sense"]["giveup"]:
                notify_hazard(config, "流量計が使えません．")
                break
            elif flow_unknown > (config["monitor"]["sense"]["giveup"] / 2):
                logging.warn("流量計が応答しないので一旦，リセットします．")
                valve.stop_flow_monitor()

            if should_terminate:
                logging.info("Terminate monitor worker")
                break

            sleep_sec = max(interval_sec - (time.time() - start_time), 1)
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
dummy_mode = os.environ.get("DUMMY_MODE", args["-D"])
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
    # dir_path=pathlib.Path(os.path.dirname(__file__)).parent / "log",
)

# NOTE: オプションでダミーモードが指定された場合，環境変数もそれに揃えておく
if dummy_mode:
    logging.warning("Set dummy mode")
    os.environ["DUMMY_MODE"] = "true"

logging.info("Using config config: {config_file}".format(config_file=config_file))
config = load_config(config_file)

# NOTE: Raspberry Pi 以外で実行したときにログで通知したいので，
# ロガーを初期化した後に import する
import valve

if not dummy_mode:
    # NOTE: 動作開始前に待つ．これを行わないと，複数の Pod が電磁弁を制御することに
    # なり，電磁弁の故障を誤判定する可能性がある．
    for i in range(config["actuator"]["interval_sec"]):
        logging.info(
            "Wait for the old Pod to finish ({i:3} / {total:3})".format(
                i=i + 1, total=config["actuator"]["interval_sec"]
            )
        )
        time.sleep(1)

signal.signal(signal.SIGTERM, sig_handler)
cmd_queue = Queue()

# NOTE: テストしたいので，threading.Thread ではなく multiprocessing.pool.ThreadPool を使う
pool = ThreadPool(processes=3)

result_list = []
result_list.append(
    pool.apply_async(
        cmd_receive_worker, (config, server_host, server_port, cmd_queue, is_one_time)
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
pool.close()

for result in result_list:
    if result.get() != 0:
        sys.exit(-1)

sys.exit(0)
