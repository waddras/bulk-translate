#!/usr/bin/env python3
"""SQLite layer: models, daily usage/quota/OOS tracking, and API-key storage.

Uses /opt/bulk-translate/bulk-translate.db (independent from bazarr-translator).
"""
import sqlite3
from datetime import datetime, timezone, timedelta

from config import cfg, DB_PATH
from logger import log

# Quota resets at 10:30 AM Asia/Qatar (UTC+3).
_QATAR_OFFSET = timezone(timedelta(hours=3))
_RESET_HOUR = 10
_RESET_MINUTE = 30

# Default models to seed on first run
_DEFAULT_MODELS = [
    ("gemini-3.5-flash", 20, 5, 1),
    ("gemini-2.5-flash", 20, 5, 2),
    ("gemini-2.5-flash-lite", 20, 10, 3),
    ("gemini-3.1-flash-lite", 500, 15, 4),
]


def day_key() -> str:
    """Return the current quota-period date string (YYYY-MM-DD).
    If before 10:30 AM Qatar time, still in yesterday's window.
    """
    now = datetime.now(_QATAR_OFFSET)
    if (now.hour, now.minute) < (_RESET_HOUR, _RESET_MINUTE):
        now = now - timedelta(days=1)
    return now.strftime("%Y-%m-%d")


# ── Schema ───────────────────────────────────────────────────────────────────
def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS models (
                id       TEXT    PRIMARY KEY,
                rpd      INTEGER NOT NULL DEFAULT 20,
                rpm      INTEGER NOT NULL DEFAULT 5,
                priority INTEGER NOT NULL UNIQUE,
                active   INTEGER NOT NULL DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage (
                model          TEXT    NOT NULL,
                day            TEXT    NOT NULL,
                requests       INTEGER NOT NULL DEFAULT 0,
                failures       INTEGER NOT NULL DEFAULT 0,
                out_of_service INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (model, day)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                email   TEXT    NOT NULL UNIQUE,
                api_key TEXT    NOT NULL,
                active  INTEGER NOT NULL DEFAULT 1,
                added   TEXT    NOT NULL
            )
        """)
        # Seed default models if table is empty
        count = conn.execute("SELECT COUNT(*) FROM models").fetchone()[0]
        if count == 0:
            for model_id, rpd, rpm, priority in _DEFAULT_MODELS:
                conn.execute(
                    "INSERT INTO models (id, rpd, rpm, priority, active) VALUES (?,?,?,?,1)",
                    (model_id, rpd, rpm, priority),
                )
            log.info("Seeded default models")
        conn.commit()
    _init_history_tables()
    log.info("DB initialized")


# ── Models ───────────────────────────────────────────────────────────────────
def get_model_pool() -> list:
    """Return all models sorted by priority."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, rpd, rpm, priority, active FROM models ORDER BY priority"
        ).fetchall()
    return [{"id": r[0], "rpd": r[1], "rpm": r[2], "priority": r[3], "active": r[4]} for r in rows]


def get_active_models() -> list:
    """Return only active models sorted by priority."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, rpd, rpm, priority FROM models WHERE active=1 ORDER BY priority"
        ).fetchall()
    return [{"id": r[0], "rpd": r[1], "rpm": r[2], "priority": r[3]} for r in rows]


def add_model(model_id: str, rpd: int, rpm: int, priority: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO models (id, rpd, rpm, priority, active) VALUES (?,?,?,?,1)",
            (model_id, rpd, rpm, priority),
        )
        conn.commit()


def update_model(model_id: str, rpd: int, rpm: int, priority: int, active: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE models SET rpd=?, rpm=?, priority=?, active=? WHERE id=?",
            (rpd, rpm, priority, active, model_id),
        )
        conn.commit()


def delete_model(model_id: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM models WHERE id=?", (model_id,))
        conn.commit()


def save_model_pool(pool: list) -> None:
    """Replace entire model pool atomically."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM models")
        for m in pool:
            conn.execute(
                "INSERT INTO models (id, rpd, rpm, priority, active) VALUES (?,?,?,?,?)",
                (m["id"], m["rpd"], m["rpm"], m["priority"], m.get("active", 1)),
            )
        conn.commit()


# ── API keys ─────────────────────────────────────────────────────────────────
def get_active_keys() -> list:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, email, api_key FROM api_keys WHERE active=1 ORDER BY id"
        ).fetchall()
    return [{"id": r[0], "email": r[1], "api_key": r[2]} for r in rows]


def get_all_keys() -> list:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, email, active, added FROM api_keys ORDER BY id"
        ).fetchall()
    return [{"id": r[0], "email": r[1], "active": r[2], "added": r[3]} for r in rows]


def add_key(email: str, api_key: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO api_keys (email, api_key, active, added) VALUES (?,?,1,?)",
            (email, api_key, day_key()),
        )
        conn.commit()


def delete_key(key_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM api_keys WHERE id=?", (key_id,))
        conn.commit()


def toggle_key(key_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE api_keys SET active=CASE WHEN active=1 THEN 0 ELSE 1 END WHERE id=?",
            (key_id,),
        )
        conn.commit()


# ── Usage / quota ────────────────────────────────────────────────────────────
def _get_usage_row(model_id: str, day: str) -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT requests, failures, out_of_service FROM usage WHERE model=? AND day=?",
            (model_id, day),
        ).fetchone()
    if row:
        return {"requests": row[0], "failures": row[1], "out_of_service": bool(row[2])}
    return {"requests": 0, "failures": 0, "out_of_service": False}


def get_all_usage() -> list:
    today = day_key()
    models = get_active_models()
    result = []
    for model in models:
        row = _get_usage_row(model["id"], today)
        result.append({
            "model": model["id"],
            "priority": model["priority"],
            "rpd_limit": model["rpd"],
            "used_today": row["requests"],
            "remaining": max(0, model["rpd"] - row["requests"]),
            "rpd_exhausted": row["requests"] >= model["rpd"],
            "failures": row["failures"],
            "out_of_service": row["out_of_service"],
        })
    return result


def get_usage_meta() -> dict:
    now = datetime.now(_QATAR_OFFSET)
    reset_today = now.replace(hour=_RESET_HOUR, minute=_RESET_MINUTE, second=0, microsecond=0)
    next_reset = reset_today + timedelta(days=1) if now >= reset_today else reset_today
    return {
        "day_key": day_key(),
        "next_reset": next_reset.strftime("%Y-%m-%d %H:%M AST"),
    }


def increment_usage(model_id: str) -> None:
    today = day_key()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO usage (model, day, requests) VALUES (?,?,1)
            ON CONFLICT(model,day) DO UPDATE SET requests=requests+1
        """, (model_id, today))
        conn.commit()


def increment_failures(model_id: str) -> int:
    today = day_key()
    threshold = cfg["OOS_THRESHOLD"]
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO usage (model, day, failures) VALUES (?,?,1)
            ON CONFLICT(model,day) DO UPDATE SET failures=failures+1
        """, (model_id, today))
        row = conn.execute(
            "SELECT failures FROM usage WHERE model=? AND day=?", (model_id, today)
        ).fetchone()
        failures = row[0] if row else 0
        if failures >= threshold:
            conn.execute(
                "UPDATE usage SET out_of_service=1 WHERE model=? AND day=?",
                (model_id, today),
            )
            log.warning(f"[{model_id}] MARKED OUT OF SERVICE (failed {failures}x today)")
        conn.commit()
    return failures


def get_available_model(skip: set = None) -> dict | None:
    """Lowest-priority-number active model that isn't OOS or RPD-exhausted."""
    skip = skip or set()
    today = day_key()
    models = get_active_models()
    for model in models:
        mid = model["id"]
        if mid in skip:
            continue
        row = _get_usage_row(mid, today)
        if row["out_of_service"] or row["requests"] >= model["rpd"]:
            continue
        return model
    return None


def reset_oos(model_id: str) -> None:
    today = day_key()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE usage SET out_of_service=0, failures=0 WHERE model=? AND day=?",
            (model_id, today),
        )
        conn.commit()


def reset_usage(model_id: str) -> None:
    today = day_key()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE usage SET requests=0, failures=0, out_of_service=0 WHERE model=? AND day=?",
            (model_id, today),
        )
        conn.commit()



# ── Job history ──────────────────────────────────────────────────────────────
def _init_history_tables():
    """Create history tables if they don't exist."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS job_history (
                id              TEXT PRIMARY KEY,
                timestamp       TEXT NOT NULL,
                status          TEXT NOT NULL,
                error           TEXT,
                completed_files TEXT NOT NULL DEFAULT '[]',
                skipped_files   TEXT NOT NULL DEFAULT '[]',
                log             TEXT NOT NULL DEFAULT '[]'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS untranslated_lines (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id          TEXT NOT NULL,
                tag             TEXT NOT NULL,
                original_text   TEXT NOT NULL,
                translated_text TEXT,
                status          TEXT NOT NULL DEFAULT 'pending'
            )
        """)
        conn.commit()


def save_job_history(job_id: str, status: str, error: str, completed_files: list,
                     skipped_files: list, log_lines: list, untranslated: list) -> None:
    """Save a completed job to the database."""
    import json
    _init_history_tables()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO job_history (id, timestamp, status, error, completed_files, skipped_files, log)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            job_id.replace("_", " ", 1),
            status,
            error,
            json.dumps(completed_files),
            json.dumps(skipped_files),
            json.dumps(log_lines),
        ))
        # Save untranslated lines
        if untranslated:
            conn.execute("DELETE FROM untranslated_lines WHERE job_id=?", (job_id,))
            for item in untranslated:
                conn.execute(
                    "INSERT INTO untranslated_lines (job_id, tag, original_text, status) VALUES (?,?,?,?)",
                    (job_id, item["tag"], item["text"], "pending"),
                )
        conn.commit()


def list_job_history(limit: int = 50) -> list:
    """Return list of past jobs (newest first)."""
    import json
    _init_history_tables()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, timestamp, status, completed_files, skipped_files FROM job_history ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    result = []
    for r in rows:
        completed = json.loads(r[3]) if r[3] else []
        skipped = json.loads(r[4]) if r[4] else []
        # Count pending untranslated
        result.append({
            "id": r[0],
            "timestamp": r[1],
            "status": r[2],
            "completed": len(completed),
            "skipped": len(skipped),
        })
    return result


def get_job_history(job_id: str) -> dict | None:
    """Load a specific job's full details."""
    import json
    _init_history_tables()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, timestamp, status, error, completed_files, skipped_files, log FROM job_history WHERE id=?",
            (job_id,)
        ).fetchone()
    if not row:
        return None
    # Get untranslated lines for this job
    with sqlite3.connect(DB_PATH) as conn:
        ut_rows = conn.execute(
            "SELECT tag, original_text, translated_text, status FROM untranslated_lines WHERE job_id=? ORDER BY id",
            (job_id,)
        ).fetchall()
    return {
        "id": row[0],
        "timestamp": row[1],
        "status": row[2],
        "error": row[3],
        "completed_files": json.loads(row[4]) if row[4] else [],
        "skipped_files": json.loads(row[5]) if row[5] else [],
        "log": json.loads(row[6]) if row[6] else [],
        "untranslated": [{"tag": r[0], "text": r[1], "translated": r[2], "status": r[3]} for r in ut_rows],
    }


def get_untranslated_for_job(job_id: str) -> list:
    """Get pending untranslated lines for a job."""
    _init_history_tables()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT tag, original_text FROM untranslated_lines WHERE job_id=? AND status='pending' ORDER BY id",
            (job_id,)
        ).fetchall()
    return [{"tag": r[0], "text": r[1]} for r in rows]


def mark_lines_translated(job_id: str, translations: dict) -> None:
    """Mark lines as translated with the provided text. translations = {tag: arabic}"""
    _init_history_tables()
    with sqlite3.connect(DB_PATH) as conn:
        for tag, text in translations.items():
            conn.execute(
                "UPDATE untranslated_lines SET translated_text=?, status='fixed' WHERE job_id=? AND tag=?",
                (text, job_id, tag),
            )
        conn.commit()
