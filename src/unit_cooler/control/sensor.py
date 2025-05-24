#!/usr/bin/env python3
"""
InfluxDB から制御用のセンシングデータを取得します。

Usage:
  sensor.py [-c CONFIG] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -D                : デバッグモードで動作します。
"""

import logging
import os

import my_lib.notify.slack
import my_lib.sensor_data
import my_lib.time
import unit_cooler.const
import unit_cooler.control.message

############################################################
# 屋外の状況を判断する際に参照する閾値
#
# 屋外の照度がこの値未満の場合、冷却の強度を弱める
LUX_THRESHOLD = 300
# 太陽の日射量がこの値未満の場合、冷却の強度を弱める
SOLAR_RAD_THRESHOLD_LOW = 200
# 太陽の日射量がこの値未満の場合、冷却の強度を強める
SOLAR_RAD_THRESHOLD_HIGH = 700
# 太陽の日射量がこの値より大きい場合、昼間とする
SOLAR_RAD_THRESHOLD_DAYTIME = 50
# 屋外の湿度がこの値を超えていたら、冷却を停止する
HUMI_THRESHOLD = 96
# 屋外の温度がこの値を超えていたら、冷却の強度を大きく強める
TEMP_THRESHOLD_HIGH_H = 35
# 屋外の温度がこの値を超えていたら、冷却の強度を強める
TEMP_THRESHOLD_HIGH_L = 32
# 屋外の温度がこの値を超えていたら、冷却の強度を少し強める
TEMP_THRESHOLD_MID = 29

# クーラーの状況を判断する際に参照する閾値
#
# クーラー動作中と判定する電力閾値(min)
AIRCON_POWER_THRESHOLD_WORK = 20
# クーラー平常運転中と判定する電力閾値(min)
AIRCON_POWER_THRESHOLD_NORMAL = 500
# クーラーフル稼働中と判定する電力閾値(min)
AIRCON_POWER_THRESHOLD_FULL = 900
# エアコンの冷房動作と判定する温度閾値(min)
AIRCON_TEMP_THRESHOLD = 20

COOLER_ACTIVITY_LIST = [
    {
        "judge": lambda mode_map: mode_map[unit_cooler.const.AIRCON_MODE.FULL] >= 2,
        "message": "2 台以上のエアコンがフル稼働しています。(cooler_status: 6)",
        "status": 6,
    },
    {
        "judge": lambda mode_map: (mode_map[unit_cooler.const.AIRCON_MODE.FULL] >= 1)
        and (mode_map[unit_cooler.control.sensor.AIRCON_MODE.NORMAL] >= 1),
        "message": "複数台ののエアコンがフル稼働もしくは平常運転しています。(cooler_status: 5)",
        "status": 5,
    },
    {
        "judge": lambda mode_map: mode_map[unit_cooler.const.AIRCON_MODE.FULL] >= 1,
        "message": "1 台以上のエアコンがフル稼働しています。(cooler_status: 4)",
        "status": 4,
    },
    {
        "judge": lambda mode_map: mode_map[unit_cooler.const.AIRCON_MODE.NORMAL] >= 2,
        "message": "2 台以上のエアコンが平常運転しています。(cooler_status: 4)",
        "status": 4,
    },
    {
        "judge": lambda mode_map: mode_map[unit_cooler.const.AIRCON_MODE.NORMAL] >= 1,
        "message": "1 台以上のエアコンが平常運転しています。(cooler_status: 3)",
        "status": 3,
    },
    {
        "judge": lambda mode_map: mode_map[unit_cooler.const.AIRCON_MODE.IDLE] >= 2,
        "message": "2 台以上のエアコンがアイドル運転しています。(cooler_status: 2)",
        "status": 2,
    },
    {
        "judge": lambda mode_map: mode_map[unit_cooler.const.AIRCON_MODE.IDLE] >= 1,
        "message": "1 台以上のエアコンがアイドル運転しています。(cooler_status: 1)",
        "status": 1,
    },
    {
        "judge": lambda mode_map: True,  # noqa: ARG005
        "message": "エアコンは稼働していません。(cooler_status: 0)",
        "status": 0,
    },
]


OUTDOOR_CONDITION_LIST = [
    {
        "judge": lambda sense_data: sense_data["humi"][0]["value"] > HUMI_THRESHOLD,
        "message": lambda sense_data: (
            "湿度 ({humi:.1f} %) が " + "{threshold:.1f} % より高いので冷却を停止します。(outdoor_status: -2)"
        ).format(humi=sense_data["humi"][0]["value"], threshold=HUMI_THRESHOLD),
        "status": -4,
    },
    {
        "judge": lambda sense_data: (sense_data["temp"][0]["value"] > TEMP_THRESHOLD_HIGH_H)
        and (sense_data["solar_rad"][0]["value"] > SOLAR_RAD_THRESHOLD_DAYTIME),
        "message": lambda sense_data: (
            "日射量 ({solar_rad:,.0f} W/m^2) が "
            "{solar_rad_threshold:,.0f} W/m^2 より大きく、"
            "外気温 ({temp:.1f} ℃) が "
            "{threshold:.1f} ℃ より高いので冷却を大きく強化します。(outdoor_status: 2)"
        ).format(
            solar_rad=sense_data["solar_rad"][0]["value"],
            solar_rad_threshold=SOLAR_RAD_THRESHOLD_DAYTIME,
            temp=sense_data["temp"][0]["value"],
            threshold=TEMP_THRESHOLD_HIGH_H,
        ),
        "status": 3,
    },
    {
        "judge": lambda sense_data: (sense_data["temp"][0]["value"] > TEMP_THRESHOLD_HIGH_L)
        and (sense_data["solar_rad"][0]["value"] > SOLAR_RAD_THRESHOLD_DAYTIME),
        "message": lambda sense_data: (
            "日射量 ({solar_rad:,.0f} W/m^2) が "
            "{solar_rad_threshold:,.0f} W/m^2 より大きく、"
            "外気温 ({temp:.1f} ℃) が "
            "{threshold:.1f} ℃ より高いので冷却を強化します。(outdoor_status: 2)"
        ).format(
            solar_rad=sense_data["solar_rad"][0]["value"],
            solar_rad_threshold=SOLAR_RAD_THRESHOLD_DAYTIME,
            temp=sense_data["temp"][0]["value"],
            threshold=TEMP_THRESHOLD_HIGH_L,
        ),
        "status": 2,
    },
    {
        "judge": lambda sense_data: sense_data["solar_rad"][0]["value"] > SOLAR_RAD_THRESHOLD_HIGH,
        "message": lambda sense_data: (
            "日射量 ({solar_rad:,.0f} W/m^2) が "
            "{threshold:,.0f} W/m^2 より大きいので冷却を少し強化します。(outdoor_status: 1)"
        ).format(
            solar_rad=sense_data["solar_rad"][0]["value"],
            threshold=SOLAR_RAD_THRESHOLD_HIGH,
        ),
        "status": 1,
    },
    {
        "judge": lambda sense_data: (sense_data["temp"][0]["value"] > TEMP_THRESHOLD_MID)
        and (sense_data["lux"][0]["value"] < LUX_THRESHOLD),
        "message": lambda sense_data: (
            " 外気温 ({temp:.1f} ℃) が {temp_threshold:.1f} ℃ より高いものの、"
            "照度 ({lux:,.0f} LUX) が {lux_threshold:,.0f} LUX より小さいので、"
            "冷却を少し弱めます。(outdoor_status: -1)"
        ).format(
            temp=sense_data["temp"][0]["value"],
            temp_threshold=TEMP_THRESHOLD_MID,
            lux=sense_data["lux"][0]["value"],
            lux_threshold=LUX_THRESHOLD,
        ),
        "status": -1,
    },
    {
        "judge": lambda sense_data: sense_data["lux"][0]["value"] < LUX_THRESHOLD,
        "message": lambda sense_data: (
            "照度 ({lux:,.0f} LUX) が "
            "{threshold:,.0f} LUX より小さいので冷却を弱めます。(outdoor_status: -2)"
        ).format(lux=sense_data["lux"][0]["value"], threshold=LUX_THRESHOLD),
        "status": -2,
    },
    {
        "judge": lambda sense_data: sense_data["solar_rad"][0]["value"] < SOLAR_RAD_THRESHOLD_LOW,
        "message": lambda sense_data: (
            "日射量 ({solar_rad:,.0f} W/m^2) が "
            "{threshold:,.0f} W/m^2 より小さいので冷却を少し弱めます。(outdoor_status: -1)"
        ).format(
            solar_rad=sense_data["solar_rad"][0]["value"],
            threshold=SOLAR_RAD_THRESHOLD_LOW,
        ),
        "status": -1,
    },
]


# NOTE: 外部環境の状況を評価する。
# (数字が大きいほど冷却を強める)
def get_outdoor_status(sense_data):
    logging.info(
        "気温: %.1f ℃, 湿度: %.1f %%, 日射量: %s W/m^2, 照度: %s LUX",
        sense_data["temp"][0]["value"],
        sense_data["humi"][0]["value"],
        f"{sense_data['solar_rad'][0]['value']:,.0f}",
        f"{sense_data['lux'][0]['value']:,.0f}",
    )
    for condition in OUTDOOR_CONDITION_LIST:
        if condition["judge"](sense_data):
            return {
                "status": condition["status"],
                "message": condition["message"](sense_data),
            }

    return {"status": 0, "message": None}


# NOTE: クーラーの稼働状況を評価する。
# (数字が大きいほど稼働状況が活発)
def get_cooler_activity(sense_data):
    mode_map = {}

    for mode in unit_cooler.const.AIRCON_MODE:
        mode_map[mode] = 0

    temp = sense_data["temp"][0]["value"]
    for aircon_power in sense_data["power"]:
        mode = get_cooler_state(aircon_power, temp)
        mode_map[mode] += 1

    logging.info(mode_map)

    for condition in COOLER_ACTIVITY_LIST:
        if condition["judge"](mode_map):
            return {
                "status": condition["status"],
                "message": condition["message"],
            }
    raise AssertionError("This should never be reached.")  # pragma: no cover # noqa: TRY003, EM101


def get_cooler_state(aircon_power, temp):
    mode = unit_cooler.const.AIRCON_MODE.OFF
    if temp is None:
        # NOTE: 外気温がわからないと暖房と冷房の区別がつかないので、致命的エラー扱いにする
        raise RuntimeError("外気温が不明のため、エアコン動作モードを判断できません。")  # noqa: EM101

    if aircon_power["value"] is None:
        logging.warning(
            "%s の消費電力が不明のため、動作モードを判断できません。OFFとみなします。", aircon_power["name"]
        )
        return unit_cooler.const.AIRCON_MODE.OFF

    if temp >= AIRCON_TEMP_THRESHOLD:
        if aircon_power["value"] > AIRCON_POWER_THRESHOLD_FULL:
            mode = unit_cooler.const.AIRCON_MODE.FULL
        elif aircon_power["value"] > AIRCON_POWER_THRESHOLD_NORMAL:
            mode = unit_cooler.const.AIRCON_MODE.NORMAL
        elif aircon_power["value"] > AIRCON_POWER_THRESHOLD_WORK:
            mode = unit_cooler.const.AIRCON_MODE.IDLE

    logging.info(
        "%s: %s W, 外気温: %.1f ℃  (mode: %s)",
        aircon_power["name"],
        f"{aircon_power['value']:,.0f}",
        temp,
        mode,
    )

    return mode


def get_sense_data(config):
    zoneinfo = my_lib.time.get_zoneinfo()

    if os.environ.get("DUMMY_MODE", "false") == "true":
        start = "-169h"
        stop = "-168h"
    else:
        start = "-1h"
        stop = "now()"

    sense_data = {}
    for kind in config["controller"]["sensor"]:
        kind_data = []
        for sensor in config["controller"]["sensor"][kind]:
            data = my_lib.sensor_data.fetch_data(
                config["controller"]["influxdb"],
                sensor["measure"],
                sensor["hostname"],
                kind,
                start,
                stop,
                last=True,
            )
            if data["valid"]:
                kind_data.append(
                    {
                        "name": sensor["name"],
                        "time": data["time"][0].replace(tzinfo=zoneinfo),
                        "value": data["value"][0],
                    }
                )
            else:
                my_lib.notify.slack.error(
                    config["slack"]["bot_token"],
                    config["slack"]["error"]["channel"]["name"],
                    config["slack"]["from"],
                    f'{sensor["name"]} のデータを取得できませんでした。',
                )

                kind_data.append({"name": sensor["name"], "value": None})

        sense_data[kind] = kind_data

    return sense_data


if __name__ == "__main__":
    # TEST Code
    import docopt
    import my_lib.config
    import my_lib.logger
    import my_lib.pretty

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    sense_data = get_sense_data(config)

    logging.info(my_lib.pretty.format(sense_data))
    logging.info(my_lib.pretty.format(get_outdoor_status(sense_data)))
    logging.info(my_lib.pretty.format(get_cooler_activity(sense_data)))
