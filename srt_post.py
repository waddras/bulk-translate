#!/usr/bin/env python3
"""Reassemble translated cues back into per-file .ar.srt outputs.

A file is only written if EVERY one of its cues was translated; otherwise it is
reported as skipped (partial). Output cues are renumbered 1..N, so any cues that
were dropped upstream (single-char noise) simply don't appear.
"""
import pysubs2

from config import cfg
from logger import log


def _resolve_output_path(base_path) -> Path:
    """Handle file conflict based on cfg['FILE_CONFLICT'] setting."""
    from pathlib import Path
    out_path = Path(str(base_path).rsplit(".", 1)[0] + ".ar.srt") if not str(base_path).endswith(".ar.srt") else base_path
    # Build proper output path
    fpath = Path(str(base_path))
    # Strip language suffix and extension, add .ar.srt
    stem = fpath.stem
    # Remove .en or .eng suffix if present
    for suffix in (".en", ".eng"):
        if stem.endswith(suffix):
            stem = stem[:-len(suffix)]
            break
    out_path = fpath.with_name(stem + ".ar.srt")

    if cfg.get("FILE_CONFLICT", "overwrite") == "rename":
        counter = 1
        while out_path.exists():
            out_path = fpath.with_name(f"{stem}.ar_{counter}.srt")
            counter += 1
    return out_path


def reassemble_files(translated_blob: dict, meta: dict, files: list):
    """Write .ar.srt next to each fully-translated source file.

    Returns (completed_names, skipped_names).
    """
    file_blocks = {i + 1: [] for i in range(len(files))}
    for tag, arabic in translated_blob.items():
        m = meta.get(tag)
        if m is None:
            log.warning(f"Tag {tag} missing from meta - skipping")
            continue
        file_blocks[m["file_idx"]].append({
            "start":     m["start"],
            "end":       m["end"],
            "text":      arabic,
            "block_idx": m["block_idx"],
        })

    completed, skipped = [], []
    for file_idx, blocks in file_blocks.items():
        fpath = files[file_idx - 1]

        if not blocks:
            log.warning(f"  No translated cues for {fpath.name} - skipping")
            skipped.append(fpath.name)
            continue

        expected = sum(1 for m in meta.values() if m["file_idx"] == file_idx)
        if len(blocks) < expected:
            log.warning(f"  {fpath.name}: only {len(blocks)}/{expected} cues translated - skipping (partial)")
            skipped.append(fpath.name)
            continue

        blocks.sort(key=lambda b: b["block_idx"])
        out_path = _resolve_output_path(fpath)
        RLM = "\u200F"
        srt_lines = []
        for i, block in enumerate(blocks, start=1):
            s = pysubs2.time.ms_to_str(block["start"], fractions=True).replace(".", ",")
            e = pysubs2.time.ms_to_str(block["end"],   fractions=True).replace(".", ",")
            text = RLM + block["text"]
            srt_lines.append(f"{i}\n{s} --> {e}\n{text}\n")
        out_path.write_text("\n".join(srt_lines), encoding="utf-8")
        log.info(f"  Written: {out_path.name} ({len(blocks)} cues)")
        completed.append(out_path.name)

    return completed, skipped
