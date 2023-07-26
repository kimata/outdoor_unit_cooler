#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Liveness のチェックを行います

Usage:
  healthz.py [-c CONFIG] [-m MODE] [-p PORT] [-d]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -m (CRTL|ACT|WEB) : 動作モード [default: CTRL]
  -p PORT           : WEB サーバのポートを指定します．[default: 5000]
  -d                : デバッグモードで動作します．
"""

from docopt import docopt

import requests
import logging
import pathlib
import datetime
import sys


sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

import logger
from config import load_config


def check_liveness_impl(name, liveness_file, interval):
    if not liveness_file.exists():
        logging.warning("{name} is not executed.".format(name=name))
        return False

    elapsed = datetime.datetime.now() - datetime.datetime.fromtimestamp(
        liveness_file.stat().st_mtime
    )
    # NOTE: 少なくとも1分は様子を見る
    if elapsed.seconds > max(interval * 2, 60):
        logging.warning(
            "Execution interval of {name} is too long. ({elapsed:,} sec)".format(
                name=name, elapsed=elapsed.seconds
            )
        )
        return False

    return True


def check_port(port):
    try:
        if (
            requests.get(
                "http://{address}:{port}/".format(address="127.0.0.1", port=port)
            ).status_code
            == 200
        ):
            return True
    except:
        pass

    logging.warning("Failed to access Flask web server")

    return False


def check_liveness(target_list, port=None):
    for target in target_list:
        if not check_liveness_impl(
            target["name"], target["liveness_file"], target["interval"]
        ):
            return False

    if (port is not None) and (not check_port(port)):
        return False

    return True


######################################################################
args = docopt(__doc__)

config_file = args["-c"]
watch_mode = args["-m"]
port = args["-p"]
debug_mode = args["-d"]

if debug_mode:
    log_level = logging.DEBUG
else:
    log_level = logging.INFO

logger.init(
    "hems.unit_cooler",
    level=log_level,
)

logging.info("Using config config: {config_file}".format(config_file=config_file))
config = load_config(config_file)

logging.info("Mode: {watch_mode}".format(watch_mode=watch_mode))
if watch_mode == "CTRL":
    name_list = ["controller"]
    port = None
elif watch_mode == "WEB":
    name_list = ["web"]
else:
    name_list = ["receiver", "actuator", "monitor"]
    port = None

target_list = []
for name in name_list:
    target_list.append(
        {
            "name": name,
            "liveness_file": pathlib.Path(config[name]["liveness"]["file"]),
            "interval": config["controller"]["interval_sec"]
            if (name == "receiver") or (name == "web")
            else config[name]["interval_sec"],
        }
    )

if check_liveness(target_list, port):
    logging.info("OK.")
    sys.exit(0)
else:
    sys.exit(-1)
