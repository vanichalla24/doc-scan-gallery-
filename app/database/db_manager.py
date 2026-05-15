"""SQLite database manager for TransLingo QA Studio."""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


DB_PATH = Path.home() / ".translingo_qa" / "translingo.db"


def _ensure_db_dir() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection():
    _ensure_db_dir()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database() -> None:
    """Create all tables if they don't exist."""
    _ensure_db_dir()
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS validation_runs (
                run_id TEXT PRIMARY KEY,
                root_folder TEXT NOT NULL,
                source_language TEXT NOT NULL,
                target_language TEXT NOT NULL,
                engines TEXT NOT NULL,
                status TEXT NOT NULL,
                scoring_weights TEXT,
                start_time TEXT,
                end_time TEXT,
                total_images INTEGER DEFAULT 0,
                processed_images INTEGER DEFAULT 0,
                average_score REAL DEFAULT 0,
                pass_rate REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS image_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                engine TEXT NOT NULL,
                image_name TEXT NOT NULL,
                original_path TEXT,
                translated_path TEXT,
                overall_score REAL DEFAULT 0,
                score_band TEXT,
                parameter_scores TEXT,
                issues TEXT,
                original_ocr_text TEXT,
                translated_ocr_text TEXT,
                processing_time REAL DEFAULT 0,
                error TEXT,
                timestamp TEXT,
                FOREIGN KEY (run_id) REFERENCES validation_runs(run_id)
            );

            CREATE TABLE IF NOT EXISTS engine_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                engine TEXT NOT NULL,
                average_score REAL DEFAULT 0,
                pass_rate REAL DEFAULT 0,
                total_images INTEGER DEFAULT 0,
                processed_images INTEGER DEFAULT 0,
                FOREIGN KEY (run_id) REFERENCES validation_runs(run_id)
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_image_results_run_id ON image_results(run_id);
            CREATE INDEX IF NOT EXISTS idx_image_results_engine ON image_results(engine);
            CREATE INDEX IF NOT EXISTS idx_image_results_score ON image_results(overall_score);
        """)
    logger.info(f"Database initialized at {DB_PATH}")


def save_run(run_data: Dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO validation_runs
            (run_id, root_folder, source_language, target_language, engines,
             status, scoring_weights, start_time, end_time, total_images,
             processed_images, average_score, pass_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_data["run_id"],
            run_data["root_folder"],
            run_data["source_language"],
            run_data["target_language"],
            json.dumps(run_data["engines"]),
            run_data["status"],
            json.dumps(run_data.get("scoring_weights", {})),
            run_data.get("start_time", datetime.now().isoformat()),
            run_data.get("end_time"),
            run_data.get("total_images", 0),
            run_data.get("processed_images", 0),
            run_data.get("average_score", 0.0),
            run_data.get("pass_rate", 0.0),
        ))


def save_image_result(result_data: Dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO image_results
            (run_id, engine, image_name, original_path, translated_path,
             overall_score, score_band, parameter_scores, issues,
             original_ocr_text, translated_ocr_text, processing_time, error, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result_data["run_id"],
            result_data["engine"],
            result_data["image_name"],
            result_data.get("original_path", ""),
            result_data.get("translated_path", ""),
            result_data.get("overall_score", 0.0),
            result_data.get("score_band", ""),
            json.dumps(result_data.get("parameter_scores", {})),
            json.dumps(result_data.get("issues", [])),
            result_data.get("original_ocr_text", ""),
            result_data.get("translated_ocr_text", ""),
            result_data.get("processing_time", 0.0),
            result_data.get("error"),
            datetime.now().isoformat(),
        ))


def save_engine_summary(summary_data: Dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO engine_summaries
            (run_id, engine, average_score, pass_rate, total_images, processed_images)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            summary_data["run_id"],
            summary_data["engine"],
            summary_data.get("average_score", 0.0),
            summary_data.get("pass_rate", 0.0),
            summary_data.get("total_images", 0),
            summary_data.get("processed_images", 0),
        ))


def list_runs(limit: int = 50) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM validation_runs ORDER BY start_time DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM validation_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
    return dict(row) if row else None


def get_image_results(run_id: str, engine: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        if engine:
            rows = conn.execute(
                "SELECT * FROM image_results WHERE run_id = ? AND engine = ? ORDER BY overall_score",
                (run_id, engine)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM image_results WHERE run_id = ? ORDER BY engine, image_name",
                (run_id,)
            ).fetchall()
    results = []
    for row in rows:
        d = dict(row)
        d["parameter_scores"] = json.loads(d.get("parameter_scores") or "{}")
        d["issues"] = json.loads(d.get("issues") or "[]")
        results.append(d)
    return results


def get_engine_summaries(run_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM engine_summaries WHERE run_id = ? ORDER BY average_score DESC",
            (run_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def save_setting(key: str, value: Any) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
            (key, json.dumps(value))
        )


def load_setting(key: str, default: Any = None) -> Any:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
    if row:
        return json.loads(row["value"])
    return default


def load_all_settings() -> Dict[str, Any]:
    with get_connection() as conn:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    return {r["key"]: json.loads(r["value"]) for r in rows}


def delete_run(run_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM image_results WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM engine_summaries WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM validation_runs WHERE run_id = ?", (run_id,))
