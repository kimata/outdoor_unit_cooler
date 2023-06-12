#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
エアコン室外機の冷却モードの指示を出します．

Usage:
  cooler_controller.py [-c CONFIG] [-p SERVER_PORT] [-O] [-D] [-t SPEEDUP] [-d]
  cooler_controller.py -C [-c CONFIG] [-s SERVER_HOST] [-p SERVER_PORT] [-d]
  cooler_controller.py -V

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -p SERVER_PORT    : ZeroMQ の Pub サーバーを動作させるポートを指定します． [default: 2222]
  -O                : 1回のみ実行
  -D                : 冷却モードをランダムに生成するモードで動作すします．
  -t SPEEDUP        : 時短モード．演算間隔を SPEEDUP 分の一にします． [default: 1]
  -d                : デバッグモードで動作します．
  -V                : 制御メッセージの一覧を表示します．
  -C                : クライアントモード(ダミー)で動作します．CI でのテスト用．
  -s SERVER_HOST    : サーバーのホスト名を指定します． [default: localhost]
"""

from docopt import docopt

import os
import sys
import logging
import pathlib
import traceback

sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

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
LUX_THRESHOLD = 300
# 太陽の日射量がこの値未満の場合，冷却の強度を弱める
SOLAR_RAD_THRESHOLD_LOW = 200
# 太陽の日射量がこの値未満の場合，冷却の強度を強める
SOLAR_RAD_THRESHOLD_HIGH = 700
# 屋外の湿度がこの値を超えていたら，冷却を停止する
HUMI_THRESHOLD = 96
# 屋外の温度がこの値を超えていたら，冷却の強度を強める
TEMP_THRESHOLD = 33

CONTROL_MSG_LIST = [
    {
        "state": COOLING_STATE.IDLE,
        "duty": {"enable": False, "on_sec": 0 * 60, "off_sec": 0 * 60},
    },
    {
        "state": COOLING_STATE.WORKING,
        "duty": {"enable": True, "on_sec": 0.2 * 60, "off_sec": 30 * 60},
    },
    {
        "state": COOLING_STATE.WORKING,
        "duty": {"enable": True, "on_sec": 0.2 * 60, "off_sec": 20 * 60},
    },
    {
        "state": COOLING_STATE.WORKING,
        "duty": {"enable": True, "on_sec": 0.4 * 60, "off_sec": 30 * 60},
    },
    {
        "state": COOLING_STATE.WORKING,
        "duty": {"enable": True, "on_sec": 0.4 * 60, "off_sec": 20 * 60},
    },
    {
        "state": COOLING_STATE.WORKING,
        "duty": {"enable": True, "on_sec": 0.3 * 60, "off_sec": 10 * 60},
    },
    {
        "state": COOLING_STATE.WORKING,
        "duty": {"enable": True, "on_sec": 0.4 * 60, "off_sec": 10 * 60},
    },
    {
        "state": COOLING_STATE.WORKING,
        "duty": {"enable": True, "on_sec": 0.4 * 60, "off_sec": 6 * 60},
    },
    {
        "state": COOLING_STATE.WORKING,
        "duty": {"enable": True, "on_sec": 0.5 * 60, "off_sec": 6 * 60},
    },
]


def notify_error(config, message):
    logging.error(message)

    if "slack" not in config:
        return

    notify_slack.error(
        config["slack"]["bot_token"],
        config["slack"]["error"]["channel"]["name"],
        config["slack"]["from"],
        message,
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
                notify_error(
                    config, "{name} のデータを取得できませんでした．".format(name=sensor["name"])
                )
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
        logging.info("2 台以上のエアコンがフル稼働しています．(cooler_status: 6)")
        return 6
    elif (mode_map[aircon.MODE.FULL] >= 1) and (mode_map[aircon.MODE.NORMAL] >= 1):
        logging.info("複数台ののエアコンがフル稼働もしくは平常運転しています．(cooler_status: 5)")
        return 5
    elif mode_map[aircon.MODE.FULL] >= 1:
        logging.info("1 台以上のエアコンがフル稼働しています．(cooler_status: 4)")
        return 4
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
    logging.info(
        "気温: {temp:.1f} ℃, 湿度: {humi:.1f} %, 日射量: {solar_rad:,.0f} W/m^2, 照度: {lux:,.0f} LUX".format(
            temp=sense_data["temp"][0]["value"],
            humi=sense_data["humi"][0]["value"],
            solar_rad=sense_data["solar_rad"][0]["value"],
            lux=sense_data["lux"][0]["value"],
        )
    )
    if sense_data["temp"][0]["value"] > TEMP_THRESHOLD:
        logging.info(
            "外気温 ({temp:.1f} ℃) が {threshold:.1f} ℃ より高いので冷却を強化します．(outdoor_status: 2)".format(
                temp=sense_data["temp"][0]["value"], threshold=TEMP_THRESHOLD
            )
        )
        return 2
    elif sense_data["humi"][0]["value"] > HUMI_THRESHOLD:
        logging.info(
            "湿度 ({humi:.1f} %) が {threshold:.1f} % より高いので冷却を停止します．(outdoor_status: -2)".format(
                humi=sense_data["humi"][0]["value"], threshold=HUMI_THRESHOLD
            )
        )
        return -4
    elif sense_data["solar_rad"][0]["value"] > SOLAR_RAD_THRESHOLD_HIGH:
        logging.info(
            "日射量 ({solar_rad:,.0f} W/m^2) が {threshold:,.0f} W/m^2 より大きいので冷却を少し強化します．(outdoor_status: 1)".format(
                solar_rad=sense_data["solar_rad"][0]["value"],
                threshold=SOLAR_RAD_THRESHOLD_HIGH,
            )
        )
        return 1
    elif sense_data["solar_rad"][0]["value"] < SOLAR_RAD_THRESHOLD_LOW:
        logging.info(
            "日射量 ({solar_rad:,.0f} W/m^2) が {threshold:,.0f} W/m^2 より小さいので冷却を少し弱めます．(outdoor_status: -1)".format(
                solar_rad=sense_data["solar_rad"][0]["value"],
                threshold=SOLAR_RAD_THRESHOLD_LOW,
            )
        )
        return -1
    elif sense_data["lux"][0]["value"] < LUX_THRESHOLD:
        logging.info(
            "照度 ({lux:,.0f} LUX) が {threshold:,.0f} LUX より小さいので冷却を少し弱めます．(outdoor_status: -1)".format(
                lux=sense_data["lux"][0]["value"], threshold=LUX_THRESHOLD
            )
        )
        return -2
    else:
        return 0


def judge_control_mode(config):
    logging.info("Judge control mode")

    sense_data = get_sense_data(config)

    cooler_status = get_cooler_status(sense_data)

    if cooler_status == 0:
        outdoor_status = None
        control_mode = cooler_status
    else:
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
        control_mode = max(
            min(int(dummy_control_mode.prev_mode + (random.random() - 0.5) * 4), 8), 0
        )
    else:
        control_mode = dummy_control_mode.prev_mode

    logging.info("control_mode: {control_mode}".format(control_mode=control_mode))

    dummy_control_mode.prev_mode = control_mode

    return control_mode


dummy_control_mode.prev_mode = 0


def gen_control_msg(config, dummy_mode=False, speedup=1):
    if dummy_mode:
        control_mode = dummy_control_mode()
    else:
        control_mode = judge_control_mode(config)

    mode_index = min(control_mode, len(CONTROL_MSG_LIST) - 1)
    control_msg = CONTROL_MSG_LIST[mode_index]

    # NOTE: 参考として，どのモードかも通知する
    control_msg["mode_index"] = mode_index

    pathlib.Path(config["controller"]["liveness"]["file"]).touch(exist_ok=True)

    if dummy_mode:
        control_msg["duty"]["on_sec"] = int(control_msg["duty"]["on_sec"] / speedup)
        control_msg["duty"]["off_sec"] = int(control_msg["duty"]["off_sec"] / speedup)

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


def print_control_msg():
    for control_msg in CONTROL_MSG_LIST:
        if control_msg["duty"]["enable"]:
            logging.info(
                (
                    "state: {state}, on_se_sec: {on_sec:4,} sec, "
                    + "off_sec: {off_sec:5,} sec, on_ratio: {on_ratio:4.1f}%"
                ).format(
                    state=control_msg["state"].name,
                    on_sec=control_msg["duty"]["on_sec"],
                    off_sec=int(control_msg["duty"]["off_sec"]),
                    on_ratio=100.0
                    * control_msg["duty"]["on_sec"]
                    / (control_msg["duty"]["on_sec"] + control_msg["duty"]["off_sec"]),
                )
            )
        else:
            logging.info("state: {state}".format(state=control_msg["state"].name))

    sys.exit(0)


######################################################################
args = docopt(__doc__)

config_file = args["-c"]
server_port = os.environ.get("HEMS_SERVER_PORT", args["-p"])
dummy_mode = args["-D"]
speedup = int(args["-t"])
debug_mode = args["-d"]
client_mode = args["-C"]
server_host = args["-s"]
is_one_time = args["-O"]
view_msg_mode = args["-V"]

if debug_mode:
    log_level = logging.DEBUG
else:
    log_level = logging.INFO

logger.init("hems.unit_cooler", level=log_level)
logging.info("Start controller (port: {port})".format(port=server_port))

logging.info("Using config config: {config_file}".format(config_file=config_file))
config = load_config(config_file)

if client_mode:
    test_client(server_host, server_port)
    sys.exit(0)
elif view_msg_mode:
    print_control_msg()

if dummy_mode:
    logging.warning("DUMMY mode")

try:
    control_pubsub.start_server(
        server_port,
        lambda: gen_control_msg(config, dummy_mode, speedup),
        config["controller"]["interval_sec"] / speedup,
        is_one_time,
    )

except:
    notify_error(config, traceback.format_exc())
    raise
