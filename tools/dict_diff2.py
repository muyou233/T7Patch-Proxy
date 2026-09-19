"""dict_diff 的补充：列出被主过滤丢弃、但**确实不在词库**的串。

主脚本 (dict_diff.py) 会把含 ^ $ & 的串整条丢弃（因为不好当键写进词库），
但词库里其实有一节专门收这类「格式标记片段」。所以这里把丢弃项拿出来，
用「词库键（小写、去首尾空白）」做精确比对，只列出真正缺的，避免重复劳动。

只读，不写词库；结果落到 ref/dict_discarded_missing.txt。
"""
import os

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
DICT = os.path.join(GAME, r"T7Patch\translate_zh.txt")
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\dict_discarded_missing.txt"


def read_lines(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    return raw.split(b"\n")


def strip_wrap(b):
    i, j = 0, len(b)
    while i < j and b[i] <= 0x20:
        i += 1
    while j > i and b[j - 1] <= 0x20:
        j -= 1
    return b[i:j]


keys = set()
for line in read_lines(DICT):
    s = line.lstrip(b" \t")
    if not s or s[:1] in (b"#", b";") or b"=" not in s:
        continue
    k = s.split(b"=", 1)[0].rstrip(b" \t\r")
    if k:
        keys.add(k.lower().decode("utf-8", "replace"))

seen = set()
rows = []
for line in read_lines(DUMP):
    s = strip_wrap(line.rstrip(b"\r"))
    if not s:
        continue
    low = s.lower()
    if low in seen:
        continue
    seen.add(low)
    # 只要有 ^ $ & 就是「格式标记片段」的候选（含非 ASCII/控制字节的仍无法表达）
    if not any(c in b"^$&" for c in s):
        continue
    if any(c >= 0x80 or c < 0x20 for c in s):
        continue
    txt = s.decode("ascii")
    if txt.lower() in keys:
        continue
    rows.append(txt)

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("含格式标记、且词库没有的唯一串：%d 条\n\n" % len(rows))
    fh.write("\n".join(sorted(rows, key=lambda x: (len(x.split()), -len(x)))))
print("written", OUT, "count:", len(rows))
