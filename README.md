# エアコン室外機冷却システム

## 概要

エアコンが動作を開始すると自動的に室外機へのミスト噴射を行います．


## システム構成

![システム構成](./img/システム構成.png)

このプログラムは上図の「コントローラ」になります．

## 詳細

- エアコン稼働状態は，F-PLUG やシャープの HEMS で計測した消費電力を infuxDB に記録し，それを参照することで行います．
- ミスト噴射は常時噴射ではなく，ON/OFFを繰り返して効果的に冷却します．
- ただし，外気温が一定温度を候えている場合，常時噴射動作に移行します．
- 流量をモニタし，元栓の閉鎖や水漏れを検知し，メールで通知します．

## 準備

Ubuntu の場合，`install.sh` を実行すると apt を使って必要なライブラリがインストールされます．

## 設定

`src/config.yaml.example` を `src/config.yaml` に名前変更し，
電磁弁制御用の GPIO 端子番号とメール通知に関する設定を行います．

## 実行

`src/unit_cooler.py` を実行します．

問題ないようでしたら，`cron/unit_cooler` を適宜編集した上で，
`/etc/cron.d` に配置して一定間隔で自動実行されるようにします．
