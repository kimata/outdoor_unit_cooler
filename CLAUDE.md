# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 室外機自動冷却システム

Raspberry Piを使用したエアコン室外機の自動冷却システム。InfluxDBからの電力データを監視し、エアコン稼働を検知すると自動的にミスト噴射を制御する省エネソリューション。

## コア開発コマンド

### セットアップ・開発

```bash
# Python依存関係インストール
uv sync

# React開発サーバー（localhost:3000）
cd react && npm start

# Pythonアプリケーション実行（開発モード）
uv run python ./src/webui.py -c config.yaml -D

# Docker Compose起動
docker-compose up -d
```

### テスト

```bash
# 全テスト実行
uv run pytest

# 並列テスト実行（高速化）
uv run pytest --numprocesses=auto

# 特定テストファイル実行
uv run pytest tests/test_webui.py

# E2Eテスト（Playwright）
uv run pytest tests/test_playwright.py

# Reactビルド
cd react && npm run build

# テストカバレッジ（HTMLレポート生成）
uv run pytest --cov=src --cov-report=html
```

### ビルド・デプロイ

```bash
# Reactアプリケーションビルド
cd react && npm ci && npm run build

# Dockerマルチアーキテクチャビルド
docker buildx build --platform linux/amd64,linux/arm64/v8 --push .

# Kubernetesデプロイ
kubectl apply -f kubernetes/outdoor_unit_cooler.yml
```

## アーキテクチャ概要

### 3層構成

1. **Controller** (`src/controller.py`) - InfluxDBデータ取得・ZeroMQ制御信号配信
2. **Actuator** (`src/actuator.py`) - Raspberry Pi GPIO制御・電磁弁操作
3. **Web UI** (`src/webui.py`) - Flask API + React フロントエンド

### プロセス間通信

- **ZeroMQ Publisher-Subscriber**パターンでリアルタイム分散メッセージング
- **Last Value Caching Proxy**による信頼性向上
- ポート: 5559（Controller→Actuator）, 5560（Web UI→Frontend）

### 技術スタック

- **バックエンド**: Python 3.12, Flask, ZeroMQ, InfluxDB client, rpi-lgpio
- **フロントエンド**: React 19 + TypeScript, Vite, Bootstrap, Chart.js, Framer Motion
- **テスト**: pytest, Playwright, pytest-cov
- **インフラ**: Docker, Kubernetes, GitLab CI

## 重要なファイル構造

### 設定ファイル

- `config.example.yaml` - メインアプリケーション設定
- `pyproject.toml` - Python依存関係・テスト設定
- `react/package.json` - React依存関係
- `compose.yaml` - Dockerサービス定義

### 主要コンポーネント

- `src/unit_cooler/` - コアビジネスロジック
- `react/src/components/` - React UIコンポーネント
- `tests/` - テストスイート
- `kubernetes/` - K8sデプロイメント設定

## 開発時の注意点

### テスト実行順序

- `pytest.mark.order`でテスト順序最適化済み
- `tests/test_webui.py`が最重要（20秒実行時間）

### React開発

- アニメーション間隔: 30秒（AnimatedNumber, AirConditioner）
- データ更新間隔: 58秒（useApi）
- Vite最適化設定でバンドル分割

### ハードウェア依存

- 流量センサー（FD-Q10C）: SPI通信
- GPIO制御: 電磁弁、LED
- テスト時はモックを使用（`tests/conftest.py`）

### Docker・K8s

- マルチアーキテクチャ対応（AMD64, ARM64）
- 特権モード必要（GPIO/SPIアクセス）
- MetalLB LoadBalancer統合

## データフロー

1. InfluxDB → Controller → ZeroMQ → Actuator
2. Actuator → センサーデータ → SQLite/InfluxDB
3. Web UI → REST API → React Frontend
4. リアルタイム更新: EventSource/Server-Sent Events

## 依存関係管理

- **uv**: Python高速パッケージマネージャー
- **my-lib**: カスタムライブラリ（git+https://github.com/kimata/my-py-lib）
- **Renovate**: 自動依存関係更新（毎週末）
