#!/usr/bin/env python3
import logging
import math
import os
import socket

import fluent.sender
import my_lib.footprint
import my_lib.pretty
import unit_cooler.actuator.sensor
import unit_cooler.actuator.valve
import unit_cooler.actuator.work_log
import unit_cooler.const


def init(pin_no):
    unit_cooler.actuator.sensor.init(pin_no)


def gen_handle(config, interval_sec):
    return {
        "config": config,
        "hostname": os.environ.get("NODE_HOSTNAME", socket.gethostname()),
        "sender": fluent.sender.FluentSender("sensor", host=config["actuator"]["monitor"]["fluent"]["host"]),
        "log_period": max(math.ceil(60 / interval_sec), 1),  # この回数毎にログを出力する
        "flow_unknown": 0,  # 流量不明が続いた回数
        "monitor_count": 0,  # 観測した回数
    }


def send_mist_condition(handle, mist_condition, control_message, dummy_mode=False):
    send_data = {"hostname": handle["hostname"], "state": mist_condition["valve"]["state"].value}

    if mist_condition["flow"] is not None:
        send_data["flow"] = mist_condition["flow"]

    if control_message is not None:
        send_data["cooling_mode"] = control_message["mode_index"]

    logging.debug("Send: %s", my_lib.pretty.format(send_data))

    if dummy_mode:
        return

    if handle["sender"].emit("rasp", send_data):
        logging.debug("Send OK")
    else:
        logging.error(handle["sender"].last_error)


def get_mist_condition():
    valve_status = unit_cooler.actuator.valve.get_status()

    if valve_status["state"] == unit_cooler.const.VALVE_STATE.OPEN:
        flow = unit_cooler.actuator.sensor.get_flow()
        get_mist_condition.last_flow = flow

        # NOTE: get_flow() の内部で流量センサーの電源を入れている場合は計測に時間がかかるので、
        # その間に電磁弁の状態が変化している可能性があるので、再度状態を取得する。
        valve_status = unit_cooler.actuator.valve.get_status()
    else:  # noqa: PLR5501
        # NOTE: 電磁弁が閉じている場合、流量が 0 になるまでは計測を継続する。
        # (電磁弁の電源を切るため、流量が 0 になった場合は、電磁弁が開かれるまで計測は再開しない)
        if get_mist_condition.last_flow != 0:
            flow = unit_cooler.actuator.sensor.get_flow()
            get_mist_condition.last_flow = flow
        else:
            flow = 0

    return {"valve": valve_status, "flow": flow}


get_mist_condition.last_flow = 0


def hazard_notify(config, message):
    hazard_file = config["actuator"]["control"]["hazard"]["file"]
    logging.error(my_lib.footprint.exists(hazard_file))
    if not my_lib.footprint.exists(hazard_file):
        unit_cooler.actuator.work_log.add(message, unit_cooler.const.LOG_LEVEL.ERROR)
        my_lib.footprint.update(hazard_file)

    unit_cooler.actuator.valve.set_state(unit_cooler.const.VALVE_STATE.CLOSE)


def check_sensing(handle, mist_condition):
    if mist_condition["flow"] is None:
        handle["flow_unknown"] += 1
    else:
        handle["flow_unknown"] = 0

    if handle["flow_unknown"] > handle["config"]["actuator"]["monitor"]["sense"]["giveup"]:
        unit_cooler.actuator.work_log.add("流量計が使えません。", unit_cooler.const.LOG_LEVEL.ERROR)
    elif handle["flow_unknown"] > (handle["config"]["actuator"]["monitor"]["sense"]["giveup"] / 2):
        unit_cooler.actuator.work_log.add(
            "流量計が応答しないので一旦、リセットします。", unit_cooler.const.LOG_LEVEL.WARN
        )
        unit_cooler.actuator.sensor.stop()


def check_mist_condition(handle, mist_condition):
    logging.debug("Check mist condition")

    if mist_condition["valve"]["state"] == unit_cooler.const.VALVE_STATE.OPEN:
        logging.debug(
            "Valve is open for %.1f sec (flow: %.1f L/min)",
            mist_condition["valve"]["duration"],
            mist_condition["flow"],
        )
        for i in range(len(handle["config"]["actuator"]["monitor"]["flow"]["on"]["max"])):
            logging.error(
                [
                    mist_condition["flow"],
                    handle["config"]["actuator"]["monitor"]["flow"]["on"]["max"][i],
                    mist_condition["valve"]["duration"],
                    5 * (i + 1),
                    mist_condition["flow"] > handle["config"]["actuator"]["monitor"]["flow"]["on"]["max"][i],
                    mist_condition["valve"]["duration"] > 5 * (i + 1),
                ]
            )

            if (
                mist_condition["flow"] > handle["config"]["actuator"]["monitor"]["flow"]["on"]["max"][i]
            ) and (mist_condition["valve"]["duration"] > 5 * (i + 1)):
                hazard_notify(
                    handle["config"],
                    (
                        "水漏れしています。"
                        "(バルブを開いてから{duration:.1f}秒経過しても流量が "
                        "{flow:.1f} L/min [> {threshold:.1f} L/min])"
                    ).format(
                        duration=mist_condition["valve"]["duration"],
                        flow=mist_condition["flow"],
                        threshold=handle["config"]["actuator"]["monitor"]["flow"]["on"]["max"][i],
                    ),
                )

        if (mist_condition["flow"] < handle["config"]["actuator"]["monitor"]["flow"]["on"]["min"]) and (
            mist_condition["valve"]["duration"] > 5
        ):
            # NOTE: ハザード扱いにはしない
            unit_cooler.actuator.work_log.add(
                (
                    "元栓が閉じています。"
                    "(バルブを開いてから{duration:.1f}秒経過しても流量が {flow:.1f} L/min)"
                ).format(duration=mist_condition["valve"]["duration"], flow=mist_condition["flow"]),
                unit_cooler.const.LOG_LEVEL.ERROR,
            )
    else:
        logging.debug("Valve is close for %.1f sec", mist_condition["valve"]["duration"])
        if (
            mist_condition["valve"]["duration"]
            >= handle["config"]["actuator"]["monitor"]["flow"]["power_off_sec"]
        ) and (mist_condition["flow"] == 0):
            # バルブが閉じてから長い時間が経っていて流量も 0 の場合、センサーを停止する
            if unit_cooler.actuator.sensor.get_power_state():
                unit_cooler.actuator.work_log.add(
                    "長い間バルブが閉じられていますので、流量計の電源を OFF します。"
                )
                unit_cooler.actuator.sensor.stop()
        elif (mist_condition["valve"]["duration"] > 120) and (
            mist_condition["flow"] > handle["config"]["actuator"]["monitor"]["flow"]["off"]["max"]
        ):
            hazard_notify(
                handle["config"],
                "電磁弁が壊れていますので制御を停止します。"
                + "(バルブを閉じてから{duration:.1f}秒経過しても流量が {flow:.1f} L/min)".format(
                    duration=mist_condition["valve"]["duration"], flow=mist_condition["flow"]
                ),
            )


def check(handle, mist_condition, need_logging):
    handle["monitor_count"] += 1

    if need_logging:
        logging.info(
            "Valve Condition: %s (flow = %s L/min)",
            mist_condition["valve"]["state"].name,
            "?" if mist_condition["flow"] is None else "{flow:.2f}".format(flow=mist_condition["flow"]),
        )

    check_sensing(handle, mist_condition)

    if mist_condition["flow"] is not None:
        check_mist_condition(handle, mist_condition)

    return True
