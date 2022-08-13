#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pathlib
import datetime
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir, "lib"))

from config import load_config

config = load_config()

liveness_file = pathlib.Path(config["liveness"]["file"])

if not liveness_file.exists():
    print("Not executed.", file=sys.stderr)
    sys.exit(-1)

elapsed = datetime.datetime.now() - datetime.datetime.fromtimestamp(
    liveness_file.stat().st_mtime
)
# NOTE: interval を短めにしているので，閾値は 3 倍にする
if elapsed.seconds > (config["sense"]["interval"] * 3):
    print(
        "Execution interval is too long. ({elapsed:,} sec)".format(
            elapsed=elapsed.seconds
        ),
        file=sys.stderr,
    )
    sys.exit(-1)

print("OK.", file=sys.stderr)
sys.exit(0)
