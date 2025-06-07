# エアコン室外機冷却システム

![システム構成](./img/システム構成.png)

## 目次

- [概要](#概要)
  - [主な特徴](#主な特徴)
  - [システムの効果](#システムの効果)
  - [動作原理](#動作原理)
- [デモ](#デモ)
- [システム構成](#システム構成)
  - [全体構成](#全体構成)
  - [ソフトウェアアーキテクチャ](#ソフトウェアアーキテクチャ)
  - [データフロー](#データフロー)
- [技術仕様](#技術仕様)
  - [使用技術](#使用技術)
  - [システム要件](#システム要件)
  - [動作環境](#動作環境)
- [セットアップ](#セットアップ)
  - [リポジトリのクローン](#リポジトリのクローン)
  - [Raspberry Pi の設定](#raspberry-pi-の設定)
  - [設定ファイルの準備](#設定ファイルの準備)
- [実行方法](#実行方法)
  - [Dockerを使用した実行](#dockerを使用した実行)
  - [ネイティブ環境での実行](#ネイティブ環境での実行)
  - [Kubernetesへのデプロイ](#kubernetesへのデプロイ)
- [設定ファイルの詳細](#設定ファイルの詳細)
- [トラブルシューティング](#トラブルシューティング)
  - [よくある問題と解決方法](#よくある問題と解決方法)
  - [ログの確認方法](#ログの確認方法)
  - [ハードウェアのテスト](#ハードウェアのテスト)
- [開発とテスト](#開発とテスト)
  - [テストの実行](#テストの実行)
  - [テスト結果とカバレッジ](#テスト結果とカバレッジ)
- [ライセンス](#ライセンス)
- [作者](#作者)

## 概要

エアコンが動作を開始すると自動的に室外機へのミスト噴射を行うシステムです。
消費電力をリアルタイムで監視し、室外機の運転状況に応じて自動的にミスト噴射を制御することで、エアコンの効率を向上させ消費電力を削減します。

### 主な特徴

- **自動制御**: エアコンの稼働状況を自動検知してミスト噴射を制御
- **効率的な冷却**: 連続噴射ではなく、ON/OFFを繰り返す間欠噴射で効果的に冷却
- **異常検知**: 流量計による水漏れ・元栓の開閉状態監視
- **リアルタイム監視**: Web UIでシステム状況をリアルタイム表示
- **通知機能**: Slackを通じたエラー通知

### システムの効果

- **省エネルギー**: 室外機の熱交換効率を向上させ、消費電力を削減
- **メンテナンスフリー**: 全自動運転で人手を必要としない
- **高い信頼性**: 異常検知機能により水漏れなどのトラブルを未然に防止
- **スケーラビリティ**: 複数のエアコンに対応可能

### 動作原理

1. **電力監視**: InfluxDBに蓄積されたエアコンの消費電力データをリアルタイムで監視
2. **状態判定**: 消費電力の変化パターンからエアコンの運転状態（冷房/暖房/停止）を判定
3. **制御判断**: 外気温度や運転モードに基づいてミスト噴射の必要性を判断
4. **ミスト制御**: 間欠的なミスト噴射により効率的に室外機を冷却
5. **フィードバック**: 流量センサーにより実際の噴射状況を監視し、異常を検知

## デモ

エアコンの稼働状況に応じてミスト噴射モードが自動的に変化する様子を確認いただけます。

https://unit-cooler-webui-demo.kubernetes.green-rabbit.net/unit_cooler/

## システム構成

### 全体構成

システムは以下の3つの主要コンポーネントで構成されています：

1. **Controller（コントローラ）**: 消費電力データを監視し、制御信号を生成
2. **Actuator（アクチュエータ）**: 電磁弁を制御し、水流を監視
3. **Web UI**: システム状況の可視化とログ表示

### ソフトウェアアーキテクチャ

![ソフトアーキ図](./img/ソフトアーキ図.png)

システムは以下の4つのワーカースレッドで動作します：

- **Cooler controller**: センサーデータを分析し制御判断を実行
- **Command receive worker**: ZeroMQ経由で制御メッセージを受信
- **Valve control worker**: 受信したコマンドに基づいて電磁弁を制御
- **Valve monitor worker**: 水流を監視し異常を検知

### データフロー

1. InfluxDBから消費電力データを取得
2. エアコンの稼働状況を判定
3. 必要に応じてミスト噴射コマンドを生成
4. ZeroMQ経由でアクチュエータに送信
5. 電磁弁を制御してミスト噴射を実行
6. 流量センサーで実際の水流を監視

## 技術仕様

### 使用技術

- **言語**: Python 3
- **フレームワーク**: Flask（Web UI）、React（フロントエンド）
- **通信**: ZeroMQ（プロセス間通信）
- **データベース**: InfluxDB（センサーデータ）、SQLite（ログ）
- **ハードウェア**: Raspberry Pi、GPIO制御
- **通知**: Slack API

### システム要件

#### ハードウェア要件

- Raspberry Pi（GPIO、SPI対応）
- 電磁弁（DC12V）
- 流量センサー（FD-Q10C）
- 水道設備

#### ソフトウェア要件

- Python 3.8+
- Node.js 16+（フロントエンド開発時）
- Docker & Docker Compose（推奨）

### 動作環境

- **Controller**: 任意のLinux/Unix環境
- **Actuator**: Raspberry Pi（ハードウェア制御のため）
- **Web UI**: 任意のLinux/Unix環境

## セットアップ

### リポジトリのクローン

```bash
git clone https://github.com/kimata/outdoor_unit_cooler.git
cd outdoor_unit_cooler
```

### Raspberry Pi の設定

`src/actuator.py` を配置する Raspberry Pi で以下の設定を行います。

#### ハードウェアインターフェースの有効化

`/boot/firmware/config.txt` に下記の設定を追加します：

```text
# SPIインターフェースを有効化（流量センサー用）
dtparam=spi=on

# Bluetoothを無効化（シリアルポート競合回避）
dtoverlay=disable-bt
```

#### シリアルコンソールの無効化

`/boot/firmware/cmdline.txt` から `console=serial0,115200` および `console=ttyAMA0,115200` の指定を削除します。

#### GPIOアクセス権限の設定

```bash
# GPIOグループにユーザーを追加
sudo usermod -a -G gpio $USER

# 再起動して設定を反映
sudo reboot
```

### 設定ファイルの準備

```bash
# 設定ファイルをコピー
cp config.example.yaml config.yaml

# 環境に合わせて編集
nano config.yaml
```

主な設定項目：
- **InfluxDB接続設定**: センサーデータの保存先
- **GPIO設定**: 電磁弁制御用のピン番号（デフォルト: 17）
- **Slack設定**: エラー通知用（使用しない場合はコメントアウト）
- **流量センサー設定**: 異常検知の閾値

## 実行方法

### Dockerを使用した実行

#### Dockerイメージのビルド

```bash
# Buildkitを使用して高速ビルド
DOCKER_BUILDKIT=1 docker build -t outdoor_unit_cooler .
```

#### Docker Composeで起動

```bash
# すべてのサービスを起動
docker-compose up -d

# 個別のサービスを起動
docker-compose up -d controller  # コントローラのみ
docker-compose up -d actuator    # アクチュエータのみ
docker-compose up -d webui       # Web UIのみ
```

#### ログの確認

```bash
# すべてのサービスのログを表示
docker-compose logs -f

# 特定のサービスのログを表示
docker-compose logs -f controller
```

### ネイティブ環境での実行

#### Python環境のセットアップ

```bash
curl -sSf https://rye-up.com/get | bash
rye sync
```

#### 各コンポーネントの起動

```bash
# Controller（任意のLinux環境で実行可能）
rye run python ./src/controller.py -c config.yaml

# Actuator（Raspberry Piで実行）
rye run python ./src/actuator.py -c config.yaml

# Web UI（任意のLinux環境で実行可能）
rye run python ./src/webui.py -c config.yaml
```

### Kubernetesへのデプロイ

#### 設定ファイルのカスタマイズ

`kubernetes/outdoor_unit_cooler.yml` を環境に合わせて編集：

```yaml
# namespace（デフォルト: hems）
metadata:
  namespace: your-namespace

# ExternalDNSホスト名（不要なら削除）
annotations:
  external-dns.alpha.kubernetes.io/hostname: your-hostname.example.com

# コンテナイメージ
spec:
  containers:
  - image: your-registry/outdoor_unit_cooler:latest

# ノードセレクター（Actuator用）
nodeSelector:
  kubernetes.io/hostname: your-raspberry-pi-node
```

#### デプロイ

```bash
# namespaceの作成
kubectl create namespace hems

# デプロイ
kubectl apply -f kubernetes/outdoor_unit_cooler.yml

# 状態確認
kubectl get pods -n hems
kubectl logs -n hems -l app=outdoor-unit-cooler
```

## 設定ファイルの詳細

### config.yaml の主要セクション

#### controller セクション
```yaml
controller:
  influxdb:
    url: "http://influxdb:8086"
    org: "your-org"
    token: "your-token"
    bucket: "sensor_data"

  watering:
    power_threshold: 100  # エアコン稼働判定の電力閾値(W)
    duration: 30          # ミスト噴射時間(秒)
    interval: 90          # 噴射間隔(秒)
```

#### actuator セクション
```yaml
actuator:
  gpio:
    valve_pin: 17         # 電磁弁制御用GPIOピン

  flow_sensor:
    port: "/dev/ttyAMA0"  # シリアルポート
    threshold_min: 0.5    # 最小流量閾値(L/min)
    threshold_max: 10.0   # 最大流量閾値(L/min)
```

#### webui セクション
```yaml
webui:
  host: "0.0.0.0"
  port: 5000
  debug: false
```

## トラブルシューティング

### よくある問題と解決方法

#### 1. 電磁弁が動作しない

**症状**: コマンドを送信しても電磁弁が開かない

**原因と対策**:
- **GPIO権限不足**: `sudo usermod -a -G gpio $USER` を実行後、再起動
- **配線ミス**: GPIO17番ピンと電磁弁の接続を確認
- **設定ミス**: `config.yaml` の `actuator.gpio.valve_pin` が正しいか確認

#### 2. 流量センサーが読み取れない

**症状**: 流量が常に0または異常値を示す

**原因と対策**:
- **シリアルポート競合**: Bluetoothが無効化されているか確認
- **権限不足**: `/dev/ttyAMA0` へのアクセス権限を確認

#### 3. Web UIにアクセスできない

**症状**: ブラウザでWeb UIが表示されない

**原因と対策**:
- **ポート設定**: デフォルトポート5000が開いているか確認
- **Dockerネットワーク**: `docker-compose ps` でサービスが起動しているか確認

#### 4. InfluxDBに接続できない

**症状**: センサーデータが記録されない

**原因と対策**:
- **接続設定**: `config.yaml` のInfluxDB URLが正しいか確認
- **認証情報**: トークンとorganization名が正しいか確認
- **ネットワーク**: InfluxDBサーバーへの接続性を確認
- **バケット名**: 指定したバケットが存在するか確認

#### 5. Slack通知が届かない

**症状**: エラーが発生してもSlack通知が来ない

**原因と対策**:
- **Webhook URL**: Slack Webhook URLが正しく設定されているか確認
- **設定確認**: `config.yaml` でSlack設定がコメントアウトされていないか確認

### ログの確認方法

#### Dockerの場合
```bash
# 全サービスのログ
docker-compose logs -f

# 特定サービスのログ
docker-compose logs -f controller
docker-compose logs -f actuator
docker-compose logs -f webui
```

### ハードウェアのテスト

#### GPIO動作確認
```bash
# GPIOの状態確認
gpio readall

# 手動で電磁弁をテスト（GPIO17を使用）
echo "17" > /sys/class/gpio/export
echo "out" > /sys/class/gpio/gpio17/direction
echo "1" > /sys/class/gpio/gpio17/value  # 開
sleep 5
echo "0" > /sys/class/gpio/gpio17/value  # 閉
```

## 開発とテスト

### テストの実行

```bash
# 全テストを実行
pytest

# カバレッジレポート付きで実行
pytest --cov=src --cov-report=html
```

### テスト結果とカバレッジ

- テスト結果: https://kimata.github.io/outdoor_unit_cooler/
- カバレッジレポート: https://kimata.github.io/outdoor_unit_cooler/coverage/

## ライセンス

このプロジェクトはMITライセンスのもとで公開されています。

## 作者

- [@kimata](https://github.com/kimata)
