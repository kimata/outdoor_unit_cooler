#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Liveness のチェックを行います

Usage:
  healthz.py [-c CONFIG] [-C] [-d]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -C                : コントローラモード
  -d                : デバッグモードで動作します．
"""

from docopt import docopt

import logging
import pathlib
import datetime
import os
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


def check_liveness(target_list):
    for target in target_list:
        if not check_liveness_impl(
            target["name"], target["liveness_file"], target["interval"]
        ):
            return False

    return True


######################################################################
args = docopt(__doc__)

config_file = args["-c"]
controller_mode = args["-C"]
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

if controller_mode:
    name_list = ["controller"]
else:
    name_list = ["actuator", "monitor", "receiver"]

target_list = []
for name in name_list:
    target_list.append(
        {
            "name": name,
            "liveness_file": pathlib.Path(config[name]["liveness"]["file"]),
            "interval": config["controller"]["interval_sec"]
            if name == "receiver"
            else config[name]["interval_sec"],
        }
    )

if check_liveness(target_list):
    logging.info("OK.")
    sys.exit(0)
else:
    sys.exit(-1)
