#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# エアコン室外機冷却システムモニタ用スクリプト．
# 噴霧量の測定を行います．

import json
import subprocess
import re

import fd_q10c
import logger

logger.init("sense_cooler", "/dev/shm", False)

value_map = {"flow": fd_q10c.sense(False)}

wifi_rssi = subprocess.check_output(
    "sudo iwconfig 2>/dev/null | grep 'Signal level' | sed 's/.*Signal level=\\(.*\\) dBm.*/\\1/'",
    shell=True,
)
wifi_rssi = wifi_rssi.rstrip().decode()

wifi_ch = subprocess.check_output(
    "sudo iwlist wlan0 channel | grep Current | sed -r 's/^.*Channel ([0-9]+)\)/\\1/'",
    shell=True,
)
try:
    wifi_ch = int(wifi_ch.rstrip().decode())
except:
    # 5GHz
    wifi_ch = 0

if re.compile("-\d+").search(wifi_rssi):
    value_map["wifi_rssi"] = int(wifi_rssi)
    value_map["wifi_ch"] = wifi_ch

print(json.dumps(value_map))

exit(0)
