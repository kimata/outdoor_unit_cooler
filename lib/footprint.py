#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time


def exists(path):
    return path.exists()


def update(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, mode="w") as f:
        f.write(str(time.time()))


def elapsed(path):
    diff_sec = time.time()
    if not path.exists():
        return diff_sec

    with open(path, mode="r") as f:
        last_update = f.read()

        if last_update != "":
            diff_sec -= float(last_update)

    return diff_sec


def clear(path):
    path.unlink(missing_ok=True)
