#!/usr/bin/env python3
"""Subtitle pre-processing: parse SRT/ASS, clean cue text, drop noise cues.

Drop rule (per locked spec): after cleaning, a cue whose text is exactly ONE
character is dropped UNLESS that character is a digit. So "5" survives while
"!", "-", "I", and a lone music note are removed. Dropped cues never enter the
blob/meta and therefore vanish from the final translated SRT.
"""
import re

import pysubs2

_TAG_RE = re.compile(r"\{[^}]*\}")


def clean_event_text(raw: str) -> str:
    """Strip ASS override tags, convert hard line breaks, and trim."""
    text = _TAG_RE.sub("", raw or "")
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
    """Return kept cues as [{text, start, end}, ...] in chronological order."""
    subs = pysubs2.SSAFile.load(str(path))
    cues = []
    for event in subs:
        clean = clean_event_text(event.text)
        if should_drop(clean):
            continue
        cues.append({"text": clean, "start": event.start, "end": event.end})
    return cues
