#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from enum import IntEnum


class VALVE_STATE(IntEnum):
    OPEN = 1
    CLOSE = 0


class COOLING_STATE(IntEnum):
    WORKING = 1
    IDLE = 0
