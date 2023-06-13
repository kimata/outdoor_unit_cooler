#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pathlib

APP_URL_PREFIX = "/rasp-water"
STATIC_FILE_PATH = "../../dist/rasp-water"

SCHEDULE_DATA_PATH = pathlib.Path(__file__).parent.parent / "data" / "schedule.dat"
LOG_DB_PATH = pathlib.Path(__file__).parent.parent / "data" / "log.db"

STAT_DIR_PATH = pathlib.Path("/dev/shm") / "rasp-water"
