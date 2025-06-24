#!/usr/bin/env python3
import my_lib.webapp.config

# テストファイルの設定を再現
my_lib.webapp.config.URL_PREFIX = "/unit_cooler"

# webui.create_app の挙動を確認
import webui

config = {
    "webui": {
        "webapp": {
            "static_dir_path": "react/dist",
            "data": {
                "log_file_path": "data/hems.unit_cooler.log"
            }
        }
    }
}

print("Before create_app:", my_lib.webapp.config.URL_PREFIX)

# create_app内でURL_PREFIXがどう変わるか確認
app = webui.create_app(config, {"msg_count": 1, "pub_port": 12345, "log_port": 12346})

print("After create_app:", my_lib.webapp.config.URL_PREFIX)

# Flaskのルーティングテーブルを確認
print("\nRegistered routes:")
for rule in app.url_map.iter_rules():
    print(f"  {rule.rule} -> {rule.endpoint}")

# テストクライアントでアクセス
client = app.test_client()

# URL_PREFIXのパスにアクセス
response = client.get(f"{my_lib.webapp.config.URL_PREFIX}/")
print(f"\nGET {my_lib.webapp.config.URL_PREFIX}/")
print(f"Status: {response.status_code}")
print(f"Headers: {dict(response.headers)}")