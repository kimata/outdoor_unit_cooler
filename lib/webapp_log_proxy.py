#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import jsonify, Blueprint, request, g
import logging
import requests
import os
import json

from webapp_config import APP_URL_PREFIX
from flask_util import support_jsonp, gzipped
from wsgiref.handlers import format_date_time

blueprint = Blueprint("webapp-proxy", __name__, url_prefix=APP_URL_PREFIX)

api_url = None


def init(api_url_):
    global api_url

    api_url = api_url_


def get_log():
    global api_url

    stop_day = 7 if os.environ.get("DUMMY_MODE", "false") == "true" else 0

    try:
        # NOTE: 簡易リバースプロキシ
        res = requests.get(api_url, params={"stop_day ": stop_day})

        # NOTE: どのみち，また JSON 文字列に戻すけど...
        return json.loads(res.text)
    except:
        logging.error("Unable to fetch log from {url}".format(url=api_url))
        return []


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
