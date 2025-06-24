"""
Test helper functions and fixtures for outdoor unit cooler tests.

This module contains common patterns extracted from test_basic.py to reduce code duplication.
"""

from __future__ import annotations

import copy
import fcntl
import logging
import os
import random
import socket
import tempfile
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

import pytest

if TYPE_CHECKING:
    from typing import Any, Callable


_port_lock = threading.Lock()
_used_ports = set()
_base_port = 10000  # Start from a higher port range to avoid system ports
_port_lock_file = Path(tempfile.gettempdir()) / "pytest_port_lock"


def _acquire_port_lock():
    """Acquire cross-process port allocation lock."""
    try:
        lock_fd = os.open(str(_port_lock_file), os.O_CREAT | os.O_WRONLY, 0o644)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        return lock_fd
    except OSError:
        return None


def _release_port_lock(lock_fd):
    """Release cross-process port allocation lock."""
    if lock_fd is not None:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
        except OSError:
            pass


def _load_used_ports():
    """Load used ports from shared file."""
    used_ports_file = Path(tempfile.gettempdir()) / "pytest_used_ports"
    try:
        with used_ports_file.open() as f:
            return {int(line.strip()) for line in f if line.strip().isdigit()}
    except (FileNotFoundError, ValueError):
        return set()


def _save_used_ports(used_ports):
    """Save used ports to shared file."""
    used_ports_file = Path(tempfile.gettempdir()) / "pytest_used_ports"
    try:
        with used_ports_file.open("w") as f:
            for port in sorted(used_ports):
                f.write(f"{port}\n")
    except OSError:
        pass


def _find_unused_port():
    """Find an unused port using cross-process coordination."""
    lock_fd = _acquire_port_lock()
    if lock_fd is None:
        # Fallback to simple system allocation if locking fails
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("localhost", 0))
            return sock.getsockname()[1]

    try:
        # Load currently used ports from all processes
        used_ports = _load_used_ports()

        # Use worker ID for initial port range preference
        worker_id = os.environ.get("PYTEST_XDIST_WORKER", "gw0")
        worker_num = int(worker_id.replace("gw", "")) if worker_id.startswith("gw") else 0

        # Calculate worker-specific starting point
        max_workers = 50
        worker_slot = worker_num % max_workers
        port_range_size = 500
        port_range_start = _base_port + (worker_slot * port_range_size)
        port_range_end = min(port_range_start + port_range_size - 1, 65535)

        # Try to find an available port
        for _attempt in range(50):
            if _attempt < 20 and port_range_start <= port_range_end:
                # Try worker-specific range first
                port = random.randint(port_range_start, port_range_end)  # noqa: S311
            else:
                # Try broader range
                port = random.randint(_base_port, 65535)  # noqa: S311

            if port in used_ports:
                continue

            # Test if port is actually available
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                try:
                    sock.bind(("localhost", port))
                    # Port is available - record it and return
                    used_ports.add(port)
                    _save_used_ports(used_ports)
                    return port
                except OSError:
                    # Port not available, try next
                    continue

        # If we get here, fall back to system allocation
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("localhost", 0))
            port = sock.getsockname()[1]
            used_ports.add(port)
            _save_used_ports(used_ports)
            return port

    finally:
        _release_port_lock(lock_fd)


def _release_port(port):
    """Release a port from the used ports set across all processes."""
    lock_fd = _acquire_port_lock()
    if lock_fd is None:
        return

    try:
        used_ports = _load_used_ports()
        used_ports.discard(port)
        _save_used_ports(used_ports)
    finally:
        _release_port_lock(lock_fd)


def wait_for_set_cooling_working(timeout: float = 30.0) -> None:
    """
    Wait for unit_cooler.actuator.valve.set_cooling_working to be called.
    
    This function uses a mock to detect when set_cooling_working is called and
    waits up to the specified timeout for it to happen.
    
    Args:
        timeout: Maximum time to wait in seconds (default: 30.0)
        
    Raises:
        pytest.fail: If set_cooling_working is not called within the timeout
    """
    set_cooling_working_called = threading.Event()
    original_set_cooling_working = None
    
    def mock_set_cooling_working(*args, **kwargs):
        # イベントをセット
        set_cooling_working_called.set()
        logging.info("set_cooling_working was called")
        # 元の関数を呼び出す
        return original_set_cooling_working(*args, **kwargs)
    
    # valve.set_cooling_working をモックして待つ
    with mock.patch(
        "unit_cooler.actuator.valve.set_cooling_working", side_effect=mock_set_cooling_working
    ) as mock_func:
        # 元の関数を保存
        original_set_cooling_working = mock_func.wraps
        
        # set_cooling_working が呼ばれるまで最大 timeout 秒待つ
        if not set_cooling_working_called.wait(timeout=timeout):
            pytest.fail(f"set_cooling_working was not called within {timeout} seconds")


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
            "msg_count": 2,
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


def control_message_modifier(mocker):
    """Modify control message list settings. Takes mocker as parameter."""

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


@pytest.fixture()
def control_message_modifier_fixture(mocker):
    """Fixture version of control_message_modifier for tests that need it as a fixture."""
    return control_message_modifier(mocker)


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
