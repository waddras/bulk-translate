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
_POS_TAG_RE = re.compile(r"\\(?:pos|an|move|fad|fade)\([^)]*\)")
_STRIP_TAG_RE = re.compile(r"\{[^}]*\}")


def _extract_pos_tags(raw: str) -> tuple:
    """Extract position tags from ASS text, return (pos_tags_string, cleaned_text).

    pos_tags_string contains only the preserved tags wrapped in {}, e.g. "{\\pos(320,50)\\an8}"
    cleaned_text has all tags removed.
    """
    # Find all tag blocks
    preserved = []
    for match in re.finditer(r"\{([^}]*)\}", raw):
        block_content = match.group(1)
        # Extract position-related tags from this block
        pos_tags = _POS_TAG_RE.findall(block_content)
        if pos_tags:
            preserved.extend(pos_tags)

    # Build preserved tag string
    pos_string = "{" + "".join(preserved) + "}" if preserved else ""

    # Clean all tags from text
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


def parse_file(path) -> list:
    """Return kept cues as [{text, start, end, pos_tags}, ...] in chronological order."""
    preserve_pos = cfg.get("PRESERVE_ASS_POSITIONS", False)
    subs = pysubs2.SSAFile.load(str(path))
    cues = []

    for event in subs:
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
