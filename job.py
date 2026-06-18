#!/usr/bin/env python3
"""Background job orchestration: build -> dedup/split -> translate -> reassemble."""
from pathlib import Path

import httpx

from config import cfg, GEMINI_API_KEY_ENV
import logger
from logger import jlog
import db
import blob
import ai
import srt_post

SEP = "=" * 60


async def run_bulk_job(file_paths: list) -> None:
    logger.reset_job_status()
    logger.clear_cancel()

    try:
        files = [Path(p) for p in file_paths]
        missing = [str(f) for f in files if not f.exists()]
        if missing:
            raise FileNotFoundError(f"Missing: {missing}")

        jlog(SEP)
        jlog(f"BULK JOB START - {len(files)} files")
        for i, f in enumerate(files, 1):
            jlog(f"  [{i:02d}] {f.name}  ({f.stat().st_size / 1024:.1f} KB)")

        api_keys = db.get_active_keys()
        if not api_keys:
            if GEMINI_API_KEY_ENV:
                api_keys = [{"id": 0, "email": "env-key", "api_key": GEMINI_API_KEY_ENV}]
            else:
                raise ValueError("No active API keys. Add via Keys tab or set GEMINI_API_KEY.")
        jlog(f"Active keys: {[k['email'] for k in api_keys]}")
        jlog(f"Limits: CHUNK_SIZE={cfg['CHUNK_SIZE']} blocks, "
             f"CHUNK_OUTPUT_TOKENS={cfg['CHUNK_OUTPUT_TOKENS'] or 'off'}, "
             f"GEMINI_MAX_OUTPUT_TOKENS={cfg['GEMINI_MAX_OUTPUT_TOKENS'] or 'model-default'}")

        jlog(SEP)
        jlog("PHASE 1 - Building blob...")
        meta, payload, stats = blob.build_blob(files)
        if stats["total"] == 0:
            raise ValueError("No dialogue cues found in selected files.")
        if stats["total"] > cfg["MAX_BLOB_LINES"]:
            raise ValueError(
                f"Blob too large: {stats['total']} cues > limit {cfg['MAX_BLOB_LINES']}. "
                "Select fewer files."
            )
        jlog(f"DEDUP: {stats['total']} total cues -> {stats['unique']} unique lines "
             f"({stats['collapsed']} duplicates collapsed, ~{stats['pct']}% fewer tokens)")

        jlog(SEP)
        jlog("PHASE 2 - Splitting unique lines into chunks...")
        chunks = blob.split_blob(payload)
        jlog(f"Split into {len(chunks)} chunks")
        for i, ch in enumerate(chunks, 1):
            jlog(f"  Chunk {i}: {len(ch)} lines, est. {blob.estimate_output_tokens(ch)} output tokens")

        jlog(SEP)
        jlog("PHASE 3 - Translating...")
        translated_unique = {}
        key_idx_ref = [0]
        async with httpx.AsyncClient() as client:
            for i, chunk in enumerate(chunks, 1):
                if logger.is_cancelled():
                    jlog(f"CANCELLED after chunk {i - 1}/{len(chunks)}")
                    break
                result = await ai.translate_chunk(client, chunk, i, len(chunks), api_keys, key_idx_ref)
                if result:
                    translated_unique.update(result)
                    jlog(f"  Chunk {i}/{len(chunks)} - {len(result)} unique lines translated")
                else:
                    jlog(f"  Chunk {i}/{len(chunks)} - FAILED or cancelled, skipping")

        cancelled = logger.is_cancelled()
        if cancelled:
            logger.mark_cancelled()
            jlog("Job cancelled - writing any fully translated files...")

        jlog(SEP)
        jlog("PHASE 4 - Reassembling output files...")
        translated_blob = blob.expand_translations(translated_unique, meta)
        completed, skipped = srt_post.reassemble_files(translated_blob, meta, files)
        logger.set_completed(completed)
        logger.set_skipped(skipped)

        jlog(SEP)
        jlog(f"{'CANCELLED' if cancelled else 'COMPLETE'} - "
             f"{len(completed)} files written, {len(skipped)} skipped")
        for f in completed:
            jlog(f"  done: {f}")
        for f in skipped:
            jlog(f"  skipped: {f} (partial or no translation)")

        logger.set_done()

    except Exception as e:
        logger.log.error(f"Bulk job FAILED: {e}")
        logger.set_error(str(e))
        logger.set_done()
    finally:
        logger.set_running(False)
