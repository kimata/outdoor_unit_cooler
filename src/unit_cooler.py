#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import yaml
import pathlib
import os
import sys

import fd_q10c
import aircon
import valve
import notifier
import logger


# 外気温がこの温度を超えていたら間欠制御を停止し，常時 ON にする
INTERM_TEMP_THRESHOLD = 30

STAT_HAZARD = pathlib.Path("/dev/shm") / "hazard"


def get_aircon_state(config):
    item_list = [
        {"tag": "hems.sharp", "name": "リビングエアコン"},
        {"tag": "fplug", "name": "書斎エアコン"},
        {"tag": "fplug", "name": "和室エアコン"},
    ]

    for item in item_list:
        if aircon.get_state(config, item["tag"], item["name"]):
            return True
    return False


def hazard_detected():
    STAT_HAZARD.touch()
    valve.ctrl_valve(False)
    sys.exit(-1)


logger.init("unit_cooler")

with open(str(pathlib.Path(os.path.dirname(__file__), "config.yml"))) as file:
    config = yaml.safe_load(file)

state = get_aircon_state(config)

try:
    interm = aircon.get_outdoor_temp() < INTERM_TEMP_THRESHOLD
except:
    interm = False

valve.init(config["valve"]["pin_no"])
duration = valve.set_state(state, interm)

if STAT_HAZARD.exists():
    notifier.send(config, "水漏れもしくは電磁弁の故障が過去に検出されているので制御を停止しています．")
    sys.exit(0)

if state:
    flow = fd_q10c.sense()
    if duration > 10:
        if flow < 0.02:
            notifier.send(config, "元栓が閉じています．")
        elif flow > 1:
            notifier.send(config, "水漏れしています．")
            hazard_detected()

else:
    if duration / (60 * 60) > 1:
        fd_q10c.stop()
    else:
        flow = fd_q10c.sense()
        if (duration > 100) and (flow > 0.01):
            notifier.send(config, "電磁弁が壊れています．")
            hazard_detected()
