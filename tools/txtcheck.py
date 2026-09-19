"""回答"txt 词库真的没问题吗"：把几个隐性约束实测一遍。
1. 采集到的串里有含 '=' 的吗（含 '=' 的串在词库里没法表达，会被第一个 '=' 截断）
2. 词库最长行 / 最长键（fgets 缓冲 1024、Lookup 里 key 缓冲 1024）
3. 词库 BOM / 行尾约定现状
4. 键里有没有非 ASCII（不该有）
"""
import os

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
DICT = os.path.join(GAME, r"T7Patch\translate_zh.txt")
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\txtcheck.txt"

runs, seen = [], set()
for ln in open(DUMP, "rb").read().split(b"\n"):
    b = ln.rstrip(b"\r")
    i, j = 0, len(b)
    while i < j and b[i] <= 0x20:
        i += 1
    while j > i and b[j - 1] <= 0x20:
        j -= 1
    b = b[i:j]
    if not b or any(c >= 0x80 for c in b) or any(c < 0x20 for c in b):
        continue
    if b not in seen:
        seen.add(b)
        runs.append(b)

with_eq = [r for r in runs if b"=" in r]

db = open(DICT, "rb").read()
lines = db.split(b"\n")
maxline, maxkey, eqkey, nonascii_key, empty_val = 0, 0, [], [], 0
entries = 0
for ln in lines:
    s = ln.rstrip(b"\r")
    if not s.strip() or s.lstrip()[:1] in (b"#", b";"):
        continue
    maxline = max(maxline, len(s))
    if b"=" not in s:
        continue
    k, v = s.split(b"=", 1)
    entries += 1
    maxkey = max(maxkey, len(k.strip()))
    if not v.strip():
        empty_val += 1
    if any(c >= 0x80 for c in k):
        nonascii_key.append(k)
    if b"=" in k:
        eqkey.append(k)

o = []
o.append("采集唯一干净串 %d 条；其中含 '=' 的 %d 条 %s" % (len(runs), len(with_eq), with_eq[:5]))
o.append("词库条目 %d 条；最长行 %d B（fgets 1024）；最长键 %d B（Lookup key 缓冲 1024）" % (entries, maxline, maxkey))
o.append("键里含 '=' 的 %d 条；键含非 ASCII 的 %d 条；空值 %d 条" % (len(eqkey), len(nonascii_key), empty_val))
o.append("BOM=%s  CRLF=%d  LF=%d" % (db[:3] == b"\xef\xbb\xbf", db.count(b"\r\n"), db.count(b"\n")))
o.append("首行是注释吗：%s" % (lines[0].strip()[:1] == b"#"))
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(o))
print("written", OUT)
