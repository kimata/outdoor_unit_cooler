#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import pathlib
import pytest
import time
import re
import json
import datetime
from unittest import mock
import logging

sys.path.append(str(pathlib.Path(__file__).parent.parent / "app"))
sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

CONFIG_FILE = "config.example.yaml"

import notify_slack
import work_log


@pytest.fixture(scope="function", autouse=True)
def env_mock():
    with mock.patch.dict(
        "os.environ",
        {
            "TEST": "true",
            "NO_COLORED_LOGS": "true",
        },
    ) as fixture:
        yield fixture


@pytest.fixture(scope="function", autouse=True)
def clear():
    with mock.patch.dict("os.environ", {"DUMMY_MODE": "true"}) as fixture:
        import actuator
        import valve
        import work_log
        from config import load_config

    config = load_config(CONFIG_FILE)

    for name in ["controller", "receiver", "actuator", "monitor", "web"]:
        pathlib.Path(config[name]["liveness"]["file"]).unlink(missing_ok=True)

    actuator.clear_hazard(config)
    valve.clear_stat()
    notify_slack.clear_interval()
    work_log.clear_hist()
    notify_slack.clear_hist()


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


def time_test(offset_min=0, offset_hour=0):
    return datetime.datetime.now().replace(
        hour=offset_hour, minute=offset_min, second=0
    )


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


def gen_fd_q10c_ser_trans_sense(is_zero=False):
    # NOTE: send/recv はプログラム視点．SPI デバイスが送信すべき内容が recv．
    if is_zero:
        return [
            {"send": [0x70, 0x09, 0x93], "recv": [0x70, 0x09, 0x93, 0x2D]},
            {"send": [0x61, 0x2E, 0x94], "recv": [0x61, 0x2E, 0x94, 0x2D]},
            {"send": [0x62, 0x12, 0x07], "recv": [0x62, 0x12, 0x07, 0x2D]},
            {"send": [0xF0, 0x2D], "recv": [0xF0, 0x2D, 0xD4, 0x1B]},
            {"send": [0xE1, 0x28], "recv": [0xE1, 0x28, 0x00, 0x2D]},
            {"send": [0xE2, 0x18], "recv": [0xE2, 0x18, 0x00, 0x2D]},
            {"send": [0xE3, 0x09], "recv": [0xE3, 0x09, 0xD4, 0x1B]},
        ]
    else:
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


def check_healthz(name, is_healthy):
    from config import load_config

    healthz_file = pathlib.Path(load_config(CONFIG_FILE)[name]["liveness"]["file"])

    assert healthz_file.exists() == is_healthy, "{name} の healthz が存在しま{state}．".format(
        name=name, state="せん" if is_healthy else "す"
    )


def check_notify_slack(message):
    if message is None:
        assert notify_slack.get_hist() == [], "正常なはずなのに，エラー通知がされています．"
    else:
        assert (
            notify_slack.get_hist()[-1].find(message) != -1
        ), "「{message}」が Slack で通知されていません．".format(message=message)


def mock_fd_q10c(
    mocker, ser_trans=gen_fd_q10c_ser_trans_sense(), count=0, spi_read=0x00
):
    import struct
    import sensor.fd_q10c

    spidev_mock = mocker.MagicMock()
    spidev_mock.xfer2.return_value = [0x00, spi_read]
    mocker.patch("spidev.SpiDev", return_value=spidev_mock)

    def ser_read_mock(length):
        ser_read_mock.i += 1

        if ser_read_mock.i == count:
            raise RuntimeError()
        for trans in ser_trans:
            if trans["send"] == ser_read_mock.write_data:
                return struct.pack("B" * len(trans["recv"]), *trans["recv"])

        logging.warning("Unknown serial transfer")
        return None

    ser_read_mock.i = 0

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

    gpio_input_mock.data = [0 for i in range(32)]

    gpio_mock.output.side_effect = gpio_output_mock
    gpio_mock.input.side_effect = gpio_input_mock

    mocker.patch("valve.GPIO", new=gpio_mock)


######################################################################
def test_controller(mocker):
    import cooler_controller

    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    cooler_controller.wait_and_term(
        *cooler_controller.start(
            {
                "config_file": CONFIG_FILE,
                "disable_proxy": True,  # NOTE: subscriber がいないので，proxy を無効化
                "speedup": 100,
                "msg_count": 1,
            }
        )
    )

    check_healthz("controller", True)
    check_healthz("receiver", False)
    check_healthz("actuator", False)
    check_healthz("monitor", False)
    check_notify_slack(None)


def test_controller_influxdb_dummy(mocker):
    import cooler_controller

    def value_mock():
        value_mock.i += 1
        if value_mock.i == 1:
            return None
        else:
            return 1

    value_mock.i = 0

    table_entry_mock = mocker.MagicMock()
    record_mock = mocker.MagicMock()
    query_api_mock = mocker.MagicMock()
    mocker.patch.object(record_mock, "get_statu", return_value=True)
    mocker.patch.object(
        record_mock,
        "get_value",
        side_effect=value_mock,
    )
    mocker.patch.object(
        record_mock,
        "get_time",
        return_value=datetime.datetime.now(datetime.timezone.utc),
    )
    table_entry_mock.__iter__.return_value = [record_mock, record_mock]
    type(table_entry_mock).records = table_entry_mock
    query_api_mock.query.return_value = [table_entry_mock]
    mocker.patch(
        "influxdb_client.InfluxDBClient.query_api",
        return_value=query_api_mock,
    )

    cooler_controller.wait_and_term(
        *cooler_controller.start(
            {
                "config_file": CONFIG_FILE,
                "disable_proxy": True,  # NOTE: subscriber がいないので，proxy を無効化
                "speedup": 100,
                "msg_count": 1,
            }
        )
    )

    check_healthz("controller", True)
    check_healthz("receiver", False)
    check_healthz("actuator", False)
    check_healthz("monitor", False)
    check_notify_slack(None)


def test_controller_start_error_1(mocker):
    import cooler_controller
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
                "config_file": CONFIG_FILE,
                "disable_proxy": True,  # NOTE: subscriber がいないので，proxy を無効化
                "speedup": 100,
                "msg_count": 1,
            }
        )
    )

    check_healthz("controller", False)
    check_healthz("actuator", False)
    check_healthz("monitor", False)
    check_healthz("receiver", False)
    check_notify_slack("Traceback")


def test_controller_start_error_2(mocker):
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

    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    cooler_controller.wait_and_term(
        *cooler_controller.start(
            {
                "config_file": CONFIG_FILE,
                "disable_proxy": False,  # NOTE: Proxy をエラーにするテストなので動かして OK
                "speedup": 100,
                "msg_count": 1,
            }
        )
    )

    # NOTE: 現状，Proxy のエラーの場合，controller としては healthz は正常になる
    check_healthz("controller", True)
    check_healthz("receiver", False)
    check_healthz("actuator", False)
    check_healthz("monitor", False)
    check_notify_slack("Traceback")


def test_controller_influxdb_error(mocker):
    import cooler_controller

    mocker.patch("influxdb_client.InfluxDBClient.query_api", side_effect=RuntimeError())

    cooler_controller.wait_and_term(
        *cooler_controller.start(
            {
                "config_file": CONFIG_FILE,
                "disable_proxy": True,
                "speedup": 100,
                "msg_count": 1,
            }
        )
    )

    check_healthz("controller", True)
    check_healthz("receiver", False)
    check_healthz("actuator", False)
    check_healthz("monitor", False)
    check_notify_slack("エアコン動作モードを判断できません．")


def test_controller_outdoor_normal(mocker):
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
            return gen_sensor_data([25])
        elif field == "power":
            return gen_sensor_data([100])
        elif field == "lux":
            return gen_sensor_data([500])
        elif field == "solar_rad":
            return gen_sensor_data([300])
        else:
            return gen_sensor_data([30])

    mocker.patch("control.fetch_data", side_effect=fetch_data_mock)

    cooler_controller.wait_and_term(
        *cooler_controller.start(
            {
                "config_file": CONFIG_FILE,
                "disable_proxy": True,  # NOTE: subscriber がいないので，proxy を無効化
                "speedup": 100,
                "msg_count": 1,
            }
        )
    )

    check_healthz("controller", True)
    check_healthz("receiver", False)
    check_healthz("actuator", False)
    check_healthz("monitor", False)
    check_notify_slack(None)


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
        if field == "temp":
            return gen_sensor_data([30])
        elif field == "power":
            fetch_data_mock.i += 1
            if (fetch_data_mock.i % 5) == 0:
                return gen_sensor_data([0])
            elif (fetch_data_mock.i % 5) == 1:
                return gen_sensor_data([10])
            elif (fetch_data_mock.i % 5) == 2:
                return gen_sensor_data([50])
            elif (fetch_data_mock.i % 5) == 3:
                return gen_sensor_data([600])
            else:
                return gen_sensor_data([1100])
        else:
            return gen_sensor_data([30])

    fetch_data_mock.i = 0

    mocker.patch("control.fetch_data", side_effect=fetch_data_mock)

    cooler_controller.wait_and_term(
        *cooler_controller.start(
            {
                "config_file": CONFIG_FILE,
                "disable_proxy": True,  # NOTE: subscriber がいないので，proxy を無効化
                "speedup": 100,
                "msg_count": 1,
            }
        )
    )

    check_healthz("controller", True)
    check_healthz("receiver", False)
    check_healthz("actuator", False)
    check_healthz("monitor", False)
    check_notify_slack(None)


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
                "config_file": CONFIG_FILE,
                "disable_proxy": True,  # NOTE: subscriber がいないので，proxy を無効化
                "speedup": 100,
                "msg_count": 1,
            }
        )
    )

    check_healthz("controller", True)
    check_healthz("receiver", False)
    check_healthz("actuator", False)
    check_healthz("monitor", False)
    check_notify_slack("データを取得できませんでした．")


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
                "config_file": CONFIG_FILE,
                "disable_proxy": True,  # NOTE: subscriber がいないので，proxy を無効化
                "speedup": 100,
                "msg_count": 1,
            }
        )
    )

    check_healthz("controller", True)
    check_healthz("receiver", False)
    check_healthz("actuator", False)
    check_healthz("monitor", False)
    check_notify_slack("エアコン動作モードを判断できません．")


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
                "config_file": CONFIG_FILE,
                "disable_proxy": True,  # NOTE: subscriber がいないので，proxy を無効化
                "speedup": 100,
                "msg_count": 1,
            }
        )
    )

    check_healthz("controller", True)
    check_healthz("receiver", False)
    check_healthz("actuator", False)
    check_healthz("monitor", False)
    check_notify_slack(None)


def test_test_client(mocker):
    import cooler_controller

    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "dummy_mode": True,
            "speedup": 100,
            "msg_count": 5,
        }
    )
    cooler_controller.start({"config_file": CONFIG_FILE, "client_mode": True})

    cooler_controller.wait_and_term(*control_handle)

    check_healthz("controller", True)
    check_healthz("receiver", False)
    check_healthz("actuator", False)
    check_healthz("monitor", False)
    check_notify_slack(None)


def test_controller_sensor_error(mocker):
    import cooler_controller

    mocker.patch("influxdb_client.InfluxDBClient.query_api", side_effect=RuntimeError())

    cooler_controller.wait_and_term(
        *cooler_controller.start(
            {
                "config_file": CONFIG_FILE,
                "disable_proxy": True,  # NOTE: subscriber がいないので，proxy を無効化
                "speedup": 100,
                "msg_count": 1,
            }
        )
    )

    check_healthz("controller", True)
    check_healthz("receiver", False)
    check_healthz("actuator", False)
    check_healthz("monitor", False)
    check_notify_slack("エアコン動作モードを判断できません．")


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
        *cooler_controller.start(
            {
                "config_file": CONFIG_FILE,
                "disable_proxy": True,  # NOTE: subscriber がいないので，proxy を無効化
                "speedup": 100,
                "msg_count": 1,
                "dummy_mode": True,
            }
        )
    )

    check_healthz("controller", True)
    check_healthz("receiver", False)
    check_healthz("actuator", False)
    check_healthz("monitor", False)
    check_notify_slack(None)


def test_controller_view_msg():
    import cooler_controller

    cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "view_msg_mode": True,
        }
    )
    check_notify_slack(None)


def test_actuator(mocker):
    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler

    mock_gpio(mocker)
    mock_fd_q10c(mocker)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})
    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 1,
        }
    )
    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 1,
        }
    )

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    check_notify_slack(None)


def test_actuator_normal(mocker):
    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler
    import control_config

    mock_gpio(mocker)
    mock_fd_q10c(mocker)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    mocker.patch(
        "control.dummy_control_mode",
        return_value={"control_mode": len(control_config.MESSAGE_LIST) - 1},
    )

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})
    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 20,
            "msg_count": 5,
        }
    )
    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 20,
            "dummy_mode": True,
            "msg_count": 5,
        }
    )

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    check_notify_slack(None)


def test_actuator_duty_disable(mocker):
    import copy

    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler
    import control
    import control_config
    from control_config import MESSAGE_LIST as MESSAGE_LIST_orig

    mock_gpio(mocker)
    mock_fd_q10c(mocker)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    mocker.patch(
        "control.dummy_control_mode",
        return_value={"control_mode": len(control_config.MESSAGE_LIST) - 1},
    )

    message_list_orig = copy.deepcopy(MESSAGE_LIST_orig)
    message_list_orig[-1]["duty"]["enable"] = False
    mocker.patch.object(control, "MESSAGE_LIST", message_list_orig)

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})
    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 5,
        }
    )
    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 5,
        }
    )

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    check_notify_slack(None)


def test_actuator_log(mocker):
    import requests

    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler

    mock_gpio(mocker)
    mock_fd_q10c(mocker)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 5,
        }
    )

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 5,
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

    # NOTE: ログが記録されるまで待つ
    time.sleep(3)

    res = requests.get(
        "http://localhost:5001/unit_cooler/api/log_view",
        headers={"Accept-Encoding": "gzip"},
    )
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
        "http://localhost:5001/unit_cooler/api/log_view",
        headers={"Accept-Encoding": "gzip"},
        params={
            "callback": "TEST",
        },
    )
    assert res.status_code == 200
    assert res.text.find("TEST(") == 0

    res = requests.get(
        "http://localhost:5001/unit_cooler/api/event",
        params={"count": "1"},
    )
    assert res.status_code == 200
    assert res.text.strip() == "data: log"

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    check_notify_slack(None)


def test_actuator_send_error(mocker):
    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler

    mock_gpio(mocker)
    mock_fd_q10c(mocker)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    mocker.patch("fluent.sender.FluentSender", new=RuntimeError())

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 1,
        }
    )

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 1,
        }
    )

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", False)
    check_notify_slack("流量のロギングを開始できません．")


def test_actuator_mode_const(mocker):
    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler

    mock_gpio(mocker)
    mock_fd_q10c(mocker)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())
    mocker.patch("control.dummy_control_mode", return_value={"control_mode": 1})

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 1,
        }
    )

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 1,
        }
    )

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    check_notify_slack(None)


def test_actuator_power_off_1(mocker, freezer):
    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler

    mock_gpio(mocker)
    mocker.patch("valve.get_flow", return_value=0)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    def dummy_mode_mock():
        dummy_mode_mock.i += 1
        if dummy_mode_mock.i <= 1:
            return {"control_mode": 1}
        else:
            return {"control_mode": 0}

    dummy_mode_mock.i = 0

    mocker.patch("control.dummy_control_mode", side_effect=dummy_mode_mock)

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    freezer.move_to(time_test(0))

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 10,
        }
    )

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 10,
        }
    )

    time.sleep(2)
    freezer.move_to(time_test(5))
    time.sleep(1)
    freezer.move_to(time_test(10))
    time.sleep(1)
    freezer.move_to(time_test(0, 3))

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    # NOTE: タイミング次第でエラーが記録されるので notify_slack はチェックしない
    # assert notify_slack.get_hist() == []
    assert work_log.get_hist()[-1].find("長い間バルブが閉じられていますので，流量計の電源を OFF します．") == 0


def test_actuator_power_off_2(mocker, freezer):
    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler

    mock_gpio(mocker)
    mock_fd_q10c(mocker, gen_fd_q10c_ser_trans_sense(True))

    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    def dummy_mode_mock():
        dummy_mode_mock.i += 1
        if dummy_mode_mock.i <= 1:
            return {"control_mode": 1}
        else:
            return {"control_mode": 0}

    dummy_mode_mock.i = 0

    mocker.patch("control.dummy_control_mode", side_effect=dummy_mode_mock)
    mocker.patch("valve.FD_Q10C.stop", side_effect=RuntimeError())

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    freezer.move_to(time_test(0))

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 5,
        }
    )

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 5,
        }
    )

    time.sleep(2)
    freezer.move_to(time_test(5))
    time.sleep(1)
    freezer.move_to(time_test(10))
    time.sleep(1)
    freezer.move_to(time_test(0, 3))
    time.sleep(1)
    freezer.move_to(time_test(5, 3))

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    # NOTE: エラーが発生していなければ OK


def test_actuator_fd_q10c_stop_error(mocker, freezer):
    import inspect

    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler

    mock_gpio(mocker)
    mock_fd_q10c(mocker, gen_fd_q10c_ser_trans_sense(True))

    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    def dummy_mode_mock():
        dummy_mode_mock.i += 1
        if dummy_mode_mock.i <= 1:
            return {"control_mode": 1}
        else:
            return {"control_mode": 0}

    dummy_mode_mock.i = 0

    mocker.patch("control.dummy_control_mode", side_effect=dummy_mode_mock)

    def com_stop_mock(spi, ser=None, is_power_off=False):
        if inspect.stack()[4].function == "stop":
            raise RuntimeError()
        else:
            return True

    mocker.patch("sensor.ltc2874.com_stop", side_effect=com_stop_mock)

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    freezer.move_to(time_test(0))

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 5,
        }
    )

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 5,
        }
    )

    time.sleep(2)
    freezer.move_to(time_test(5))
    time.sleep(1)
    freezer.move_to(time_test(10))
    time.sleep(1)
    freezer.move_to(time_test(0, 3))
    time.sleep(1)
    freezer.move_to(time_test(5, 3))

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    # NOTE: エラーが発生していなければ OK


def test_actuator_fd_q10c_get_state_error(mocker, freezer):
    import inspect

    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler

    mock_gpio(mocker)
    mock_fd_q10c(mocker, gen_fd_q10c_ser_trans_sense(True))

    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    def dummy_mode_mock():
        dummy_mode_mock.i += 1
        if dummy_mode_mock.i <= 1:
            return {"control_mode": 1}
        else:
            return {"control_mode": 0}

    dummy_mode_mock.i = 0

    mocker.patch("control.dummy_control_mode", side_effect=dummy_mode_mock)

    def com_status_mock(spi):
        if inspect.stack()[4].function == "get_state":
            raise RuntimeError()
        else:
            return True

    mocker.patch("sensor.ltc2874.com_status", side_effect=com_status_mock)

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    freezer.move_to(time_test(0))

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 5,
        }
    )

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 5,
        }
    )

    time.sleep(2)
    freezer.move_to(time_test(5))
    time.sleep(1)
    freezer.move_to(time_test(10))
    time.sleep(1)
    freezer.move_to(time_test(0, 3))
    time.sleep(1)
    freezer.move_to(time_test(5, 3))

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    # NOTE: エラーが発生していなければ OK


def test_actuator_no_test(mocker):
    import signal

    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler

    mock_gpio(mocker)
    mock_fd_q10c(mocker)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    mocker.patch.dict("os.environ", {"TEST": "false"})

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 2,
        }
    )

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 2,
        }
    )

    time.sleep(1)

    # NOTE: signal のテストもついでにやっておく
    unit_cooler.sig_handler(signal.SIGKILL, None)
    unit_cooler.sig_handler(signal.SIGTERM, None)

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    # NOTE: 正常終了すれば OK


def test_actuator_unable_to_receive(mocker, freezer):
    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler

    mock_gpio(mocker)
    mocker.patch("valve.get_flow", return_value=0)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    freezer.move_to(time_test(0))

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 1,
        }
    )

    time.sleep(2)
    freezer.move_to(time_test(20))

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 1,
        }
    )

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    check_notify_slack("冷却モードの指示を受信できません．")


def test_actuator_open(mocker, freezer):
    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler

    mock_gpio(mocker)
    mock_fd_q10c(mocker)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    mocker.patch("control.dummy_control_mode", return_value={"control_mode": 0})

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    freezer.move_to(time_test(0))

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 10,
        }
    )

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 10,
        }
    )
    time.sleep(1)
    freezer.move_to(time_test(10))
    time.sleep(1)
    freezer.move_to(time_test(20))
    time.sleep(1)
    freezer.move_to(time_test(30))

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    check_notify_slack("電磁弁が壊れていますので制御を停止します．")


def test_actuator_flow_unknown_1(mocker):
    import copy

    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler
    import control_config
    import control
    from control_config import MESSAGE_LIST as MESSAGE_LIST_orig

    mock_gpio(mocker)
    mocker.patch("valve.get_flow", return_value=None)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())
    mocker.patch(
        "control.dummy_control_mode",
        return_value={"control_mode": len(control_config.MESSAGE_LIST) - 1},
    )

    message_list_orig = copy.deepcopy(MESSAGE_LIST_orig)
    message_list_orig[-1]["duty"]["on_sec"] = 100000
    mocker.patch.object(control, "MESSAGE_LIST", message_list_orig)

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 15,
        }
    )

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 15,
        }
    )

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    check_notify_slack("流量計が使えません．")


def test_actuator_flow_unknown_2(mocker):
    import copy

    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler
    import control_config
    import control
    from control_config import MESSAGE_LIST as MESSAGE_LIST_orig

    mock_gpio(mocker)
    mocker.patch("valve.FD_Q10C.get_value", side_effect=RuntimeError)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())
    mocker.patch(
        "control.dummy_control_mode",
        return_value={"control_mode": len(control_config.MESSAGE_LIST) - 1},
    )

    message_list_orig = copy.deepcopy(MESSAGE_LIST_orig)
    message_list_orig[-1]["duty"]["on_sec"] = 100000
    mocker.patch.object(control, "MESSAGE_LIST", message_list_orig)

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 15,
        }
    )

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 15,
        }
    )

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    check_notify_slack("流量計が使えません．")


def test_actuator_leak(mocker, freezer):
    import copy

    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler
    import control_config
    import control
    from control_config import MESSAGE_LIST as MESSAGE_LIST_orig

    mock_gpio(mocker)
    mocker.patch("valve.get_flow", return_value=10)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())
    mocker.patch(
        "control.dummy_control_mode",
        return_value={"control_mode": len(control_config.MESSAGE_LIST) - 1},
    )

    message_list_orig = copy.deepcopy(MESSAGE_LIST_orig)
    message_list_orig[-1]["duty"]["on_sec"] = 1000000
    mocker.patch.object(control, "MESSAGE_LIST", message_list_orig)

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    freezer.move_to(time_test(0))

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 10,
        }
    )
    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 10,
        }
    )

    time.sleep(2)
    freezer.move_to(time_test(1))
    time.sleep(2)
    freezer.move_to(time_test(2))
    time.sleep(2)
    freezer.move_to(time_test(3))
    time.sleep(2)

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    assert (
        notify_slack.get_hist()[-1].find("水漏れしています．") == 0
        or notify_slack.get_hist()[-2].find("水漏れしています．") == 0
    )


def test_actuator_speedup(mocker):
    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler

    mock_gpio(mocker)
    mocker.patch("valve.get_flow", return_value=None)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 5,
        }
    )

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 5,
        }
    )

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    # NOTE: 正常終了すれば OK


def test_actuator_monitor_error(mocker):
    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler

    mock_gpio(mocker)
    mocker.patch("valve.get_flow", return_value=None)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    mocker.patch("unit_cooler.send_valve_condition", side_effect=RuntimeError())

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 2,
        }
    )

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 2,
        }
    )

    time.sleep(2)

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", False)
    check_notify_slack("Traceback")


def test_actuator_slack_error(mocker):
    import slack_sdk

    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler

    mock_gpio(mocker)
    mocker.patch("valve.get_flow", return_value=None)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    def webclient_mock(self, token):
        raise slack_sdk.errors.SlackClientError()

    mocker.patch.object(slack_sdk.web.client.WebClient, "__init__", webclient_mock)

    mocker.patch("unit_cooler.send_valve_condition", side_effect=RuntimeError())

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 2,
        }
    )

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 2,
        }
    )

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", False)
    check_notify_slack("Traceback")


def test_actuator_close(mocker, freezer):
    import copy

    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler
    import control_config
    import control
    from control_config import MESSAGE_LIST as MESSAGE_LIST_orig

    mock_gpio(mocker)
    mocker.patch("valve.get_flow", return_value=0)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())
    mocker.patch(
        "control.dummy_control_mode",
        return_value={"control_mode": len(control_config.MESSAGE_LIST) - 1},
    )

    message_list_orig = copy.deepcopy(MESSAGE_LIST_orig)
    message_list_orig[-1]["duty"]["on_sec"] = 1000000
    mocker.patch.object(control, "MESSAGE_LIST", message_list_orig)

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    freezer.move_to(time_test(0))

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 10,
        }
    )

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "dummy_mode": True,
            "speedup": 100,
            "msg_count": 10,
        }
    )
    freezer.move_to(time_test(1))
    time.sleep(1)
    freezer.move_to(time_test(2))
    time.sleep(1)
    freezer.move_to(time_test(3))
    time.sleep(1)
    freezer.move_to(time_test(4))

    unit_cooler.wait_and_term(*actuator_handle)
    cooler_controller.wait_and_term(*control_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    check_notify_slack("元栓が閉じています．")


def test_actuator_emit_error(mocker):
    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler

    mock_gpio(mocker)
    mock_fd_q10c(mocker)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    sender_mock = mocker.MagicMock()
    sender_mock.emit.return_value = False
    mocker.patch("fluent.sender.FluentSender", return_value=sender_mock)

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})
    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 1,
        }
    )
    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 1,
        }
    )

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    check_notify_slack(None)


def test_actuator_notify_hazard(mocker):
    import os

    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler
    from config import load_config

    mock_gpio(mocker)
    mock_fd_q10c(mocker)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    hazard_file = pathlib.Path(load_config(CONFIG_FILE)["actuator"]["hazard"]["file"])
    mtime = time.time() - 12 * 60 * 60
    hazard_file.touch()
    os.utime(hazard_file, (mtime, mtime))

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 5,
        }
    )

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 5,
        }
    )

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    check_notify_slack("過去に水漏れもしくは電磁弁の故障が検出されているので制御を停止しています．")


def test_actuator_ctrl_error(mocker):
    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler

    mock_gpio(mocker)
    mock_fd_q10c(mocker)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    mocker.patch("unit_cooler.set_cooling_state", side_effect=RuntimeError())

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 10,
        }
    )

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 10,
        }
    )

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz(
        "receiver", False
    )  # NOTE: actuator の異常で queue が close するので receiver も fail する
    check_healthz("actuator", False)
    check_healthz("monitor", True)
    check_notify_slack("Traceback")


def test_actuator_recv_error(mocker):
    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler
    from control_pubsub import start_client as start_client_orig

    mock_gpio(mocker)
    mock_fd_q10c(mocker)
    mocker.patch("control.fetch_data", return_value=gen_sensor_data())

    def start_client_mock(server_host, server_port, func, msg_count=0):
        start_client_orig(server_host, server_port, func, msg_count)
        raise RuntimeError()

    mocker.patch("control_pubsub.start_client", side_effect=start_client_mock)

    # NOTE: mock で差し替えたセンサーを使わせるため，ダミーモードを取り消す
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 1,
        }
    )

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 10,
        }
    )

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    check_notify_slack("Traceback")


def test_actuator_iolink_short(mocker):
    # NOTE: RPi.GPIO を差し替えるため，一旦ダミーモードにする
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    import cooler_controller
    import unit_cooler
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
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 2,
        }
    )

    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 2,
        }
    )

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    check_notify_slack(None)  # NOTE: 単発では通知しない


#####################################################################
def test_fd_q10c(mocker):
    import sensor.fd_q10c

    mock_fd_q10c(mocker)

    assert sensor.fd_q10c.FD_Q10C().get_value(False) is None
    assert sensor.fd_q10c.FD_Q10C().get_value(True) == 2.57
    assert sensor.fd_q10c.FD_Q10C().get_value_map() == {"flow": 2.57}


def test_fd_q10c_ping(mocker):
    import sensor.fd_q10c

    mock_fd_q10c(mocker, gen_fd_q10c_ser_trans_ping())

    assert sensor.fd_q10c.FD_Q10C().ping()


def test_fd_q10c_stop(mocker):
    import sensor.fd_q10c

    mock_fd_q10c(mocker)
    sensor = sensor.fd_q10c.FD_Q10C()
    sensor.stop()

    # NOTE: エラーが発生していなければ OK


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

    # NOTE: エラーが発生していなければ OK


def test_fd_q10c_short(mocker):
    import sensor.fd_q10c

    fd_q10c_ser_trans = gen_fd_q10c_ser_trans_sense()
    fd_q10c_ser_trans[3]["recv"] = fd_q10c_ser_trans[3]["recv"][0:2]
    mock_fd_q10c(mocker, fd_q10c_ser_trans)

    assert sensor.fd_q10c.FD_Q10C().get_value() is None


def test_fd_q10c_ext(mocker):
    import sensor.fd_q10c

    fd_q10c_ser_trans = gen_fd_q10c_ser_trans_sense()
    fd_q10c_ser_trans.insert(
        3, {"send": [0xF0, 0x2D], "recv": [0xF0, 0x2D, 0xD1, 0x18]}
    )

    mock_fd_q10c(mocker, fd_q10c_ser_trans, count=10)

    assert sensor.fd_q10c.FD_Q10C().get_value(True) is None


def test_fd_q10c_wait(mocker):
    import sensor.fd_q10c

    fd_q10c_ser_trans = gen_fd_q10c_ser_trans_sense()
    fd_q10c_ser_trans.insert(
        3, {"send": [0xF0, 0x2D], "recv": [0xF0, 0x2D, 0x01, 0x3C]}
    )

    mock_fd_q10c(mocker, fd_q10c_ser_trans, count=10)

    assert sensor.fd_q10c.FD_Q10C().get_value(True) is None


def test_fd_q10c_checksum(mocker):
    import sensor.fd_q10c

    fd_q10c_ser_trans = gen_fd_q10c_ser_trans_sense()
    fd_q10c_ser_trans[3]["recv"][3] = 0x11
    mock_fd_q10c(mocker, fd_q10c_ser_trans)

    assert sensor.fd_q10c.FD_Q10C().get_value(True) is None


def test_fd_q10c_power_on(mocker):
    import sensor.fd_q10c

    mock_fd_q10c(mocker, spi_read=0x11)

    assert sensor.fd_q10c.FD_Q10C().get_value(True) == 2.57


def test_fd_q10c_unknown_datatype(mocker):
    import sensor.fd_q10c

    mock_fd_q10c(mocker)

    assert sensor.fd_q10c.FD_Q10C().read_param(
        0x94, sensor.fd_q10c.driver.DATA_TYPE_RAW, True
    ) == [1, 1]


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

    assert sensor.fd_q10c.FD_Q10C().get_value() is None


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

    assert sensor.fd_q10c.FD_Q10C().get_value() is None


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

    assert sensor.fd_q10c.FD_Q10C().get_value() is None


def test_fd_q10c_timeout(mocker):
    import sensor.fd_q10c

    mock_fd_q10c(mocker)

    mocker.patch("fcntl.flock", side_effect=IOError())

    assert sensor.fd_q10c.FD_Q10C().get_value() is None


def test_actuator_restart():
    import cooler_controller
    import unit_cooler

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 1,
        }
    )
    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 6,
        }
    )

    unit_cooler.wait_and_term(*actuator_handle)

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 1,
        }
    )

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    check_notify_slack(None)
    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)


def test_webapp(mocker):
    import requests
    import webapp
    import webapp_event
    import webapp_log
    import cooler_controller
    import unit_cooler
    import gzip

    mocker.patch("control.fetch_data", return_value=gen_sensor_data())
    mocker.patch("unit_cooler_info.get_day_sum", return_value=100)

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 5,
        }
    )
    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 5,
        }
    )

    time.sleep(2)

    app = webapp.create_app({"config_file": CONFIG_FILE, "msg_count": 1})
    client = app.test_client()

    response = client.get("/")
    assert response.status_code == 302
    assert re.search(r"/unit_cooler/$", response.location)

    response = client.get("/unit_cooler/")
    assert response.status_code == 200
    assert "室外機" in response.data.decode("utf-8")

    response = client.get(
        "/unit_cooler/",
        headers={"Accept-Encoding": "gzip"},
    )
    assert response.status_code == 200
    assert "室外機" in gzip.decompress(response.data).decode("utf-8")

    response = client.get("/unit_cooler/api/log_view")
    assert response.status_code == 200
    assert "data" in response.json
    assert len(response.json["data"]) != 0
    assert "last_time" in response.json

    response = client.get("/unit_cooler/api/event", query_string={"count": "2"})
    assert response.status_code == 200
    assert response.data.decode()

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

    response = client.get("/unit_cooler/api/stat")
    assert response.status_code == 200
    assert "watering" in response.json
    assert "sensor" in response.json
    assert "mode" in response.json
    assert "cooler_status" in response.json
    assert "outdoor_status" in response.json

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

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    # NOTE: カバレッジのため
    webapp_event.stop_watch()
    webapp_log.term()

    check_notify_slack(None)
    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    check_healthz("web", True)


def test_webapp_dummy_mode(mocker):
    import webapp
    import webapp_event
    import webapp_log
    import cooler_controller
    import unit_cooler

    mocker.patch("control.fetch_data", return_value=gen_sensor_data())
    mocker.patch("unit_cooler_info.get_day_sum", return_value=100)

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 5,
        }
    )
    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 5,
        }
    )

    time.sleep(2)

    app = webapp.create_app(
        {"config_file": CONFIG_FILE, "msg_count": 1, "dummy_mode": True}
    )
    client = app.test_client()

    response = client.get("/unit_cooler/api/stat")
    assert response.status_code == 200
    assert "watering" in response.json
    assert "sensor" in response.json
    assert "mode" in response.json
    assert "cooler_status" in response.json
    assert "outdoor_status" in response.json

    mocker.patch(
        "flask.wrappers.Response.status_code",
        return_value=301,
        new_callable=mocker.PropertyMock,
    )

    response = client.get("/unit_cooler/", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 301

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    client.delete()

    # NOTE: カバレッジのため
    webapp_event.stop_watch()
    webapp_log.term()

    check_notify_slack(None)
    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    check_healthz("web", True)


def test_webapp_queue_overflow(mocker):
    import webapp
    import cooler_controller
    import unit_cooler
    from config import load_config

    mocker.patch.dict("os.environ", {"WERKZEUG_RUN_MAIN": "true"})

    mocker.patch("control.fetch_data", return_value=gen_sensor_data())
    mocker.patch("unit_cooler_info.get_day_sum", return_value=100)

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 5,
        }
    )
    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "msg_count": 7,
        }
    )

    app = webapp.create_app(
        {"config_file": CONFIG_FILE, "msg_count": 1, "dummy_mode": False}
    )
    client = app.test_client()

    # NOTE: カバレッジ用にキューを溢れさせる
    for _ in range(100):
        webapp.queuing_message(
            load_config(CONFIG_FILE), app.config["MESSAGE_QUEUE"], "TEST"
        )
        time.sleep(0.01)

    response = client.get("/unit_cooler/api/stat")
    assert response.status_code == 200
    assert "watering" in response.json
    assert "sensor" in response.json
    assert "mode" in response.json
    assert "cooler_status" in response.json
    assert "outdoor_status" in response.json

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    client.delete()

    check_notify_slack(None)
    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    check_healthz("web", True)


def test_webapp_day_sum(mocker):
    import webapp
    import cooler_controller
    import unit_cooler

    mocker.patch.dict("os.environ", {"WERKZEUG_RUN_MAIN": "true"})

    fetch_data_mock = mocker.MagicMock()
    fetch_data_mock.to_values.side_effect = [[[None, 10]], [], RuntimeError()]

    mocker.patch("sensor_data.fetch_data_impl", return_value=fetch_data_mock)

    sensor_data = gen_sensor_data()
    sensor_data["valid"] = False
    mocker.patch("control.fetch_data", return_value=sensor_data)

    actuator_handle = unit_cooler.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 5,
        }
    )
    control_handle = cooler_controller.start(
        {
            "config_file": CONFIG_FILE,
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 5,
        }
    )

    time.sleep(2)

    app = webapp.create_app(
        {"config_file": CONFIG_FILE, "msg_count": 1, "dummy_mode": True}
    )
    client = app.test_client()

    response = client.get("/unit_cooler/api/stat")
    assert response.status_code == 200
    assert "watering" in response.json
    assert "sensor" in response.json
    assert "mode" in response.json
    assert "cooler_status" in response.json
    assert "outdoor_status" in response.json

    response = client.get("/unit_cooler/api/stat")
    assert response.status_code == 200

    response = client.get("/unit_cooler/api/stat")
    assert response.status_code == 200

    cooler_controller.wait_and_term(*control_handle)
    unit_cooler.wait_and_term(*actuator_handle)

    client.delete()

    check_notify_slack(None)
    check_healthz("controller", True)
    check_healthz("receiver", True)
    check_healthz("actuator", True)
    check_healthz("monitor", True)
    check_healthz("web", True)
