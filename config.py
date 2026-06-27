#!/usr/bin/env python3
"""Configuration: paths, default settings, and live (mutable) cfg dict.

This module is a leaf — it must not import any of our other modules so it can
be safely imported everywhere. `cfg` is mutated IN PLACE (never rebound) so
that every module reading `config.cfg[...]` at call-time always sees the
latest values after a settings update.
"""
import os
import json
import logging
from pathlib import Path

log = logging.getLogger("bulk-translate.config")

# ── Paths ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY_ENV = os.environ.get("GEMINI_API_KEY", "")
DB_PATH       = "/opt/bulk-translate/bulk-translate.db"
BULK_DIR      = "/opt/bulk-translate"
SETTINGS_PATH = "/opt/bulk-translate/settings.json"

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "NUM_CHUNKS":               1,      # split deduped blob into N chunks (1 = single shot)
    "MAX_LINES_PER_CHUNK":      1000,   # max lines per chunk (chunks split evenly, each <= this)
    "PARALLEL_CHUNKS":          1,      # number of chunks sent simultaneously (1 = sequential)
    "PARALLEL_COOLDOWN":        60,     # seconds between parallel batch starts
    "TRANSLATION_MODE":         "chunked",  # "chunked", "multi_turn", or "full_context"
    "GEMINI_MAX_OUTPUT_TOKENS": 0,      # sent as maxOutputTokens (0 = omit, use model default)
    "OOS_THRESHOLD":            2,      # retry-exhaustions/day before a model is marked OOS
    "RETRY_ATTEMPTS":           5,
    "RETRY_COOLDOWN":           10,     # seconds between retries
    "MAX_BLOB_LINES":           50000,  # sanity cap on total cues per job
    "MAX_FAILED_CHUNKS":        5,      # max retry chunks for untranslated lines before giving up
    "FILE_CONFLICT":            "overwrite",  # "overwrite" or "rename"
    "EMBED_FONT":               True,   # embed subsetted font in ASS output
    "PRESERVE_TAGS":            "pos, an, move, fad, fade;",  # comma-separated tag names to preserve
    "FONT_NAME":                "Amiri",
    "FONT_SIZE":                40,
    "FONT_OUTLINE":             1,
    "FONT_SHADOW":              0,
    "FONT_ALIGNMENT":           2,
    "FONT_MARGIN_L":            20,
    "FONT_MARGIN_R":            20,
    "FONT_MARGIN_V":            30,
    "PROMPT_TEMPLATE":          "You are a professional English to Arabic subtitle translator.\n\nContext: These are subtitles from the anime \"{show_name}\". The lines below form a continuous conversation in sequential order — use the full context to produce natural, flowing Arabic dialogue.\n\nRules:\n- Translate to Modern Standard Arabic (MSA), but keep dialogue natural and conversational\n- These lines are a continuous scene — maintain consistency in tone, character voice, and references across all lines\n- Preserve humor, sarcasm, and emotional tone\n- Keep translations concise — must be readable as subtitles\n\nTranslate each value in the following JSON object.\nReturn a valid JSON object with the EXACT same keys and ONLY Arabic values.\nNo extra keys, no explanation, no markdown.\n\n{json_blob}",
}


def load_settings() -> dict:
    """Load settings.json merged over DEFAULT_SETTINGS (defaults fill any gaps)."""
    merged = json.loads(json.dumps(DEFAULT_SETTINGS))  # deep copy
    try:
        if Path(SETTINGS_PATH).exists():
            with open(SETTINGS_PATH) as f:
                merged.update(json.load(f))
    except Exception as e:
        log.warning(f"Failed to load settings ({e}); using defaults")
    return merged


def save_settings(s: dict) -> None:
    Path(SETTINGS_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(s, f, indent=2)


# Live config object. IMPORTANT: mutate in place via update_settings(), never rebind.
cfg = load_settings()


def update_settings(new_values: dict) -> dict:
    """Mutate cfg in place and persist. Returns the live cfg."""
    cfg.update(new_values)
    save_settings(cfg)
    log.info("Settings updated and saved")
    return cfg
