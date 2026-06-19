#!/usr/bin/env python3
"""Test: embed Noto Sans Arabic font into an ASS subtitle file."""
from pathlib import Path
import pysubs2
import glob

cands = glob.glob("/usr/share/fonts/**/Amiri-Regular.ttf", recursive=True)
if not cands:
    raise SystemExit("Font not found. Run: find /usr/share/fonts -name '*Amiri*'")
ttf = cands[0]
print("Using font:", ttf)


def ass_encode(data):
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
        for v in vals[: n + 1]:
            buf.append(chr(v + 33))
    s = "".join(buf)
    return [s[i:i + 80] for i in range(0, len(s), 80)]


INPUT = "/mnt/secure/srv/hddmedia/anime/Haikyuu!!/Season 1/Haikyu!! - S01E01.ar.srt"
subs = pysubs2.SSAFile.load(INPUT)
for st in subs.styles.values():
    st.fontname = "Amiri"
    st.encoding = 1
    st.alignment = 2
ass_content = subs.to_string("ass")

font_bytes = Path(ttf).read_bytes()
encoded_lines = ass_encode(font_bytes)
fonts_section = "\n[Fonts]\nfontname: Amiri-Regular_0.ttf\n"
fonts_section += "\n".join(encoded_lines)
fonts_section += "\n"

ass_content = ass_content.rstrip() + "\n" + fonts_section

out = Path(INPUT).parent / (Path(INPUT).stem + "_embedded_amiri.ass")
out.write_text(ass_content, encoding="utf-8")
print("Done:", out)
print("Size:", round(out.stat().st_size / 1024), "KB")
