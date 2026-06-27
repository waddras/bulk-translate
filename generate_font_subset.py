#!/usr/bin/env python3
"""Generate subsetted Arabic fonts for ASS embedding.

Run once after install (or whenever you add new fonts):
    python3 generate_font_subset.py

Output: /opt/bulk-translate/fonts/<FontName>-subset.ttf

Requirements: pip install fonttools brotli
"""
from pathlib import Path
from fontTools.subset import Subsetter
from fontTools.ttLib import TTFont
import glob

OUTPUT_DIR = "/opt/bulk-translate/fonts"

# Fonts to subset: (display name, glob pattern for the Regular .ttf)
FONTS = [
    ("Amiri", "/usr/share/fonts/**/Amiri-Regular.ttf"),
    ("IBM Plex Sans Arabic", "/usr/share/fonts/**/IBMPlexSansArabic-Regular.ttf"),
    ("Noto Sans Arabic", "/usr/share/fonts/**/NotoSansArabic-Regular.ttf"),
    ("Cairo", "/usr/share/fonts/**/Cairo*.ttf"),
    ("Tajawal", "/usr/share/fonts/**/Tajawal-Regular.ttf"),
    ("Almarai", "/usr/share/fonts/**/Almarai-Regular.ttf"),
]

# Unicode ranges to keep
UNICODE_RANGES = set(
    list(range(0x0600, 0x06FF + 1)) +  # Arabic
    list(range(0x0750, 0x077F + 1)) +  # Arabic Supplement
    list(range(0xFB50, 0xFDFF + 1)) +  # Arabic Presentation Forms-A
    list(range(0xFE70, 0xFEFF + 1)) +  # Arabic Presentation Forms-B
    list(range(0x0020, 0x007F + 1)) +  # Basic Latin
    list(range(0x2000, 0x206F + 1)) +  # General Punctuation
    [0x200F, 0x202B, 0x202C, 0x2067, 0x2069]  # Bidi marks
)


def subset_font(name, pattern):
    cands = glob.glob(pattern, recursive=True)
    if not cands:
        print(f"  SKIP: {name} — not found ({pattern})")
        return None
    ttf_path = cands[0]
    original_size = Path(ttf_path).stat().st_size

    font = TTFont(ttf_path)
    subsetter = Subsetter()
    subsetter.populate(unicodes=UNICODE_RANGES)
    subsetter.subset(font)

    # Save with sanitized filename
    safe_name = name.replace(" ", "")
    out_path = Path(OUTPUT_DIR) / f"{safe_name}-subset.ttf"
    font.save(str(out_path))
    subset_size = out_path.stat().st_size

    print(f"  {name}: {original_size // 1024} KB -> {subset_size // 1024} KB ({out_path.name})")
    return out_path


def main():
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    print(f"Generating font subsets in {OUTPUT_DIR}/\n")

    generated = []
    for name, pattern in FONTS:
        result = subset_font(name, pattern)
        if result:
            generated.append(name)

    print(f"\nDone. {len(generated)} fonts subsetted: {', '.join(generated)}")


if __name__ == "__main__":
    main()
