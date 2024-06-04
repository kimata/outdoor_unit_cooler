#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
エアコン室外機の Web UI アプリケーションです．
水やりを自動化するアプリのサーバーです

Usage:
  webapp.py [-c CONFIG] [-s CONTROL_HOST] [-p PUB_PORT] [-a ACTUATOR_HOST] [-n COUNT] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します． [default: config.yaml]
  -s CONTROL_HOST   : コントローラのホスト名を指定します． [default: localhost]
  -p PUB_PORT       : ZeroMQ の Pub サーバーを動作させるポートを指定します． [default: 2222]
  -a ACTUATOR_HOST  : アクチュエータのホスト名を指定します． [default: localhost]
  -n COUNT          : n 回制御メッセージを受信したら終了します．0 は制限なし． [default: 0]
  -D                : ダミーモードで実行します．
"""

import logging
import os
import pathlib
import sys
import threading
from multiprocessing import Queue

from docopt import docopt
from flask import Flask
from flask_cors import CORS

sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

import control_pubsub
import logger
import unit_cooler_info
import webapp_base
import webapp_log_proxy
import webapp_util
from config import load_config

watch_thread = None


def queuing_message(config, message_queue, message):
    if message_queue.full():
        message_queue.get()

    # NOTE: 初回，強制的に関数を呼んで，キャッシュさせる
    if unit_cooler_info.get_last_message.last_message is None:
        unit_cooler_info.get_last_message(config, message_queue)

    logging.debug("receive control message")
    message_queue.put(message)
    pathlib.Path(config["web"]["liveness"]["file"]).touch()


def watch_client(config, server_host, server_port, message_queue, msg_count):
    logging.info("Start watch client (host: {host}:{port})".format(host=server_host, port=server_port))
    control_pubsub.start_client(
        server_host,
        server_port,
        lambda message: queuing_message(config, message_queue, message),
        msg_count,
    )


def create_app(arg):
    global watch_thread
    setting = {
        "config_file": "config.yaml",
        "control_host": "localhost",
        "pub_port": 2222,
        "actuator_host": "localhost",
        "dummy_mode": False,
        "msg_count": 0,
    }
    setting.update(arg)

    logger.init("hems.unit_cooler", level=logging.INFO)

    logging.info(
        "Using ZMQ server of {control_host}:{control_port}".format(
            control_host=setting["control_host"],
            control_port=setting["pub_port"],
        )
    )
    config = load_config(setting["config_file"])

    # NOTE: オプションでダミーモードが指定された場合，環境変数もそれに揃えておく
    if setting["dummy_mode"]:
        os.environ["DUMMY_MODE"] = "true"
    else:
        os.environ["DUMMY_MODE"] = "false"

    message_queue = Queue(10)
    watch_thread = threading.Thread(
        target=watch_client,
        args=(
            config,
            setting["control_host"],
            setting["pub_port"],
            message_queue,
            setting["msg_count"],
        ),
    )
    watch_thread.start()

    # NOTE: アクセスログは無効にする
    # logging.getLogger("werkzeug").setLevel(logging.ERROR)

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        if setting["dummy_mode"]:
            logging.warning("Set dummy mode")
    else:  # pragma: no cover
        pass

    app = Flask("unit_cooler")

    CORS(app)

    app.config["CONFIG"] = config
    app.config["SERVER_HOST"] = setting["control_host"]
    app.config["SERVER_PORT"] = setting["pub_port"]
    app.config["MESSAGE_QUEUE"] = message_queue

    app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

    app.register_blueprint(unit_cooler_info.blueprint)

    app.register_blueprint(webapp_base.blueprint_default)
    app.register_blueprint(webapp_base.blueprint)
    app.register_blueprint(webapp_log_proxy.blueprint)
    app.register_blueprint(webapp_util.blueprint)

    webapp_log_proxy.init("http://{host}:5001/unit_cooler".format(host=setting["actuator_host"]))

    # app.debug = True

    return app


if __name__ == "__main__":
    args = docopt(__doc__)

    config_file = args["-c"]
    control_host = os.environ.get("HEMS_CONTROL_HOST", args["-s"])
    pub_port = int(os.environ.get("HEMS_PUB_PORT", args["-p"]))
    actuator_host = os.environ.get("HEMS_ACTUATOR_HOST", args["-a"])
    dummy_mode = args["-D"]
    msg_count = int(args["-n"])

    app_arg = {
        "config_file": config_file,
        "control_host": control_host,
        "pub_port": pub_port,
        "actuator_host": actuator_host,
        "dummy_mode": dummy_mode,
        "msg_count": msg_count,
    }

    app = create_app(app_arg)

    # NOTE: スクリプトの自動リロード停止したい場合は use_reloader=False にする
    app.run(host="0.0.0.0", threaded=True, use_reloader=True)
