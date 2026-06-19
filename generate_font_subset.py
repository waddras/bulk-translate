#!/usr/bin/env python3
"""Generate subsetted Amiri font for ASS embedding.

Run once after install (or whenever you want to regenerate):
    python3 generate_font_subset.py

Output: /opt/bulk-translate/fonts/Amiri-subset.ttf

Requirements: pip install fonttools brotli
"""
from pathlib import Path
from fontTools.subset import Subsetter
from fontTools.ttLib import TTFont
import glob

OUTPUT_DIR = "/opt/bulk-translate/fonts"
OUTPUT_FILE = f"{OUTPUT_DIR}/Amiri-subset.ttf"

# Find Amiri font
cands = glob.glob("/usr/share/fonts/**/Amiri-Regular.ttf", recursive=True)
if not cands:
    raise SystemExit(
        "Amiri-Regular.ttf not found.\n"
        "Install it: apt install fonts-hosny-amiri\n"
        "Or: find /usr/share/fonts -name '*Amiri*'"
    )
ttf_path = cands[0]
print(f"Source font: {ttf_path}")
print(f"Original size: {Path(ttf_path).stat().st_size // 1024} KB")

# Subset: Arabic + Latin + punctuation + bidi marks
font = TTFont(ttf_path)
subsetter = Subsetter()
subsetter.populate(unicodes=set(
    list(range(0x0600, 0x06FF + 1)) +  # Arabic
    list(range(0x0750, 0x077F + 1)) +  # Arabic Supplement
    list(range(0xFB50, 0xFDFF + 1)) +  # Arabic Presentation Forms-A
    list(range(0xFE70, 0xFEFF + 1)) +  # Arabic Presentation Forms-B
    list(range(0x0020, 0x007F + 1)) +  # Basic Latin
    list(range(0x2000, 0x206F + 1)) +  # General Punctuation
    [0x200F, 0x202B, 0x202C, 0x2067, 0x2069]  # Bidi marks
))
subsetter.subset(font)

# Save
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
font.save(OUTPUT_FILE)
size = Path(OUTPUT_FILE).stat().st_size // 1024
print(f"Subset saved: {OUTPUT_FILE}")
print(f"Subset size: {size} KB")
