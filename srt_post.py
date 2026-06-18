#!/usr/bin/env python3
"""Reassemble translated cues back into per-file .ar.srt outputs.

Never skips a file. If some cues are untranslated, uses the original English
text and reports the count. Output cues are renumbered 1..N.
"""
import pysubs2
from pathlib import Path

from config import cfg
from logger import log


RLM = "\u200F"


def _resolve_output_path(base_path) -> Path:
    """Handle file conflict based on cfg['FILE_CONFLICT'] setting."""
    fpath = Path(str(base_path))
    stem = fpath.stem
    for suffix in (".en", ".eng", ".en.hi"):
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
    """Write .ar.srt for every file. Untranslated cues keep original text.

    Returns (completed_names, warnings_list).
    """
    # Group all meta entries by file
    file_cues = {i + 1: [] for i in range(len(files))}
    for tag, m in meta.items():
        file_cues[m["file_idx"]].append((tag, m))

    completed, warnings = [], []

    for file_idx, cues in file_cues.items():
        fpath = files[file_idx - 1]
        if not cues:
            log.warning(f"  No cues for {fpath.name} - skipping (empty)")
            warnings.append(f"{fpath.name}: no cues found")
            continue

        cues.sort(key=lambda x: x[1]["block_idx"])
        untranslated = []
        blocks = []

        for tag, m in cues:
            arabic = translated_blob.get(tag)
            if arabic is not None:
                blocks.append({
                    "start": m["start"],
                    "end": m["end"],
                    "text": RLM + arabic,
                    "block_idx": m["block_idx"],
                })
            else:
                # Keep original text
                blocks.append({
                    "start": m["start"],
                    "end": m["end"],
                    "text": m["text"],
                    "block_idx": m["block_idx"],
                })
                untranslated.append((tag, m["text"]))

        out_path = _resolve_output_path(fpath)
        srt_lines = []
        for i, block in enumerate(blocks, start=1):
            s = pysubs2.time.ms_to_str(block["start"], fractions=True).replace(".", ",")
            e = pysubs2.time.ms_to_str(block["end"], fractions=True).replace(".", ",")
            srt_lines.append(f"{i}\n{s} --> {e}\n{block['text']}\n")
        out_path.write_text("\n".join(srt_lines), encoding="utf-8")

        if untranslated:
            log.warning(f"  {out_path.name}: {len(blocks) - len(untranslated)}/{len(blocks)} "
                        f"translated, {len(untranslated)} kept as original:")
            for tag, text in untranslated[:10]:
                log.warning(f"    [{tag}] \"{text}\"")
            if len(untranslated) > 10:
                log.warning(f"    ... and {len(untranslated) - 10} more")
            warnings.append(f"{out_path.name}: {len(untranslated)} lines untranslated")
            log.info(f"  Written: {out_path.name} ({len(blocks)} cues, {len(untranslated)} original)")
        else:
            log.info(f"  Written: {out_path.name} ({len(blocks)} cues)")

        completed.append(out_path.name)

    return completed, warnings
