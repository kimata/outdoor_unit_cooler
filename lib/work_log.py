#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from enum import IntEnum
import logging


import notify_slack
import webapp_log
import webapp_event


class WORK_LOG_LEVEL(IntEnum):
    INFO = webapp_log.APP_LOG_LEVEL.INFO
    WARN = webapp_log.APP_LOG_LEVEL.WARN
    ERROR = webapp_log.APP_LOG_LEVEL.ERROR


config = None
queue = None


def init(config_, queue_):
    global config
    global queue

    config = config_
    queue = queue_

    webapp_log.init(config)


def work_log(message, level=WORK_LOG_LEVEL.INFO):
    global queue

    queue.put(webapp_event.EVENT_TYPE.LOG)
    webapp_log.app_log(message, level)

    if level == WORK_LOG_LEVEL.ERROR:
        notify_error(config, message)


def notify_error(message, is_log=False):
    global config

    if is_log:
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


if __name__ == "__main__":
    import logger
    import os
    from config import load_config

    logger.init("test", level=logging.INFO)

    init(load_config())

    print(webapp_log.get_log())
