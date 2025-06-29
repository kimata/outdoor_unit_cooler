#!/bin/bash
# 室外機冷却システム監視機能導入スクリプト
# 既存システムに影響を与えない非侵襲的な監視システムを導入

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 室外機冷却システム監視機能導入スクリプト"
echo "==============================================="

# オプション解析
DEPLOY_MODE="basic"
FORCE_RECREATE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --basic)
            DEPLOY_MODE="basic"
            shift
            ;;
        --full)
            DEPLOY_MODE="full"
            shift
            ;;
        --advanced)
            DEPLOY_MODE="advanced"
            shift
            ;;
        --force)
            FORCE_RECREATE=true
            shift
            ;;
        --help)
            echo "使用方法:"
            echo "  $0 [オプション]"
            echo ""
            echo "オプション:"
            echo "  --basic     基本監視のみ（デフォルト）"
            echo "  --full      Prometheus + Grafana付き完全版"
            echo "  --advanced  機械学習異常検知付き"
            echo "  --force     既存コンテナを強制再作成"
            echo "  --help      このヘルプを表示"
            exit 0
            ;;
        *)
            echo "不明なオプション: $1"
            echo "$0 --help でヘルプを表示"
            exit 1
            ;;
    esac
done

echo "📋 導入モード: $DEPLOY_MODE"

# 必要なファイルの存在確認
echo "📁 必要なファイルの確認中..."

required_files=(
    "src/monitoring_agent.py"
    "monitoring_config.yaml"
    "monitoring.Dockerfile"
    "monitoring-compose.yml"
)

for file in "${required_files[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo "❌ 必要なファイルが見つかりません: $file"
        exit 1
    fi
    echo "✅ $file"
done

# Docker/Docker Composeの確認
echo "🐳 Docker環境の確認中..."
if ! command -v docker &> /dev/null; then
    echo "❌ Dockerがインストールされていません"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Composeがインストールされていません"
    exit 1
fi

echo "✅ Docker環境OK"

# 既存サービスの確認
echo "🔍 既存サービスの確認中..."
if docker ps --format "table {{.Names}}" | grep -q "unit-cooler"; then
    echo "✅ 既存のunit-coolerサービスが動作中"
else
    echo "⚠️  既存のunit-coolerサービスが見つかりません"
    echo "   先に既存システムを起動してください: docker-compose up -d"
fi

# 既存の監視コンテナの停止（必要に応じて）
if docker ps -a --format "table {{.Names}}" | grep -q "unit-cooler-monitoring"; then
    if [[ "$FORCE_RECREATE" == "true" ]]; then
        echo "🛑 既存の監視コンテナを停止中..."
        docker stop unit-cooler-monitoring || true
        docker rm unit-cooler-monitoring || true
    else
        echo "⚠️  既存の監視コンテナが存在します"
        echo "   強制再作成する場合は --force オプションを使用してください"
    fi
fi

# 設定ファイルのカスタマイズ確認
echo "⚙️  設定ファイルの確認..."
if [[ -f "monitoring_config.yaml" ]]; then
    echo "✅ 設定ファイル: monitoring_config.yaml"
    echo "   カスタマイズが必要な場合は編集してください"
else
    echo "❌ 設定ファイルが見つかりません"
    exit 1
fi

# Prometheusメトリクス取得用設定作成（fullモード用）
if [[ "$DEPLOY_MODE" == "full" || "$DEPLOY_MODE" == "advanced" ]]; then
    echo "📊 Prometheus設定ファイルを作成中..."

    cat > prometheus.yml << 'EOF'
global:
  scrape_interval: 60s
  evaluation_interval: 60s

scrape_configs:
  - job_name: 'unit-cooler-monitoring'
    static_configs:
      - targets: ['unit-cooler-monitoring:8081']
    metrics_path: '/metrics/prometheus'
    scrape_interval: 60s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['unit-cooler-monitoring:8081']
    metrics_path: '/metrics/system'
    scrape_interval: 30s
EOF

    echo "✅ prometheus.yml を作成しました"
fi

# Docker イメージのビルド
echo "🔨 監視用Dockerイメージをビルド中..."
if docker build -f monitoring.Dockerfile -t unit-cooler-monitoring:latest .; then
    echo "✅ Dockerイメージビルド完了"
else
    echo "❌ Dockerイメージのビルドに失敗しました"
    exit 1
fi

# サービス起動
echo "🚀 監視サービスを起動中..."

case $DEPLOY_MODE in
    "basic")
        echo "   基本監視モードで起動..."
        docker-compose -f monitoring-compose.yml up -d unit-cooler-monitoring
        ;;
    "full")
        echo "   完全監視モード（Prometheus + Grafana）で起動..."
        docker-compose -f monitoring-compose.yml --profile monitoring-full up -d
        ;;
    "advanced")
        echo "   高度監視モード（機械学習付き）で起動..."
        # 高度な設定をONにする
        sed -i 's/enabled: false/enabled: true/g' monitoring_config.yaml
        docker-compose -f monitoring-compose.yml --profile monitoring-full up -d
        ;;
esac

# 起動確認
echo "⏳ サービス起動確認中..."
sleep 10

if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "unit-cooler-monitoring.*Up"; then
    echo "✅ 監視サービスが正常に起動しました"
else
    echo "❌ 監視サービスの起動に失敗しました"
    echo "ログを確認してください: docker logs unit-cooler-monitoring"
    exit 1
fi

# 動作確認
echo "🔍 動作確認中..."

# メトリクスファイルの確認
if docker exec unit-cooler-monitoring test -f /tmp/unit_cooler_monitoring/metrics.json; then
    echo "✅ メトリクス収集が動作中"
else
    echo "⚠️  メトリクスファイルがまだ作成されていません（起動直後のため正常）"
fi

# アクセス情報の表示
echo ""
echo "🎉 監視システムの導入が完了しました！"
echo "==========================================="
echo ""
echo "📊 アクセス情報:"
echo "  メトリクス確認:        http://localhost:8081/metrics/json"
echo "  Prometheus形式:        http://localhost:8081/metrics/prometheus"

if [[ "$DEPLOY_MODE" == "full" || "$DEPLOY_MODE" == "advanced" ]]; then
    echo "  Prometheus:           http://localhost:9090"
    echo "  Grafana:             http://localhost:3000 (admin/admin123)"
fi

echo ""
echo "📁 監視データ:"
echo "  メトリクスファイル:    /tmp/unit_cooler_monitoring/metrics.json"
echo "  アラートファイル:      /tmp/unit_cooler_monitoring/alerts.json"
echo "  Prometheus形式:       /tmp/unit_cooler_monitoring/metrics.prom"
echo ""
echo "🔧 管理コマンド:"
echo "  ログ確認:             docker logs unit-cooler-monitoring"
echo "  監視停止:             docker-compose -f monitoring-compose.yml down"
echo "  監視再起動:           docker-compose -f monitoring-compose.yml restart unit-cooler-monitoring"
echo "  設定変更後の再起動:    docker-compose -f monitoring-compose.yml up -d --force-recreate unit-cooler-monitoring"
echo ""
echo "⚙️  設定変更:"
echo "  設定ファイル:         monitoring_config.yaml"
echo "  変更後は再起動が必要です"
echo ""

# 簡単な動作テスト
echo "🧪 簡単な動作テストを実行中..."
sleep 5

# メトリクス取得テスト
if curl -s -f http://localhost:8081/metrics/json > /dev/null 2>&1; then
    echo "✅ HTTP APIが正常に動作しています"
elif docker exec unit-cooler-monitoring test -f /tmp/unit_cooler_monitoring/metrics.json; then
    echo "✅ ファイルベースでメトリクス収集が動作しています"
else
    echo "⚠️  まだメトリクス収集が開始されていません（数分後に確認してください）"
fi

echo ""
echo "✅ 導入完了！監視システムが既存システムとは独立して動作しています。"
