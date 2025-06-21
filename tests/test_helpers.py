"""
Test helper functions and fixtures for outdoor unit cooler tests.

This module contains common patterns extracted from test_basic.py to reduce code duplication.
"""

from __future__ import annotations

import copy
import time
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from typing import Any, Callable


class ComponentManager:
    """Manages component startup and teardown for tests."""  # noqa: D203

    def __init__(self):
        """Initialize ComponentManager with empty handles."""
        self.handles = {}
        self.auto_teardown = True

    def start_actuator(self, config: dict[str, Any], server_port: int, log_port: int, **kwargs) -> tuple:
        """Start actuator with standard configuration."""
        import actuator

        default_config = {
            "speedup": 100,
            "msg_count": 1,
            "pub_port": server_port,
            "log_port": log_port,
        }
        default_config.update(kwargs)
        self.handles["actuator"] = actuator.start(config, default_config)
        return self.handles["actuator"]

    def start_controller(self, config: dict[str, Any], server_port: int, real_port: int, **kwargs) -> tuple:
        """Start controller with standard configuration."""
        import controller

        default_config = {
            "speedup": 100,
            "dummy_mode": True,
            "msg_count": 1,
            "server_port": server_port,
            "real_port": real_port,
        }
        default_config.update(kwargs)
        self.handles["controller"] = controller.start(config, default_config)
        return self.handles["controller"]

    def start_webui(self, config: dict[str, Any], server_port: int, log_port: int, **kwargs) -> tuple:
        """Start webui with standard configuration."""
        import webui

        default_config = {
            "msg_count": 1,
            "dummy_mode": True,
            "pub_port": server_port,
            "log_port": log_port,
        }
        default_config.update(kwargs)
        self.handles["webui"] = webui.start(config, default_config)
        return self.handles["webui"]

    def wait_and_term_controller(self):
        """Wait and terminate controller explicitly."""
        if "controller" in self.handles:
            import controller

            controller.wait_and_term(*self.handles["controller"])
            del self.handles["controller"]

    def wait_and_term_actuator(self):
        """Wait and terminate actuator explicitly."""
        if "actuator" in self.handles:
            import actuator

            actuator.wait_and_term(*self.handles["actuator"])
            del self.handles["actuator"]

    def wait_and_term_webui(self):
        """Wait and terminate webui explicitly."""
        if "webui" in self.handles:
            import webui

            webui.wait_and_term(*self.handles["webui"])
            del self.handles["webui"]

    def teardown_all(self):
        """Teardown all started components."""
        if not self.auto_teardown:
            return

        import actuator
        import controller
        import webui

        if "controller" in self.handles:
            controller.wait_and_term(*self.handles["controller"])
        if "actuator" in self.handles:
            actuator.wait_and_term(*self.handles["actuator"])
        if "webui" in self.handles:
            webui.wait_and_term(*self.handles["webui"])


@pytest.fixture()
def component_manager():
    """Fixture providing component management functionality."""
    manager = ComponentManager()
    yield manager
    manager.teardown_all()


@pytest.fixture()
def standard_actuator_mocks(mocker):
    """Provide standard mock setup for most actuator tests."""
    from tests.test_basic import gen_sense_data, mock_fd_q10c, mock_gpio

    mock_gpio(mocker)
    mock_fd_q10c(mocker)
    mocker.patch("my_lib.sensor_data.fetch_data", return_value=gen_sense_data())
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})
    return mocker


@pytest.fixture()
def standard_mocks(mocker):
    """Provide standard mock setup for most actuator tests."""
    from tests.test_basic import gen_sense_data, mock_fd_q10c, mock_gpio

    mock_gpio(mocker)
    mock_fd_q10c(mocker)
    mocker.patch("my_lib.sensor_data.fetch_data", return_value=gen_sense_data())
    mocker.patch.dict("os.environ", {"DUMMY_MODE": "false"})
    return mocker


@pytest.fixture()
def controller_mocks(mocker):
    """Provide standard mock setup for controller tests."""
    from tests.test_basic import gen_sense_data

    mocker.patch("my_lib.sensor_data.fetch_data", return_value=gen_sense_data())
    return mocker


@pytest.fixture()
def webapp_client(config, server_port, log_port):
    """Create a webapp test client with standard configuration."""
    import webui

    app = webui.create_app(
        config, {"msg_count": 1, "dummy_mode": True, "pub_port": server_port, "log_port": log_port}
    )
    client = app.test_client()
    yield client
    client.delete()


def check_standard_liveness(
    config: dict[str, Any], expected_states: dict[tuple[str, ...], bool] | None = None
):
    """Check standard liveness states for all components."""
    from tests.test_basic import check_liveness

    defaults = {
        ("controller",): True,
        ("actuator", "subscribe"): True,
        ("actuator", "control"): True,
        ("actuator", "monitor"): True,
        ("webui", "subscribe"): False,
    }

    if expected_states:
        defaults.update(expected_states)

    for path, expected in defaults.items():
        check_liveness(config, list(path), expected)


def check_controller_only_liveness(config: dict[str, Any]):
    """Apply common pattern for controller-only tests."""
    check_standard_liveness(
        config,
        {
            ("actuator", "subscribe"): False,
            ("actuator", "control"): False,
            ("actuator", "monitor"): False,
        },
    )


def check_standard_post_test(config: dict[str, Any]):
    """Perform standard post-test checks (liveness + slack notification)."""
    from tests.test_basic import check_notify_slack

    check_standard_liveness(config)
    check_notify_slack(None)


def create_fetch_data_mock(field_mappings: dict[str, Any]) -> Callable:
    """Create a fetch_data mock with custom field mappings."""
    from tests.test_basic import gen_sense_data

    def fetch_data_mock(  # noqa: PLR0913
        db_config,  # noqa: ARG001
        measure,  # noqa: ARG001
        hostname,  # noqa: ARG001
        field,
        start="-30h",  # noqa: ARG001
        stop="now()",  # noqa: ARG001
        every_min=1,  # noqa: ARG001
        window_min=3,  # noqa: ARG001
        create_empty=True,  # noqa: ARG001
        last=False,  # noqa: ARG001
    ):
        return field_mappings.get(field, gen_sense_data())

    return fetch_data_mock


def advance_time_sequence(time_machine, minutes: list[int], sleep_duration: float = 1):
    """Advance time through a sequence of minutes with sleep intervals."""
    from tests.test_basic import move_to

    for minute in minutes:
        if isinstance(minute, tuple):
            move_to(time_machine, minute[1], minute[0])  # (hour, minute)
        else:
            move_to(time_machine, minute)
        time.sleep(sleep_duration)


@pytest.fixture()
def control_message_modifier(mocker):
    """Provide helper to modify control message list settings."""

    def modify_duty_settings(**kwargs):
        import unit_cooler.controller.message
        from unit_cooler.controller.message import CONTROL_MESSAGE_LIST as CONTROL_MESSAGE_LIST_ORIG

        message_list = copy.deepcopy(CONTROL_MESSAGE_LIST_ORIG)
        for key, value in kwargs.items():
            if "." in key:
                # Support nested keys like "duty.on_sec"
                keys = key.split(".")
                target = message_list[-1]
                for k in keys[:-1]:
                    target = target[k]
                target[keys[-1]] = value
            else:
                message_list[-1]["duty"][key] = value

        mocker.patch.object(unit_cooler.controller.message, "CONTROL_MESSAGE_LIST", message_list)
        return message_list

    return modify_duty_settings


def assert_standard_api_response(response, required_fields: list[str] | None = None):
    """Assert standard API response structure."""
    if response.status_code != 200:
        msg = f"Expected status 200, got {response.status_code}"
        raise AssertionError(msg)
    json_data = response.json

    default_fields = ["watering", "sensor", "mode", "cooler_status", "outdoor_status"]
    fields_to_check = required_fields or default_fields

    for field in fields_to_check:
        if field not in json_data:
            msg = f"Required field '{field}' not found in response"
            raise AssertionError(msg)


def run_standard_test_sequence(component_manager, test_func, config, server_port, real_port, **kwargs):
    """Run a standard test sequence with component startup, test execution, and teardown."""
    # Start components
    log_port = kwargs.get("log_port", 5001)
    actuator_kwargs = kwargs.get("actuator_kwargs", {})
    controller_kwargs = kwargs.get("controller_kwargs", {})

    component_manager.start_actuator(config, server_port, log_port, **actuator_kwargs)
    component_manager.start_controller(config, server_port, real_port, **controller_kwargs)

    # Run the test function
    test_func(config, server_port, real_port, log_port)

    # Components will be torn down automatically by the fixture


# Pre-configured field mappings for common test scenarios
OUTDOOR_NORMAL_FIELDS = {
    "temp": None,  # Will use gen_sense_data([25]) in actual usage
    "power": None,  # Will use gen_sense_data([100]) in actual usage
    "lux": None,  # Will use gen_sense_data([500]) in actual usage
    "solar_rad": None,  # Will use gen_sense_data([300]) in actual usage
}

TEMP_LOW_FIELDS = {
    "temp": None,  # Will use gen_sense_data([15]) in actual usage
    "power": None,  # Will use gen_sense_data([100]) in actual usage
}

POWER_OFF_FIELDS = {
    "temp": None,  # Will use gen_sense_data([35]) in actual usage
    "power": None,  # Will use gen_sense_data([0]) in actual usage
}
