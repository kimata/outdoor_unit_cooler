#!/usr/bin/env python3
import json
import logging

import zmq

import unit_cooler.const


def start_client(server_host, server_port, func, msg_count=0):
    logging.info("Start ZMQ client...")

    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    target = f"tcp://{server_host}:{server_port}"
    socket.connect(target)
    socket.setsockopt_string(zmq.SUBSCRIBE, unit_cooler.const.PUBSUB_CH)

    logging.info("Client initialize done.")

    receive_count = 0
    while True:
        ch, json_str = socket.recv_string().split(" ", 1)
        json_data = json.loads(json_str)
        logging.debug("recv %s", json_data)
        func(json_data)

        if msg_count != 0:
            receive_count += 1
            logging.debug("(receive_count, msg_count) = (%d, %d)", receive_count, msg_count)
            if receive_count == msg_count:
                logging.info("Terminate, because the specified number of times has been reached.")
                break

    logging.warning("Stop ZMQ client")

    socket.disconnect(target)
    socket.close()
    context.destroy()
