#!/usr/bin/env python3
"""
屋外の気象情報とエアコンの稼働状況に基づき、冷却モードを決定します。

Usage:
  engine.py [-c CONFIG] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -D                : デバッグモードで動作します。
"""

import copy
import logging

import my_lib.notify.slack
import unit_cooler.control.message
import unit_cooler.control.sensor
import unit_cooler.util

# 最低でもこの時間は ON にする (テスト時含む)
ON_SEC_MIN = 5
# 最低でもこの時間は OFF にする (テスト時含む)
OFF_SEC_MIN = 5


def dummy_cooling_mode():
    cooling_mode = (dummy_cooling_mode.prev_mode + 1) % len(unit_cooler.control.message.CONTROL_MESSAGE_LIST)
    dummy_cooling_mode.prev_mode = cooling_mode

    logging.info("cooling_mode: %d", cooling_mode)

    return {"cooling_mode": cooling_mode}


dummy_cooling_mode.prev_mode = 0


def judge_cooling_mode(config):
    logging.info("Judge cooling mode")

    sense_data = unit_cooler.control.sensor.get_sense_data(config)

    try:
        cooler_activity = unit_cooler.control.sensor.get_cooler_activity(sense_data)
    except RuntimeError as e:
        unit_cooler.util.notify_error(config, e.args[0])
        cooler_activity = {"status": 0, "message": None}

    if cooler_activity["status"] == 0:
        outdoor_status = {"status": None, "message": None}
        cooling_mode = 0
    else:
        outdoor_status = unit_cooler.control.sensor.get_outdoor_status(sense_data)
        cooling_mode = max(cooler_activity["status"] + outdoor_status["status"], 0)

    if cooler_activity["message"] is not None:
        logging.info(cooler_activity["message"])
    if outdoor_status["message"] is not None:
        logging.info(outdoor_status["message"])

    logging.info(
        "cooling_mode: %d (cooler_status: %s, outdoor_status: %s)",
        cooling_mode,
        cooler_activity["status"],
        outdoor_status["status"],
    )

    return {
        "cooling_mode": cooling_mode,
        "cooler_status": cooler_activity,
        "outdoor_status": outdoor_status,
        "sense_data": sense_data,
    }


def gen_control_msg(config, dummy_mode=False, speedup=1):
    mode = dummy_cooling_mode() if dummy_mode else judge_cooling_mode(config)
    mode_index = min(mode["cooling_mode"], len(unit_cooler.control.message.CONTROL_MESSAGE_LIST) - 1)
    control_msg = copy.deepcopy(unit_cooler.control.message.CONTROL_MESSAGE_LIST[mode_index])

    # NOTE: 参考として、どのモードかも通知する
    control_msg["mode_index"] = mode_index

    if dummy_mode:
        control_msg["duty"]["on_sec"] = max(control_msg["duty"]["on_sec"] / speedup, ON_SEC_MIN)
        control_msg["duty"]["off_sec"] = max(control_msg["duty"]["off_sec"] / speedup, OFF_SEC_MIN)

    return control_msg


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

    logging.info(my_lib.pretty.format(gen_control_msg(config)))
