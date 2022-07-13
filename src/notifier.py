#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import smtplib
import pathlib
from email.mime.text import MIMEText
import logging

INTERVAL_MIN = 60 * 3

STAT_DIR_PATH = pathlib.Path("/dev/shm")
STAT_PATH_NOTIFY = STAT_DIR_PATH / "cooler_notify"


def send_impl(config, message):
    smtp = smtplib.SMTP("smtp.gmail.com", 587)
    smtp.starttls()
    smtp.login(config["mail"]["user"], config["mail"]["pass"])

    msg = MIMEText(message, "html")
    msg["Subject"] = "【クーラー冷却システム】"
    msg["To"] = config["mail"]["to"]
    msg["From"] = config["mail"]["from"]

    smtp.send_message(msg)

    logging.info("sendmail")

    smtp.quit()


def send(config, message):
    logging.info("notify: {message}".format(message=message))

    if (
        STAT_PATH_NOTIFY.exists()
        and ((time.time() - STAT_PATH_NOTIFY.stat().st_mtime) / 60) < INTERVAL_MIN
    ):
        return
    send_impl(config, message)

    STAT_PATH_NOTIFY.touch()


if __name__ == "__main__":
    import yaml
    import logger

    logger.init("test")
    with open(str(pathlib.Path(os.path.dirname(__file__), "config.yml"))) as file:
        config = yaml.safe_load(file)

    send(config, "Testです")
