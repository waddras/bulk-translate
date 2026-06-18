#!/usr/bin/env python3
"""Logging setup + shared job state.

Leaf module (imports only stdlib). The job state dict is mutated IN PLACE and
only ever accessed through the helpers below, so routes and the background job
always observe the same live object (no stale references after a reset).
"""
import asyncio
import logging

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
