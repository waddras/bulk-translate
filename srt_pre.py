#!/usr/bin/env python3
"""Subtitle pre-processing: parse SRT/ASS, clean cue text, drop noise cues.

Drop rule: after cleaning, a cue whose text is exactly ONE character is dropped
UNLESS that character is a digit. Dropped cues never enter the blob/meta.

When PRESERVE_ASS_POSITIONS is enabled, position-related tags (\pos, \an, \move,
\fad, \fade) are preserved separately in the cue dict as "pos_tags" so they can
be re-applied in the output without being sent for translation.
"""
import re

import pysubs2

from config import cfg

_ALL_TAGS_RE = re.compile(r"\{[^}]*\}")


def _get_preserve_tags() -> list:
    """Parse PRESERVE_TAGS setting into a list of tag names."""
    raw = cfg.get("PRESERVE_TAGS", "pos, an, move, fad, fade;")
    raw = raw.rstrip(";").strip()
    return [t.strip() for t in raw.split(",") if t.strip()]


def _extract_pos_tags(raw: str) -> tuple:
    """Extract preserved tags from ASS text based on PRESERVE_TAGS setting.

    Returns (pos_tags_string, cleaned_text).
    """
    preserve_list = _get_preserve_tags()
    if not preserve_list:
        clean = _ALL_TAGS_RE.sub("", raw)
        clean = clean.replace(r"\N", "\n").replace(r"\n", "\n").strip()
        return "", clean

    # Build regex to match any of the preserved tag names
    # Matches \tagname(...) or \tagname followed by a numeric/text value
    tag_pattern = "|".join(re.escape(t) for t in preserve_list)
    preserve_re = re.compile(r"\\(?:" + tag_pattern + r")(?:\([^)]*\)|[^\\}]*)")

    preserved = []
    for match in re.finditer(r"\{([^}]*)\}", raw):
        block_content = match.group(1)
        found = preserve_re.findall(block_content)
        if found:
            preserved.extend(found)

    pos_string = "{" + "".join(preserved) + "}" if preserved else ""

    clean = _ALL_TAGS_RE.sub("", raw)
    clean = clean.replace(r"\N", "\n").replace(r"\n", "\n").strip()

    return pos_string, clean


def clean_event_text(raw: str) -> str:
    """Strip ASS override tags, convert hard line breaks, and trim."""
    text = _ALL_TAGS_RE.sub("", raw or "")
    text = text.replace(r"\N", "\n").replace(r"\n", "\n")
    return text.strip()


def should_drop(text: str) -> bool:
    """True if the cleaned cue is empty, or a single non-digit character."""
    if not text:
        return True
    if len(text) == 1 and not text.isdigit():
        return True
    return False


def parse_file(path, keep_styles: list = None) -> list:
    """Return kept cues as [{text, start, end, pos_tags}, ...] in chronological order.

    If keep_styles is provided, only cues whose style is in the list are kept.
    """
    preserve_pos = cfg.get("PRESERVE_ASS_POSITIONS", False)
    subs = pysubs2.SSAFile.load(str(path))
    cues = []

    for event in subs:
        # Filter by style if specified
        if keep_styles is not None and hasattr(event, 'style'):
            if event.style not in keep_styles:
                continue

        if preserve_pos and event.text:
            pos_tags, clean = _extract_pos_tags(event.text)
        else:
            pos_tags = ""
            clean = clean_event_text(event.text)

        if should_drop(clean):
            continue

        cues.append({
            "text": clean,
            "start": event.start,
            "end": event.end,
            "pos_tags": pos_tags,
        })

    return cues



def get_styles_from_file(path) -> list:
    """Return list of style names from an ASS/SSA file. Returns [] for SRT."""
    try:
        subs = pysubs2.SSAFile.load(str(path))
        return list(subs.styles.keys())
    except Exception:
        return []


def get_styles_from_files(paths: list) -> list:
    """Return unique style names across all files (sorted)."""
    all_styles = set()
    for p in paths:
        all_styles.update(get_styles_from_file(p))
    return sorted(all_styles)
