#!/usr/bin/env python3
"""Reassemble translated cues back into per-file .ar.srt outputs.

A file is only written if EVERY one of its cues was translated; otherwise it is
reported as skipped (partial). Output cues are renumbered 1..N, so any cues that
were dropped upstream (single-char noise) simply don't appear.
"""
import pysubs2

from logger import log


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
        out_path = fpath.with_suffix(".ar.srt")
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
