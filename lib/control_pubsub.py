#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import zmq
import json
import logging
import time
import traceback

CH = "unit_cooler"
SER_TIMEOUT = 10


def start_server(server_port, func, interval_sec, msg_count=0):
    logging.info("Start ZMQ server (port: {port})...".format(port=server_port))

    context = zmq.Context()

    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:{port}".format(port=server_port))

    logging.info("Server initialize done.")

    i = 0
    try:
        while True:
            start_time = time.time()
            socket.send_string(
                "{ch} {json_str}".format(ch=CH, json_str=json.dumps(func()))
            )

            if msg_count != 0:
                # NOTE: Proxy が間に入るので，1回多く回す
                if i == msg_count:
                    break
                i += 1

            sleep_sec = max(interval_sec - (time.time() - start_time), 1)
            logging.debug("Seep {sleep_sec:.1f} sec...".format(sleep_sec=sleep_sec))
            time.sleep(sleep_sec)
    except:
        logging.error(traceback.format_exc())

    socket.close()
    context.destroy()

    logging.warning("Stop ZMQ server")


# NOTE: Last Value Caching Proxy
# see https://zguide.zeromq.org/docs/chapter5/
def start_proxy(server_host, server_port, proxy_port, msg_count=0):
    logging.info(
        "Start ZMQ proxy server (front: {server_host}:{server_port}, port: {port})...".format(
            server_host=server_host, server_port=server_port, port=proxy_port
        )
    )

    context = zmq.Context()

    frontend = context.socket(zmq.SUB)
    frontend.connect("tcp://{host}:{port}".format(host=server_host, port=server_port))
    frontend.setsockopt_string(zmq.SUBSCRIBE, CH)

    backend = context.socket(zmq.XPUB)
    backend.bind("tcp://*:{port}".format(port=proxy_port))

    cache = {}

    poller = zmq.Poller()
    poller.register(frontend, zmq.POLLIN)
    poller.register(backend, zmq.POLLIN)

    i = 0
    while True:
        try:
            events = dict(poller.poll(1000))
        except KeyboardInterrupt:  # pragma: no cover
            break

        if frontend in events:
            recv_data = frontend.recv_string()
            ch, json_str = recv_data.split(" ", 1)
            logging.debug("Store cache")
            cache[ch] = json_str

            backend.send_string(recv_data)

        if msg_count != 0:
            i += 1
            if i == msg_count:
                break

        if backend in events:
            logging.debug("Backend event")
            event = backend.recv()
            if event[0] == 0:
                logging.debug("Unsubscribed")
            elif event[0] == 1:
                logging.debug("Subscribed")
                ch = event[1:].decode("utf-8")
                if ch in cache:
                    logging.debug("Send cache")
                    backend.send_string(
                        "{ch} {json_str}".format(ch=CH, json_str=cache[ch])
                    )
                else:
                    logging.warning("Cache is empty")
            else:  # pragma: no cover
                pass

    frontend.close()
    backend.close()
    context.destroy()

    logging.warning("Stop ZMQ proxy server")


def start_client(server_host, server_port, func, msg_count=0):
    logging.info("Start ZMQ client...")

    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    target = "tcp://{host}:{port}".format(host=server_host, port=server_port)
    socket.connect(target)
    socket.setsockopt_string(zmq.SUBSCRIBE, CH)

    logging.info("Client initialize done.")

    i = 0
    while True:
        ch, json_str = socket.recv_string().split(" ", 1)
        json_data = json.loads(json_str)
        logging.debug("recv {json}".format(json=json_data))
        func(json_data)

        if msg_count != 0:
            i += 1
            if i == msg_count:
                break

    logging.warning("Stop ZMQ client")

    socket.disconnect(target)
    socket.close()
    context.destroy()


# NOTE: 現在は使用していない
def get_last_message(server_host, server_port):  # pragma: no cover
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    target = "tcp://{host}:{port}".format(host=server_host, port=server_port)
    socket.connect(target)
    socket.setsockopt_string(zmq.SUBSCRIBE, CH)

    ch, json_str = socket.recv_string().split(" ", 1)

    socket.disconnect(target)
    socket.close()
    context.destroy()

    return json.loads(json_str)
