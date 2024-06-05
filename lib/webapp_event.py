#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import multiprocessing
import threading
import time
import traceback
from enum import Enum

from flask import Blueprint, Response, request, stream_with_context
from webapp_config import APP_URL_PREFIX

blueprint = Blueprint("webapp-event", __name__, url_prefix=APP_URL_PREFIX)


class EVENT_TYPE(Enum):
    CONTROL = "control"
    SCHEDULE = "schedule"
    LOG = "log"


# NOTE: サイズは上の Enum の個数+1 にしておく
event_count = multiprocessing.Array("i", 4)

is_stop_watch = False
watch_thread = None


def notify_watch_impl(queue):
    global is_stop_watch

    logging.info("Start notify watch thread")

    while True:
        if is_stop_watch:
            break
        try:
            if not queue.empty():
                notify_event(queue.get())
            time.sleep(0.1)

        except OverflowError:  # pragma: no cover
            # NOTE: テストする際，freezer 使って日付をいじるとこの例外が発生する
            logging.debug(traceback.format_exc())
            pass
        except ValueError:  # pragma: no cover
            # NOTE: 終了時，queue が close された後に empty() や get() を呼ぶとこの例外が
            # 発生する．
            logging.warning(traceback.format_exc())
            pass

    logging.warning("Stop notify watch thread")


def notify_watch(queue):
    global is_stop_watch
    global watch_thread

    is_stop_watch = False

    watch_thread = threading.Thread(target=notify_watch_impl, args=(queue,))
    watch_thread.start()


def stop_watch():
    global is_stop_watch
    global watch_thread

    if watch_thread is not None:
        is_stop_watch = True
        # NOTE: pytest で freezer 使うと下記で固まるので join を見送る
        # watch_thread.join()
        watch_thread = None


def event_index(event_type):
    if event_type == EVENT_TYPE.CONTROL:
        return 0
    elif event_type == EVENT_TYPE.SCHEDULE:
        return 1
    elif event_type == EVENT_TYPE.LOG:
        return 2
    else:  # pragma: no cover
        return 3


def notify_event(event_type):
    global event_count

    event_count[event_index(event_type)] += 1


@blueprint.route("/api/event", methods=["GET"])
def api_event():
    count = request.args.get("count", 0, type=int)

    def event_stream():
        global event_count

        last_count = []
        for i in range(len(event_count)):
            last_count.append(event_count[i])

        i = 0
        j = 0
        while True:
            time.sleep(0.5)
            for name, event_type in EVENT_TYPE.__members__.items():
                index = event_index(event_type)

                if last_count[index] != event_count[index]:
                    logging.debug("notify event: {name}".format(name=event_type.value))
                    yield "data: {}\n\n".format(event_type.value)
                    last_count[index] = event_count[index]

                    i += 1

                    if i == count:
                        return
            # NOTE: クライアントが切断された時にソケットを解放するため，定期的に yield を呼ぶ
            j += 1
            if j == 100:
                yield "data: dummy\n\n"
                j = 0

    res = Response(stream_with_context(event_stream()), mimetype="text/event-stream")
    res.headers.add("Access-Control-Allow-Origin", "*")
    res.headers.add("Cache-Control", "no-cache")
    res.headers.add("X-Accel-Buffering", "no")

    return res
