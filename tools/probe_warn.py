# -*- coding: utf-8 -*-
r"""Probe the deployed dll for the start-up notice, and for the old wording.

Wide literals land in the binary as UTF-16LE, narrow ones as ASCII/UTF-8, so
each needle is searched in both encodings.  The rollback copy (.bak) is checked
too: proving the OLD wording is still in there is what makes the "old wording
gone" result meaningful rather than a broken search.
"""
import io, os

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
NEW = os.path.join(GAME, "d3d11.dll")
OLD = os.path.join(GAME, "d3d11.dll.bak")

MUST_BE_PRESENT = [
    "T7 Patch 未能启动",
    "原因：%ls",
    "补丁版本 %hs；详细记录",
    "验证游戏文件的完整性",
    "unsupported Black Ops III build (timestamp 0x%08X, image size 0x%08X)",
    "proxy: %s, T7Patch not applied",
    "BlackOps3.exe",
    "T7 Patch could not start",
]

MUST_BE_GONE = [
    "unsupported executable, T7Patch not applied",
]


def has(haystack, text):
    hits = []
    for enc in ("utf-16-le", "utf-8"):
        try:
            if text.encode(enc) in haystack:
                hits.append(enc)
        except UnicodeEncodeError:
            pass
    return hits


new = io.open(NEW, "rb").read()
old = io.open(OLD, "rb").read() if os.path.exists(OLD) else b""

lines = ["new = %s (%d bytes)" % (os.path.basename(NEW), len(new)),
         "old = %s (%d bytes)" % (os.path.basename(OLD), len(old)), ""]

ok = True
lines.append("== must be present in the deployed dll ==")
for text in MUST_BE_PRESENT:
    enc = has(new, text)
    lines.append("   %-62s %s" % (text[:60], ",".join(enc) if enc else "MISSING"))
    if not enc:
        ok = False

lines.append("")
lines.append("== must be gone from the deployed dll ==")
for text in MUST_BE_GONE:
    enc = has(new, text)
    old_enc = has(old, text)
    lines.append("   %-62s new=%s  old=%s" % (
        text[:60], ",".join(enc) if enc else "gone", ",".join(old_enc) if old_enc else "gone"))
    if enc:
        ok = False

lines.append("")
lines.append("RESULT: " + ("OK" if ok else "FAIL"))
io.open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\probe_warn.txt",
        "w", encoding="utf-8").write("\n".join(lines))
print("done")
