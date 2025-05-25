#!/usr/bin/env python3
import logging
import threading

import flask
import flask_cors
import my_lib.webapp.event
import my_lib.webapp.log
import werkzeug.serving


def create_app(config, event_queue):
    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    app = flask.Flask("unit_cooler_log")

    flask_cors.CORS(app)

    app.config["CONFIG"] = config

    app.json.compat = True

    app.register_blueprint(my_lib.webapp.log.blueprint)
    app.register_blueprint(my_lib.webapp.event.blueprint)

    my_lib.webapp.log.init(config)
    my_lib.webapp.event.start(event_queue)

    # app.debug = True

    return app


def start(config, event_queue):
    # NOTE: Flask は別のプロセスで実行
    server = werkzeug.serving.make_server(
        "0.0.0.0",  # noqa: S104
        config["actuator"]["log_server"]["webapp"]["port"],
        create_app(config, event_queue),
        threaded=True,
    )
    thread = threading.Thread(target=server.serve_forever)

    logging.info("Start log server")

    thread.start()

    return {
        "server": server,
        "thread": thread,
    }


def term(handle):
    logging.warning("Stop log server")

    my_lib.webapp.event.term()

    handle["server"].shutdown()
    handle["server"].server_close()
    handle["thread"].join()

    my_lib.webapp.log.term()
