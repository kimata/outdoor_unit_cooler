#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
エアコン室外機の Web UI アプリケーションです．
水やりを自動化するアプリのサーバーです

Usage:
  webapp.py [-c CONFIG] [-s SERVER_HOST] [-p SERVER_PORT] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -s SERVER_HOST    : サーバーのホスト名を指定します． [default: localhost]
  -p SERVER_PORT    : ZeroMQ の サーバーを動作させるポートを指定します． [default: 2222]
  -D                : ダミーモードで実行します．
"""

from docopt import docopt

from flask import Flask
from flask_cors import CORS
import sys
import pathlib
import time
import logging
from socket import getaddrinfo
from socket import AF_INET, SOCK_STREAM
import atexit

sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

import unit_cooler_info
import control_pubsub

import webapp_base
import webapp_util
import webapp_log
import webapp_event


def nslookup(hostname):
    try:
        addrinfolist = getaddrinfo(hostname, None, 0, 0, 0, 0)
    except:
        return None

    for family, kind, proto, canonical, sockaddr in addrinfolist:
        if family != AF_INET:
            continue

        if kind != SOCK_STREAM:
            continue

        return sockaddr[0]
    return None


def notify_terminate():
    webapp_log.app_log("🏃 アプリを再起動します．")
    # NOTE: ログを送信できるまでの時間待つ
    time.sleep(1)


atexit.register(notify_terminate)


def queuing_message(config, message_queue, message):
    if message_queue.full():
        message_queue.get()

    # NOTE: 初回，強制的に関数を呼んで，キャッシュさせる
    if unit_cooler_info.get_last_message.last_message is None:
        unit_cooler_info.get_last_message(config, message_queue)

    logging.debug("receive control message")
    message_queue.put(message)
    pathlib.Path(config["web"]["liveness"]["file"]).touch()


def watch_client(
    config,
    server_host,
    server_port,
    message_queue,
):
    logging.info(
        "Start watch client (host: {host}:{port})".format(
            host=server_host, port=server_port
        )
    )
    control_pubsub.start_client(
        server_host,
        server_port,
        lambda message: queuing_message(config, message_queue, message),
    )


if __name__ == "__main__":
    import logger
    from config import load_config
    from multiprocessing import Queue
    import threading
    import os

    args = docopt(__doc__)

    config_file = args["-c"]
    server_hostname = os.environ.get("HEMS_SERVER_HOST", args["-s"])
    server_host = nslookup(server_hostname)
    server_port = os.environ.get("HEMS_SERVER_PORT", args["-p"])
    dummy_mode = args["-D"]

    logger.init("hems.unit_cooler", level=logging.INFO)

    logging.info(
        "Using ZMQ server of {server_host}:{server_port} (hostname: {server_hostname})".format(
            server_hostname=server_hostname,
            server_host=server_host,
            server_port=server_port,
        )
    )
    config = load_config(config_file)

    # NOTE: オプションでダミーモードが指定された場合，環境変数もそれに揃えておく
    if dummy_mode:
        os.environ["DUMMY_MODE"] = "true"
    else:
        os.environ["DUMMY_MODE"] = "false"

    message_queue = Queue()
    threading.Thread(
        target=watch_client,
        args=(config, server_host, server_port, message_queue),
    ).start()

    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        if dummy_mode:
            logging.warning("Set dummy mode")

    app = Flask(__name__)

    CORS(app)

    app.config["CONFIG"] = config
    app.config["SERVER_HOST"] = server_host
    app.config["SERVER_PORT"] = server_port
    app.config["MESSAGE_QUEUE"] = message_queue

    app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

    app.register_blueprint(unit_cooler_info.blueprint)

    app.register_blueprint(webapp_base.blueprint_default)
    app.register_blueprint(webapp_base.blueprint)
    app.register_blueprint(webapp_event.blueprint)
    app.register_blueprint(webapp_log.blueprint)
    app.register_blueprint(webapp_util.blueprint)

    # app.debug = True
    # NOTE: スクリプトの自動リロード停止したい場合は use_reloader=False にする
    app.run(host="0.0.0.0", threaded=True, use_reloader=True)
