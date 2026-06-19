#!/usr/bin/env python3
"""
Test: embed subsetted Amiri font into ASS subtitle file.

Usage:
    python3 test_embed_amiri_subset.py

Requirements:
    pip install fonttools brotli pysubs2

Output:
    Creates a .ass file next to the input with embedded Arabic font.

=== FONT STYLE SETTINGS ===
Edit the values below to customize subtitle appearance.
"""
from pathlib import Path
from fontTools.subset import Subsetter
from fontTools.ttLib import TTFont
import pysubs2
import glob
import tempfile

# ╔══════════════════════════════════════════════════════════════════╗
# ║  EDIT THESE VALUES TO CUSTOMIZE SUBTITLE APPEARANCE            ║
# ╚══════════════════════════════════════════════════════════════════╝

INPUT = "/mnt/secure/srv/hddmedia/anime/Haikyuu!!/Season 1/Haikyu!! - S01E01.ar.srt"

FONT_NAME = "Amiri"          # Font family name (must match embedded font)
FONT_SIZE = 40               # Font size in pixels
ENCODING = 1                 # 1 = Default (let renderer decide direction)
ALIGNMENT = 2                # 1=left 2=center 3=right (bottom row)
                             # 4=left 5=center 6=right (middle row)
                             # 7=left 8=center 9=right (top row)

OUTLINE = 1                  # Outline thickness (0 = no outline)
SHADOW = 0                   # Shadow depth (0 = no shadow)
BOLD = False                 # Bold text
ITALIC = False               # Italic text

# Colors in ASS format: &HAABBGGRR (hex, alpha-blue-green-red)
PRIMARY_COLOR = "&H00FFFFFF"   # Main text color (white)
SECONDARY_COLOR = "&H0000FFFF" # Secondary color (yellow, used for karaoke)
OUTLINE_COLOR = "&H00000000"   # Outline color (black)
BACK_COLOR = "&H00000000"      # Shadow/background color (black)

# Margins (distance from screen edge in pixels)
MARGIN_LEFT = 20
MARGIN_RIGHT = 20
MARGIN_VERTICAL = 30          # Bottom margin (or top if alignment is 7/8/9)

# ╔══════════════════════════════════════════════════════════════════╗
# ║  END OF SETTINGS — no need to edit below this line             ║
# ╚══════════════════════════════════════════════════════════════════╝

# Find Amiri font file
cands = glob.glob("/usr/share/fonts/**/Amiri-Regular.ttf", recursive=True)
if not cands:
    raise SystemExit("Amiri not found. Run: find /usr/share/fonts -name '*Amiri*'")
ttf_path = cands[0]
print(f"Using font: {ttf_path}")

# Subset font to Arabic + Latin only
font = TTFont(ttf_path)
subsetter = Subsetter()
subsetter.populate(unicodes=set(
    list(range(0x0600, 0x06FF + 1)) +  # Arabic
    list(range(0x0750, 0x077F + 1)) +  # Arabic Supplement
    list(range(0xFB50, 0xFDFF + 1)) +  # Arabic Presentation Forms-A
    list(range(0xFE70, 0xFEFF + 1)) +  # Arabic Presentation Forms-B
    list(range(0x0020, 0x007F + 1)) +  # Basic Latin (punct, digits, letters)
    list(range(0x2000, 0x206F + 1)) +  # General Punctuation
    [0x200F, 0x202B, 0x202C, 0x2067, 0x2069]  # Bidi marks
))
subsetter.subset(font)
tmp = tempfile.NamedTemporaryFile(suffix=".ttf", delete=False)
font.save(tmp.name)
tmp.close()
subset_bytes = Path(tmp.name).read_bytes()
print(f"Original font: {Path(ttf_path).stat().st_size // 1024} KB")
print(f"Subset font:   {len(subset_bytes) // 1024} KB")


# ASS UUEncode for font embedding
def ass_encode(data):
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


# Load subtitle and apply style settings
subs = pysubs2.SSAFile.load(INPUT)
for st in subs.styles.values():
    st.fontname = FONT_NAME
    st.fontsize = FONT_SIZE
    st.encoding = ENCODING
    st.alignment = ALIGNMENT
    st.outline = OUTLINE
    st.shadow = SHADOW
    st.bold = BOLD
    st.italic = ITALIC
    st.primarycolor = pysubs2.Color.from_ass(PRIMARY_COLOR)
    st.secondarycolor = pysubs2.Color.from_ass(SECONDARY_COLOR)
    st.outlinecolor = pysubs2.Color.from_ass(OUTLINE_COLOR)
    st.backcolor = pysubs2.Color.from_ass(BACK_COLOR)
    st.marginl = MARGIN_LEFT
    st.marginr = MARGIN_RIGHT
    st.marginv = MARGIN_VERTICAL

ass_content = subs.to_string("ass")

# Embed the subsetted font
encoded_lines = ass_encode(subset_bytes)
fonts_section = "\n[Fonts]\nfontname: Amiri-Regular_0.ttf\n"
fonts_section += "\n".join(encoded_lines)
fonts_section += "\n"
ass_content = ass_content.rstrip() + "\n" + fonts_section

# Write output
out = Path(INPUT).parent / (Path(INPUT).stem + "_subset_amiri.ass")
out.write_text(ass_content, encoding="utf-8")
print(f"Output file: {out.stat().st_size // 1024} KB")
print(f"Done: {out}")
