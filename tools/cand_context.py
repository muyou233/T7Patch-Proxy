# -*- coding: utf-8 -*-
r"""Context for the 30 "interface text candidates" + the ambiguous extras.

Same idea as review_context.py: the neighbours in the flat dump are what tells
us which screen a string belongs to, and that decides whether it is interface
text (translate) or a player name / map name / folder name (keep as-is).
"""
import io

DUMP = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\T7Patch\ui_dump.txt"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\cand_context.txt"

ITEMS = [
    # the 30 from the work list
    "ELIMINATIONS", "XDCROAZZY", "STOOPID", "Zombie Elimination",
    "Weapon Obtained", "CRITICAL KILLS", "Weapon Shared", "Perk Acquired",
    "G11: KABOOM!", "PING: 10", "PING: 11", "PING: 9", "PING: 8",
    "Zombie Explosive Kill", "Zombie Headshot Kill", "Zombie Melee Kill",
    "Ulises Damian Qu", "P90: I'm downed!", "G11: I'm downed!",
    "Minecraft by Scriptwo 2", "Minecraft Shi No Numa", "I'm the king of",
    "P90: I got the KAP-40.", "G11: I got the SVU-AS.",
    "G11: I shared a KAP-40 here.", "P90: I shared a M1216 here.",
    "G11: I got a new perk.", "Shi No Numa in minecraft style. Have fun!",
    "A minecraft theme map made by Scriptwo !",
    "This map was entirely made by me, in terms of mapping. Gameplay features, scripting and",
]

lines = io.open(DUMP, "r", encoding="utf-8", errors="replace").read().split("\n")
stripped = [ln.strip() for ln in lines]

out = ["dump: %s" % DUMP, "lines: %d" % len(lines), ""]

for item in ITEMS:
    hits = [i for i, s in enumerate(stripped) if s == item]
    mode = "整行"
    if not hits:
        hits = [i for i, s in enumerate(stripped) if item in s]
        mode = "子串"
    out.append("### %s   (%d 处, %s)" % (item, len(hits), mode))
    if not hits:
        out.append("    <找不到>")
        out.append("")
        continue
    lo_all = min(hits)
    lo = max(0, lo_all - 6)
    hi = min(len(lines), lo_all + 7)
    for i in range(lo, hi):
        mark = "  <<<" if i in hits else ""
        out.append("   %5d | %s%s" % (i + 1, lines[i], mark))
    out.append("")

io.open(OUT, "w", encoding="utf-8").write("\n".join(out))
print("written", OUT)
