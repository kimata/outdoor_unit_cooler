#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import (
    send_from_directory,
    Blueprint,
)

from webapp_config import APP_URL_PREFIX, STATIC_FILE_PATH
from flask_util import gzipped

blueprint = Blueprint("webapp-base", __name__, url_prefix=APP_URL_PREFIX)


@blueprint.route("/", defaults={"filename": "index.html"})
@blueprint.route("/<path:filename>")
@gzipped
def angular(filename):
    return send_from_directory(STATIC_FILE_PATH, filename)
