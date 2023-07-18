#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
エアコン室外機の冷却を行うと共に流量を Fluentd に送信します

Usage:
  unit_cooler.py [-c CONFIG] [-s CONTROL_HOST] [-p PUB_PORT] [-O] [-D] [-t SPEEDUP] [-d]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -s CONTROL_HOST   : コントローラのホスト名を指定します． [default: localhost]
  -p PUB_PORT       : ZeroMQ の Pub サーバーを動作させるポートを指定します． [default: 2222]
  -O                : 1回のみ実行
  -D                : ダミーモードで実行します．
  -t SPEEDUP        : 時短モード．演算間隔を SPEEDUP 分の一にします． [default: 1]
  -d                : デバッグモードで動作します．
"""

from docopt import docopt

import os
import sys

from multiprocessing.pool import ThreadPool
from multiprocessing import Queue, Process

from flask import Flask
from flask_cors import CORS

import socket
import time
import datetime
import math
import signal
import pathlib
import logging
import atexit

import fluent.sender

sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

import control_pubsub
from actuator import (
    set_cooling_state,
    get_valve_status,
    send_valve_condition,
    check_valve_condition,
    stop_valve_monitor,
    notify_hazard,
    check_hazard,
)
import traceback
from config import load_config
from work_log import init, work_log, WORK_LOG_LEVEL
from valve_state import VALVE_STATE, COOLING_STATE
from control import notify_error
import webapp_log
import webapp_event
import logger

LOG_SERVER_PORT = 5001
DUMMY_MODE_SPEEDUP = 12.0

recv_cooling_mode = None
should_terminate = False


def sig_handler(num, frame):
    global should_terminate

    logging.warning("receive signal {num}".format(num=num))

    if num == signal.SIGTERM:
        should_terminate = True


def queue_put(config, cmd_queue, message):
    cmd_queue.put(message)
    pathlib.Path(config["receiver"]["liveness"]["file"]).touch()


# NOTE: コントローラから制御指示を受け取ってキューに積むワーカ
def cmd_receive_worker(config, control_host, pub_port, cmd_queue, is_one_time=False):
    logging.info(
        "Start command receive worker ({host}:{port})".format(
            host=control_host, port=pub_port
        )
    )
    try:
        control_pubsub.start_client(
            control_host,
            pub_port,
            lambda message: queue_put(config, cmd_queue, message),
            is_one_time,
        )
        return 0
    except:
        logging.error("Stop receive worker")
        notify_error(traceback.format_exc(), True)
        return -1


# NOTE: バルブを制御するワーカ
def valve_ctrl_worker(
    config, cmd_queue, dummy_mode=False, speedup=1, is_one_time=False
):
    global recv_cooling_mode

    logging.info("Start control worker")

    if dummy_mode:
        logging.warning("DUMMY mode")

    cooling_mode = {"state": COOLING_STATE.IDLE}
    interval_sec = config["actuator"]["interval_sec"] / speedup
    receive_time = datetime.datetime.now()
    is_receive = False
    mode_index_prev = -1
    try:
        while True:
            start_time = time.time()

            if not cmd_queue.empty():
                while not cmd_queue.empty():
                    cooling_mode = cmd_queue.get()

                recv_cooling_mode = cooling_mode
                receive_time = datetime.datetime.now()
                is_receive = True
                logging.info(
                    "Receive: {cooling_mode}".format(cooling_mode=str(cooling_mode))
                )
                if mode_index_prev != cooling_mode["mode_index"]:
                    work_log(
                        "冷却モードが変更されました．({prev} → {cur})".format(
                            prev="init" if mode_index_prev == -1 else mode_index_prev,
                            cur=cooling_mode["mode_index"],
                        )
                    )
                mode_index_prev = cooling_mode["mode_index"]

            if check_hazard(config):
                cooling_mode = {"state": COOLING_STATE.IDLE}

            set_cooling_state(config, cooling_mode)

            pathlib.Path(config["actuator"]["liveness"]["file"]).touch()

            if is_one_time and is_receive:
                return 0

            if (datetime.datetime.now() - receive_time).total_seconds() > config[
                "controller"
            ]["interval_sec"] * 10:
                notify_error("Unable to receive command.", True)

            if should_terminate:
                logging.info("Terminate control worker")
                break

            sleep_sec = max(interval_sec - (time.time() - start_time), 1)
            logging.debug("Seep {sleep_sec:.1f} sec...".format(sleep_sec=sleep_sec))
            time.sleep(sleep_sec)
    except:
        logging.error("Stop control worker")
        notify_error(traceback.format_exc(), True)
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
        notify_error("Failed to initialize monitor worker", True)

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

            valve_status = get_valve_status()
            valve_condition = check_valve_condition(config, valve_status)

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

            if valve_status["state"] == VALVE_STATE.OPEN:
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
                stop_valve_monitor()

            if should_terminate:
                logging.info("Terminate monitor worker")
                break

            sleep_sec = max(interval_sec - (time.time() - start_time), 1)
            logging.debug("Seep {sleep_sec:.1f} sec...".format(sleep_sec=sleep_sec))
            time.sleep(sleep_sec)
    except:
        logging.error("Stop monitor worker")
        notify_error(traceback.format_exc(), True)
        return -1


def log_server_start(config, queue):
    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    app = Flask("unit_cooler_log")

    CORS(app)

    app.config["CONFIG"] = config
    app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

    app.register_blueprint(webapp_log.blueprint)
    app.register_blueprint(webapp_event.blueprint)

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        webapp_log.init(config)
        webapp_event.notify_watch(queue)

    # app.debug = True
    # NOTE: Flask 主体ではないので，自動リロードは OFF にする．
    app.run(
        host="0.0.0.0",
        port=LOG_SERVER_PORT,
        threaded=True,
        use_reloader=False,
    )


def start(
    config_file, control_host, pub_port, dummy_mode, speedup, is_one_time, debug_mode
):
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

    # NOTE: Raspberry Pi 以外で実行したときに，valve の中でそれをログ通知したいので，
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
    log_event_queue = Queue()

    logging.info("Initialize valve")
    init(config, log_event_queue)
    valve.init(config["actuator"]["valve"]["pin_no"])

    # NOTE: テストしたいので，threading.Thread ではなく multiprocessing.pool.ThreadPool を使う
    pool = ThreadPool(processes=3)

    result_list = []
    result_list.append(
        pool.apply_async(
            cmd_receive_worker, (config, control_host, pub_port, cmd_queue, is_one_time)
        )
    )

    result_list.append(
        pool.apply_async(
            valve_ctrl_worker, (config, cmd_queue, dummy_mode, speedup, is_one_time)
        )
    )
    result_list.append(
        pool.apply_async(
            valve_monitor_worker, (config, dummy_mode, speedup, is_one_time)
        )
    )
    pool.close()

    # NOTE: 他のスレッドが終了したら，メインスレッドを終了させたいので，
    # Flask は別のプロセスで実行
    log_p = Process(target=log_server_start, args=(config, log_event_queue))
    log_p.start()

    def terminate_log_server():
        log_p.kill()
        webapp_event.stop_watch()
        webapp_log.term()

    # NOTE: 終了した場合に，Web サーバも終了するようにしておく
    atexit.register(terminate_log_server)

    for result in result_list:
        if result.get() != 0:
            sys.exit(-1)

    terminate_log_server()

    sys.exit(0)


######################################################################
if __name__ == "__main__":
    args = docopt(__doc__)

    config_file = args["-c"]
    control_host = os.environ.get("HEMS_CONTROL_HOST", args["-s"])
    pub_port = os.environ.get("HEMS_PUB_PORT", args["-p"])
    dummy_mode = os.environ.get("DUMMY_MODE", args["-D"])
    speedup = int(args["-t"])
    is_one_time = args["-O"]
    debug_mode = args["-d"]

    start(
        config_file,
        control_host,
        pub_port,
        dummy_mode,
        speedup,
        is_one_time,
        debug_mode,
    )
