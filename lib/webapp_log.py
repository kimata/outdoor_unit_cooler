#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from enum import IntEnum
from flask import jsonify, Blueprint, request, g
import logging
import threading
import time
import sqlite3
import datetime
from multiprocessing.pool import ThreadPool
from wsgiref.handlers import format_date_time
from webapp_config import APP_URL_PREFIX, LOG_DB_PATH
from webapp_event import notify_event, EVENT_TYPE
from flask_util import support_jsonp, gzipped
import notify_slack


class APP_LOG_LEVEL(IntEnum):
    INFO = 0
    WARN = 1
    ERROR = 2


blueprint = Blueprint("webapp-log", __name__, url_prefix=APP_URL_PREFIX)

sqlite = None
log_lock = None
thread_pool = None
config = None


def init(config_):
    global config
    global sqlite
    global log_lock
    global thread_pool

    config = config_

    sqlite = sqlite3.connect(LOG_DB_PATH, check_same_thread=False)
    sqlite.execute("CREATE TABLE IF NOT EXISTS log(date INT, message TEXT)")
    sqlite.commit()
    sqlite.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))

    log_lock = threading.Lock()
    thread_pool = ThreadPool(processes=3)


def app_log_impl(message, level):
    global config
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

        if os.environ.get("DUMMY_MODE", "false") == "true":
            logging.error("This application is terminated because it is in dummy mode.")
            os._exit(-1)


def app_log(message, level=APP_LOG_LEVEL.INFO, exit=False):
    global thread_pool

    if level == APP_LOG_LEVEL.ERROR:
        logging.error(message)
    elif level == APP_LOG_LEVEL.WARN:
        logging.warning(message)
    else:
        logging.info(message)

    # NOTE: 実際のログ記録は別スレッドに任せて，すぐにリターンする
    thread_pool.apply_async(app_log_impl, (message, level))

    if exit:
        thread_pool.close()


def get_log(stop_day):
    global sqlite

    # NOTE: stop_day 日前までののログしか出さない

    cur = sqlite.cursor()
    cur.execute(
        'SELECT * FROM log WHERE date <= DATETIME("now", "localtime", ?)',
        ["-{stop_day} days".format(stop_day=stop_day)],
    )
    return cur.fetchall()[::-1]


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
    stop_day = request.args.get("stop_day", 0, type=int)

    # NOTE: @gzipped をつけた場合，キャッシュ用のヘッダを付与しているので，
    # 無効化する．
    g.disable_cache = True

    log = get_log(stop_day)

    if len(log) == 0:
        last_time = time.time()
    else:
        last_time = datetime.datetime.strptime(
            log[0]["date"], "%Y-%m-%d %H:%M:%S"
        ).timestamp()

    response = jsonify({"data": log, "last_time": last_time})

    response.headers["Last-Modified"] = format_date_time(last_time)
    response.make_conditional(request)

    return response


if __name__ == "__main__":
    import logger
    from config import load_config

    logger.init("test", level=logging.INFO)

    init(load_config())

    print(get_log(1))
