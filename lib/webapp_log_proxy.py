#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import jsonify, Blueprint, request, Response, g
import logging
import requests
import time
import os
import json
import sseclient  # つかうのは sseclient，sseclient-py ではない

from webapp_config import APP_URL_PREFIX
from flask_util import support_jsonp, gzipped
from wsgiref.handlers import format_date_time

blueprint = Blueprint("webapp-proxy", __name__, url_prefix=APP_URL_PREFIX)

api_base_url = None


def init(api_base_url_):
    global api_base_url

    api_base_url = api_base_url_


def get_log():
    global api_base_url

    stop_day = 7 if os.environ.get("DUMMY_MODE", "false") == "true" else 0

    try:
        url = "{base_url}{api_endpoint}".format(
            base_url=api_base_url, api_endpoint="/api/log_view"
        )

        # NOTE: 簡易リバースプロキシ
        res = requests.get(url, params={"stop_day": stop_day})
        res.raise_for_status()

        # NOTE: どのみち，また JSON 文字列に戻すけど...
        return json.loads(res.text)
    except:
        logging.error("Unable to fetch log from {url}".format(url=url))
        return {"data": [], "last_time": time.time()}


# NOTE: リバースプロキシの場合は，webapp_event ではなく，
# ここで /api/event をハンドリングする
@blueprint.route("/api/event", methods=["GET"])
def api_event():
    count = request.args.get("count", 0, type=int)

    # NOTE: EventStream を中継する
    def event_stream():
        url = "{base_url}{api_endpoint}".format(
            base_url=api_base_url, api_endpoint="/api/event"
        )
        sse = sseclient.SSEClient(url)
        i = 0
        for event in sse:
            yield "data: {}\n\n".format(event.data)
            i += 1

            if i == count:
                return
        pass  # pragma: no cover

    res = Response(event_stream(), mimetype="text/event-stream")
    res.headers.add("Access-Control-Allow-Origin", "*")
    res.headers.add("Cache-Control", "no-cache")
    res.headers.add("X-Accel-Buffering", "no")

    return res


@blueprint.route("/api/log_view", methods=["GET"])
@support_jsonp
@gzipped
def api_log_view():
    # NOTE: @gzipped をつけた場合，キャッシュ用のヘッダを付与しているので，
    # 無効化する．
    g.disable_cache = True
    log = get_log()

    response = jsonify(log)

    response.headers["Last-Modified"] = format_date_time(log["last_time"])
    response.make_conditional(request)

    return response


if __name__ == "__main__":
    import logger
    from config import load_config

    logger.init("test", level=logging.INFO)

    init(load_config()["web"]["log_api"]["url"])

    print(get_log())
