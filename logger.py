#!/usr/bin/env python3
"""Logging setup + shared job state + job history persistence.

Leaf module (imports only stdlib). The job state dict is mutated IN PLACE and
only ever accessed through the helpers below, so routes and the background job
always observe the same live object (no stale references after a reset).
"""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bulk-translate")

HISTORY_DIR = "/opt/bulk-translate/history"

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
    save_job_history()


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


# ── Cancellation ──────────────────────────────────────────────────────────────
def set_cancel() -> None:
    _cancel_flag.set()


def clear_cancel() -> None:
    _cancel_flag.clear()


def is_cancelled() -> bool:
    return _cancel_flag.is_set()



# ── Job history ───────────────────────────────────────────────────────────────
def save_job_history() -> None:
    """Persist the current job log to a timestamped JSON file."""
    try:
        Path(HISTORY_DIR).mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        status_word = "cancelled" if _job_status.get("cancelled") else \
                      "error" if _job_status.get("error") else "ok"
        filename = f"{ts}_{status_word}.json"
        data = {
            "timestamp": ts,
            "status": status_word,
            "error": _job_status.get("error"),
            "completed_files": _job_status.get("completed_files", []),
            "skipped_files": _job_status.get("skipped_files", []),
            "log": _job_status.get("log", []),
        }
        (Path(HISTORY_DIR) / filename).write_text(json.dumps(data, indent=2), encoding="utf-8")
        log.info(f"Job history saved: {filename}")
    except Exception as e:
        log.warning(f"Failed to save job history: {e}")


def list_job_history() -> list:
    """Return list of past job summaries (newest first)."""
    hdir = Path(HISTORY_DIR)
    if not hdir.exists():
        return []
    files = sorted(hdir.glob("*.json"), reverse=True)
    result = []
    for f in files[:50]:  # cap to last 50
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            result.append({
                "id": f.stem,
                "timestamp": data.get("timestamp", ""),
                "status": data.get("status", ""),
                "completed": len(data.get("completed_files", [])),
                "skipped": len(data.get("skipped_files", [])),
            })
        except Exception:
            pass
    return result


def get_job_history(job_id: str) -> dict | None:
    """Load a specific past job's full log."""
    fpath = Path(HISTORY_DIR) / f"{job_id}.json"
    if not fpath.exists():
        return None
    try:
        return json.loads(fpath.read_text(encoding="utf-8"))
    except Exception:
        return None
