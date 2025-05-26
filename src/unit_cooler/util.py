#!/usr/bin/env python3
import logging
import os

import my_lib.notify.slack


def notify_error(config, message, is_logging=True):
    if is_logging:
        logging.error(message)

    if ("slack" not in config) or (
        (os.environ.get("TEST", "false") != "true") and (os.environ.get("DUMMY_MODE", "false") == "true")
    ):
        # NOTE: テストではなく、ダミーモードで実行している時は Slack 通知しない
        return

    my_lib.notify.slack.error(
        config["slack"]["bot_token"],
        config["slack"]["error"]["channel"]["name"],
        config["slack"]["from"],
        message,
        config["slack"]["error"]["interval_min"],
    )
