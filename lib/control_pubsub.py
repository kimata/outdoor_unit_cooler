#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import zmq
import json
import logging
import time

CH = "unit_cooler"
SER_TIMEOUT = 10


def start_server(server_port, func, interval_sec, is_one_time=False):
    logging.info("Start serial server...")

    context = zmq.Context()

    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:{port}".format(port=server_port))

    logging.info("Server initialize done.")

    while True:
        socket.send_string("{ch} {json_str}".format(ch=CH, json_str=json.dumps(func())))

        if is_one_time:
            break
        time.sleep(interval_sec)


def start_client(server_host, server_port, func):
    logging.info("Start serial client...")

    socket = zmq.Context().socket(zmq.SUB)
    socket.connect("tcp://{host}:{port}".format(host=server_host, port=server_port))
    socket.setsockopt_string(zmq.SUBSCRIBE, CH)

    logging.info("Client initialize done.")

    while True:
        ch, json_str = socket.recv_string().split(" ", 1)
        json_data = json.loads(json_str)
        logging.debug("recv {json}".format(json=json_data))
        func(json_data)
