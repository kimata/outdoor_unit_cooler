# ❄️ outdoor-unit-cooler

Raspberry Pi を使ったエアコン室外機自動冷却システム

[![Regression](https://github.com/kimata/outdoor_unit_cooler/actions/workflows/regression.yaml/badge.svg)](https://github.com/kimata/outdoor_unit_cooler/actions/workflows/regression.yaml)

## 📋 概要

エアコンの消費電力をリアルタイムで監視し、運転開始を検知すると自動的に室外機へのミスト噴射を行うスマートな冷却システムです。間欠的なミスト噴射により室外機の熱交換効率を向上させ、エアコンの消費電力を削減します。

### 主な特徴

- ❄️ **自動制御** - エアコンの稼働状況を自動検知してミスト噴射を制御
- 💧 **効率的な冷却** - 連続噴射ではなく間欠噴射で効果的に室外機を冷却
- 🔍 **異常検知** - 流量計による水漏れ・元栓の開閉状態監視
- 📊 **リアルタイム監視** - Web UIでシステム状況をリアルタイム表示
- 📱 **通知機能** - Slackを通じたエラー通知とアラート
- 🏠 **省エネルギー** - 室外機の熱交換効率向上により消費電力を削減
- 🔧 **メンテナンスフリー** - 全自動運転で人手を必要としない

## 🖼️ スクリーンショット

![システム構成](./img/システム構成.png)

## 🎮 デモ

実際の動作を体験できるデモサイト：

🔗 https://unit-cooler-webui-demo.kubernetes.green-rabbit.net/unit_cooler/

## 🏗️ システム構成

### アーキテクチャ

![ソフトアーキ図](./img/ソフトアーキ図.png)

システムは3つの主要コンポーネントで構成：

1. **Controller（コントローラ）** - InfluxDBから消費電力データを監視し、制御信号を生成
2. **Actuator（アクチュエータ）** - 電磁弁を制御し、水流量を監視
3. **Web UI** - システム状況の可視化とログ表示

### 技術スタック

#### フロントエンド
- **フレームワーク**: React 18
- **UIライブラリ**: Bootstrap + React Bootstrap
- **ビルドツール**: Vite
- **言語**: TypeScript/JavaScript

#### バックエンド
- **フレームワーク**: Flask (Python)
- **パッケージマネージャー**: uv (高速・モダン)
- **通信**: ZeroMQ (プロセス間通信)
- **データベース**: InfluxDB (センサーデータ), SQLite (ログ)

#### ハードウェア
- **制御**: Raspberry Pi + GPIO制御
- **センサー**: 流量センサー (FD-Q10C)
- **アクチュエータ**: 電磁弁 (DC12V)

## 🚀 セットアップ

### 必要な環境

- Raspberry Pi (GPIO制御が可能なモデル)
- Python 3.12+
- Node.js 20.x
- Docker (オプション)

### 1. リポジトリのクローン

```bash
git clone https://github.com/kimata/outdoor_unit_cooler.git
cd outdoor_unit_cooler
```

### 2. Raspberry Pi の設定

#### ハードウェアインターフェースの有効化

`/boot/firmware/config.txt` に下記の設定を追加：

```text
# SPIインターフェースを有効化（流量センサー用）
dtparam=spi=on

# Bluetoothを無効化（シリアルポート競合回避）
dtoverlay=disable-bt
```

#### シリアルコンソールの無効化

`/boot/firmware/cmdline.txt` から `console=serial0,115200` および `console=ttyAMA0,115200` の指定を削除。

#### GPIOアクセス権限の設定

```bash
# GPIOグループにユーザーを追加
sudo usermod -a -G gpio $USER

# 再起動して設定を反映
sudo reboot
```

### 3. 設定ファイルの準備

```bash
cp config.example.yaml config.yaml
# config.yaml を環境に合わせて編集
```

設定項目の例：
- InfluxDB接続設定（センサーデータの保存先）
- GPIO設定（電磁弁制御用のピン番号）
- Slack設定（エラー通知用）
- 流量センサー設定（異常検知の閾値）

## 💻 実行方法

### Docker を使用する場合（推奨）

```bash
# フロントエンドのビルド
cd react
npm ci
npm run build
cd ..

# Docker Composeで起動
docker-compose up -d

# ログの確認
docker-compose logs -f
```

### Docker を使用しない場合

#### uv を使用（推奨）

```bash
# uvのインストール（未インストールの場合）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 依存関係のインストール
uv sync

# Controller（任意のLinux環境で実行可能）
uv run python ./src/controller.py -c config.yaml

# Actuator（Raspberry Piで実行）
uv run python ./src/actuator.py -c config.yaml

# Web UI（任意のLinux環境で実行可能）
uv run python ./src/webui.py -c config.yaml
```

### 開発モード

```bash
# フロントエンド開発サーバー
cd react
npm start

# バックエンド（デバッグモード）
uv run python ./src/webui.py -c config.yaml -D

# ダミーモード（ハードウェアなしでテスト）
uv run python ./src/actuator.py -c config.yaml -d
```

## 🧪 テスト

```bash
# Pythonテスト（カバレッジ付き）
uv run pytest

# 特定のテストファイルを実行
uv run pytest tests/test_basic.py tests/test_error_handling.py

# 並列実行でテスト高速化
uv run pytest --numprocesses=auto

# E2Eテスト（Playwright）
uv run pytest tests/test_playwright.py
```

テスト結果：
- HTMLレポート: `tests/evidence/index.htm`
- カバレッジ: `tests/evidence/coverage/`
- E2E録画: `tests/evidence/test_*/`

## 🎯 API エンドポイント

### システム状態
- `GET /unit_cooler/api/status` - システム全体の状態取得
- `GET /unit_cooler/api/sensor` - センサーデータ取得

### 制御
- `POST /unit_cooler/api/valve_ctrl` - 電磁弁の手動制御
- `GET /unit_cooler/api/mode` - 動作モード取得/設定

### ログ・履歴
- `GET /unit_cooler/api/log` - システムログ取得
- `GET /unit_cooler/api/log_view` - ログビューア

## ☸️ Kubernetes デプロイ

Kubernetes用の設定ファイルが含まれています：

```bash
# namespaceの作成
kubectl create namespace hems

# デプロイ
kubectl apply -f kubernetes/outdoor_unit_cooler.yml

# 状態確認
kubectl get pods -n hems
kubectl logs -n hems -l app=outdoor-unit-cooler
```

詳細は設定ファイルをカスタマイズしてご利用ください。

## 🔧 トラブルシューティング

### よくある問題

#### 電磁弁が動作しない
- **GPIO権限不足**: `sudo usermod -a -G gpio $USER` を実行後、再起動
- **配線確認**: GPIO17番ピンと電磁弁の接続を確認
- **設定確認**: `config.yaml` の `actuator.gpio.valve_pin` をチェック

#### 流量センサーが読み取れない
- **シリアルポート競合**: Bluetoothが無効化されているか確認
- **権限不足**: `/dev/ttyAMA0` へのアクセス権限を確認

#### Web UIにアクセスできない
- **ポート確認**: デフォルトポート5000が開いているか確認
- **サービス確認**: `docker-compose ps` でサービス起動状況を確認

### ログ確認

```bash
# Dockerの場合
docker-compose logs -f controller
docker-compose logs -f actuator
docker-compose logs -f webui

# ネイティブ実行の場合
# 各コンポーネントのログは標準出力に表示
```

## 📊 CI/CD

GitHub Actions によるCI/CDパイプライン：
- テスト結果: https://kimata.github.io/outdoor_unit_cooler/
- カバレッジレポート: https://kimata.github.io/outdoor_unit_cooler/coverage/

## 📝 ライセンス

このプロジェクトは MIT License のもとで公開されています。

---

<div align="center">

**⭐ このプロジェクトが役に立った場合は、Star をお願いします！**

[🐛 Issue 報告](https://github.com/kimata/outdoor_unit_cooler/issues) | [💡 Feature Request](https://github.com/kimata/outdoor_unit_cooler/issues/new?template=feature_request.md) | [📖 詳細なドキュメント](./docs)

</div>
