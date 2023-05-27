#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
エアコン室外機の冷却モードの指示を出します．

Usage:
  cooler_controller.py [-f CONFIG] [-p SERVER_PORT] [-O] [-D] [-d]
  cooler_controller.py -C [-f CONFIG] [-s SERVER_HOST] [-p SERVER_PORT] [-d]

Options:
  -f CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -p SERVER_PORT    : ZeroMQ の Pub サーバーを動作させるポートを指定します． [default: 2222]
  -O                : 1回のみ実行
  -D                : ダミーモードで実行します．(冷却モードをランダムに生成します)  
  -d                : デバッグモードで動作します．
  -C                : クライアントモード(ダミー)で動作します．CI でのテスト用．
  -s SERVER_HOST    : サーバーのホスト名を指定します． [default: localhost]
"""

from docopt import docopt

import os
import sys
import logging
import pathlib
import traceback

sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir, "lib"))

from valve import COOLING_STATE
import control_pubsub
from sensor_data import fetch_data
import aircon
import notify_slack
from config import load_config
import logger

############################################################
# 制御モードを決めるにあたって，参照する外部環境の閾値
#
# 屋外の照度がこの値未満の場合，冷却の強度を弱める
LUX_THRESHOLD = 500
# 太陽の日射量がこの値未満の場合，冷却の強度を弱める
SOLAR_RAD_THRESHOLD_LOW = 200
# 太陽の日射量がこの値未満の場合，冷却の強度を強める
SOLAR_RAD_THRESHOLD_HIGH = 700
# 屋外の湿度がこの値を超えていたら，冷却を停止する
HUMI_THRESHOLD = 98
# 屋外の温度がこの値を超えていたら，冷却の強度を強める
TEMP_THRESHOLD = 33

DUMMY_MODE_SPEEDUP = 12.0

def notify_error(config):
    if "slack" not in config:
        return
    
    notify_slack.error(
        config["slack"]["bot_token"],
        config["slack"]["error"]["channel"]["name"],
        config["slack"]["from"],
        traceback.format_exc(),
        config["slack"]["error"]["interval_min"],
    )


def get_sense_data(config):
    sense_data = {}

    for kind in config["controller"]["sensor"]:
        kind_data = []
        for sensor in config["controller"]["sensor"][kind]:
            data = fetch_data(
                config["controller"]["influxdb"],
                sensor["measure"],
                sensor["hostname"],
                kind,
                "1h",
                last=True,
            )
            if data["valid"]:
                kind_data.append({"name": sensor["name"], "value": data["value"][0]})
            else:
                logging.warning("{name} のデータを取得できませんでした．".format(name=sensor["name"]))
                kind_data.append({"name": sensor["name"], "value": None})

        sense_data[kind] = kind_data

    return sense_data


# NOTE: クーラーの稼働状況を 5 段階で評価する．
# (5 がフル稼働，0 が非稼働)
def get_cooler_status(sense_data):
    mode_map = {}

    for mode in aircon.MODE:
        mode_map[mode] = 0

    temp = sense_data["temp"][0]["value"]
    for aircon_power in sense_data["power"]:
        mode = aircon.get_cooler_state(aircon_power, temp)
        mode_map[mode] += 1

    logging.info(mode_map)

    if mode_map[aircon.MODE.FULL] >= 2:
        logging.info("エアコンが，2 台以上フル稼働しています．(cooler_status: 6)")
        return 6
    elif (mode_map[aircon.MODE.FULL] >= 1) and (mode_map[aircon.MODE.NORMAL] >= 1):
        logging.info("1 台以上のエアコンがフル稼働しています．(cooler_status: 5)")
        return 5
    elif mode_map[aircon.MODE.NORMAL] >= 2:
        logging.info("2 台以上のエアコンが平常運転しています．(cooler_status: 4)")
        return 4
    elif mode_map[aircon.MODE.NORMAL] >= 1:
        logging.info("1 台以上のエアコンが平常運転しています．(cooler_status: 3)")
        return 3
    elif mode_map[aircon.MODE.IDLE] >= 2:
        logging.info("2 台以上のエアコンがアイドル運転しています．(cooler_status: 2)")
        return 2
    elif mode_map[aircon.MODE.IDLE] >= 1:
        logging.info("1 台以上のエアコンがアイドル運転しています．(cooler_status: 1)")
        return 1
    else:
        logging.info("エアコンは稼働していません．(cooler_status: 0)")
        return 0


# NOTE: 外部環境の状況を 5 段階で評価する．
# (-2 が冷却停止, 0 が中立, 2 が強める)
def get_outdoor_status(sense_data):
    if sense_data["temp"][0]["value"] > TEMP_THRESHOLD:
        logging.info(
            "外気温 ({temp:.1f} ℃) が高いので冷却を強化します．(outdoor_status: 2)".format(
                temp=sense_data["temp"][0]["value"]
            )
        )
        return 2
    elif sense_data["humi"][0]["value"] > HUMI_THRESHOLD:
        logging.info(
            "湿度 ({humi:.1f} %) が高いので冷却を停止します．(outdoor_status: -2)".format(
                humi=sense_data["humi"][0]["value"]
            )
        )
        return -2
    elif sense_data["solar_rad"][0]["value"] > SOLAR_RAD_THRESHOLD_HIGH:
        logging.info(
            "日射量 ({solar_rad:.0f} W/m^2) が大きいので冷却を少し強化します．(outdoor_status: 1)".format(
                solar_rad=sense_data["solar_rad"][0]["value"]
            )
        )
        return 1
    elif sense_data["solar_rad"][0]["value"] < SOLAR_RAD_THRESHOLD_LOW:
        logging.info(
            "日射量 ({solar_rad:.0f} W/m^2) が小さいので冷却を少し弱めます．(outdoor_status: -1)".format(
                solar_rad=sense_data["solar_rad"][0]["value"]
            )
        )
        return -1
    elif sense_data["lux"][0]["value"] < LUX_THRESHOLD:
        logging.info(
            "照度 ({lux:,.0f} LUX) が小さいので冷却を少し弱めます．(outdoor_status: -1)".format(
                lux=sense_data["lux"][0]["value"]
            )
        )
        return -1
    else:
        return 0


def judge_control_mode(config):
    logging.info("Judge control mode")

    sense_data = get_sense_data(config)

    cooler_status = get_cooler_status(sense_data)
    outdoor_status = get_outdoor_status(sense_data)

    control_mode = max(cooler_status + outdoor_status, 0)

    logging.info(
        (
            "control_mode: {control_mode} "
            + "(cooler_status: {cooler_status}, "
            + "outdoor_status: {outdoor_status})"
        ).format(
            control_mode=control_mode,
            cooler_status=cooler_status,
            outdoor_status=outdoor_status,
        )
    )

    return control_mode


def dummy_control_mode():
    import random

    # NOTE: ある程度連続性を持ったランダムな制御量を生成する
    dice = int(random.random() * 10)
    if dice < 2:
        control_mode = max(min(int(random.random() * 15) - 4, 8), 0)
    elif dice < 8:
        control_mode = max(min(int(dummy_control_mode.prev_mode + (random.random()-0.5)*4), 8), 0)
    else:
        control_mode = dummy_control_mode.prev_mode

    logging.info("control_mode: {control_mode}".format(control_mode=control_mode))

    dummy_control_mode.prev_mode = control_mode

    return control_mode

dummy_control_mode.prev_mode = 0


def gen_control_msg(config, dummy_mode=False):
    if dummy_mode:
        control_mode = dummy_control_mode()
    else:
        control_mode = judge_control_mode(config)

    match control_mode:
        case 0:
            control_msg = {
                "state": COOLING_STATE.IDLE,
                "duty": {"enable": False, "on_sec": 0*60, "off_sec": 0*60},
            }
        case 1:
            control_msg = {
                "state": COOLING_STATE.WORKING,
                "duty": {"enable": True, "on_sec": 1*60, "off_sec": 30*60},
            }
        case 2:
            control_msg = {
                "state": COOLING_STATE.WORKING,
                "duty": {"enable": True, "on_sec": 2*60, "off_sec": 30*60},
            }
        case 3:
            control_msg = {
                "state": COOLING_STATE.WORKING,
                "duty": {"enable": True, "on_sec": 1*60, "off_sec": 20*60},
            }
        case 4:
            control_msg = {
                "state": COOLING_STATE.WORKING,
                "duty": {"enable": True, "on_sec": 2*60, "off_sec": 20*60},
            }
        case 5:
            control_msg = {
                "state": COOLING_STATE.WORKING,
                "duty": {"enable": True, "on_sec": 1*60, "off_sec": 10*60},
            }
        case 6:
            control_msg = {
                "state": COOLING_STATE.WORKING,
                "duty": {"enable": True, "on_sec": 2*60, "off_sec": 10*60},
            }
        case 7:
            control_msg = {
                "state": COOLING_STATE.WORKING,
                "duty": {"enable": True, "on_sec": 1*60, "off_sec": 5*60},
            }
        case 8:
            control_msg = {
                "state": COOLING_STATE.WORKING,
                "duty": {"enable": True, "on_sec": 2*60, "off_sec": 5*60},
            }
    
    pathlib.Path(config["liveness"]["file"]).touch(exist_ok=True)

    if dummy_mode:
        control_msg = {
            "state": control_msg["state"],
            "duty": {
                "enable": control_msg["duty"]["enable"],
                "on_sec": control_msg["duty"]["on_sec"] / DUMMY_MODE_SPEEDUP,
                "off_sec": control_msg["duty"]["off_sec"] / DUMMY_MODE_SPEEDUP,
            }
        }
    
    return control_msg


def test_client(server_host, server_port):
    logging.info(
        "Start test client (host: {host}:{port})".format(
            host=server_host, port=server_port
        )
    )
    control_pubsub.start_client(
        server_host,
        server_port,
        lambda message: (
            logging.info("receive: {message}".format(message=message)),
            os._exit(0),
        ),
    )


######################################################################
args = docopt(__doc__)

config_file = args["-f"]
server_port = os.environ.get("HEMS_SERVER_PORT", args["-p"])
dummy_mode = args["-D"]
debug_mode = args["-d"]
client_mode = args["-C"]
server_host = args["-s"]
is_one_time = args["-O"]

if debug_mode:
    log_level = logging.DEBUG
else:
    log_level = logging.INFO

logger.init("hems.unit_cooler", level=log_level)

if client_mode:
    test_client(server_host, server_port)
    sys.exit(0)

logging.info("Start controller (port: {port})".format(port=server_port))

logging.info("Using config config: {config_file}".format(config_file=config_file))
config = load_config(config_file)

if dummy_mode:
    logging.warn("DUMMY mode")
    interval_sec = config["controller"]["interval_sec"] / DUMMY_MODE_SPEEDUP
else:
    interval_sec = config["controller"]["interval_sec"] 

try:
    control_pubsub.start_server(
        server_port,
        lambda: gen_control_msg(config, dummy_mode),
        interval_sec,
        is_one_time,
    )

except:
    notify_error(config)
    raise
