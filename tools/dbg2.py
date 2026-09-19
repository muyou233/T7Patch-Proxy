"""查证：为什么 ^3[p^7] personalize 这条被判成「采集里找不到原文」。"""
import io
import os
import re

GAME_DUMP = (r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
             r"\T7Patch\ui_dump.txt")
DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
MARK = re.compile(r"\^[0-9A-Za-z]")


def strip_marks(s):
    return MARK.sub("", s)


def trim(s):
    i, j = 0, len(s)
    while i < j and ord(s[i]) <= 0x20:
        i += 1
    while j > i and ord(s[j - 1]) <= 0x20:
        j -= 1
    return s[i:j]


out = []

with io.open(GAME_DUMP, "r", encoding="utf-8", errors="replace", newline="") as fh:
    dump = [trim(l.rstrip("\r\n")) for l in fh]
dump = [d for d in dump if d and not d.lstrip().startswith("#")]

out.append("=== dump 里所有含 personalize 的行（repr）===")
for d in sorted(set(dump)):
    if "personalize" in d.lower():
        out.append("  raw   : %r" % d)
        out.append("  strip : %r" % strip_marks(d).lower())
        out.append("  marks : %r" % [m.group(0) for m in MARK.finditer(d)])

out.append("")
out.append("=== 词库里所有含 personalize 的键（repr）===")
with io.open(DICT, "r", encoding="utf-8", newline="") as fh:
    for ln in fh:
        ln = ln.rstrip("\r\n")
        if "personalize" in ln.lower() and not ln.lstrip().startswith("#"):
            k = trim(ln.split("=", 1)[0])
            out.append("  raw   : %r" % ln)
            out.append("  key   : %r" % k)
            out.append("  strip : %r" % strip_marks(k).lower())
            out.append("  marks : %r" % [m.group(0) for m in MARK.finditer(k)])
            out.append("  -> 逐字符: %s" % " ".join("%02x" % ord(c) for c in k))

txt = "\n".join(out)
print(txt)
