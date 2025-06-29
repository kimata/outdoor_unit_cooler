"""アクチュエータのメトリクス情報を公開するAPI"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import flask
import my_lib.flask_util
import my_lib.footprint
import my_lib.webapp.config

import unit_cooler.actuator.sensor
import unit_cooler.actuator.valve
import unit_cooler.const

# グローバルメトリクス管理
_metrics_lock = threading.Lock()
_metrics_data = {
    "valve_operations": 0,
    "sensor_reads": 0,
    "errors": 0,
    "warnings": 0,
    "last_valve_operation": None,
    "last_sensor_read": None,
    "last_error": None,
    "uptime_start": time.time(),
    # バルブ稼働時間関連
    "valve_on_total_seconds": 0.0,
    "valve_on_session_count": 0,
    "valve_last_on_time": None,
    "valve_current_state": "CLOSE",
    "valve_session_times": [],  # 最新10セッションの記録
}

blueprint = flask.Blueprint("metrics", __name__, url_prefix=my_lib.webapp.config.URL_PREFIX)

logger = logging.getLogger(__name__)

# データベース設定
_db_path = None
_db_lock = threading.Lock()


def init_metrics_db():
    """メトリクスデータベースの初期化"""
    global _db_path  # noqa: PLW0603

    try:
        # Flaskアプリのconfigからパスを取得
        config = flask.current_app.config.get("CONFIG", {})
        _db_path = (
            config.get("actuator", {})
            .get("log_server", {})
            .get("webapp", {})
            .get("data", {})
            .get("metrics_db_path")
        )

        if not _db_path:
            logger.warning("metrics_db_path not configured, using default")
            _db_path = "data/metrics.db"

        # データベースファイルのディレクトリを作成
        db_path = Path(_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # テーブル作成
        with _db_lock:
            conn = sqlite3.connect(_db_path)
            cursor = conn.cursor()

            # メトリクステーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    valve_operations INTEGER DEFAULT 0,
                    sensor_reads INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    warnings INTEGER DEFAULT 0,
                    valve_on_total_seconds REAL DEFAULT 0,
                    valve_session_count INTEGER DEFAULT 0,
                    valve_duty_cycle_percentage REAL DEFAULT 0,
                    valve_current_state TEXT DEFAULT 'CLOSE',
                    valve_hardware_state TEXT DEFAULT 'CLOSE',
                    valve_duration_sec INTEGER DEFAULT 0,
                    flow_value REAL NULL,
                    sensor_power_state BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # インデックス作成
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_created_at ON metrics(created_at)")

            conn.commit()
            conn.close()

        logger.info("Metrics database initialized: %s", _db_path)

    except Exception:
        logger.exception("Error initializing metrics database")
        _db_path = None


def save_metrics_to_db(metrics_data: dict[str, Any]):
    """メトリクスをデータベースに保存"""
    global _db_path

    if not _db_path:
        return

    try:
        with _db_lock:
            conn = sqlite3.connect(_db_path)
            cursor = conn.cursor()

            # メトリクスデータを抽出
            counters = metrics_data.get("counters", {})
            valve_timing = metrics_data.get("valve_timing", {})
            actuator = metrics_data.get("actuator", {})

            valve_info = actuator.get("valve", {})
            sensor_info = actuator.get("sensor", {})

            # データベースに挿入
            cursor.execute(
                """
                INSERT INTO metrics (
                    timestamp,
                    valve_operations,
                    sensor_reads,
                    errors,
                    warnings,
                    valve_on_total_seconds,
                    valve_session_count,
                    valve_duty_cycle_percentage,
                    valve_current_state,
                    valve_hardware_state,
                    valve_duration_sec,
                    flow_value,
                    sensor_power_state
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    metrics_data.get("timestamp", time.time()),
                    counters.get("valve_operations", 0),
                    counters.get("sensor_reads", 0),
                    counters.get("errors", 0),
                    counters.get("warnings", 0),
                    valve_timing.get("total_on_seconds", 0),
                    valve_timing.get("session_count", 0),
                    valve_timing.get("duty_cycle_percentage", 0),
                    valve_timing.get("current_state", "CLOSE"),
                    valve_info.get("state", "CLOSE"),
                    valve_info.get("duration_sec", 0),
                    sensor_info.get("flow_value"),
                    sensor_info.get("power_state", True),
                ),
            )

            conn.commit()
            conn.close()

            logger.debug("Metrics saved to database")

    except Exception:
        logger.exception("Error saving metrics to database")


def get_metrics_from_db(hours: int = 24) -> list:
    """データベースからメトリクスを取得"""
    global _db_path

    if not _db_path:
        return []

    try:
        with _db_lock:
            conn = sqlite3.connect(_db_path)
            cursor = conn.cursor()

            # 過去N時間のデータを取得
            since_timestamp = time.time() - (hours * 3600)

            cursor.execute(
                """
                SELECT
                    timestamp,
                    valve_operations,
                    sensor_reads,
                    errors,
                    warnings,
                    valve_on_total_seconds,
                    valve_session_count,
                    valve_duty_cycle_percentage,
                    valve_current_state,
                    valve_hardware_state,
                    valve_duration_sec,
                    flow_value,
                    sensor_power_state,
                    created_at
                FROM metrics
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 1000
            """,
                (since_timestamp,),
            )

            rows = cursor.fetchall()
            conn.close()

            # 辞書形式に変換
            columns = [
                "timestamp",
                "valve_operations",
                "sensor_reads",
                "errors",
                "warnings",
                "valve_on_total_seconds",
                "valve_session_count",
                "valve_duty_cycle_percentage",
                "valve_current_state",
                "valve_hardware_state",
                "valve_duration_sec",
                "flow_value",
                "sensor_power_state",
                "created_at",
            ]

            return [dict(zip(columns, row, strict=True)) for row in rows]

    except Exception:
        logger.exception("Error reading metrics from database")
        return []


@blueprint.route("/api/metrics/history", methods=["GET"])
@my_lib.flask_util.support_jsonp
def get_metrics_history():
    """過去のメトリクス履歴を取得"""
    try:
        # クエリパラメータから時間範囲を取得
        hours = int(flask.request.args.get("hours", 24))
        limit = int(flask.request.args.get("limit", 1000))

        # データベースから取得
        history_data = get_metrics_from_db(hours)

        # 必要に応じて制限
        if len(history_data) > limit:
            history_data = history_data[:limit]

        response = {
            "timestamp": time.time(),
            "hours": hours,
            "count": len(history_data),
            "data": history_data,
        }

        return flask.jsonify(response)

    except Exception as e:
        logger.exception("Error getting metrics history")
        return flask.jsonify({"error": str(e), "timestamp": time.time()}), 500


def increment_metric(metric_name: str, details: dict[str, Any] | None = None):
    """メトリクスカウンタを増加させる"""
    with _metrics_lock:
        if metric_name in _metrics_data:
            _metrics_data[metric_name] += 1

        # 詳細情報を記録
        timestamp = time.time()
        if metric_name == "valve_operations":
            _metrics_data["last_valve_operation"] = {"timestamp": timestamp, "details": details or {}}
        elif metric_name == "sensor_reads":
            _metrics_data["last_sensor_read"] = {"timestamp": timestamp, "details": details or {}}
        elif metric_name == "errors":
            _metrics_data["last_error"] = {"timestamp": timestamp, "details": details or {}}


def get_actuator_specific_metrics() -> dict[str, Any]:
    """アクチュエータ固有のメトリクスを収集（システム情報は別API利用）"""
    try:
        # バルブ状態の取得
        valve_status = unit_cooler.actuator.valve.get_status()
        valve_state = valve_status["state"].name
        valve_duration = valve_status["duration"]

        # フロー情報の取得
        flow = unit_cooler.actuator.sensor.get_flow(force_power_on=False)
        sensor_power_state = unit_cooler.actuator.sensor.get_power_state()

        # ファイルベースのステータス情報
        stat_dir = Path("/dev/shm/unit_cooler")  # noqa: S108
        valve_working = my_lib.footprint.exists(unit_cooler.actuator.valve.STAT_PATH_VALVE_STATE_WORKING)
        valve_idle = my_lib.footprint.exists(unit_cooler.actuator.valve.STAT_PATH_VALVE_STATE_IDLE)

        # 作業履歴の情報（テスト環境での履歴）
        valve_hist_count = 0
        try:
            valve_hist = unit_cooler.actuator.valve.get_hist()
            valve_hist_count = len(valve_hist)
        except Exception:
            # 履歴の取得に失敗した場合はデフォルト値を使用
            valve_hist_count = 0

        return {
            "valve": {
                "state": valve_state,
                "duration_sec": valve_duration,
                "is_working": valve_working,
                "is_idle": valve_idle,
                "history_count": valve_hist_count,
            },
            "sensor": {
                "flow_value": flow,
                "power_state": sensor_power_state,
                "flow_available": flow is not None,
            },
            "actuator": {"timestamp": time.time(), "stat_dir_exists": stat_dir.exists()},
        }
    except Exception as e:
        logger.exception("Error collecting actuator metrics")
        return {"error": str(e)}


@blueprint.route("/api/metrics", methods=["GET"])
@my_lib.flask_util.support_jsonp
def get_metrics_json():
    """メトリクス情報をJSON形式で返す"""
    try:
        with _metrics_lock:
            current_metrics = _metrics_data.copy()

        # アクチュエータ固有メトリクスを追加
        actuator_metrics = get_actuator_specific_metrics()

        # 稼働時間の計算
        uptime_seconds = time.time() - current_metrics["uptime_start"]

        # バルブ稼働時間メトリクスを取得
        valve_timing = get_valve_timing_metrics()

        response = {
            "timestamp": time.time(),
            "uptime_seconds": uptime_seconds,
            "counters": {
                "valve_operations": current_metrics["valve_operations"],
                "sensor_reads": current_metrics["sensor_reads"],
                "errors": current_metrics["errors"],
                "warnings": current_metrics["warnings"],
            },
            "valve_timing": valve_timing,
            "last_events": {
                "valve_operation": current_metrics["last_valve_operation"],
                "sensor_read": current_metrics["last_sensor_read"],
                "error": current_metrics["last_error"],
            },
            "actuator": actuator_metrics,
            "note": "For system metrics (CPU, memory, etc.), use /unit_cooler/api/sysinfo",
        }

        # データベースに保存
        save_metrics_to_db(response)

        return flask.jsonify(response)

    except Exception as e:
        logger.exception("Error generating metrics")
        return flask.jsonify({"error": str(e), "timestamp": time.time()}), 500


@blueprint.route("/api/metrics/prometheus", methods=["GET"])
def get_metrics_prometheus():
    """メトリクス情報をPrometheus形式で返す"""
    try:
        with _metrics_lock:
            current_metrics = _metrics_data.copy()

        actuator_metrics = get_actuator_specific_metrics()
        valve_timing = get_valve_timing_metrics()
        uptime_seconds = time.time() - current_metrics["uptime_start"]

        # Prometheus形式のメトリクス生成
        prom_lines = []

        # ヘルプとタイプ情報
        prom_lines.extend(
            [
                "# HELP unit_cooler_actuator_valve_operations_total Total number of valve operations",
                "# TYPE unit_cooler_actuator_valve_operations_total counter",
                f"unit_cooler_actuator_valve_operations_total {current_metrics['valve_operations']}",
                "",
                "# HELP unit_cooler_actuator_sensor_reads_total Total number of sensor reads",
                "# TYPE unit_cooler_actuator_sensor_reads_total counter",
                f"unit_cooler_actuator_sensor_reads_total {current_metrics['sensor_reads']}",
                "",
                "# HELP unit_cooler_actuator_errors_total Total number of errors",
                "# TYPE unit_cooler_actuator_errors_total counter",
                f"unit_cooler_actuator_errors_total {current_metrics['errors']}",
                "",
                "# HELP unit_cooler_actuator_uptime_seconds Actuator uptime in seconds",
                "# TYPE unit_cooler_actuator_uptime_seconds gauge",
                f"unit_cooler_actuator_uptime_seconds {uptime_seconds:.2f}",
                "",
                "# HELP unit_cooler_actuator_valve_on_total_seconds Total valve ON time in seconds",
                "# TYPE unit_cooler_actuator_valve_on_total_seconds counter",
                f"unit_cooler_actuator_valve_on_total_seconds {valve_timing['total_on_seconds']:.2f}",
                "",
                "# HELP unit_cooler_actuator_valve_sessions_total Total number of valve ON sessions",
                "# TYPE unit_cooler_actuator_valve_sessions_total counter",
                f"unit_cooler_actuator_valve_sessions_total {valve_timing['session_count']}",
                "",
                "# HELP unit_cooler_actuator_valve_duty_cycle_percentage Valve duty cycle percentage",
                "# TYPE unit_cooler_actuator_valve_duty_cycle_percentage gauge",
                (
                    f"unit_cooler_actuator_valve_duty_cycle_percentage "
                    f"{valve_timing['duty_cycle_percentage']:.2f}"
                ),
                "",
                "# HELP unit_cooler_actuator_valve_average_session_duration_seconds",
                "# Average valve ON session duration",
                "# TYPE unit_cooler_actuator_valve_average_session_duration_seconds gauge",
                (
                    f"unit_cooler_actuator_valve_average_session_duration_seconds "
                    f"{valve_timing['average_session_duration_seconds']:.2f}"
                ),
                "",
            ]
        )

        # アクチュエータメトリクス
        if "valve" in actuator_metrics:
            valve_state_value = 1 if actuator_metrics["valve"]["state"] == "OPEN" else 0
            prom_lines.extend(
                [
                    "# HELP unit_cooler_actuator_valve_state Current valve state (1=OPEN, 0=CLOSE)",
                    "# TYPE unit_cooler_actuator_valve_state gauge",
                    f"unit_cooler_actuator_valve_state {valve_state_value}",
                    "",
                    "# HELP unit_cooler_actuator_valve_duration_seconds Valve current state duration",
                    "# TYPE unit_cooler_actuator_valve_duration_seconds gauge",
                    (
                        f"unit_cooler_actuator_valve_duration_seconds "
                        f"{actuator_metrics['valve']['duration_sec']}"
                    ),
                    "",
                ]
            )

        if "sensor" in actuator_metrics and actuator_metrics["sensor"]["flow_value"] is not None:
            prom_lines.extend(
                [
                    "# HELP unit_cooler_actuator_flow_value Current flow value",
                    "# TYPE unit_cooler_actuator_flow_value gauge",
                    f"unit_cooler_actuator_flow_value {actuator_metrics['sensor']['flow_value']:.2f}",
                    "",
                ]
            )

        response_text = "\n".join(prom_lines)

        return flask.Response(response_text, mimetype="text/plain; version=0.0.4; charset=utf-8")

    except Exception as e:
        logger.exception("Error generating Prometheus metrics")
        return flask.Response(f"# Error generating metrics: {e}\n", status=500, mimetype="text/plain")


@blueprint.route("/api/metrics/health", methods=["GET"])
@my_lib.flask_util.support_jsonp
def get_health():
    """ヘルスチェック用エンドポイント"""
    try:
        actuator_metrics = get_actuator_specific_metrics()

        # 基本的な健全性チェック
        is_healthy = True
        issues = []

        if "error" in actuator_metrics:
            is_healthy = False
            issues.append(f"Actuator metrics error: {actuator_metrics['error']}")

        if "sensor" in actuator_metrics and not actuator_metrics["sensor"]["power_state"]:
            issues.append("Sensor power is off")

        response = {"healthy": is_healthy, "timestamp": time.time(), "issues": issues, "version": "1.0.0"}

        status_code = 200 if is_healthy else 503
        return flask.jsonify(response), status_code

    except Exception as e:
        logger.exception("Health check error")
        return flask.jsonify({"healthy": False, "error": str(e), "timestamp": time.time()}), 500


# メトリクス収集のためのヘルパー関数（他のモジュールから呼び出し可能）
def record_valve_operation(operation: str, state: str):
    """バルブ操作を記録"""
    increment_metric("valve_operations", {"operation": operation, "state": state, "source": "valve_module"})

    # バルブ稼働時間の記録
    _record_valve_timing(state)


def record_sensor_read(sensor_type: str, value: Any):
    """センサー読み取りを記録"""
    increment_metric("sensor_reads", {"sensor_type": sensor_type, "value": value, "source": "sensor_module"})


def record_error(error_type: str, message: str):
    """エラーを記録"""
    increment_metric("errors", {"error_type": error_type, "message": message, "source": "general"})


def record_warning(warning_type: str, message: str):
    """警告を記録"""
    increment_metric("warnings", {"warning_type": warning_type, "message": message, "source": "general"})


def _record_valve_timing(new_state: str):
    """バルブ稼働時間の内部記録"""
    with _metrics_lock:
        current_time = time.time()
        prev_state = _metrics_data["valve_current_state"]

        # CLOSE → OPEN への変化
        if prev_state == "CLOSE" and new_state == "OPEN":
            _metrics_data["valve_last_on_time"] = current_time
            _metrics_data["valve_current_state"] = "OPEN"

        # OPEN → CLOSE への変化
        elif prev_state == "OPEN" and new_state == "CLOSE":
            if _metrics_data["valve_last_on_time"] is not None:
                # ON時間を計算
                session_duration = current_time - _metrics_data["valve_last_on_time"]
                _metrics_data["valve_on_total_seconds"] += session_duration
                _metrics_data["valve_on_session_count"] += 1

                # セッション履歴を記録（最新10件）
                session_info = {
                    "start_time": _metrics_data["valve_last_on_time"],
                    "end_time": current_time,
                    "duration_seconds": session_duration,
                }
                _metrics_data["valve_session_times"].append(session_info)
                if len(_metrics_data["valve_session_times"]) > 10:
                    _metrics_data["valve_session_times"].pop(0)

                _metrics_data["valve_last_on_time"] = None
            _metrics_data["valve_current_state"] = "CLOSE"


def get_valve_timing_metrics() -> dict[str, Any]:
    """バルブ稼働時間メトリクスを取得"""
    with _metrics_lock:
        current_time = time.time()
        uptime_seconds = current_time - _metrics_data["uptime_start"]

        # 現在ONの場合、その時間も加算して計算
        current_session_duration = 0
        if _metrics_data["valve_current_state"] == "OPEN" and _metrics_data["valve_last_on_time"] is not None:
            current_session_duration = current_time - _metrics_data["valve_last_on_time"]

        total_on_time = _metrics_data["valve_on_total_seconds"] + current_session_duration

        # 各種計算値
        duty_cycle_ratio = (total_on_time / uptime_seconds * 100) if uptime_seconds > 0 else 0
        average_session_duration = 0
        if _metrics_data["valve_on_session_count"] > 0:
            # 現在のセッションも平均に含める
            session_count = _metrics_data["valve_on_session_count"]
            if current_session_duration > 0:
                session_count += 1
            average_session_duration = total_on_time / session_count

        return {
            "total_on_seconds": total_on_time,
            "session_count": _metrics_data["valve_on_session_count"],
            "average_session_duration_seconds": average_session_duration,
            "duty_cycle_percentage": duty_cycle_ratio,
            "current_state": _metrics_data["valve_current_state"],
            "current_session_duration": current_session_duration,
            "recent_sessions": _metrics_data["valve_session_times"][-5:],  # 最新5件
            "uptime_seconds": uptime_seconds,
        }
