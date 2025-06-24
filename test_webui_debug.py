#!/usr/bin/env python3
# テストケースのデバッグ版

import time
import my_lib.notify.slack
import my_lib.webapp.config
import pytest
from unittest import mock

my_lib.webapp.config.URL_PREFIX = "/unit_cooler"

from tests.test_helpers import (
    _find_unused_port,
    _release_port,
)

# テスト用の設定
CONFIG_FILE = "config.example.yaml"
SCHEMA_CONFIG = "config.schema"

# モックの設定
with mock.patch.dict("os.environ", {"TEST": "true", "NO_COLORED_LOGS": "true"}):
    with mock.patch("my_lib.notify.slack.slack_sdk.web.client.WebClient.chat_postMessage", return_value=True):
        with mock.patch("my_lib.sensor.omron_2jcie_bu01.Omron2JCIE_BU01.__init__", return_value=None):
            with mock.patch("my_lib.sensor.omron_2jcie_bu01.Omron2JCIE_BU01.get_value", return_value={"temperature": 25.0}):
                # ポートの取得
                server_port = _find_unused_port()
                real_port = _find_unused_port()
                log_port = _find_unused_port()
                
                # 設定ファイルのロード
                import my_lib.config
                import pathlib
                config = my_lib.config.load(CONFIG_FILE, pathlib.Path(SCHEMA_CONFIG))
                
                # ダミーのセンサーデータ
                def gen_sense_data():
                    return {"cooler": {"temperature": 30.0}}
                
                # モックの設定
                with mock.patch("my_lib.sensor_data.fetch_data", return_value=gen_sense_data()):
                    with mock.patch("my_lib.sensor_data.get_day_sum", return_value=100):
                        # actuatorとcontrollerの起動
                        import actuator
                        import controller
                        
                        actuator_handle = actuator.start(
                            config,
                            {
                                "speedup": 100,
                                "dummy_mode": True,
                                "msg_count": 10,
                                "pub_port": server_port,
                                "log_port": log_port,
                            },
                        )
                        control_handle = controller.start(
                            config,
                            {
                                "speedup": 100,
                                "dummy_mode": True,
                                "msg_count": 10,
                                "server_port": server_port,
                                "real_port": real_port,
                            },
                        )
                        
                        time.sleep(4)
                        
                        # webui の作成
                        with mock.patch.dict("os.environ", {"DUMMY_MODE": "false"}):
                            import webui
                            
                            print(f"URL_PREFIX before create_app: {repr(my_lib.webapp.config.URL_PREFIX)}")
                            
                            app = webui.create_app(config, {"msg_count": 1, "pub_port": server_port, "log_port": log_port})
                            client = app.test_client()
                            
                            print(f"URL_PREFIX after create_app: {repr(my_lib.webapp.config.URL_PREFIX)}")
                            
                            # ルーティングテーブルの確認
                            print("\nRegistered routes:")
                            for rule in app.url_map.iter_rules():
                                print(f"  {rule.rule} -> {rule.endpoint}")
                            
                            # テストリクエスト
                            print(f"\nTesting GET {repr(my_lib.webapp.config.URL_PREFIX + '/')}")
                            res = client.get(f"{my_lib.webapp.config.URL_PREFIX}/")
                            print(f"Status: {res.status_code}")
                            print(f"Response data: {res.data[:200]}...")
                            
                            # 念のため直接パスも試す
                            print("\nTesting GET '/unit_cooler/'")
                            res = client.get("/unit_cooler/")
                            print(f"Status: {res.status_code}")
                            
                            # 終了処理
                            controller.wait_and_term(*control_handle)
                            actuator.wait_and_term(*actuator_handle)
                            
                            _release_port(server_port)
                            _release_port(real_port)
                            _release_port(log_port)