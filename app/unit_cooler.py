#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# エアコン室外機冷却システム用スクリプト．
# 室外機への噴霧を制御しつつ，実際に噴霧した量のモニタリングを行います．

import os
import socket
import sys
import time
import pathlib
import logging
import fluent.sender

sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir, "lib"))

import sense_data
import fd_q10c
import aircon
import valve
import notifier
from config import load_config
import logger


# 外気温がこの温度を超えていたら間欠制御を停止し，常時 ON にする
INTERM_TEMP_THRESHOLD = 34

# 電磁弁の故障を検出したときに作成するファイル
STAT_HAZARD = pathlib.Path("/dev/shm") / "hazard"


def get_outdoor_temp(config):
    return sense_data.get_db_value(
        config["influxdb"],
        config["sensor"]["temperature"][0]["hostname"],
        config["sensor"]["temperature"][0]["measure"],
        "temp",
    )


def is_cooler_working(config, temp):
    for item in config["sensor"]["power"]:
        try:
            if aircon.get_cooler_state(config, item["measure"], item["hostname"], temp):
                return True
        except:
            pass
    else:
        return False


def judge_control_mode(config):
    temp = get_outdoor_temp(config)
    state = is_cooler_working(config, temp)

    interm = temp < INTERM_TEMP_THRESHOLD

    return {"state": state, "interm": interm}


def hazard_detected(config, message):
    notifier.send(config, message)

    STAT_HAZARD.touch()
    valve.ctrl_valve(False)


def control_valve(config, valve_mode):
    logging.info("Judge mode")

    if STAT_HAZARD.exists():
        hazard_detected(config, "水漏れもしくは電磁弁の故障が過去に検出されているので制御を停止しています．")

    logging.info("Control valve")
    valve.init(config["valve"]["pin_no"])
    duration = valve.set_state(valve_mode["state"], valve_mode["interm"])

    return duration


def check_valve(config, valve_state):
    flow = -1
    if valve_state:
        if duration > 10:
            flow = fd_q10c.sense()
            if flow < 0.02:
                notifier.send(config, "元栓が閉じています．")
            elif flow > 2:
                hazard_detected(config, "水漏れしています．")
    else:
        if duration / (60 * 60) > 1:
            # NOTE: 電磁弁をしばらく使っていない場合は，流量計の電源を切る
            fd_q10c.stop()
        else:
            flow = fd_q10c.sense()
            if (duration > 100) and (flow > 0.01):
                hazard_detected(config, "電磁弁が壊れています．")

    if flow == -1:
        flow = fd_q10c.sense(False)


def send_spray_state(sender, hostname, spray_state):
    logging.info("Send valve state")

    spray_state.update({"hostname": hostname})
    if sender.emit("rasp", spray_state):
        logging.info("Send OK")
    else:
        logging.error(sender.last_error)


######################################################################
logger.init("Outdoor unit coolerr")

logging.info("Load config...")
config = load_config()

hostname = os.environ.get("NODE_HOSTNAME", socket.gethostname())

logging.info("Hostanm: {hostname}".format(hostname=hostname))

sender = fluent.sender.FluentSender("sensor", host=config["fluent"]["host"])

while True:
    logging.info("Start.")

    valve_mode = judge_control_mode(config)
    duration = control_valve(config, valve_mode)
    valve_state = valve.get_state()
    flow = check_valve(config, valve_state)

    spray_state = {"flow": flow, "valve": valve_state}
    send_spray_state(sender, hostname, spray_state)

    logging.info("Finish.")
    pathlib.Path(config["liveness"]["file"]).touch()

    logging.info(
        "sleep {sleep_time} sec...".format(sleep_time=config["sense"]["interval"])
    )
    time.sleep(config["sense"]["interval"])
