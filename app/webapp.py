#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
エアコン室外機の Web UI アプリケーションです．
水やりを自動化するアプリのサーバーです

Usage:
  webapp.py [-c CONFIG] [-s SERVER_HOST] [-p SERVER_PORT]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -s SERVER_HOST    : サーバーのホスト名を指定します． [default: localhost]
  -p SERVER_PORT    : ZeroMQ の サーバーを動作させるポートを指定します． [default: 2222]
"""

from docopt import docopt

from flask import Flask
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

import valve


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


if __name__ == "__main__":
    import logger
    from config import load_config
    import os

    args = docopt(__doc__)

    config_file = args["-c"]
    server_hostname = os.environ.get("HEMS_SERVER_HOST", args["-s"])
    server_host = nslookup(server_hostname)
    server_port = os.environ.get("HEMS_SERVER_PORT", args["-p"])

    logger.init("hems.unit_cooler", level=logging.INFO)

    logging.info(
        "Using ZMQ server of {server_host}:{server_port} (hostname: {server_hostname})".format(
            server_hostname=server_hostname,
            server_host=server_host,
            server_port=server_port,
        )
    )

    # NOTE: アクセスログは無効にする
    # logging.getLogger("werkzeug").setLevel(logging.ERROR)

    app = Flask(__name__)

    app.config["CONFIG"] = load_config(config_file)
    app.config["SERVER_HOST"] = server_host
    app.config["SERVER_PORT"] = server_port

    app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

    app.register_blueprint(unit_cooler_info.blueprint)

    app.register_blueprint(webapp_base.blueprint)
    app.register_blueprint(webapp_event.blueprint)
    app.register_blueprint(webapp_log.blueprint)
    app.register_blueprint(webapp_util.blueprint)

    # app.debug = True
    # NOTE: スクリプトの自動リロード停止したい場合は use_reloader=False にする
    app.run(host="0.0.0.0", threaded=True, use_reloader=True)
