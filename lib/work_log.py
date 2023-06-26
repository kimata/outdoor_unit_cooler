#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from enum import IntEnum
import os
import pathlib
import logging
import threading
import sqlite3
from multiprocessing.pool import ThreadPool

import notify_slack


class WORK_LOG_LEVEL(IntEnum):
    INFO = 0
    WARN = 1
    ERROR = 2


LOG_DB_PATH = pathlib.Path(os.path.dirname(__file__)).parent / "data" / "log.dat"


config = None
sqlite = None
log_lock = None
thread_pool = None


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


def notify_error(config, message):
    logging.error(message)

    if "slack" not in config:
        return

    notify_slack.error(
        config["slack"]["bot_token"],
        config["slack"]["error"]["channel"]["name"],
        config["slack"]["from"],
        message,
        config["slack"]["error"]["interval_min"],
    )


def work_log_impl(message, level):
    global config
    global log_lock

    with log_lock:
        sqlite.execute(
            'INSERT INTO log VALUES (DATETIME("now", "localtime"), ?)', [message]
        )
        sqlite.execute(
            'DELETE FROM log WHERE date <= DATETIME("now", "localtime", "-60 days")'
        )
        sqlite.commit()

    if level == WORK_LOG_LEVEL.ERROR:
        notify_error(config, message)


def work_log(message, level=WORK_LOG_LEVEL.INFO):
    global thread_pool

    thread_pool.apply_async(work_log_impl, (message, level))


def get_work_log(stop_day=0):
    global sqlite

    cur = sqlite.cursor()
    cur.execute(
        'SELECT * FROM log WHERE date <= DATETIME("now", "localtime", ?)',
        ["{stop_day} days".format(stop_day=stop_day)],
    )
    return cur.fetchall()[::-1]


if __name__ == "__main__":
    import logger
    from config import load_config

    logger.init("test", level=logging.INFO)

    init(load_config())

    print(get_work_log())
