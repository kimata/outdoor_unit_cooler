#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import zmq
import json
import logging
import time

CH = "unit_cooler"
SER_TIMEOUT = 10


def start_server(server_port, func, interval_sec, is_one_time=False):
    logging.info("Start control server (port: {port})...".format(port=server_port))

    context = zmq.Context()

    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:{port}".format(port=server_port))

    logging.info("Server initialize done.")

    i = 0
    while True:
        start_time = time.time()
        socket.send_string("{ch} {json_str}".format(ch=CH, json_str=json.dumps(func())))

        if is_one_time:
            # NOTE: Proxy がいるので，2回回す
            if i == 1:
                break
            i += 1

        sleep_sec = interval_sec - (time.time() - start_time)
        logging.debug("Seep {sleep_sec:.1f} sec...".format(sleep_sec=sleep_sec))
        time.sleep(sleep_sec)


# NOTE: Last Value Caching Proxy
# see https://zguide.zeromq.org/docs/chapter5/
def start_proxy(server_host, server_port, proxy_port, is_one_time=False):
    logging.info(
        "Start proxy server (front: {server_host}:{server_port}, port: {port})...".format(
            server_host=server_host, server_port=server_port, port=proxy_port
        )
    )

    context = zmq.Context.instance()

    frontend = context.socket(zmq.SUB)
    frontend.connect("tcp://{host}:{port}".format(host=server_host, port=server_port))
    frontend.setsockopt_string(zmq.SUBSCRIBE, CH)

    backend = context.socket(zmq.XPUB)
    backend.bind("tcp://*:{port}".format(port=proxy_port))

    cache = {}

    poller = zmq.Poller()
    poller.register(frontend, zmq.POLLIN)
    poller.register(backend, zmq.POLLIN)

    while True:
        events = dict(poller.poll(1000))

        if frontend in events:
            recv_data = frontend.recv_string()
            ch, json_str = recv_data.split(" ", 1)
            logging.info("store cache")
            cache[ch] = json_str
            backend.send_string(recv_data)
            if is_one_time:
                break

        if backend in events:
            event = backend.recv()
            if event[0] == 1:
                logging.info("subscribed")
                ch = event[1:].decode("utf-8")
                if ch in cache:
                    logging.info("send cache")
                    backend.send_string(
                        "{ch} {json_str}".format(ch=CH, json_str=cache[ch])
                    )
                else:
                    logging.warn("cache is empty")


def start_client(server_host, server_port, func, is_one_time=False):
    logging.info("Start control client...")

    socket = zmq.Context().socket(zmq.SUB)
    socket.connect("tcp://{host}:{port}".format(host=server_host, port=server_port))
    socket.setsockopt_string(zmq.SUBSCRIBE, CH)

    logging.info("Client initialize done.")

    while True:
        ch, json_str = socket.recv_string().split(" ", 1)
        json_data = json.loads(json_str)
        logging.debug("recv {json}".format(json=json_data))
        func(json_data)

        if is_one_time:
            break


def get_last_message(server_host, server_port):
    socket = zmq.Context().socket(zmq.SUB)
    socket.connect("tcp://{host}:{port}".format(host=server_host, port=server_port))
    socket.setsockopt_string(zmq.SUBSCRIBE, CH)

    ch, json_str = socket.recv_string().split(" ", 1)

    return json.loads(json_str)
