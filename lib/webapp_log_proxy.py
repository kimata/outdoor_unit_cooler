#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import jsonify, Blueprint
import logging
import requests
import json

from webapp_config import APP_URL_PREFIX
from flask_util import support_jsonp, gzipped


blueprint = Blueprint("webapp-proxy", __name__, url_prefix=APP_URL_PREFIX)

api_url = None


def init(api_url_):
    global api_url

    api_url = api_url_


def get_log():
    global api_url

    try:
        # NOTE: 簡易リバースプロキシ
        res = requests.get(api_url)

        # NOTE: どのみち，また JSON 文字列に戻すけど...
        return json.loads(res.text)["data"]
    except:
        logging.error("Unable to fetch log from {url}".format(url=api_url))
        return []


@blueprint.route("/api/log_view", methods=["GET"])
@support_jsonp
@gzipped
def api_log_view():

    return jsonify({"data": get_log()})


if __name__ == "__main__":
    import logger
    from config import load_config

    logger.init("test", level=logging.INFO)

    init(load_config()["web"]["log_api"]["url"])

    print(get_log())
