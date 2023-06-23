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
