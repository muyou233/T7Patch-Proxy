# -*- coding: utf-8 -*-
"""包含式扫描：找出 31 个候选名在 dump / 词库里的"近似命中"（含但不等于），
用来发现"看起来是地图名、实际也可能是武器名/其它 UI 串"的情况。
"""
import io

DUMP = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\T7Patch\ui_dump.txt"
DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\mapname_contain.txt"

CAND = ["Aquarium", "Breach", "Combine", "Evac", "Exodus", "Fringe", "Havoc",
        "Hunted", "Infection", "Metro", "Redwood", "Stronghold", "Nuk3town",
        "Rise", "Splash", "Skyjacked", "Gauntlet", "Knockout", "Rift", "Spire",
        "Verge", "Rumble", "Berserk", "Cryogen", "Empire", "Citadel", "Micro",
        "Outlaw", "Rupture", "Redwood Snow", "Fringe Nightfall"]

def load(p):
    with io.open(p, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()

dump, dic = load(DUMP), load(DICT)

# 词库里所有已有的键（含模板键），用于判断会不会撞车
keys = []
for i, ln in enumerate(dic, 1):
    s = ln.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k = s.split("=", 1)[0].strip()
    keys.append((i, k))

o = []
for name in CAND:
    nl = name.lower()
    o.append("=== %s ===" % name)

    # dump 里"含但不等于"
    near = [(i + 1, ln) for i, ln in enumerate(dump)
            if nl in ln.strip().lower() and ln.strip().lower() != nl]
    if near:
        for ln_no, ln in near[:6]:
            o.append("   dump 含: L%-5d %s" % (ln_no, ln))
    else:
        o.append("   dump 含: (无)")

    # 词库已有键里"含该名"（说明别的条目用到过这个词）
    used = [(i, k) for i, k in keys if nl in k.lower() and k.lower() != nl]
    if used:
        for i, k in used[:8]:
            o.append("   词库键含: L%-5d %s" % (i, k))
    else:
        o.append("   词库键含: (无)")
    o.append("")

with io.open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(o))
print("written", OUT)
