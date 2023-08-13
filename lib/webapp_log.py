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
from multiprocessing import Queue
from wsgiref.handlers import format_date_time
from webapp_config import APP_URL_PREFIX, LOG_DB_PATH
from webapp_event import notify_event, EVENT_TYPE
from flask_util import support_jsonp, gzipped
import notify_slack
import traceback


class APP_LOG_LEVEL(IntEnum):
    INFO = 0
    WARN = 1
    ERROR = 2


blueprint = Blueprint("webapp-log", __name__, url_prefix=APP_URL_PREFIX)

sqlite = None
log_thread = None
log_lock = None
log_queue = None
config = None
should_terminate = False


def init(config_, is_read_only=False):
    global config
    global sqlite
    global log_lock
    global log_queue
    global log_thread
    global should_terminate

    config = config_

    if sqlite is None:
        LOG_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        sqlite = sqlite3.connect(LOG_DB_PATH, check_same_thread=False)
        sqlite.execute(
            "CREATE TABLE IF NOT EXISTS log(id INTEGER primary key autoincrement, date INTEGER, message TEXT)"
        )
        sqlite.commit()
        sqlite.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))

    if not is_read_only:
        should_terminate = False

        log_lock = threading.Lock()
        log_queue = Queue()
        log_thread = threading.Thread(target=app_log_worker, args=(log_queue,))
        log_thread.start()


def term(is_read_only=False):
    global sqlite
    global log_thread
    global should_terminate

    if sqlite is not None:
        sqlite.close()
        sqlite = None

    if not is_read_only:
        if log_thread is None:
            return
        should_terminate = True

        log_queue.close()
        log_thread.join()
        log_thread = None


def app_log_impl(message, level):
    global config
    global sqlite

    with log_lock:
        assert sqlite is not None

        sqlite.execute(
            'INSERT INTO log VALUES (NULL, DATETIME("now", "localtime"), ?)',
            [message],
        )
        sqlite.execute('DELETE FROM log WHERE date <= DATETIME("now", "localtime", "-60 days")')
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

        if (os.environ.get("DUMMY_MODE", "false") == "true") and (
            os.environ.get("TEST", "false") != "true"
        ):  # pragma: no cover
            logging.error("This application is terminated because it is in dummy mode.")
            os._exit(-1)


def app_log_worker(log_queue):
    global should_terminate

    assert log_queue is not None

    sleep_sec = 0.4

    while True:
        if should_terminate:
            break

        try:
            if not log_queue.empty():
                log = log_queue.get()
                app_log_impl(log["message"], log["level"])
        except OverflowError:  # pragma: no cover
            # NOTE: テストする際，freezer 使って日付をいじるとこの例外が発生する
            logging.debug(traceback.format_exc())
            pass
        except ValueError:  # pragma: no cover
            # NOTE: 終了時，queue が close された後に empty() や get() を呼ぶとこの例外が
            # 発生する．
            logging.warning(traceback.format_exc())
            pass

        time.sleep(sleep_sec)


def app_log(message, level=APP_LOG_LEVEL.INFO):
    global log_queue

    assert log_queue is not None

    if level == APP_LOG_LEVEL.ERROR:
        logging.error(message)
    elif level == APP_LOG_LEVEL.WARN:
        logging.warning(message)
    else:
        logging.info(message)

    # NOTE: 実際のログ記録は別スレッドに任せて，すぐにリターンする
    log_queue.put({"message": message, "level": level})


def get_log(stop_day):
    global sqlite

    assert sqlite is not None

    # NOTE: stop_day 日前までののログしか出さない
    cur = sqlite.cursor()
    cur.execute(
        'SELECT * FROM log WHERE date <= DATETIME("now", "localtime", ?) ORDER BY id DESC LIMIT 500',
        ["-{stop_day} days".format(stop_day=stop_day)],
    )
    return cur.fetchall()


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
        last_time = datetime.datetime.strptime(log[0]["date"], "%Y-%m-%d %H:%M:%S").timestamp()

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
