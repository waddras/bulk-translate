#!/usr/bin/env python3
"""Test: embed subsetted Amiri font (Arabic + Latin punct only) into ASS."""
from pathlib import Path
from fontTools.subset import Subsetter
from fontTools.ttLib import TTFont
import pysubs2
import glob
import tempfile

# Find Amiri
cands = glob.glob("/usr/share/fonts/**/Amiri-Regular.ttf", recursive=True)
if not cands:
    raise SystemExit("Amiri not found. Run: find /usr/share/fonts -name '*Amiri*'")
ttf_path = cands[0]

# Subset: keep Arabic block + basic Latin punctuation + digits
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
print(f"Original: {Path(ttf_path).stat().st_size // 1024} KB")
print(f"Subset:   {len(subset_bytes) // 1024} KB")


# ASS encode
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


INPUT = "/mnt/secure/srv/hddmedia/anime/Haikyuu!!/Season 1/Haikyu!! - S01E01.ar.srt"
subs = pysubs2.SSAFile.load(INPUT)
for st in subs.styles.values():
    st.fontname = "Amiri"
    st.fontsize = 40
    st.encoding = 1
    st.alignment = 2
    st.shadow = 0
    st.outline = 0
ass_content = subs.to_string("ass")

encoded_lines = ass_encode(subset_bytes)
fonts_section = "\n[Fonts]\nfontname: Amiri-Regular_0.ttf\n"
fonts_section += "\n".join(encoded_lines)
fonts_section += "\n"
ass_content = ass_content.rstrip() + "\n" + fonts_section

out = Path(INPUT).parent / (Path(INPUT).stem + "_subset_amiri.ass")
out.write_text(ass_content, encoding="utf-8")
print(f"Output:   {out.stat().st_size // 1024} KB")
print("Done:", out)
