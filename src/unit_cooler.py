#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import fd_q10c
import aircon
import valve
import notifier
import yaml
import pathlib
import os
import logger

logger.init("unit_cooler")

with open(str(pathlib.Path(os.path.dirname(__file__), "config.yaml"))) as file:
    config = yaml.safe_load(file)

state = aircon.get_state("書斎エアコン")
duration = valve.set_state(state)

flow = fd_q10c.sense()

logging.info("flow: {flow} L/min".format(flow=flow))

if state:
    if (duration > 10) and (flow < 0.01):
        notifier.send(config, "元栓が閉じています．")
else:
    if duration / (60 * 60) > 1:
        fd_q10c.stop()

    if (duration > 100) and (flow > 0.01):
        notifier.send(config, "電磁弁が壊れています．")
