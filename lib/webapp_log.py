#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from enum import IntEnum
from flask import jsonify, Blueprint, g, current_app
import logging
import threading
import sqlite3
from multiprocessing.pool import ThreadPool

from webapp_config import APP_URL_PREFIX, LOG_DB_PATH
from webapp_event import notify_event, EVENT_TYPE
from flask_util import support_jsonp, gzipped
import notify_slack


class APP_LOG_LEVEL(IntEnum):
    INFO = 0
    WARN = 1
    ERROR = 2


blueprint = Blueprint("webapp-log", __name__, url_prefix=APP_URL_PREFIX)

config = None
sqlite = None
log_lock = None
thread_pool = None


@blueprint.before_app_first_request
def init():
    global config
    global sqlite
    global log_lock
    global thread_pool

    config = current_app.config["CONFIG"]

    sqlite = sqlite3.connect(LOG_DB_PATH, check_same_thread=False)
    sqlite.execute("CREATE TABLE IF NOT EXISTS log(date INT, message TEXT)")
    sqlite.commit()
    sqlite.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))

    log_lock = threading.Lock()
    thread_pool = ThreadPool(processes=3)


def app_log_impl(message, level):
    with log_lock:
        sqlite.execute(
            'INSERT INTO log VALUES (DATETIME("now", "localtime"), ?)', [message]
        )
        sqlite.execute(
            'DELETE FROM log WHERE date <= DATETIME("now", "localtime", "-60 days")'
        )
        sqlite.commit()

        notify_event(EVENT_TYPE.LOG)

    if level == APP_LOG_LEVEL.ERROR:
        if "slack" in config:
            notify_slack.error(
                config["slack"]["bot_token"],
                config["slack"]["error"]["channel"]["name"],
                config["slack"]["from"],
                message,
                config["slack"]["error"]["interval_min"],
            )

        if current_app.config["DUMMY_MODE"]:
            logging.error("This application is terminated because it is in dummy mode.")
            os._exit(-1)


def app_log(message, level=APP_LOG_LEVEL.INFO):
    global thread_pool

    if level == APP_LOG_LEVEL.ERROR:
        logging.error(message)
    elif level == APP_LOG_LEVEL.WARN:
        logging.warning(message)
    else:
        logging.info(message)

    # NOTE: ブラウザからアクセスされる前に再起動される場合．
    if thread_pool is None:
        app_log_impl(message)

    # NOTE: 実際のログ記録は別スレッドに任せて，すぐにリターンする
    thread_pool.apply_async(app_log_impl, (message, level))


@blueprint.route("/api/log_clear", methods=["GET"])
@support_jsonp
def api_log_clear():
    with log_lock:
        cur = sqlite.cursor()
        cur.execute("DELETE FROM log")
    app_log("🧹 ログがクリアされました。")

    return jsonify({"result": "success"})


@blueprint.route("/api/log_view", methods=["GET"])
@support_jsonp
@gzipped
def api_log_view():
    g.disable_cache = True

    cur = sqlite.cursor()
    cur.execute("SELECT * FROM log")
    return jsonify({"data": cur.fetchall()[::-1]})


if __name__ == "__main__":
    import logger
    import time

    logger.init("test", level=logging.INFO)

    init()

    for i in range(5):
        app_log("テスト {i}".format(i=i))

    time.sleep(1)

    thread_pool.close()
    thread_pool.terminate()
