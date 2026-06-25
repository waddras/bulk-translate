#!/usr/bin/env python3
"""Logging setup + shared job state.

Leaf module (imports only stdlib for the state management).
Job history is persisted to SQLite via db.py on completion.
"""
import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bulk-translate")

# ── Shared job state ──────────────────────────────────────────────────────────
_cancel_flag = asyncio.Event()
_job_status = {
    "running": False,
    "done": False,
    "error": None,
    "log": [],
    "cancelled": False,
    "completed_files": [],
    "skipped_files": [],
    "untranslated": [],
}


def reset_job_status() -> None:
    """Reset state for a new run (mutates in place, sets running=True)."""
    _job_status.clear()
    _job_status.update({
        "running": True,
        "done": False,
        "error": None,
        "log": [],
        "cancelled": False,
        "completed_files": [],
        "skipped_files": [],
        "untranslated": [],
    })


def get_job_status() -> dict:
    return _job_status


def jlog(msg: str) -> None:
    """Log to journal AND append to the web-visible job log."""
    log.info(msg)
    _job_status["log"].append(msg)


def set_error(msg: str) -> None:
    _job_status["error"] = msg


def set_done() -> None:
    _job_status["done"] = True
    _save_to_db()


def set_running(value: bool) -> None:
    _job_status["running"] = value


def is_running() -> bool:
    return bool(_job_status.get("running"))


def mark_cancelled() -> None:
    _job_status["cancelled"] = True


def set_completed(files: list) -> None:
    _job_status["completed_files"] = files


def set_skipped(files: list) -> None:
    _job_status["skipped_files"] = files


def set_untranslated(lines: list) -> None:
    """Store ordered list of {tag, text} for untranslated lines."""
    _job_status["untranslated"] = lines


# ── Cancellation ──────────────────────────────────────────────────────────────
def set_cancel() -> None:
    _cancel_flag.set()


def clear_cancel() -> None:
    _cancel_flag.clear()


def is_cancelled() -> bool:
    return _cancel_flag.is_set()



# ── Job history (saved to SQLite via db.py) ───────────────────────────────────
def _save_to_db() -> None:
    """Save current job to the database."""
    try:
        import db
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        status_word = "cancelled" if _job_status.get("cancelled") else \
                      "error" if _job_status.get("error") else "ok"
        job_id = f"{ts}_{status_word}"
        db.save_job_history(
            job_id=job_id,
            status=status_word,
            error=_job_status.get("error"),
            completed_files=_job_status.get("completed_files", []),
            skipped_files=_job_status.get("skipped_files", []),
            log_lines=_job_status.get("log", []),
            untranslated=_job_status.get("untranslated", []),
        )
        log.info(f"Job saved to DB: {job_id}")
    except Exception as e:
        log.warning(f"Failed to save job to DB: {e}")
