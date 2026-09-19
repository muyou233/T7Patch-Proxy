"""打印某个候选串在 dump 里的所有原始变体（repr），看清重复到底差在哪。"""
import os
import re

DUMP = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\T7Patch\ui_dump.txt"
NEEDLE = "bo3 workshop stack (experimental)"

raw = open(DUMP, "rb").read()
if raw[:3] == b"\xef\xbb\xbf":
    raw = raw[3:]

hits = []
for line in raw.split(b"\n"):
    s = line.rstrip(b"\r")
    t = s.strip(b" \t")
    if not t:
        continue
    txt = t.decode("ascii", "replace")
    if re.sub(r"\s+", " ", txt).strip().lower() == NEEDLE:
        hits.append(txt)

print("variants:", len(hits))
for h in hits:
    print("  %r  (len=%d)" % (h, len(h)))
