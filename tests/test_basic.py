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
def clear():
    with mock.patch.dict("os.environ", {"DUMMY_MODE": "true"}) as fixture:
        import actuator
        import valve
        import control
        from config import load_config

        config = load_config(CONFIG_FILE)

        for name in ["controller", "actuator", "monitor", "receiver", "web"]:
            pathlib.Path(config[name]["liveness"]["file"]).unlink(missing_ok=True)

        actuator.clear_hazard(config)
        control.clear_hist()
        valve.clear_stat()

        yield fixture


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


def check_healthz(name):
    from config import load_config

    healthz_file = pathlib.Path(load_config(CONFIG_FILE)[name]["liveness"]["file"])

    if healthz_file.exists():
        return healthz_file.stat().st_mtime
    else:
        return None


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
    import control

    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    cooler_controller.wait_and_term(
        *cooler_controller.start(
            {
                "speedup": 40,
                "msg_count": 1,
            }
        )
    )

    assert control.get_error_hist() == []
    assert check_healthz("controller") is not None


def test_controller_start_error_1(mocker):
    import cooler_controller
    import control
    from threading import Thread as Thread_orig

    def thread_mock(
        group=None, target=None, name=None, args=(), kwargs={}, *, daemon=None
    ):
        thread_mock.i += 1
        if thread_mock.i == 1:
            raise RuntimeError()
        else:
            return Thread_orig(target=target, args=args)

    thread_mock.i = 0

    mocker.patch("threading.Thread", new=thread_mock)

    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    cooler_controller.wait_and_term(
        *cooler_controller.start(
            {
                "speedup": 40,
                "msg_count": 1,
            }
        )
    )

    assert control.get_error_hist() == []
    assert check_healthz("controller") is None


def test_controller_start_error_2(mocker):
    import control
    import cooler_controller
    from threading import Thread as Thread_orig

    def thread_mock(
        group=None, target=None, name=None, args=(), kwargs={}, *, daemon=None
    ):
        thread_mock.i += 1
        if thread_mock.i == 2:
            raise RuntimeError()
        else:
            return Thread_orig(target=target, args=args)

    thread_mock.i = 0

    mocker.patch("threading.Thread", new=thread_mock)
    # mocker.patch("threading.Thread.__init__", new=thread_mock)

    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    cooler_controller.wait_and_term(
        *cooler_controller.start(
            {
                "speedup": 40,
                "msg_count": 1,
            }
        )
    )

    assert control.get_error_hist() == []
    # NOTE: 現状，Proxy のエラーの場合，controller としては healthz は正常になる
    assert check_healthz("controller") is not None


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

    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler
    import control

    mock_gpio(mocker)
    mock_fd_q10c(mocker)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    actuator_handle = unit_cooler.start(
        {
            "speedup": 40,
            "dummy_mode": True,
            "msg_count": 2,
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
                backoff_factor=10,
            )
        ),
    )
    res = requests.get("http://localhost:5001/unit_cooler/api/log_view")
    assert res.status_code == 200
    assert "data" in json.loads(res.text)
    assert len(json.loads(res.text)["data"]) != 0
    assert "last_time" in json.loads(res.text)

    res = requests.get("http://localhost:5001/unit_cooler/api/log_clear")
    assert res.status_code == 200
    assert json.loads(res.text)["result"] == "success"

    res = requests.get("http://localhost:5001/unit_cooler/api/log_view")
    assert res.status_code == 200
    assert "data" in json.loads(res.text)
    assert len(json.loads(res.text)["data"]) == 0
    assert "last_time" in json.loads(res.text)

    res = requests.get(
        "http://localhost:5001/unit_cooler/api/event",
        params={"count": "1"},
    )
    assert res.status_code == 200
    assert res.text.strip() == "data: log"

    unit_cooler.wait_and_term(*actuator_handle)
    cooler_controller.wait_and_term(*control_handle)
    assert control.get_error_hist() == []


# def test_actuator_signal(mocker):
#     import signal

#     # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
#     mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

#     import cooler_controller
#     import unit_cooler

#     mock_gpio(mocker)
#     mock_fd_q10c(mocker)
#     mocker.patch("control.fetch_data", return_value=gen_sensor_data())

#     # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
#     mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

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
#             "dummy_mode": True,
#             "msg_count": 5,
#         }
#     )

#     unit_cooler.sig_handler(signal.SIGTERM, None)

#     unit_cooler.wait_and_term(*actuator_handle)
#     cooler_controller.wait_and_term(*control_handle)


# def test_actuator_recv_error(mocker):
#     # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
#     mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

#     import cooler_controller
#     import unit_cooler
#     from control_pubsub import start_client as start_client_orig

#     mock_gpio(mocker)
#     mock_fd_q10c(mocker)
#     mocker.patch("control.fetch_data", return_value=gen_sensor_data())

#     def start_client_mock(server_host, server_port, func, msg_count=0):
#         start_client_orig(server_host, server_port, func, msg_count)
#         raise RuntimeError()

#     mocker.patch("control_pubsub.start_client", side_effect=start_client_mock)

#     # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
#     mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

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
#             "dummy_mode": True,
#             "msg_count": 10,
#         }
#     )
#     time.sleep(3)

#     unit_cooler.wait_and_term(*actuator_handle)
#     cooler_controller.wait_and_term(*control_handle)


def test_actuator_iolink_short(mocker):

    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler
    import control
    import sensor.fd_q10c

    mock_gpio(mocker)

    # NOTE: 流量計の故障モードを代表して，unit_cooler に対してテスト
    fd_q10c_ser_trans = gen_fd_q10c_ser_trans_sense()
    fd_q10c_ser_trans[3]["recv"] = fd_q10c_ser_trans[3]["recv"][0:2]
    mock_fd_q10c(mocker, fd_q10c_ser_trans)
    sensor.fd_q10c.FD_Q10C().get_value()

    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    actuator_handle = unit_cooler.start(
        {
            "speedup": 40,
            "dummy_mode": True,
            "msg_count": 2,
        }
    )

    control_handle = cooler_controller.start(
        {
            "speedup": 40,
            "dummy_mode": True,
            "msg_count": 10,
        }
    )

    unit_cooler.wait_and_term(*actuator_handle)
    cooler_controller.wait_and_term(*control_handle)
    assert control.get_error_hist() == []


#####################################################################


def test_fd_q10c(mocker):
    import sensor.fd_q10c

    mock_fd_q10c(mocker)

    sensor.fd_q10c.FD_Q10C().get_value(False)
    sensor.fd_q10c.FD_Q10C().get_value_map()


def test_fd_q10c_ping(mocker):
    import sensor.fd_q10c

    mock_fd_q10c(mocker, gen_fd_q10c_ser_trans_ping())

    sensor.fd_q10c.FD_Q10C().ping()


def test_fd_q10c_stop(mocker):
    import sensor.fd_q10c

    mock_fd_q10c(mocker)
    sensor = sensor.fd_q10c.FD_Q10C()
    sensor.stop()


def test_fd_q10c_stop_error_1(mocker):
    import sensor.fd_q10c

    mocker.patch("fcntl.flock", side_effect=IOError)

    mock_fd_q10c(mocker)
    sensor = sensor.fd_q10c.FD_Q10C()
    with pytest.raises(RuntimeError):
        sensor.stop()


def test_fd_q10c_stop_error_2(mocker):
    import sensor.fd_q10c

    mocker.patch("serial.Serial.close", side_effect=IOError)

    mock_fd_q10c(mocker)
    sensor = sensor.fd_q10c.FD_Q10C()
    sensor.stop()

    sensor.get_value()
    sensor.stop()


def test_fd_q10c_short(mocker):
    import sensor.fd_q10c

    fd_q10c_ser_trans = gen_fd_q10c_ser_trans_sense()
    fd_q10c_ser_trans[3]["recv"] = fd_q10c_ser_trans[3]["recv"][0:2]
    mock_fd_q10c(mocker, fd_q10c_ser_trans)

    sensor.fd_q10c.FD_Q10C().get_value()


def test_fd_q10c_checksum(mocker):
    import sensor.fd_q10c

    fd_q10c_ser_trans = gen_fd_q10c_ser_trans_sense()
    fd_q10c_ser_trans[3]["recv"][3] = 0x11
    mock_fd_q10c(mocker, fd_q10c_ser_trans)

    sensor.fd_q10c.FD_Q10C().get_value()


def test_fd_q10c_header_error(mocker):
    import inspect
    import sensor.fd_q10c
    from sensor.ltc2874 import msq_checksum as msq_checksum_orig

    data_injected = 0xC0
    fd_q10c_ser_trans = gen_fd_q10c_ser_trans_sense()
    fd_q10c_ser_trans[3]["recv"][2] = data_injected
    mock_fd_q10c(mocker, fd_q10c_ser_trans)

    # NOTE: 特定の関数からの特定の引数での call の際のみ，入れ替える
    def msq_checksum_mock(data):
        if (inspect.stack()[4].function == "isdu_res_read") and (
            data == [data_injected]
        ):
            return fd_q10c_ser_trans[3]["recv"][3]
        else:
            return msq_checksum_orig(data)

    mocker.patch("sensor.ltc2874.msq_checksum", side_effect=msq_checksum_mock)

    mock_fd_q10c(mocker, fd_q10c_ser_trans)

    sensor.fd_q10c.FD_Q10C().get_value()


def test_fd_q10c_chk_error(mocker):
    import inspect
    import sensor.fd_q10c
    from sensor.ltc2874 import msq_checksum as msq_checksum_orig

    data_injected = 0xD3
    fd_q10c_ser_trans = gen_fd_q10c_ser_trans_sense()
    fd_q10c_ser_trans[6]["recv"][2] = data_injected
    mock_fd_q10c(mocker, fd_q10c_ser_trans)

    # NOTE: 特定の関数からの特定の引数での call の際のみ，入れ替える
    def msq_checksum_mock(data):
        if (inspect.stack()[4].function == "isdu_res_read") and (
            data == [data_injected]
        ):
            return fd_q10c_ser_trans[6]["recv"][3]
        else:
            return msq_checksum_orig(data)

    mocker.patch("sensor.ltc2874.msq_checksum", side_effect=msq_checksum_mock)

    mock_fd_q10c(mocker, fd_q10c_ser_trans)

    sensor.fd_q10c.FD_Q10C().get_value()


def test_fd_q10c_header_invalid(mocker):
    import inspect
    import sensor.fd_q10c
    from sensor.ltc2874 import msq_checksum as msq_checksum_orig

    data_injected = 0x00
    fd_q10c_ser_trans = gen_fd_q10c_ser_trans_sense()
    fd_q10c_ser_trans[3]["recv"][2] = data_injected
    mock_fd_q10c(mocker, fd_q10c_ser_trans)

    # NOTE: 特定の関数からの特定の引数での call の際のみ，入れ替える
    def msq_checksum_mock(data):
        if (inspect.stack()[4].function == "isdu_res_read") and (
            data == [data_injected]
        ):
            return fd_q10c_ser_trans[3]["recv"][3]
        else:
            return msq_checksum_orig(data)

    mocker.patch("sensor.ltc2874.msq_checksum", side_effect=msq_checksum_mock)

    mock_fd_q10c(mocker, fd_q10c_ser_trans)

    sensor.fd_q10c.FD_Q10C().get_value()


def test_fd_q10c_timeout(mocker):
    import sensor.fd_q10c

    mock_fd_q10c(mocker)

    mocker.patch("fcntl.flock", side_effect=IOError())

    sensor.fd_q10c.FD_Q10C().get_value()


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


def test_webapp(mocker):
    import requests
    import webapp
    import webapp_event
    import cooler_controller
    import unit_cooler

    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    actuator_handle = unit_cooler.start(
        {
            "speedup": 40,
            "dummy_mode": True,
            "msg_count": 5,
        }
    )
    control_handle = cooler_controller.start(
        {
            "speedup": 40,
            "dummy_mode": True,
            "msg_count": 15,
        }
    )

    app = webapp.create_app({"config_file": CONFIG_FILE, "msg_count": 1})
    client = app.test_client()

    response = client.get("/")
    assert response.status_code == 302
    assert re.search(r"/unit_cooler/$", response.location)

    response = client.get("/unit_cooler/")
    assert response.status_code == 200
    assert "室外機" in response.data.decode("utf-8")

    response = client.get("/unit_cooler/api/log_view")
    assert response.status_code == 200
    assert "data" in response.json
    assert len(response.json["data"]) != 0
    assert "last_time" in response.json

    response = client.get("/unit_cooler/api/memory")
    assert response.status_code == 200
    assert "memory" in response.json

    response = client.get("/unit_cooler/api/snapshot")
    assert response.status_code == 200
    assert "msg" in response.json

    response = client.get("/unit_cooler/api/snapshot")
    assert response.status_code == 200
    assert "msg" not in response.json

    response = client.get("/unit_cooler/api/sysinfo")
    assert response.status_code == 200
    assert "date" in response.json
    assert "uptime" in response.json
    assert "loadAverage" in response.json

    response = client.get(
        "/unit_cooler/api/stat",
        query_string={
            "cmd": "clear",
        },
    )
    assert response.status_code == 200
    assert "watering" in response.json
    assert "sensor" in response.json
    assert "mode" in response.json
    assert "cooler_status" in response.json
    assert "outdoor_status" in response.json

    response = client.get("/unit_cooler/api/event", query_string={"count": "2"})
    assert response.status_code == 200
    assert response.data.decode()

    response = requests.models.Response()
    response.status_code = 500
    mocker.patch("webapp_log_proxy.requests.get", return_value=response)

    # NOTE: mock を戻す手間を避けるため，最後に実施
    response = client.get("/unit_cooler/api/log_view")
    assert response.status_code == 200
    assert "data" in response.json
    assert len(response.json["data"]) == 0
    assert "last_time" in response.json

    client.delete()

    unit_cooler.wait_and_term(*actuator_handle)
    cooler_controller.wait_and_term(*control_handle)

    # NOTE: カバレッジのため
    webapp_event.stop_watch()


def test_terminate():
    # webapp.term()
    pass
