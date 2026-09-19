"""词库 QA（只读）：① 检查键在采集里的命中情况（找拼写错）② 行尾/BOM 约定。"""
import os

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
DICT = os.path.join(GAME, r"T7Patch\translate_zh.txt")
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\dict_qa.txt"


def raw(path):
    with open(path, "rb") as fh:
        return fh.read()


def strip_wrap(b):
    i, j = 0, len(b)
    while i < j and b[i] < 0x20:
        i += 1
    while j > i and b[j - 1] < 0x20:
        j -= 1
    return b[i:j]


out = []
for name, p in (("ui_dump.txt", DUMP), ("translate_zh.txt", DICT)):
    b = raw(p)
    out.append("%s: %d B, BOM=%s, CRLF=%d, LF=%d"
               % (name, len(b), b[:3] == b"\xef\xbb\xbf", b.count(b"\r\n"), b.count(b"\n")))

dump_keys = set()
for line in raw(DUMP).split(b"\n"):
    s = strip_wrap(line.rstrip(b"\r"))
    if s and not any(c >= 0x80 for c in s):
        dump_keys.add(s.lower().decode("ascii", "replace"))

out.append("")
out.append("=== 词库里「本次采集没出现」的键（多半是拼写/措辞不对，也可能是这次没浏览到）===")
n = 0
for line in raw(DICT).split(b"\n"):
    s = line.lstrip(b" \t")
    if not s or s[:1] in (b"#", b";") or b"=" not in s:
        continue
    k = s.split(b"=", 1)[0].rstrip(b" \t\r").lower().decode("ascii", "replace")
    if k and k not in dump_keys:
        out.append("  " + k)
        n += 1
out.append("（共 %d 条）" % n)

out.append("")
out.append("=== 词库里重复的键 ===")
seen, dup = set(), []
for line in raw(DICT).split(b"\n"):
    s = line.lstrip(b" \t")
    if not s or s[:1] in (b"#", b";") or b"=" not in s:
        continue
    k = s.split(b"=", 1)[0].rstrip(b" \t\r").lower().decode("ascii", "replace")
    if k in seen:
        dup.append(k)
    seen.add(k)
from collections import Counter
for k, c in Counter(dup).most_common():
    out.append("  %s  x%d" % (k, c + 1))

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("written", OUT)
