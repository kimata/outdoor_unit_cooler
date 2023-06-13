#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import Blueprint, Response
from enum import Enum
import time

from webapp_config import APP_URL_PREFIX

blueprint = Blueprint("webapp-event", __name__, url_prefix=APP_URL_PREFIX)


class EVENT_TYPE(Enum):
    CONTROL = "control"
    SCHEDULE = "schedule"
    LOG = "log"


event_count = {
    EVENT_TYPE.CONTROL: 0,
    EVENT_TYPE.SCHEDULE: 0,
    EVENT_TYPE.LOG: 0,
}


def notify_event(event_type):
    global event_count

    event_count[event_type] += 1


@blueprint.route("/api/event", methods=["GET"])
def api_event():
    global event_count

    def event_stream():
        last_count = event_count.copy()
        while True:
            time.sleep(0.1)
            for method in last_count:
                if last_count[method] != event_count[method]:
                    yield "data: {}\n\n".format(method.value)
                    last_count[method] = event_count[method]

    res = Response(event_stream(), mimetype="text/event-stream")
    res.headers.add("Access-Control-Allow-Origin", "*")
    res.headers.add("Cache-Control", "no-cache")

    return res
