#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pathlib

APP_URL_PREFIX = "/unit_cooler"
STATIC_FILE_PATH = "../react/build/"

LOG_DB_PATH = pathlib.Path(__file__).parent.parent / "data" / "log.db"

STAT_DIR_PATH = pathlib.Path("/dev/shm") / "rasp-water"
