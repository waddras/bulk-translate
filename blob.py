#!/usr/bin/env python3
"""Blob construction, deduplication, splitting, token estimation, and expansion.

Tag scheme: "FFLLLL" — 2-digit file index + 4-digit cue index within that file.

`meta` keeps EVERY cue (each with its own tag + timestamps) so reassembly is
unaffected by dedup. The translation `payload` carries each unique cleaned line
only ONCE (keyed by the first tag that produced it — the "representative"), and
every cue records its representative in meta["rep"] so translations fan back out
to all occurrences. Dedup is exact-match, case-sensitive, on cleaned text, and
global across all selected files.
"""
from config import cfg
from logger import jlog, log
import srt_pre


def build_blob(files: list, keep_styles: list = None):
    """Return (meta, payload, stats).

    meta:    {tag: {file_idx, file_path, block_idx, start, end, text, rep}}
    payload: {rep_tag: text}  -- unique lines only
    stats:   {total, unique, collapsed, pct}
    """
    meta = {}
    payload = {}
    text_to_rep = {}
    total = 0

    for file_idx, fpath in enumerate(files, start=1):
        file_id = f"{file_idx:02d}"
        try:
            cues = srt_pre.parse_file(fpath, keep_styles=keep_styles)
        except Exception as e:
            jlog(f"  Failed to parse {fpath.name}: {e}")
            continue

        for block_num, cue in enumerate(cues, start=1):
            tag = f"{file_id}{block_num:04d}"
            text = cue["text"]
            total += 1

            rep = text_to_rep.get(text)
            if rep is None:
                rep = tag
                text_to_rep[text] = tag
                payload[tag] = text

            meta[tag] = {
                "file_idx":  file_idx,
                "file_path": str(fpath),
                "block_idx": block_num,
                "start":     cue["start"],
                "end":       cue["end"],
                "text":      text,
                "rep":       rep,
                "pos_tags":  cue.get("pos_tags", ""),
            }
        jlog(f"  [{file_id}] {fpath.name} -> {len(cues)} cues")

    unique = len(payload)
    collapsed = total - unique
    pct = round(collapsed / total * 100) if total else 0
    stats = {"total": total, "unique": unique, "collapsed": collapsed, "pct": pct}
    return meta, payload, stats


def estimate_output_tokens(chunk: dict) -> int:
    """Rough Arabic output-token estimate (chars * 1.5 / 3)."""
    total_chars = sum(len(v) for v in chunk.values())
    return int(total_chars / 3 * 1.5)


def split_blob(payload: dict) -> list:
    """Split the unique payload into equal chunks, each <= MAX_LINES_PER_CHUNK."""
    max_lines = max(1, cfg.get("MAX_LINES_PER_CHUNK", 1000))
    items = list(payload.items())
    total = len(items)
    if total <= max_lines:
        return [dict(items)]
    num_chunks = (total + max_lines - 1) // max_lines  # ceil division
    chunk_size = (total + num_chunks - 1) // num_chunks  # distribute evenly
    chunks = []
    for i in range(0, total, chunk_size):
        chunks.append(dict(items[i:i + chunk_size]))
    return chunks


def expand_translations(translated_unique: dict, meta: dict) -> dict:
    """Fan unique-line translations back out to every cue via meta["rep"].

    Returns {tag: arabic} only for cues whose representative was translated;
    cues whose rep is missing are left out so the partial-file check can catch
    them downstream.
    """
    out = {}
    for tag, m in meta.items():
        arabic = translated_unique.get(m["rep"])
        if arabic is not None:
            out[tag] = arabic
    return out



def build_retry_with_context(missing_keys: set, full_payload: dict, context_lines: int = 3) -> list:
    """Build retry chunks for missing keys, including neighboring lines as context.

    Each retry chunk contains the missing lines + surrounding context lines.
    Returns list of dicts: [{"translate_keys": [...], "context": {all keys+values}}]
    """
    all_keys = list(full_payload.keys())
    key_to_idx = {k: i for i, k in enumerate(all_keys)}
    max_lines = max(1, cfg.get("MAX_LINES_PER_CHUNK", 1000))

    # For each missing key, gather its context window
    missing_sorted = sorted(missing_keys, key=lambda k: key_to_idx.get(k, 0))

    # Split missing into batches of max_lines
    batches = []
    for i in range(0, len(missing_sorted), max_lines):
        batch_keys = missing_sorted[i:i + max_lines]
        batches.append(batch_keys)

    result = []
    for batch_keys in batches:
        # Collect context: for each missing key, include neighbors
        context_set = set()
        for k in batch_keys:
            idx = key_to_idx.get(k, 0)
            for offset in range(-context_lines, context_lines + 1):
                neighbor_idx = idx + offset
                if 0 <= neighbor_idx < len(all_keys):
                    context_set.add(all_keys[neighbor_idx])

        # Build the context dict (includes the missing keys + neighbors)
        context = {k: full_payload[k] for k in sorted(context_set, key=lambda x: key_to_idx.get(x, 0))}
        result.append({
            "translate_keys": batch_keys,
            "context": context,
        })

    return result
