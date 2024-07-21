#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

import aircon
from valve_state import COOLING_STATE

############################################################
# 制御モードを決めるにあたって，参照する外部環境の閾値
#
# 屋外の照度がこの値未満の場合，冷却の強度を弱める
LUX_THRESHOLD = 300
# 太陽の日射量がこの値未満の場合，冷却の強度を弱める
SOLAR_RAD_THRESHOLD_LOW = 200
# 太陽の日射量がこの値未満の場合，冷却の強度を強める
SOLAR_RAD_THRESHOLD_HIGH = 700
# 太陽の日射量がこの値より大きい場合，昼間とする
SOLAR_RAD_THRESHOLD_DAYTIME = 50
# 屋外の湿度がこの値を超えていたら，冷却を停止する
HUMI_THRESHOLD = 96
# 屋外の温度がこの値を超えていたら，冷却の強度を大きく強める
TEMP_THRESHOLD_HIGH_H = 35
# 屋外の温度がこの値を超えていたら，冷却の強度を強める
TEMP_THRESHOLD_HIGH_L = 32
# 屋外の温度がこの値を超えていたら，冷却の強度を少し強める
TEMP_THRESHOLD_MID = 29

# 最低でもこの時間は ON にする (テスト時含む)
ON_SEC_MIN = 5
# 最低でもこの時間は OFF にする (テスト時含む)
OFF_SEC_MIN = 5


MESSAGE_LIST = [
    # 0
    {
        "state": COOLING_STATE.IDLE,
        "duty": {"enable": False, "on_sec": 0 * 60, "off_sec": 0 * 60},
    },
    # 1
    {
        "state": COOLING_STATE.WORKING,
        "duty": {"enable": True, "on_sec": 0.2 * 60, "off_sec": 30 * 60},
    },
    # 2
    {
        "state": COOLING_STATE.WORKING,
        "duty": {"enable": True, "on_sec": 0.2 * 60, "off_sec": 20 * 60},
    },
    # 3
    {
        "state": COOLING_STATE.WORKING,
        "duty": {"enable": True, "on_sec": 0.3 * 60, "off_sec": 20 * 60},
    },
    # 4
    {
        "state": COOLING_STATE.WORKING,
        "duty": {"enable": True, "on_sec": 0.3 * 60, "off_sec": 15 * 60},
    },
    # 5
    {
        "state": COOLING_STATE.WORKING,
        "duty": {"enable": True, "on_sec": 0.4 * 60, "off_sec": 8 * 60},
    },
    # 6
    {
        "state": COOLING_STATE.WORKING,
        "duty": {"enable": True, "on_sec": 0.4 * 60, "off_sec": 6 * 60},
    },
    # 7
    {
        "state": COOLING_STATE.WORKING,
        "duty": {"enable": True, "on_sec": 0.4 * 60, "off_sec": 5 * 60},
    },
    # 8
    {
        "state": COOLING_STATE.WORKING,
        "duty": {"enable": True, "on_sec": 0.4 * 60, "off_sec": 3 * 60},
    },
]


CORRECTION_CONDITION = [
    {
        "judge": lambda sense_data: sense_data["humi"][0]["value"] > HUMI_THRESHOLD,
        "message": lambda sense_data: (
            "湿度 ({humi:.1f} %) が " + "{threshold:.1f} % より高いので冷却を停止します．(outdoor_status: -2)"
        ).format(humi=sense_data["humi"][0]["value"], threshold=HUMI_THRESHOLD),
        "correction": -4,
    },
    {
        "judge": lambda sense_data: (sense_data["temp"][0]["value"] > TEMP_THRESHOLD_HIGH_H)
        and (sense_data["solar_rad"][0]["value"] > SOLAR_RAD_THRESHOLD_DAYTIME),
        "message": lambda sense_data: (
            "日射量 ({solar_rad:,.0f} W/m^2) が "
            + "{solar_rad_threshold:,.0f} W/m^2 より大きく，"
            + "外気温 ({temp:.1f} ℃) が "
            + "{threshold:.1f} ℃ より高いので冷却を大きく強化します．(outdoor_status: 2)"
        ).format(
            solar_rad=sense_data["solar_rad"][0]["value"],
            solar_rad_threshold=SOLAR_RAD_THRESHOLD_DAYTIME,
            temp=sense_data["temp"][0]["value"],
            threshold=TEMP_THRESHOLD_HIGH_H,
        ),
        "correction": 3,
    },
    {
        "judge": lambda sense_data: (sense_data["temp"][0]["value"] > TEMP_THRESHOLD_HIGH_L)
        and (sense_data["solar_rad"][0]["value"] > SOLAR_RAD_THRESHOLD_DAYTIME),
        "message": lambda sense_data: (
            "日射量 ({solar_rad:,.0f} W/m^2) が "
            + "{solar_rad_threshold:,.0f} W/m^2 より大きく，"
            + "外気温 ({temp:.1f} ℃) が "
            + "{threshold:.1f} ℃ より高いので冷却を強化します．(outdoor_status: 2)"
        ).format(
            solar_rad=sense_data["solar_rad"][0]["value"],
            solar_rad_threshold=SOLAR_RAD_THRESHOLD_DAYTIME,
            temp=sense_data["temp"][0]["value"],
            threshold=TEMP_THRESHOLD_HIGH_L,
        ),
        "correction": 2,
    },
    {
        "judge": lambda sense_data: sense_data["solar_rad"][0]["value"] > SOLAR_RAD_THRESHOLD_HIGH,
        "message": lambda sense_data: (
            "日射量 ({solar_rad:,.0f} W/m^2) が " + "{threshold:,.0f} W/m^2 より大きいので冷却を少し強化します．(outdoor_status: 1)"
        ).format(
            solar_rad=sense_data["solar_rad"][0]["value"],
            threshold=SOLAR_RAD_THRESHOLD_HIGH,
        ),
        "correction": 1,
    },
    {
        "judge": lambda sense_data: (sense_data["temp"][0]["value"] > TEMP_THRESHOLD_MID)
        and (sense_data["lux"][0]["value"] < LUX_THRESHOLD),
        "message": lambda sense_data: (
            " 外気温 ({temp:.1f} ℃) が {temp_threshold:.1f} ℃ より高いものの，"
            + "照度 ({lux:,.0f} LUX) が {lux_threshold:,.0f} LUX より小さいので，"
            + "冷却を少し弱めます．(outdoor_status: -1)"
        ).format(
            temp=sense_data["temp"][0]["value"],
            temp_threshold=TEMP_THRESHOLD_MID,
            lux=sense_data["lux"][0]["value"],
            lux_threshold=LUX_THRESHOLD,
        ),
        "correction": -1,
    },
    {
        "judge": lambda sense_data: sense_data["lux"][0]["value"] < LUX_THRESHOLD,
        "message": lambda sense_data: (
            "照度 ({lux:,.0f} LUX) が " + "{threshold:,.0f} LUX より小さいので冷却を弱めます．(outdoor_status: -2)"
        ).format(lux=sense_data["lux"][0]["value"], threshold=LUX_THRESHOLD),
        "correction": -2,
    },
    {
        "judge": lambda sense_data: sense_data["solar_rad"][0]["value"] < SOLAR_RAD_THRESHOLD_LOW,
        "message": lambda sense_data: (
            "日射量 ({solar_rad:,.0f} W/m^2) が " + "{threshold:,.0f} W/m^2 より小さいので冷却を少し弱めます．(outdoor_status: -1)"
        ).format(
            solar_rad=sense_data["solar_rad"][0]["value"],
            threshold=SOLAR_RAD_THRESHOLD_LOW,
        ),
        "correction": -1,
    },
]

COOLER_CONDITION = [
    {
        "judge": lambda mode_map: mode_map[aircon.MODE.FULL] >= 2,
        "message": "2 台以上のエアコンがフル稼働しています．(cooler_status: 6)",
        "status": 6,
    },
    {
        "judge": lambda mode_map: (mode_map[aircon.MODE.FULL] >= 1) and (mode_map[aircon.MODE.NORMAL] >= 1),
        "message": "複数台ののエアコンがフル稼働もしくは平常運転しています．(cooler_status: 5)",
        "status": 5,
    },
    {
        "judge": lambda mode_map: mode_map[aircon.MODE.FULL] >= 1,
        "message": "1 台以上のエアコンがフル稼働しています．(cooler_status: 4)",
        "status": 4,
    },
    {
        "judge": lambda mode_map: mode_map[aircon.MODE.NORMAL] >= 2,
        "message": "2 台以上のエアコンが平常運転しています．(cooler_status: 4)",
        "status": 4,
    },
    {
        "judge": lambda mode_map: mode_map[aircon.MODE.NORMAL] >= 1,
        "message": "1 台以上のエアコンが平常運転しています．(cooler_status: 3)",
        "status": 3,
    },
    {
        "judge": lambda mode_map: mode_map[aircon.MODE.IDLE] >= 2,
        "message": "2 台以上のエアコンがアイドル運転しています．(cooler_status: 2)",
        "status": 2,
    },
    {
        "judge": lambda mode_map: mode_map[aircon.MODE.IDLE] >= 1,
        "message": "1 台以上のエアコンがアイドル運転しています．(cooler_status: 1)",
        "status": 1,
    },
    {
        "judge": lambda mode_map: True,
        "message": "エアコンは稼働していません．(cooler_status: 0)",
        "status": 0,
    },
]


# NOTE: クーラーの稼働状況を評価する．
# (数字が大きいほど稼働状況が活発)
def get_cooler_status(config, sense_data):
    mode_map = {}

    for mode in aircon.MODE:
        mode_map[mode] = 0

    temp = sense_data["temp"][0]["value"]
    for aircon_power in sense_data["power"]:
        mode = aircon.get_cooler_state(aircon_power, temp)
        mode_map[mode] += 1

    logging.info(mode_map)

    for condition in COOLER_CONDITION:
        if condition["judge"](mode_map):
            return {
                "status": condition["status"],
                "message": condition["message"],
            }
    raise AssertionError("This should never be reached.")  # pragma: no cover


# NOTE: 外部環境の状況を評価する．
# (数字が大きいほど冷却を強める)
def get_outdoor_status(sense_data):
    logging.info(
        "気温: {temp:.1f} ℃, 湿度: {humi:.1f} %, 日射量: {solar_rad:,.0f} W/m^2, 照度: {lux:,.0f} LUX".format(
            temp=sense_data["temp"][0]["value"],
            humi=sense_data["humi"][0]["value"],
            solar_rad=sense_data["solar_rad"][0]["value"],
            lux=sense_data["lux"][0]["value"],
        )
    )
    for condition in CORRECTION_CONDITION:
        if condition["judge"](sense_data):
            return {
                "status": condition["correction"],
                "message": condition["message"](sense_data),
            }

    return {"status": 0, "message": None}
