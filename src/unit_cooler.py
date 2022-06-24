#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import yaml
import pathlib
import os

import fd_q10c
import aircon
import valve
import notifier
import logger


def get_aircon_state():
    item_list = [
        {"tag": "hems.sharp", "name": "リビングエアコン"},
        {"tag": "fplug", "name": "書斎エアコン"},
        {"tag": "fplug", "name": "和室エアコン"},
    ]

    for item in item_list:
        if aircon.get_state(item["tag"], item["name"]):
            return True
    return False


logger.init("unit_cooler")

with open(str(pathlib.Path(os.path.dirname(__file__), "config.yaml"))) as file:
    config = yaml.safe_load(file)

state = get_aircon_state()
duration = valve.set_state(state)

if state:
    flow = fd_q10c.sense()
    if duration > 10:
        if flow < 0.01:
            notifier.send(config, "元栓が閉じています．")
        elif flow > 1:
            notifier.send(config, "水漏れしています．")
else:
    if duration / (60 * 60) > 1:
        fd_q10c.stop()
    else:
        flow = fd_q10c.sense()
        if (duration > 100) and (flow > 0.01):
            notifier.send(config, "電磁弁が壊れています．")
