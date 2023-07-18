#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
エアコン室外機の冷却モードの指示を出します．

Usage:
  cooler_controller.py [-c CONFIG] [-p SERVER_PORT] [-r REAL_PORT] [-n COUNT] [-D] [-t SPEEDUP] [-d]
  cooler_controller.py -C [-c CONFIG] [-s SERVER_HOST] [-p SERVER_PORT] [-P PROXY_PORT] [-d]
  cooler_controller.py -V

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -p SERVER_PORT    : ZeroMQ の サーバーを動作させるポートを指定します． [default: 2222]
  -r REAL_PORT      : ZeroMQ の 本当のサーバーを動作させるポートを指定します． [default: 2200]
  -n COUNT          : n 回制御メッセージを生成したら終了します．0 は制限なし．[default: 0]
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

from control import gen_control_msg, notify_error, print_control_msg
import control_pubsub
from config import load_config
import logger


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


# NOTE: Last Value Caching Proxy
def cache_proxy_start(config, server_host, real_port, server_port, msg_count):
    try:
        thread = threading.Thread(
            target=control_pubsub.start_proxy,
            args=(server_host, real_port, server_port, msg_count),
        )
        thread.start()

        return thread
    except:
        notify_error(config, traceback.format_exc())
        raise


def control_server_start(config, real_port, dummy_mode, speedup, msg_count):
    try:
        thread = threading.Thread(
            target=control_pubsub.start_server,
            args=(
                real_port,
                lambda: gen_control_msg(config, dummy_mode, speedup),
                config["controller"]["interval_sec"] / speedup,
                msg_count,
            ),
        )
        thread.start()

        return thread
    except:
        notify_error(config, traceback.format_exc())
        raise


def start(arg):
    setting = {
        "config_file": "config.yaml",
        "server_host": "localhost",
        "real_port": 2200,
        "server_port": 2222,
        "client_mode": False,
        "view_msg_mode": False,
        "dummy_mode": False,
        "debug_mode": False,
        "speedup": 1,
        "msg_count": 0,
    }
    setting.update(arg)

    if setting["debug_mode"]:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logger.init("hems.unit_cooler", level=log_level)

    if setting["client_mode"]:
        test_client(setting["server_host"], setting["server_port"])
        return
    elif setting["view_msg_mode"]:
        print_control_msg()
        return

    logging.info("Start controller (port: {port})".format(port=setting["server_port"]))

    logging.info(
        "Using config config: {config_file}".format(config_file=setting["config_file"])
    )
    config = load_config(setting["config_file"])

    if setting["dummy_mode"]:
        logging.warning("DUMMY mode")
        os.environ["DUMMY_MODE"] = "true"

    try:
        proxy_thread = cache_proxy_start(
            config,
            setting["server_host"],
            setting["real_port"],
            setting["server_port"],
            setting["msg_count"],
        )
        control_thread = control_server_start(
            config,
            setting["real_port"],
            setting["dummy_mode"],
            setting["speedup"],
            setting["msg_count"],
        )

        return (proxy_thread, control_thread)
    except:
        notify_error(config, traceback.format_exc())
        raise


def wait_and_term(proxy_thread, control_thread):
    proxy_thread.join()
    control_thread.join()


######################################################################
if __name__ == "__main__":
    args = docopt(__doc__)

    config_file = args["-c"]
    server_port = int(os.environ.get("HEMS_SERVER_PORT", args["-p"]))
    real_port = int(args["-r"])
    dummy_mode = args["-D"]
    speedup = int(args["-t"])
    debug_mode = args["-d"]
    client_mode = args["-C"]
    server_host = args["-s"]
    msg_count = int(args["-n"])
    view_msg_mode = args["-V"]

    app_arg = {
        "config_file": config_file,
        "server_host": server_host,
        "real_port": real_port,
        "server_port": server_port,
        "client_mode": client_mode,
        "view_msg_mode": view_msg_mode,
        "dummy_mode": dummy_mode,
        "debug_mode": debug_mode,
        "speedup": speedup,
        "msg_count": msg_count,
    }

    wait_and_term(*start(app_arg))

    sys.exit(0)
