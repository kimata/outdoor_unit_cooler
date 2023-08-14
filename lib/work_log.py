#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from enum import IntEnum
import logging

import webapp_log
import webapp_event
from control import notify_error


class WORK_LOG_LEVEL(IntEnum):
    INFO = webapp_log.APP_LOG_LEVEL.INFO
    WARN = webapp_log.APP_LOG_LEVEL.WARN
    ERROR = webapp_log.APP_LOG_LEVEL.ERROR


config = None
queue = None

log_hist = []


def init(config_, queue_):
    global config
    global queue

    config = config_
    queue = queue_

    webapp_log.init(config)


def term():
    global queue
    queue.close()
    webapp_log.term()


# NOTE: テスト用
def hist_clear():
    global log_hist

    log_hist = []


# NOTE: テスト用
def hist_get():
    global log_hist

    return log_hist


def work_log(message, level=WORK_LOG_LEVEL.INFO):
    global log_hist
    global queue

    queue.put(webapp_event.EVENT_TYPE.LOG)
    webapp_log.app_log(message, level)

    log_hist.append(message)

    if level == WORK_LOG_LEVEL.ERROR:
        notify_error(config, message, False)


if __name__ == "__main__":
    import logger
    from config import load_config

    logger.init("test", level=logging.INFO)

    init(load_config())

    print(webapp_log.get_log())
