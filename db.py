#!/usr/bin/env python3
"""SQLite layer: per-model daily usage/quota/OOS tracking and API-key storage.

Shares /opt/bazarr-translator/usage.db with the bazarr-translator service.
Reads MODEL_POOL / OOS_THRESHOLD from the live cfg at call-time.
"""
import sqlite3
from datetime import datetime, timezone, timedelta

from config import cfg, DB_PATH
from logger import log

# Quota resets at 10:30 AM Asia/Qatar (UTC+3). Before 10:30 we're still in
# the previous day's quota window.
_QATAR_OFFSET = timezone(timedelta(hours=3))
_RESET_HOUR   = 10
_RESET_MINUTE = 30


def day_key() -> str:
    """Return the current quota-period date string (YYYY-MM-DD).

    If it's before 10:30 AM Qatar time, we're still in yesterday's window.
    """
    now = datetime.now(_QATAR_OFFSET)
    if (now.hour, now.minute) < (_RESET_HOUR, _RESET_MINUTE):
        now = now - timedelta(days=1)
    return now.strftime("%Y-%m-%d")


# ── Schema ───────────────────────────────────────────────────────────────────
def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
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
        # Migrate older usage tables that predate these columns.
        for col in ("failures", "out_of_service"):
            try:
                conn.execute(f"ALTER TABLE usage ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
            except Exception:
                pass
        conn.commit()
    log.info("DB initialized")


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
    """Raises sqlite3.IntegrityError if the email already exists."""
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
    # compute next reset time for display
    now = datetime.now(_QATAR_OFFSET)
    reset_today = now.replace(hour=_RESET_HOUR, minute=_RESET_MINUTE, second=0, microsecond=0)
    if now >= reset_today:
        next_reset = reset_today + timedelta(days=1)
    else:
        next_reset = reset_today
    result = []
    for model in sorted(cfg["MODEL_POOL"], key=lambda m: m.get("priority", 99)):
        row = _get_usage_row(model["id"], today)
        result.append({
            "model":          model["id"],
            "priority":       model.get("priority", 99),
            "rpd_limit":      model["rpd"],
            "used_today":     row["requests"],
            "remaining":      max(0, model["rpd"] - row["requests"]),
            "rpd_exhausted":  row["requests"] >= model["rpd"],
            "failures":       row["failures"],
            "out_of_service": row["out_of_service"],
        })
    return result


def get_usage_meta() -> dict:
    """Return quota-period metadata for display in the UI."""
    now = datetime.now(_QATAR_OFFSET)
    reset_today = now.replace(hour=_RESET_HOUR, minute=_RESET_MINUTE, second=0, microsecond=0)
    next_reset = reset_today + timedelta(days=1) if now >= reset_today else reset_today
    return {
        "day_key":    day_key(),
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
    """Bump the daily failure count; mark OOS once it reaches OOS_THRESHOLD."""
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
    """Lowest-priority-number model that isn't OOS, RPD-exhausted, or skipped."""
    skip = skip or set()
    today = day_key()
    for model in sorted(cfg["MODEL_POOL"], key=lambda m: m.get("priority", 99)):
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
