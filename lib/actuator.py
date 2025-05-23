#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import pathlib
import time

from work_log import WORK_LOG_LEVEL, work_log

HAZARD_NOTIFY_INTERVAL_MIN = 30

actuator_valve = None


def init_actuator(pin_no):
    global actuator_valve

    # NOTE: Raspberry Pi 以外で実行したときに，GPIO をダミーで差し替え，
    # valve の中でそれをログ通知したいので，初期化関数の中で import する
    import valve

    actuator_valve = valve
    actuator_valve.init(pin_no)


def hazard_clear(config):
    pathlib.Path(config["actuator"]["hazard"]["file"]).unlink(missing_ok=True)


def hazard_notify(config, message):
    if (not pathlib.Path(config["actuator"]["hazard"]["file"]).exists()) or (
        (time.time() - pathlib.Path(config["actuator"]["hazard"]["file"]).stat().st_mtime) / 60
        > HAZARD_NOTIFY_INTERVAL_MIN
    ):
        work_log(message, WORK_LOG_LEVEL.ERROR)
        pathlib.Path(config["actuator"]["hazard"]["file"]).touch()

    actuator_valve.set_state(actuator_valve.VALVE_STATE.CLOSE)


def hazard_check(config):
    if pathlib.Path(config["actuator"]["hazard"]["file"]).exists():
        hazard_notify(config, "過去に水漏れもしくは電磁弁の故障が検出されているので制御を停止しています．")
        return True
    else:
        return False


def set_cooling_state(config, cooling_mode):
    if hazard_check(config):
        cooling_mode = {"state": actuator_valve.COOLING_STATE.IDLE}

    return actuator_valve.set_cooling_state(cooling_mode)


def get_valve_status():
    return actuator_valve.get_status()


def stop_valve_monitor():
    actuator_valve.stop_flow_monitor()


def check_valve_condition(config):
    logging.debug("Check valve condition")

    flow = -1

    valve_status = get_valve_status()
    if valve_status["state"] == actuator_valve.VALVE_STATE.OPEN:
        flow = actuator_valve.get_flow()

        # NOTE: get_flow() の内部で流量センサーの電源を入れている場合は計測に時間がかかるので，
        # その間に電磁弁の状態が変化している可能性があるので，再度状態を取得する
        valve_status = get_valve_status()

        check_valve_condition.last_flow = flow
        if (
            (valve_status["state"] == actuator_valve.VALVE_STATE.OPEN)
            and (flow is not None)
            and (flow < config["actuator"]["valve"]["on"]["min"])
        ):
            if valve_status["duration"] > 5:
                # NOTE: ハザード扱いにはしない
                work_log(
                    "元栓が閉じています．(バルブを開いてから{duration:.1f}秒経過しても流量が {flow:.1f} L/min)".format(
                        duration=valve_status["duration"], flow=flow
                    ),
                    WORK_LOG_LEVEL.ERROR,
                )
        elif (flow is not None) and (flow > config["actuator"]["valve"]["on"]["max"]):
            if valve_status["duration"] > 15:
                hazard_notify(
                    config,
                    "水漏れしています．(バルブを開いてから{duration:.1f}秒経過しても流量が {flow:.1f} L/min)".format(
                        duration=valve_status["duration"],
                        flow=flow,
                    ),
                )
    else:
        logging.debug("Valve is close for {duration:.1f} sec".format(duration=valve_status["duration"]))

        if (valve_status["duration"] >= config["actuator"]["valve"]["power_off_sec"]) and (
            check_valve_condition.last_flow == 0
        ):
            # バルブが閉じてから長い時間が経っていて流量も 0 の場合，センサーを停止する
            flow = 0.0
            if actuator_valve.get_power_state():
                work_log("長い間バルブが閉じられていますので，流量計の電源を OFF します．")
            actuator_valve.stop_sensing()
        else:
            flow = actuator_valve.get_flow(force_power_on=False)
            check_valve_condition.last_flow = flow
            if (
                (valve_status["duration"] > 120)
                and (flow is not None)
                and (flow > config["actuator"]["valve"]["off"]["max"])
            ):
                hazard_notify(
                    config,
                    "電磁弁が壊れていますので制御を停止します．"
                    + "(バルブを閉じてから{duration:.1f}秒経過しても流量が {flow:.1f} L/min)".format(
                        duration=valve_status["duration"], flow=flow
                    ),
                )

    return {"state": valve_status["state"], "flow": flow}


check_valve_condition.last_flow = 0


def send_valve_condition(sender, hostname, recv_cooling_mode, valve_condition, dummy_mode=False):
    # NOTE: 少し加工して送りたいので，まずコピーする
    send_data = {"state": valve_condition["state"]}

    if valve_condition["flow"] is not None:
        send_data["flow"] = valve_condition["flow"]

    if recv_cooling_mode is not None:
        send_data["cooling_mode"] = recv_cooling_mode["mode_index"]

    send_data["state"] = valve_condition["state"].value
    send_data["hostname"] = hostname

    logging.debug("Send: {valve_condition}".format(valve_condition=send_data))

    if dummy_mode:
        return

    if sender.emit("rasp", send_data):
        logging.debug("Send OK")
    else:
        logging.error(sender.last_error)
