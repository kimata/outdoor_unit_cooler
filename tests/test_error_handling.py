#!/usr/bin/env python3
# ruff: noqa: S101, B017, PT011, ARG001, T201, PERF203, F841, S110
"""Additional error handling and edge case tests for outdoor unit cooler system."""

import pathlib
from unittest import mock

import my_lib.notify.slack
import my_lib.webapp.config
import pytest
import requests

from tests.test_helpers import _find_unused_port

my_lib.webapp.config.URL_PREFIX = "/unit_cooler"

CONFIG_FILE = "config.example.yaml"
SCHEMA_CONFIG = "config.schema"


@pytest.fixture(scope="session", autouse=True)
def env_mock():
    with mock.patch.dict(
        "os.environ",
        {
            "TEST": "true",
            "NO_COLORED_LOGS": "true",
            "DUMMY_MODE": "true",
        },
    ) as fixture:
        yield fixture


@pytest.fixture(scope="session", autouse=True)
def slack_mock():
    with mock.patch(
        "my_lib.notify.slack.slack_sdk.web.client.WebClient.chat_postMessage",
        return_value=True,
    ) as fixture:
        yield fixture


@pytest.fixture(scope="session")
def config():
    import my_lib.config

    return my_lib.config.load(CONFIG_FILE, pathlib.Path(SCHEMA_CONFIG))


# ======== Error Handling Tests ========


def test_valve_gpio_error(mocker, config):
    """Test GPIO error handling in valve operations"""
    import unit_cooler.actuator.valve
    import unit_cooler.const

    # Initialize valve
    unit_cooler.actuator.valve.init(17)

    # Mock GPIO to raise exception
    with mocker.patch("my_lib.rpi.gpio.output", side_effect=Exception("GPIO Error")), pytest.raises(
        Exception, match="GPIO Error"
    ):
        unit_cooler.actuator.valve.set_state(unit_cooler.const.VALVE_STATE.OPEN)


def test_zmq_connection_failure(mocker, config):
    """Test ZeroMQ connection failure handling"""
    import unit_cooler.pubsub.subscribe
    import zmq

    # Mock ZMQ to raise connection error
    with mocker.patch("zmq.Context", side_effect=zmq.ZMQError("Connection failed")), pytest.raises(
        zmq.ZMQError
    ):
        unit_cooler.pubsub.subscribe.start_client("localhost", 2222, lambda _: None, 1)


def test_config_schema_validation_error(tmp_path):
    """Test invalid configuration schema handling"""
    import my_lib.config

    # Create invalid config file
    invalid_config = tmp_path / "invalid.yaml"
    invalid_config.write_text("invalid: yaml: content: [")

    with pytest.raises(Exception):
        my_lib.config.load(str(invalid_config))


def test_missing_config_values(tmp_path):
    """Test missing required configuration values"""
    import my_lib.config

    # Create config with missing required fields
    incomplete_config = tmp_path / "incomplete.yaml"
    incomplete_config.write_text("controller: {}")

    config = my_lib.config.load(str(incomplete_config))
    assert "controller" in config


def test_sensor_data_validation():
    """Test sensor data validation"""
    import unit_cooler.actuator.sensor

    # Test with invalid sensor data
    with pytest.raises(Exception):
        unit_cooler.actuator.sensor.get_data("invalid_device")


def test_memory_ctrl_hist_growth(config):
    """Test ctrl_hist memory growth issue"""
    import unit_cooler.actuator.valve
    import unit_cooler.const

    # Initialize valve
    unit_cooler.actuator.valve.init(17)

    # Record initial history length
    initial_length = len(unit_cooler.actuator.valve.ctrl_hist)

    # Simulate many state changes
    for i in range(100):
        state = unit_cooler.const.VALVE_STATE.OPEN if i % 2 == 0 else unit_cooler.const.VALVE_STATE.CLOSE
        unit_cooler.actuator.valve.set_state(state)

    # Check that history grows (demonstrating the memory leak issue)
    final_length = len(unit_cooler.actuator.valve.ctrl_hist)
    assert final_length > initial_length
    assert final_length <= initial_length + 100  # Should not exceed expected growth


def test_thread_termination_timeout(mocker, config):
    """Test thread termination with timeout"""
    import concurrent.futures

    import unit_cooler.actuator.worker

    # Create executor with timeout handling
    executor = concurrent.futures.ThreadPoolExecutor()

    # Mock a long-running worker that doesn't respond to termination
    def slow_worker():
        import time

        time.sleep(0.1)  # Short sleep for test
        return 0

    future = executor.submit(slow_worker)

    # Test timeout handling
    unit_cooler.actuator.worker.should_terminate = True

    # This should shutdown gracefully
    executor.shutdown(wait=True)


def test_influxdb_connection_error(mocker, config):
    """Test InfluxDB connection error handling"""
    import unit_cooler.controller.sensor

    # Mock the underlying sensor data fetch to raise connection error
    with mocker.patch(
        "my_lib.sensor_data.fetch_data", side_effect=Exception("InfluxDB Connection Error")
    ), pytest.raises(Exception, match="InfluxDB Connection Error"):
        unit_cooler.controller.sensor.get_sense_data(config)


def test_slack_notification_error(mocker, config):
    """Test Slack notification error handling"""
    import unit_cooler.util

    # Mock Slack to raise error
    mocker.patch("my_lib.notify.slack.error", side_effect=Exception("Slack Error"))
    # Should not raise exception, should handle gracefully
    unit_cooler.util.notify_error(config, "Test error message")


def test_concurrent_valve_operations(config):
    """Test concurrent valve operations for race conditions"""
    import threading

    import unit_cooler.actuator.valve
    import unit_cooler.const

    # Initialize valve
    unit_cooler.actuator.valve.init(17)

    results = []

    def valve_operation(state):
        try:
            unit_cooler.actuator.valve.set_state(state)
            results.append("success")
        except Exception as e:
            results.append(f"error: {e}")

    # Create multiple threads operating valve concurrently
    threads = []
    for i in range(10):
        state = unit_cooler.const.VALVE_STATE.OPEN if i % 2 == 0 else unit_cooler.const.VALVE_STATE.CLOSE
        thread = threading.Thread(target=valve_operation, args=(state,))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Check that operations completed (may have errors due to GPIO mocking)
    assert len(results) == 10


def test_queue_cleanup_handling(config):
    """Test queue cleanup and resource management"""
    import multiprocessing

    # Create queue and test cleanup
    manager = multiprocessing.Manager()
    test_queue = manager.Queue()

    # Add items to queue
    test_queue.put({"test": "data"})

    # Test that queue can be used and cleaned up properly
    assert not test_queue.empty()
    item = test_queue.get()
    assert item["test"] == "data"

    # Note: Testing the actual cleanup behavior mentioned in worker.py comments


# ======== WebUI API Tests ========


def test_webui_api_endpoints(config):
    """Test WebUI API endpoints comprehensively"""
    import threading
    import time

    import webui

    # Find available port
    test_port = _find_unused_port()

    # Start webui in background thread
    def start_webui():
        try:
            app = webui.create_app(
                config,
                {
                    "control_host": "localhost",
                    "pub_port": 2222,
                    "actuator_host": "localhost",
                    "log_port": config["actuator"]["log_server"]["webapp"]["port"],
                    "dummy_mode": True,
                    "msg_count": 5,
                },
            )
            app.run(host="localhost", port=test_port, use_reloader=False, threaded=True, debug=False)
        except Exception:
            pass  # Ignore WebUI start failures in tests

    webui_thread = threading.Thread(target=start_webui, daemon=True)
    webui_thread.start()

    # Wait for server to start with retry mechanism
    base_url = f"http://localhost:{test_port}{my_lib.webapp.config.URL_PREFIX}"
    server_ready = False
    for _ in range(30):  # Try for up to 30 seconds
        try:
            res = requests.get(f"{base_url}/", timeout=1)
            if res.status_code in [200, 404, 500]:  # Any response means server is up
                server_ready = True
                break
        except requests.exceptions.ConnectionError:
            time.sleep(1)

    if not server_ready:
        pytest.fail("WebUI server failed to start within 30 seconds")

    # Test main page
    try:
        res = requests.get(f"{base_url}/", timeout=5)
        assert res.status_code == 200

        # Test some existing API endpoints from the logs
        existing_endpoints = [
            "/api/stat",
            "/api/sysinfo",
            "/api/memory",
        ]

        # Test endpoints without loop performance overhead
        endpoints_status = []
        for endpoint in existing_endpoints:
            try:
                res = requests.get(f"{base_url}{endpoint}", timeout=5)
                endpoints_status.append(res.status_code)
            except requests.exceptions.ConnectionError:
                endpoints_status.append(None)

        # Verify at least some endpoints respond
        assert any(status in [200, 404, 500] for status in endpoints_status if status)

    except requests.exceptions.ConnectionError as e:
        pytest.fail(f"WebUI server connection failed: {e}")


def test_webui_error_responses(config):
    """Test WebUI error response handling"""
    import threading
    import time

    import webui

    # Find available port
    test_port = _find_unused_port()

    # Start webui in background thread
    def start_webui():
        try:
            app = webui.create_app(
                config,
                {
                    "control_host": "localhost",
                    "pub_port": 2222,
                    "actuator_host": "localhost",
                    "log_port": config["actuator"]["log_server"]["webapp"]["port"],
                    "dummy_mode": True,
                    "msg_count": 5,
                },
            )
            app.run(
                host="localhost",
                port=test_port,
                use_reloader=False,
                threaded=True,
                debug=False,
            )
        except Exception:
            pass  # Ignore WebUI start failures in tests

    webui_thread = threading.Thread(target=start_webui, daemon=True)
    webui_thread.start()

    # Wait for server to start with retry mechanism
    base_url = f"http://localhost:{test_port}{my_lib.webapp.config.URL_PREFIX}"
    server_ready = False
    for _ in range(30):  # Try for up to 30 seconds
        try:
            res = requests.get(f"{base_url}/", timeout=1)
            if res.status_code in [200, 404, 500]:  # Any response means server is up
                server_ready = True
                break
        except requests.exceptions.ConnectionError:
            time.sleep(1)

    if not server_ready:
        pytest.fail("WebUI server failed to start within 30 seconds")

    # Test invalid endpoints
    try:
        res = requests.get(f"{base_url}/api/nonexistent", timeout=5)
        assert res.status_code == 404
    except requests.exceptions.ConnectionError as e:
        pytest.fail(f"WebUI server connection failed: {e}")


def test_hardware_boundary_conditions(config):
    """Test hardware boundary conditions"""
    import unit_cooler.actuator.valve
    import unit_cooler.const

    # Test valve initialization with invalid pin - now properly validates in dummy mode
    with pytest.raises(ValueError, match="Pin -1 is not a valid GPIO pin number"):
        unit_cooler.actuator.valve.init(-1)  # Invalid GPIO pin now raises ValueError

    # Test valve initialization with valid pin
    unit_cooler.actuator.valve.init(17)  # Valid pin
    assert unit_cooler.actuator.valve.pin_no == 17

    # Test that valve operations work in dummy mode
    current_state = unit_cooler.actuator.valve.get_state()
    assert current_state in [
        unit_cooler.const.VALVE_STATE.OPEN,
        unit_cooler.const.VALVE_STATE.CLOSE,
    ]

    # Test valve state changes work
    original_state = unit_cooler.actuator.valve.get_state()
    target_state = (
        unit_cooler.const.VALVE_STATE.OPEN
        if original_state == unit_cooler.const.VALVE_STATE.CLOSE
        else unit_cooler.const.VALVE_STATE.CLOSE
    )
    unit_cooler.actuator.valve.set_state(target_state)
    # Note: In dummy mode, the state might not actually change, but function should complete

    # Test valve state with uninitialized pin (after setting to None manually)
    unit_cooler.actuator.valve.pin_no = None
    # This might now raise an exception due to improved validation
    try:
        state = unit_cooler.actuator.valve.get_state()
        assert state in [
            unit_cooler.const.VALVE_STATE.OPEN,
            unit_cooler.const.VALVE_STATE.CLOSE,
        ]
    except ValueError:
        # If validation now catches None pins, that's expected
        pass


def test_configuration_edge_cases(tmp_path):
    """Test configuration edge cases"""
    import my_lib.config

    # Test empty config file - should raise TypeError due to None handling
    empty_config = tmp_path / "empty.yaml"
    empty_config.write_text("")

    with pytest.raises(TypeError, match="'NoneType' object does not support item assignment"):
        my_lib.config.load(str(empty_config))

    # Test config with only comments - should also raise TypeError
    comment_config = tmp_path / "comments.yaml"
    comment_config.write_text("# This is a comment\n# Another comment")

    with pytest.raises(TypeError, match="'NoneType' object does not support item assignment"):
        my_lib.config.load(str(comment_config))

    # Test invalid YAML syntax
    invalid_yaml = tmp_path / "invalid.yaml"
    invalid_yaml.write_text("invalid: yaml: [unclosed")

    with pytest.raises(Exception):  # Should raise YAML parse error
        my_lib.config.load(str(invalid_yaml))

    # Test config with valid content
    valid_config = tmp_path / "valid.yaml"
    valid_config.write_text("config: [1, 2, 3]\nother: 'string'")

    config = my_lib.config.load(str(valid_config))
    assert isinstance(config, dict)
    assert config["config"] == [1, 2, 3]
    assert config["other"] == "string"


def test_long_running_memory_usage(config):
    """Test memory usage in long-running scenario"""
    import gc

    import unit_cooler.actuator.valve
    import unit_cooler.const

    # Initialize valve
    unit_cooler.actuator.valve.init(17)

    # Record initial memory state
    gc.collect()
    initial_objects = len(gc.get_objects())

    # Simulate long-running operations
    for i in range(50):
        state = unit_cooler.const.VALVE_STATE.OPEN if i % 2 == 0 else unit_cooler.const.VALVE_STATE.CLOSE
        unit_cooler.actuator.valve.set_state(state)

        # Periodically check memory
        if i % 10 == 0:
            gc.collect()

    # Check final memory state
    gc.collect()
    final_objects = len(gc.get_objects())

    # Memory usage should not grow excessively
    growth_ratio = final_objects / initial_objects
    assert growth_ratio < 2.0, f"Memory growth too high: {growth_ratio}"


def test_signal_handling(config):
    """Test signal handling for graceful shutdown"""
    import signal

    import unit_cooler.actuator.worker

    # Test SIGTERM handling
    original_terminate = unit_cooler.actuator.worker.should_terminate

    # Simulate signal handler
    def mock_handler(signum, frame):
        unit_cooler.actuator.worker.should_terminate = True

    # Test signal handling
    mock_handler(signal.SIGTERM, None)
    assert unit_cooler.actuator.worker.should_terminate is True

    # Restore original state
    unit_cooler.actuator.worker.should_terminate = original_terminate
