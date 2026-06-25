#!/usr/bin/env python3
"""Fix RTL marks on existing translated subtitle files.

Replaces old single RLI at start with proper RLI+PDI pair on each sub-line.
Works on both .srt and .ass files.

Usage:
    python3 fix_rtl.py /path/to/folder
    python3 fix_rtl.py /path/to/file.ar.srt
    python3 fix_rtl.py /path/to/file.ar.ass

Processes all .ar.srt and .ar.ass files in the given path (recursive).
"""
import sys
from pathlib import Path

RLI = "\u2067"
PDI = "\u2069"
RLM = "\u200F"
RLE = "\u202B"
PDF = "\u202C"

# All old bidi marks we want to strip before re-wrapping
OLD_MARKS = {RLI, PDI, RLM, RLE, PDF}


def strip_bidi(text: str) -> str:
    """Remove all existing bidi marks from text."""
    return "".join(c for c in text if c not in OLD_MARKS)


def wrap_rtl(text: str) -> str:
    """Wrap each sub-line with RLI+PDI pair."""
    lines = text.split("\n")
    return "\n".join(RLI + line + PDI for line in lines)


def fix_srt_file(filepath: Path) -> int:
    """Fix RTL in an SRT file. Returns number of cues fixed."""
    content = filepath.read_text(encoding="utf-8", errors="replace")
    lines = content.split("\n")
    fixed = 0
    result = []

    for line in lines:
        # Skip index lines, timestamp lines, and empty lines
        stripped = line.strip()
        if not stripped or stripped.isdigit() or "-->" in stripped:
            result.append(line)
        else:
            # This is a text line — strip old marks and re-wrap
            clean = strip_bidi(line)
            if clean:
                result.append(RLI + clean + PDI)
                fixed += 1
            else:
                result.append(line)

    filepath.write_text("\n".join(result), encoding="utf-8")
    return fixed


def fix_ass_file(filepath: Path) -> int:
    """Fix RTL in an ASS file. Returns number of dialogue lines fixed."""
    content = filepath.read_text(encoding="utf-8", errors="replace")
    lines = content.split("\n")
    fixed = 0
    result = []
    in_events = False

    for line in lines:
        if line.strip().lower() == "[events]":
            in_events = True
            result.append(line)
            continue
        if line.startswith("[") and in_events:
            in_events = False

        if in_events and line.startswith("Dialogue:"):
            # Split at the last comma-separated field (Text)
            parts = line.split(",", 9)
            if len(parts) >= 10:
                text_part = parts[9]
                # Preserve ASS tags at the start
                import re
                tag_match = re.match(r"^(\{[^}]*\})*", text_part)
                tags = tag_match.group(0) if tag_match else ""
                clean_text = text_part[len(tags):]
                # Strip old bidi marks from the text portion
                clean_text = strip_bidi(clean_text)
                # Re-wrap each sub-line (ASS uses \N for line breaks)
                sub_lines = clean_text.replace("\\N", "\n").split("\n")
                wrapped = "\\N".join(RLI + sl + PDI for sl in sub_lines)
                parts[9] = tags + wrapped
                result.append(",".join(parts))
                fixed += 1
            else:
                result.append(line)
        else:
            result.append(line)

    filepath.write_text("\n".join(result), encoding="utf-8")
    return fixed


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 fix_rtl.py /path/to/folder_or_file")
        sys.exit(1)

    target = Path(sys.argv[1])

    if target.is_file():
        files = [target]
    elif target.is_dir():
        files = list(target.rglob("*.ar.srt")) + list(target.rglob("*.ar.ass"))
    else:
        print(f"Not found: {target}")
        sys.exit(1)

    if not files:
        print("No .ar.srt or .ar.ass files found.")
        sys.exit(0)

    print(f"Found {len(files)} files to fix:")
    total_fixed = 0

    for f in sorted(files):
        if f.suffix == ".srt":
            count = fix_srt_file(f)
        elif f.suffix == ".ass":
            count = fix_ass_file(f)
        else:
            continue
        total_fixed += count
        print(f"  {f.name} — {count} lines fixed")

    print(f"\nDone. {total_fixed} total lines fixed across {len(files)} files.")


if __name__ == "__main__":
    main()
