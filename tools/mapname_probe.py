# -*- coding: utf-8 -*-
"""逐个核对候选地图名的上下文：在 ui_dump.txt 里出现的位置 + 邻居行。
目的：区分"纯地图名"和"同时被武器/其它 UI 使用的名字"。
"""
import io, os, re

DUMP = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\T7Patch\ui_dump.txt"
DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\mapname_probe.txt"

CAND = [
    # 基础图（截图里那一列）
    "Aquarium", "Breach", "Combine", "Evac", "Exodus", "Fringe", "Havoc",
    "Hunted", "Infection", "Metro", "Redwood", "Stronghold", "Nuk3town",
    # DLC 图
    "Rise", "Splash", "Skyjacked", "Gauntlet", "Knockout", "Rift", "Spire",
    "Verge", "Rumble", "Berserk", "Cryogen", "Empire", "Citadel", "Micro",
    "Outlaw", "Rupture",
    # 变体
    "Redwood Snow", "Fringe Nightfall",
]

def load(path):
    with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()

dump = load(DUMP)
dic = load(DICT)

keys = {}
for i, ln in enumerate(dic, 1):
    s = ln.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k = s.split("=", 1)[0].strip().lower()
    keys.setdefault(k, (i, s))

o = []
o.append("dump lines = %d" % len(dump))
o.append("dict keys  = %d" % len(keys))
o.append("")

for name in CAND:
    nl = name.lower()
    hits = [i for i, ln in enumerate(dump) if ln.strip().lower() == nl]
    o.append("=== %s   (dump 精确命中 %d 处) ===" % (name, len(hits)))
    if nl in keys:
        o.append("  [词库已有] 行 %d: %s" % keys[nl])
    else:
        o.append("  [词库无]")
    for h in hits[:8]:
        lo, hi = max(0, h - 3), min(len(dump), h + 4)
        o.append("  --- dump line %d ---" % (h + 1))
        for j in range(lo, hi):
            mark = ">>" if j == h else "  "
            o.append("   %s %s" % (mark, dump[j]))
    if len(hits) > 8:
        o.append("  ... 其余 %d 处省略" % (len(hits) - 8))
    o.append("")

with io.open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(o))
print("written", OUT)
