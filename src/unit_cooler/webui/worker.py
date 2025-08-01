#!/usr/bin/env python3
import logging
import threading
import traceback

import my_lib.footprint

import unit_cooler.const
import unit_cooler.pubsub.subscribe

# グローバル終了フラグ
should_terminate = threading.Event()


def term():
    """終了フラグを設定する関数"""
    should_terminate.set()
    logging.info("Termination flag set for webui worker")


def queue_put(message_queue, message, liveness_file):
    message["state"] = unit_cooler.const.COOLING_STATE(message["state"])

    if message_queue.full():
        message_queue.get()

    logging.info("Receive message: %s", message)

    message_queue.put(message)
    my_lib.footprint.update(liveness_file)


# NOTE: 制御メッセージを Subscribe して、キューに積み、cooler_stat.py で WebUI に渡すワーカ
def subscribe_worker(config, control_host, pub_port, message_queue, liveness_file, msg_count=0):  # noqa: PLR0913
    logging.info("Start webui subscribe worker (%s:%d)", control_host, pub_port)

    ret = 0
    try:
        # 終了フラグを渡してstart_clientを呼び出し
        unit_cooler.pubsub.subscribe.start_client(
            control_host,
            pub_port,
            lambda message: queue_put(message_queue, message, liveness_file),
            msg_count,
            should_terminate,
        )
    except Exception:
        logging.exception("Failed to receive control message")
        unit_cooler.util.notify_error(config, traceback.format_exc())
        ret = -1

    logging.warning("Stop subscribe worker")

    return ret
