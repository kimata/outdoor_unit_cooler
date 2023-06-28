#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import Blueprint, Response
from enum import Enum
import threading
import time
import logging
import multiprocessing

from webapp_config import APP_URL_PREFIX

blueprint = Blueprint("webapp-event", __name__, url_prefix=APP_URL_PREFIX)


class EVENT_TYPE(Enum):
    CONTROL = "control"
    SCHEDULE = "schedule"
    LOG = "log"


# NOTE: サイズは上の Enum の個数+1 にしておく
event_count = multiprocessing.Array("i", 4)

is_stop_watch = False


def notify_watch_impl(queue):
    global is_stop_watch

    logging.info("Start notify watch thread")

    while True:
        while not queue.empty():
            notify_event(queue.get())
        time.sleep(0.1)

        if is_stop_watch:
            break

    logging.info("Stop notify watch thread")


def notify_watch(queue):
    global is_stop_watch

    is_stop_watch = False
    threading.Thread(target=notify_watch_impl, args=(queue,)).start()


def stop_watch():
    global is_stop_watch

    is_stop_watch = True


def event_index(event_type):
    if event_type == EVENT_TYPE.CONTROL:
        return 0
    elif event_type == EVENT_TYPE.SCHEDULE:
        return 1
    elif event_type == EVENT_TYPE.LOG:
        return 2
    else:
        return 3


def notify_event(event_type):
    global event_count
    event_count[event_index(event_type)] += 1


@blueprint.route("/api/event", methods=["GET"])
def api_event():
    global event_count

    def event_stream():
        last_count = []
        for i in range(len(event_count)):
            last_count.append(event_count[i])

        while True:
            time.sleep(1)
            for name, event_type in EVENT_TYPE.__members__.items():
                i = event_index(event_type)

                if last_count[i] != event_count[i]:
                    logging.debug("notify event: {name}".format(name=event_type.value))
                    yield "data: {}\n\n".format(event_type.value)
                    last_count[i] = event_count[i]

    res = Response(event_stream(), mimetype="text/event-stream")
    res.headers.add("Access-Control-Allow-Origin", "*")
    res.headers.add("Cache-Control", "no-cache")
    res.headers.add("X-Accel-Buffering", "no")

    return res
