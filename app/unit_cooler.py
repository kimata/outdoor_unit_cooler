#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
エアコン室外機の冷却を行うと共に流量を Fluentd に送信します

Usage:
  unit_cooler.py [-c CONFIG] [-s CONTROL_HOST] [-p PUB_PORT] [-n COUNT] [-D] [-t SPEEDUP] [-d]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します． [default: config.yaml]
  -s CONTROL_HOST   : コントローラのホスト名を指定します． [default: localhost]
  -p PUB_PORT       : ZeroMQ の Pub サーバーを動作させるポートを指定します． [default: 2222]
  -n COUNT          : n 回制御メッセージを受信したら終了します．0 は制限なし． [default: 0]
  -D                : ダミーモードで実行します．
  -t SPEEDUP        : 時短モード．演算間隔を SPEEDUP 分の一にします． [default: 1]
  -d                : デバッグモードで動作します．
"""

from docopt import docopt

import os
import sys

from multiprocessing import Queue
import concurrent.futures
import threading
from flask import Flask
from flask_cors import CORS
import werkzeug.serving

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
from actuator import (
    init_actuator,
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
import work_log
from valve_state import VALVE_STATE, COOLING_STATE
from control import notify_error
import webapp_log
import webapp_event
import logger

LOG_SERVER_PORT = 5001
DUMMY_MODE_SPEEDUP = 12.0

recv_cooling_mode = None
should_terminate = False


def queue_put(config, cmd_queue, message):
    cmd_queue.put(message)
    pathlib.Path(config["receiver"]["liveness"]["file"]).touch()


# NOTE: コントローラから制御指示を受け取ってキューに積むワーカ
def cmd_receive_worker(config, control_host, pub_port, cmd_queue, msg_count=0):
    logging.info(
        "Start command receive worker ({host}:{port})".format(
            host=control_host, port=pub_port
        )
    )
    ret = 0
    try:
        control_pubsub.start_client(
            control_host,
            pub_port,
            lambda message: queue_put(config, cmd_queue, message),
            msg_count,
        )
    except:
        notify_error(config, traceback.format_exc())
        ret = -1
    logging.warning("Stop receive worker")


# NOTE: バルブを制御するワーカ
def valve_ctrl_worker(config, cmd_queue, dummy_mode=False, speedup=1, msg_count=0):
    global recv_cooling_mode
    global should_terminate

    logging.info("Start valve control worker")

    if dummy_mode:
        logging.warning("DUMMY mode")

    cooling_mode = {"state": COOLING_STATE.IDLE}
    interval_sec = config["actuator"]["interval_sec"] / speedup
    receive_time = datetime.datetime.now()
    mode_index_prev = -1
    receive_count = 0
    ret = 0
    try:
        while True:
            start_time = time.time()
            if should_terminate:
                logging.info("Terminate control worker")
                break
            try:
                if not cmd_queue.empty():
                    while not cmd_queue.empty():
                        cooling_mode = cmd_queue.get()
                        receive_count += 1
                        if os.environ.get("TEST", "false") == "true":
                            # NOTE: テスト時は，コマンドの数を整合させたいので，
                            # 1 回に1個のコマンドの未処理する．
                            break

                    recv_cooling_mode = cooling_mode
                    receive_time = datetime.datetime.now()
                    logging.info(
                        "Receive: {cooling_mode}".format(cooling_mode=str(cooling_mode))
                    )
                    if mode_index_prev != cooling_mode["mode_index"]:
                        work_log.work_log(
                            "冷却モードが変更されました．({prev} → {cur})".format(
                                prev="init"
                                if mode_index_prev == -1
                                else mode_index_prev,
                                cur=cooling_mode["mode_index"],
                            )
                        )
                    mode_index_prev = cooling_mode["mode_index"]
            except OverflowError:  # pragma: no cover
                # NOTE: テストする際，freezer 使って日付をいじるとこの例外が発生する
                logging.debug(traceback.format_exc())
                pass
            if check_hazard(config):
                cooling_mode = {"state": COOLING_STATE.IDLE}
            set_cooling_state(config, cooling_mode)

            pathlib.Path(config["actuator"]["liveness"]["file"]).touch()

            if msg_count != 0:
                logging.debug(
                    "(receive_count, msg_count) = ({receive_count}, {msg_count})".format(
                        receive_count=receive_count, msg_count=msg_count
                    )
                )
                if receive_count >= msg_count:
                    break

            if (datetime.datetime.now() - receive_time).total_seconds() > config[
                "controller"
            ]["interval_sec"] * 10:
                work_log.work_log("冷却モードの指示を受信できません．", work_log.WORK_LOG_LEVEL.ERROR)

            sleep_sec = max(interval_sec - (time.time() - start_time), 0.5)
            logging.debug("Seep {sleep_sec:.1f} sec...".format(sleep_sec=sleep_sec))
            time.sleep(sleep_sec)
    except:
        notify_error(config, traceback.format_exc())
        ret = -1

    logging.warning("Stop valve control worker")
    # NOTE: Queue を close した後に put されると ValueError が発生するので，
    # 明示的に閉じるのをやめた．
    # cmd_queue.close()

    return ret


# NOTE: バルブの状態をモニタするワーカ
def valve_monitor_worker(config, dummy_mode=False, speedup=1, msg_count=0):
    global recv_cooling_mode
    global should_terminate

    logging.info("Start monitor worker")

    sender = None
    hostname = "unit_cooler"
    try:
        sender = fluent.sender.FluentSender(
            "sensor", host=config["monitor"]["fluent"]["host"]
        )
        hostname = os.environ.get("NODE_HOSTNAME", socket.gethostname())
    except:
        work_log.work_log("流量のロギングを開始できません．", work_log.WORK_LOG_LEVEL.ERROR)
        return -1

    interval_sec = config["monitor"]["interval_sec"] / speedup
    log_period = max(math.ceil(60 / interval_sec), 1)

    i = 0
    flow_unknown = 0
    monitor_count = 0
    ret = 0
    try:
        while True:
            start_time = time.time()

            if should_terminate:
                logging.info("Terminate monitor worker")
                break

            valve_status = get_valve_status()
            valve_condition = check_valve_condition(config, valve_status)

            send_valve_condition(
                sender, hostname, recv_cooling_mode, valve_condition, dummy_mode
            )
            monitor_count += 1

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

            if msg_count != 0:
                logging.debug(
                    "(monitor_count, msg_count) = ({monitor_count}, {msg_count})".format(
                        monitor_count=monitor_count, msg_count=msg_count
                    )
                )
                if monitor_count >= msg_count:
                    break

            if flow_unknown > config["monitor"]["sense"]["giveup"]:
                work_log.work_log("流量計が使えません．", work_log.WORK_LOG_LEVEL.ERROR)

                break
            elif flow_unknown > (config["monitor"]["sense"]["giveup"] / 2):
                logging.warning("流量計が応答しないので一旦，リセットします．")
                stop_valve_monitor()

            sleep_sec = max(interval_sec - (time.time() - start_time), 0.5)
            logging.debug("Seep {sleep_sec:.1f} sec...".format(sleep_sec=sleep_sec))
            time.sleep(sleep_sec)
    except:
        notify_error(config, traceback.format_exc())
        ret = -1

    logging.warning("Stop monitor worker")
    return ret


def log_server_app(config, queue):
    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    app = Flask("unit_cooler_log")

    CORS(app)

    app.config["CONFIG"] = config
    app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

    app.register_blueprint(webapp_log.blueprint)
    app.register_blueprint(webapp_event.blueprint)

    webapp_log.init(config, is_read_only=True)
    webapp_event.notify_watch(queue)

    # app.debug = True

    return app


def start(arg):
    global should_terminate
    global log_server_handle

    should_terminate = False

    setting = {
        "config_file": "config.yaml",
        "control_host": "localhost",
        "pub_port": 2222,
        "dummy_mode": False,
        "speedup": 1,
        "msg_count": 0,
        "debug_mode": False,
    }
    setting.update(arg)

    if setting["debug_mode"]:  # pragma: no cover
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logger.init(
        "hems.unit_cooler",
        level=log_level,
        # dir_path=pathlib.Path(os.path.dirname(__file__)).parent / "log",
    )

    # NOTE: オプションでダミーモードが指定された場合，環境変数もそれに揃えておく
    if setting["dummy_mode"]:
        logging.warning("Set dummy mode")
        os.environ["DUMMY_MODE"] = "true"

    logging.info(
        "Using config config: {config_file}".format(config_file=setting["config_file"])
    )
    config = load_config(setting["config_file"])

    if not setting["dummy_mode"] and (os.environ.get("TEST", "false") != "true"):
        # NOTE: 動作開始前に待つ．これを行わないと，複数の Pod が電磁弁を制御することに
        # なり，電磁弁の故障を誤判定する可能性がある．
        for i in range(config["actuator"]["interval_sec"]):
            logging.info(
                "Wait for the old Pod to finish ({i:3} / {total:3})".format(
                    i=i + 1, total=config["actuator"]["interval_sec"]
                )
            )
            time.sleep(1)

    cmd_queue = Queue()
    log_event_queue = Queue()

    logging.info("Initialize valve")
    work_log.init(config, log_event_queue)
    init_actuator(config["actuator"]["valve"]["pin_no"])

    worker_def = [
        {
            "name": "cmd_receive_worker",
            "param": [
                cmd_receive_worker,
                config,
                setting["control_host"],
                setting["pub_port"],
                cmd_queue,
                setting["msg_count"],
            ],
        },
        {
            "name": "valve_ctrl_worker",
            "param": [
                valve_ctrl_worker,
                config,
                cmd_queue,
                setting["dummy_mode"],
                setting["speedup"],
                setting["msg_count"],
            ],
        },
        {
            "name": "valve_monitor_worker",
            "param": [
                valve_monitor_worker,
                config,
                setting["dummy_mode"],
                setting["speedup"],
                setting["msg_count"],
            ],
        },
    ]

    thread_list = []
    # NOTE: テストしたいので，threading.Thread ではなく multiprocessing.pool.ThreadPool を使う
    executor = concurrent.futures.ThreadPoolExecutor()

    for worker_info in worker_def:
        future = executor.submit(*worker_info["param"])
        thread_list.append({"name": worker_info["name"], "future": future})

    # NOTE: Flask は別のプロセスで実行
    log_server_server = werkzeug.serving.make_server(
        "0.0.0.0",
        LOG_SERVER_PORT,
        log_server_app(config, log_event_queue),
        threaded=True,
    )
    log_server_thread = threading.Thread(target=log_server_server.serve_forever)

    logging.info("Start log server")

    log_server_thread.start()

    log_server_handle = {
        "server": log_server_server,
        "thread": log_server_thread,
    }

    signal.signal(signal.SIGTERM, sig_handler)

    return (executor, thread_list, log_server_handle)


def sig_handler(num, frame):
    global should_terminate

    logging.warning("receive signal {num}".format(num=num))

    if num == signal.SIGTERM:
        should_terminate = True


def terminate_log_server(log_server_handle):
    logging.warning("Stop log server")

    webapp_event.stop_watch()

    log_server_handle["server"].shutdown()
    log_server_handle["server"].server_close()
    log_server_handle["thread"].join()

    webapp_log.term(is_read_only=True)
    work_log.term()


def wait_and_term(executor, thread_list, log_server_handle):
    global should_terminate

    should_terminate = True

    ret = 0
    for thread_info in thread_list:
        logging.info("Wait {name} finish".format(name=thread_info["name"]))

        if thread_info["future"].result() != 0:
            logging.warning("Error occurred in {name}".format(name=thread_info["name"]))
            ret = -1

    logging.info("Shutdown executor")
    executor.shutdown()

    terminate_log_server(log_server_handle)

    logging.warning("Terminate unit_cooler")

    return ret


######################################################################
if __name__ == "__main__":
    args = docopt(__doc__)

    config_file = args["-c"]
    control_host = os.environ.get("HEMS_CONTROL_HOST", args["-s"])
    pub_port = int(os.environ.get("HEMS_PUB_PORT", args["-p"]))
    dummy_mode = os.environ.get("DUMMY_MODE", args["-D"])
    speedup = int(args["-t"])
    msg_count = int(args["-n"])
    debug_mode = args["-d"]

    app_arg = {
        "config_file": config_file,
        "control_host": control_host,
        "pub_port": pub_port,
        "dummy_mode": dummy_mode,
        "speedup": speedup,
        "msg_count": msg_count,
        "debug_mode": debug_mode,
    }

    sys.exit(wait_and_term(*start(app_arg)))
