#!/usr/bin/env python3
"""
エアコン室外機の冷却モードの指示を出します。

Usage:
  publish.py [-c CONFIG] [-s SERVER_HOST] [-p SERVER_PORT] [-r REAL_PORT] [-n COUNT] [-t SPEEDUP] [-d] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。 [default: config.yaml]
  -s SERVER_HOST    : サーバーのホスト名を指定します。 [default: localhost]
  -p SERVER_PORT    : ZeroMQ の サーバーを動作させるポートを指定します。 [default: 2222]
  -r REAL_PORT      : ZeroMQ の 本当のサーバーを動作させるポートを指定します。 [default: 2200]
  -n COUNT          : n 回制御メッセージを生成したら終了します。0 は制限なし。 [default: 1]
  -t SPEEDUP        : 時短モード。演算間隔を SPEEDUP 分の一にします。 [default: 20]
  -d                : ダミーモード(冷却モードをランダムに生成)で動作します。
  -D                : デバッグモードで動作します。
"""

import json
import logging
import time

import unit_cooler.const
import zmq


def start_server(server_port, func, interval_sec, msg_count=0):
    logging.info("Start ZMQ server (port: %d)...", server_port)

    context = zmq.Context()

    socket = context.socket(zmq.PUB)
    socket.bind(f"tcp://*:{server_port}")

    logging.info("Server initialize done.")

    send_count = 0
    try:
        while True:
            start_time = time.time()
            socket.send_string(f"{unit_cooler.const.PUBSUB_CH} {json.dumps(func())}")

            if msg_count != 0:
                logging.debug("(send_count, msg_count) = (%d, %d)", send_count, msg_count)
                send_count += 1
                # NOTE: Proxy が間に入るので、2回多く回す
                if send_count == (msg_count + 2):
                    logging.info("Terminate, because the specified number of times has been reached.")
                    break

            sleep_sec = max(interval_sec - (time.time() - start_time), 0.5)
            logging.debug("Seep %.1f sec...", sleep_sec)
            time.sleep(sleep_sec)
    except Exception:
        logging.exception("Server failed")

    socket.close()
    context.destroy()

    logging.warning("Stop ZMQ server")


# NOTE: Last Value Caching Proxy
# see https://zguide.zeromq.org/docs/chapter5/
def start_proxy(server_host, server_port, proxy_port, msg_count=0):  # noqa: PLR0915, C901
    logging.info("Start ZMQ proxy server (front: %s:%d, port: %d)...", server_host, server_port, proxy_port)

    context = zmq.Context()

    frontend = context.socket(zmq.SUB)
    frontend.connect(f"tcp://{server_host}:{server_port}")
    frontend.setsockopt_string(zmq.SUBSCRIBE, unit_cooler.const.PUBSUB_CH)

    backend = context.socket(zmq.XPUB)
    backend.bind(f"tcp://*:{proxy_port}")

    cache = {}

    poller = zmq.Poller()
    poller.register(frontend, zmq.POLLIN)
    poller.register(backend, zmq.POLLIN)

    subscribed = False  # NOTE: テスト用
    proxy_count = 0
    while True:
        try:
            events = dict(poller.poll(100))
        except KeyboardInterrupt:  # pragma: no cover
            break

        if frontend in events:
            recv_data = frontend.recv_string()
            ch, json_str = recv_data.split(" ", 1)
            logging.debug("Store cache")
            cache[ch] = json_str

            backend.send_string(recv_data)
            if subscribed:
                proxy_count += 1

        if backend in events:
            logging.debug("Backend event")
            event = backend.recv()
            if event[0] == 0:
                logging.debug("Unsubscribed")
            elif event[0] == 1:
                logging.debug("Subscribed")
                subscribed = True
                ch = event[1:].decode("utf-8")
                if ch in cache:
                    logging.debug("Send cache")
                    backend.send_string(f"{unit_cooler.const.PUBSUB_CH} {cache[unit_cooler.const.PUBSUB_CH]}")
                    proxy_count += 1
                else:
                    logging.warning("Cache is empty")
            else:  # pragma: no cover
                pass

        if msg_count != 0:
            logging.debug("(proxy_count, msg_count) = (%d, %d)", proxy_count, msg_count)
            if proxy_count == msg_count:
                logging.info("Terminate, because the specified number of times has been reached.")
                break

    frontend.close()
    backend.close()
    context.destroy()

    logging.warning("Stop ZMQ proxy server")


if __name__ == "__main__":
    # TEST Code
    import os
    import threading

    import docopt
    import my_lib.config
    import my_lib.logger
    import my_lib.pretty
    import unit_cooler.actuator.subscribe
    import unit_cooler.const
    import unit_cooler.controller.engine

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    server_host = args["-s"]
    server_port = int(os.environ.get("HEMS_SERVER_PORT", args["-p"]))
    real_port = int(args["-r"])
    msg_count = int(args["-n"])
    speedup = int(args["-t"])
    dummy_mode = args["-D"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    proxy_thread = threading.Thread(
        target=start_proxy,
        args=(server_host, real_port, server_port, msg_count),
    )
    proxy_thread.start()

    server_thread = threading.Thread(
        target=start_server,
        args=(
            real_port,
            lambda: unit_cooler.controller.engine.gen_control_msg(config, dummy_mode, speedup),
            config["controller"]["interval_sec"] / speedup,
            msg_count,
        ),
    )
    server_thread.start()

    unit_cooler.actuator.subscribe.start_client(
        server_host,
        server_port,
        lambda message: logging.info("receive: %s", message),
        msg_count,
    )

    server_thread.join()
    proxy_thread.join()
