#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import pathlib
import pytest
import re
import time
import json
import datetime
from unittest import mock
import logging

sys.path.append(str(pathlib.Path(__file__).parent.parent / "app"))
sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

CONFIG_FILE = "config.example.yaml"


@pytest.fixture(scope="function", autouse=True)
def env_mock():
    with mock.patch.dict("os.environ", {"TEST": "true"}) as fixture:
        yield fixture


@pytest.fixture(scope="function", autouse=True)
def clear_hazard():
    import actuator
    from config import load_config

    actuator.clear_hazard(load_config(CONFIG_FILE))


@pytest.fixture(scope="function", autouse=True)
def slack_mock():
    with mock.patch(
        "notify_slack.slack_sdk.web.client.WebClient.chat_postMessage",
        retunr_value=True,
    ) as fixture:
        yield fixture


@pytest.fixture(scope="function", autouse=True)
def fluent_mock():
    with mock.patch("fluent.sender.FluentSender.emit") as fixture:

        def emit_mock(label, data):
            return True

        fixture.side_effect = emit_mock

        yield fixture


def gen_sensor_data(value=[30, 34, 25], valid=True):
    sensor_data = {
        "value": value,
        "time": [],
        "valid": valid,
    }

    for i in range(len(value)):
        sensor_data["time"].append(
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(minutes=i - len(value))
        )

    return sensor_data


def gen_fd_q10c_ser_trans_sense():
    # NOTE: send/recv はプログラム視点．SPI デバイスが送信すべき内容が recv．
    return [
        {"send": [0x70, 0x09, 0x93], "recv": [0x70, 0x09, 0x93, 0x2D]},
        {"send": [0x61, 0x2E, 0x94], "recv": [0x61, 0x2E, 0x94, 0x2D]},
        {"send": [0x62, 0x12, 0x7], "recv": [0x62, 0x12, 0x7, 0x2D]},
        {"send": [0xF0, 0x2D], "recv": [0xF0, 0x2D, 0xD4, 0x1B]},
        {"send": [0xE1, 0x28], "recv": [0xE1, 0x28, 0x1, 0x3C]},
        {"send": [0xE2, 0x18], "recv": [0xE2, 0x18, 0x1, 0x3C]},
        {"send": [0xE3, 0x9], "recv": [0xE3, 0x9, 0xD4, 0x1B]},
    ]


def gen_fd_q10c_ser_trans_ping():
    # NOTE: send/recv はプログラム視点．SPI デバイスが送信すべき内容が recv．
    return [
        {"send": [0x70, 0x09, 0x93], "recv": [0x70, 0x09, 0x93, 0x2D]},
        {"send": [0x61, 0x35, 0x12], "recv": [0x61, 0x35, 0x12, 0x2D]},
        {"send": [0x62, 0x09, 0x81], "recv": [0x62, 0x09, 0x81, 0x2D]},
        {"send": [0xF0, 0x2D], "recv": [0xF0, 0x2D, 0xD9, 0x3A]},
        {"send": [0xE1, 0x28], "recv": [0xE1, 0x28, 0x46, 0x06]},
        {"send": [0xE2, 0x18], "recv": [0xE2, 0x18, 0x44, 0x27]},
        {"send": [0xE3, 0x09], "recv": [0xE3, 0x09, 0x2D, 0x28]},
        {"send": [0xE4, 0x2B], "recv": [0xE4, 0x2B, 0x51, 0x30]},
        {"send": [0xE5, 0x3A], "recv": [0xE5, 0x3A, 0x31, 0x0C]},
        {"send": [0xE6, 0x0A], "recv": [0xE6, 0x0A, 0x30, 0x1D]},
        {"send": [0xE7, 0x1B], "recv": [0xE7, 0x1B, 0x43, 0x05]},
        {"send": [0xE8, 0x1B], "recv": [0xE8, 0x1B, 0xE5, 0x3A]},
    ]


def mock_fd_q10c(mocker, ser_trans=gen_fd_q10c_ser_trans_sense()):
    import logging
    import struct
    import sensor.fd_q10c

    spidev_mock = mocker.MagicMock()
    spidev_mock.xfer2.return_value = [0x00, 0x00]
    mocker.patch("spidev.SpiDev", return_value=spidev_mock)

    def ser_read_mock(length):
        for trans in ser_trans:
            if trans["send"] == ser_read_mock.write_data:
                return struct.pack("B" * len(trans["recv"]), *trans["recv"])

        logging.warning("Unknown serial transfer")
        return None

    ser_read_mock.write_data = None

    def ser_write_mock(data):
        ser_read_mock.write_data = list(struct.unpack("B" * len(data), data))

    ser_mock = mocker.MagicMock()
    ser_mock.read.side_effect = ser_read_mock
    ser_mock.write.side_effect = ser_write_mock
    mocker.patch("serial.Serial", return_value=ser_mock)

    mocker.patch("valve.FD_Q10C", new=sensor.fd_q10c.FD_Q10C)


def mock_gpio(mocker):
    gpio_mock = mocker.MagicMock()

    def gpio_output_mock(gpio, value):
        gpio_input_mock.data[gpio] = value

    def gpio_input_mock(gpio):
        return gpio_input_mock.data[gpio]

    gpio_input_mock.data = {}

    gpio_mock.output.side_effect = gpio_output_mock
    gpio_mock.input.side_effect = gpio_input_mock

    mocker.patch("valve.GPIO", return_value=gpio_mock)


######################################################################
def test_controller(mocker):
    import cooler_controller

    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    cooler_controller.wait_and_term(
        *cooler_controller.start(
            {
                "speedup": 40,
                "msg_count": 1,
            }
        )
    )


def test_controller_aircon_mode(mocker):
    import cooler_controller

    def fetch_data_mock(
        db_config,
        measure,
        hostname,
        field,
        start="-30h",
        stop="now()",
        every_min=1,
        window_min=3,
        create_empty=True,
        last=False,
    ):
        fetch_data_mock.i += 1

        if (fetch_data_mock.i % 4) == 0:
            return gen_sensor_data([10])
        elif (fetch_data_mock.i % 4) == 1:
            return gen_sensor_data([50])
        elif (fetch_data_mock.i % 4) == 2:
            return gen_sensor_data([600])
        else:
            return gen_sensor_data([1100])

    fetch_data_mock.i = 0

    mocker.patch("control.fetch_data", side_effect=fetch_data_mock)

    cooler_controller.wait_and_term(
        *cooler_controller.start(
            {
                "speedup": 40,
                "msg_count": 1,
            }
        )
    )


def test_controller_aircon_invalid(mocker):
    import cooler_controller

    def fetch_data_mock(
        db_config,
        measure,
        hostname,
        field,
        start="-30h",
        stop="now()",
        every_min=1,
        window_min=3,
        create_empty=True,
        last=False,
    ):
        if field == "power":
            sensor_data = gen_sensor_data()
            sensor_data["valid"] = False
            return sensor_data
        else:
            return gen_sensor_data()

    mocker.patch("control.fetch_data", side_effect=fetch_data_mock)

    cooler_controller.wait_and_term(
        *cooler_controller.start(
            {
                "speedup": 40,
                "msg_count": 1,
            }
        )
    )


def test_controller_temp_invalid(mocker):
    import cooler_controller

    def fetch_data_mock(
        db_config,
        measure,
        hostname,
        field,
        start="-30h",
        stop="now()",
        every_min=1,
        window_min=3,
        create_empty=True,
        last=False,
    ):
        if field == "temp":
            sensor_data = gen_sensor_data()
            sensor_data["valid"] = False
            return sensor_data
        else:
            return gen_sensor_data()

    mocker.patch("control.fetch_data", side_effect=fetch_data_mock)

    cooler_controller.wait_and_term(
        *cooler_controller.start(
            {
                "speedup": 40,
                "msg_count": 1,
            }
        )
    )


def test_controller_temp_low(mocker):
    import cooler_controller

    def fetch_data_mock(
        db_config,
        measure,
        hostname,
        field,
        start="-30h",
        stop="now()",
        every_min=1,
        window_min=3,
        create_empty=True,
        last=False,
    ):
        if field == "temp":
            return gen_sensor_data([0])
        else:
            return gen_sensor_data()

    mocker.patch("control.fetch_data", side_effect=fetch_data_mock)

    cooler_controller.wait_and_term(
        *cooler_controller.start(
            {
                "speedup": 40,
                "msg_count": 1,
            }
        )
    )


def test_test_client(mocker):
    import cooler_controller

    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    control_handle = cooler_controller.start(
        {
            "dummy_mode": True,
            "speedup": 40,
            "msg_count": 5,
        }
    )
    cooler_controller.start({"client_mode": True})

    cooler_controller.wait_and_term(*control_handle)


def test_controller_sensor_error(mocker):
    import cooler_controller

    mocker.patch("influxdb_client.InfluxDBClient.query_api", side_effect=RuntimeError())

    cooler_controller.wait_and_term(
        *cooler_controller.start(
            {
                "speedup": 40,
                "msg_count": 1,
            }
        )
    )


def test_controller_dummy_error(mocker):
    import cooler_controller

    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    def send_string_mock(
        u: str, flags: int = 0, copy: bool = True, encoding: str = "utf-8", **kwargs
    ):
        send_string_mock.i += 1

        if send_string_mock.i == 1:
            return True
        else:
            raise RuntimeError()

    send_string_mock.i = 0

    mocker.patch("control_pubsub.zmq.Socket.send_string", side_effect=send_string_mock)

    cooler_controller.wait_and_term(
        *cooler_controller.start({"speedup": 40, "msg_count": 1, "dummy_mode": True})
    )


def test_controller_view_msg():
    import cooler_controller

    cooler_controller.start(
        {
            "view_msg_mode": True,
        }
    )


def test_actuator(mocker):
    import requests

    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler

    mock_gpio(mocker)
    mock_fd_q10c(mocker)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    actuator_handle = unit_cooler.start(
        {
            "speedup": 40,
            "dummy_mode": True,
            "msg_count": 4,
        }
    )

    control_handle = cooler_controller.start(
        {
            "speedup": 40,
            "dummy_mode": True,
            "msg_count": 10,
        }
    )

    requests.Session().mount(
        "http://",
        requests.adapters.HTTPAdapter(
            max_retries=requests.adapters.Retry(
                total=120,
                connect=100,
                backoff_factor=0.5,
            )
        ),
    )
    res = requests.get("http://localhost:5001/unit_cooler/api/log_view")
    assert "data" in json.loads(res.text)

    response = requests.get(
        "http://localhost:5001/unit_cooler/api/event",
        params={"count": "1"},
    )
    assert response.status_code == 200
    assert response.text.strip() == "data: log"

    unit_cooler.wait_and_term(*actuator_handle)
    cooler_controller.wait_and_term(*control_handle)


def test_actuator_iolink_short(mocker):
    import requests

    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler
    import sensor.fd_q10c

    mock_gpio(mocker)

    fd_q10c_ser_trans = gen_fd_q10c_ser_trans_sense()
    fd_q10c_ser_trans[3]["recv"] = fd_q10c_ser_trans[3]["recv"][0:2]
    mock_fd_q10c(mocker, fd_q10c_ser_trans)
    sensor.fd_q10c.FD_Q10C().get_value()

    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    actuator_handle = unit_cooler.start(
        {
            "speedup": 40,
            "msg_count": 6,
        }
    )

    control_handle = cooler_controller.start(
        {
            "speedup": 40,
            "dummy_mode": True,
            "msg_count": 12,
        }
    )

    requests.Session().mount(
        "http://",
        requests.adapters.HTTPAdapter(
            max_retries=requests.adapters.Retry(
                total=120,
                connect=100,
                backoff_factor=0.5,
            )
        ),
    )
    res = requests.get("http://localhost:5001/unit_cooler/api/log_view")
    assert "data" in json.loads(res.text)

    response = requests.get(
        "http://localhost:5001/unit_cooler/api/event",
        params={"count": "1"},
    )
    assert response.status_code == 200
    assert response.text.strip() == "data: log"

    unit_cooler.wait_and_term(*actuator_handle)
    cooler_controller.wait_and_term(*control_handle)


# def test_actuator_slow_start(mocker):
#     import cooler_controller
#     import unit_cooler

#     mock_gpio(mocker)
#     mock_fd_q10c(mocker)
#     mocker.patch("control.fetch_data", return_value=gen_sensor_data())

#     control_handle = cooler_controller.start(
#         {
#             "speedup": 40,
#             "msg_count": 10,
#         }
#     )
#     time.sleep(3)
#     unit_cooler.wait_and_term(
#         *unit_cooler.start(
#             {
#                 "speedup": 40,
#                 "dummy_mode": True,
#                 "msg_count": 1,
#             }
#         )
#     )
#     cooler_controller.wait_and_term(*control_handle)

#####################################################################

# def test_fd_q10c(mocker):
#     import sensor.fd_q10c

#     mock_fd_q10c(mocker)

#     sensor.fd_q10c.FD_Q10C().get_value(False)
#     sensor.fd_q10c.FD_Q10C().get_value_map()


# def test_fd_q10c_ping(mocker):
#     import sensor.fd_q10c

#     mock_fd_q10c(mocker, gen_fd_q10c_ser_trans_ping())

#     sensor.fd_q10c.FD_Q10C().ping()


# def test_fd_q10c_stop(mocker):
#     import sensor.fd_q10c

#     mock_fd_q10c(mocker)
#     sensor = sensor.fd_q10c.FD_Q10C()
#     sensor.stop()


# def test_fd_q10c_stop_error_1(mocker):
#     import sensor.fd_q10c

#     mocker.patch("fcntl.flock", side_effect=IOError)

#     mock_fd_q10c(mocker)
#     sensor = sensor.fd_q10c.FD_Q10C()
#     with pytest.raises(RuntimeError):
#         sensor.stop()


# def test_fd_q10c_stop_error_2(mocker):
#     import sensor.fd_q10c

#     mocker.patch("serial.Serial.close", side_effect=IOError)

#     mock_fd_q10c(mocker)
#     sensor = sensor.fd_q10c.FD_Q10C()
#     sensor.stop()

#     sensor.get_value()
#     sensor.stop()


# def test_fd_q10c_short(mocker):
#     import sensor.fd_q10c

#     fd_q10c_ser_trans = gen_fd_q10c_ser_trans_sense()
#     fd_q10c_ser_trans[3]["recv"] = fd_q10c_ser_trans[3]["recv"][0:2]
#     mock_fd_q10c(mocker, fd_q10c_ser_trans)

#     sensor.fd_q10c.FD_Q10C().get_value()


# def test_fd_q10c_checksum(mocker):
#     import sensor.fd_q10c

#     fd_q10c_ser_trans = gen_fd_q10c_ser_trans_sense()
#     fd_q10c_ser_trans[3]["recv"][3] = 0x11
#     mock_fd_q10c(mocker, fd_q10c_ser_trans)

#     sensor.fd_q10c.FD_Q10C().get_value()


# def test_fd_q10c_header_error(mocker):
#     import inspect
#     import sensor.fd_q10c
#     from sensor.ltc2874 import msq_checksum as msq_checksum_orig

#     data_injected = 0xC0
#     fd_q10c_ser_trans = gen_fd_q10c_ser_trans_sense()
#     fd_q10c_ser_trans[3]["recv"][2] = data_injected
#     mock_fd_q10c(mocker, fd_q10c_ser_trans)

#     # NOTE: 特定の関数からの特定の引数での call の際のみ，入れ替える
#     def msq_checksum_mock(data):
#         if (inspect.stack()[4].function == "isdu_res_read") and (
#             data == [data_injected]
#         ):
#             return fd_q10c_ser_trans[3]["recv"][3]
#         else:
#             return msq_checksum_orig(data)

#     mocker.patch("sensor.ltc2874.msq_checksum", side_effect=msq_checksum_mock)

#     mock_fd_q10c(mocker, fd_q10c_ser_trans)

#     sensor.fd_q10c.FD_Q10C().get_value()


# def test_fd_q10c_chk_error(mocker):
#     import inspect
#     import sensor.fd_q10c
#     from sensor.ltc2874 import msq_checksum as msq_checksum_orig

#     data_injected = 0xD3
#     fd_q10c_ser_trans = gen_fd_q10c_ser_trans_sense()
#     fd_q10c_ser_trans[6]["recv"][2] = data_injected
#     mock_fd_q10c(mocker, fd_q10c_ser_trans)

#     # NOTE: 特定の関数からの特定の引数での call の際のみ，入れ替える
#     def msq_checksum_mock(data):
#         if (inspect.stack()[4].function == "isdu_res_read") and (
#             data == [data_injected]
#         ):
#             return fd_q10c_ser_trans[6]["recv"][3]
#         else:
#             return msq_checksum_orig(data)

#     mocker.patch("sensor.ltc2874.msq_checksum", side_effect=msq_checksum_mock)

#     mock_fd_q10c(mocker, fd_q10c_ser_trans)

#     sensor.fd_q10c.FD_Q10C().get_value()


# def test_fd_q10c_header_invalid(mocker):
#     import inspect
#     import sensor.fd_q10c
#     from sensor.ltc2874 import msq_checksum as msq_checksum_orig

#     data_injected = 0x00
#     fd_q10c_ser_trans = gen_fd_q10c_ser_trans_sense()
#     fd_q10c_ser_trans[3]["recv"][2] = data_injected
#     mock_fd_q10c(mocker, fd_q10c_ser_trans)

#     # NOTE: 特定の関数からの特定の引数での call の際のみ，入れ替える
#     def msq_checksum_mock(data):
#         if (inspect.stack()[4].function == "isdu_res_read") and (
#             data == [data_injected]
#         ):
#             return fd_q10c_ser_trans[3]["recv"][3]
#         else:
#             return msq_checksum_orig(data)

#     mocker.patch("sensor.ltc2874.msq_checksum", side_effect=msq_checksum_mock)

#     mock_fd_q10c(mocker, fd_q10c_ser_trans)

#     sensor.fd_q10c.FD_Q10C().get_value()


# def test_fd_q10c_timeout(mocker):
#     import sensor.fd_q10c

#     mock_fd_q10c(mocker)

#     mocker.patch("fcntl.flock", side_effect=IOError())

#     sensor.fd_q10c.FD_Q10C().get_value()


# def test_actuator_restart():
#     import cooler_controller
#     import unit_cooler

#     actuator_handle = unit_cooler.start(
#         {
#             "speedup": 40,
#             "dummy_mode": True,
#             "msg_count": 1,
#         }
#     )
#     control_handle = cooler_controller.start(
#         {
#             "speedup": 40,
#             "msg_count": 6,
#         }
#     )

#     unit_cooler.wait_and_term(*actuator_handle)

#     actuator_handle = unit_cooler.start(
#         {
#             "speedup": 40,
#             "dummy_mode": True,
#             "msg_count": 1,
#         }
#     )
#     unit_cooler.wait_and_term(*actuator_handle)
#     cooler_controller.wait_and_term(*control_handle)


# def test_webapp(mocker):
#     import webapp
#     import cooler_controller
#     import unit_cooler

#     mocker.patch("control.fetch_data", return_value=gen_sensor_data())

#     actuator_handle = unit_cooler.start(
#         {
#             "speedup": 40,
#             "dummy_mode": True,
#             "msg_count": 10,
#         }
#     )

#     app = webapp.create_app({"config_file": CONFIG_FILE, "msg_count": 1})
#     client = app.test_client()

#     response = client.get("/unit_cooler/api/log_view")
#     assert response.status_code == 200

#     response = client.get("/unit_cooler/api/memory")
#     assert response.status_code == 200
#     assert "memory" in response.json

#     response = client.get("/unit_cooler/api/snapshot")
#     assert response.status_code == 200
#     assert "msg" in response.json

#     response = client.get("/unit_cooler/api/snapshot")
#     assert response.status_code == 200
#     assert "msg" not in response.json

#     # response = client.get("/unit_cooler/api/sysinfo")
#     # assert response.status_code == 200
#     # assert "date" not in response.json
#     # assert "uptime" not in response.json
#     # assert "loadAverage" not in response.json

#     response = client.get(
#         "/unit_cooler/api/stat",
#         query_string={
#             "cmd": "clear",
#         },
#     )
#     assert response.status_code == 200
#     # assert "watering" not in response.json
#     # assert "sensor" not in response.json
#     # assert "mode" not in response.json
#     # assert "cooler_status" not in response.json
#     # assert "outdoor_status" not in response.json

#     control_handle = cooler_controller.start(
#         {
#             "speedup": 40,
#             "dummy_mode": True,
#             "msg_count": 20,
#         }
#     )

#     import logging

#     logging.error("X")
#     response = client.get("/unit_cooler/api/event", query_string={"count": "2"})
#     logging.error("Y")
#     assert response.status_code == 200
#     logging.error("Z")

#     # assert response.data.decode()
#     logging.error("A")
#     client.delete()
#     logging.error("B")
#     unit_cooler.wait_and_term(*actuator_handle)
#     logging.error("C")
#     cooler_controller.wait_and_term(*control_handle)


def test_terminate():
    # webapp.term()
    pass
