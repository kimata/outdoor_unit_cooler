#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest


def pytest_addoption(parser):
    parser.addoption("--server", default="127.0.0.1")


@pytest.fixture
def server(request):
    return request.config.getoption("--server")
