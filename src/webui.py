#!/usr/bin/env python3
"""
エアコン室外機冷却システムの Web UI です。

Usage:
  webapp.py [-c CONFIG] [-s CONTROL_HOST] [-p PUB_PORT] [-a ACTUATOR_HOST] [-n COUNT] [-D] [-d]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。 [default: config.yaml]
  -s CONTROL_HOST   : コントローラのホスト名を指定します。 [default: localhost]
  -p PUB_PORT       : ZeroMQ の Pub サーバーを動作させるポートを指定します。 [default: 2222]
  -a ACTUATOR_HOST  : アクチュエータのホスト名を指定します。 [default: localhost]
  -n COUNT          : n 回制御メッセージを受信したら終了します。0 は制限なし。 [default: 0]
  -d                : ダミーモードで実行します。
  -D                : デバッグモードで動作します。
"""

import atexit
import logging
import multiprocessing
import os
import pathlib
import threading

import flask
import flask_cors

SCHEMA_CONFIG = "config.schema"


def create_app(config, setting):
    logging.info("Using ZMQ server of %s:%d", setting["control_host"], setting["pub_port"])

    # NOTE: オプションでダミーモードが指定された場合、環境変数もそれに揃えておく
    if dummy_mode:
        os.environ["DUMMY_MODE"] = "true"
    else:  # pragma: no cover
        os.environ["DUMMY_MODE"] = "false"

    # NOTE: テストのため、環境変数 DUMMY_MODE をセットしてからロードしたいのでこの位置
    import my_lib.webapp.config

    my_lib.webapp.config.URL_PREFIX = "/unit_cooler"
    my_lib.webapp.config.init(config["webui"])

    import my_lib.webapp.base
    import my_lib.webapp.log_proxy
    import my_lib.webapp.util
    import unit_cooler.webui.cooler_stat

    message_queue = multiprocessing.Queue(10)
    worker_thread = threading.Thread(
        target=unit_cooler.webui.worker.subscribe_worker,
        args=(
            config,
            setting["control_host"],
            setting["pub_port"],
            message_queue,
            pathlib.Path(config["webui"]["subscribe"]["liveness"]["file"]),
            setting["msg_count"],
        ),
    )
    worker_thread.start()

    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        if setting["dummy_mode"]:
            logging.warning("Set dummy mode")
    else:  # pragma: no cover
        pass

    app = flask.Flask("unit-cooler-webui")

    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        if dummy_mode:
            logging.warning("Set dummy mode")
        else:  # pragma: no cover
            pass

        # rasp_water.webapp_schedule.init(config)
        # rasp_water.webapp_valve.init(config)

        def notify_terminate():  # pragma: no cover
            pass
            # rasp_water.valve.set_state(rasp_water.valve.VALVE_STATE.CLOSE)
            # my_lib.webapp.log.info("🏃 アプリを再起動します。")
            # my_lib.webapp.log.term()

        atexit.register(notify_terminate)
    else:  # pragma: no cover
        pass

    flask_cors.CORS(app)

    app.config["CONFIG"] = config
    app.config["MESSAGE_QUEUE"] = message_queue

    app.json.compat = True

    app.register_blueprint(my_lib.webapp.base.blueprint_default)
    app.register_blueprint(my_lib.webapp.base.blueprint)
    app.register_blueprint(my_lib.webapp.log_proxy.blueprint)
    app.register_blueprint(my_lib.webapp.util.blueprint)
    app.register_blueprint(unit_cooler.webui.cooler_stat.blueprint)

    my_lib.webapp.log_proxy.init("http://{host}:5001/unit_cooler".format(host=setting["actuator_host"]))

    # app.debug = True

    return app


if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    control_host = os.environ.get("HEMS_CONTROL_HOST", args["-s"])
    pub_port = int(os.environ.get("HEMS_PUB_PORT", args["-p"]))
    actuator_host = os.environ.get("HEMS_ACTUATOR_HOST", args["-a"])
    dummy_mode = args["-d"]
    msg_count = int(args["-n"])
    debug_mode = args["-D"]

    my_lib.logger.init("hems.unit_cooler", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file, pathlib.Path(SCHEMA_CONFIG))

    app = create_app(
        config,
        {
            "control_host": control_host,
            "pub_port": pub_port,
            "actuator_host": actuator_host,
            "dummy_mode": dummy_mode,
            "msg_count": msg_count,
        },
    )

    # NOTE: スクリプトの自動リロード停止したい場合は use_reloader=False にする
    app.run(host="0.0.0.0", threaded=True, use_reloader=True)  # noqa: S104
