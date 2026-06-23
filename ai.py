#!/usr/bin/env python3
"""Gemini translation call with retry, model fallback, and OOS handling.

Attempt-level detail goes to the python logger (journalctl) to keep the
web-visible job log readable; job.py emits the high-level per-chunk summaries.
"""
import asyncio
import json

import httpx
import json_repair

from config import cfg
from logger import log, is_cancelled
import db
from blob import estimate_output_tokens

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

_DEFAULT_PROMPT_HEADER = (
    "You are a professional English to Arabic subtitle translator.\n"
    "Translate each value in the following JSON object to Arabic.\n"
    "Return a valid JSON object with the EXACT same keys and ONLY Arabic values.\n"
    "Place punctuation at the END of each Arabic line. No extra keys or explanation.\n\n"
)


def _build_prompt(chunk: dict, show_name: str = "") -> str:
    """Build the translation prompt using the configurable template."""
    template = cfg.get("PROMPT_TEMPLATE", "")
    if template and "{json_blob}" in template:
        name = show_name or "Unknown"
        return template.replace("{show_name}", name).replace("{json_blob}", json.dumps(chunk, ensure_ascii=False))
    # Fallback to basic prompt if template is missing/broken
    return _DEFAULT_PROMPT_HEADER + json.dumps(chunk, ensure_ascii=False)


def _generation_config() -> dict:
    gen = {"temperature": 0.1, "responseMimeType": "application/json"}
    max_out = cfg.get("GEMINI_MAX_OUTPUT_TOKENS", 0)
    if max_out and max_out > 0:
        gen["maxOutputTokens"] = max_out
    return gen


async def translate_chunk(client: httpx.AsyncClient, chunk: dict, chunk_num: int,
                          total: int, api_keys: list, key_idx_ref: list,
                          show_name: str = "") -> dict | None:
    """Translate one chunk. Returns {key: arabic} or None on cancel/total failure."""
    est = estimate_output_tokens(chunk)
    log.info(f"CHUNK {chunk_num}/{total} - {len(chunk)} lines - est. ~{est} output tokens")

    prompt = _build_prompt(chunk, show_name)
    gen_cfg = _generation_config()

    retry_attempts = cfg["RETRY_ATTEMPTS"]
    retry_cooldown = cfg["RETRY_COOLDOWN"]
    failed_models: set = set()

    while True:
        if is_cancelled():
            log.info(f"CHUNK {chunk_num}/{total} - cancelled before model selection")
            return None

        model = db.get_available_model(skip=failed_models)
        if model is None:
            log.warning(f"CHUNK {chunk_num}/{total} - all models OOS/exhausted - sleeping 60s")
            failed_models.clear()
            await asyncio.sleep(60)
            continue

        model_id = model["id"]
        url = f"{GEMINI_BASE}/{model_id}:generateContent"
        key_entry = api_keys[key_idx_ref[0] % len(api_keys)]
        key_idx_ref[0] += 1
        log.info(f"CHUNK {chunk_num}/{total} - model: {model_id} - key: {key_entry['email']}")

        for attempt in range(1, retry_attempts + 1):
            if is_cancelled():
                log.info(f"CHUNK {chunk_num}/{total} - cancelled during attempt {attempt}")
                return None
            try:
                log.info(f"CHUNK {chunk_num}/{total} - [{model_id}] attempt {attempt}/{retry_attempts}")
                response = await client.post(
                    url,
                    headers={"x-goog-api-key": key_entry["api_key"]},
                    json={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": gen_cfg},
                    timeout=300.0,
                )
                if response.status_code == 404:
                    log.warning(f"[{model_id}] 404 dead endpoint - skipping")
                    db.increment_failures(model_id)
                    failed_models.add(model_id)
                    break
                response.raise_for_status()
                raw = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                result = json_repair.loads(raw)
                db.increment_usage(model_id)
                log.info(f"CHUNK {chunk_num}/{total} - [{model_id}] SUCCESS ({len(result)} keys)")
                return result

            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                if code == 404:
                    log.warning(f"[{model_id}] 404 - skipping permanently")
                    db.increment_failures(model_id)
                    failed_models.add(model_id)
                    break
                log.warning(f"CHUNK {chunk_num}/{total} - [{model_id}] attempt {attempt} HTTP {code}")
                if attempt < retry_attempts:
                    log.info(f"Retrying in {retry_cooldown}s...")
                    await asyncio.sleep(retry_cooldown)
                else:
                    f = db.increment_failures(model_id)
                    log.warning(f"[{model_id}] exhausted retries (failure #{f}) - next model")
                    failed_models.add(model_id)

            except Exception as e:
                log.warning(f"CHUNK {chunk_num}/{total} - [{model_id}] attempt {attempt} FAILED: {e}")
                if attempt < retry_attempts:
                    log.info(f"Retrying in {retry_cooldown}s...")
                    await asyncio.sleep(retry_cooldown)
                else:
                    f = db.increment_failures(model_id)
                    log.warning(f"[{model_id}] exhausted retries (failure #{f}) - next model")
                    failed_models.add(model_id)



# === Multi-turn conversation mode ===
async def translate_multi_turn(client: httpx.AsyncClient, chunks: list, full_payload: dict,
                               api_keys: list, show_name: str = "") -> dict:
    """Send full blob as context in turn 1, then request chunks in subsequent turns.

    Returns combined {key: arabic} dict for all chunks.
    """
    translated = {}
    gen_cfg = _generation_config()
    retry_attempts = cfg["RETRY_ATTEMPTS"]
    retry_cooldown = cfg["RETRY_COOLDOWN"]

    # Build initial context message
    name = show_name or "Unknown"
    template = cfg.get("PROMPT_TEMPLATE", "")
    context_msg = (
        f"You are a professional English to Arabic subtitle translator.\n"
        f"Context: These are subtitles from \"{name}\".\n"
        f"Here is the FULL script ({len(full_payload)} lines) for reference. "
        f"DO NOT translate yet. I will ask you to translate specific sections.\n\n"
        f"{json.dumps(full_payload, ensure_ascii=False)}"
    )

    # Conversation history
    contents = [
        {"role": "user", "parts": [{"text": context_msg}]},
        {"role": "model", "parts": [{"text": "Understood. I have the full script. Send me the sections to translate and I will return JSON with the same keys and Arabic values."}]},
    ]

    failed_models = set()
    for i, chunk in enumerate(chunks, 1):
        if is_cancelled():
            log.info(f"Multi-turn: cancelled at chunk {i}")
            break

        chunk_msg = (
            f"Translate ONLY the following {len(chunk)} lines. "
            f"Return a valid JSON object with ONLY these keys and Arabic values. "
            f"No extra keys, no explanation.\n\n"
            f"{json.dumps(chunk, ensure_ascii=False)}"
        )
        contents.append({"role": "user", "parts": [{"text": chunk_msg}]})

        est = estimate_output_tokens(chunk)
        log.info(f"MULTI-TURN {i}/{len(chunks)} - {len(chunk)} lines - est. ~{est} tokens")

        model = db.get_available_model(skip=failed_models)
        if model is None:
            log.warning(f"All models exhausted at chunk {i}")
            break

        model_id = model["id"]
        url = f"{GEMINI_BASE}/{model_id}:generateContent"
        key_entry = api_keys[i % len(api_keys)]
        log.info(f"MULTI-TURN {i}/{len(chunks)} - model: {model_id} - key: {key_entry['email']}")

        success = False
        for attempt in range(1, retry_attempts + 1):
            if is_cancelled():
                break
            try:
                response = await client.post(
                    url,
                    headers={"x-goog-api-key": key_entry["api_key"]},
                    json={"contents": contents, "generationConfig": gen_cfg},
                    timeout=300.0,
                )
                if response.status_code == 404:
                    db.increment_failures(model_id)
                    failed_models.add(model_id)
                    break
                response.raise_for_status()
                raw = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                result = json_repair.loads(raw)
                db.increment_usage(model_id)
                translated.update(result)
                # Add model response to conversation
                contents.append({"role": "model", "parts": [{"text": raw}]})
                log.info(f"MULTI-TURN {i}/{len(chunks)} - SUCCESS ({len(result)} keys)")
                success = True
                break
            except Exception as e:
                log.warning(f"MULTI-TURN {i} attempt {attempt} FAILED: {e}")
                if attempt < retry_attempts:
                    await asyncio.sleep(retry_cooldown)
                else:
                    db.increment_failures(model_id)
                    failed_models.add(model_id)

        if not success:
            # Remove the failed user turn so conversation stays clean
            contents.pop()
            log.warning(f"MULTI-TURN {i} - all attempts failed, skipping chunk")

    return translated


# === Full context mode ===
async def translate_full_context(client: httpx.AsyncClient, chunk: dict, chunk_num: int,
                                 total: int, full_payload: dict, api_keys: list,
                                 key_idx_ref: list, show_name: str = "") -> dict | None:
    """Send entire blob as context + ask for specific chunk keys only.

    Returns {key: arabic} or None.
    """
    est = estimate_output_tokens(chunk)
    log.info(f"FULL-CTX {chunk_num}/{total} - {len(chunk)} lines - est. ~{est} tokens")

    name = show_name or "Unknown"
    prompt = (
        f"You are a professional English to Arabic subtitle translator.\n"
        f"Context: These are subtitles from \"{name}\".\n\n"
        f"FULL SCRIPT for reference ({len(full_payload)} lines):\n"
        f"{json.dumps(full_payload, ensure_ascii=False)}\n\n"
        f"---\n"
        f"Translate ONLY the following {len(chunk)} lines. "
        f"Return a valid JSON object with ONLY these keys and Arabic values. "
        f"No extra keys, no explanation.\n\n"
        f"{json.dumps(chunk, ensure_ascii=False)}"
    )

    gen_cfg = _generation_config()
    retry_attempts = cfg["RETRY_ATTEMPTS"]
    retry_cooldown = cfg["RETRY_COOLDOWN"]
    failed_models = set()

    while True:
        if is_cancelled():
            return None
        model = db.get_available_model(skip=failed_models)
        if model is None:
            log.warning(f"FULL-CTX {chunk_num} - all models exhausted - sleeping 60s")
            failed_models.clear()
            await asyncio.sleep(60)
            continue

        model_id = model["id"]
        url = f"{GEMINI_BASE}/{model_id}:generateContent"
        key_entry = api_keys[key_idx_ref[0] % len(api_keys)]
        key_idx_ref[0] += 1
        log.info(f"FULL-CTX {chunk_num}/{total} - model: {model_id} - key: {key_entry['email']}")

        for attempt in range(1, retry_attempts + 1):
            if is_cancelled():
                return None
            try:
                log.info(f"FULL-CTX {chunk_num} - [{model_id}] attempt {attempt}/{retry_attempts}")
                response = await client.post(
                    url,
                    headers={"x-goog-api-key": key_entry["api_key"]},
                    json={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": gen_cfg},
                    timeout=300.0,
                )
                if response.status_code == 404:
                    db.increment_failures(model_id)
                    failed_models.add(model_id)
                    break
                response.raise_for_status()
                raw = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                result = json_repair.loads(raw)
                db.increment_usage(model_id)
                log.info(f"FULL-CTX {chunk_num}/{total} - [{model_id}] SUCCESS ({len(result)} keys)")
                return result
            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                if code == 404:
                    db.increment_failures(model_id)
                    failed_models.add(model_id)
                    break
                log.warning(f"FULL-CTX {chunk_num} - [{model_id}] attempt {attempt} HTTP {code}")
                if attempt < retry_attempts:
                    await asyncio.sleep(retry_cooldown)
                else:
                    db.increment_failures(model_id)
                    failed_models.add(model_id)
            except Exception as e:
                log.warning(f"FULL-CTX {chunk_num} - [{model_id}] attempt {attempt} FAILED: {e}")
                if attempt < retry_attempts:
                    await asyncio.sleep(retry_cooldown)
                else:
                    db.increment_failures(model_id)
                    failed_models.add(model_id)
