#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time

import aircon
import valve
import logger

logger.init("unit_cooler")

valve.set_state(aircon.get_state("書斎エアコン"))
