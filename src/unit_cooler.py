#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import yaml
import pathlib
import os
import logging

import fd_q10c
import aircon
import valve
import notifier
import logger


logger.init("unit_cooler")

with open(str(pathlib.Path(os.path.dirname(__file__), "config.yaml"))) as file:
    config = yaml.safe_load(file)

state = aircon.get_state("書斎エアコン") or aircon.get_state("和室エアコン")
duration = valve.set_state(state)

if state:
    if duration > 10:
        flow = fd_q10c.sense()
        if flow < 0.01:
            notifier.send(config, "元栓が閉じています．")
else:
    if duration / (60 * 60) > 1:
        fd_q10c.stop()
    elif duration > 100:
        flow = fd_q10c.sense()
        if flow > 0.01:
            notifier.send(config, "電磁弁が壊れています．")
