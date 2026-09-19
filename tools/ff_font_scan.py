"""只读扫 fastfile：找字体/字形资产名，并统计英文包里有没有 CJK 字节。
快版本：直接对关键字做 bytes.find，命中处取一段 ASCII 窗口，不做全文正则。"""
import mmap
import os
import re

CJK = re.compile(b"[\xe4-\xe9][\x80-\xbf][\x80-\xbf]")

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
ZONE = os.path.join(GAME, "zone")
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\ff_font_scan.txt"

FILES = [
    "en_core_frontend.ff",
    "en_core_ui.ff",
    "en_core_common.ff",
    "core_frontend.ff",
    "core_frontend.xpak",
    "en_core_frontend.xpak",
]

KEYWORDS = [b"font", b".ttf", b".otf", b"glyph", b"/fonts", b"fonts/", b"codfont"]

out = []
for name in FILES:
    path = os.path.join(ZONE, name)
    if not os.path.exists(path):
        out.append("MISSING %s" % name)
        continue
    size = os.path.getsize(path)
    hits = {}
    with open(path, "rb") as fh:
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        for kw in KEYWORDS:
            start = 0
            n = 0
            while n < 400:
                at = mm.find(kw, start)
                if at < 0:
                    break
                a, b = at - 40, at + 60
                if a < 0:
                    a = 0
                if b > len(mm):
                    b = len(mm)
                win = bytes(mm[a:b])
                txt = "".join(chr(c) if 0x20 <= c <= 0x7E else "." for c in win)
                key = (kw.decode(), txt)
                if key not in hits:
                    hits[key] = at
                start = at + 1
                n += 1
        # 英文包里有没有汉字（UTF-8 三字节，近似；一次正则过一遍）
        cjk = len(CJK.findall(mm))
        mm.close()
    out.append("=== %s  %s B  字体类命中 %d 条  近似 CJK 字节对计数 %d ===" %
               (name, format(size, ","), len(hits), cjk))
    for (kw, txt), at in list(hits.items())[:25]:
        out.append("   [%s @%d] %s" % (kw, at, txt))

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("written", OUT)
