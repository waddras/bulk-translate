#!/usr/bin/env python3
"""Reassemble translated cues into .ar.srt or .ar.ass output files.

Never skips a file. Untranslated cues keep original text. Output format
and font settings are read from the live cfg at call-time.
"""
import pysubs2
from pathlib import Path

from config import cfg
from logger import log

RLI = "\u2067"
PDI = "\u2069"


def _wrap_rtl(text: str) -> str:
    """Wrap each line within a cue with RLI+PDI pair."""
    lines = text.split("\n")
    return "\n".join(RLI + line + PDI for line in lines)
FONT_SUBSET_PATH = "/opt/bulk-translate/fonts/Amiri-subset.ttf"


def _resolve_output_path(base_path) -> Path:
    """Build output path with correct extension and conflict handling."""
    fpath = Path(str(base_path))
    stem = fpath.stem
    for suffix in (".en", ".eng", ".en.hi"):
        if stem.endswith(suffix):
            stem = stem[:-len(suffix)]
            break
    ext = ".ar.ass" if cfg.get("OUTPUT_FORMAT", "ass") == "ass" else ".ar.srt"
    out_path = fpath.with_name(stem + ext)

    if cfg.get("FILE_CONFLICT", "overwrite") == "rename":
        counter = 1
        base_stem = stem
        while out_path.exists():
            out_path = fpath.with_name(f"{base_stem}.ar_{counter}" + ext.replace(".ar", ""))
            counter += 1
    return out_path


def _ass_encode(data: bytes) -> list:
    """Encode binary font data into ASS UUEncode format."""
    buf = []
    for i in range(0, len(data), 3):
        chunk = data[i:i + 3]
        n = len(chunk)
        b = chunk + b"\x00" * (3 - n)
        vals = [
            b[0] >> 2,
            ((b[0] & 3) << 4) | (b[1] >> 4),
            ((b[1] & 15) << 2) | (b[2] >> 6),
            b[2] & 63,
        ]
        for v in vals[:n + 1]:
            buf.append(chr(v + 33))
    s = "".join(buf)
    return [s[i:i + 80] for i in range(0, len(s), 80)]


def _build_ass_output(blocks: list, meta_cues: list) -> str:
    """Build a complete ASS file string from translated blocks."""
    subs = pysubs2.SSAFile()

    # Apply font style from settings
    style = pysubs2.SSAStyle()
    style.fontname = cfg.get("FONT_NAME", "Amiri")
    style.fontsize = cfg.get("FONT_SIZE", 40)
    style.encoding = 1
    style.alignment = cfg.get("FONT_ALIGNMENT", 2)
    style.outline = cfg.get("FONT_OUTLINE", 1)
    style.shadow = cfg.get("FONT_SHADOW", 0)
    style.bold = False
    style.italic = False
    style.marginl = cfg.get("FONT_MARGIN_L", 20)
    style.marginr = cfg.get("FONT_MARGIN_R", 20)
    style.marginv = cfg.get("FONT_MARGIN_V", 30)
    subs.styles["Default"] = style

    # Add dialogue events
    for block in blocks:
        event = pysubs2.SSAEvent()
        event.start = block["start"]
        event.end = block["end"]
        event.text = block["text"]
        event.style = "Default"
        subs.append(event)

    ass_content = subs.to_string("ass")

    # Embed font if enabled
    if cfg.get("EMBED_FONT", True):
        font_path = Path(FONT_SUBSET_PATH)
        if font_path.exists():
            font_bytes = font_path.read_bytes()
            encoded_lines = _ass_encode(font_bytes)
            font_name = cfg.get("FONT_NAME", "Amiri").replace(" ", "") + "-Regular_0.ttf"
            fonts_section = f"\n[Fonts]\nfontname: {font_name}\n"
            fonts_section += "\n".join(encoded_lines)
            fonts_section += "\n"
            ass_content = ass_content.rstrip() + "\n" + fonts_section
        else:
            log.warning(f"Font subset not found at {FONT_SUBSET_PATH} - skipping embed")

    return ass_content


def reassemble_files(translated_blob: dict, meta: dict, files: list):
    """Write output files. Untranslated cues keep original text.

    Returns (completed_names, warnings_list).
    """
    output_format = cfg.get("OUTPUT_FORMAT", "ass")
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
            pos_tags = m.get("pos_tags", "")

            if arabic is not None:
                text = pos_tags + _wrap_rtl(arabic) if pos_tags else _wrap_rtl(arabic)
            else:
                text = pos_tags + _wrap_rtl(m["text"]) if pos_tags else _wrap_rtl(m["text"])
                untranslated.append((tag, m["text"]))

            blocks.append({
                "start": m["start"],
                "end": m["end"],
                "text": text,
                "block_idx": m["block_idx"],
            })

        out_path = _resolve_output_path(fpath)

        if output_format == "ass":
            ass_content = _build_ass_output(blocks, cues)
            out_path.write_text(ass_content, encoding="utf-8")
        else:
            # SRT output
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
