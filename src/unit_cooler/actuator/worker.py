#!/usr/bin/env python3
"""
アクチュエータで動作するワーカです。

Usage:
  worker.py [-c CONFIG] [-s CONTROL_HOST] [-p PUB_PORT] [-n COUNT] [-t SPEEDUP] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。 [default: config.yaml]
  -s CONTROL_HOST   : コントローラのホスト名を指定します。 [default: localhost]
  -p PUB_PORT       : ZeroMQ の Pub サーバーを動作させるポートを指定します。 [default: 2222]
  -n COUNT          : n 回制御メッセージを受信したら終了します。0 は制限なし。 [default: 1]
  -t SPEEDUP        : 時短モード。演算間隔を SPEEDUP 分の一にします。 [default: 1]
  -D                : デバッグモードで動作します。
"""

import concurrent.futures
import logging
import pathlib
import threading
import time
import traceback

import my_lib.footprint

import unit_cooler.actuator.control
import unit_cooler.actuator.monitor
import unit_cooler.const
import unit_cooler.pubsub.subscribe
import unit_cooler.util

last_control_message = {"mode_index": -1, "state": unit_cooler.const.COOLING_STATE.IDLE}
should_terminate = threading.Event()


def queue_put(message_queue, message, liveness_file):
    message["state"] = unit_cooler.const.COOLING_STATE(message["state"])

    logging.info("Receive message: %s", message)

    message_queue.put(message)
    my_lib.footprint.update(liveness_file)


def sleep_until_next_iter(start_time, interval_sec):
    sleep_sec = max(interval_sec - (time.time() - start_time), 0.5)
    logging.debug("Seep %.1f sec...", sleep_sec)
    time.sleep(sleep_sec)


# NOTE: コントローラから制御指示を受け取ってキューに積むワーカ
def subscribe_worker(config, control_host, pub_port, message_queue, liveness_file, msg_count=0):  # noqa: PLR0913
    logging.info("Start actuator subscribe worker (%s:%d)", control_host, pub_port)
    ret = 0
    try:
        unit_cooler.pubsub.subscribe.start_client(
            control_host,
            pub_port,
            lambda message: queue_put(message_queue, message, liveness_file),
            msg_count,
        )
    except Exception:
        logging.exception("Failed to receive control message")
        unit_cooler.util.notify_error(config, traceback.format_exc())
        ret = -1

    logging.warning("Stop subscribe worker")
    return ret


# NOTE: バルブの状態をモニタするワーカ
def monitor_worker(config, liveness_file, dummy_mode=False, speedup=1, msg_count=0):
    global last_control_message
    global should_terminate

    logging.info("Start monitor worker")

    interval_sec = config["actuator"]["monitor"]["interval_sec"] / speedup
    try:
        handle = unit_cooler.actuator.monitor.gen_handle(config, interval_sec)
    except Exception:
        logging.exception("Failed to create handle")

        unit_cooler.actuator.work_log.add(
            "流量のロギングを開始できません。", unit_cooler.const.LOG_LEVEL.ERROR
        )
        return -1

    i = 0
    ret = 0
    try:
        while True:
            start_time = time.time()

            need_logging = (i % handle["log_period"]) == 0
            i += 1

            mist_condition = unit_cooler.actuator.monitor.get_mist_condition()
            unit_cooler.actuator.monitor.check(handle, mist_condition, need_logging)
            unit_cooler.actuator.monitor.send_mist_condition(
                handle, mist_condition, last_control_message, dummy_mode
            )

            my_lib.footprint.update(liveness_file)

            if should_terminate.is_set():
                logging.info("Terminate monitor worker")
                break

            if msg_count != 0:
                logging.debug("(monitor_count, msg_count) = (%d, %d)", handle["monitor_count"], msg_count)
                # NOTE: monitor_worker が先に終了しないようにする
                if handle["monitor_count"] >= (msg_count + 100):
                    logging.info(
                        "Terminate monitor worker, because the specified number of times has been reached."
                    )
                    break

            sleep_until_next_iter(start_time, interval_sec)
    except Exception:
        unit_cooler.util.notify_error(config, traceback.format_exc())
        ret = -1

    logging.warning("Stop monitor worker")
    return ret


# NOTE: バルブを制御するワーカ
def control_worker(config, message_queue, liveness_file, dummy_mode=False, speedup=1, msg_count=0):  # noqa: PLR0913
    global last_control_message  # noqa: PLW0603
    global should_terminate

    logging.info("Start control worker")

    if dummy_mode:
        logging.warning("DUMMY mode")

    interval_sec = config["actuator"]["control"]["interval_sec"] / speedup
    handle = unit_cooler.actuator.control.gen_handle(config, message_queue)

    ret = 0
    try:
        while True:
            start_time = time.time()

            last_control_message = unit_cooler.actuator.control.get_control_message(
                handle, last_control_message
            )

            unit_cooler.actuator.control.execute(config, last_control_message)

            my_lib.footprint.update(liveness_file)

            if should_terminate.is_set():
                logging.info("Terminate control worker")
                break

            if msg_count != 0:
                logging.debug("(receive_count, msg_count) = (%d, %d)", handle["receive_count"], msg_count)
                if handle["receive_count"] >= msg_count:
                    logging.info("Terminate control, because the specified number of times has been reached.")
                    break

            sleep_until_next_iter(start_time, interval_sec)
    except Exception:
        logging.exception("Failed to control valve")
        unit_cooler.util.notify_error(config, traceback.format_exc())
        ret = -1

    logging.warning("Stop control worker")
    # NOTE: Queue を close した後に put されると ValueError が発生するので、
    # 明示的に閉じるのをやめた。
    # message_queue.close()

    return ret


def get_worker_def(config, message_queue, setting):
    return [
        {
            "name": "subscribe_worker",
            "param": [
                subscribe_worker,
                config,
                setting["control_host"],
                setting["pub_port"],
                message_queue,
                pathlib.Path(config["actuator"]["subscribe"]["liveness"]["file"]),
                setting["msg_count"],
            ],
        },
        {
            "name": "monitor_worker",
            "param": [
                monitor_worker,
                config,
                pathlib.Path(config["actuator"]["monitor"]["liveness"]["file"]),
                setting["dummy_mode"],
                setting["speedup"],
                setting["msg_count"],
            ],
        },
        {
            "name": "control_worker",
            "param": [
                control_worker,
                config,
                message_queue,
                pathlib.Path(config["actuator"]["control"]["liveness"]["file"]),
                setting["dummy_mode"],
                setting["speedup"],
                setting["msg_count"],
            ],
        },
    ]


def start(executor, worker_def):
    global should_terminate

    should_terminate.clear()
    thread_list = []

    for worker_info in worker_def:
        future = executor.submit(*worker_info["param"])
        thread_list.append({"name": worker_info["name"], "future": future})

    return thread_list


def term():
    global should_terminate

    should_terminate.set()


if __name__ == "__main__":
    # TEST Code
    import multiprocessing
    import os
    import pathlib

    import docopt
    import my_lib.config
    import my_lib.logger
    import my_lib.pretty
    import my_lib.webapp.config

    import unit_cooler.actuator.valve

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    control_host = os.environ.get("HEMS_CONTROL_HOST", args["-s"])
    pub_port = int(os.environ.get("HEMS_PUB_PORT", args["-p"]))
    speedup = int(args["-t"])
    msg_count = int(args["-n"])
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)
    message_queue = multiprocessing.Queue()
    event_queue = multiprocessing.Queue()

    os.environ["DUMMY_MODE"] = "true"

    my_lib.webapp.config.init(config["actuator"])
    my_lib.webapp.log.init(config)
    unit_cooler.actuator.work_log.init(config, event_queue)

    unit_cooler.actuator.valve.init(config["actuator"]["control"]["valve"]["pin_no"])
    unit_cooler.actuator.monitor.init(config["actuator"]["control"]["valve"]["pin_no"])

    # NOTE: テストしやすいように、threading.Thread ではなく multiprocessing.pool.ThreadPool を使う
    executor = concurrent.futures.ThreadPoolExecutor()

    setting = {
        "control_host": control_host,
        "pub_port": pub_port,
        "speedup": speedup,
        "msg_count": msg_count,
        "dummy_mode": True,
    }

    thread_list = start(executor, get_worker_def(config, message_queue, setting))

    for thread_info in thread_list:
        logging.info("Wait %s finish", thread_info["name"])

        if thread_info["future"].result() != 0:
            logging.warning("Error occurred in %s", thread_info["name"])

    unit_cooler.actuator.work_log.term()

    logging.info("Shutdown executor")
    executor.shutdown()
