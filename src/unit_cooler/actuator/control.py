#!/usr/bin/env python3
import logging
import os

import my_lib.time
import unit_cooler.actuator.valve
import unit_cooler.const
import unit_cooler.util

HAZARD_NOTIFY_INTERVAL_MIN = 30


def gen_handle(config, message_queue):
    return {
        "config": config,
        "message_queue": message_queue,
        "receive_time": my_lib.time.now(),
        "receive_count": 0,
    }


def hazard_register(config):
    my_lib.footprint.update(config["actuator"]["control"]["hazard"]["file"])


def hazard_clear(config):
    my_lib.footprint.clear(config["actuator"]["control"]["hazard"]["file"])


def hazard_notify(config, message):
    if (
        my_lib.footprint.elapsed(config["actuator"]["control"]["hazard"]["file"]) / 60
        > HAZARD_NOTIFY_INTERVAL_MIN
    ):
        unit_cooler.actuator.work_log.add(message, unit_cooler.const.LOG_LEVEL.ERROR)

        hazard_register(config)

    unit_cooler.actuator.valve.set_state(unit_cooler.const.VALVE_STATE.CLOSE)


def hazard_check(config):
    if my_lib.footprint.exists(config["actuator"]["control"]["hazard"]["file"]):
        hazard_notify(config, "過去に水漏れもしくは電磁弁の故障が検出されているので制御を停止しています。")
        return True
    else:
        return False


def get_control_message_impl(handle, last_message):
    if handle["message_queue"].empty():
        if (my_lib.time.now() - handle["receive_time"]).total_seconds() > handle["config"]["controller"][
            "interval_sec"
        ] * 3:
            unit_cooler.actuator.work_log.add(
                "冷却モードの指示を受信できません。", unit_cooler.const.LOG_LEVEL.ERROR
            )

        return last_message

    control_message = None
    while not handle["message_queue"].empty():
        control_message = handle["message_queue"].get()

        logging.info("Receive: %s", control_message)

        handle["receive_time"] = my_lib.time.now()
        handle["receive_count"] += 1
        if os.environ.get("TEST", "false") == "true":
            # NOTE: テスト時は、コマンドの数を整合させたいので、
            # 1 回に1個のコマンドのみ処理する。
            break

    if control_message["mode_index"] != last_message["mode_index"]:
        unit_cooler.actuator.work_log.add(
            ("冷却モードが変更されました。({before} → {after})").format(
                before="init" if last_message["mode_index"] == -1 else last_message["mode_index"],
                after=control_message["mode_index"],
            )
        )

    return control_message


def get_control_message(handle, last_message):
    try:
        return get_control_message_impl(handle, last_message)
    except OverflowError:  # pragma: no cover
        # NOTE: テストする際、timemachinefreezer 使って日付をいじるとこの例外が発生する
        logging.exception("Failed to get control message")
        return last_message


def execute(config, control_message):
    if hazard_check(config):
        control_message = {"mode_index": 0, "state": unit_cooler.const.COOLING_STATE.IDLE}

    unit_cooler.actuator.valve.set_cooling_state(control_message)
