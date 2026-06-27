#!/usr/bin/env python3
"""Bulk Subtitle Translator - FastAPI app (routes only).

All logic lives in the sibling modules; this file just wires HTTP endpoints to
them. Run with:  uvicorn main:app --host 0.0.0.0 --port 8091
"""
import json
import sqlite3
import asyncio
from pathlib import Path
from typing import List

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

import config
import db
import job
import extract
import logger
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Bulk Subtitle Translator", version="2.1.0")


class TranslationRequest(BaseModel):
    files: List[str]
    keep_styles: List[str] = []


class ExtractRequest(BaseModel):
    files: List[str]
    track_index: int
    suffix: str
    convert_to_srt: bool = False


class AddKeyRequest(BaseModel):
    email: str
    api_key: str


class SettingsRequest(BaseModel):
    TRANSLATION_MODE: str
    MAX_LINES_PER_CHUNK: int
    PARALLEL_CHUNKS: int
    PARALLEL_COOLDOWN: int
    GEMINI_MAX_OUTPUT_TOKENS: int
    OOS_THRESHOLD: int
    RETRY_ATTEMPTS: int
    RETRY_COOLDOWN: int
    MAX_BLOB_LINES: int
    MAX_FAILED_CHUNKS: int
    FILE_CONFLICT: str
    EMBED_FONT: bool
    PRESERVE_TAGS: str
    PROMPT_TEMPLATE: str
    FONT_NAME: str
    FONT_SIZE: int
    FONT_OUTLINE: int
    FONT_SHADOW: int
    FONT_ALIGNMENT: int
    FONT_MARGIN_L: int
    FONT_MARGIN_R: int
    FONT_MARGIN_V: int


class ModelPoolRequest(BaseModel):
    models: list


@app.on_event("startup")
async def startup():
    Path(config.BULK_DIR).mkdir(parents=True, exist_ok=True)
    db.init_db()


@app.get("/api/usage")
async def api_usage():
    meta = db.get_usage_meta()
    return JSONResponse({
        "date":       meta["day_key"],
        "next_reset": meta["next_reset"],
        "models":     db.get_all_usage(),
    })


@app.post("/api/usage/{model_id}/reset-oos")
async def api_reset_oos(model_id: str):
    db.reset_oos(model_id)
    return {"ok": True}


@app.post("/api/usage/{model_id}/reset-usage")
async def api_reset_usage(model_id: str):
    db.reset_usage(model_id)
    return {"ok": True}


@app.get("/api/keys")
async def api_list_keys():
    return JSONResponse(db.get_all_keys())


@app.post("/api/keys")
async def api_add_key(req: AddKeyRequest):
    try:
        db.add_key(req.email, req.api_key)
        return {"ok": True, "email": req.email}
    except sqlite3.IntegrityError:
        raise HTTPException(400, f"Key for {req.email} already exists")


@app.delete("/api/keys/{key_id}")
async def api_delete_key(key_id: int):
    db.delete_key(key_id)
    return {"ok": True}


@app.post("/api/keys/{key_id}/toggle")
async def api_toggle_key(key_id: int):
    db.toggle_key(key_id)
    return {"ok": True}


@app.get("/api/settings")
async def api_get_settings():
    return JSONResponse(config.cfg)


@app.post("/api/settings")
async def api_update_settings(req: SettingsRequest):
    config.update_settings(req.dict())
    return {"ok": True}


@app.get("/api/models")
async def api_get_models():
    return JSONResponse(db.get_model_pool())


@app.post("/api/models")
async def api_save_models(payload: ModelPoolRequest):
    models = payload.models
    priorities = [m.get("priority") for m in models if isinstance(m, dict)]
    if len(priorities) != len(set(priorities)):
        raise HTTPException(400, "Duplicate priority numbers.")
    if not models:
        raise HTTPException(400, "Cannot save empty model pool.")
    db.save_model_pool(models)
    return {"ok": True}


@app.get("/api/job-status")
async def api_job_status():
    return JSONResponse(logger.get_job_status())


@app.get("/api/job-stream")
async def api_job_stream():
    """Server-Sent Events stream — pushes log lines and status in real time."""
    async def event_generator():
        last_idx = 0
        while True:
            status = logger.get_job_status()
            log_lines = status.get("log", [])
            # Send any new lines since last check
            if len(log_lines) > last_idx:
                for line in log_lines[last_idx:]:
                    yield f"data: {json.dumps({'type': 'log', 'line': line})}\n\n"
                last_idx = len(log_lines)
            # Send status update
            yield f"data: {json.dumps({'type': 'status', 'running': status['running'], 'done': status.get('done', False), 'cancelled': status.get('cancelled', False), 'error': status.get('error'), 'completed_files': status.get('completed_files', []), 'skipped_files': status.get('skipped_files', [])})}\n\n"
            if not status["running"] and status.get("done"):
                yield f"data: {json.dumps({'type': 'end'})}\n\n"
                break
            await asyncio.sleep(1)
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/job/cancel")
async def api_cancel_job():
    if not logger.is_running():
        raise HTTPException(400, "No job running")
    logger.set_cancel()
    logger.log.info("Cancel requested by user")
    return {"ok": True, "message": "Cancel signal sent"}


@app.post("/api/job/force-kill")
async def api_force_kill():
    """Force restart the service via systemctl. Nuclear option."""
    import subprocess
    logger.log.warning("FORCE KILL requested by user — restarting service")
    # This kills our own process; systemd will restart it
    subprocess.Popen(["systemctl", "restart", "bulk-translate"])
    return {"ok": True, "message": "Service restarting"}


@app.post("/api/analyze")
async def api_analyze(payload: TranslationRequest, background_tasks: BackgroundTasks):
    if logger.is_running():
        raise HTTPException(409, "A job is already running")
    if not payload.files:
        raise HTTPException(400, "No files provided")
    background_tasks.add_task(job.run_analyze, payload.files, payload.keep_styles or None)
    return {"ok": True, "queued": len(payload.files)}


@app.post("/api/set-show-name")
async def api_set_show_name(payload: dict):
    """Override the auto-detected show name."""
    name = payload.get("name", "")
    job.set_show_name(name)
    return {"ok": True, "name": name}


class FixResendRequest(BaseModel):
    job_id: str
    model_id: str


class FixManualRequest(BaseModel):
    job_id: str
    translations: List[str]


@app.post("/api/fix-resend")
async def api_fix_resend(payload: FixResendRequest, background_tasks: BackgroundTasks):
    """Resend untranslated lines to a specific model."""
    if logger.is_running():
        raise HTTPException(409, "A job is already running")
    untranslated = db.get_untranslated_for_job(payload.job_id)
    if not untranslated:
        # Try current job status
        status = logger.get_job_status()
        untranslated = status.get("untranslated", [])
    if not untranslated:
        raise HTTPException(400, "No untranslated lines found")
    background_tasks.add_task(
        job.run_fix_resend, untranslated, payload.model_id
    )
    return {"ok": True, "lines": len(untranslated)}


@app.post("/api/fix-manual")
async def api_fix_manual(payload: FixManualRequest):
    """Apply manual translations to untranslated lines."""
    untranslated = db.get_untranslated_for_job(payload.job_id)
    if not untranslated:
        status = logger.get_job_status()
        untranslated = status.get("untranslated", [])
    if not untranslated:
        raise HTTPException(400, "No untranslated lines found")
    if len(payload.translations) != len(untranslated):
        raise HTTPException(400, f"Expected {len(untranslated)} lines, got {len(payload.translations)}")
    # Map translations back to tags and save
    translations = {}
    for i, item in enumerate(untranslated):
        translations[item["tag"]] = payload.translations[i]
    db.mark_lines_translated(payload.job_id, translations)
    return JSONResponse({"ok": True, "applied": len(translations)})


@app.post("/api/translate")
async def api_translate(background_tasks: BackgroundTasks):
    if logger.is_running():
        raise HTTPException(409, "A job is already running")
    if not job.is_analyze_ready():
        raise HTTPException(400, "No valid analyze results. Run Analyze first.")
    if db.get_available_model() is None:
        raise HTTPException(429, "All models exhausted or OOS for today")
    background_tasks.add_task(job.run_translate)
    return {"ok": True}


@app.get("/api/analyze-status")
async def api_analyze_status():
    return JSONResponse(job.get_analyze_summary())


@app.post("/api/detect-styles")
async def api_detect_styles(payload: TranslationRequest):
    """Detect ASS styles from selected subtitle files (for translate flow)."""
    import srt_pre
    styles = srt_pre.get_styles_from_files(payload.files)
    return JSONResponse({"styles": styles})


@app.post("/api/probe")
async def api_probe(payload: TranslationRequest, background_tasks: BackgroundTasks):
    """Probe MKV files for subtitle tracks."""
    if logger.is_running():
        raise HTTPException(409, "A job is already running")
    if not payload.files:
        raise HTTPException(400, "No files provided")
    background_tasks.add_task(extract.run_probe, payload.files)
    return {"ok": True, "queued": len(payload.files)}


@app.post("/api/extract")
async def api_extract(payload: ExtractRequest, background_tasks: BackgroundTasks):
    """Extract subtitle track from MKV files."""
    if logger.is_running():
        raise HTTPException(409, "A job is already running")
    if not payload.files:
        raise HTTPException(400, "No files provided")
    if not payload.suffix:
        raise HTTPException(400, "Suffix is required")
    background_tasks.add_task(
        extract.run_extract, payload.files, payload.track_index,
        payload.suffix, payload.convert_to_srt
    )
    return {"ok": True, "queued": len(payload.files)}


class FilterStylesRequest(BaseModel):
    paths: List[str]
    keep_styles: List[str]


@app.post("/api/filter-styles")
async def api_filter_styles(req: FilterStylesRequest):
    """Filter styles from extracted ASS files."""
    from extract import _filter_ass_styles
    from logger import log as slog
    filtered = 0
    total_lines_removed = 0
    total_styles_removed = 0
    slog.info(f"STYLE FILTER - {len(req.paths)} files, keeping: {', '.join(req.keep_styles)}")
    for fp in req.paths:
        p = Path(fp)
        if p.exists() and p.suffix == ".ass":
            stats = _filter_ass_styles(str(p), req.keep_styles)
            filtered += 1
            total_lines_removed += stats["lines_removed"]
            total_styles_removed += stats["styles_removed"]
    slog.info(f"STYLE FILTER COMPLETE - {filtered} files, {total_lines_removed} lines removed, {total_styles_removed} styles removed")
    return {"ok": True, "filtered": filtered, "lines_removed": total_lines_removed, "styles_removed": total_styles_removed}


@app.get("/api/browse")
async def api_browse(path: str = "/", mode: str = "translate"):
    p = Path(path.strip("'\" ")).resolve()
    if not p.exists() or not p.is_dir():
        raise HTTPException(404, f"Not a directory: {path}")
    dirs, files = [], []
    sub_exts = {".srt", ".ass"}
    mkv_exts = {".mkv", ".mp4", ".avi"}
    target_exts = mkv_exts if mode == "extract" else sub_exts
    for item in sorted(p.iterdir()):
        if item.is_dir() and not item.name.startswith("."):
            dirs.append({"name": item.name, "path": str(item)})
        elif item.is_file() and item.suffix.lower() in target_exts:
            files.append({
                "name": item.name,
                "path": str(item),
                "size_kb": round(item.stat().st_size / 1024, 1),
            })
    return JSONResponse({"current": str(p), "parent": str(p.parent), "dirs": dirs, "files": files})


class RenameRequest(BaseModel):
    path: str
    new_name: str


@app.post("/api/file/rename")
async def api_file_rename(req: RenameRequest):
    p = Path(req.path)
    if not p.exists():
        raise HTTPException(404, "File not found")
    new_path = p.with_name(req.new_name)
    if new_path.exists():
        raise HTTPException(400, f"File {req.new_name} already exists")
    p.rename(new_path)
    return {"ok": True, "new_path": str(new_path)}


class DeleteRequest(BaseModel):
    paths: List[str]


@app.post("/api/file/delete")
async def api_file_delete(req: DeleteRequest):
    deleted = []
    for fp in req.paths:
        p = Path(fp)
        if p.exists() and p.is_file():
            p.unlink()
            deleted.append(fp)
    return {"ok": True, "deleted": len(deleted)}


@app.post("/api/fix-rtl")
async def api_fix_rtl(req: DeleteRequest):
    """Fix RTL marks on selected subtitle files."""
    from fix_rtl import fix_srt_file, fix_ass_file
    fixed_files = 0
    fixed_lines = 0
    for fp in req.paths:
        p = Path(fp)
        if not p.exists() or not p.is_file():
            continue
        if p.suffix == ".srt":
            count = fix_srt_file(p)
        elif p.suffix == ".ass":
            count = fix_ass_file(p)
        else:
            continue
        fixed_files += 1
        fixed_lines += count
    return {"ok": True, "fixed_files": fixed_files, "fixed_lines": fixed_lines}


@app.get("/api/history")
async def api_history():
    return JSONResponse(db.list_job_history())


@app.get("/api/history/{job_id}")
async def api_history_detail(job_id: str):
    data = db.get_job_history(job_id)
    if data is None:
        raise HTTPException(404, "Job not found")
    return JSONResponse(data)



# Static files - MUST be last (catch-all)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return HTMLResponse(Path("static/index.html").read_text(encoding="utf-8"))
