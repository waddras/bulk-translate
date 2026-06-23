#!/usr/bin/env python3
"""Background job orchestration: Analyze (P1+P2) then Translate (P3+P4).

The two-step flow stores analyze results in module-level state so that
Translate can pick them up without re-parsing.
"""
from pathlib import Path

import httpx

from config import cfg, GEMINI_API_KEY_ENV
import logger
from logger import jlog
import db
import blob
import ai
import sub_post

SEP = "=" * 60

# ── Stored analyze state ─────────────────────────────────────────────────────
_analyze_state = {
    "ready": False,
    "files": [],
    "meta": {},
    "chunks": [],
    "payload": {},
    "file_paths": [],
    "settings_hash": None,
    "show_name": "",
}


def _settings_hash():
    """Simple hash of settings that affect chunking so we can detect changes."""
    return f"{cfg['NUM_CHUNKS']}|{cfg['MAX_BLOB_LINES']}"


def is_analyze_ready() -> bool:
    """True if analyze completed and settings haven't changed since."""
    return _analyze_state["ready"] and _analyze_state["settings_hash"] == _settings_hash()


def get_analyze_summary() -> dict:
    return {
        "ready": is_analyze_ready(),
        "file_count": len(_analyze_state["files"]),
        "chunk_count": len(_analyze_state["chunks"]),
        "show_name": _analyze_state.get("show_name", ""),
    }


def set_show_name(name: str):
    """Override the auto-detected show name."""
    _analyze_state["show_name"] = name


def _detect_show_name(files: list) -> str:
    """Auto-detect show name from filenames (common prefix before ' - S' or ' - E')."""
    import re
    names = [f.stem for f in files]
    if not names:
        return ""
    # Try to find common prefix before season/episode marker
    patterns = [r'^(.+?)\s*-\s*S\d', r'^(.+?)\s*-\s*E\d', r'^(.+?)\s+S\d']
    for pattern in patterns:
        matches = []
        for name in names:
            m = re.match(pattern, name)
            if m:
                matches.append(m.group(1).strip())
        if matches:
            # Return the most common match
            from collections import Counter
            return Counter(matches).most_common(1)[0][0]
    # Fallback: longest common prefix
    if len(names) == 1:
        return names[0].split(' - ')[0].strip() if ' - ' in names[0] else names[0]
    prefix = names[0]
    for name in names[1:]:
        while not name.startswith(prefix) and prefix:
            prefix = prefix[:-1]
    return prefix.strip().rstrip('-').strip()


def invalidate_analyze():
    """Clear stored analyze state (called when selection or settings change)."""
    _analyze_state["ready"] = False
    _analyze_state["files"] = []
    _analyze_state["meta"] = {}
    _analyze_state["chunks"] = []
    _analyze_state["file_paths"] = []


# ── Phase 1+2: Analyze ────────────────────────────────────────────────────────
async def run_analyze(file_paths: list, keep_styles: list = None) -> None:
    logger.reset_job_status()
    logger.clear_cancel()
    invalidate_analyze()

    try:
        files = [Path(p) for p in file_paths]
        missing = [str(f) for f in files if not f.exists()]
        if missing:
            raise FileNotFoundError(f"Missing: {missing}")

        jlog(SEP)
        jlog(f"ANALYZE - {len(files)} files")
        for i, f in enumerate(files, 1):
            jlog(f"  [{i:02d}] {f.name}  ({f.stat().st_size / 1024:.1f} KB)")

        jlog(f"Settings: NUM_CHUNKS={cfg['NUM_CHUNKS']}, "
             f"MAX_BLOB_LINES={cfg['MAX_BLOB_LINES']}")

        # Phase 1
        jlog(SEP)
        jlog("PHASE 1 - Building blob...")
        meta, payload, stats = blob.build_blob(files, keep_styles=keep_styles)
        if stats["total"] == 0:
            raise ValueError("No dialogue cues found in selected files.")
        if stats["total"] > cfg["MAX_BLOB_LINES"]:
            raise ValueError(
                f"Blob too large: {stats['total']} cues > limit {cfg['MAX_BLOB_LINES']}. "
                "Select fewer files."
            )
        jlog(f"DEDUP: {stats['total']} total cues -> {stats['unique']} unique lines "
             f"({stats['collapsed']} duplicates collapsed, ~{stats['pct']}% fewer tokens)")

        # Phase 2
        jlog(SEP)
        jlog("PHASE 2 - Splitting unique lines into chunks...")
        chunks = blob.split_blob(payload)
        jlog(f"Split into {len(chunks)} chunks")
        total_tokens = 0
        for i, ch in enumerate(chunks, 1):
            est = blob.estimate_output_tokens(ch)
            total_tokens += est
            jlog(f"  Chunk {i}: {len(ch)} lines, est. {est} output tokens")
        jlog(f"Total estimated output tokens: {total_tokens}")

        # Store for Translate phase
        _analyze_state["ready"] = True
        _analyze_state["files"] = files
        _analyze_state["meta"] = meta
        _analyze_state["chunks"] = chunks
        _analyze_state["payload"] = payload
        _analyze_state["file_paths"] = file_paths
        _analyze_state["settings_hash"] = _settings_hash()
        _analyze_state["show_name"] = _detect_show_name(files)

        jlog(f"Detected show: {_analyze_state['show_name']}")
        jlog(SEP)
        jlog("ANALYZE COMPLETE - Ready to translate. Click Translate to proceed.")
        logger.set_done()

    except Exception as e:
        logger.log.error(f"Analyze FAILED: {e}")
        logger.set_error(str(e))
        logger.set_done()
    finally:
        logger.set_running(False)


# ── Phase 3+4: Translate ──────────────────────────────────────────────────────
async def run_translate() -> None:
    logger.reset_job_status()
    logger.clear_cancel()

    try:
        if not is_analyze_ready():
            raise ValueError("No valid analyze results. Run Analyze first.")

        files = _analyze_state["files"]
        meta = _analyze_state["meta"]
        chunks = _analyze_state["chunks"]
        payload = _analyze_state.get("payload", {})
        show_name = _analyze_state.get("show_name", "")
        mode = cfg.get("TRANSLATION_MODE", "chunked")

        jlog(SEP)
        jlog(f"TRANSLATE - {len(files)} files, {len(chunks)} chunks, mode: {mode}")
        jlog(f"Show: {show_name}")

        # Check API keys
        api_keys = db.get_active_keys()
        if not api_keys:
            if GEMINI_API_KEY_ENV:
                api_keys = [{"id": 0, "email": "env-key", "api_key": GEMINI_API_KEY_ENV}]
            else:
                raise ValueError("No active API keys. Add via Keys tab or set GEMINI_API_KEY.")
        jlog(f"Active keys: {[k['email'] for k in api_keys]}")
        jlog(f"GEMINI_MAX_OUTPUT_TOKENS={cfg['GEMINI_MAX_OUTPUT_TOKENS'] or 'model-default'}")

        # Phase 3 — dispatch by mode
        jlog(SEP)
        jlog("PHASE 3 - Translating...")
        translated_unique = {}
        key_idx_ref = [0]

        if mode == "multi_turn":
            jlog(f"Mode: Multi-turn conversation ({len(payload)} lines as context)")
            async with httpx.AsyncClient() as client:
                translated_unique = await ai.translate_multi_turn(
                    client, chunks, payload, api_keys, show_name
                )
                for i, chunk in enumerate(chunks, 1):
                    done = sum(1 for k in chunk if k in translated_unique)
                    jlog(f"  Chunk {i}/{len(chunks)} - {done}/{len(chunk)} lines")

        elif mode == "full_context":
            jlog(f"Mode: Full context per chunk ({len(payload)} lines sent each time)")
            async with httpx.AsyncClient() as client:
                for i, chunk in enumerate(chunks, 1):
                    if logger.is_cancelled():
                        jlog(f"CANCELLED after chunk {i - 1}/{len(chunks)}")
                        break
                    result = await ai.translate_full_context(
                        client, chunk, i, len(chunks), payload, api_keys, key_idx_ref, show_name
                    )
                    if result:
                        translated_unique.update(result)
                        jlog(f"  Chunk {i}/{len(chunks)} - {len(result)} unique lines translated")
                    else:
                        jlog(f"  Chunk {i}/{len(chunks)} - FAILED or cancelled")

        else:  # chunked (default)
            async with httpx.AsyncClient() as client:
                for i, chunk in enumerate(chunks, 1):
                    if logger.is_cancelled():
                        jlog(f"CANCELLED after chunk {i - 1}/{len(chunks)}")
                        break

                    result = await ai.translate_chunk(
                        client, chunk, i, len(chunks), api_keys, key_idx_ref, show_name
                    )
                    if result:
                        translated_unique.update(result)
                        jlog(f"  Chunk {i}/{len(chunks)} - {len(result)} unique lines translated")
                    else:
                        jlog(f"  Chunk {i}/{len(chunks)} - FAILED or cancelled")
                        result = {}

                    # CHECK: verify all sent keys came back
                    sent_keys = set(chunk.keys())
                    returned_keys = set(result.keys()) if result else set()
                    missing_keys = sent_keys - returned_keys

                    if not missing_keys:
                        jlog(f"  Chunk {i}/{len(chunks)} - verification OK, all lines returned")
                    elif i < len(chunks):
                        jlog(f"  Chunk {i}/{len(chunks)} - {len(missing_keys)} lines missing:")
                        for mk in sorted(missing_keys):
                            jlog(f"    [{mk}] \"{chunk[mk]}\"")
                        jlog(f"  -> Appending {len(missing_keys)} missing lines to chunk {i+1}")
                        for mk in missing_keys:
                            chunks[i][mk] = chunk[mk]
                    else:
                        jlog(f"  Chunk {i}/{len(chunks)} (last) - {len(missing_keys)} lines missing:")
                        for mk in sorted(missing_keys):
                            jlog(f"    [{mk}] \"{chunk[mk]}\"")
                        jlog(f"  -> Sending retry chunk ({len(missing_keys)} lines) from priority 1...")
                        retry_chunk = {mk: chunk[mk] for mk in missing_keys}
                        retry_key_idx = [0]
                        retry_result = await ai.translate_chunk(
                            client, retry_chunk, len(chunks) + 1, len(chunks) + 1,
                            api_keys, retry_key_idx, show_name
                        )
                        if retry_result:
                            translated_unique.update(retry_result)
                            still_missing = missing_keys - set(retry_result.keys())
                            if still_missing:
                                jlog(f"  Retry recovered {len(retry_result)} lines, "
                                     f"{len(still_missing)} still untranslated (keeping original):")
                                for sm in sorted(still_missing):
                                    jlog(f"    [{sm}] \"{chunk[sm]}\"")
                            else:
                                jlog(f"  Retry recovered all {len(retry_result)} missing lines")
                        else:
                            jlog(f"  Retry FAILED - {len(missing_keys)} lines will keep original text:")
                            for mk in sorted(missing_keys):
                                jlog(f"    [{mk}] \"{chunk[mk]}\"")
        cancelled = logger.is_cancelled()
        if cancelled:
            logger.mark_cancelled()
            jlog("Job cancelled - writing any fully translated files...")

        # Phase 4
        jlog(SEP)
        jlog("PHASE 4 - Reassembling output files...")
        translated_blob = blob.expand_translations(translated_unique, meta)
        completed, warnings = sub_post.reassemble_files(translated_blob, meta, files)
        logger.set_completed(completed)
        logger.set_skipped(warnings)

        jlog(SEP)
        jlog(f"{'CANCELLED' if cancelled else 'COMPLETE'} - "
             f"{len(completed)} files written" +
             (f", {len(warnings)} with warnings" if warnings else ""))
        for f in completed:
            jlog(f"  done: {f}")
        for w in warnings:
            jlog(f"  warning: {w}")

        # Invalidate analyze after successful translate
        if not cancelled:
            invalidate_analyze()

        logger.set_done()

    except Exception as e:
        logger.log.error(f"Translate FAILED: {e}")
        logger.set_error(str(e))
        logger.set_done()
    finally:
        logger.set_running(False)
