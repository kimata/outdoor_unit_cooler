# エアコン室外機冷却システム

## 概要

エアコンが動作を開始すると自動的に室外機へのミスト噴射を行うシステムです．

## デモ

エアコンの稼働状況に応じてミスト噴射モードが自動的に変化する様子を確認いただけます．

https://unit-cooler-webapp-demo.kubernetes.green-rabbit.net/unit_cooler/

## システム構成

### 全体構成

![システム構成](./img/システム構成.png)

このプログラムは上図の「コントローラ」に対応します．

### ソフト構成

![ソフトアーキ図](./img/ソフトアーキ図.png)

このプログラムは，上記の中で赤字で記載した 4 つのスレッドに対応します．

-   Cooler controller
-   Command receive worker
-   Valve control worker
-   Valve monitor worker

## 詳細

-   F-PLUG やシャープの HEMS で計測した消費電力が infuxDB に記録されていることを前提にしています．
-   ミスト噴射は常時噴射ではなく，ON/OFF を繰り返して効果的に冷却します．
-   流量計で流量をモニタし，元栓の開き忘れや水漏れを検知し，Slack で通知します．

## 準備

`app/unit_cooler.py` を配置する Raspberry Pi で，`/boot/firmware/config.txt` に下記の
設定を追加します．

```text
dtparam=spi=on
dtoverlay=disable-bt
```

## 設定

`src/config.example.yml` を `src/config.yml` に名前変更します．
環境に合わせて適宜書き換えてください．

Slack を使っていない場合は，Slack の設定をコメントアウトしてください．

## 実行

`docker build` でイメージを構築し，`app/cooler_controller.py` と `app/unit_cooler.py` 
を動かします．Web インターフェースが欲しい場合は，`app/webapp.py` も動かします．

Kubernetes 用の設定ファイルが `kubernetes/outdoor_unit_cooler.yml` に入っていますので，
これを参考にしていただくと良いと思います．

カスタマイズが必要になりそうなのは下記の項目になります．

<dl>
  <dt>namespace</dt>
  <dd><code>hems</code> というネームスペースを作っていますので，環境に合わせて変更します．</dd>

  <dt>external-dns.alpha.kubernetes.io/hostname</dt>
  <dd>ExternalDNS で設定するホスト名を指定します．環境に合わせて変更いただくか，不要であれば削除します．</dd>
  
  <dt>image</dt>
  <dd>ビルドしたイメージを登録してあるコンテナリポジトリに書き換えます．</dd>
  
  <dt>nodeSelector</dt>
  <dd>Pod を配置したいノード名に変更します．</dd>
  
  <dt>NODE_HOSTNAME</dt>
  <dd>散布量を InfluxDB に登録する際のホスト名
  を指定します．<code>config.yaml</code> の controller.watering.hostname の設定と合わせる必要があります．</dd>
</dl>

## テスト結果

-   https://kimata.github.io/outdoor_unit_cooler/
-   https://kimata.github.io/outdoor_unit_cooler/coverage/

## TODO
- 当初つける予定が無かった Web UI (デモモード有)をつけるにあたって，場当たり的な対応をしているので再設計要


