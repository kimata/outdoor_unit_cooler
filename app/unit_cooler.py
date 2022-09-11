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

# 屋外の照度がこの値を下回っていたら，制御を停止する
NIGHT_LUX_THRESHOLD = 100
# 屋外の湿度がこの値を超えていたら常時 OFF にする
INTERM_HUMI_THRESHOLD = 98
# 屋外の温度がこの値を超えていたら間欠制御を停止し，常時 ON にする
INTERM_TEMP_THRESHOLD = 34

# 電磁弁の故障を検出したときに作成するファイル
STAT_HAZARD = pathlib.Path("/dev/shm") / "hazard"


def get_sensor_value(config, sensor_type):
    return sense_data.get_db_value(
        config["influxdb"],
        config["sensor"][sensor_type][0]["hostname"],
        config["sensor"][sensor_type][0]["measure"],
        sensor_type,
    )


def get_cooler_mode(config, temp):
    mode = 0
    for item in config["sensor"]["power"]:
        try:
            mode = max(
                mode,
                aircon.get_cooler_state(
                    config, item["measure"], item["hostname"], temp
                ),
            )
        except:
            pass

    return mode


def judge_control_mode(config):
    logging.info("Judge control mode")
    temp = get_sensor_value(config, "temp")
    humi = get_sensor_value(config, "humi")
    lux = get_sensor_value(config, "lux")
    mode = get_cooler_mode(config, temp)

    logging.info(
        "input: temp={temp:.1f}℃, humi={humi:.1f}% lux={lux:,.0f}, mode={mode}".format(
            temp=temp, humi=humi, lux=lux, mode=mode
        )
    )

    # NOTE: 屋外が暗かったり湿度が非常に高い場合は無条件に動作停止
    if (lux < NIGHT_LUX_THRESHOLD) or (humi > INTERM_HUMI_THRESHOLD):
        state = False
        interm = False
    else:
        # NOTE: エアコンが動いていたら，とりあえず動かす
        state = mode != 0

        # NOTE: 間欠動作にするかどうかは，屋外の温度とクーラーの動作モードで決める
        if temp < INTERM_TEMP_THRESHOLD:
            if mode < 2:
                interm = True
            else:
                interm = False
        else:
            interm = False

    logging.info(
        "output: state={state}, interm={interm}".format(state=state, interm=interm)
    )

    return {"state": state, "interm": interm}


def hazard_detected(config, message):
    notifier.send(config, message)

    STAT_HAZARD.touch()
    valve.ctrl_valve(False)


def init_valve():
    # NOTE: バルブの故障を誤判定しないよう，まずはバルブを閉じた状態にする
    logging.info("Initialize valve")
    valve.init(config["valve"]["pin_no"])
    valve.set_state(False, False)
    time.sleep(5)


def control_valve(config, valve_mode):
    logging.info("Control valve")

    if STAT_HAZARD.exists():
        hazard_detected(config, "水漏れもしくは電磁弁の故障が過去に検出されているので制御を停止しています．")

    valve.init(config["valve"]["pin_no"])
    duration = valve.set_state(valve_mode["state"], valve_mode["interm"])

    return duration


def check_valve(config, valve_state, duration):
    logging.info("Check valve")
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
                hazard_detected(config, "電磁弁が壊れていますので制御を停止します．")

    if flow == -1:
        flow = fd_q10c.sense(False)

    return flow


def send_spray_state(sender, hostname, spray_state):
    logging.info("Send valve state")

    logging.info(
        "valve = {valve}, flow = {flow:.2f} L/min".format(
            valve="ON" if valve == 1 else "OFF", flow=flow
        )
    )

    spray_state.update({"hostname": hostname})
    if sender.emit("rasp", spray_state):
        logging.info("Send OK")
    else:
        logging.error(sender.last_error)


######################################################################
logger.init("hems.unit_cooler")

logging.info("Load config...")
config = load_config()

hostname = os.environ.get("NODE_HOSTNAME", socket.gethostname())

logging.info("Hostname: {hostname}".format(hostname=hostname))

sender = fluent.sender.FluentSender("sensor", host=config["fluent"]["host"])

init_valve()

prev_mode = {"state": False, "interm": False}
while True:
    logging.info("Start.")

    valve_mode = judge_control_mode(config)
    duration = control_valve(config, valve_mode)
    valve_state = valve.get_state()

    if (
        prev_mode["state"]
        and valve_mode["state"]
        and (prev_mode["interm"] != valve_mode["interm"])
    ):
        # NOTE: 間欠制御モードが変化した場合は duration を 0 にする．
        # これをしないと，OFF Duty 中に間欠制御から定常制御に変わった場合に，
        # 元栓が閉じていると誤判定してしまう．
        duration = 0

    flow = check_valve(config, valve_state, duration)

    spray_state = {"flow": flow, "valve": valve_state}
    send_spray_state(sender, hostname, spray_state)
    prev_mode = valve_mode

    logging.info("Finish.")
    pathlib.Path(config["liveness"]["file"]).touch()

    logging.info(
        "sleep {sleep_time} sec...".format(sleep_time=config["sense"]["interval"])
    )
    time.sleep(config["sense"]["interval"])
