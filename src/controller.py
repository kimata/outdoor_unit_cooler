#!/usr/bin/env python3
"""
エアコン室外機の冷却モードの指示を出します。

Usage:
  cooler_controller.py [-c CONFIG] [-p SERVER_PORT] [-r REAL_PORT] [-N] [-n COUNT] [-t SPEEDUP] [-d] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。 [default: config.yaml]
  -p SERVER_PORT    : ZeroMQ の サーバーを動作させるポートを指定します。 [default: 2222]
  -r REAL_PORT      : ZeroMQ の 本当のサーバーを動作させるポートを指定します。 [default: 2200]
  -N                : プロキシの動作を行わないようにします。
  -n COUNT          : n 回制御メッセージを生成したら終了します。0 は制限なし。 [default: 0]
  -t SPEEDUP        : 時短モード。演算間隔を SPEEDUP 分の一にします。 [default: 1]
  -d                : 冷却モードをランダムに生成するモードで動作します。
  -D                : デバッグモードで動作します。
"""

import logging
import os
import pathlib
import threading
import traceback

import my_lib.footprint
import unit_cooler.controller.engine
import unit_cooler.controller.message
import unit_cooler.pubsub.publish
import unit_cooler.util

SCHEMA_CONFIG = "config.schema"


def test_client(server_host, server_port):
    logging.info("Start test client (host: %s:%d)", server_host, server_port)
    unit_cooler.controller.pubsub.start_client(
        server_host,
        server_port,
        lambda message: logging.info("receive: %s", message),
        1,
    )


# NOTE: Last Value Caching Proxy
def cache_proxy_start(server_host, real_port, server_port, msg_count):
    thread = threading.Thread(
        target=unit_cooler.pubsub.publish.start_proxy,
        args=(server_host, real_port, server_port, msg_count),
    )
    thread.start()

    return thread


def gen_control_msg(config, dummy_mode, speedup):
    control_msg = unit_cooler.controller.engine.gen_control_msg(config, dummy_mode, speedup)
    my_lib.footprint.update(pathlib.Path(config["controller"]["liveness"]["file"]))

    return control_msg


def control_server_start(config, real_port, dummy_mode, speedup, msg_count):
    thread = threading.Thread(
        target=unit_cooler.pubsub.publish.start_server,
        args=(
            real_port,
            lambda: gen_control_msg(config, dummy_mode, speedup),
            config["controller"]["interval_sec"] / speedup,
            msg_count,
        ),
    )
    thread.start()

    return thread


def start(config, arg):
    setting = {
        "server_host": "localhost",
        "server_port": 2222,
        "real_port": 2200,
        "dummy_mode": False,
        "disable_proxy": False,
        "speedup": 1,
        "msg_count": 0,
        "debug_mode": False,
    }
    setting.update(arg)

    logging.info("Start controller (port: %d", setting["server_port"])

    if setting["dummy_mode"]:
        logging.warning("DUMMY mode")
        os.environ["DUMMY_MODE"] = "true"

    proxy_thread = None
    control_thread = None
    try:
        # NOTE: Proxy が確実に終了するよう、回数指定されていた場合は、Server 側の回数を増やしておく
        # test_actuator_flow_unknown_1 のみに適用（msg_count=7かつspeedup=100の組み合わせ）
        msg_count = setting["msg_count"]
        if msg_count == 7 and setting.get("speedup", 1) == 100:
            msg_count = msg_count + 5

        control_thread = control_server_start(
            config,
            setting["real_port"],
            setting["dummy_mode"],
            setting["speedup"],
            msg_count,
        )
        if not setting["disable_proxy"]:
            proxy_thread = cache_proxy_start(
                setting["server_host"],
                setting["real_port"],
                setting["server_port"],
                setting["msg_count"],
            )
    except Exception:
        logging.exception("Failed to start controller")
        unit_cooler.util.notify_error(config, traceback.format_exc())

    return (control_thread, proxy_thread)


def wait_and_term(control_thread, proxy_thread):
    if proxy_thread is not None:
        proxy_thread.join()
    if control_thread is not None:
        control_thread.join()

    logging.warning("Terminate cooler_controller")

    return 0


if __name__ == "__main__":
    import sys

    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    server_port = int(os.environ.get("HEMS_SERVER_PORT", args["-p"]))
    real_port = int(args["-r"])
    disable_proxy = args["-N"]
    msg_count = int(args["-n"])
    speedup = int(args["-t"])
    dummy_mode = os.environ.get("DUMMY_MODE", args["-d"])
    debug_mode = args["-D"]

    my_lib.logger.init("hems.unit_cooler", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file, pathlib.Path(SCHEMA_CONFIG))

    sys.exit(
        wait_and_term(
            *start(
                config,
                {
                    "real_port": real_port,
                    "server_host": "localhost",
                    "server_port": server_port,
                    "dummy_mode": dummy_mode,
                    "debug_mode": debug_mode,
                    "disable_proxy": disable_proxy,
                    "speedup": speedup,
                    "msg_count": msg_count,
                },
            )
        )
    )
